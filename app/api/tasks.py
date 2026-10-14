"""任务相关路由：上传、列表、详情、导出、下载、去重、重试、删除。"""
from __future__ import annotations

import datetime
import os
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import require_auth
from app.core.config import OUTPUT_DIR, UPLOAD_DIR, settings
from app.core.database import get_db
from app.models import Invoice, Task
from app.schemas.schemas import (
    DuplicateOut,
    InvoiceOut,
    MessageResponse,
    TaskOut,
    UploadResponse,
)
from app.services import archive_service, task_service
from app.services.image_service import SUPPORTED_IMAGE_EXTS
from app.utils.file_utils import ext_lower, safe_join
from app.utils.rar_utils import extract_rar
from app.utils.zip_utils import extract_zip
from app.workers import worker

router = APIRouter(prefix="/api/tasks", tags=["tasks"], dependencies=[Depends(require_auth)])

ALLOWED_EXTS = SUPPORTED_IMAGE_EXTS | {"pdf", "zip", "rar"}
PROCESSABLE_EXTS = SUPPORTED_IMAGE_EXTS | {"pdf"}


@router.post("/upload", response_model=UploadResponse)
async def upload(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="未选择文件")

    # 收集可处理文件（zip 解压成其中的图片/PDF）
    collected: List[tuple] = []
    for f in files:
        ext = ext_lower(f.filename or "")
        data = await f.read()
        if len(data) > settings.max_upload_size:
            raise HTTPException(status_code=400, detail=f"文件过大: {f.filename}")
        if ext == "zip":
            try:
                extracted = extract_zip(data, PROCESSABLE_EXTS, settings.max_upload_size)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            if not extracted:
                raise HTTPException(
                    status_code=400, detail=f"压缩包内没有可处理的图片或 PDF: {f.filename}"
                )
            collected.extend(extracted)
        elif ext == "rar":
            try:
                extracted = extract_rar(data, PROCESSABLE_EXTS, settings.max_upload_size)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            if not extracted:
                raise HTTPException(
                    status_code=400, detail=f"压缩包内没有可处理的图片或 PDF: {f.filename}"
                )
            collected.extend(extracted)
        elif ext in PROCESSABLE_EXTS:
            collected.append((os.path.basename(f.filename or "unnamed"), data))
        else:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {f.filename}")

    task_id = task_service.create_task([name for name, _ in collected])
    original_dir = safe_join(UPLOAD_DIR, task_id, "original")
    os.makedirs(original_dir, exist_ok=True)

    for name, data in collected:
        with open(os.path.join(original_dir, name), "wb") as out:
            out.write(data)

    worker.submit_task(task_id)
    return UploadResponse(task_id=task_id, file_count=len(collected))


@router.get("", response_model=List[TaskOut])
def list_tasks(db=Depends(get_db)):
    tasks = db.query(Task).order_by(Task.created_at.desc()).all()
    return tasks


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: str, db=Depends(get_db)):
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("/{task_id}/invoices", response_model=List[InvoiceOut])
def list_invoices(
    task_id: str,
    status: str = None,
    buyer_name: str = None,
    invoice_no: str = None,
    db=Depends(get_db),
):
    q = db.query(Invoice).filter(Invoice.task_id == task_id)
    if status:
        q = q.filter(Invoice.status == status)
    if buyer_name:
        q = q.filter(Invoice.buyer_name.like(f"%{buyer_name}%"))
    if invoice_no:
        q = q.filter(Invoice.invoice_no.like(f"%{invoice_no}%"))
    return q.order_by(Invoice.id.asc()).all()


@router.get("/{task_id}/duplicates", response_model=List[DuplicateOut])
def list_duplicates(task_id: str, db=Depends(get_db)):
    dups = (
        db.query(Invoice)
        .filter(Invoice.task_id == task_id, Invoice.is_duplicate == True)  # noqa: E712
        .all()
    )
    result = []
    for d in dups:
        kept_file = ""
        if d.duplicate_of and not d.duplicate_of.startswith("ledger:"):
            kept = db.query(Invoice).filter(Invoice.id == int(d.duplicate_of)).first()
            kept_file = kept.original_filename if kept else ""
        elif d.duplicate_of and d.duplicate_of.startswith("ledger:"):
            kept_file = "历史记录"
        result.append(
            DuplicateOut(
                invoice_no=d.invoice_no,
                invoice_code=d.invoice_code,
                invoice_type=d.invoice_type,
                buyer_name=d.buyer_name,
                buyer_tax_no=d.buyer_tax_no,
                kept_file=kept_file,
                skipped_file=d.original_filename,
                processed_at=(d.updated_at + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S") if d.updated_at else "",
            )
        )
    return result


@router.post("/{task_id}/export", response_model=MessageResponse)
def export(task_id: str):
    dup = task_service.export_task(task_id)
    return MessageResponse(detail=f"已重新导出，重复记录 {dup} 条")


@router.post("/{task_id}/retry-failed", response_model=MessageResponse)
def retry_failed(task_id: str):
    n = task_service.retry_failed(task_id)
    return MessageResponse(detail=f"已重试，成功 {n} 条")


@router.post("/{task_id}/cancel", response_model=MessageResponse)
def cancel_task(task_id: str):
    worker.cancel_task(task_id)
    return MessageResponse(detail="已请求取消")


@router.delete("/{task_id}", response_model=MessageResponse)
def delete_task(task_id: str):
    task_service.delete_task(task_id)
    return MessageResponse(detail="已删除")


# ---- 下载 ----

@router.get("/{task_id}/download")
def download_all(task_id: str):
    zip_path = archive_service.make_word_zip(task_id)
    if not zip_path:
        raise HTTPException(status_code=404, detail="未找到 Word 文档，请先导出")
    return FileResponse(zip_path, filename=f"{task_id}_word.zip")


@router.get("/{task_id}/download/duplicates")
def download_duplicates(task_id: str):
    p = safe_join(OUTPUT_DIR, task_id, "重复发票报告.xlsx")
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="重复报告不存在")
    return FileResponse(p, filename="重复发票报告.xlsx")
