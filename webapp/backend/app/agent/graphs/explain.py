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


def _parse_unit(state: dict[str, Any]) -> dict[str, Any] | None:
    """从 page_context.unit 或 slots 里抽出完整院校专业上下文。

    字符串 unit_id 的第二段可能是专业代码，不能安全当作专业名查询。
    这里只需前两段（院校代码、专业）就能取证；batch 由 profile/slots 回退。
    """
    page_ctx = state.get("page_context") or {}
    slots = state.get("slots") or {}

    raw = page_ctx.get("unit") or page_ctx.get("unit_id") or slots.get("unit")
    if isinstance(raw, dict):
        code = str(raw.get("school_code") or raw.get("code") or "").strip()
        major = str(raw.get("major_name") or raw.get("major") or "").strip()
        if code and major:
            return dict(raw)

    # Candidate IDs contain a major code, not a major name. They are insufficient
    # for the exact historical lookup and must not be treated as names.
    if isinstance(raw, str) and "|" in raw:
        return None

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
        return {"school_code": code, "major_name": major}
    return None


async def explain_collect_node(state: dict[str, Any]) -> dict[str, Any]:
    """确定性取证：定位 unit → get_unit_detail（+ get_school_profile）→ 写 ledger。

    拿不到 unit → 置 clarify，主图据此结束本轮（不猜院校-专业）。
    """
    parsed = _parse_unit(state)
    if parsed is None:
        return {"clarify": CLARIFY_GENERIC}

    code = str(parsed.get("school_code") or parsed.get("code") or "").strip()
    major = str(parsed.get("major_name") or parsed.get("major") or "").strip()
    major_code = str(parsed.get("major_code") or "").strip() or None
    profile = state.get("profile") or {}
    ledger: EvidenceLedger = state["ledger"]
    tools = {t.name: t for t in build_tools(ledger, profile)}

    category = profile.get("category")

    # The clicked match result is the authoritative evidence for its risk bucket.
    ledger.add("selected_candidate", {"school_code": code, "major_name": major}, parsed)

    # 1) 单元历年分数/位次明细（必取）
    detail_args: dict[str, Any] = {"code": code, "major_name": major}
    if major_code is not None:
        detail_args["major_code"] = major_code
    if category is not None:
        detail_args["category"] = category
    detail = await tools["get_unit_detail"].ainvoke(detail_args)
    if not detail.get("data"):
        return {"clarify": "未找到这个院校专业的历史录取明细，请返回匹配结果重新选择。"}

    # 2) 院校画像（辅助解读，拿不到不阻断）
    try:
        await tools["get_school_profile"].ainvoke({"code": code})
    except Exception:  # noqa: BLE001 — 辅助证据取不到不影响主流程
        pass

    return {"clarify": None}
