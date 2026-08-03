from fastapi import APIRouter, Query
from typing import Optional
from app.services import locate as svc

router = APIRouter(prefix="/locate", tags=["locate"])


@router.get("/score-to-rank")
async def score_to_rank(
    year: int = Query(...),
    category: str = Query(...),
    subject: str = Query(...),
    score: int = Query(...),
):
    """分数转位次：返回位次/位次区间、同分人数、来源。"""
    return await svc.score_to_rank(year, category, subject, score)


@router.get("/rank-to-score")
async def rank_to_score(
    year: int = Query(...),
    category: str = Query(...),
    subject: str = Query(...),
    rank: int = Query(...),
):
    """位次转分数。"""
    return await svc.rank_to_score(year, category, subject, rank)


@router.get("/control-line")
async def control_line(
    year: int = Query(...),
    category: str = Query(...),
    subject: str = Query(...),
    score: int = Query(...),
    batch: Optional[str] = Query(None),
    line_type: Optional[str] = Query(None),
):
    """省控线判断：控制线、分差、是否过线、说明。"""
    return await svc.judge_line(year, category, subject, score,
                                batch=batch, line_type=line_type)


@router.get("/summary")
async def summary(
    year: int = Query(...),
    category: str = Query(...),
    subject: str = Query(...),
    score: Optional[int] = Query(None),
    rank: Optional[int] = Query(None),
    batch: Optional[str] = Query(None),
):
    """个人定位摘要：百分位、过线情况、跨年同位次分数。"""
    return await svc.personal_summary(year, category, subject,
                                      score=score, rank=rank, batch=batch)


@router.get("/rank-context")
async def rank_context(
    category: str = Query(...),
    subject: str = Query(...),
    rank: int = Query(..., description="考生全省位次（主锚点）"),
    batch: Optional[str] = Query(None),
):
    """面向未来考生的位次锚点定位：位次的历史分数等价 + 位次法过线参考。

    不需要 year：考生所在年份隐含固定，2025/2026 始终作为历史参考年一起使用。
    """
    return await svc.rank_context(category, subject, rank, batch=batch)
