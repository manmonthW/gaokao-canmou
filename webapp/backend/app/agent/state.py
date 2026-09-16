"""LangGraph 主图状态（§6.2）。

TypedDict 而非 dataclass：LangGraph 需要可合并的 dict 状态，节点返回部分字段
即可。evidence 不放进状态序列化，而是由运行时持有的 EvidenceLedger 管理（可溯源）；
状态里只带 ledger 引用，避免大对象反复拷贝。
"""
from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from .evidence import EvidenceLedger


def _extend_events(
    left: list[dict[str, Any]] | None, right: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """events 的 reducer：追加而非覆盖，让各节点的进度事件汇聚成一条时间线。"""
    return (left or []) + (right or [])


class AgentState(TypedDict, total=False):
    """一次请求的全部状态。字段与 §6.2 一一对应。"""

    # —— 入口上下文（请求时注入，确定性） ——
    job_id: str
    question: str  # 用户原问
    mode: str  # 问答 / 解读 / 体检 / 政策（入口可预设，也可由 route_intent 确定）
    profile: dict[str, Any]  # 年份/类别/学科类/批次/位次或位次区间/再选科目/偏好
    page_context: dict[str, Any]  # 当前单元 ID / 当前方案
    history: list[dict[str, str]]  # ≤6 轮，前端传入；服务端不存长期对话

    # —— 路由与插槽 ——
    intent: str  # explain_unit / policy_qa / plan_review / find_options / need_clarify / refuse
    slots: dict[str, Any]  # 省份/城市/专业关键词/档位/层次等
    task_spec: dict[str, Any]  # 经原文/profile 验证的当前任务合同
    plan: list[dict[str, Any]]  # 确定性只读工具执行计划
    coverage: list[dict[str, Any]]  # 每个用户要求维度的执行覆盖状态

    # —— 工具循环 ——
    messages: Annotated[list[BaseMessage], add_messages]

    # —— 证据与产出 ——
    ledger: EvidenceLedger  # E1..En，运行时对象（不序列化入检查点）
    draft: dict[str, Any]  # synthesize 产出的 AdvisorAnswer（model_dump）
    issues: list[dict[str, str]]  # 校验发现的问题：{code, detail_zh}

    # —— 预算与预算（§6.3） ——
    tool_rounds: int  # 工具循环轮数（上限 5）
    tool_calls: int  # 单轮对话累计工具调用（上限 8）
    repairs: int  # 修复次数（上限 1）
    usage: dict[str, Any]  # 累计 token / 各节点耗时
    events: Annotated[list[dict[str, Any]], _extend_events]  # 给前端的进度事件

    # —— 交付 ——
    answer: dict[str, Any]  # 最终交付给前端的结果（含程序追加的免责声明）
    clarify: Optional[str]  # need_clarify / rank 缺失时的追问文本，设则本轮提前结束
    model_failed: bool  # synthesize/repair 模型空答/拦截时置位，由路由转 fallback（§8.4）
