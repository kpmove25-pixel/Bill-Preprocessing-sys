"""发票人工校正路由 + 图片预览。"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import require_auth
from app.core.database import SessionLocal, get_db
from app.models import AuditLog, Invoice
from app.schemas.schemas import EDITABLE_FIELDS, InvoiceOut, InvoiceUpdate
from app.utils.file_utils import safe_join

router = APIRouter(dependencies=[Depends(require_auth)])


@router.put("/api/invoices/{invoice_id}", response_model=InvoiceOut)
def update_invoice(invoice_id: int, body: InvoiceUpdate, db=Depends(get_db)):
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="发票记录不存在")

    data = body.dict(exclude_unset=True)
    changes = []
    for field, new_val in data.items():
        if field not in EDITABLE_FIELDS and field != "status":
            continue
        old_val = getattr(inv, field, "")
        if old_val != new_val:
            setattr(inv, field, new_val)
            changes.append((field, str(old_val), str(new_val)))

    # 修正后状态设为已确认（除非显式指定）
    if changes and "status" not in data:
        inv.status = "confirmed"
        inv.need_review = False

    for field, before, after in changes:
        db.add(
            AuditLog(
                task_id=inv.task_id,
                invoice_id=inv.id,
                action="update",
                field=field,
                before_value=before,
                after_value=after,
                operator="user",
            )
        )
    db.commit()
    db.refresh(inv)
    return inv


@router.get("/api/invoices/{invoice_id}/image")
def invoice_image(invoice_id: int, db=Depends(get_db)):
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv or not inv.jpg_path or not os.path.exists(inv.jpg_path):
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(inv.jpg_path)
