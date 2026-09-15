"""Deterministic volunteer-plan health checks shared by the UI and future Agent tools."""
from collections import Counter


STRATEGY_BASELINES = {
    "冲击": {"冲": 0.36, "稳": 0.29, "保": 0.35, "label": "冲击型 36/29/35"},
    "均衡": {"冲": 0.20, "稳": 0.50, "保": 0.30, "label": "均衡型 20/50/30"},
    "稳妥": {"冲": 0.10, "稳": 0.55, "保": 0.35, "label": "稳妥型 10/55/35"},
}
RISK_LABELS = ("冲", "稳", "保", "高波动", "数据不足")


def analyze_plan(plan: dict) -> dict:
    entries = plan.get("entries") or []
    counts = {risk: 0 for risk in RISK_LABELS}
    counts.update(Counter(e.get("risk") for e in entries if e.get("risk") in counts))
    total = len(entries)
    if total == 0:
        return {
            "counts": counts, "total": 0,
            "warnings": ["方案为空：请从「智能匹配」或「收藏」中加入志愿。"],
            "notes": [], "ok": False, "issues": 0,
        }

    problems = []
    seen = Counter(f"{e.get('school_code')}|{e.get('major_code') or e.get('major_name')}" for e in entries)
    missing = sum(e.get("last_year_rank") is None for e in entries)
    plan_version = plan.get("data_version")
    version_mismatch = sum(
        bool(plan_version and e.get("data_version") and e.get("data_version") != plan_version)
        for e in entries
    )
    flagged = [
        f"{e.get('school_name')}·{e.get('major_name')}（{'、'.join(e.get('flags') or [])}）"
        for e in entries if e.get("flags")
    ]
    duplicates = sum(n > 1 for n in seen.values())

    if counts["冲"] / total > 0.5:
        problems.append(f"「冲」占比 {round(counts['冲'] / total * 100)}%（>50%），风险过度集中，建议增加稳/保志愿。")
    if counts["保"] == 0:
        problems.append("没有「保」档志愿，存在滑档风险，建议至少配置 2–3 个保底。")
    if counts["稳"] == 0 and total >= 5:
        problems.append("没有「稳」档志愿，梯度断层，建议补充。")
    if counts["高波动"] / total > 0.3:
        problems.append("「高波动」志愿占比偏高，结果不确定性大。")

    baseline = STRATEGY_BASELINES.get(plan.get("strategy"), STRATEGY_BASELINES["均衡"])
    if total >= 10:
        safe_ratio = counts["保"] / total
        if safe_ratio < baseline["保"] - 0.1:
            problems.append(
                f"保底配比不足：保 {counts['保']}/{total}（{round(safe_ratio * 100)}%）低于「{baseline['label']}」基线约 "
                f"{round(baseline['保'] * 100)}%——保底是防滑档安全垫，建议补充标准保底。"
            )
        reach_ratio = counts["冲"] / total
        if reach_ratio > baseline["冲"] + 0.15:
            problems.append(
                f"冲刺占比偏高：{round(reach_ratio * 100)}% 超出「{baseline['label']}」基线（约 "
                f"{round(baseline['冲'] * 100)}%）15 个百分点以上，挤压稳/保槽位。"
            )
    if missing:
        problems.append(f"{missing} 个志愿缺少最低位次数据（仅分数参考），判定可靠性有限。")
    if duplicates:
        problems.append(f"存在 {duplicates} 组重复的「院校+专业」，请检查是否误加。")
    if version_mismatch:
        problems.append(f"{version_mismatch} 个志愿的数据版本与方案创建时不一致，建议重新匹配后确认。")
    if flagged:
        suffix = f" 等 {len(flagged)} 项" if len(flagged) > 5 else ""
        problems.append(
            f"{len(flagged)} 个志愿含特殊报考标记，需逐项核实学费/协议/报考条件后再保留："
            + "；".join(flagged[:5]) + suffix + "。"
        )
    if total > 112:
        problems.append("志愿数超过辽宁本科批 112 个上限。")

    with_rank = [(i, e) for i, e in enumerate(entries) if e.get("last_year_rank") is not None]
    if total >= 5:
        tail = max(3, -(-total // 5))
        bad_tail = sum(e.get("risk") != "保" for e in entries[-tail:])
        if bad_tail:
            problems.append(f"尾部保底不足：最后 {tail} 个志愿中有 {bad_tail} 个不是「保」档——尾部每一位都应是滑档前的安全网，请补深保底段。")
        inverted = 0
        gaps = []
        for (prev_i, prev), (cur_i, cur) in zip(with_rank, with_rank[1:]):
            a, b = prev["last_year_rank"], cur["last_year_rank"]
            if b < a:
                inverted += 1
            elif a > 0 and b > a * 2.5:
                gaps.append(f"第 {prev_i + 1}→{cur_i + 1} 位")
        if inverted:
            problems.append(f"{inverted} 处志愿顺序倒退（后一位比前一位更难录），建议点「按冲→稳→保重排」。")
        if gaps:
            suffix = " 等" if len(gaps) > 3 else ""
            problems.append(f"梯度断层：{'、'.join(gaps[:3])}{suffix}相邻志愿门槛位次跳变过大（超过 2.5 倍），中间建议补充过渡志愿。")
        over_safe = sum(e.get("risk") == "保" and bool(e.get("over_safe")) for e in entries)
        if over_safe:
            problems.append(f"含 {over_safe} 个「过深保底」（门槛位次 > 你位次 3 倍）：保护在 2 倍左右已饱和，过深不增加安全性、只消耗志愿额度，建议替换为标准保底或极稳垫底。")
        over_reach = sum(e.get("risk") == "冲" and bool(e.get("over_reach")) for e in entries)
        if over_reach:
            problems.append(f"含 {over_reach} 个「超冲」（门槛好于你位次 20% 以上）：差距过大基本只消耗槽位，建议最多保留 1–2 个梦想位置于表头。")

    notes = []
    cooling = sum(e.get("trend_label") in {"持续降温", "趋势（内部分化）"} for e in entries)
    heating = sum(e.get("trend_label") == "持续升温" for e in entries)
    if cooling:
        notes.append(f"有 {cooling} 个志愿所属专业门槛连降两年。本表分档以历史最难年为基准，对它们偏保守——这些位置实际可能比标注的更容易录取。")
    if heating:
        notes.append(f"有 {heating} 个志愿所属专业门槛连升两年。去年门槛可能低估明年，这些位置宜留更多余量，不要当作稳档看待。")
    ok = not problems
    return {
        "counts": counts, "total": total,
        "warnings": ["梯度结构良好：冲稳保配置合理，无重复与数据缺失。"] if ok else problems,
        "notes": notes, "ok": ok, "issues": len(problems),
    }
