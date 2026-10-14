"""图片转换测试。"""
import os

from PIL import Image

from app.services.image_service import convert_to_jpg, is_image_file


def _make_png(path, mode="RGBA", size=(100, 80)):
    img = Image.new(mode, size, (255, 0, 0, 128) if mode == "RGBA" else (255, 0, 0))
    img.save(path)


def test_is_image_file():
    assert is_image_file("a.jpg")
    assert is_image_file("b.png")
    assert not is_image_file("c.pdf")


def test_convert_rgba_to_jpg(tmp_path):
    src = tmp_path / "in.png"
    dst = tmp_path / "out.jpg"
    _make_png(str(src), mode="RGBA")
    convert_to_jpg(str(src), str(dst))
    assert os.path.exists(dst)
    with Image.open(dst) as img:
        assert img.mode == "RGB"


def test_convert_png_to_jpg(tmp_path):
    src = tmp_path / "in.png"
    dst = tmp_path / "out.jpg"
    _make_png(str(src), mode="RGB")
    convert_to_jpg(str(src), str(dst))
    with Image.open(dst) as img:
        assert img.format == "JPEG"
