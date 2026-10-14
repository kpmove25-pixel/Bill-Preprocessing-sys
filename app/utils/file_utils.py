"""文件与路径工具：安全路径、非法字符清洗、文件名清洗。"""
import re
import unicodedata

# Windows 非法字符 + 常见非法字符
_ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]')
# 连续点或尾部点/空格
_TRIM_DOTS = re.compile(r"^\.+|\.+$")
_SPACES = re.compile(r"\s+")


def sanitize_filename(name: str, max_len: int = 80) -> str:
    """清洗为合法文件夹/文件名。

    - 替换非法字符
    - 去除首尾空格和点
    - 限制长度（按字符，避免路径过长）
    - 空名兜底
    """
    if not name:
        return "未命名"
    name = unicodedata.normalize("NFKC", str(name))
    name = _ILLEGAL_CHARS.sub("_", name)
    name = _SPACES.sub(" ", name).strip()
    name = _TRIM_DOTS.sub("", name)
    name = name.strip()
    if not name:
        return "未命名"
    # 限制长度，避免多字节截断问题
    if len(name) > max_len:
        name = name[:max_len].rstrip(" .")
    return name or "未命名"


def safe_join(base_dir, *parts) -> str:
    """拼接路径并防止路径穿越。"""
    import os

    base = os.path.abspath(base_dir)
    full = os.path.abspath(os.path.join(base, *parts))
    if not full.startswith(base + os.sep) and full != base:
        raise ValueError(f"路径穿越风险: {parts}")
    return full


def file_stem(filename: str) -> str:
    """去除扩展名。"""
    import os

    return os.path.splitext(os.path.basename(filename))[0]


def ext_lower(filename: str) -> str:
    import os

    return os.path.splitext(filename)[1].lower().lstrip(".")
