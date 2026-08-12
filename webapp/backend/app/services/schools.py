"""院校与院校专业详情服务。"""
from app import db
from app.config import MAX_PAGE_SIZE


async def get_school_strength(code: str):
    """院校学科实力聚合（任务 #8，migration 0014）：学科评估/一流学科 +
    一流专业与第三方评级 + 院校级实力标签。院校不存在返回 None；
    三张明细表为空时返回空列表，不报错。

    展示口径（与 strength_dictionary 免责语义一致）：
    - school_disciplines 只返回 verify_status='verified' 或 official=TRUE 的行；
      eval5_a 为非官方来源（official=FALSE），未人工核验前不对外返回。
    - major_strengths 按 source/data_year 排序，LIMIT 500 防极端膨胀。
    """
    basic = await db.fetch_one("SELECT code FROM schools WHERE code=%s", (code,))
    if not basic:
        return None
    disc_rows = await db.fetch_all(
        """SELECT discipline_name, source, data_year, grade, official,
                  verify_status
           FROM school_disciplines
           WHERE school_code=%s AND (verify_status = 'verified' OR official = TRUE)
           ORDER BY source, data_year, discipline_name""", (code,))
    major_rows = await db.fetch_all(
        """SELECT major_name, major_code, source, data_year, batch, rank, tier,
                  note
           FROM major_strengths WHERE school_code=%s
           ORDER BY source, data_year LIMIT 500""", (code,))
    tags_row = await db.fetch_one(
        "SELECT strength_tags FROM school_profiles WHERE code=%s", (code,))
    return {
        "disciplines": [
            {"discipline_name": r[0], "source": r[1], "data_year": r[2],
             "grade": r[3], "official": r[4], "verify_status": r[5]}
            for r in disc_rows
        ],
        "majors": [
            {"major_name": r[0], "major_code": r[1], "source": r[2],
             "data_year": r[3], "batch": r[4], "rank": r[5],
             "tier": r[6], "note": r[7]}
            for r in major_rows
        ],
        "strength_tags": list((tags_row[0] if tags_row else None) or []),
    }


async def get_school(code: str):
    basic = await db.fetch_one(
        "SELECT code, name FROM schools WHERE code=%s", (code,))
    if not basic:
        return None
    prof = await db.fetch_one(
        """SELECT province, city, affiliation, level, nature, type,
                  is_985, is_211, is_dfc, established, strength,
                  school_style, employment_region, rank_ref, note,
                  website, intro, postgrad_recommend_rate
           FROM school_profiles WHERE code=%s""", (code,))
    city = None
    if prof and prof[1]:
        c = await db.fetch_one(
            """SELECT city, province, region, tier, gdp, gdp_year,
                      cluster, coastal, note
               FROM cities WHERE city=%s""", (prof[1],))
        if c:
            city = {
                "city": c[0], "province": c[1], "region": c[2], "tier": c[3],
                "gdp": float(c[4]) if c[4] is not None else None,
                "gdp_year": c[5], "cluster": c[6], "coastal": c[7], "note": c[8],
            }
    yearly = await db.fetch_all(
        """SELECT year, category, subject, count(*) AS recs,
                  count(DISTINCT major_name) AS majors,
                  min(lowest_score), max(lowest_score),
                  min(lowest_rank), max(lowest_rank)
           FROM admission_scores WHERE school_code=%s
           GROUP BY year, category, subject
           ORDER BY year DESC, category, subject""", (code,))
    majors = await db.fetch_all(
        """SELECT a.major_name, a.major_code,
                  count(DISTINCT a.year) AS years,
                  max(a.year) AS last_year, count(*) AS recs,
                  COALESCE((SELECT array_agg(DISTINCT x ORDER BY x)
                            FROM admission_scores b, unnest(b.flags) x
                            WHERE b.school_code = a.school_code
                              AND b.major_name = a.major_name
                              AND b.flags <> '{}'), '{}') AS flags
           FROM admission_scores a WHERE a.school_code=%s
           GROUP BY a.school_code, a.major_name, a.major_code
        ORDER BY years DESC, major_name ASC
        LIMIT 300""", (code,))

    # 新增键（任务 #8）：院校实力聚合；既有键结构不变
    strength = await get_school_strength(code)

    return {
        "code": basic[0], "name": basic[1],
        "profile": ({
            "province": prof[0], "city": prof[1], "affiliation": prof[2],
            "level": prof[3], "nature": prof[4], "type": prof[5],
            "is_985": prof[6], "is_211": prof[7], "is_dfc": prof[8],
            "established": prof[9], "strength": prof[10],
            "school_style": prof[11], "employment_region": prof[12],
            "rank_ref": prof[13], "note": prof[14],
            "website": prof[15], "intro": prof[16],
            "postgrad_rate": float(prof[17]) if prof[17] is not None else None,
        } if prof else None),
        "city": city,
        "yearly_summary": [
            {"year": r[0], "category": r[1], "subject": r[2], "records": r[3],
             "major_count": r[4], "lowest_score_range": [r[5], r[6]],
             "lowest_rank_range": [r[7], r[8]]}
            for r in yearly
        ],
        "majors": [
            {"major_name": r[0], "major_code": r[1], "years": r[2],
             "last_year": r[3], "records": r[4], "flags": list(r[5] or [])}
            for r in majors
        ],
        "strength": strength,
    }


async def get_school_major(code: str, major_name: str, major_code: str = None,
                           year=None, category=None):
    where = "WHERE a.school_code=%s AND a.major_name=%s"
    params = [code, major_name]
    if major_code:
        where += " AND a.major_code=%s"; params.append(major_code)
    if year:
        where += " AND a.year=%s"; params.append(year)
    if category:
        where += " AND a.category=%s"; params.append(category)
    rows = await db.fetch_all(
        f"""SELECT a.year, a.category, a.subject, a.batch, a.is_collection,
                   a.score_kind, a.lowest_score, a.lowest_rank, a.tiebreak_1,
                   sf.filename, sf.note, sf.status
            FROM admission_scores a
            LEFT JOIN source_files sf ON a.src_id = sf.id
            {where}
            ORDER BY a.year DESC, a.category, a.subject, a.batch, a.score_kind""",
        params,
    )
    return [
        {
            "year": r[0], "category": r[1], "subject": r[2], "batch": r[3],
            "is_collection": r[4], "score_kind": r[5],
            "lowest_score": float(r[6]) if r[6] is not None else None,
            "lowest_rank": r[7], "tiebreak_1": float(r[8]) if r[8] is not None else None,
            "source_file": r[9], "source_note": r[10], "source_status": r[11],
        }
        for r in rows
    ]
