"""台账服务测试。"""
from app.core.database import Base, engine
from app.models import InvoiceLedger  # noqa: F401  # 确保模型注册
from app.services import ledger_service


def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_record_and_check():
    _reset_db()
    try:
        invs = [{
            "dedup_key": "011001900111::12345678",
            "invoice_code": "011001900111",
            "invoice_no": "12345678",
            "invoice_type": "增值税专用发票",
            "buyer_name": "买方A",
            "seller_name": "卖方B",
            "amount": "100.00",
            "original_filename": "a.pdf",
        }]
        assert ledger_service.record(invs, "task1") == 1
        # 幂等：重复 record 不新增，仅 seen_count + 1
        assert ledger_service.record(invs, "task2") == 0

        entry = ledger_service.check("12345678", "011001900111")
        assert entry is not None
        assert entry["invoice_no"] == "12345678"
        assert entry["seen_count"] == 2
        assert entry["first_task_id"] == "task1"

        # 未命中
        assert ledger_service.check("99999999", "") is None
    finally:
        _reset_db()


def test_find_history():
    _reset_db()
    try:
        # task1 首次处理号码 12345678
        ledger_service.record([{
            "dedup_key": "12345678",
            "invoice_code": "",
            "invoice_no": "12345678",
            "invoice_type": "",
            "buyer_name": "买方",
            "seller_name": "",
            "amount": "",
            "original_filename": "old.pdf",
        }], "task1")

        keep = [
            {
                "id": 10, "dedup_key": "12345678", "invoice_no": "12345678",
                "invoice_code": "", "invoice_type": "", "buyer_name": "买方",
                "buyer_tax_no": "", "original_filename": "new.pdf",
            },
            {
                "id": 11, "dedup_key": "88888888", "invoice_no": "88888888",
                "invoice_code": "", "invoice_type": "", "buyer_name": "买方",
                "buyer_tax_no": "", "original_filename": "fresh.pdf",
            },
        ]
        final_keep, historical = ledger_service.find_history(keep, "task2")
        assert [x["id"] for x in final_keep] == [11]
        assert [x["id"] for x in historical] == [10]
        assert historical[0]["historical_source"] == "task1"

        # 同任务不算历史重复（re-export 幂等）
        final_keep2, historical2 = ledger_service.find_history(keep, "task1")
        assert historical2 == []
        assert [x["id"] for x in final_keep2] == [10, 11]
    finally:
        _reset_db()
