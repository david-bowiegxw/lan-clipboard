#!/usr/bin/env bash
# LAN Clipboard · 局域网剪贴板 — one-click start (macOS / Linux)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "📦 Creating virtual environment · 创建虚拟环境…"
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "📥 Checking dependencies · 检查依赖…"
pip3 install -q -r requirements.txt

mkdir -p "$SCRIPT_DIR/uploads"

echo ""
echo "🚀 Starting server · 启动服务…"
python3 server.py
