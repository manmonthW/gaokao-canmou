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
_CITY_NAMES = (
    "沈阳", "大连", "鞍山", "抚顺", "本溪", "丹东", "锦州", "营口",
    "阜新", "辽阳", "盘锦", "铁岭", "朝阳", "葫芦岛",
)
_LEVEL_NAMES = ("本科", "专科")
_UNSUPPORTED_SCHOOL_TAGS = ("985", "211", "双一流")
_MAJOR_SUFFIXES = ("专业", "类", "学", "工程", "技术", "医学", "教育", "管理")
_FOLLOW_UP_MARKERS = ("那", "改成", "换成", "再看", "比较一下", "对比一下", "呢")
MAX_PLAN_STEPS = 8


class TaskSpec(BaseModel):
    """Validated representation of what the current turn asks the Agent to do."""

    intent: str
    provinces: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    majors: list[str] = Field(default_factory=list)
    levels: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    group_by: list[Literal["province", "city", "major", "level", "risk"]] = Field(default_factory=list)
    requested_output: Literal["list", "comparison", "explanation"] = "list"
    effective_question: str = ""
    clarification: str | None = None
    replanned_from_history: bool = False
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


def _slot_values(slots: dict[str, Any], key: str) -> list[str]:
    raw = slots.get(key)
    values = raw if isinstance(raw, list) else [raw]
    return [str(value).strip() for value in values if isinstance(value, str) and value.strip()]


def _verified_slot_values(question: str, slots: dict[str, Any], key: str) -> list[str]:
    """Accept model-extracted open vocabulary only when it appears verbatim in user text."""
    return [value for value in _slot_values(slots, key) if value in question]


def _major_values(question: str, slots: dict[str, Any]) -> list[str]:
    values = _verified_slot_values(question, slots, "major_keyword")
    if values:
        return values
    # A conservative fallback covers common short follow-ups without trusting
    # arbitrary model inventions. It intentionally avoids generic request words.
    tokens = question.replace("，", "、").replace(",", "、").split("、")
    candidates: list[str] = []
    for token in tokens:
        token = token.strip(" 请推荐查找看看院校学校和与的")
        if 2 <= len(token) <= 16 and any(token.endswith(suffix) for suffix in _MAJOR_SUFFIXES):
            candidates.append(token)
    return list(dict.fromkeys(candidates))


def _history_base_question(state: dict[str, Any], question: str) -> str | None:
    if len(question) > 24 or not any(marker in question for marker in _FOLLOW_UP_MARKERS):
        return None
    for turn in reversed(state.get("history") or []):
        if turn.get("role") != "user":
            continue
        content = str(turn.get("content") or "").strip()
        if content and content != question and any(
            word in content for word in ("推荐", "院校", "专业", "冲", "稳", "保", "比较", "对比")
        ):
            return content
    return None


def build_task_spec(state: dict[str, Any]) -> TaskSpec:
    """Build an executable task contract without trusting free-form model values."""
    question = str(state.get("question") or "")
    profile = state.get("profile") or {}
    slots = state.get("slots") or {}
    intent = str(state.get("intent") or "need_clarify")

    base_question = _history_base_question(state, question)
    effective_question = f"{base_question}；当前补充：{question}" if base_question else question
    replaces_dimension = base_question is not None and any(marker in question for marker in ("改成", "换成"))

    provinces = _mentioned_values(effective_question, _PROVINCE_NAMES)
    current_provinces = _mentioned_values(question, _PROVINCE_NAMES)
    if replaces_dimension and current_provinces:
        provinces = current_provinces
    if not provinces and profile.get("province"):
        provinces = [str(profile["province"])]

    cities = _mentioned_values(effective_question, _CITY_NAMES)
    current_cities = _mentioned_values(question, _CITY_NAMES)
    if replaces_dimension and current_cities:
        cities = current_cities
    if not cities and profile.get("city"):
        cities = [str(profile["city"])]

    majors = _major_values(effective_question, slots)
    current_majors = _major_values(question, slots)
    if replaces_dimension and current_majors:
        majors = current_majors
    if not majors and profile.get("major_keyword"):
        majors = [str(profile["major_keyword"])]

    levels = _mentioned_values(effective_question, _LEVEL_NAMES)
    current_levels = _mentioned_values(question, _LEVEL_NAMES)
    if replaces_dimension and current_levels:
        levels = current_levels
    if not levels and profile.get("level"):
        levels = [str(profile["level"])]

    risks = _mentioned_values(effective_question, _RISK_NAMES)
    current_risks = _mentioned_values(question, _RISK_NAMES)
    if replaces_dimension and current_risks:
        risks = current_risks
    if not risks and profile.get("risk") in _RISK_NAMES:
        risks = [str(profile["risk"])]

    dimensions = {
        "province": provinces,
        "city": cities,
        "major": majors,
        "level": levels,
        "risk": risks,
    }
    group_by = [name for name, values in dimensions.items() if len(values) > 1]
    requested_output: Literal["list", "comparison", "explanation"] = "list"
    if any(word in question for word in ("比较", "对比", "区别")):
        requested_output = "comparison"
    elif intent == "explain_unit":
        requested_output = "explanation"

    clarification = None
    unsupported_tags = _mentioned_values(effective_question, _UNSUPPORTED_SCHOOL_TAGS)
    if unsupported_tags:
        clarification = (
            f"当前候选检索还不能把「{'、'.join(unsupported_tags)}」作为院校层次精确筛选。"
            "请改用本科/专科层次，或先按城市、专业和冲稳保筛选。"
        )
    elif any(len(values) > MAX_PLAN_STEPS for values in dimensions.values()):
        clarification = f"一次最多比较 {MAX_PLAN_STEPS} 个目标，请缩小城市、专业、院校层次或档位范围。"
    elif requested_output == "comparison" and not group_by:
        clarification = "请告诉我至少两个要比较的城市、专业、院校层次或冲稳保档位。"
    elif len(group_by) > 1:
        labels = {"province": "省份", "city": "城市", "major": "专业", "level": "院校层次", "risk": "档位"}
        names = "、".join(labels[name] for name in group_by)
        clarification = f"你同时给了多个{names}。请说明想按哪个维度分别比较，避免遗漏或组合错位。"

    return TaskSpec(
        intent=intent,
        provinces=provinces,
        cities=cities,
        majors=majors,
        levels=levels,
        risks=risks,
        group_by=group_by,
        requested_output=requested_output,
        effective_question=effective_question,
        clarification=clarification,
        replanned_from_history=base_question is not None,
        semantic_slots=dict(slots),
    )


def build_plan(spec: TaskSpec) -> list[PlanStep]:
    """Expand independent filters into bounded deterministic retrieval steps."""
    if spec.intent != "find_options" or spec.clarification:
        return []

    values_by_dimension = {
        "province": spec.provinces,
        "city": spec.cities,
        "major_keyword": spec.majors,
        "level": spec.levels,
        "risk": spec.risks,
    }
    group_key = spec.group_by[0] if spec.group_by else None
    arg_key = "major_keyword" if group_key == "major" else group_key
    dimensions = values_by_dimension.get(arg_key, []) if arg_key else [None]

    common_args = {
        key: values[0]
        for key, values in values_by_dimension.items()
        if values and key != arg_key
    }

    steps: list[PlanStep] = []
    for index, value in enumerate(dimensions[:MAX_PLAN_STEPS], start=1):
        args = dict(common_args)
        if arg_key and value:
            args[arg_key] = value
        key = f"{group_key}:{value}" if group_key and value else "all"
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
