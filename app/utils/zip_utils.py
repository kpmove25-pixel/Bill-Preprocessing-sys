"""zip 压缩包解压工具：安全解压出可处理的票据文件。"""
from __future__ import annotations

import io
import os
import zipfile
from typing import List, Tuple


def _zip_member_name(info: zipfile.ZipInfo) -> str:
    """处理 zip 内中文文件名。

    Windows 压缩工具常用 GBK 编码，zipfile 默认按 cp437 解码会乱码。
    带 UTF-8 标志位的（flag_bits 0x800）zipfile 已按 UTF-8 正确解码，直接返回。
    """
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("gbk")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def extract_zip(data: bytes, allowed_exts: set, max_file_size: int) -> List[Tuple[str, bytes]]:
    """安全解压 zip，返回 [(文件名, bytes)]，仅保留 allowed_exts 内的文件。

    - 跳过目录、__MACOSX、隐藏文件、不支持类型、嵌套 zip
    - 防 zip slip（路径穿越）
    - 单文件大小限制（防解压炸弹）
    - 同名文件自动加序号去重

    :raises ValueError: 数据不是合法 zip 压缩包
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise ValueError("无法解析的压缩包（请确认是标准 zip 格式）") from e

    results: List[Tuple[str, bytes]] = []
    seen: set = set()
    with zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = _zip_member_name(info)
            parts = name.replace("\\", "/").split("/")
            # zip slip 防护：绝对路径或含 .. 段
            if name.startswith("/") or ".." in parts:
                continue
            # 跳过 macOS 元数据目录
            if "__MACOSX" in parts:
                continue
            base = parts[-1]
            if not base or base.startswith("."):
                continue
            ext = os.path.splitext(base)[1].lower().lstrip(".")
            if ext not in allowed_exts:
                continue
            raw = zf.read(info)
            if len(raw) > max_file_size:
                continue
            # 同名去重
            final = base
            stem, e = os.path.splitext(base)
            k = 1
            while final in seen:
                final = f"{stem}_{k}{e}"
                k += 1
            seen.add(final)
            results.append((final, raw))
    return results
