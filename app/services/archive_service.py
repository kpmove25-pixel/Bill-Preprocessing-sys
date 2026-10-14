"""归档服务：按购买方分组，生成文件夹、拷贝图片、生成 Excel、打包 zip。"""
from __future__ import annotations

import logging
import os
import shutil
import zipfile
from collections import defaultdict
from typing import Dict, List, Optional

from app.core.config import OUTPUT_DIR
from app.services import excel_service, word_service
from app.utils.file_utils import sanitize_filename, safe_join

logger = logging.getLogger(__name__)


def build_buyer_folder_name(buyer_name: str, buyer_tax_no: str) -> str:
    """购买方文件夹命名：清洗后名称 + 税号。"""
    name = sanitize_filename(buyer_name)
    if not buyer_name or not buyer_name.strip():
        name = "未识别购买方"
    if buyer_tax_no:
        return f"{name}_{buyer_tax_no}"
    return name


def group_by_buyer(invoices: List[dict]) -> Dict[str, List[dict]]:
    """按 (buyer_name, buyer_tax_no) 分组。"""
    groups = defaultdict(list)
    for inv in invoices:
        buyer = inv.get("buyer_name", "").strip() or "未识别购买方"
        tax = inv.get("buyer_tax_no", "").strip()
        key = f"{buyer}__{tax}"
        groups[key].append(inv)
    return dict(groups)


def archive_task(task_id: str, kept_invoices: List[dict]) -> dict:
    """归档一个任务的所有保留发票。

    返回归档结果信息（含各购买方目录、excel 路径、重复数）。
    """
    task_out = safe_join(OUTPUT_DIR, task_id)
    # 清空旧输出，重新归档（人工校正后重导出）
    if os.path.exists(task_out):
        shutil.rmtree(task_out)
    os.makedirs(task_out, exist_ok=True)

    groups = group_by_buyer(kept_invoices)
    result = {"buyers": [], "summary_excel": "", "total": len(kept_invoices)}

    all_rows = []
    for (buyer_key, invs) in groups.items():
        buyer_name, buyer_tax_no = buyer_key.split("__", 1)
        folder_name = build_buyer_folder_name(buyer_name, buyer_tax_no)
        folder_path = safe_join(task_out, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        # 拷贝 jpg（命名：购买方名称_发票金额，重名时追加发票号码）
        used_names = set()
        for inv in invs:
            jpg = inv.get("jpg_path", "")
            if not jpg or not os.path.exists(jpg):
                continue
            ext = os.path.splitext(jpg)[1].lower() or ".jpg"
            buyer = sanitize_filename(inv.get("buyer_name", "") or "未识别购买方")
            amount = sanitize_filename((inv.get("amount", "") or "").strip() or "无金额")
            base = f"{buyer}_{amount}"
            name = base
            if name in used_names:
                no = sanitize_filename((inv.get("invoice_no", "") or "").strip())
                name = f"{base}_{no}" if no else f"{base}_{len(used_names) + 1}"
            used_names.add(name)
            dst = os.path.join(folder_path, name + ext)
            if os.path.abspath(jpg) != os.path.abspath(dst):
                shutil.copy2(jpg, dst)
            inv["archived_jpg"] = dst

        # 生成购买方 Excel
        excel_name = excel_service.build_buyer_excel_name(buyer_name, buyer_tax_no)
        excel_path = os.path.join(folder_path, excel_name)
        excel_service.generate_buyer_excel(invs, excel_path)
        for inv in invs:
            inv["excel_path"] = excel_path

        # 生成购买方 Word（7 字段表格 + 票据图片）
        word_path = os.path.join(folder_path, f"{folder_name}.docx")
        word_service.generate_buyer_word(buyer_name, buyer_tax_no, invs, word_path)
        for inv in invs:
            inv["word_path"] = word_path

        result["buyers"].append({
            "buyer_name": buyer_name,
            "buyer_tax_no": buyer_tax_no,
            "folder_name": folder_name,
            "folder_path": folder_path,
            "excel_path": excel_path,
            "count": len(invs),
        })
        all_rows.extend(invs)

    # 总汇总
    summary_path = os.path.join(task_out, "全部发票汇总.xlsx")
    excel_service.generate_summary_excel(all_rows, summary_path)
    result["summary_excel"] = summary_path

    return result


def generate_duplicate_report(task_id: str, duplicates: List[dict]) -> str:
    """生成重复报告 Excel。"""
    task_out = safe_join(OUTPUT_DIR, task_id)
    os.makedirs(task_out, exist_ok=True)
    report_path = os.path.join(task_out, "重复发票报告.xlsx")
    excel_service.generate_duplicate_excel(duplicates, report_path)
    return report_path


def make_word_zip(task_id: str) -> Optional[str]:
    """仅打包各购买方的 Word 文档（.docx）为一个 zip，不含图片与 Excel。

    :return: zip 路径；若输出目录不存在或无任何 docx，返回 None。
    """
    task_out = safe_join(OUTPUT_DIR, task_id)
    if not os.path.isdir(task_out):
        return None

    word_files = []
    for root, _dirs, files in os.walk(task_out):
        for f in files:
            if f.lower().endswith(".docx"):
                word_files.append(os.path.join(root, f))

    if not word_files:
        return None

    zip_path = os.path.join(OUTPUT_DIR, f"{task_id}_word.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for full in word_files:
            zf.write(full, os.path.basename(full))
    return zip_path
