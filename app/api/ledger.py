"""台账路由：历史号码查重。"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from app.api.deps import require_auth
from app.schemas.schemas import LedgerCheckRequest, LedgerCheckResponse, LedgerEntry
from app.services import ledger_service

router = APIRouter(prefix="/api/ledger", tags=["ledger"], dependencies=[Depends(require_auth)])


@router.post("/check", response_model=LedgerCheckResponse)
def check_ledger(req: LedgerCheckRequest):
    entry = ledger_service.check(req.invoice_no, req.invoice_code)
    if entry is None:
        return LedgerCheckResponse(found=False, entry=None)
    return LedgerCheckResponse(found=True, entry=LedgerEntry(**entry))


@router.get("", response_model=List[LedgerEntry])
def list_ledger():
    return ledger_service.list_ledger()
