"""Word 文档生成：按购买方生成「字段表格 + 票据图片」的 Word。"""
from __future__ import annotations

import logging
import os
from typing import List

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

logger = logging.getLogger(__name__)

# 与 Excel 汇总保持一致的 7 列表头
WORD_HEADERS = ["序号", "开票时间", "发票代码", "发票号码", "收款方", "金额", "金额（不含税）"]

# 票据图片插入宽度（cm），适配 A4 页面
PIC_WIDTH_CM = 15.0


def _invoice_row(seq: int, inv: dict) -> list:
    """与 excel_service._invoice_row 一致的字段顺序。"""
    return [
        seq,
        inv.get("invoice_date", ""),
        inv.get("invoice_code", ""),
        inv.get("invoice_no", ""),
        inv.get("seller_name", ""),
        inv.get("amount", ""),
        inv.get("amount_excluding_tax", ""),
    ]


def generate_buyer_word(
    buyer_name: str,
    buyer_tax_no: str,
    invoices: List[dict],
    output_path: str,
) -> str:
    """生成单个购买方的 Word 文档。

    结构：标题（购买方）→ 7 字段信息表格 → 下方依次插入各不重复票据图片。
    """
    doc = Document()

    # 标题
    name = (buyer_name or "").strip() or "未识别购买方"
    title = f"{name}_{buyer_tax_no}" if buyer_tax_no else name
    heading = doc.add_heading(title, level=1)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 7 字段表格
    table = doc.add_table(rows=1, cols=len(WORD_HEADERS))
    table.style = "Table Grid"
    hdr_cells = table.rows[0].cells
    for idx, h in enumerate(WORD_HEADERS):
        hdr_cells[idx].text = h

    for i, inv in enumerate(invoices, start=1):
        row_cells = table.add_row().cells
        for j, val in enumerate(_invoice_row(i, inv)):
            row_cells[j].text = "" if val is None else str(val)

    # 表格下方插入不重复票据图片
    for inv in invoices:
        jpg = inv.get("archived_jpg") or inv.get("jpg_path", "")
        if jpg and os.path.exists(jpg):
            doc.add_paragraph()
            doc.add_picture(jpg, width=Cm(PIC_WIDTH_CM))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path
