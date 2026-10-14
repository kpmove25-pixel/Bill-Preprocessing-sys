#!/usr/bin/env bash
# Linux / macOS 启动脚本
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "创建虚拟环境..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt

echo "启动服务，监听 0.0.0.0:8000 ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
