#!/bin/bash
# 临时检查：选科链路现状 + 批次数据分布
cd /home/ekewang/projects/gaokao/ln
echo '== grep subject fields =='
grep -n 'excluded_by_subject\|subject_unverified\|subjreq' \
  webapp/backend/app/services/match.py webapp/backend/app/routers/match.py \
  webapp/frontend/src/types.ts webapp/frontend/src/views/Match.vue | head -25
echo '== db checks =='
cd etl && python3 - <<'PY'
import psycopg2
from config import DSN
conn = psycopg2.connect(DSN); cur = conn.cursor()
cur.execute("SELECT batch, count(*) FROM admission_scores GROUP BY batch ORDER BY 2 DESC")
print("batches:", cur.fetchall())
cur.execute("SELECT year, count(*) FROM subject_requirements GROUP BY year")
print("subject_requirements:", cur.fetchall())
cur.execute("SELECT count(*) FROM major_profiles WHERE subject_req IS NOT NULL")
print("major_profiles with subject_req:", cur.fetchone()[0])
cur.execute("SELECT count(DISTINCT school_code) FROM admission_scores WHERE batch LIKE '%专科%'")
print("zk schools in admission:", cur.fetchone()[0])
cur.execute("SELECT count(*) FROM admission_scores WHERE batch LIKE '%提前%'")
print("early-batch rows:", cur.fetchone()[0])
conn.close()
PY
