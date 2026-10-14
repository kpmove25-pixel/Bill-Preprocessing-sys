"""图片处理：统一转换为 RGB JPG，去除透明通道，可选预处理。"""
from __future__ import annotations

import logging
import os
from typing import Optional

from PIL import Image, ImageOps

from app.core.config import settings

logger = logging.getLogger(__name__)

# 支持的图片扩展名
SUPPORTED_IMAGE_EXTS = {"jpg", "jpeg", "png", "bmp", "tiff", "tif", "webp"}


def is_image_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    return ext in SUPPORTED_IMAGE_EXTS


def convert_to_jpg(src_path: str, dst_path: str, quality: Optional[int] = None) -> str:
    """将任意支持图片转成 RGB JPG。

    - 转 RGB、去除透明通道（填充白色背景）
    - 自动旋转（EXIF）
    - 质量默认 90-95
    """
    quality = quality or settings.jpg_quality
    with Image.open(src_path) as img:
        img = ImageOps.exif_transpose(img)  # 修正 EXIF 旋转
        if img.mode in ("RGBA", "LA", "P"):
            # 处理透明通道：叠加到白色背景
            if img.mode == "P":
                img = img.convert("RGBA")
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        elif img.mode == "CMYK":
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")
        img.save(dst_path, "JPEG", quality=quality)
    return dst_path


def preprocess_image(src_path: str, dst_path: str) -> str:
    """可选预处理：目前为直通（灰度/二值化等可按需扩展）。

    MVP 默认不做破坏性处理，保留原图质量，仅统一 JPG 格式。
    """
    return src_path
