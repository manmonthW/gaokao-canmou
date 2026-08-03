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
