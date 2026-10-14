"""rar 压缩包解压工具：调用系统解压工具安全解压出可处理的票据文件。

RAR 是专有压缩格式，Python 标准库无法解压，需借助外部解压工具（支持 RAR4/RAR5 读取）：
- macOS / Linux：bsdtar（libarchive）
- Windows：unrar（WinRAR）或 7z（7-Zip）
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import List, Tuple


# 各系统常见的 RAR 解压工具及探测顺序
_EXTRACTOR_CANDIDATES = [
    ("bsdtar", "bsdtar"),  # macOS / Linux（libarchive）
    ("unrar", "unrar"),    # WinRAR 命令行
    ("7z", "7z"),          # 7-Zip
    ("7za", "7z"),         # 7-Zip 独立版
    ("unar", "unar"),      # The Unarchiver
]


def _find_extractor() -> Tuple[str, str]:
    """探测可用的 RAR 解压工具，返回 (工具路径, 类型)。

    :raises ValueError: 未找到任何可用工具
    """
    for tool, kind in _EXTRACTOR_CANDIDATES:
        path = shutil.which(tool)
        if path:
            return path, kind
    raise ValueError("未找到可用的解压工具，请安装 7-Zip 或 WinRAR 后重试")


def _extract_command(kind: str, tool: str, rar_path: str, outdir: str) -> List[str]:
    """按工具类型生成对应的解压命令。"""
    if kind == "bsdtar":
        return [tool, "-xf", rar_path, "-C", outdir]
    if kind == "7z":
        return [tool, "x", rar_path, f"-o{outdir}", "-y"]
    if kind == "unrar":
        return [tool, "x", "-o+", rar_path, outdir + os.sep]
    if kind == "unar":
        return [tool, "-o", outdir, rar_path]
    raise ValueError(f"未知的解压工具类型: {kind}")


def _collect_from_dir(
    outdir: str, allowed_exts: set, max_file_size: int
) -> List[Tuple[str, bytes]]:
    """遍历解压目录，收集 allowed_exts 内的文件（平铺 + 过滤 + 同名去重）。

    子目录一律平铺为 basename，跳过 __MACOSX、隐藏文件、不支持类型与超大文件。
    """
    results: List[Tuple[str, bytes]] = []
    seen: set = set()
    for root, dirs, files in os.walk(outdir):
        # 跳过 macOS 元数据目录
        dirs[:] = [d for d in dirs if d != "__MACOSX"]
        for name in files:
            if name.startswith("."):
                continue
            ext = os.path.splitext(name)[1].lower().lstrip(".")
            if ext not in allowed_exts:
                continue
            full = os.path.join(root, name)
            if os.path.getsize(full) > max_file_size:
                continue
            # 同名去重
            final = name
            stem, e = os.path.splitext(name)
            k = 1
            while final in seen:
                final = f"{stem}_{k}{e}"
                k += 1
            seen.add(final)
            with open(full, "rb") as f:
                results.append((final, f.read()))
    return results


def extract_rar(
    data: bytes, allowed_exts: set, max_file_size: int
) -> List[Tuple[str, bytes]]:
    """安全解压 rar，返回 [(文件名, bytes)]，仅保留 allowed_exts 内的文件。

    - 自动探测系统解压工具（bsdtar / unrar / 7z / unar）解压 RAR4/RAR5
    - 落盘在受控临时目录内，规避 zip-slip 路径穿越
    - 跳过 __MACOSX、隐藏文件、不支持类型、超大文件
    - 子目录平铺 + 同名自动加序号

    :raises ValueError: 无可用解压工具、解压失败或数据非法
    """
    tool, kind = _find_extractor()
    with tempfile.TemporaryDirectory() as tmpdir:
        rar_path = os.path.join(tmpdir, "input.rar")
        with open(rar_path, "wb") as f:
            f.write(data)
        outdir = os.path.join(tmpdir, "out")
        os.makedirs(outdir, exist_ok=True)
        proc = subprocess.run(
            _extract_command(kind, tool, rar_path, outdir),
            capture_output=True,
        )
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="ignore").strip()
            raise ValueError(f"无法解析 rar 压缩包：{err}")
        return _collect_from_dir(outdir, allowed_exts, max_file_size)
