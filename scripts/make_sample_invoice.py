"""生成模拟票据图片/PDF，用于测试与验收。

用法：
    python scripts/make_sample_invoice.py            # 生成图片样例到 samples/
    python scripts/make_sample_invoice.py --pdf      # 额外生成多页 PDF 样例
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    # Windows
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    # Linux
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]


def _find_font(size=24):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_invoice(no, code, itype, buyer, buyer_tax, seller, seller_tax,
                 amount, tax, date, drawer, out_path, width=1000, height=700):
    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)
    title_font = _find_font(36)
    font = _find_font(26)
    small = _find_font(22)

    d.text((width // 2 - 150, 40), itype, fill="black", font=title_font)
    lines = [
        f"发票代码：{code}",
        f"发票号码：{no}",
        f"开票日期：{date}",
        f"购买方名称：{buyer}",
        f"购买方纳税人识别号：{buyer_tax}",
        f"销售方名称：{seller}",
        f"销售方纳税人识别号：{seller_tax}",
        f"合计金额：{amount}",
        f"税额：{tax}",
        f"价税合计（小写）：￥{amount}",
        f"税率：13%",
        f"开票人：{drawer}",
        f"校验码：{no}{code}",
    ]
    y = 120
    for line in lines:
        d.text((60, y), line, fill="black", font=font)
        y += 55

    # 表格框
    d.rectangle([40, 100, width - 40, height - 40], outline="black", width=2)
    img.save(out_path, "JPEG", quality=92)
    return out_path


def make_samples(out_dir: str, with_pdf: bool):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    samples = [
        dict(no="12345678", code="011001900111", itype="增值税专用发票",
             buyer="测试科技有限公司", buyer_tax="91310000774400001X",
             seller="示例贸易有限公司", seller_tax="91440300MA5D123456",
             amount="1130.00", tax="130.00", date="2023年05月15日", drawer="张三"),
        dict(no="87654321", code="011001900222", itype="增值税普通发票",
             buyer="北京某某有限公司", buyer_tax="91110105MA00XXXX00",
             seller="上海某某科技有限公司", seller_tax="91310115MA1XXXXX00",
             amount="2260.00", tax="260.00", date="2024年01月10日", drawer="李四"),
        dict(no="24042000000012345678", code="", itype="电子发票（全电发票）",
             buyer="广州某某信息技术有限公司", buyer_tax="91440101MA5XXXXXX0",
             seller="深圳某某软件有限公司", seller_tax="91440300MA5XXXXXX1",
             amount="3390.00", tax="390.00", date="2024年04月20日", drawer="王五"),
        # 与第一条重复，用于测试去重
        dict(no="12345678", code="011001900111", itype="增值税专用发票",
             buyer="测试科技有限公司", buyer_tax="91310000774400001X",
             seller="示例贸易有限公司", seller_tax="91440300MA5D123456",
             amount="1130.00", tax="130.00", date="2023年05月15日", drawer="张三"),
    ]

    paths = []
    for i, s in enumerate(samples, start=1):
        p = out_dir / f"sample_{i}.jpg"
        draw_invoice(out_path=str(p), **s)
        paths.append(p)
        print(f"已生成 {p}")

    if with_pdf:
        import fitz

        pdf_path = out_dir / "sample_multi.pdf"
        doc = fitz.open()
        for p in paths[:3]:
            page = doc.new_page(width=1000, height=700)
            page.insert_image(fitz.Rect(0, 0, 1000, 700), filename=str(p))
        doc.save(str(pdf_path))
        doc.close()
        print(f"已生成 {pdf_path}")

    print("完成。")


if __name__ == "__main__":
    make_samples("samples", with_pdf="--pdf" in sys.argv)
