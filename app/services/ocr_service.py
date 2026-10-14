"""OCR 引擎抽象层。

支持 RapidOCR（默认）、PaddleOCR（可切换）、None（仅 PDF 文本）。
统一输出 OcrBlock 列表：文本 + 置信度 + 坐标。
"""
from __future__ import annotations

import base64
import dataclasses
import json
import logging
import time
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class OcrBlock:
    """单行 OCR 结果。bbox 为 (x0, y0, x1, y1)，原点在左上角。"""

    text: str
    confidence: float = 0.0
    bbox: tuple = (0, 0, 0, 0)

    @property
    def center_y(self) -> float:
        return (self.bbox[1] + self.bbox[3]) / 2

    @property
    def center_x(self) -> float:
        return (self.bbox[0] + self.bbox[2]) / 2


class BaseOcrEngine(ABC):
    name: str = "base"

    @abstractmethod
    def recognize(self, image_path: str) -> List[OcrBlock]:
        """识别单张图片，返回 OcrBlock 列表。"""


class RapidOcrEngine(BaseOcrEngine):
    name = "rapidocr"

    def __init__(self):
        self._engine = None
        self._init_error: Optional[str] = None
        try:
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR()
        except Exception as e:  # noqa: BLE001
            self._init_error = str(e)
            logger.warning("RapidOCR 初始化失败，将降级为无 OCR：%s", e)

    def recognize(self, image_path: str) -> List[OcrBlock]:
        if self._engine is None:
            logger.warning("RapidOCR 不可用（%s），返回空结果", self._init_error)
            return []
        result, _ = self._engine(image_path)
        blocks: List[OcrBlock] = []
        if not result:
            return blocks
        for item in result:
            # rapidocr 返回 [box, text, score]
            box = item[0]
            text = item[1]
            score = float(item[2]) if len(item) > 2 else 0.0
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            bbox = (min(xs), min(ys), max(xs), max(ys))
            blocks.append(OcrBlock(text=text, confidence=score, bbox=bbox))
        return blocks


class PaddleOcrEngine(BaseOcrEngine):
    name = "paddleocr"

    def __init__(self, lang: str = "ch"):
        self._engine = None
        self._init_error: Optional[str] = None
        try:
            from paddleocr import PaddleOCR

            self._engine = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
        except Exception as e:  # noqa: BLE001
            self._init_error = str(e)
            logger.warning("PaddleOCR 初始化失败，将降级为无 OCR：%s", e)

    def recognize(self, image_path: str) -> List[OcrBlock]:
        if self._engine is None:
            logger.warning("PaddleOCR 不可用（%s），返回空结果", self._init_error)
            return []
        raw = self._engine.ocr(image_path, cls=True)
        blocks: List[OcrBlock] = []
        if not raw:
            return blocks
        for line in raw:
            if not line:
                continue
            for item in line:
                box = item[0]
                text = item[1][0]
                score = float(item[1][1])
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                bbox = (min(xs), min(ys), max(xs), max(ys))
                blocks.append(OcrBlock(text=text, confidence=score, bbox=bbox))
        return blocks


class BaiduOcrEngine(BaseOcrEngine):
    """百度云通用文字识别（高精度·含位置）引擎。

    使用 API Key + Secret Key 换取 access_token（30 天有效，内存缓存），
    调用 /rest/2.0/ocr/v1/accurate 接口，返回带坐标与置信度的文字行。
    """

    name = "baidu"
    TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
    OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate"

    def __init__(self):
        self._api_key = (settings.baidu_api_key or "").strip()
        self._secret_key = (settings.baidu_secret_key or "").strip()
        self._token: Optional[str] = None
        self._token_expire: float = 0.0
        self._init_error: Optional[str] = None
        if not self._api_key or not self._secret_key:
            self._init_error = "未配置 BAIDU_API_KEY / BAIDU_SECRET_KEY"
            logger.warning("百度 OCR 未配置密钥，将返回空结果")

    def _get_access_token(self) -> str:
        """获取并缓存 access_token（提前 60 秒过期）。"""
        if self._token and time.time() < self._token_expire - 60:
            return self._token
        params = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self._api_key,
                "client_secret": self._secret_key,
            }
        )
        req = urllib.request.Request(f"{self.TOKEN_URL}?{params}", method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if "access_token" not in data:
            raise RuntimeError(f"百度云 token 获取失败: {data}")
        self._token = data["access_token"]
        # 默认 2592000 秒（30 天）
        self._token_expire = time.time() + int(data.get("expires_in", 2592000))
        return self._token

    def recognize(self, image_path: str) -> List[OcrBlock]:
        if self._init_error:
            logger.warning("百度 OCR 不可用（%s），返回空结果", self._init_error)
            return []
        try:
            token = self._get_access_token()
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
            body = urllib.parse.urlencode({"image": img_b64}).encode("utf-8")
            url = f"{self.OCR_URL}?access_token={token}"
            req = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "error_code" in data:
                raise RuntimeError(
                    f"百度 OCR 识别失败({data.get('error_code')}): {data.get('error_msg')}"
                )
            blocks: List[OcrBlock] = []
            for item in data.get("words_result", []) or []:
                text = item.get("words", "")
                if not text or not text.strip():
                    continue
                loc = item.get("location", {}) or {}
                left = int(loc.get("left", 0))
                top = int(loc.get("top", 0))
                width = int(loc.get("width", 0))
                height = int(loc.get("height", 0))
                prob = item.get("probability", {})
                if isinstance(prob, dict):
                    conf = float(prob.get("average", 1.0))
                else:
                    conf = 1.0
                blocks.append(
                    OcrBlock(
                        text=text,
                        confidence=conf,
                        bbox=(left, top, left + width, top + height),
                    )
                )
            return blocks
        except Exception as e:  # noqa: BLE001
            logger.warning("百度 OCR 识别异常: %s", e)
            return []


class NoneOcrEngine(BaseOcrEngine):
    """无 OCR 引擎，仅用于 PDF 文本层提取场景。"""

    name = "none"

    def recognize(self, image_path: str) -> List[OcrBlock]:
        return []


_ENGINE: Optional[BaseOcrEngine] = None


def get_ocr_engine() -> BaseOcrEngine:
    """单例获取 OCR 引擎（按配置实例化）。"""
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    name = settings.ocr_engine.lower()
    if name == "rapidocr":
        _ENGINE = RapidOcrEngine()
    elif name == "paddleocr":
        _ENGINE = PaddleOcrEngine(lang=settings.ocr_lang)
    elif name == "baidu":
        _ENGINE = BaiduOcrEngine()
    else:
        _ENGINE = NoneOcrEngine()
    return _ENGINE


def reset_ocr_engine() -> None:
    """重置引擎（测试用）。"""
    global _ENGINE
    _ENGINE = None
