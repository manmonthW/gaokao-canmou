from fastapi import APIRouter
from app.schemas import DataStatusResponse
from app.services import data_status as svc

router = APIRouter(tags=["data-status"])


@router.get("/data-status", response_model=DataStatusResponse)
async def data_status():
    """当前数据版本、待发布批次、数据覆盖统计。"""
    return await svc.get_data_status()
