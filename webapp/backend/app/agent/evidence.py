"""证据账本（§8）：所有结论可溯源。

每个工具调用产出一条 Evidence（自增 eid E1/E2/...），记录 tool/args/data/ts。
综合节点通过 render_for_prompt() 拿到紧凑文本（带 eid 供引用），
模型在回答里用 eid 引用来源，前端可回链到原始数据。

裁剪策略：列表默认截断（候选 ≤20、line_refs 按年），避免撑爆提示词。
"""
import time
from dataclasses import dataclass, field
from typing import Any

# 列表裁剪上限：候选、通用列表
_MAX_LIST_ITEMS = 20


def _truncate(value: Any, max_items: int = _MAX_LIST_ITEMS) -> Any:
    """递归裁剪：长列表截断并附计数标记，dict 逐字段裁剪。"""
    if isinstance(value, list):
        clipped = [_truncate(v, max_items) for v in value[:max_items]]
        if len(value) > max_items:
            clipped.append(f"…(共 {len(value)} 项，已截断 {len(value) - max_items} 项)")
        return clipped
    if isinstance(value, dict):
        return {k: _truncate(v, max_items) for k, v in value.items()}
    return value


@dataclass
class Evidence:
    """一条证据：工具调用的入参摘要与裁剪后的返回。"""

    eid: str
    tool: str
    args: dict
    data: Any
    ts: float = field(default_factory=time.time)


class EvidenceLedger:
    """证据账本：add 写入并返回 eid，get/all 读取，render_for_prompt 供综合节点。"""

    def __init__(self) -> None:
        self._items: list[Evidence] = []
        self._by_eid: dict[str, Evidence] = {}
        self._counter = 0

    def add(self, tool: str, args: dict, data: Any) -> str:
        """写入一条证据（data 会被裁剪），返回自增 eid。"""
        self._counter += 1
        eid = f"E{self._counter}"
        ev = Evidence(eid=eid, tool=tool, args=_truncate(args), data=_truncate(data))
        self._items.append(ev)
        self._by_eid[eid] = ev
        return eid

    def get(self, eid: str) -> Evidence | None:
        return self._by_eid.get(eid)

    def all(self) -> list[Evidence]:
        return list(self._items)

    def render_for_prompt(self) -> str:
        """给综合节点的紧凑文本：每条以 [eid] tool(args) 开头，随后 data。"""
        if not self._items:
            return "（暂无证据）"
        lines: list[str] = []
        for ev in self._items:
            arg_str = ", ".join(f"{k}={v!r}" for k, v in ev.args.items())
            lines.append(f"[{ev.eid}] {ev.tool}({arg_str})")
            lines.append(f"    {ev.data}")
        return "\n".join(lines)
