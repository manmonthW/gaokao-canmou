from fastapi import APIRouter, Query
from typing import Optional
from app.services import datacenter as svc

router = APIRouter(prefix="/datacenter", tags=["datacenter"])


@router.get("/control-lines")
async def control_lines(year: Optional[int] = Query(None),
                        category: Optional[str] = Query(None),
                        subject: Optional[str] = Query(None)):
    """历年省控线。"""
    return await svc.control_lines(year=year, category=category, subject=subject)


@router.get("/score-rank")
async def score_rank(year: int = Query(...),
                     category: str = Query(...),
                     subject: str = Query(...),
                     page: int = Query(1, ge=1),
                     page_size: int = Query(50, ge=1, le=500)):
    """一分一段表（分页）。"""
    return await svc.score_rank_table(year, category, subject, page=page,
                                      page_size=page_size)


@router.get("/records")
async def records(year: Optional[int] = Query(None),
                  category: Optional[str] = Query(None),
                  subject: Optional[str] = Query(None),
                  batch: Optional[str] = Query(None),
                  is_collection: Optional[bool] = Query(None),
                  school: Optional[str] = Query(None),
                  major: Optional[str] = Query(None),
                  page: int = Query(1, ge=1),
                  page_size: int = Query(50, ge=1, le=500)):
    """原始录取记录（分页、可筛选）。"""
    return await svc.admission_records(year=year, category=category,
                                       subject=subject, batch=batch,
                                       is_collection=is_collection,
                                       school=school, major=major,
                                       page=page, page_size=page_size)


@router.get("/source-files")
async def source_files():
    """源文件溯源列表。"""
    return await svc.source_files()


@router.get("/publication-status")
async def publication_status():
    """批次发布状态（区分无数据 vs 待发布）。"""
    return await svc.publication_status()
