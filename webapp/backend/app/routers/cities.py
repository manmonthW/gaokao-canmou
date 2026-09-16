from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from app.services import cities as svc

router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("/provinces")
async def list_provinces():
    """省份下拉选项，只返回 cities 表中的省级名称。"""
    return await svc.list_provinces()


@router.get("")
async def list_cities(
    province: Optional[str] = Query(None, description="省份"),
    q: Optional[str] = Query(None, description="城市名称关键词"),
):
    """城市列表：可按省份与关键词过滤，附院校数。"""
    return await svc.list_cities(province=province, q=q)


@router.get("/{city}")
async def city_detail(city: str):
    """城市详情：城市画像 + 该城院校清单。"""
    data = await svc.get_city(city)
    if not data:
        raise HTTPException(status_code=404, detail="城市未找到")
    return data
