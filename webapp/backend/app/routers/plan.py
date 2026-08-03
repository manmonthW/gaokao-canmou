"""志愿方案导出路由（Phase 3）。

POST /api/v1/plan/export  → 返回 xlsx 文件。
方案数据由前端（localStorage 匿名存储）传入，服务端无状态、不落库。
"""
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services.plan_export import build_plan_xlsx

router = APIRouter(prefix="/plan", tags=["plan"])


class PlanExaminee(BaseModel):
    year: int
    category: str
    subject: str
    batch: str
    score: Optional[float] = None
    rank: Optional[int] = None


class PlanItem(BaseModel):
    risk: Optional[str] = None
    school_code: Optional[str] = None
    school_name: Optional[str] = None
    major_code: Optional[str] = None
    major_name: Optional[str] = None
    last_year: Optional[int] = None
    last_year_score: Optional[float] = None
    last_year_rank: Optional[int] = None
    rank_diff_last: Optional[int] = None
    level: Optional[str] = None
    city: Optional[str] = None
    note: Optional[str] = None


class PlanExportRequest(BaseModel):
    plan_name: str = Field(default="志愿方案", max_length=60)
    note: Optional[str] = None
    data_version: Optional[str] = None
    created_at: Optional[str] = None
    examinee: PlanExaminee
    items: list[PlanItem] = Field(default_factory=list, max_length=200)


@router.post("/export")
async def export_plan(req: PlanExportRequest):
    data = build_plan_xlsx(req.model_dump())
    filename = f"{req.plan_name}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition":
                f"attachment; filename*=UTF-8''{quote(filename)}",
        },
    )
