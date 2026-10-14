import os, sys
os.environ["DATABASE_URL"] = "sqlite:///./data/e2e_test.db"
os.environ["USE_AUTH"] = "false"
sys.path.insert(0, os.getcwd())

from app.core.database import SessionLocal, init_db, engine, Base
from app.models import Invoice, Task
from app.services import task_service, ledger_service

Base.metadata.drop_all(bind=engine)
init_db()

# 1. 历史台账：taskA 已处理号码 12345678
ledger_service.record([{
    "dedup_key": "12345678", "invoice_code": "", "invoice_no": "12345678",
    "invoice_type": "", "buyer_name": "历史买方", "seller_name": "",
    "amount": "88.00", "original_filename": "old.pdf",
}], "taskA")

# 2. 新任务 taskB 再次上传相同号码
task_id = "taskB"
with SessionLocal() as db:
    db.add(Task(task_id=task_id, status="pending", total_files=1))
    db.add(Invoice(
        task_id=task_id, invoice_code="", invoice_no="12345678",
        invoice_type="增值税普通发票", buyer_name="新买方", seller_name="",
        amount="88.00", original_filename="new.pdf", jpg_path="",
        status="pending", is_duplicate=False,
    ))
    db.commit()

# 3. finalize
n = task_service.finalize_task(task_id)
print("finalize 返回重复数:", n)

with SessionLocal() as db:
    inv = db.query(Invoice).filter(Invoice.task_id == task_id).first()
    print("is_duplicate:", inv.is_duplicate)
    print("duplicate_of:", repr(inv.duplicate_of))
    print("remark:", inv.remark)

# 4. 验证台账 seen_count 未被误增（历史重复不应重复登记）
entry = ledger_service.check("12345678", "")
print("台账 seen_count:", entry["seen_count"], "(应为 1)")
print("台账 first_task_id:", entry["first_task_id"], "(应为 taskA)")
