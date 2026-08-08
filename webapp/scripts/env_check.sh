#!/usr/bin/env bash
# 环境自检：数据库连通性 / 数据版本 / 端口占用
set -e
cd "$(dirname "$0")/.."

export PGPASSWORD=gaokao123
echo "== admission_scores count =="
psql -U gaokao -h localhost -d gaokao -tAc "SELECT count(*) FROM admission_scores;"

echo "== data_releases =="
psql -U gaokao -h localhost -d gaokao -tAc "SELECT version, status FROM data_releases ORDER BY id DESC LIMIT 3;"

echo "== flags column exists? =="
psql -U gaokao -h localhost -d gaokao -tAc "SELECT count(*) FROM information_schema.columns WHERE table_name='admission_scores' AND column_name='flags';"

echo "== gaokao_web_ro role =="
psql -U gaokao -h localhost -d gaokao -tAc "SELECT 1 FROM pg_roles WHERE rolname='gaokao_web_ro';"

echo "== listening ports (8000/5173/5174) =="
ss -ltn 2>/dev/null | grep -E ':(8000|5173|5174)\b' || echo "no dev servers running"

echo "== python / node =="
python3 --version || true
node --version || true
