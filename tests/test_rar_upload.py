"""rar 压缩包解压测试（解压工具探测 + 落盘收集逻辑）。"""
import os
from unittest import mock

import pytest

from app.utils import rar_utils

ALLOWED = {"jpg", "jpeg", "png", "pdf"}


def test_collect_from_dir_flatten_and_filter(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "__MACOSX").mkdir()
    (tmp_path / "a" / "1.jpg").write_bytes(b"jpg1")
    (tmp_path / "b" / "2.pdf").write_bytes(b"pdf2")
    (tmp_path / "b" / "c.txt").write_bytes(b"txt")
    (tmp_path / "__MACOSX" / "._x.png").write_bytes(b"meta")
    (tmp_path / ".DS_Store").write_bytes(b"hidden")
    out = rar_utils._collect_from_dir(str(tmp_path), ALLOWED, 1024)
    assert dict(out) == {"1.jpg": b"jpg1", "2.pdf": b"pdf2"}


def test_collect_duplicate_names(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "x.jpg").write_bytes(b"1")
    (tmp_path / "b" / "x.jpg").write_bytes(b"2")
    out = rar_utils._collect_from_dir(str(tmp_path), ALLOWED, 1024)
    assert [n for n, _ in out] == ["x.jpg", "x_1.jpg"]


def test_collect_size_limit(tmp_path):
    (tmp_path / "big.jpg").write_bytes(b"x" * 2000)
    (tmp_path / "small.jpg").write_bytes(b"s")
    out = rar_utils._collect_from_dir(str(tmp_path), ALLOWED, 1024)
    assert [n for n, _ in out] == ["small.jpg"]


def test_collect_skips_nested_zip(tmp_path):
    (tmp_path / "inner.zip").write_bytes(b"zip-bytes")
    (tmp_path / "y.jpg").write_bytes(b"y")
    out = rar_utils._collect_from_dir(str(tmp_path), ALLOWED, 1024)
    assert [n for n, _ in out] == ["y.jpg"]


def test_find_extractor_present():
    path, kind = rar_utils._find_extractor()
    assert path
    assert kind in {"bsdtar", "unrar", "7z", "unar"}


def test_extract_command():
    outdir = "/tmp/out"
    assert rar_utils._extract_command("bsdtar", "/usr/bin/bsdtar", "a.rar", outdir) == [
        "/usr/bin/bsdtar", "-xf", "a.rar", "-C", outdir,
    ]
    assert rar_utils._extract_command("7z", "7z", "a.rar", outdir) == [
        "7z", "x", "a.rar", f"-o{outdir}", "-y",
    ]
    assert rar_utils._extract_command("unrar", "unrar", "a.rar", outdir) == [
        "unrar", "x", "-o+", "a.rar", outdir + os.sep,
    ]
    assert rar_utils._extract_command("unar", "unar", "a.rar", outdir) == [
        "unar", "-o", outdir, "a.rar",
    ]


def test_extract_rar_no_extractor():
    with mock.patch(
        "app.utils.rar_utils._find_extractor",
        side_effect=ValueError("未找到可用的解压工具"),
    ):
        with pytest.raises(ValueError):
            rar_utils.extract_rar(b"x", ALLOWED, 1024)


def test_extract_rar_invalid_data():
    with pytest.raises(ValueError):
        rar_utils.extract_rar(b"not a rar archive", ALLOWED, 1024)
