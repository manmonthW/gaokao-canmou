#!/usr/bin/env bash
# 执行 0011/0012/0013/0014/0015 迁移并回读验证（全部幂等可重跑）
set -e
cd /home/ekewang/projects/gaokao/ln
export PGPASSWORD=gaokao123

psql -U gaokao -h localhost -d gaokao -v ON_ERROR_STOP=1 \
  -f webapp/backend/migrations/0011_major_flags.sql
psql -U gaokao -h localhost -d gaokao -v ON_ERROR_STOP=1 \
  -f webapp/backend/migrations/0012_subject_requirements.sql
psql -U gaokao -h localhost -d gaokao -v ON_ERROR_STOP=1 \
  -f webapp/backend/migrations/0013_postgrad_rate.sql
psql -U gaokao -h localhost -d gaokao -v ON_ERROR_STOP=1 \
  -f webapp/backend/migrations/0014_major_strength.sql
psql -U gaokao -h localhost -d gaokao -v ON_ERROR_STOP=1 \
  -f webapp/backend/migrations/0015_major_admission_summary.sql

echo "== flag_dictionary =="
psql -U gaokao -h localhost -d gaokao -c "SELECT flag,label,severity FROM flag_dictionary ORDER BY flag;"
echo "== flags column =="
psql -U gaokao -h localhost -d gaokao -tAc "SELECT column_name FROM information_schema.columns WHERE table_name='admission_scores' AND column_name='flags';"
echo "== subject_requirements =="
psql -U gaokao -h localhost -d gaokao -tAc "SELECT count(*) FROM subject_requirements;"
echo "== postgrad_recommend_rate column =="
psql -U gaokao -h localhost -d gaokao -tAc "SELECT column_name FROM information_schema.columns WHERE table_name='school_profiles' AND column_name='postgrad_recommend_rate';"
echo "== strength tables (0014) =="
psql -U gaokao -h localhost -d gaokao -tAc "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('school_disciplines','major_strengths','strength_dictionary') ORDER BY table_name;"
echo "== strength_dictionary =="
psql -U gaokao -h localhost -d gaokao -tAc "SELECT count(*) FROM strength_dictionary;"
echo "== strength_tags column =="
psql -U gaokao -h localhost -d gaokao -tAc "SELECT column_name FROM information_schema.columns WHERE table_name='school_profiles' AND column_name='strength_tags';"
echo "== major_admission_summary (0015) =="
psql -U gaokao -h localhost -d gaokao -tAc "SELECT count(*) FROM major_admission_summary;"
