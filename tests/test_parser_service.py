"""解析器测试。"""
from app.services.ocr_service import OcrBlock
from app.services.parser_service import ParserService


def _blocks(lines):
    return [
        OcrBlock(text=t, confidence=0.9, bbox=(0, i * 20, 400, i * 20 + 18))
        for i, t in enumerate(lines)
    ]


SAMPLE = [
    "增值税专用发票",
    "发票代码 011001900111",
    "发票号码 12345678",
    "开票日期 2023年05月15日",
    "购买方名称 测试科技有限公司",
    "纳税人识别号 91310000774400001X",
    "销售方名称 示例贸易有限公司",
    "纳税人识别号 91440300MA5D123456",
    "合计 ￥1,000.00",
    "税额 ￥130.00",
    "价税合计(小写) ￥1,130.00",
    "税率 13%",
    "开票人 张三",
    "校验码 12345678901234567890",
]


def test_parse_basic_fields():
    parsed = ParserService().parse(_blocks(SAMPLE))
    assert parsed.invoice_type == "增值税专用发票"
    assert parsed.invoice_code == "011001900111"
    assert parsed.invoice_no == "12345678"
    assert parsed.buyer_name == "测试科技有限公司"
    assert parsed.seller_name == "示例贸易有限公司"
    assert parsed.invoice_date == "2023-05-15"
    assert parsed.amount == "1130.00"
    assert parsed.tax_amount == "130.00"
    assert parsed.amount_excluding_tax == "1000.00"
    assert parsed.tax_rate == "13.00%"
    assert parsed.drawer == "张三"


def test_parse_full_electric():
    lines = [
        "电子发票（全电发票）",
        "发票号码 24042000000012345678",
        "开票日期 2024年4月20日",
        "购买方信息 名称：北京某某有限公司",
        "统一社会信用代码 91110105MA00XXXX00",
        "销售方信息 名称：上海某某科技有限公司",
        "统一社会信用代码 91310115MA1XXXXX00",
        "价税合计（大写）壹仟壹佰叁拾元整",
        "价税合计（小写）￥1,130.00",
        "税率 13%",
    ]
    parsed = ParserService().parse(_blocks(lines))
    assert parsed.invoice_type == "全电发票"
    assert parsed.invoice_no == "24042000000012345678"
    assert parsed.amount == "1130.00"


def test_parse_missing_no_marks_review():
    parsed = ParserService().parse(_blocks(["增值税普通发票", "金额 ￥100.00"]))
    assert parsed.needs_review is True


def test_normalize_amount():
    from app.services.parser_service import _normalize_amount

    assert _normalize_amount("￥1,234.56") == "1234.56"
    assert _normalize_amount("¥ 88.8") == "88.80"
    assert _normalize_amount("") == ""
