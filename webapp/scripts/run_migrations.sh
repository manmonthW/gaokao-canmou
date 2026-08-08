#!/usr/bin/env bash
# 执行 0011/0012 迁移并回读验证
set -e
cd /home/ekewang/projects/gaokao/ln
export PGPASSWORD=gaokao123

psql -U gaokao -h localhost -d gaokao -v ON_ERROR_STOP=1 \
  -f webapp/backend/migrations/0011_major_flags.sql
psql -U gaokao -h localhost -d gaokao -v ON_ERROR_STOP=1 \
  -f webapp/backend/migrations/0012_subject_requirements.sql

echo "== flag_dictionary =="
psql -U gaokao -h localhost -d gaokao -c "SELECT flag,label,severity FROM flag_dictionary ORDER BY flag;"
echo "== flags column =="
psql -U gaokao -h localhost -d gaokao -tAc "SELECT column_name FROM information_schema.columns WHERE table_name='admission_scores' AND column_name='flags';"
echo "== subject_requirements =="
psql -U gaokao -h localhost -d gaokao -tAc "SELECT count(*) FROM subject_requirements;"
