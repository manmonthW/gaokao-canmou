#!/usr/bin/env bash
# 启动后端（setsid 完全脱离会话，日志写入项目内便于查看）
cd /home/ekewang/projects/gaokao/ln/webapp/backend
LOG=/home/ekewang/projects/gaokao/ln/webapp/scripts/backend.log
setsid nohup ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > "$LOG" 2>&1 &
disown || true
sleep 4
echo "== log =="
tail -n 20 "$LOG"
echo "== port =="
ss -ltn | grep ':8000' || echo "NOT LISTENING"
