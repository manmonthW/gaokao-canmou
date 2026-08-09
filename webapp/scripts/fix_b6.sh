#!/bin/bash
# 清理国标码孤儿行并重跑 B6（省内报考代码口径）
cd /home/ekewang/projects/gaokao/ln/etl || exit 1
python3 - <<'PY'
import psycopg2
from config import DSN
conn = psycopg2.connect(DSN); cur = conn.cursor()
cur.execute("DELETE FROM major_profiles WHERE source='ln_xk_2027' AND school_code NOT IN (SELECT code FROM schools)")
print("orphan rows deleted:", cur.rowcount)
conn.commit(); conn.close()
PY
python3 - <<'PY'
import psycopg2
from config import DSN
import load_material_phase1 as m
conn = psycopg2.connect(DSN)
m.load_b6(conn)
cur = conn.cursor()
cur.execute("SELECT count(*) FROM major_profiles WHERE subject_req IS NOT NULL")
print("major_profiles with subject_req:", cur.fetchone()[0])
conn.close()
PY
