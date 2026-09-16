"""输入守卫 + 确定性校验器 + 免责声明追加（§6.1 / §8.2 / §8.4）。

本模块不走模型，全部是确定性规则：
  • input_guard：越界/注入/艺体推荐 → 直接判定 refuse（在入图第一关）。
  • verify_answer：对综合节点产出的 AdvisorAnswer 逐条核对证据，返回 issues 列表。
  • append_disclaimer：免责声明由程序追加（§8.2），绝不交给模型写。

校验器的每条规则对应 §8.2：单元存在 / 数字可溯源 / 档位一致 / 禁用表述 /
状态不省略 / 越界内容 / 引用完整。任一失败都记一条 {code, detail_zh} issue，
供 repair 节点拿到「具体问题」重写（§3 原则 6）。
"""
from __future__ import annotations

import re
from typing import Any

from .evidence import EvidenceLedger

# ---- 越界：非普通类类别、非辽宁、代填、艺体推荐（§8.2 越界内容）----
_OUT_OF_SCOPE_CATEGORY = ("艺术", "体育", "艺术类", "体育类", "艺体")
_OUT_OF_SCOPE_KEYWORDS = (
    "代填", "代报", "帮我填报", "替我填", "包过", "内部指标",
)
_NON_LIAONING_HINT = ("北京", "上海", "天津", "重庆", "广东", "江苏", "浙江", "山东", "河南", "四川")

# ---- 注入：试图套出系统提示词/凭证/环境（§11）----
_INJECTION_PATTERNS = (
    "忽略", "ignore", "system prompt", "系统提示", "你的提示词", "repeat the above",
    "环境变量", "api key", "api-key", "token", "密钥", "secret", "凭证",
)

# ---- 禁用表述（§8.2 禁用表述）----
_FORBIDDEN_PHRASES = (
    "一定能录取", "一定录取", "保证录取", "保证能", "包录取", "百分百",
    "录取概率", "录取几率", "稳录", "必录",
)
_FORBIDDEN_PCT = re.compile(r"百分之[一-龥\d]+的把握")

# ---- 状态提示词（§8.2 状态不省略）：证据里出现这些 → caveats 必须覆盖 ----
_STATUS_HINTS = ("未核验", "数据不足", "未发布", "暂无数据", "仅供参考", "待更新")

# ---- 免责声明（§8.2 由程序追加）----
DISCLAIMER = (
    "以上为基于历史数据的参考，位次、分数线每年会波动，录取结果以官方公布为准，请结合自身情况谨慎填报。"
)


def input_guard(question: str, profile: dict[str, Any] | None) -> tuple[bool, str | None]:
    """入图第一关：返回 (allowed, refuse_reason_zh)。

    allowed=False 时 refuse_reason_zh 为给用户的中文说明；主图据此直连 refuse→END。
    这里只做确定性拦截，语义模糊的留给 route_intent 的模型判 refuse。
    """
    q = (question or "").strip()
    if not q:
        return False, "请告诉我你想咨询什么，比如你的位次和想看的批次。"

    profile = profile or {}
    category = str(profile.get("category") or "")
    if any(c in category for c in _OUT_OF_SCOPE_CATEGORY):
        return False, None  # 类别越界，refuse 文案由主图统一取 REFUSE_OUT_OF_SCOPE

    low = q.lower()
    if any(k in q or k in low for k in _OUT_OF_SCOPE_KEYWORDS):
        return False, None
    if any(k in low for k in _INJECTION_PATTERNS):
        return False, "这个问题我没法帮你，我只能基于公开的招录数据给辽宁普通类考生做参考。"

    return True, None


def _iter_evidence_numbers(ledger: EvidenceLedger) -> set[int]:
    """收集证据里出现过的所有整数（位次/分数/人数），供数字可溯源核对。"""
    nums: set[int] = set()

    def walk(v: Any) -> None:
        if isinstance(v, bool):
            return
        if isinstance(v, int):
            nums.add(v)
        elif isinstance(v, float):
            nums.add(int(v))
        elif isinstance(v, str):
            for m in re.findall(r"\d+", v):
                try:
                    nums.add(int(m))
                except ValueError:
                    pass
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    for ev in ledger.all():
        walk(ev.data)
    return nums


def _evidence_text(ledger: EvidenceLedger) -> str:
    """证据里出现过的院校/专业等自由文本拼成一块，供档位/单元存在的包含式核对。"""
    parts: list[str] = []

    def walk(v: Any) -> None:
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    for ev in ledger.all():
        walk(ev.data)
    return "\n".join(parts)


def _extract_ints_ge100(text: str) -> list[int]:
    """抽取文本里所有 ≥100 的整数（位次/分数/人数量级），用于数字可溯源。"""
    out: list[int] = []
    for m in re.findall(r"\d+", text):
        try:
            n = int(m)
        except ValueError:
            continue
        if n >= 100:
            out.append(n)
    return out


def _number_traceable(n: int, evidence_nums: set[int]) -> bool:
    """数字可溯源：原值命中即可；否则去掉千位后（±容差）能对上证据里的某个值也算。

    位次常被模型四舍五入到千位（12013→12000），故允许「抹掉千位」后就近匹配。
    """
    if n in evidence_nums:
        return True
    # 抹到千位：n 落在 [k*1000, k*1000+999] 时，看证据里有没有同区间的值
    lo = (n // 1000) * 1000
    hi = lo + 999
    return any(lo <= e <= hi for e in evidence_nums)


def verify_answer(answer: dict[str, Any], ledger: EvidenceLedger) -> list[dict[str, str]]:
    """§8.2 确定性校验：返回 issues 列表（空 = 通过）。

    answer 为 AdvisorAnswer.model_dump()。每条 issue = {code, detail_zh}，
    detail_zh 要具体到「第几段/哪个值」，供 repair 节点定向重写（§3 原则 6）。
    """
    issues: list[dict[str, str]] = []
    valid_eids = {ev.eid for ev in ledger.all()}
    ev_text = _evidence_text(ledger)
    ev_nums = _iter_evidence_numbers(ledger)

    sections = answer.get("sections") or []
    units = answer.get("recommended_units") or []
    caveats = answer.get("caveats") or []
    summary = answer.get("summary") or ""

    # 全文（summary + 每段 body）用于禁用表述与数字可溯源
    full_text_parts = [summary] + [str(s.get("body", "")) for s in sections]
    full_text = "\n".join(full_text_parts)

    # 1) 禁用表述
    for phrase in _FORBIDDEN_PHRASES:
        if phrase in full_text:
            issues.append({
                "code": "forbidden_phrase",
                "detail_zh": f"出现了承诺性/禁用表述「{phrase}」，请改成中性、可核验的说法。",
            })
    if _FORBIDDEN_PCT.search(full_text):
        issues.append({
            "code": "forbidden_phrase",
            "detail_zh": "出现了「百分之…的把握」这类录取概率表述，请删除或改为中性说法。",
        })

    # 2) 引用完整 + 引用有效：每段正文至少 1 个有效证据 id
    for i, s in enumerate(sections, start=1):
        eids = s.get("evidence_ids") or []
        if not eids:
            issues.append({
                "code": "missing_citation",
                "detail_zh": f"第{i}段正文没有标注任何证据编号，请补上来源（如 E1）。",
            })
            continue
        for eid in eids:
            if eid not in valid_eids:
                issues.append({
                    "code": "invalid_citation",
                    "detail_zh": f"第{i}段引用的证据编号「{eid}」不存在，请改成证据里真实存在的编号。",
                })

    # 3) 数字可溯源：正文里 ≥100 的整数（抹千位后）必须能在证据数值里找到
    for i, s in enumerate(sections, start=1):
        for n in _extract_ints_ge100(str(s.get("body", ""))):
            if not _number_traceable(n, ev_nums):
                issues.append({
                    "code": "number_not_traceable",
                    "detail_zh": f"第{i}段里的数字「{n}」在证据中找不到来源，请删掉它或改成证据里的真实数值。",
                })

    # 4) 单元存在 + 档位一致：recommended_units 的院校/专业必须在证据文本里出现
    for j, u in enumerate(units, start=1):
        school = str(u.get("school") or "").strip()
        major = str(u.get("major") or "").strip()
        u_eids = u.get("evidence_ids") or []
        if school and school not in ev_text:
            issues.append({
                "code": "unit_not_in_evidence",
                "detail_zh": f"第{j}个推荐院校「{school}」在证据中不存在，请删掉或改成证据里检索到的院校。",
            })
        if major and major not in ev_text:
            issues.append({
                "code": "unit_not_in_evidence",
                "detail_zh": f"第{j}个推荐专业「{major}」在证据中不存在，请删掉或改成证据里检索到的专业。",
            })
        for eid in u_eids:
            if eid not in valid_eids:
                issues.append({
                    "code": "invalid_citation",
                    "detail_zh": f"第{j}个推荐单元引用的证据编号「{eid}」不存在。",
                })

    # 5) 状态不省略：证据里带未核验/数据不足/未发布提示时，caveats 必须提到
    caveat_text = "\n".join(str(c) for c in caveats)
    for hint in _STATUS_HINTS:
        if hint in ev_text and hint not in caveat_text:
            issues.append({
                "code": "status_omitted",
                "detail_zh": f"证据里出现了「{hint}」，但注意事项（caveats）没有说明，请如实补上。",
            })
            break  # 一条足以触发 repair，不刷屏

    return issues


def append_disclaimer(answer: dict[str, Any]) -> dict[str, Any]:
    """§8.2：免责声明由程序追加到 caveats 末尾（不交给模型写）。幂等。"""
    caveats = list(answer.get("caveats") or [])
    if DISCLAIMER not in caveats:
        caveats.append(DISCLAIMER)
    answer = dict(answer)
    answer["caveats"] = caveats
    return answer
