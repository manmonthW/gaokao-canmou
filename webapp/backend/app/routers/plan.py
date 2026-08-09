"""志愿方案导出路由（Phase 3）。

POST /api/v1/plan/export  → 返回 xlsx 文件。
方案数据由前端（localStorage 匿名存储）传入，服务端无状态、不落库。
"""
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from app.services.plan_export import build_plan_xlsx

router = APIRouter(prefix="/plan", tags=["plan"])


def _empty_to_none(v):
    """前端 localStorage 快照可能带空字符串（v-model.number 清空残留），
    数值字段遇空白一律视为 null，避免 float/int 解析 422。"""
    if isinstance(v, str) and not v.strip():
        return None
    return v


class PlanExaminee(BaseModel):
    year: int
    category: str
    subject: str
    batch: str
    score: Optional[float] = None
    rank: Optional[int] = None

    _clean_nums = field_validator("score", "rank", mode="before")(_empty_to_none)


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

    _clean_nums = field_validator(
        "last_year", "last_year_score", "last_year_rank", "rank_diff_last",
        mode="before")(_empty_to_none)


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
