"""专业字典服务：基于 major_catalog（教育部本科专业目录）的标准专业浏览，
并关联 admission_scores 中"在辽招生"的实际数据（院校数、分数/位次区间）。

设计要点（从用户需求出发）：
- 用户脑中是"标准专业"（如 计算机科学与技术），分数库里是"招生专业名"
  （如 工科试验班(卓越计划)[计算机科学与...]），两者命名不一致。
- 因此关联时不要求精确相等，而用 major_name ILIKE '%标准名%' 做"包含"匹配，
  把分散在该标准专业下的招生记录聚合成一个视图，给出院校数 + 分数区间。
- 另外提供门类/专业类的导航（13 门类 → 专业类 → 专业），支持浏览式探索。
"""
from app import db
from app.config import MAX_PAGE_SIZE


async def list_disciplines():
    """返回 13 个学科门类及其专业数，用于左侧导航。"""
    rows = await db.fetch_all(
        """SELECT discipline, count(*) AS cnt
           FROM major_catalog
           GROUP BY discipline
           ORDER BY cnt DESC, discipline ASC"""
    )
    return [{"discipline": r[0], "count": r[1]} for r in rows]


async def list_categories(discipline: str = None):
    """返回专业类（含所属门类、专业数）。可按门类过滤。"""
    sql = """SELECT category, discipline, count(*) AS cnt
             FROM major_catalog"""
    params = []
    if discipline:
        sql += " WHERE discipline=%s"
        params.append(discipline)
    sql += " GROUP BY category, discipline ORDER BY discipline, category"
    rows = await db.fetch_all(sql, params)
    return [
        {"category": r[0], "discipline": r[1], "count": r[2]} for r in rows
    ]


async def search_catalog(
    q: str = None,
    discipline: str = None,
    category: str = None,
    limit: int = 100,
):
    """按关键词/门类/专业类筛选标准专业，并附在辽招生概览。

    返回字段：
      code, name, category, discipline,
      school_count   —— 在辽招该专业的院校数（模糊关联）
      lowest_score_range / lowest_rank_range —— 分数/位次区间
      has_admission  —— 分数库是否命中（命中才有真实数据）
    """
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    where = "WHERE 1=1"
    params = []
    if q:
        where += " AND mc.name ILIKE %s"
        params.append(f"%{q}%")
    if discipline:
        where += " AND mc.discipline=%s"
        params.append(discipline)
    if category:
        where += " AND mc.category=%s"
        params.append(category)
    params.append(limit)

    rows = await db.fetch_all(
        f"""SELECT mc.code, mc.name, mc.category, mc.discipline,
                   count(DISTINCT a.school_code) FILTER (WHERE a.school_code IS NOT NULL) AS school_cnt,
                   min(a.lowest_score) FILTER (WHERE a.school_code IS NOT NULL),
                   max(a.lowest_score) FILTER (WHERE a.school_code IS NOT NULL),
                   min(a.lowest_rank) FILTER (WHERE a.school_code IS NOT NULL),
                   max(a.lowest_rank) FILTER (WHERE a.school_code IS NOT NULL)
            FROM major_catalog mc
            LEFT JOIN admission_scores a
                   ON a.major_name ILIKE '%%' || mc.name || '%%'
            {where}
            GROUP BY mc.code, mc.name, mc.category, mc.discipline
            ORDER BY school_cnt DESC NULLS LAST, mc.discipline, mc.category, mc.name
            LIMIT %s""",
        params,
    )
    return [
        {
            "code": r[0],
            "name": r[1],
            "category": r[2],
            "discipline": r[3],
            "school_count": r[4] or 0,
            "lowest_score_range": [r[5], r[6]],
            "lowest_rank_range": [r[7], r[8]],
            "has_admission": (r[4] or 0) > 0,
        }
        for r in rows
    ]


async def get_major_detail(name: str):
    """返回标准专业详情：基本信息 + 热门专业图文（若 OCR 资料存在）。

    返回字段：
      code, name, category, discipline,
      hot_profile: { degree, length, gender_ratio, introduction, subject_req,
                     career, training_goal, discipline_req, main_courses,
                     postgrad_dir, employment_dir, hot_schools, image_path,
                     has_image } | None
    """
    row = await db.fetch_one(
        """SELECT mc.code, mc.name, mc.category, mc.discipline,
                  h.degree, h.length, h.gender_ratio, h.introduction,
                  h.subject_req, h.career, h.training_goal, h.discipline_req,
                  h.main_courses, h.postgrad_dir, h.employment_dir,
                  h.hot_schools, h.image_path,
                  h.training_req, h.knowledge_ability, h.social_celebrities,
                  h.arts_science_ratio, h.level_raw
           FROM major_catalog mc
           LEFT JOIN major_hot_profiles h ON h.name = mc.name
           WHERE mc.name=%s""",
        (name,),
    )
    if not row:
        return None

    hot = None
    if row[8] or row[16] or row[17] or row[18] or row[19]:  # 任一资料字段存在即有资料
        hot = {
            "degree": row[4],
            "length": row[5],
            "gender_ratio": row[6],
            "introduction": row[7],
            "subject_req": row[8],
            "career": row[9],
            "training_goal": row[10],
            "discipline_req": row[11],
            "main_courses": row[12],
            "postgrad_dir": row[13],
            "employment_dir": row[14],
            "hot_schools": row[15] or [],
            "image_path": row[16],
            "has_image": bool(row[16]),
            "training_req": row[17],
            "knowledge_ability": row[18],
            "social_celebrities": row[19],
            "arts_science_ratio": row[20],
            "level_raw": row[21],
        }

    return {
        "code": row[0],
        "name": row[1],
        "category": row[2],
        "discipline": row[3],
        "hot_profile": hot,
    }
