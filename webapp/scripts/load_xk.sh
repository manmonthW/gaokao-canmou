#!/bin/bash
# 灌入 2027 选科要求三表（bk/zk/jx）
cd /home/ekewang/projects/gaokao/ln/etl || exit 1
for t in bk zk jx; do
  python3 load_subject_requirements.py --file "../2026allmaterial/2027lnzsxkap0407${t}.xlsx" --year 2027
done
python3 - <<'PY'
import psycopg2
from config import DSN
conn = psycopg2.connect(DSN); cur = conn.cursor()
cur.execute("SELECT count(*), count(DISTINCT school_code) FROM subject_requirements WHERE year=2027")
print("total/distinct-schools:", cur.fetchone())
cur.execute("SELECT first_req, count(*) FROM subject_requirements WHERE year=2027 GROUP BY 1 ORDER BY 2 DESC LIMIT 8")
print("first_req dist:", cur.fetchall())
cur.execute("SELECT school_name, major_name, first_req, re_req FROM subject_requirements WHERE year=2027 AND re_req IS NOT NULL LIMIT 5")
for r in cur.fetchall(): print("sample:", r)
conn.close()
PY
