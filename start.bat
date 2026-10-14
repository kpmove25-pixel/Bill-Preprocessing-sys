@echo off
REM Windows 启动脚本
cd /d %~dp0

if not exist .venv (
    echo 创建虚拟环境...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install -r requirements.txt

echo 启动服务，监听 0.0.0.0:8000 ...
uvicorn app.main:app --host 0.0.0.0 --port 8000
