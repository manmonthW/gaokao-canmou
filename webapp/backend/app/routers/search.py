from fastapi import APIRouter, Query
from typing import Optional
from app.services import search as svc

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/schools")
async def schools(q: str = Query(..., min_length=1),
                 limit: int = Query(20, ge=1, le=500)):
    """搜索院校：支持名称与代码。"""
    return await svc.search_schools(q, limit=limit)


@router.get("/majors")
async def majors(q: str = Query(..., min_length=1),
                 year: Optional[int] = Query(None),
                 category: Optional[str] = Query(None),
                 subject: Optional[str] = Query(None),
                 limit: int = Query(20, ge=1, le=500)):
    """搜索专业：支持原始专业名称，按招生院校数排序。"""
    return await svc.search_majors(q, year=year, category=category,
                                   subject=subject, limit=limit)
