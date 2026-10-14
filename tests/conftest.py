"""pytest 公共配置。"""
import os
import sys

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 测试期间使用临时 SQLite 数据库，避免污染真实数据
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test.db")
os.environ.setdefault("USE_AUTH", "false")
os.environ.setdefault("OCR_ENGINE", "none")
