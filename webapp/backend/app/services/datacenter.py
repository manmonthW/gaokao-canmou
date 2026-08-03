"""数据中心服务：省控线、一分一段、原始录取记录、源文件、批次发布状态。"""
from app import db
from app.config import MAX_PAGE_SIZE


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
