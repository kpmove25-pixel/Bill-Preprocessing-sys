"""去重服务：根据唯一键规则计算去重键、标记重复记录。"""
from __future__ import annotations

import logging
from typing import List

from app.core.config import settings

logger = logging.getLogger(__name__)


def build_dedup_key(
    invoice_type: str,
    invoice_code: str,
    invoice_no: str,
    strategy: str = None,
) -> str:
    """根据去重策略构造唯一键。

    方案 B：不带「发票类型」前缀，规避 OCR 类型识别偏差导致的漏判。
    - 全电发票（20 位号码）直接用号码；
    - 传统票有代码用 `代码::号码`，无代码用号码；
    - strategy='invoice_no' 时仅按发票号码；
    - 无号码返回空，表示无法去重（进入待人工处理）。
    """
    strategy = strategy or settings.dedup_strategy
    code = (invoice_code or "").strip()
    no = (invoice_no or "").strip()

    if strategy == "invoice_no":
        return no or ""

    # 全电发票：20 位号码，无发票代码
    if len(no) == 20:
        return no

    if code:
        return f"{code}::{no}"
    if no:
        return no
    # 无号码：返回空，表示无法去重（进入待人工处理）
    return ""


def deduplicate(invoices: List[dict], strategy: str = None) -> tuple:
    """对发票记录列表执行去重。

    invoices: 每项需含 invoice_type/invoice_code/invoice_no/id 等字段的字典。
    返回 (keep_list, duplicate_list)：
    - keep_list: 保留的记录（附 dedup_key）
    - duplicate_list: 重复记录（附 dedup_key, duplicate_of 指向保留记录的 id）
    """
    seen: dict = {}
    keep: List[dict] = []
    dups: List[dict] = []
    for inv in invoices:
        key = build_dedup_key(
            inv.get("invoice_type", ""),
            inv.get("invoice_code", ""),
            inv.get("invoice_no", ""),
            strategy,
        )
        inv["dedup_key"] = key
        if not key:
            # 无号码，不参与去重，直接保留（标记待人工处理）
            inv["is_duplicate"] = False
            keep.append(inv)
            continue
        if key in seen:
            inv["is_duplicate"] = True
            inv["duplicate_of"] = seen[key]["id"]
            dups.append(inv)
        else:
            seen[key] = inv
            inv["is_duplicate"] = False
            keep.append(inv)
    return keep, dups
