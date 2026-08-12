"""元数据服务：下拉枚举（年份/科类/选科/批次/层次/性质/类型/省份）。"""
import psycopg2

from app import db


async def get_meta():
    years = await db.fetch_all(
        "SELECT DISTINCT year FROM admission_scores ORDER BY year")
    categories = await db.fetch_all(
        "SELECT DISTINCT category FROM admission_scores ORDER BY category")
    subjects = await db.fetch_all(
        "SELECT DISTINCT subject FROM admission_scores "
        "WHERE subject IS NOT NULL ORDER BY subject")
    batches = await db.fetch_all(
        "SELECT DISTINCT batch FROM admission_scores "
        "WHERE batch IS NOT NULL ORDER BY batch")
    # 科类→批次映射：供前端「原始记录」筛选时按已选科类联动批次下拉，
    # 避免把「专科批」等跨科类共享的批次值在未选科类时平铺，误导用户
    # （如普通类考生看到艺术/体育专属批次）。数据驱动，无硬编码。
    batch_by_cat_rows = await db.fetch_all(
        "SELECT DISTINCT category, batch FROM admission_scores "
        "WHERE batch IS NOT NULL AND category IS NOT NULL "
        "ORDER BY category, batch")
    score_kinds = await db.fetch_all(
        "SELECT DISTINCT score_kind FROM admission_scores "
        "WHERE score_kind IS NOT NULL ORDER BY score_kind")
    provinces = await db.fetch_all(
        "SELECT DISTINCT province FROM school_profiles "
        "WHERE province IS NOT NULL ORDER BY province")
    levels = await db.fetch_all(
        "SELECT DISTINCT level FROM school_profiles "
        "WHERE level IS NOT NULL ORDER BY level")
    natures = await db.fetch_all(
        "SELECT DISTINCT nature FROM school_profiles "
        "WHERE nature IS NOT NULL ORDER BY nature")
    types = await db.fetch_all(
        "SELECT DISTINCT type FROM school_profiles "
        "WHERE type IS NOT NULL ORDER BY type")
    # 专业级报考标记词表（D2a，migration 0011）：前端筛选与文案统一来源
    major_flag_rows = await db.fetch_all(
        "SELECT flag, label, severity, note FROM flag_dictionary ORDER BY flag")
    # 院校/专业实力标签词表（任务 #8，migration 0014）：
    # strength_tags 展示文案与第三方免责口径的唯一权威来源。
    # 旧库（未跑 0014）降级为空词表：新功能隐身、既有 meta 字段不回归。
    try:
        strength_tag_rows = await db.fetch_all(
            """SELECT tag, label, kind, third_party, source_note, display_order
               FROM strength_dictionary ORDER BY display_order, tag""")
    except psycopg2.Error as e:
        if not db.schema_missing(e):
            raise
        strength_tag_rows = []

    # 组装科类→批次映射
    batches_by_category: dict[str, list[str]] = {}
    for cat, bat in batch_by_cat_rows:
        batches_by_category.setdefault(cat, []).append(bat)

    # 年份语义字段（年度接入免改前端）：
    # last_year=最新数据年，examinee_year=考生年（最新数据年+1）。
    year_vals = [r[0] for r in years]

    return {
        "years": year_vals,
        "examinee_year": (year_vals[-1] + 1) if year_vals else None,
        "last_year": year_vals[-1] if year_vals else None,
        "history_years": year_vals,
        "categories": [r[0] for r in categories],
        "subjects": [r[0] for r in subjects],
        "batches": [r[0] for r in batches],
        "batches_by_category": batches_by_category,
        "score_kinds": [r[0] for r in score_kinds],
        "provinces": [r[0] for r in provinces],
        "levels": [r[0] for r in levels],
        "natures": [r[0] for r in natures],
        "types": [r[0] for r in types],
        "flags": ["985", "211", "双一流"],
        "major_flags": [
            {"flag": r[0], "label": r[1], "severity": r[2], "note": r[3]}
            for r in major_flag_rows
        ],
        "strength_dictionary": [
            {"tag": r[0], "label": r[1], "kind": r[2], "third_party": r[3],
             "source_note": r[4], "display_order": r[5]}
            for r in strength_tag_rows
        ],
    }
