"""文件工具测试。"""
from app.utils.file_utils import sanitize_filename, safe_join


def test_sanitize_illegal_chars():
    assert sanitize_filename('a/b\\c:d*e?f"g<h>i|j') == "a_b_c_d_e_f_g_h_i_j"


def test_sanitize_trim_dots_spaces():
    assert sanitize_filename("  公司名.  ") == "公司名"


def test_sanitize_empty():
    assert sanitize_filename("") == "未命名"
    assert sanitize_filename("   ") == "未命名"


def test_safe_join_ok():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = safe_join(d, "sub", "file.txt")
        assert p.endswith("file.txt")


def test_safe_join_traversal():
    import pytest

    with pytest.raises(ValueError):
        safe_join("/tmp", "..", "..", "etc")
