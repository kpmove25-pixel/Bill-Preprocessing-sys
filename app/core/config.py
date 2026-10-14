"""应用配置，统一从环境变量读取（可被 .env 覆盖）。"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 数据目录
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
FAILED_DIR = BASE_DIR / "failed"
MODEL_DIR = BASE_DIR / "models"


class Settings:
    def __init__(self):
        self.app_host = os.getenv("APP_HOST", "0.0.0.0")
        self.app_port = int(os.getenv("APP_PORT", "8000"))

        self.database_url = os.getenv(
            "DATABASE_URL", f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}"
        )

        # 登录
        self.use_auth = os.getenv("USE_AUTH", "true").lower() in ("1", "true", "yes", "on")
        self.app_username = os.getenv("APP_USERNAME", "admin")
        self.app_password = os.getenv("APP_PASSWORD", "admin123")

        # OCR
        self.ocr_engine = os.getenv("OCR_ENGINE", "rapidocr")
        self.ocr_lang = os.getenv("OCR_LANG", "ch")
        self.ocr_confidence_threshold = float(
            os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.6")
        )

        # 百度云 OCR（OCR_ENGINE=baidu 时生效）
        self.baidu_api_key = os.getenv("BAIDU_API_KEY", "")
        self.baidu_secret_key = os.getenv("BAIDU_SECRET_KEY", "")

        # 上传
        self.max_upload_size_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
        self.max_upload_size = self.max_upload_size_mb * 1024 * 1024

        # 图片
        self.jpg_quality = int(os.getenv("JPG_QUALITY", "92"))

        # 去重策略：unique(类型+代码+号码) / invoice_no(仅号码)
        self.dedup_strategy = os.getenv("DEDUP_STRATEGY", "unique")

    def ensure_dirs(self):
        for d in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, FAILED_DIR, MODEL_DIR):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
