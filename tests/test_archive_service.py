"""归档服务测试。"""
import zipfile

from app.services import archive_service
from app.services.archive_service import build_buyer_folder_name, group_by_buyer


def test_build_buyer_folder_name():
    assert build_buyer_folder_name("测试公司", "91310000XXXX") == "测试公司_91310000XXXX"
    assert build_buyer_folder_name("测试公司", "") == "测试公司"
    assert build_buyer_folder_name("", "") == "未识别购买方"
    assert build_buyer_folder_name("a/b\\c", "") == "a_b_c"


def test_group_by_buyer():
    invs = [
        {"buyer_name": "A公司", "buyer_tax_no": "111"},
        {"buyer_name": "A公司", "buyer_tax_no": "111"},
        {"buyer_name": "B公司", "buyer_tax_no": "222"},
    ]
    groups = group_by_buyer(invs)
    assert len(groups) == 2
    assert sum(len(v) for v in groups.values()) == 3


def test_make_word_zip(tmp_path, monkeypatch):
    """仅打包各购买方 Word，排除图片与 Excel。"""
    monkeypatch.setattr(archive_service, "OUTPUT_DIR", str(tmp_path))
    buyer_dir = tmp_path / "task1" / "公司A_111"
    buyer_dir.mkdir(parents=True)
    (buyer_dir / "公司A_111.docx").write_bytes(b"docx-a")
    (buyer_dir / "发票.jpg").write_bytes(b"jpg")
    (tmp_path / "task1" / "全部发票汇总.xlsx").write_bytes(b"xlsx")

    zip_path = archive_service.make_word_zip("task1")
    assert zip_path
    with zipfile.ZipFile(zip_path) as zf:
        assert zf.namelist() == ["公司A_111.docx"]


def test_make_word_zip_no_output(tmp_path, monkeypatch):
    monkeypatch.setattr(archive_service, "OUTPUT_DIR", str(tmp_path))
    assert archive_service.make_word_zip("missing") is None
