"""录取结果自愿回填（P4 反馈闭环）。

设计说明（docs/first-principles-review.md §5.3 建议 P4）：
  - 录取结束后邀请用户（自愿、匿名化）回填「实际被第几志愿录取」；
  - 这是系统的第一个真实标签集，直接支撑分档阈值校准与
    「概率化展示是否可行」的判断；
  - 匿名优先（P3）：不登录也可提交；登录则关联账号便于自己查看/撤回；
  - 数据存 SQLite 用户库（app/user_db.py），不碰只读 PG 分析库。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app import user_db
from app.services.auth import optional_user

router = APIRouter(tags=["feedback"])

_OUTCOMES = {"admitted", "slipped", "unknown"}
_RISKS = {"冲", "稳", "保", "高波动", "数据不足"}


class FeedbackReq(BaseModel):
    examinee_year: int = Field(ge=2020, le=2100)
    category: str | None = Field(default=None, max_length=32)
    subject: str | None = Field(default=None, max_length=32)
    batch: str | None = Field(default=None, max_length=64)
    examinee_rank: int | None = Field(default=None, ge=1)
    plan_total: int | None = Field(default=None, ge=1, le=112)
    outcome: str  # admitted / slipped / unknown
    admitted_order: int | None = Field(default=None, ge=1, le=112)
    admitted_risk: str | None = None
    admitted_school: str | None = Field(default=None, max_length=128)
    admitted_major: str | None = Field(default=None, max_length=128)
    note: str | None = Field(default=None, max_length=500)


@router.post("/feedback")
async def submit_feedback(req: FeedbackReq, user=Depends(optional_user)):
    """提交一条录取结果回填（匿名可用）。"""
    if req.outcome not in _OUTCOMES:
        return {"error": "outcome 必须是 admitted / slipped / unknown 之一。"}
    if req.outcome == "admitted" and req.admitted_order is None:
        return {"error": "「已被录取」需要填写实际被第几志愿录取。"}
    if (req.plan_total and req.admitted_order
            and req.admitted_order > req.plan_total):
        return {"error": "录取志愿序号不能大于方案志愿总数。"}
    if req.admitted_risk is not None and req.admitted_risk not in _RISKS:
        return {"error": "录取志愿的档位无效。"}
    row = {
        "user_id": user["id"] if user else None,
        "examinee_year": req.examinee_year,
        "category": req.category,
        "subject": req.subject,
        "batch": req.batch,
        "examinee_rank": req.examinee_rank,
        "plan_total": req.plan_total,
        "outcome": req.outcome,
        "admitted_order": req.admitted_order,
        "admitted_risk": req.admitted_risk,
        "admitted_school": req.admitted_school,
        "admitted_major": req.admitted_major,
        "note": req.note,
    }
    fid = await user_db.add_feedback(row)
    return {"ok": True, "id": fid}


@router.get("/feedback/summary")
async def feedback_summary():
    """回填数据的匿名汇总（总量 / 按结果 / 按录取档位），用于可信度叙事。"""
    return await user_db.feedback_summary()
