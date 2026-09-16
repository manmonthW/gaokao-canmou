"""子图 C（explain_unit，§6.1）：单个院校-专业的解读。

入口：page_context.unit（“院校代码|专业名”等）或 slots.unit。确定性拿证据（get_unit_detail /
可选 get_school_profile / check_subject_req）→ 写 ledger → 交给主图 synthesize 写结构化答案。

本子图不自己调模型：取证是确定性的（§3），解读由主图 synthesize 统一产出、verify 把关。
若拿不到 unit（无法定位到具体院校-专业），直接置 clarify 追问，结束本轮。
"""
from __future__ import annotations

from typing import Any

from app.agent.evidence import EvidenceLedger
from app.agent.prompts import CLARIFY_GENERIC
from app.agent.tools import build_tools


def _parse_unit(state: dict[str, Any]) -> tuple[str, str] | None:
    """从 page_context.unit 或 slots 里抽出（院校代码, 专业名）。

    unit_id 约定：${school_code}|${major_code || major_name}|${batch}（与前端 candidateId 对齐）。
    这里只需前两段（院校代码、专业）就能取证；batch 由 profile/slots 回退。
    """
    page_ctx = state.get("page_context") or {}
    slots = state.get("slots") or {}

    raw = page_ctx.get("unit") or page_ctx.get("unit_id") or slots.get("unit")
    if isinstance(raw, str) and "|" in raw:
        parts = raw.split("|")
        code = parts[0].strip()
        major = parts[1].strip() if len(parts) > 1 else ""
        if code and major:
            return code, major

    # 退而取结构化字段（page_context 直接给 school_code / major_name）
    code = str(page_ctx.get("school_code") or slots.get("school_code") or "").strip()
    major = str(
        page_ctx.get("major_name")
        or page_ctx.get("major")
        or slots.get("major_name")
        or slots.get("major")
        or ""
    ).strip()
    if code and major:
        return code, major
    return None


async def explain_collect_node(state: dict[str, Any]) -> dict[str, Any]:
    """确定性取证：定位 unit → get_unit_detail（+ get_school_profile）→ 写 ledger。

    拿不到 unit → 置 clarify，主图据此结束本轮（不猜院校-专业）。
    """
    parsed = _parse_unit(state)
    if parsed is None:
        return {"clarify": CLARIFY_GENERIC}

    code, major = parsed
    profile = state.get("profile") or {}
    ledger: EvidenceLedger = state["ledger"]
    tools = {t.name: t for t in build_tools(ledger, profile)}

    year = profile.get("year")
    category = profile.get("category")

    # 1) 单元历年分数/位次明细（必取）
    detail_args: dict[str, Any] = {"code": code, "major_name": major}
    if year is not None:
        detail_args["year"] = year
    if category is not None:
        detail_args["category"] = category
    await tools["get_unit_detail"].ainvoke(detail_args)

    # 2) 院校画像（辅助解读，拿不到不阻断）
    try:
        await tools["get_school_profile"].ainvoke({"code": code})
    except Exception:  # noqa: BLE001 — 辅助证据取不到不影响主流程
        pass

    return {"clarify": None}
