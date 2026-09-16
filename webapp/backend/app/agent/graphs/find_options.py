"""子图 A（find_options，§6.1）：按位次/分数找合适的院校-专业（选校问答）。

确定性前置：位次是必需输入（分数能反查位次也行）。拿不到就追问 CLARIFY_NEED_RANK，
绝不让模型自己猜位次（§3 原则：确定性事实来自工具）。

取证：先 locate_rank（位次定位），再 search_candidates（检索候选），写 ledger。
本批用确定性取证不走工具循环模型（避免网关 tools+reasoning 限制与轮数不稳定）；
结构化解读统一交给主图 synthesize。候选单元只来自工具结果（写进 ledger）。
"""
from __future__ import annotations

from typing import Any, Optional

from app.agent.evidence import EvidenceLedger
from app.agent.prompts import CLARIFY_NEED_RANK
from app.agent.tools import build_tools


def _rank_from_state(state: dict[str, Any]) -> Optional[int]:
    """从 slots 或 profile 里取位次（正整数），拿不到返回 None。"""
    slots = state.get("slots") or {}
    profile = state.get("profile") or {}
    for src in (slots, profile):
        raw = src.get("rank")
        if raw is None:
            continue
        try:
            n = int(raw)
        except (TypeError, ValueError):
            continue
        if n > 0:
            return n
    return None


def _score_from_state(state: dict[str, Any]) -> Optional[int]:
    """没位次时尝试取分数（能反查位次），拿不到返回 None。"""
    slots = state.get("slots") or {}
    profile = state.get("profile") or {}
    for src in (slots, profile):
        raw = src.get("score")
        if raw is None:
            continue
        try:
            n = int(raw)
        except (TypeError, ValueError):
            continue
        if n >= 0:
            return n
    return None


async def find_options_collect_node(state: dict[str, Any]) -> dict[str, Any]:
    """确定性取证：位次门禁 → locate_rank → search_candidates → 写 ledger。

    没有位次也没有分数 → 置 clarify=CLARIFY_NEED_RANK，主图据此结束本轮（不猜位次）。
    """
    rank = _rank_from_state(state)
    score = _score_from_state(state)
    if rank is None and score is None:
        return {"clarify": CLARIFY_NEED_RANK}

    profile = state.get("profile") or {}
    slots = state.get("slots") or {}
    ledger: EvidenceLedger = state["ledger"]
    tools = {t.name: t for t in build_tools(ledger, profile)}

    category = profile.get("category") or slots.get("category") or "普通类"
    subject = profile.get("subject") or slots.get("subject") or ""
    batch = profile.get("batch") or slots.get("batch") or ""
    year = profile.get("year") or slots.get("year")

    # 1) 位次定位（有位次才取；locate 需要正整数位次）
    if rank is not None:
        locate_args: dict[str, Any] = {
            "category": category,
            "subject": subject,
            "rank": rank,
        }
        if batch:
            locate_args["batch"] = batch
        try:
            await tools["locate_rank"].ainvoke(locate_args)
        except Exception:  # noqa: BLE001 — 定位失败不阻断检索
            pass

    # 2) 候选检索（search_candidates 需 year/category/subject/batch）
    search_args: dict[str, Any] = {
        "year": int(year) if year is not None else 0,
        "category": category,
        "subject": subject,
        "batch": batch,
    }
    if rank is not None:
        search_args["rank"] = rank
    if score is not None:
        search_args["score"] = score
    # Optional filters must come from trusted structured context. Route-model
    # slots are semantic hints and can vary or invent unsupported values.
    for key in ("province", "city", "level", "major_keyword", "risk"):
        val = profile.get(key)
        if val:
            search_args[key] = val

    await tools["search_candidates"].ainvoke(search_args)
    return {"clarify": None}
