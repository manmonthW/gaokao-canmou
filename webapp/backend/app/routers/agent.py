"""Authenticated, allowlisted asynchronous Agent job API."""
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from app.agent import config, jobs
from app.services.auth import current_user

router = APIRouter(prefix="/agent", tags=["agent"])


class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


class CreateJobRequest(BaseModel):
    mode: Literal["问答", "解读"] = "问答"
    message: str = Field(min_length=1, max_length=500)
    profile: dict[str, Any] = Field(default_factory=dict)
    page_context: dict[str, Any] = Field(default_factory=dict)
    history: list[HistoryTurn] = Field(default_factory=list, max_length=6)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("问题不能为空")
        return value


class FeedbackRequest(BaseModel):
    helpful: bool
    reason: str | None = Field(default=None, max_length=500)


def _authorized(user=Depends(current_user)):
    if not config.AGENT_ENABLED:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "参谋助手暂未开放")
    if not jobs.is_allowed(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "参谋助手目前仅对邀请用户开放")
    return user


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_job(req: CreateJobRequest, user=Depends(_authorized)):
    payload = req.model_dump()
    decision, active = await jobs.admission(user["id"], payload)
    if decision == "active":
        return {"job_id": active["id"], "status": active["status"], "reused": True}
    if decision == "rate_limit":
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "每小时任务数已达上限")
    if decision == "budget":
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "今日参谋额度已用完，请明天再试")
    if decision == "conflict":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "active_job", "job_id": active["id"], "message": "上一条问题仍在分析，请先取消或等待完成"},
        )
    job = await jobs.create(user["id"], payload)
    return {"job_id": job["id"], "status": job["status"], "reused": False}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, after: int = Query(default=0, ge=0), user=Depends(_authorized)):
    job = await jobs.get(job_id, user["id"], after)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    return job


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, user=Depends(_authorized)):
    state = await jobs.cancel(job_id, user["id"])
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    return {"job_id": job_id, "status": state}


@router.post("/jobs/{job_id}/feedback")
async def give_feedback(job_id: str, req: FeedbackRequest, user=Depends(_authorized)):
    if not await jobs.feedback(job_id, user["id"], req.helpful, req.reason):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    return {"ok": True}
