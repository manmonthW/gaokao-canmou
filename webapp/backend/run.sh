#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
# 使用本地 venv 的 uvicorn；端口可用 PORT 环境变量覆盖（默认 8000）
exec ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
