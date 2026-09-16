"""主图（§6.1）：确定性编排的 LangGraph StateGraph。

START → guard → load_context → route_intent
      → {find_options → 子图A取证, explain_unit → 子图C取证, need_clarify/refuse → 结束本轮}
      → synthesize → verify → {deliver / repair→synthesize / fallback→deliver} → END

本批只实现 find_options（子图A）与 explain_unit（子图C）（决策 3A）；
policy_qa / plan_review 归到 need_clarify 追问（下一批接入）。

模型只做语义（route_intent 分类、synthesize/repair 写解读），程序做确定性（guard/取证/verify/降级/免责）。
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agent.evidence import EvidenceLedger
from app.agent.graphs.common import (
    ModelEmptyError,
    _verify_route,
    deliver_node,
    fallback_node,
    repair_node,
    synthesize_node,
    verify_node,
)
from app.agent.graphs.explain import explain_collect_node
from app.agent.graphs.explain import _parse_unit
from app.agent.graphs.find_options import find_options_collect_node
from app.agent.guards import input_guard
from app.agent.llm import make_model
from app.agent.prompts import (
    CLARIFY_GENERIC,
    REFUSE_OUT_OF_SCOPE,
    ROUTE_INTENT_SYSTEM,
)
from app.agent.state import AgentState

# 本批直接取证的意图（有子图）；其余意图本批追问。
_SUPPORTED_INTENTS = {"find_options", "explain_unit"}


def guard_node(state: AgentState) -> dict[str, Any]:
    """§8.2 入图第一关：确定性拦截越界/注入 → 直接置 clarify（refuse 文案）结束本轮。"""
    question = state.get("question") or ""
    profile = state.get("profile") or {}
    allowed, reason = input_guard(question, profile)
    if allowed:
        return {"clarify": None}
    # reason 为 None 表示类别/内容越界，统一取越界文案；否则用 guard 给的说明。
    return {"clarify": reason or REFUSE_OUT_OF_SCOPE}


def _guard_route(state: AgentState) -> str:
    """guard 后：被拦（clarify 非空）→ END；否则进 load_context。"""
    if state.get("clarify"):
        return "end"
    return "load_context"


def load_context_node(state: AgentState) -> dict[str, Any]:
    """初始化运行时对象：建空证据账本，重置预算计数。

    ledger 为运行时对象（不序列化入检查点），各取证节点写入、synthesize/verify 读取。
    """
    updates: dict[str, Any] = {"repairs": 0}
    if state.get("ledger") is None:
        updates["ledger"] = EvidenceLedger()
    return updates


async def route_intent_node(state: AgentState) -> dict[str, Any]:
    """§6.1 意图分类：带 tools 语义但本节点只做分类（reasoning=none）。

    模型只输出 {intent, slots}；解析失败降级为 need_clarify（不猜、不报错）。
    """
    import json

    from langchain_core.messages import HumanMessage, SystemMessage

    from app.agent.graphs.common import _extract_content, _strip_code_fence

    # A concrete page unit is authoritative context; do not ask the model to
    # classify short follow-ups such as "为什么是稳档" without that signal.
    if _parse_unit(state) is not None:
        return {"intent": "explain_unit", "slots": dict(state.get("profile") or {})}

    question = state.get("question") or ""
    profile = state.get("profile") or {}
    user = f"用户问题：{question}\n已知考生上下文：{json.dumps(profile, ensure_ascii=False)}"

    try:
        model = make_model(node="intent")
        resp = await model.ainvoke(
            [SystemMessage(content=ROUTE_INTENT_SYSTEM), HumanMessage(content=user)]
        )
        parsed = json.loads(_strip_code_fence(_extract_content(resp).strip()))
    except Exception:  # noqa: BLE001 — 分类失败降级为追问，不猜意图
        return {"intent": "need_clarify", "slots": {}}

    if not isinstance(parsed, dict):
        return {"intent": "need_clarify", "slots": {}}

    intent = str(parsed.get("intent") or "need_clarify").strip()
    slots = parsed.get("slots")
    if not isinstance(slots, dict):
        slots = {}
    # 已有考生上下文优先，模型 slots 只补缺
    merged = {**slots, **{k: v for k, v in profile.items() if v is not None}}
    return {"intent": intent, "slots": merged}


def _intent_route(state: AgentState) -> str:
    """route_intent 后：本批支持的意图进对应取证子图；其余→ 追问/拒绝（END）。"""
    intent = state.get("intent") or ""
    if intent == "find_options":
        return "find_options"
    if intent == "explain_unit":
        return "explain_unit"
    if intent == "refuse":
        return "refuse"
    return "clarify"


def refuse_node(state: AgentState) -> dict[str, Any]:
    """越界：统一取拒绝文案，结束本轮。"""
    return {"clarify": REFUSE_OUT_OF_SCOPE}


def clarify_node(state: AgentState) -> dict[str, Any]:
    """need_clarify / policy_qa / plan_review（本批未接）：追问，结束本轮。"""
    if state.get("clarify"):
        return {}
    return {"clarify": CLARIFY_GENERIC}


def _collect_route(state: AgentState) -> str:
    """取证子图后：子图置了 clarify（位次缺失/无法定位）→ END；否则进 synthesize。"""
    if state.get("clarify"):
        return "end"
    return "synthesize"


async def synthesize_guarded_node(state: AgentState) -> dict[str, Any]:
    """synthesize 包一层降级捕获：模型空答/拦截 → 标记 model_failed，由路由转 fallback。"""
    try:
        return await synthesize_node(state)
    except ModelEmptyError:
        return {"model_failed": True}


async def repair_guarded_node(state: AgentState) -> dict[str, Any]:
    """repair 包一层降级捕获：修复时模型空答 → 标记 model_failed（转 fallback）。"""
    try:
        return await repair_node(state)
    except ModelEmptyError:
        # 保留已有 repairs 计数推进，避免死循环
        return {"model_failed": True, "repairs": int(state.get("repairs") or 0) + 1}


def _synthesize_route(state: AgentState) -> str:
    """synthesize 后：模型失败→fallback；否则进 verify。"""
    if state.get("model_failed"):
        return "fallback"
    return "verify"


def build_advisor_graph():
    """组装并编译主图。返回可 ainvoke 的 CompiledGraph。

    编排：guard → load_context → route_intent → {取证子图} → synthesize → verify
           → deliver / repair→synthesize / fallback→deliver。
    预算（§6.3）：修复上限由 _verify_route 把关（repairs<1）；硬截止/token 上限在调用端控。
    """
    g = StateGraph(AgentState)

    g.add_node("guard", guard_node)
    g.add_node("load_context", load_context_node)
    g.add_node("route_intent", route_intent_node)
    g.add_node("find_options", find_options_collect_node)
    g.add_node("explain_unit", explain_collect_node)
    g.add_node("refuse", refuse_node)
    g.add_node("clarify", clarify_node)
    g.add_node("synthesize", synthesize_guarded_node)
    g.add_node("verify", verify_node)
    g.add_node("repair", repair_guarded_node)
    g.add_node("deliver", deliver_node)
    g.add_node("fallback", fallback_node)

    g.add_edge(START, "guard")
    g.add_conditional_edges(
        "guard", _guard_route, {"end": END, "load_context": "load_context"}
    )
    g.add_edge("load_context", "route_intent")
    g.add_conditional_edges(
        "route_intent",
        _intent_route,
        {
            "find_options": "find_options",
            "explain_unit": "explain_unit",
            "refuse": "refuse",
            "clarify": "clarify",
        },
    )
    g.add_edge("refuse", END)
    g.add_edge("clarify", END)
    g.add_conditional_edges(
        "find_options", _collect_route, {"end": END, "synthesize": "synthesize"}
    )
    g.add_conditional_edges(
        "explain_unit", _collect_route, {"end": END, "synthesize": "synthesize"}
    )
    g.add_conditional_edges(
        "synthesize", _synthesize_route, {"fallback": "fallback", "verify": "verify"}
    )
    g.add_conditional_edges(
        "verify",
        _verify_route,
        {"deliver": "deliver", "repair": "repair", "fallback": "fallback"},
    )
    g.add_conditional_edges(
        "repair", _synthesize_route, {"fallback": "fallback", "verify": "verify"}
    )
    g.add_edge("fallback", "deliver")
    g.add_edge("deliver", END)

    return g.compile()
