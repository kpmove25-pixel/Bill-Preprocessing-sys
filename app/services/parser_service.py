"""票据结构化解析：关键词 + 正则 + 坐标位置综合解析。

输入：OcrBlock 列表（来自 OCR 或 PDF 文本层，均带坐标）。
输出：ParsedInvoice 数据类。
"""
from __future__ import annotations

import dataclasses
import logging
import re
from typing import List, Tuple

from app.services.ocr_service import OcrBlock

logger = logging.getLogger(__name__)

# 金额：￥/¥ + 数字（含逗号、小数点）
_MONEY_RE = re.compile(r"[¥￥]\s*([0-9][0-9,]*\.[0-9]{1,2})")
# 裸数字金额（不带货币符号，用于合计/税额行）
_MONEY_RAW_RE = re.compile(r"([0-9][0-9,]*\.[0-9]{2})")
# 日期：2023年1月1日 / 2023-01-01 / 2023/1/1
_DATE_RE = re.compile(r"(\d{4})\s*[年\-/.]\s*(\d{1,2})\s*[月\-/.]\s*(\d{1,2})\s*日?")
# 税率：6%、13%、1.5% 等
_RATE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


@dataclasses.dataclass
class ParsedInvoice:
    invoice_code: str = ""
    invoice_no: str = ""
    invoice_type: str = ""
    buyer_name: str = ""
    buyer_tax_no: str = ""
    seller_name: str = ""
    seller_tax_no: str = ""
    amount: str = ""  # 价税合计
    amount_excluding_tax: str = ""
    tax_amount: str = ""
    tax_rate: str = ""
    invoice_date: str = ""
    check_code: str = ""
    drawer: str = ""
    ocr_confidence: float = 0.0
    needs_review: bool = False
    remarks: List[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _clean_text(s: str) -> str:
    """全角转半角、去除特殊符号。"""
    if not s:
        return ""
    out = []
    for ch in s:
        code = ord(ch)
        if code == 0x3000:  # 全角空格
            out.append(" ")
        elif 0xFF01 <= code <= 0xFF5E:  # 全角字符
            out.append(chr(code - 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)


def _normalize_amount(s: str) -> str:
    """金额统一两位小数，去除 ￥¥、逗号、空格。"""
    s = _clean_text(s or "")
    s = s.replace("￥", "").replace("¥", "").replace(",", "").replace(" ", "")
    s = re.sub(r"[^0-9.]", "", s)
    if not s:
        return ""
    try:
        return f"{float(s):.2f}"
    except ValueError:
        return ""


def _format_date(y: str, m: str, d: str) -> str:
    try:
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except ValueError:
        return ""


def _find_line_after_keyword(lines: List[Tuple[str, OcrBlock]], keywords: List[str]):
    """在文本行中查找包含关键词的行，返回其后的值文本。"""
    for text, block in lines:
        for kw in keywords:
            idx = text.find(kw)
            if idx != -1:
                after = text[idx + len(kw):].strip(":： \t")
                if after:
                    return after, block
                return None, block
    return None, None


def _first_money(lines: List[Tuple[str, OcrBlock]], keywords: List[str], exclude=None) -> str:
    """在含关键词的行中提取金额。exclude 用于排除包含特定词的干扰行。"""
    exclude = exclude or []
    for text, _ in lines:
        if any(x in text for x in exclude):
            continue
        for kw in keywords:
            if kw in text:
                m = _MONEY_RE.search(text)
                if m:
                    return _normalize_amount(m.group(1))
                m2 = _MONEY_RAW_RE.search(text)
                if m2:
                    return _normalize_amount(m2.group(1))
    return ""


class ParserService:
    """从 OCR 文本块解析票据字段。"""

    def parse(self, blocks: List[OcrBlock]) -> ParsedInvoice:
        result = ParsedInvoice()
        if not blocks:
            result.needs_review = True
            result.remarks.append("无 OCR 文本")
            return result

        lines: List[Tuple[str, OcrBlock]] = []
        for b in blocks:
            t = _clean_text(b.text).strip()
            if t:
                lines.append((t, b))

        full_text = "\n".join(t for t, _ in lines)
        result.ocr_confidence = self._avg_confidence(blocks)

        result.invoice_type = self._detect_type(full_text)
        result.invoice_code = self._extract_invoice_code(lines)
        result.invoice_no = self._extract_invoice_no(lines, full_text)

        if self._has_multiple_invoice_no(lines):
            result.needs_review = True
            result.remarks.append("疑似一页多票，需人工处理")

        result.buyer_name, result.seller_name = self._extract_names(lines)

        result.buyer_tax_no, result.seller_tax_no = self._extract_tax_nos(lines)

        result.amount, result.amount_excluding_tax, result.tax_amount = (
            self._extract_amounts(lines)
        )
        result.tax_rate = self._extract_rate(full_text)

        result.invoice_date = self._extract_date(full_text)
        result.check_code = self._extract_check_code(lines)
        result.drawer = self._extract_drawer(lines)

        if not result.invoice_no:
            result.needs_review = True
            result.remarks.append("发票号码缺失")
        if not result.buyer_name and not result.seller_name:
            result.needs_review = True
            result.remarks.append("购买方/销售方名称缺失")
        if not result.invoice_type:
            result.needs_review = True
            result.remarks.append("票种无法识别")

        return result

    # ---- 内部方法 ----

    @staticmethod
    def _avg_confidence(blocks: List[OcrBlock]) -> float:
        if not blocks:
            return 0.0
        return round(sum(b.confidence for b in blocks) / len(blocks), 4)

    @staticmethod
    def _detect_type(full_text: str) -> str:
        if "增值税专用发票" in full_text:
            return "增值税专用发票"
        if "全电发票" in full_text or "数电票" in full_text or "全面数字化电子发票" in full_text:
            return "全电发票"
        if "增值税普通发票" in full_text or "增值税电子普通发票" in full_text:
            return "电子普通发票" if "电子" in full_text else "增值税普通发票"
        if "电子发票" in full_text and "普通" in full_text:
            return "电子普通发票"
        if "电子发票" in full_text and "专用" in full_text:
            return "增值税专用发票"
        return ""

    @staticmethod
    def _extract_invoice_code(lines) -> str:
        # 仅匹配「发票代码」，避免误命中「统一社会信用代码」
        val, _ = _find_line_after_keyword(lines, ["发票代码"])
        if val:
            m = re.search(r"(\d{8,12})", val)
            if m:
                return m.group(1)
        return ""

    @staticmethod
    def _extract_invoice_no(lines, full_text: str) -> str:
        val, _ = _find_line_after_keyword(lines, ["发票号码", "号码", "No:", "No."])
        if val:
            m = re.search(r"(\d{8,20})", val)
            if m:
                return m.group(1)
        # 分块：「发票号码」标签右侧的号码（避免全局匹配到银行账号等）
        val2 = ParserService._value_after_label(lines, ["发票号码", "号码"])
        if val2:
            m = re.search(r"(\d{8,20})", val2)
            if m:
                return m.group(1)
        m20 = re.search(r"(?<!\d)(\d{20})(?!\d)", full_text)
        if m20:
            return m20.group(1)
        return ""

    @staticmethod
    def _has_multiple_invoice_no(lines) -> bool:
        # 仅统计「发票号码」关键词行中的 20 位号码，避免银行账号等干扰
        nums = set()
        for text, block in lines:
            if "发票号码" in text or "发票号" in text:
                nums.update(re.findall(r"(?<!\d)(\d{20})(?!\d)", text))
        return len(nums) > 1

    @staticmethod
    def _valid_name(s: str) -> str:
        """清洗名称值，排除数字/金额/日期/标签词等非名称内容。"""
        s = re.sub(r"[：:]\s*", "", s).strip()
        if not s or s.isdigit():
            return ""
        if _MONEY_RE.search(s) or _DATE_RE.search(s):
            return ""
        # 排除标签词（信用代码/税号/号码/日期等，避免误当名称）
        for kw in ("统一社会信用代码", "纳税人识别号", "信用代码", "识别号", "税号",
                   "发票号码", "发票代码", "开票日期", "名称"):
            if kw in s:
                return ""
        return s

    @staticmethod
    def _extract_names(lines) -> Tuple[str, str]:
        """提取购买方/销售方名称，兼顾传统与数电发票布局。

        1) 关键词 + 值同行（传统发票/旧票据：「购买方名称 值」）；
        2) 布局感知（数电发票：「名称：xxx」同块或「名称：」+ 值分块），
           按坐标判断左右/上下布局：左（上）=购买方，右（下）=销售方。
        """
        # 1) 关键词 + 值同行（传统发票/旧票据：「购买方名称 值」）
        buyer = ""
        seller = ""
        for text, block in lines:
            if not buyer:
                m = re.search(
                    r"(?:购买方名称|购方名称|购买方信息|购方信息)\s*[:：]?\s*([^\s：:，,]+)",
                    text,
                )
                if m:
                    buyer = ParserService._valid_name(m.group(1))
            if not seller:
                m = re.search(
                    r"(?:销售方名称|销方名称|销售方信息|销方信息)\s*[:：]?\s*([^\s：:，,]+)",
                    text,
                )
                if m:
                    seller = ParserService._valid_name(m.group(1))
        if buyer or seller:
            return buyer, seller

        # 2) 布局感知
        name_rows: List[Tuple[str, float, float]] = []

        # 1) 「名称：xxx」同块
        for text, block in lines:
            m = re.match(r"^名称\s*[:：]?\s*(.+)$", text)
            if m:
                val = ParserService._valid_name(m.group(1))
                if val:
                    name_rows.append((val, block.center_x, block.center_y))

        # 2) 「名称：」独立块 + 右侧/下方值块（PDF 文本层拆块）
        label_pos = [
            (block.center_x, block.center_y)
            for text, block in lines
            if re.fullmatch(r"名称\s*[:：]?", text)
        ]
        for lx, ly in label_pos:
            best = None
            for text, block in lines:
                val = ParserService._valid_name(text)
                if not val:
                    continue
                dx = block.center_x - lx
                dy = abs(block.center_y - ly)
                if dx > 0 and dy < 15:
                    if best is None or block.center_x < best[1][0]:
                        best = (val, (block.center_x, block.center_y))
            if best:
                name_rows.append((best[0], best[1][0], best[1][1]))

        # 去重
        seen = set()
        uniq = []
        for r in name_rows:
            if r[0] not in seen:
                seen.add(r[0])
                uniq.append(r)

        if not uniq:
            return "", ""
        if len(uniq) == 1:
            return uniq[0][0], ""

        (n1, x1, y1), (n2, x2, y2) = uniq[0], uniq[1]
        if abs(x1 - x2) >= abs(y1 - y2):
            # 左右布局：左=购买方，右=销售方
            return (n1, n2) if x1 < x2 else (n2, n1)
        # 上下布局：上=购买方，下=销售方
        return (n1, n2) if y1 < y2 else (n2, n1)

    @staticmethod
    def _extract_tax_nos(lines) -> Tuple[str, str]:
        """布局感知提取购买方/销售方税号（统一社会信用代码）。

        1) 优先从含「信用代码/税号/识别号」关键词的行提取 15-20 位字母数字；
        2) 补充独立成行的 15-20 位字母数字（排除纯数字发票号码）；
        3) 按坐标左右/上下布局归入购买方/销售方。
        """
        tax_rows: List[Tuple[str, float, float]] = []

        def add(val: str, block) -> None:
            val = val.strip().upper()
            if len(val) == 20 and val.isdigit():
                return  # 排除纯 20 位发票号码
            if not re.fullmatch(r"[0-9A-Z]{15,20}", val):
                return
            if not any(c.isdigit() for c in val):
                return
            if any(val == t for t, _, _ in tax_rows):
                return
            tax_rows.append((val, block.center_x, block.center_y))

        # 1) 带关键词的行
        for text, block in lines:
            if not any(
                kw in text
                for kw in ("统一社会信用代码", "纳税人识别号", "信用代码", "识别号", "税号")
            ):
                continue
            for m in re.finditer(r"[0-9A-Z]{15,20}", text):
                add(m.group(0), block)

        # 2) 独立成行的税号（补充，应对「标签」「值」分块）
        if len(tax_rows) < 2:
            for text, block in lines:
                t = text.strip().upper()
                if not t.isdigit() and re.fullmatch(r"[0-9A-Z]{15,20}", t):
                    add(t, block)

        if not tax_rows:
            return "", ""
        if len(tax_rows) == 1:
            return tax_rows[0][0], ""

        (t1, x1, y1), (t2, x2, y2) = tax_rows[0], tax_rows[1]
        if abs(x1 - x2) >= abs(y1 - y2):
            return (t1, t2) if x1 < x2 else (t2, t1)
        return (t1, t2) if y1 < y2 else (t2, t1)

    @staticmethod
    def _extract_amounts(lines) -> Tuple[str, str, str]:
        """布局感知提取价税合计、不含税金额、税额。

        金额行通常带 ¥/￥ 前缀；价税合计 = 不含税 + 税额，故金额最大；
        排除价税合计后，次大 = 不含税金额，最小 = 税额（税额恒小于不含税）。
        """
        money: List[Tuple[float, str, float, float]] = []
        for text, block in lines:
            for m in re.finditer(r"[¥￥]\s*([0-9][0-9,]*\.[0-9]{1,2})", text):
                val = _normalize_amount(m.group(1))
                if not val:
                    continue
                money.append((float(val), val, block.center_x, block.center_y))

        if not money:
            return "", "", ""

        # 按值去重（同一金额可能重复出现）
        seen = set()
        dedup = []
        for r in money:
            if r[1] not in seen:
                seen.add(r[1])
                dedup.append(r)
        money = dedup

        # 按金额降序
        money.sort(key=lambda r: -r[0])

        amount = money[0][1]
        rest = money[1:]
        excluding = rest[0][1] if rest else ""
        tax = rest[-1][1] if len(rest) >= 2 else ""

        return amount, excluding, tax

    @staticmethod
    def _extract_rate(full_text: str) -> str:
        m = _RATE_RE.search(full_text)
        if m:
            return f"{float(m.group(1)):.2f}%"
        return ""

    @staticmethod
    def _extract_date(full_text: str) -> str:
        for line in full_text.split("\n"):
            if "开票日期" in line or "日期" in line:
                m = _DATE_RE.search(line)
                if m:
                    return _format_date(m.group(1), m.group(2), m.group(3))
        m = _DATE_RE.search(full_text)
        if m:
            return _format_date(m.group(1), m.group(2), m.group(3))
        return ""

    @staticmethod
    def _value_after_label(lines, labels) -> str:
        """提取标签后的值：优先同行，其次标签右侧/下方最近块（应对「标签」「值」分块）。"""
        val, _ = _find_line_after_keyword(lines, labels)
        if val:
            return val
        # 分块：标签块 → 右侧/下方最近的值块
        for text, lbl in lines:
            if not any(lb in text for lb in labels):
                continue
            lx, ly = lbl.center_x, lbl.center_y
            best = None
            for t, blk in lines:
                s = t.strip()
                if not s:
                    continue
                if any(lb in s for lb in labels):
                    continue
                dx = blk.center_x - lx
                dy = blk.center_y - ly
                if dx > -5 and -5 <= dy <= 40:
                    if best is None or (blk.center_y, blk.center_x) < best[1]:
                        best = (s, (blk.center_y, blk.center_x))
            if best:
                return best[0]
        return ""

    @staticmethod
    def _extract_check_code(lines) -> str:
        val = ParserService._value_after_label(lines, ["校验码"])
        return val.strip()[:40] if val else ""

    @staticmethod
    def _extract_drawer(lines) -> str:
        val = ParserService._value_after_label(lines, ["开票人"])
        return val.strip()[:30] if val else ""


parser_service = ParserService()
