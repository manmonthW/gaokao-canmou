"""数据中心服务：省控线、一分一段、原始录取记录、源文件、批次发布状态、选科要求。"""
import re

import psycopg2

from app import db
from app.config import MAX_PAGE_SIZE

# 官方选科三表文件名后缀 → 表类型（bk 本科 / zk 专科 / jx 军校）
_XK_TABLE_SUFFIX = re.compile(r"(bk|zk|jx)(?=\.xlsx?$)", re.I)


def _xk_table_of(filename):
    m = _XK_TABLE_SUFFIX.search(filename or "")
    return m.group(1).lower() if m else None


async def control_lines(year=None, category=None, subject=None):
    where = "WHERE 1=1"
    params = []
    if year:
        where += " AND year=%s"; params.append(year)
    if category:
        where += " AND category=%s"; params.append(category)
    if subject:
        where += " AND subject=%s"; params.append(subject)
    rows = await db.fetch_all(
        f"""SELECT year, category, subject, line_type, score, note
            FROM batch_control_line {where}
            ORDER BY year DESC, category, subject, line_type""",
        params,
    )
    return [
        {"year": r[0], "category": r[1], "subject": r[2],
         "line_type": r[3], "score": r[4], "note": r[5]}
        for r in rows
    ]


async def score_rank_table(year, category, subject, page=1, page_size=50):
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    offset = (max(page, 1) - 1) * page_size
    total = await db.fetch_one(
        "SELECT count(*) FROM score_rank WHERE year=%s AND category=%s AND subject=%s",
        (year, category, subject))
    total = total[0] if total else 0
    rows = await db.fetch_all(
        """SELECT score, count, cumulative_rank, is_top_bucket, source
           FROM score_rank
           WHERE year=%s AND category=%s AND subject=%s
           ORDER BY score DESC
           LIMIT %s OFFSET %s""",
        (year, category, subject, page_size, offset),
    )
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [
            {"score": r[0], "count": r[1], "cumulative_rank": r[2],
             "is_top_bucket": r[3], "source": r[4]}
            for r in rows
        ],
    }


async def admission_records(year=None, category=None, subject=None, batch=None,
                            is_collection=None, school=None, major=None,
                            page=1, page_size=50):
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    offset = (max(page, 1) - 1) * page_size
    where = "WHERE 1=1"
    params = []
    if year:
        where += " AND year=%s"; params.append(year)
    if category:
        where += " AND category=%s"; params.append(category)
    if subject:
        where += " AND subject=%s"; params.append(subject)
    if batch:
        where += " AND batch=%s"; params.append(batch)
    if is_collection is not None:
        where += " AND is_collection=%s"; params.append(is_collection)
    if school:
        where += " AND school_name ILIKE %s"; params.append(f"%{school}%")
    if major:
        where += " AND major_name ILIKE %s"; params.append(f"%{major}%")

    total = await db.fetch_one(
        f"SELECT count(*) FROM admission_scores {where}", params)
    total = total[0] if total else 0
    params.extend([page_size, offset])
    rows = await db.fetch_all(
        f"""SELECT year, category, subject, batch, is_collection, score_kind,
                   school_code, school_name, major_code, major_name,
                   lowest_score, lowest_rank, src_id
            FROM admission_scores {where}
            ORDER BY year DESC, category, subject, school_name, major_name
            LIMIT %s OFFSET %s""",
        params,
    )
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [
            {"year": r[0], "category": r[1], "subject": r[2], "batch": r[3],
             "is_collection": r[4], "score_kind": r[5], "school_code": r[6],
             "school_name": r[7], "major_code": r[8], "major_name": r[9],
             "lowest_score": float(r[10]) if r[10] is not None else None,
             "lowest_rank": r[11], "src_id": r[12]}
            for r in rows
        ],
    }


async def source_files():
    rows = await db.fetch_all(
        """SELECT id, filename, fmt, year, category, batch, is_collection,
                  subject, status, note, loaded_at
           FROM source_files
           ORDER BY loaded_at DESC NULLS LAST, id DESC""")
    return [
        {"id": r[0], "filename": r[1], "fmt": r[2], "year": r[3],
         "category": r[4], "batch": r[5], "is_collection": r[6],
         "subject": r[7], "status": r[8], "note": r[9],
         "loaded_at": str(r[10]) if r[10] else None}
        for r in rows
    ]


async def publication_status():
    rows = await db.fetch_all(
        """SELECT year, category, subject, batch, stage, status,
                  official_published_at, system_updated_at, source_url, note
           FROM admission_publication_status
           ORDER BY year DESC, category, subject, batch, stage""")
    return [
        {"year": r[0], "category": r[1], "subject": r[2], "batch": r[3],
         "stage": r[4], "status": r[5],
         "official_published_at": str(r[6]) if r[6] else None,
         "system_updated_at": str(r[7]) if r[7] else None,
         "source_url": r[8], "note": r[9]}
        for r in rows
    ]


async def collection_reference(category, subject=None, batch=None,
                               rank=None, window=0.3):
    """P6 往年征集参考：你的位次带内曾有哪些院校专业进入征集志愿。

    定位是「最坏情况参考」：征集是滑档后真实存在的安全网，帮考生理解
    滑档后的真实世界；征集数据**绝不进入**智能匹配（match 始终
    is_collection=FALSE），两者不冲突。给位次时只看 ±window 位次带内，
    不给位次则返回该批次全部征集记录（限量）。
    """
    window = min(max(window, 0.05), 0.8)
    where = "WHERE is_collection=TRUE AND category=%s"
    params = [category]
    if subject:
        where += " AND subject=%s"; params.append(subject)
    if batch:
        where += " AND batch=%s"; params.append(batch)
    band = None
    if rank and rank > 0:
        band = {"lo": max(1, int(rank * (1 - window))),
                "hi": int(rank * (1 + window))}
        where += " AND lowest_rank BETWEEN %s AND %s"
        params.extend([band["lo"], band["hi"]])
    rows = await db.fetch_all(
        f"""SELECT year, batch, school_name, major_name, score_kind,
                   lowest_score, lowest_rank
            FROM admission_scores {where}
            ORDER BY year DESC, lowest_rank NULLS LAST, school_name
            LIMIT 400""",
        params,
    )
    return {
        "category": category, "subject": subject, "batch": batch,
        "rank": rank, "band": band,
        "items": [
            {"year": r[0], "batch": r[1], "school_name": r[2],
             "major_name": r[3], "score_kind": r[4],
             "lowest_score": float(r[5]) if r[5] is not None else None,
             "lowest_rank": r[6]}
            for r in rows
        ],
        "note": ("征集志愿是常规投档未录满后的补充录取，属于「最坏情况参考」，"
                 "不代表这些院校专业明年的正常录取水平；征集数据不参与本站智能匹配，"
                 "请以省招考办官方征集公告为准。"),
    }


async def subject_requirements_summary():
    """选科要求三表汇总：各年份 × 表类型（本科/专科/军校）行数与院校数。"""
    rows = await db.fetch_all(
        """SELECT sr.year, sf.filename,
                  count(*) AS rows, count(DISTINCT sr.school_name) AS schools
           FROM subject_requirements sr
           JOIN source_files sf ON sf.id = sr.src_id
           GROUP BY sr.year, sf.filename
           ORDER BY sr.year DESC, sf.filename""")
    items = []
    for r in rows:
        t = _xk_table_of(r[1])
        if not t:
            continue
        items.append({"year": r[0], "table": t, "filename": r[1],
                      "rows": r[2], "schools": r[3]})
    return {"items": items,
            "note": ("官方《拟在辽招生普通高校专业选考科目要求》三表："
                     "bk 本科 / zk 专科 / jx 军校；「不限」即不提科目要求。")}


async def subject_requirements(year=None, table=None, school=None, major=None,
                               first_req=None, page=1, page_size=50):
    """选科要求三表明细（分页）：按年份/表类型/院校/专业/首选要求筛选。"""
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    offset = (max(page, 1) - 1) * page_size
    where = "WHERE 1=1"
    params = []
    if year:
        where += " AND sr.year=%s"; params.append(year)
    if table:
        where += " AND sf.filename ILIKE %s"; params.append(f"%{table}.xlsx")
    if school:
        where += " AND sr.school_name ILIKE %s"; params.append(f"%{school}%")
    if major:
        where += " AND sr.major_name ILIKE %s"; params.append(f"%{major}%")
    if first_req:
        where += " AND sr.first_req=%s"; params.append(first_req)

    total = await db.fetch_one(
        f"""SELECT count(*) FROM subject_requirements sr
            JOIN source_files sf ON sf.id = sr.src_id {where}""", params)
    total = total[0] if total else 0
    params.extend([page_size, offset])
    rows = await db.fetch_all(
        f"""SELECT sr.year, sf.filename, sr.school_code, sr.school_name,
                   sr.major_code, sr.major_name, sr.group_code,
                   sr.first_req, sr.re_req
            FROM subject_requirements sr
            JOIN source_files sf ON sf.id = sr.src_id {where}
            ORDER BY sr.year DESC, sr.school_code, sr.school_name,
                     sr.major_code NULLS LAST
            LIMIT %s OFFSET %s""",
        params,
    )
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [
            {"year": r[0], "table": _xk_table_of(r[1]),
             "school_code": r[2], "school_name": r[3],
             "major_code": r[4], "major_name": r[5], "group_code": r[6],
             "first_req": r[7], "re_req": r[8]}
            for r in rows
        ],
    }


async def major_trend(*, subject=None, batch=None, label=None, q=None,
                      page=1, page_size=50):
    """专业冷热趋势全量表（migration 0017），供数据中心透明展示。

    默认按「两段合计超额漂移」的绝对值降序——把移动最剧烈的专业顶上来，
    这是用户最想先看到的；「样本不足」永远排最后。
    """
    where, params = ["1=1"], []
    if subject:
        where.append("t.subject = %s")
        params.append(subject)
    if batch:
        where.append("t.batch = %s")
        params.append(batch)
    if label:
        where.append("t.label = %s")
        params.append(label)
    if q:
        where.append("t.major_key ILIKE %s")
        params.append(f"%{q}%")
    w = " AND ".join(where)
    try:
        total = await db.fetch_one(
            f"SELECT count(*) FROM major_trend t WHERE {w}", params)
    except psycopg2.Error as e:
        if not db.schema_missing(e):
            raise
        return {"total": 0, "page": page, "page_size": page_size, "items": [],
                "unavailable": True}
    total = total[0] if total else 0
    rows = await db.fetch_all(
        f"""SELECT t.subject, t.batch, t.major_key, t.label, t.label_reason,
                   t.n_pairs_1, t.excess_1, t.thr_1, t.concord_1,
                   t.n_pairs_2, t.excess_2, t.thr_2, t.concord_2,
                   t.excess_total, t.units_2024, t.units_2025, t.units_2026,
                   t.eq_score_delta, t.eq_score_delta_market
              FROM major_trend t WHERE {w}
             ORDER BY (t.label = '样本不足'),
                      abs(coalesce(t.excess_total, 0)) DESC,
                      t.major_key
             LIMIT %s OFFSET %s""",
        params + [page_size, (page - 1) * page_size],
    )
    f = lambda v: float(v) if v is not None else None       # noqa: E731
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [
            {"subject": r[0], "batch": r[1], "major_key": r[2],
             "label": r[3], "label_reason": r[4],
             "n_pairs_1": r[5], "excess_1": f(r[6]), "thr_1": f(r[7]),
             "concord_1": f(r[8]),
             "n_pairs_2": r[9], "excess_2": f(r[10]), "thr_2": f(r[11]),
             "concord_2": f(r[12]),
             "excess_total": f(r[13]),
             "units": {"2024": r[14], "2025": r[15], "2026": r[16]},
             "eq_score_delta": f(r[17]), "eq_score_delta_market": f(r[18])}
            for r in rows
        ],
    }


async def major_trend_market():
    """全省大盘门槛漂移基准（各学科类×批次×年段）。"""
    try:
        rows = await db.fetch_all(
            """SELECT subject, batch, year_from, year_to, drift_log
                 FROM major_trend_market ORDER BY subject, batch, year_from""")
    except psycopg2.Error as e:
        if not db.schema_missing(e):
            raise
        return []
    return [{"subject": a, "batch": b, "year_from": c, "year_to": d,
             "drift_log": float(e)} for a, b, c, d, e in rows]
