"""检查某张图片是否被误判为「一页多票」（检测到多个 20 位号码）。"""
import re
import sys

sys.path.insert(0, "/Users/movekp/webroot/票据凭证系统")

from app.services.ocr_service import RapidOcrEngine

eng = RapidOcrEngine()
img = "uploads/2026101423175290d250/jpg/微信图片_20261014213047_72_8.jpg"
blocks = eng.recognize(img)
full = "\n".join(b.text for b in blocks)
nums = re.findall(r"(?<!\d)(\d{20})(?!\d)", full)
print("检测到的 20 位号码（去重）:", sorted(set(nums)))
print("---- 含 20 位号码的行 ----")
for b in blocks:
    for m in re.findall(r"(?<!\d)(\d{20})(?!\d)", b.text):
        print("  %r" % b.text)
