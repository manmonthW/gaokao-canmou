"""数据状态服务：当前发布版本 + 待发布批次 + 数据覆盖。"""
from app import db


async def get_data_status():
    rel = await db.fetch_one(
        """SELECT version, data_as_of, covered_years, covered_categories,
                  covered_batches, status, publisher, published_at, quality_summary
           FROM data_releases
           WHERE status = 'published'
           ORDER BY published_at DESC
           LIMIT 1"""
    )
    pend = await db.fetch_all(
        """SELECT year, category, subject, batch, stage, status, note
           FROM admission_publication_status
           WHERE status IN ('待发布', '部分发布')
           ORDER BY year, category, subject, batch, stage"""
    )
    cov = await db.fetch_all(
        """SELECT year, category, count(*)
           FROM admission_scores
           GROUP BY year, category
           ORDER BY year, category"""
    )

    release = None
    if rel:
        release = {
            "version": rel[0],
            "data_as_of": str(rel[1]),
            "covered_years": rel[2] or [],
            "covered_categories": rel[3] or [],
            "covered_batches": rel[4] or [],
            "status": rel[5],
            "publisher": rel[6],
            "published_at": str(rel[7]) if rel[7] else None,
            "quality_summary": rel[8],
        }

    pending = [
        {
            "year": r[0], "category": r[1], "subject": r[2], "batch": r[3],
            "stage": r[4], "status": r[5], "note": r[6],
        }
        for r in pend
    ]
    coverage = [{"year": r[0], "category": r[1], "count": r[2]} for r in cov]

    return {"release": release, "pending_batches": pending, "coverage": coverage}


async def get_matrix():
    """发布状态矩阵（D4）：每个 (年份×类别×学科类×批次×阶段) 的
    官方发布状态 × 库内记录数，一眼看出「官方已发布但库内没有」的缺口。"""
    rows = await db.fetch_all(
        """SELECT p.year, p.category, p.subject, p.batch, p.stage, p.status,
                  p.note, p.official_published_at, COALESCE(a.cnt, 0) AS records
           FROM admission_publication_status p
           LEFT JOIN (
             SELECT year, category, subject, batch, count(*) AS cnt
             FROM admission_scores GROUP BY 1,2,3,4
           ) a ON a.year = p.year AND a.category = p.category
              AND a.subject = p.subject AND a.batch = p.batch
           ORDER BY p.year, p.category, p.subject, p.batch, p.stage""")
    matrix = [
        {
            "year": r[0], "category": r[1], "subject": r[2], "batch": r[3],
            "stage": r[4], "status": r[5], "note": r[6],
            "official_published_at": str(r[7]) if r[7] else None,
            "records": r[8],
            "gap": r[5] in ("部分发布", "已完成") and r[8] == 0,
        }
        for r in rows
    ]
    # 库内有数据但未登记发布状态的批次（登记遗漏）
    extra = await db.fetch_all(
        """SELECT a.year, a.category, a.subject, a.batch, count(*)
           FROM admission_scores a
           LEFT JOIN admission_publication_status p
             ON p.year = a.year AND p.category = a.category
            AND p.subject = a.subject AND p.batch = a.batch
           WHERE p.id IS NULL
           GROUP BY 1,2,3,4 ORDER BY 1,2,3,4""")
    unregistered = [
        {"year": r[0], "category": r[1], "subject": r[2], "batch": r[3],
         "records": r[4]}
        for r in extra
    ]
    return {"matrix": matrix, "unregistered": unregistered}
