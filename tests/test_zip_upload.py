"""zip 压缩包解压测试。"""
import io
import zipfile

import pytest

from app.utils.zip_utils import extract_zip

ALLOWED = {"jpg", "jpeg", "png", "pdf"}


def _make_zip(members):
    """members: [(arcname, data_bytes)]"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members:
            zf.writestr(name, data)
    return buf.getvalue()


def test_extract_images_and_pdf():
    data = _make_zip([("a/1.jpg", b"jpg1"), ("b/2.pdf", b"pdf2"), ("c.txt", b"txt")])
    out = extract_zip(data, ALLOWED, 1024)
    assert [n for n, _ in out] == ["1.jpg", "2.pdf"]
    assert [d for _, d in out] == [b"jpg1", b"pdf2"]


def test_skip_macosx_and_hidden():
    data = _make_zip([("__MACOSX/._1.jpg", b"x"), (".DS_Store", b"y"), ("real.png", b"z")])
    out = extract_zip(data, ALLOWED, 1024)
    assert [n for n, _ in out] == ["real.png"]


def test_zip_slip_rejected():
    data = _make_zip([("../evil.jpg", b"x"), ("ok.jpg", b"y")])
    out = extract_zip(data, ALLOWED, 1024)
    assert [n for n, _ in out] == ["ok.jpg"]


def test_duplicate_names():
    data = _make_zip([("a/x.jpg", b"1"), ("b/x.jpg", b"2")])
    out = extract_zip(data, ALLOWED, 1024)
    assert [n for n, _ in out] == ["x.jpg", "x_1.jpg"]


def test_size_limit():
    data = _make_zip([("big.jpg", b"x" * 2000), ("small.jpg", b"s")])
    out = extract_zip(data, ALLOWED, 1024)
    assert [n for n, _ in out] == ["small.jpg"]


def test_chinese_filename_utf8():
    data = _make_zip([("发票_123.jpg", b"x")])
    out = extract_zip(data, ALLOWED, 1024)
    assert [n for n, _ in out] == ["发票_123.jpg"]


def test_nested_zip_skipped():
    inner = _make_zip([("x.jpg", b"x")])
    data = _make_zip([("inner.zip", inner), ("y.jpg", b"y")])
    out = extract_zip(data, ALLOWED, 1024)
    assert [n for n, _ in out] == ["y.jpg"]


def test_invalid_zip():
    with pytest.raises(ValueError):
        extract_zip(b"not a zip", ALLOWED, 1024)


def test_no_supported_files():
    data = _make_zip([("a.txt", b"x")])
    assert extract_zip(data, ALLOWED, 1024) == []
