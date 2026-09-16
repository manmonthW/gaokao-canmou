"""Bounded Agent harness: understand, plan, execute, and verify coverage.

The model supplies semantic hints. Deterministic code validates executable
constraints against the original question/profile before any tool is called.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


_PROVINCE_NAMES = (
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
    "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆", "香港",
    "澳门", "台湾",
)
_RISK_NAMES = ("冲", "稳", "保")
MAX_PLAN_STEPS = 8


class TaskSpec(BaseModel):
    """Validated representation of what the current turn asks the Agent to do."""

    intent: str
    provinces: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    group_by: list[Literal["province", "risk"]] = Field(default_factory=list)
    requested_output: Literal["list", "comparison", "explanation"] = "list"
    semantic_slots: dict[str, Any] = Field(default_factory=dict)


class PlanStep(BaseModel):
    """One bounded, idempotent read operation."""

    id: str
    tool: Literal["search_candidates"]
    args: dict[str, Any] = Field(default_factory=dict)
    coverage_key: str
    status: Literal["pending", "done", "empty", "failed"] = "pending"
    evidence_ids: list[str] = Field(default_factory=list)


class CoverageItem(BaseModel):
    """Execution coverage for one required part of the user's request."""

    key: str
    status: Literal["covered", "empty", "failed", "not_run"]
    evidence_ids: list[str] = Field(default_factory=list)


def _mentioned_values(question: str, values: tuple[str, ...]) -> list[str]:
    return [value for value in values if value in question]


def build_task_spec(state: dict[str, Any]) -> TaskSpec:
    """Build an executable task contract without trusting free-form model values."""
    question = str(state.get("question") or "")
    profile = state.get("profile") or {}
    slots = state.get("slots") or {}
    intent = str(state.get("intent") or "need_clarify")

    provinces = _mentioned_values(question, _PROVINCE_NAMES)
    if not provinces and profile.get("province"):
        provinces = [str(profile["province"])]

    risks = _mentioned_values(question, _RISK_NAMES)
    if not risks and profile.get("risk") in _RISK_NAMES:
        risks = [str(profile["risk"])]

    group_by: list[Literal["province", "risk"]] = []
    if len(provinces) > 1:
        group_by.append("province")
    if len(risks) > 1:
        group_by.append("risk")
    requested_output: Literal["list", "comparison", "explanation"] = "list"
    if any(word in question for word in ("比较", "对比", "区别")):
        requested_output = "comparison"
    elif intent == "explain_unit":
        requested_output = "explanation"

    return TaskSpec(
        intent=intent,
        provinces=provinces,
        risks=risks,
        group_by=group_by,
        requested_output=requested_output,
        semantic_slots=dict(slots),
    )


def build_plan(spec: TaskSpec) -> list[PlanStep]:
    """Expand independent filters into bounded deterministic retrieval steps."""
    if spec.intent != "find_options":
        return []

    dimensions: list[tuple[str | None, str | None]] = []
    if spec.provinces:
        dimensions = [(province, None) for province in spec.provinces]
    elif spec.risks:
        dimensions = [(None, risk) for risk in spec.risks]
    else:
        dimensions = [(None, None)]

    steps: list[PlanStep] = []
    for index, (province, risk) in enumerate(dimensions[:MAX_PLAN_STEPS], start=1):
        args = {key: value for key, value in (("province", province), ("risk", risk)) if value}
        key = ":".join((province or "all", risk or "all"))
        steps.append(
            PlanStep(
                id=f"P{index}",
                tool="search_candidates",
                args=args,
                coverage_key=key,
            )
        )
    return steps


def coverage_from_plan(plan: list[dict[str, Any] | PlanStep]) -> list[CoverageItem]:
    status_map = {
        "done": "covered",
        "empty": "empty",
        "failed": "failed",
        "pending": "not_run",
    }
    items: list[CoverageItem] = []
    for raw in plan:
        step = raw if isinstance(raw, PlanStep) else PlanStep.model_validate(raw)
        items.append(
            CoverageItem(
                key=step.coverage_key,
                status=status_map[step.status],
                evidence_ids=step.evidence_ids,
            )
        )
    return items


def completion_issues(state: dict[str, Any]) -> list[dict[str, str]]:
    """Verify that all planned retrieval work ran before answer generation."""
    issues: list[dict[str, str]] = []
    for item in coverage_from_plan(state.get("plan") or []):
        if item.status == "not_run":
            issues.append({
                "code": "coverage_not_run",
                "detail_zh": f"用户要求的检索范围「{item.key}」尚未执行。",
            })
        elif item.status == "failed":
            issues.append({
                "code": "coverage_failed",
                "detail_zh": f"用户要求的检索范围「{item.key}」执行失败。",
            })
    return issues
