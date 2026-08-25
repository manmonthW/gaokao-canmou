"""专业字典服务：基于 major_catalog（教育部本科专业目录）的标准专业浏览，
并关联 admission_scores 中"在辽招生"的实际数据（院校数、分数/位次区间）。

设计要点（从用户需求出发）：
- 用户脑中是"标准专业"（如 计算机科学与技术），分数库里是"招生专业名"
  （如 工科试验班(卓越计划)[计算机科学与...]），两者命名不一致。
- 因此关联时不要求精确相等，而用 major_name ILIKE '%标准名%' 做"包含"匹配，
  把分散在该标准专业下的招生记录聚合成一个视图，给出院校数 + 分数区间。
- 另外提供门类/专业类的导航（13 门类 → 专业类 → 专业），支持浏览式探索。

性能（0015）：
- ILIKE 双侧通配无法走索引，737 专业 × 6.7 万分数的实时聚合每次约 25s。
  分数数据一年只在年度投档入库时变一次，故聚合结果预计算进
  major_admission_summary（etl/load_major_summary.py 全量重建），
  读路径直连汇总表；旧库未跑 0015 时降级回原实时 ILIKE 查询，功能不回归。
"""
from app import db
from app.services.match import TREND_LABEL_DISPLAY
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

    try:
        # 快路径：直连 0015 预计算汇总表（年度投档入库后由 ETL 重建）
        rows = await db.fetch_all(
            f"""SELECT mc.code, mc.name, mc.category, mc.discipline,
                       COALESCE(s.school_count, 0),
                       s.min_score, s.max_score, s.min_rank, s.max_rank
                FROM major_catalog mc
                LEFT JOIN major_admission_summary s
                       ON s.code = mc.code AND s.name = mc.name
                {where}
                ORDER BY COALESCE(s.school_count, 0) DESC, mc.discipline, mc.category, mc.name
                LIMIT %s""",
            params,
        )
    except Exception as e:
        if not db.schema_missing(e):
            raise
        # 旧库降级（未跑 0015）：回退实时 ILIKE 全表聚合，慢但可用
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
    # 列表徽标用的趋势标签（0017）：一次批量取，避免逐行查询。
    # 只取本科批的持续趋势——列表是扫读场景，「平稳/样本不足」不渲染徽标
    # （house rule：数据为空不占位），把它们一并带下去只会增加前端判空负担。
    names = [r[1] for r in rows]
    trend_map: dict = {}
    if names:
        try:
            for mk, subject, lab in await db.fetch_all(
                """SELECT major_key, subject, label FROM major_trend
                    WHERE major_key = ANY(%s) AND batch = '本科批'
                      AND label IN ('持续降温','持续升温','趋势（内部分化）')""",
                (names,),
            ):
                trend_map.setdefault(mk, []).append(
                    {"subject": subject, "label": lab,
                     "label_display": TREND_LABEL_DISPLAY.get(lab, lab)})
        except Exception:
            trend_map = {}          # 旧库未跑 0017：静默降级，列表照常渲染
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
            # 新键追加在末尾（契约只增不改）
            "trend_labels": trend_map.get(r[1], []),
        }
        for r in rows
    ]


async def get_major_eval5(name: str):
    """返回该专业对应的第五轮学科评估 A 类结果。

    通过 major_eval_map 将本科专业名映射到学科评估学科名，
    再 JOIN school_disciplines（source='eval5_a', verify_status='verified'）
    取出 A+/A/A- 各等级院校清单。

    返回结构：
      {
        "discipline": str | None,   # 映射到的学科名（无则 None）
        "grades": {                  # 按等级分组的院校名列表（已排序）
          "A+": [...], "A": [...], "A-": [...]
        }
      }
    无对应评估数据时 discipline=None, grades={}
    """
    row = await db.fetch_one(
        """SELECT m.eval_discipline
           FROM major_eval_map m
           WHERE m.major_name=%s
           LIMIT 1""",
        (name,),
    )
    if not row:
        return {"discipline": None, "grades": {}}
    discipline = row[0]

    rows = await db.fetch_all(
        """SELECT sd.grade, sd.school_name
           FROM school_disciplines sd
           WHERE sd.discipline_name=%s
             AND sd.source='eval5_a'
             AND sd.verify_status='verified'
           ORDER BY sd.grade, sd.school_name""",
        (discipline,),
    )
    grades: dict[str, list[str]] = {}
    for grade, school in rows:
        grades.setdefault(grade, []).append(school)
    return {"discipline": discipline, "grades": grades}


async def get_major_trend(name: str):
    """返回该标准专业的冷热趋势（migration 0017），按学科类×批次分组。

    **不跨学科类合并**：docs/major-trend-2024-2026.md §3.4 已证明法学、会计学、
    金融学在物理类与历史类结论相反，合并会得出错误结论。

    每组附「在辽招生单元数」——这一条比标签本身更重要：人工智能门槛平稳但单元
    +67%（强需求吃下扩招），土木工程门槛平稳但单元 −28%（靠缩招撑住），
    只看标签会把两者都读成「没变化」。旧库（未跑 0017）返回空列表。
    """
    try:
        rows = await db.fetch_all(
            """SELECT t.subject, t.batch, t.label, t.label_reason,
                      t.n_pairs_2, t.concord_2, t.excess_total,
                      t.units_2024, t.units_2025, t.units_2026, t.tier_split,
                      t.eq_score_delta, t.eq_score_delta_market,
                      c.note, c.source_name, c.source_url, c.published_on
                 FROM major_trend t
                 LEFT JOIN major_trend_context c
                   ON c.major_key = t.major_key AND c.subject IN (t.subject, '')
                WHERE t.major_key = %s
                ORDER BY t.batch DESC, t.subject""",
            (name,),
        )
    except Exception:
        return []
    out = []
    for (subject, batch, lab, reason, n2, conc, ex,
         n24, n25, n26, tiers, eqd, eqm,
         ctx_note, ctx_src, ctx_url, ctx_on) in rows:
        out.append({
            "subject": subject,
            "batch": batch,
            "label": lab,
            "label_display": TREND_LABEL_DISPLAY.get(lab, lab),
            "label_reason": reason,
            "n_schools": n2,
            "concord": float(conc) if conc is not None else None,
            "excess_total": float(ex) if ex is not None else None,
            "units": {"2024": n24, "2025": n25, "2026": n26},
            "tier_split": tiers,
            "eq_score_delta": float(eqd) if eqd is not None else None,
            "eq_score_delta_market": float(eqm) if eqm is not None else None,
            "context": ({"note": ctx_note, "source_name": ctx_src,
                         "source_url": ctx_url,
                         "published_on": ctx_on.isoformat() if ctx_on else None}
                        if ctx_note else None),
        })
    return out


async def get_major_detail(name: str):
    """返回标准专业详情：基本信息 + 热门专业图文（若 OCR 资料存在）。

    返回字段：
     code, name, category, discipline,
     hot_profile: { degree, length, gender_ratio, introduction, subject_req,
                    career, training_goal, discipline_req, main_courses,
                    postgrad_dir, employment_dir, hot_schools, image_path,
                    has_image } | None
     eval5: { discipline, grades } 第五轮学科评估 A 类结果
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

    # 第五轮学科评估 A 类结果（经 major_eval_map 关联到该专业）
    eval5 = await get_major_eval5(name)
    # 冷热趋势（0017）：新键追加在末尾，契约只增不改
    trend = await get_major_trend(name)

    return {
        "code": row[0],
        "name": row[1],
        "category": row[2],
        "discipline": row[3],
        "hot_profile": hot,
        "eval5": eval5,
        "trend": trend,
    }
