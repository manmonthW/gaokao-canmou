"""专业字典路由：标准专业浏览 + 在辽招生关联 + 热门专业图文详情。"""
import os
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from typing import Optional
from app.services import major_catalog as svc

HOT_ROOT = "/home/ekewang/projects/gaokao/ln/2026allmaterial/热门专业盘点/clean"

router = APIRouter(prefix="/major-catalog", tags=["major-catalog"])


@router.get("/disciplines")
async def disciplines():
    """学科门类导航（13 门类 + 专业数）。"""
    return await svc.list_disciplines()


@router.get("/categories")
async def categories(discipline: Optional[str] = Query(None)):
    """专业类导航，可按门类过滤。"""
    return await svc.list_categories(discipline=discipline)


@router.get("/search")
async def search(
    q: Optional[str] = Query(None, description="专业名称关键词"),
    discipline: Optional[str] = Query(None, description="学科门类"),
    category: Optional[str] = Query(None, description="专业类"),
    limit: int = Query(100, ge=1, le=500),
):
    """标准专业检索，并附在辽招生概览（院校数 + 分数/位次区间）。"""
    return await svc.search_catalog(
        q=q, discipline=discipline, category=category, limit=limit
    )


@router.get("/detail")
async def detail(name: str = Query(..., description="标准专业名称")):
    """专业详情：基础信息 + 热门专业图文（OCR 资料，若有）。"""
    return await svc.get_major_detail(name)


@router.get("/hot-image")
async def hot_image(name: str = Query(..., description="专业名称")):
    """返回热门专业盘点 PNG 原图（用于图文卡片）。"""
    # 精确匹配：遍历目录找含该专业名的文件
    target = None
    for f in os.listdir(HOT_ROOT):
        if f.endswith(".png") and name in f:
            target = os.path.join(HOT_ROOT, f)
            break
    if not target or not os.path.exists(target):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="图片未找到")
    return FileResponse(target)
