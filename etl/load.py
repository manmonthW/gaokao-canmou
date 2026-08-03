import psycopg2, psycopg2.extras
from config import DSN


def get_conn():
    return psycopg2.connect(DSN)


def load_file(conn, filename, fmt, meta, records, raw_pages=None,
              status="loaded", note=None, sheet=None):
    """幂等入库：先按文件名删除旧数据，再写入。"""
    raw_pages = raw_pages or []
    with conn:
        with conn.cursor() as cur:
            # 清旧
            cur.execute("SELECT id FROM source_files WHERE filename=%s", (filename,))
            old = cur.fetchone()
            if old:
                sid = old[0]
                cur.execute("DELETE FROM admission_scores WHERE src_id=%s", (sid,))
                cur.execute("DELETE FROM raw_texts WHERE src_id=%s", (sid,))
                cur.execute("DELETE FROM source_files WHERE id=%s", (sid,))

            cur.execute(
                """INSERT INTO source_files
                   (filename,fmt,year,category,batch,is_collection,subject,
                    sheet,status,note,loaded_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
                   RETURNING id""",
                (filename, fmt, meta.get("year"), meta.get("category"),
                 meta.get("batch"), meta.get("is_collection"),
                 meta.get("subject"), sheet, status, note))
            sid = cur.fetchone()[0]

            if status == "encrypted":
                return sid

            # 院校维度
            schools = {(r["school_code"], r["school_name"])
                       for r in records
                       if r.get("school_code") and r.get("school_name")}
            if schools:
                psycopg2.extras.execute_values(
                    cur,
                    "INSERT INTO schools (code,name) VALUES %s "
                    "ON CONFLICT (code) DO NOTHING",
                    list(schools))

            rows = [(
                sid, r.get("year"), r.get("category"), r.get("batch"),
                r.get("is_collection"), r.get("subject"),
                r.get("school_code"), r.get("school_name"),
                r.get("major_code"), r.get("major_name"),
                r.get("score_kind"), r.get("lowest_score"),
                r.get("tb1"), r.get("tb2"), r.get("tb3"), r.get("tb4"),
                r.get("tb5"), r.get("tb6"), r.get("tb7"),
                psycopg2.extras.Json(r.get("raw_row")),
            ) for r in records]
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO admission_scores
                   (src_id,year,category,batch,is_collection,subject,
                    school_code,school_name,major_code,major_name,
                    score_kind,lowest_score,
                    tiebreak_1,tiebreak_2,tiebreak_3,tiebreak_4,
                    tiebreak_5,tiebreak_6,tiebreak_7,raw_row)
                   VALUES %s""",
                rows)

            if raw_pages:
                psycopg2.extras.execute_values(
                    cur,
                    "INSERT INTO raw_texts (src_id,page,content) VALUES %s",
                    [(sid, p, t) for p, t in raw_pages])
    return sid
