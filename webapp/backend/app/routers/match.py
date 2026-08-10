from fastapi import APIRouter, Query
from typing import List, Optional
from pydantic import BaseModel
from app.services import match as svc

router = APIRouter(prefix="/match", tags=["match"])


class RefreshItem(BaseModel):
    school_code: str
    major_code: Optional[str] = None
    major_name: Optional[str] = None
    batch: str


class RefreshRequest(BaseModel):
    year: int
    category: str
    subject: str
    batch: str
    rank: Optional[int] = None
    score: Optional[int] = None
    rank_lo: Optional[int] = None
    rank_hi: Optional[int] = None
    items: List[RefreshItem]


@router.get("")
async def match(
    year: int = Query(...),
    category: str = Query(...),
    subject: str = Query(...),
    batch: str = Query(...),
    rank: Optional[int] = Query(None),
    score: Optional[int] = Query(None),
    rank_lo: Optional[int] = Query(None, description="P1 备考期：估计位次下界（更好），与 rank_hi 同给启用区间模式"),
    rank_hi: Optional[int] = Query(None, description="P1 备考期：估计位次上界（更差）"),
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
    pref_sort: Optional[str] = Query(
        None, description="P5 同档内排序偏好：certainty 确定性优先（默认）/ level 院校层次优先 / city 城市分级优先"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
):
    """普通类智能匹配：输入分数+位次 → 定位 + 冲稳保候选，每项可解释。"""
    return await svc.match(
        year=year, category=category, subject=subject, batch=batch,
        rank=rank, score=score, rank_lo=rank_lo, rank_hi=rank_hi,
        province=province, city=city, level=level,
        nature=nature, type_=type, major_keyword=major_keyword,
        has_both_years=has_both_years, risk=risk,
        exclude_flags=[s.strip() for s in exclude_flags.split(",") if s.strip()]
        if exclude_flags else None,
        electives=[s.strip() for s in electives.split(",") if s.strip()]
        if electives else None,
        pref_sort=pref_sort,
        page=page, page_size=page_size,
    )


@router.post("/refresh")
async def refresh(req: RefreshRequest):
    """工作台「刷新到最新数据」：年度接入后旧方案快照缺新年数据，
    按方案条目逐单元用最新全量数据重算 yearly/位次/分档。"""
    return await svc.refresh_snapshots(
        year=req.year, category=req.category, subject=req.subject, batch=req.batch,
        rank=req.rank, score=req.score, rank_lo=req.rank_lo, rank_hi=req.rank_hi,
        items=[i.model_dump() for i in req.items],
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
