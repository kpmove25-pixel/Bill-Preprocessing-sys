"""Excel 生成：按购买方生成汇总表、总汇总、重复报告。"""
from __future__ import annotations

import logging
import os
from typing import List

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.utils.file_utils import sanitize_filename

logger = logging.getLogger(__name__)

HEADERS = [
    "序号", "开票时间", "发票代码", "发票号码", "收款方", "金额", "金额（不含税）",
]

HEADER_FILL = PatternFill(start_color="DDEBF7", end_color="DDEBF7", fill_type="solid")
HEADER_FONT = Font(bold=True)


def _invoice_row(seq: int, inv: dict) -> list:
    return [
        seq, inv.get("invoice_date", ""), inv.get("invoice_code", ""),
        inv.get("invoice_no", ""), inv.get("seller_name", ""),
        inv.get("amount", ""), inv.get("amount_excluding_tax", ""),
    ]


def _write_sheet(ws, rows: List[list]):
    ws.append(HEADERS)
    for col_idx, _ in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in rows:
        ws.append(row)
    # 自适应列宽（近似）
    for col_idx in range(1, len(HEADERS) + 1):
        max_len = 0
        for row in ws.iter_rows(min_col=col_idx, max_col=col_idx):
            for cell in row:
                if cell.value is not None:
                    max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 40)


def generate_buyer_excel(invoices: List[dict], output_path: str) -> str:
    """生成单个购买方的汇总 Excel。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "发票汇总"
    rows = [_invoice_row(i + 1, inv) for i, inv in enumerate(invoices)]
    _write_sheet(ws, rows)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    wb.save(output_path)
    return output_path


def generate_summary_excel(invoices: List[dict], output_path: str) -> str:
    """生成总汇总 Excel。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "全部发票汇总"
    rows = [_invoice_row(i + 1, inv) for i, inv in enumerate(invoices)]
    _write_sheet(ws, rows)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    wb.save(output_path)
    return output_path


def generate_duplicate_excel(duplicates: List[dict], output_path: str) -> str:
    """生成重复发票报告 Excel。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "重复发票报告"
    dup_headers = [
        "序号", "发票号码", "发票代码", "发票类型", "购买方名称", "购买方税号",
        "保留文件", "被跳过文件", "处理时间",
    ]
    ws.append(dup_headers)
    for col_idx in range(1, len(dup_headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for i, d in enumerate(duplicates, start=1):
        ws.append([
            i, d.get("invoice_no", ""), d.get("invoice_code", ""),
            d.get("invoice_type", ""), d.get("buyer_name", ""),
            d.get("buyer_tax_no", ""), d.get("kept_file", ""),
            d.get("skipped_file", ""), d.get("processed_at", ""),
        ])
    for col_idx in range(1, len(dup_headers) + 1):
        max_len = 0
        for row in ws.iter_rows(min_col=col_idx, max_col=col_idx):
            for cell in row:
                if cell.value is not None:
                    max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 40)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    wb.save(output_path)
    return output_path


def build_buyer_excel_name(buyer_name: str, buyer_tax_no: str) -> str:
    """生成购买方 Excel 文件名，同名冲突追加税号。"""
    name = sanitize_filename(buyer_name)
    if not name:
        name = "未识别购买方"
    if buyer_tax_no:
        return f"{name}_{buyer_tax_no}_发票汇总.xlsx"
    return f"{name}_发票汇总.xlsx"
