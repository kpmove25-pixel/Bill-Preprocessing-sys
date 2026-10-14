"""FastAPI 应用入口。"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, health, invoices, ledger, tasks
from app.core.config import BASE_DIR, settings
from app.core.database import init_db
from app.core.logging_config import setup_logging
from app.services import ledger_service
from app.workers import worker

WEB_DIR = BASE_DIR / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings.ensure_dirs()
    init_db()
    ledger_service.backfill()
    worker.start_worker()
    yield
    worker.stop_worker()


app = FastAPI(title="票据预处理与 OCR 归档系统", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 业务路由
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(tasks.router)
app.include_router(invoices.router)
app.include_router(ledger.router)


# 前端静态资源
if (WEB_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(str(WEB_DIR / "index.html"))


@app.exception_handler(404)
async def not_found(request, exc):
    # 前端路由回退到 index.html
    if request.url.path.startswith("/api"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return FileResponse(str(WEB_DIR / "index.html"))
