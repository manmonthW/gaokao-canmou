"""搜索服务：院校（名称/代码）、专业（名称）。

说明：专业标准库（majors）属 Phase 4，本期直接从 admission_scores.major_name
做归一化前的原始名称检索，并按招生院校数排序。
"""
from app import db
from app.config import MAX_PAGE_SIZE


async def search_schools(q: str, limit: int = 20):
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    like = f"%{q}%"
    rows = await db.fetch_all(
        """SELECT s.code, s.name,
                  sp.province, sp.city, sp.level, sp.nature, sp.type,
                  sp.is_985, sp.is_211, sp.is_dfc
           FROM schools s
           LEFT JOIN school_profiles sp ON s.code = sp.code
           WHERE s.name ILIKE %s OR s.code ILIKE %s
           ORDER BY (s.name = %s) DESC, length(s.name) ASC, s.name ASC
           LIMIT %s""",
        (like, like, q, limit),
    )
    return [
        {
            "code": r[0], "name": r[1],
            "province": r[2], "city": r[3], "level": r[4], "nature": r[5],
            "type": r[6], "is_985": r[7], "is_211": r[8], "is_dfc": r[9],
        }
        for r in rows
    ]


async def search_majors(q: str, year=None, category=None, subject=None, limit: int = 20):
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    like = f"%{q}%"
    where = "WHERE a.major_name ILIKE %s"
    params = [like]
    if year:
        where += " AND a.year=%s"; params.append(year)
    if category:
        where += " AND a.category=%s"; params.append(category)
    if subject:
        where += " AND a.subject=%s"; params.append(subject)
    params.append(limit)
    rows = await db.fetch_all(
        f"""SELECT a.major_name,
                   count(DISTINCT a.school_code) AS school_cnt,
                   min(a.lowest_score), max(a.lowest_score),
                   min(a.lowest_rank), max(a.lowest_rank),
                   count(*) AS rec_cnt
            FROM admission_scores a
            {where}
            GROUP BY a.major_name
            ORDER BY school_cnt DESC, a.major_name ASC
            LIMIT %s""",
        params,
    )
    return [
        {
            "major_name": r[0],
            "school_count": r[1],
            "lowest_score_range": [r[2], r[3]],
            "lowest_rank_range": [r[4], r[5]],
            "record_count": r[6],
        }
        for r in rows
    ]
