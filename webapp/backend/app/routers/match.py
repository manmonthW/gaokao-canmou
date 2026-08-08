from fastapi import APIRouter, Query
from typing import Optional
from app.services import match as svc

router = APIRouter(prefix="/match", tags=["match"])


@router.get("")
async def match(
    year: int = Query(...),
    category: str = Query(...),
    subject: str = Query(...),
    batch: str = Query(...),
    rank: Optional[int] = Query(None),
    score: Optional[int] = Query(None),
    province: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    nature: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    major_keyword: Optional[str] = Query(None),
    has_both_years: Optional[bool] = Query(None),
    risk: Optional[str] = Query(None, description="仅返回某一风险档：保/稳/冲/高波动/数据不足"),
    exclude_flags: Optional[str] = Query(
        None, description="排除含指定报考标记的单元，逗号分隔，如 中外合作,定向"),
    electives: Optional[str] = Query(
        None, description="再选科目，逗号分隔，如 化学,生物；仅当该年选科要求已入库时生效"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
):
    """普通类智能匹配：输入分数+位次 → 定位 + 冲稳保候选，每项可解释。"""
    return await svc.match(
        year=year, category=category, subject=subject, batch=batch,
        rank=rank, score=score, province=province, city=city, level=level,
        nature=nature, type_=type, major_keyword=major_keyword,
        has_both_years=has_both_years, risk=risk,
        exclude_flags=[s.strip() for s in exclude_flags.split(",") if s.strip()]
        if exclude_flags else None,
        electives=[s.strip() for s in electives.split(",") if s.strip()]
        if electives else None,
        page=page, page_size=page_size,
    )


@router.get("/sensitivity")
async def sensitivity(
    year: int = Query(...),
    category: str = Query(...),
    subject: str = Query(...),
    batch: str = Query(...),
    rank: Optional[int] = Query(None),
    score: Optional[int] = Query(None),
    province: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    nature: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    major_keyword: Optional[str] = Query(None),
    has_both_years: Optional[bool] = Query(None),
    exclude_flags: Optional[str] = Query(
        None, description="排除含指定报考标记的单元，逗号分隔，如 中外合作,定向"),
    electives: Optional[str] = Query(
        None, description="再选科目，逗号分隔；仅当该年选科要求已入库时生效"),
):
    """A3 敏感度一键试算：位次 ±5%/±10% 时同一候选集的分档变化。"""
    return await svc.sensitivity(
        year=year, category=category, subject=subject, batch=batch,
        rank=rank, score=score, province=province, city=city, level=level,
        nature=nature, type_=type, major_keyword=major_keyword,
        has_both_years=has_both_years,
        exclude_flags=[s.strip() for s in exclude_flags.split(",") if s.strip()]
        if exclude_flags else None,
        electives=[s.strip() for s in electives.split(",") if s.strip()]
        if electives else None,
    )
