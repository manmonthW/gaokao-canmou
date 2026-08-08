#!/usr/bin/env bash
# 重启后端（A1–A4 代码变更后需重启，原进程无 --reload）
set -e
cd "$(dirname "$0")/../backend"
# 杀掉占用 8000 的旧进程
PID=$(ss -tlnp 2>/dev/null | grep ':8000 ' | grep -oP 'pid=\K[0-9]+' | head -1 || true)
if [ -n "$PID" ]; then
  echo "killing old backend pid=$PID"
  kill "$PID" || true
  sleep 2
fi
bash ../scripts/start_backend.sh
sleep 4
for i in $(seq 1 10); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "backend UP"
    exit 0
  fi
  sleep 1
done
echo "backend NOT up, tail of log:"
tail -20 ../scripts/backend.log || true
exit 1
