from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from app.services import schools as svc

router = APIRouter(prefix="/schools", tags=["schools"])


@router.get("/{code}")
async def school_detail(code: str):
    """院校详情：画像、城市、历年招生摘要、专业列表。"""
    detail = await svc.get_school(code)
    if not detail:
        raise HTTPException(status_code=404, detail=f"院校不存在：{code}")
    return detail


@router.get("/{code}/strength")
async def school_strength(code: str):
    """院校学科实力（任务 #8）：学科评估/一流学科、一流专业与第三方评级、
    院校级实力标签；未收录时各列表为空。"""
    data = await svc.get_school_strength(code)
    if not data:
        raise HTTPException(status_code=404, detail=f"院校不存在：{code}")
    return {"code": code, **data}


@router.get("/{code}/major")
async def school_major_detail(
    code: str,
    major_name: str = Query(...),
    major_code: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
):
    """院校专业详情：历年最低分、最低位次、批次、征集、数据来源。"""
    rows = await svc.get_school_major(code, major_name, major_code=major_code,
                                      year=year, category=category)
    return {"code": code, "major_name": major_name,
            "major_code": major_code, "records": rows}
