"""去重逻辑测试。"""
from app.services.dedup_service import build_dedup_key, deduplicate


def test_build_dedup_key_normal():
    k = build_dedup_key("增值税专用发票", "011001900111", "12345678")
    assert k == "011001900111::12345678"


def test_build_dedup_key_no_code():
    k = build_dedup_key("增值税普通发票", "", "12345678")
    assert k == "12345678"


def test_build_dedup_key_full_electric():
    k = build_dedup_key("全电发票", "", "24042000000012345678")
    assert k == "24042000000012345678"


def test_build_dedup_key_invoice_no_only():
    k = build_dedup_key("全电发票", "", "24042000000012345678", strategy="invoice_no")
    assert k == "24042000000012345678"


def test_deduplicate_keeps_first():
    invs = [
        {"id": 1, "invoice_type": "增值税专用发票", "invoice_code": "C", "invoice_no": "1"},
        {"id": 2, "invoice_type": "增值税专用发票", "invoice_code": "C", "invoice_no": "1"},
        {"id": 3, "invoice_type": "增值税专用发票", "invoice_code": "C", "invoice_no": "2"},
    ]
    keep, dups = deduplicate(invs)
    assert len(keep) == 2
    assert len(dups) == 1
    assert dups[0]["id"] == 2
    assert dups[0]["duplicate_of"] == 1


def test_deduplicate_no_invoice_no_not_dropped():
    invs = [
        {"id": 1, "invoice_type": "", "invoice_code": "", "invoice_no": ""},
    ]
    keep, dups = deduplicate(invs)
    assert len(keep) == 1
    assert len(dups) == 0
