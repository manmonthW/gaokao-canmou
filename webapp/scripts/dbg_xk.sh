#!/bin/bash
cd /home/ekewang/projects/gaokao/ln/etl || exit 1
python3 - <<'PY'
import psycopg2
from config import DSN
conn = psycopg2.connect(DSN); cur = conn.cursor()
# 2027 目标年的匹配池用 2025/2026 投档单元；看 school_code 口径
cur.execute("SELECT school_code, school_name, major_name FROM admission_scores WHERE year=2026 AND batch='本科批' LIMIT 3")
print("admission sample:", cur.fetchall())
cur.execute("SELECT school_code, school_name, major_name FROM subject_requirements WHERE year=2027 AND school_name='北京大学' LIMIT 3")
print("subjreq sample:", cur.fetchall())
cur.execute("""SELECT count(*) FROM (
  SELECT DISTINCT a.school_code, a.major_name FROM admission_scores a WHERE a.year IN (2025,2026)) u
  JOIN subject_requirements s ON s.school_code=u.school_code AND s.major_name=u.major_name AND s.year=2027""")
print("unit-level join hits:", cur.fetchone()[0])
cur.execute("""SELECT count(*) FROM (
  SELECT DISTINCT a.school_code, a.major_name FROM admission_scores a WHERE a.year IN (2025,2026)) u
  JOIN subject_requirements s ON s.school_name=u.school_code AND s.major_name=u.major_name AND s.year=2027""")
print("join by school_name-as-code:", cur.fetchone()[0])
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='schools'")
print('schools cols:', [r[0] for r in cur.fetchall()])
cur.execute("SELECT code, name FROM schools WHERE name IN ('河南理工大学','北京大学')")
print('schools sample:', cur.fetchall())
cur.execute("""SELECT count(*) FROM (SELECT DISTINCT school_name, major_name FROM admission_scores WHERE year IN (2025,2026)) u
  JOIN subject_requirements s ON s.school_name=u.school_name AND s.major_name=u.major_name AND s.year=2027""")
print('join by (school_name, major_name):', cur.fetchone()[0])
cur.execute("""SELECT count(*) FROM subject_requirements s WHERE s.year=2027
  AND EXISTS (SELECT 1 FROM admission_scores a WHERE a.year IN (2025,2026) AND a.school_name=s.school_name)""")
print('school-name level coverage:', cur.fetchone()[0])
conn.close()
PY
