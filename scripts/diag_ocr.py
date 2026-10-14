"""批量诊断：遍历上传的微信图片 + 电子发票 PDF，打印解析结果。"""
import sys
import glob
import os

sys.path.insert(0, "/Users/movekp/webroot/票据凭证系统")

from app.services.ocr_service import RapidOcrEngine
from app.services.parser_service import parser_service
from app.services import pdf_service

FIELDS = [
    "invoice_no", "buyer_name", "buyer_tax_no", "seller_name", "seller_tax_no",
    "amount", "amount_excluding_tax", "tax_amount", "tax_rate", "invoice_date",
    "drawer",
]

eng = RapidOcrEngine()
base = "uploads/2026101423175290d250"


def show(label, blocks):
    p = parser_service.parse(blocks)
    print("  " + label)
    for k in FIELDS:
        print("    %-20s: %r" % (k, getattr(p, k)))
    if p.remarks:
        print("    remarks:", p.remarks)


print("========== 微信图片 ==========")
for img in sorted(glob.glob(base + "/original/微信图片*.jpg")):
    blocks = eng.recognize(img)
    show(os.path.basename(img), blocks)

print("\n========== 电子发票 PDF ==========")
for pdf in sorted(glob.glob(base + "/original/*.pdf")):
    pages = pdf_service.extract_pdf_pages(pdf)
    for pg in pages:
        if pg.text_blocks:
            show(os.path.basename(pdf) + " (p%d)" % pg.page_no, pg.text_blocks)
