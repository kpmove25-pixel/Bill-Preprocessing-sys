"""任务编排服务：文件处理流水线 + 去重 + 归档 + 导出。"""
from __future__ import annotations

import datetime
import logging
import os
import shutil
import uuid
from typing import List, Optional

from app.core.config import FAILED_DIR, OUTPUT_DIR, UPLOAD_DIR, settings
from app.core.database import SessionLocal
from app.models import AuditLog, FileRecord, Invoice, InvoiceLedger, Task
from app.services import archive_service, dedup_service, image_service, ledger_service, pdf_service
from app.services.ocr_service import OcrBlock, get_ocr_engine
from app.services.parser_service import parser_service
from app.utils.file_utils import ext_lower, safe_join

logger = logging.getLogger(__name__)

IMAGE_EXTS = image_service.SUPPORTED_IMAGE_EXTS
PDF_EXTS = {"pdf"}


def new_task_id() -> str:
    return datetime.datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6]


def _invoice_to_dict(inv: Invoice) -> dict:
    cols = [
        "id", "invoice_code", "invoice_no", "invoice_type", "buyer_name",
        "buyer_tax_no", "seller_name", "seller_tax_no", "amount",
        "amount_excluding_tax", "tax_amount", "tax_rate", "invoice_date",
        "check_code", "drawer", "original_filename", "jpg_path",
        "ocr_confidence", "status", "remark",
    ]
    d = {c: getattr(inv, c) for c in cols}
    d["dedup_key"] = inv.dedup_key
    return d


def create_task(filenames: List[str]) -> str:
    """创建任务并初始化目录。"""
    task_id = new_task_id()
    with SessionLocal() as db:
        task = Task(task_id=task_id, status="pending", total_files=len(filenames))
        db.add(task)
        db.commit()
    for sub in ("original", "jpg"):
        os.makedirs(safe_join(UPLOAD_DIR, task_id, sub), exist_ok=True)
    return task_id


def _update_task(task_id: str, **kwargs):
    with SessionLocal() as db:
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task:
            for k, v in kwargs.items():
                setattr(task, k, v)
            task.updated_at = datetime.datetime.utcnow()
            db.commit()


def process_file(task_id: str, original_path: str) -> dict:
    """处理单个文件，返回该文件产生的发票 dict 列表。

    单个文件失败不影响任务整体。
    """
    ext = ext_lower(original_path)
    stem = os.path.splitext(os.path.basename(original_path))[0]
    invoices: List[dict] = []
    engine = get_ocr_engine()

    try:
        if ext in PDF_EXTS:
            invoices = _process_pdf(task_id, original_path, stem, engine)
        elif ext in IMAGE_EXTS:
            invoices = _process_image(task_id, original_path, stem, engine)
        else:
            raise ValueError(f"不支持的文件类型: .{ext}")
        return {"ok": True, "invoices": invoices, "error": ""}
    except Exception as e:  # noqa: BLE001
        logger.exception("处理文件失败 %s", original_path)
        _move_to_failed(task_id, original_path, str(e))
        return {"ok": False, "invoices": [], "error": str(e)}


def _process_image(task_id, original_path, stem, engine) -> List[dict]:
    jpg_dir = safe_join(UPLOAD_DIR, task_id, "jpg")
    jpg_path = os.path.join(jpg_dir, f"{stem}.jpg")
    image_service.convert_to_jpg(original_path, jpg_path)
    blocks = engine.recognize(jpg_path)
    return [_save_invoice(task_id, original_path, jpg_path, blocks, page_no=1)]


def _process_pdf(task_id, original_path, stem, engine) -> List[dict]:
    pages = pdf_service.extract_pdf_pages(original_path)
    if not pages:
        return []
    jpg_dir = safe_join(UPLOAD_DIR, task_id, "jpg")
    invoices: List[dict] = []
    for page in pages:
        jpg_path = os.path.join(jpg_dir, f"{stem}_page{page.page_no}.jpg")
        if page.has_text_layer:
            # 电子 PDF 优先用文本层
            blocks: List[OcrBlock] = page.text_blocks
            _render_single_page(original_path, page.page_no, jpg_path)
        else:
            # 扫描 PDF：转图片 + OCR
            _render_single_page(original_path, page.page_no, jpg_path)
            blocks = engine.recognize(jpg_path)
        invoices.append(
            _save_invoice(task_id, original_path, jpg_path, blocks, page_no=page.page_no)
        )
    return invoices


def _render_single_page(pdf_path: str, page_no: int, out_path: str):
    import fitz

    with fitz.open(pdf_path) as doc:
        page = doc[page_no - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        pix.save(out_path)


def _save_invoice(
    task_id: str,
    original_path: str,
    jpg_path: Optional[str],
    blocks: List[OcrBlock],
    page_no: int,
) -> dict:
    parsed = parser_service.parse(blocks)
    ocr_conf = str(parsed.ocr_confidence)

    if parsed.ocr_confidence < settings.ocr_confidence_threshold:
        parsed.needs_review = True
        parsed.remarks.append(f"OCR 置信度低于阈值 {settings.ocr_confidence_threshold}")

    status = "needs_review" if parsed.needs_review else "pending"
    remark = "；".join(parsed.remarks)

    with SessionLocal() as db:
        inv = Invoice(
            task_id=task_id,
            invoice_code=parsed.invoice_code,
            invoice_no=parsed.invoice_no,
            invoice_type=parsed.invoice_type,
            buyer_name=parsed.buyer_name,
            buyer_tax_no=parsed.buyer_tax_no,
            seller_name=parsed.seller_name,
            seller_tax_no=parsed.seller_tax_no,
            amount=parsed.amount,
            amount_excluding_tax=parsed.amount_excluding_tax,
            tax_amount=parsed.tax_amount,
            tax_rate=parsed.tax_rate,
            invoice_date=parsed.invoice_date,
            check_code=parsed.check_code,
            drawer=parsed.drawer,
            original_filename=os.path.basename(original_path),
            jpg_path=jpg_path or "",
            ocr_text="\n".join(b.text for b in blocks),
            ocr_confidence=ocr_conf,
            status=status,
            need_review=parsed.needs_review,
            remark=remark,
        )
        db.add(inv)
        db.commit()
        db.refresh(inv)
        return _invoice_to_dict(inv)


def _move_to_failed(task_id: str, original_path: str, error: str):
    failed_dir = safe_join(FAILED_DIR, task_id)
    os.makedirs(failed_dir, exist_ok=True)
    dst = os.path.join(failed_dir, os.path.basename(original_path))
    if os.path.exists(original_path):
        shutil.move(original_path, dst)
    with SessionLocal() as db:
        fr = FileRecord(
            task_id=task_id,
            original_path=original_path,
            file_type=ext_lower(original_path),
            status="failed",
            error_message=error,
        )
        db.add(fr)
        db.commit()


def process_task(task_id: str):
    """处理整个任务：遍历原始文件 → 处理 → 去重 → 归档。"""
    # 延迟导入避免循环依赖（worker 在运行时会先加载完成）
    from app.workers import worker as _worker

    _update_task(task_id, status="processing")
    original_dir = safe_join(UPLOAD_DIR, task_id, "original")
    files = sorted(
        f for f in os.listdir(original_dir)
        if os.path.isfile(os.path.join(original_dir, f))
    )
    success = 0
    failed = 0
    for i, fname in enumerate(files, start=1):
        if _worker.is_cancelled(task_id):
            _update_task(task_id, status="cancelled")
            logger.info("任务 %s 已被取消，停止处理", task_id)
            return
        path = os.path.join(original_dir, fname)
        result = process_file(task_id, path)
        if result["ok"]:
            success += len(result["invoices"])
        else:
            failed += 1
        _update_task(
            task_id,
            processed_files=i,
            success_count=success,
            failed_count=failed,
        )

    if _worker.is_cancelled(task_id):
        _update_task(task_id, status="cancelled")
        logger.info("任务 %s 已被取消，停止归档", task_id)
        return

    # 去重 + 归档
    dup_count = finalize_task(task_id)
    _update_task(task_id, status="done", duplicate_count=dup_count)
    logger.info("任务 %s 处理完成：成功 %d，失败 %d，重复 %d", task_id, success, failed, dup_count)


def finalize_task(task_id: str) -> int:
    """去重 + 台账查历史 + 归档，返回重复数量（含历史重复）。"""
    with SessionLocal() as db:
        invoices = db.query(Invoice).filter(Invoice.task_id == task_id).all()
        inv_dicts = [_invoice_to_dict(i) for i in invoices]

    keep, dups = dedup_service.deduplicate(inv_dicts)

    # 台账查历史：把 keep 拆成「最终保留」和「历史重复」
    final_keep, historical_dups = ledger_service.find_history(keep, task_id)

    # 写回标记
    with SessionLocal() as db:
        for d in dups:
            inv = db.query(Invoice).filter(Invoice.id == d["id"]).first()
            if inv:
                inv.is_duplicate = True
                inv.duplicate_of = str(d["duplicate_of"])
        for h in historical_dups:
            inv = db.query(Invoice).filter(Invoice.id == h["id"]).first()
            if inv:
                inv.is_duplicate = True
                inv.duplicate_of = f"ledger:{h['dedup_key']}"
                src = h.get("historical_source", "")
                prefix = f"历史重复，首次处理于任务 {src}"
                inv.remark = (inv.remark + "；" + prefix) if inv.remark else prefix
        for k in final_keep:
            inv = db.query(Invoice).filter(Invoice.id == k["id"]).first()
            if inv:
                inv.is_duplicate = False
                inv.duplicate_of = ""
                inv.dedup_key = k["dedup_key"]
        db.commit()

    # 归档（仅保留非重复、非历史重复）
    archive_service.archive_task(task_id, final_keep)

    # 写入台账（幂等 upsert）
    ledger_service.record(final_keep, task_id)

    # 生成重复报告（任务内重复 + 历史重复）
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dup_report = []
    with SessionLocal() as db:
        for d in dups:
            kept = db.query(Invoice).filter(Invoice.id == d["duplicate_of"]).first()
            dup_report.append({
                "invoice_no": d.get("invoice_no", ""),
                "invoice_code": d.get("invoice_code", ""),
                "invoice_type": d.get("invoice_type", ""),
                "buyer_name": d.get("buyer_name", ""),
                "buyer_tax_no": d.get("buyer_tax_no", ""),
                "kept_file": kept.original_filename if kept else "",
                "skipped_file": d.get("original_filename", ""),
                "processed_at": now,
            })
    for h in historical_dups:
        dup_report.append({
            "invoice_no": h.get("invoice_no", ""),
            "invoice_code": h.get("invoice_code", ""),
            "invoice_type": h.get("invoice_type", ""),
            "buyer_name": h.get("buyer_name", ""),
            "buyer_tax_no": h.get("buyer_tax_no", ""),
            "kept_file": f"历史记录（任务 {h.get('historical_source', '')}）",
            "skipped_file": h.get("original_filename", ""),
            "processed_at": now,
        })
    archive_service.generate_duplicate_report(task_id, dup_report)
    return len(dups) + len(historical_dups)


def export_task(task_id: str) -> int:
    """人工校正后重新去重、重新归档、重新导出 Excel。"""
    return finalize_task(task_id)


def retry_failed(task_id: str) -> int:
    """重试失败文件。"""
    failed_dir = safe_join(FAILED_DIR, task_id)
    if not os.path.isdir(failed_dir):
        return 0
    original_dir = safe_join(UPLOAD_DIR, task_id, "original")
    os.makedirs(original_dir, exist_ok=True)
    retried = 0
    for fname in os.listdir(failed_dir):
        src = os.path.join(failed_dir, fname)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(original_dir, fname)
        shutil.move(src, dst)
        result = process_file(task_id, dst)
        if result["ok"]:
            retried += len(result["invoices"])
    finalize_task(task_id)
    return retried


def delete_task(task_id: str):
    """删除任务及数据。"""
    for base, sub in (
        (UPLOAD_DIR, ""),
        (OUTPUT_DIR, ""),
        (FAILED_DIR, ""),
    ):
        p = safe_join(base, task_id) if sub == "" else safe_join(base, task_id, sub)
        if os.path.exists(p):
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                os.remove(p)
    # zip
    z = os.path.join(OUTPUT_DIR, f"{task_id}.zip")
    if os.path.exists(z):
        os.remove(z)
    with SessionLocal() as db:
        db.query(Invoice).filter(Invoice.task_id == task_id).delete()
        db.query(FileRecord).filter(FileRecord.task_id == task_id).delete()
        db.query(AuditLog).filter(AuditLog.task_id == task_id).delete()
        db.query(Task).filter(Task.task_id == task_id).delete()
        # 同步清理台账：删除首次登记自本任务的号码，避免残留孤儿记录导致后续误判历史重复
        db.query(InvoiceLedger).filter(InvoiceLedger.first_task_id == task_id).delete()
        db.commit()
