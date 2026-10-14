"""API 请求/响应模型。"""
from __future__ import annotations

import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    auth_enabled: bool


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    status: str
    total_files: int
    processed_files: int
    success_count: int
    failed_count: int
    duplicate_count: int
    progress: float = 0.0
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str
    invoice_code: str = ""
    invoice_no: str = ""
    invoice_type: str = ""
    buyer_name: str = ""
    buyer_tax_no: str = ""
    seller_name: str = ""
    seller_tax_no: str = ""
    amount: str = ""
    amount_excluding_tax: str = ""
    tax_amount: str = ""
    tax_rate: str = ""
    invoice_date: str = ""
    check_code: str = ""
    drawer: str = ""
    original_filename: str = ""
    jpg_path: str = ""
    ocr_confidence: str = ""
    status: str = ""
    is_duplicate: bool = False
    duplicate_of: str = ""
    need_review: bool = False
    remark: str = ""
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None


# 可人工编辑的字段
EDITABLE_FIELDS = [
    "invoice_code", "invoice_no", "invoice_type", "buyer_name", "buyer_tax_no",
    "seller_name", "seller_tax_no", "amount", "amount_excluding_tax",
    "tax_amount", "tax_rate", "invoice_date", "check_code", "drawer", "remark",
]


class InvoiceUpdate(BaseModel):
    invoice_code: Optional[str] = None
    invoice_no: Optional[str] = None
    invoice_type: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_tax_no: Optional[str] = None
    seller_name: Optional[str] = None
    seller_tax_no: Optional[str] = None
    amount: Optional[str] = None
    amount_excluding_tax: Optional[str] = None
    tax_amount: Optional[str] = None
    tax_rate: Optional[str] = None
    invoice_date: Optional[str] = None
    check_code: Optional[str] = None
    drawer: Optional[str] = None
    remark: Optional[str] = None
    status: Optional[str] = None


class MessageResponse(BaseModel):
    detail: str


class BuyerFolder(BaseModel):
    buyer_name: str
    buyer_tax_no: str
    folder_name: str
    count: int


class DuplicateOut(BaseModel):
    invoice_no: str = ""
    invoice_code: str = ""
    invoice_type: str = ""
    buyer_name: str = ""
    buyer_tax_no: str = ""
    kept_file: str = ""
    skipped_file: str = ""
    processed_at: str = ""


class UploadResponse(BaseModel):
    task_id: str
    file_count: int


class LedgerCheckRequest(BaseModel):
    invoice_no: str
    invoice_code: str = ""


class LedgerEntry(BaseModel):
    dedup_key: str = ""
    invoice_code: str = ""
    invoice_no: str = ""
    invoice_type: str = ""
    buyer_name: str = ""
    seller_name: str = ""
    amount: str = ""
    first_seen_at: str = ""
    first_task_id: str = ""
    first_filename: str = ""
    seen_count: int = 0


class LedgerCheckResponse(BaseModel):
    found: bool
    entry: Optional[LedgerEntry] = None
