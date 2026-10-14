"""PDF 处理：按页拆分，电子 PDF 提取文本层，扫描 PDF 转图片。"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Optional

from app.services.ocr_service import OcrBlock

logger = logging.getLogger(__name__)


@dataclass
class PdfPage:
    """PDF 单页结果。"""

    page_no: int
    text: str = ""  # 文本层内容（电子 PDF）
    has_text_layer: bool = False  # 是否有可提取的文本
    image_path: Optional[str] = None  # 渲染出的图片路径
    text_blocks: List[OcrBlock] = None  # 文本层（带坐标）

    def __post_init__(self):
        if self.text_blocks is None:
            self.text_blocks = []


def pdf_page_count(pdf_path: str) -> int:
    import fitz

    with fitz.open(pdf_path) as doc:
        return doc.page_count


def is_pdf_encrypted(pdf_path: str) -> bool:
    import fitz

    with fitz.open(pdf_path) as doc:
        return doc.needs_pass


def render_pdf_pages(pdf_path: str, out_dir: str, prefix: str, zoom: float = 2.0) -> List[str]:
    """将 PDF 每一页渲染成 JPG，返回图片路径列表。"""
    import fitz

    os.makedirs(out_dir, exist_ok=True)
    paths: List[str] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            out_path = os.path.join(out_dir, f"{prefix}_page{i + 1}.jpg")
            pix.save(out_path)
            paths.append(out_path)
    return paths


def extract_pdf_pages(pdf_path: str) -> List[PdfPage]:
    """提取 PDF 每页文本层与坐标。

    返回 PdfPage 列表，每页包含 text（纯文本）与 text_blocks（带坐标）。
    """
    import fitz

    pages: List[PdfPage] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            d = page.get_text("dict")
            blocks: List[OcrBlock] = []
            text_parts: List[str] = []
            for b in d.get("blocks", []):
                if b.get("type") != 0:  # 仅文本块
                    continue
                for line in b.get("lines", []):
                    line_text = "".join(
                        s.get("text", "") for s in line.get("spans", [])
                    )
                    if not line_text.strip():
                        continue
                    x0, y0, x1, y1 = line["bbox"]
                    blocks.append(
                        OcrBlock(text=line_text, confidence=1.0, bbox=(x0, y0, x1, y1))
                    )
                    text_parts.append(line_text)
            full_text = "\n".join(text_parts)
            pages.append(
                PdfPage(
                    page_no=i + 1,
                    text=full_text,
                    has_text_layer=bool(full_text.strip()),
                    text_blocks=blocks,
                )
            )
    return pages


def has_text_layer(pdf_path: str) -> bool:
    """快速判断 PDF 是否有文本层。"""
    pages = extract_pdf_pages(pdf_path)
    return any(p.has_text_layer for p in pages)
