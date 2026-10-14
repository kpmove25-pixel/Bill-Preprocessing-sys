"""票据号码台账服务：跨任务历史查重。"""
from __future__ import annotations

import datetime
import logging
from typing import List, Optional

from app.core.database import SessionLocal
from app.models import Invoice, InvoiceLedger
from app.services.dedup_service import build_dedup_key

logger = logging.getLogger(__name__)


def _key(invoice_code: str, invoice_no: str) -> str:
    """按方案 B 计算台账去重键（忽略发票类型）。"""
    return build_dedup_key("", invoice_code or "", invoice_no or "")


def _fmt_local(dt: datetime.datetime) -> str:
    """naive UTC -> 北京时间字符串(+8)。"""
    if not dt:
        return ""
    return (dt + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")


def record(keep_dicts: List[dict], task_id: str) -> int:
    """将保留发票写入台账（幂等 upsert），返回新登记条数。"""
    with SessionLocal() as db:
        new_count = 0
        for inv in keep_dicts:
            key = inv.get("dedup_key") or _key(
                inv.get("invoice_code", ""), inv.get("invoice_no", "")
            )
            if not key:
                continue
            rec = db.query(InvoiceLedger).filter(InvoiceLedger.dedup_key == key).first()
            if rec:
                rec.seen_count += 1
            else:
                db.add(InvoiceLedger(
                    dedup_key=key,
                    invoice_code=inv.get("invoice_code", ""),
                    invoice_no=inv.get("invoice_no", ""),
                    invoice_type=inv.get("invoice_type", ""),
                    buyer_name=inv.get("buyer_name", ""),
                    seller_name=inv.get("seller_name", ""),
                    amount=inv.get("amount", ""),
                    first_seen_at=datetime.datetime.utcnow(),
                    first_task_id=task_id,
                    first_filename=inv.get("original_filename", ""),
                    seen_count=1,
                ))
                new_count += 1
        db.commit()
        return new_count


def find_history(keep_dicts: List[dict], task_id: str) -> tuple:
    """将 keep 列表拆分为 (final_keep, historical_dups)。

    命中台账且首次来源不是当前任务的，视为历史重复（避免 re-export 误判自己）。
    """
    final_keep: List[dict] = []
    historical: List[dict] = []
    keys = [inv.get("dedup_key") for inv in keep_dicts if inv.get("dedup_key")]
    existing: dict = {}
    if keys:
        with SessionLocal() as db:
            rows = db.query(InvoiceLedger).filter(InvoiceLedger.dedup_key.in_(keys)).all()
            existing = {r.dedup_key: r for r in rows}
    for inv in keep_dicts:
        key = inv.get("dedup_key")
        rec = existing.get(key) if key else None
        if rec and rec.first_task_id != task_id:
            inv["historical_source"] = rec.first_task_id
            historical.append(inv)
        else:
            final_keep.append(inv)
    return final_keep, historical


def check(invoice_no: str, invoice_code: str = "") -> Optional[dict]:
    """按号码查询台账，命中返回历史详情，未命中返回 None。"""
    key = _key(invoice_code or "", invoice_no or "")
    if not key:
        return None
    with SessionLocal() as db:
        rec = db.query(InvoiceLedger).filter(InvoiceLedger.dedup_key == key).first()
        if not rec:
            return None
        return {
            "dedup_key": rec.dedup_key,
            "invoice_code": rec.invoice_code,
            "invoice_no": rec.invoice_no,
            "invoice_type": rec.invoice_type,
            "buyer_name": rec.buyer_name,
            "seller_name": rec.seller_name,
            "amount": rec.amount,
            "first_seen_at": _fmt_local(rec.first_seen_at),
            "first_task_id": rec.first_task_id,
            "first_filename": rec.first_filename,
            "seen_count": rec.seen_count,
        }


def list_ledger() -> List[dict]:
    """台账列表（按首次处理时间倒序）。"""
    with SessionLocal() as db:
        rows = db.query(InvoiceLedger).order_by(InvoiceLedger.first_seen_at.desc()).all()
        return [{
            "dedup_key": r.dedup_key,
            "invoice_code": r.invoice_code,
            "invoice_no": r.invoice_no,
            "invoice_type": r.invoice_type,
            "buyer_name": r.buyer_name,
            "seller_name": r.seller_name,
            "amount": r.amount,
            "first_seen_at": _fmt_local(r.first_seen_at),
            "first_task_id": r.first_task_id,
            "first_filename": r.first_filename,
            "seen_count": r.seen_count,
        } for r in rows]


def backfill() -> int:
    """把现有 Invoice 中非重复且有号码的票登记进台账（方案 B 键，幂等）。

    使用内存 set 去重，避免同一 session 内未 flush 导致的唯一键冲突。
    """
    with SessionLocal() as db:
        invs = db.query(Invoice).filter(Invoice.is_duplicate == False).all()  # noqa: E712
        existing_keys = {r.dedup_key for r in db.query(InvoiceLedger).all()}
        added = 0
        for inv in invs:
            key = _key(inv.invoice_code, inv.invoice_no)
            if not key or key in existing_keys:
                continue
            db.add(InvoiceLedger(
                dedup_key=key,
                invoice_code=inv.invoice_code,
                invoice_no=inv.invoice_no,
                invoice_type=inv.invoice_type,
                buyer_name=inv.buyer_name,
                seller_name=inv.seller_name,
                amount=inv.amount,
                first_seen_at=inv.created_at or datetime.datetime.utcnow(),
                first_task_id=inv.task_id,
                first_filename=inv.original_filename,
                seen_count=1,
            ))
            existing_keys.add(key)
            added += 1
        db.commit()
        return added
