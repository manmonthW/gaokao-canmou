#!/usr/bin/env bash
# 启动前体检：PostgreSQL 状态 + 端口占用
echo "== postgres =="
pg_isready -h localhost -p 5432 || echo "PG_DOWN"
echo "== ports 8000 / 5173 =="
(ss -ltn 2>/dev/null | grep -E ':(8000|5173)\b') || echo "ports free"
