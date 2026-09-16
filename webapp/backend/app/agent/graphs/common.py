"""图层共用节点与工具函数（§6 / §8）。

集中三件事，供主图复用：
  • _ainvoke_json：调模型 → 取 AIMessage.content → 解析为 dict（空答按 §5.3 视为预算耗尽错误）。
  • synthesize / repair 节点：只依据证据写结构化答案；带工具的节点在子图里，本层无工具。
  • verify / deliver / fallback 节点：确定性校验 + 免责声明由程序追加（§8.2）。

模型只做语义判断，程序做确定性事实（§3）。verify 失败把「具体问题」交给 repair 重写（§3 原则6）。
"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.contracts import AdvisorAnswer
from app.agent.evidence import EvidenceLedger
from app.agent.guards import append_disclaimer, verify_answer
from app.agent.llm import make_model
from app.agent.prompts import REPAIR_SYSTEM, SYNTHESIZE_SYSTEM

# 修复上限（§6.3）：只修一次，再失败走确定性模板。
_MAX_REPAIRS = 1


class ModelEmptyError(RuntimeError):
    """§5.3 规则4：空答=预算耗尽=错误。由 synthesize/repair 抛出，主图降级捕获。"""


def _extract_content(message: Any) -> str:
    """从 AIMessage 里取纯文本 content（兼容 content 为 list 分块的情形）。"""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(str(part["text"]))
        return "".join(parts)
    return str(content or "")


def _strip_code_fence(text: str) -> str:
    """去掉模型偶尔包的 ```json ... ``` 围栏，取第一个完整 JSON 对象。"""
    t = text.strip()
    if t.startswith("```"):
        # 去掉首行 ```json / ``` 与末行 ```
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    # 截取第一个 { 到最后一个 }，容忍前后杂字
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        return t[start : end + 1]
    return t


async def _ainvoke_json(*, node: str, system: str, user: str) -> dict[str, Any]:
    """调生成节点模型并把回答解析成 dict。

    空答按 §5.3 规则4 视为预算耗尽 → 抛 ModelEmptyError 供主图降级。
    解析失败也当作模型未产出有效结构 → 同样抛 ModelEmptyError（走修复/降级）。
    """
    model = make_model(node=node)
    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    resp = await model.ainvoke(messages)
    raw = _extract_content(resp).strip()
    if not raw:
        raise ModelEmptyError(f"{node} 返回空内容（预算耗尽或网关拦截）。")
    try:
        parsed = json.loads(_strip_code_fence(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ModelEmptyError(f"{node} 输出无法解析为 JSON：{exc}") from exc
    if not isinstance(parsed, dict):
        raise ModelEmptyError(f"{node} 输出不是 JSON 对象。")
    return parsed


def _normalize_answer(parsed: dict[str, Any]) -> dict[str, Any]:
    """用 AdvisorAnswer 归一：补默认、丢多余键，产出稳定的 model_dump。"""
    answer = AdvisorAnswer.model_validate(parsed)
    return answer.model_dump()


def _synthesize_user_prompt(state: dict[str, Any], ledger: EvidenceLedger) -> str:
    """给综合/修复节点的用户消息：原问题 + 证据清单。"""
    question = state.get("question") or ""
    intent = state.get("intent") or ""
    return (
        f"用户问题：{question}\n"
        f"意图：{intent}\n\n"
        f"证据（只能用这些内容作答，正文每段标注 evidence_ids）：\n"
        f"{ledger.render_for_prompt()}"
    )


async def synthesize_node(state: dict[str, Any]) -> dict[str, Any]:
    """§6.1 综合：无工具、reasoning=low，只依据证据写结构化答案。"""
    ledger: EvidenceLedger = state["ledger"]
    user = _synthesize_user_prompt(state, ledger)
    parsed = await _ainvoke_json(node="synthesize", system=SYNTHESIZE_SYSTEM, user=user)
    draft = _normalize_answer(parsed)
    return {"draft": draft}


def _repair_user_prompt(state: dict[str, Any], ledger: EvidenceLedger) -> str:
    """给修复节点的用户消息：上一版答案 + 具体问题清单 + 证据。"""
    draft = state.get("draft") or {}
    issues = state.get("issues") or []
    issue_lines = "\n".join(
        f"  {i}. [{it.get('code', '')}] {it.get('detail_zh', '')}"
        for i, it in enumerate(issues, start=1)
    )
    return (
        f"上一版答案（JSON）：\n{json.dumps(draft, ensure_ascii=False)}\n\n"
        f"具体问题（逐条修复）：\n{issue_lines}\n\n"
        f"证据（只能用这些内容作答）：\n{ledger.render_for_prompt()}"
    )


async def repair_node(state: dict[str, Any]) -> dict[str, Any]:
    """§6.1 定向修复：只改被指出的地方，重出完整答案；修复计数 +1。"""
    ledger: EvidenceLedger = state["ledger"]
    user = _repair_user_prompt(state, ledger)
    parsed = await _ainvoke_json(node="repair", system=REPAIR_SYSTEM, user=user)
    draft = _normalize_answer(parsed)
    repairs = int(state.get("repairs") or 0) + 1
    return {"draft": draft, "repairs": repairs}


def verify_node(state: dict[str, Any]) -> dict[str, Any]:
    """§8.2 确定性校验：对 draft 逐条核对证据，产出 issues 列表（空=通过）。"""
    draft = state.get("draft") or {}
    ledger: EvidenceLedger = state["ledger"]
    issues = verify_answer(draft, ledger)
    return {"issues": issues}


def _verify_route(state: dict[str, Any]) -> str:
    """verify 后的确定性分支：通过→deliver；失败且还能修→repair；否则→fallback。"""
    issues = state.get("issues") or []
    if not issues:
        return "deliver"
    if int(state.get("repairs") or 0) < _MAX_REPAIRS:
        return "repair"
    return "fallback"


def deliver_node(state: dict[str, Any]) -> dict[str, Any]:
    """§8.2 交付：程序追加免责声明（不交给模型写），产出最终 answer。"""
    draft = state.get("draft") or {}
    answer = append_disclaimer(draft)
    return {"answer": answer}


def _units_from_ledger(ledger: EvidenceLedger):
    """从 search_candidates 证据里抽院校-专业条目（降级用），最多 10 条。"""
    from app.agent.contracts import RecommendedUnit

    units = []
    cited_eid: str | None = None
    for ev in ledger.all():
        if ev.tool != "search_candidates":
            continue
        data = ev.data if isinstance(ev.data, dict) else {}
        items = data.get("items") or data.get("units") or data.get("candidates") or []
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            school = str(it.get("school_name") or it.get("school") or "").strip()
            major = str(it.get("major_name") or it.get("major") or "").strip()
            if not school or not major:
                continue
            cited_eid = ev.eid
            units.append(
                RecommendedUnit(
                    school=school,
                    major=major,
                    batch=it.get("batch"),
                    rank_last=it.get("last_year_rank"),
                    risk=it.get("risk"),
                    evidence_ids=[ev.eid],
                )
            )
            if len(units) >= 10:
                return units, [ev.eid]
    return units, ([cited_eid] if cited_eid else [ev.eid for ev in ledger.all()])


def fallback_node(state: dict[str, Any]) -> dict[str, Any]:
    """§8.4 降级：修复仍失败 → 确定性模板答案，只列证据不加解读。

    不再走模型：把 ledger 里检索到的院校-专业与位次列成中性条目，
    caveats 说明「AI 解读暂不可用」，再由程序追加免责声明。
    """
    ledger: EvidenceLedger = state["ledger"]
    units, _ = _units_from_ledger(ledger)
    summary = (
        "AI 解读暂不可用，下面只列出检索到的院校-专业与历年位次，供你自行参考。"
        if units
        else "AI 解读暂不可用，且这次没有检索到可用的院校-专业数据。"
    )
    draft = AdvisorAnswer(
        summary=summary,
        sections=[],
        recommended_units=units,
        caveats=["本次为降级结果：AI 未能生成解读，以上仅为检索到的原始数据。"],
        follow_ups=[],
        needs_clarification=False,
    ).model_dump()
    answer = append_disclaimer(draft)
    return {"draft": draft, "answer": answer, "issues": []}
