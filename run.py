"""本地启动入口。"""
import uvicorn

from app.core.config import settings

if __name__ == "__main__":
    settings.ensure_dirs()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )
