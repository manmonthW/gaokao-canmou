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


def sync_publication_status(conn):
    """按库内数据同步发布状态矩阵：admission_scores 中存在的
    (年×类别×学科类×批次×阶段) 组合一律标记「已完成」（幂等）；
    无数据的组合（如「待发布」占位行）不动。防止矩阵出现
    「库内有数据但未登记发布状态」的登记遗漏（2024 接入曾漏）。"""
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO admission_publication_status
                  (year, category, subject, batch, stage, status, system_updated_at)
                SELECT DISTINCT year, category, subject, batch,
                       CASE WHEN is_collection THEN '征集' ELSE '常规' END,
                       '已完成', now()
                FROM admission_scores
                WHERE year IS NOT NULL AND category IS NOT NULL
                  AND subject IS NOT NULL AND batch IS NOT NULL
                ON CONFLICT (year, category, subject, batch, stage)
                DO UPDATE SET status='已完成', note=NULL, system_updated_at=now()""")
            return cur.rowcount
