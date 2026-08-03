from fastapi import APIRouter
from app.schemas import MetaResponse
from app.services import meta as svc

router = APIRouter(tags=["meta"])


@router.get("/meta", response_model=MetaResponse)
async def meta():
    """下拉筛选枚举。"""
    return await svc.get_meta()
