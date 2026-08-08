#!/usr/bin/env bash
# 启动前端 dev server（setsid 脱离会话）
cd /home/ekewang/projects/gaokao/ln/webapp/frontend
LOG=/home/ekewang/projects/gaokao/ln/webapp/scripts/frontend.log
setsid nohup npm run dev -- --host 0.0.0.0 --port 5173 > "$LOG" 2>&1 &
disown || true
sleep 6
echo "== log =="
tail -n 15 "$LOG"
echo "== port =="
ss -ltn | grep ':5173' || echo "NOT LISTENING"
