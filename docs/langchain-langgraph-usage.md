# 本项目 LangChain / LangGraph 用法梳理

> 代码范围：`webapp/backend/app/agent/`。本文描述当前实际实现，不是最初方案。

## 1. 一句话结论

本项目没有使用通用 ReAct Agent，而是采用：

- **LangGraph**：编排一个有边界、可验证、最多修复一次的确定性工作流；
- **LangChain**：统一模型接口、结构化输出、消息对象和强类型只读工具；
- **业务代码**：负责权限、输入守卫、取证计划、工具调用、事实校验、降级和免责声明。

即：**模型负责语义，程序负责事实和控制。**

## 2. 目录职责

| 文件 | 职责 |
| --- | --- |
| `agent/graphs/advisor.py` | LangGraph 主图、节点、条件路由 |
| `agent/state.py` | 图状态 `AgentState` 和 reducer |
| `agent/graphs/common.py` | 模型结构化调用、综合、修复、校验、交付、降级 |
| `agent/graphs/find_options.py` | 找院校专业的确定性取证节点 |
| `agent/graphs/explain.py` | 单个院校专业的确定性取证节点 |
| `agent/llm.py` | LangChain `BaseChatModel` 工厂及 EricAI 认证 |
| `agent/tools/__init__.py` | LangChain `StructuredTool` 封装的 7 个只读工具 |
| `agent/harness.py` | 将模型语义结果收敛成受验证、有限的执行计划 |
| `agent/evidence.py` | 证据账本，生成 `E1...En` 引用 |
| `agent/guards.py` | 输入守卫、回答校验、免责声明 |
| `agent/jobs.py` | 图外任务队列、超时、取消、持久化、限流 |
| `tests/agent/` | 假模型图测试、工具测试、任务测试和评测集 |

## 3. LangGraph 的用法

### 3.1 状态图

`agent/graphs/advisor.py` 使用：

```python
from langgraph.graph import END, START, StateGraph

g = StateGraph(AgentState)
g.add_node("guard", guard_node)
g.add_node("route_intent", route_intent_node)
g.add_conditional_edges("route_intent", route_fn, route_map)
return g.compile()
```

实际主流程：

```text
START
  → guard
  → load_context
  → route_intent
  → plan
  → find_options | explain_unit
  → synthesize
  → verify
      ├─ deliver
      ├─ repair → verify（最多一次）
      └─ fallback → deliver
  → END
```

另外，越界、信息不足和拒绝会提前结束。

### 3.2 状态与 reducer

`agent/state.py` 用 `TypedDict` 定义图的共享状态。节点只返回自己修改的部分：

```python
class AgentState(TypedDict, total=False):
    question: str
    profile: dict[str, Any]
    intent: str
    draft: dict[str, Any]
    issues: list[dict[str, str]]
```

两个字段使用 reducer：

- `messages: Annotated[..., add_messages]`：按消息语义合并；
- `events: Annotated[..., _extend_events]`：追加进度事件而不是覆盖。

当前业务流程没有真正依赖 `messages` channel，模型调用主要直接传 `SystemMessage/HumanMessage`。

注意：节点返回的每个 key 都必须在 `AgentState` 中声明。例如 `model_failed` 未声明时 LangGraph 会拒绝更新。

### 3.3 条件边实现控制边界

主要条件路由包括：

- `_guard_route`：守卫不通过立即结束；
- `_intent_route`：只开放 `find_options` 和 `explain_unit`；
- `_collect_route`：取证不完整时不进入模型综合；
- `_synthesize_route`：模型失败直接走确定性降级；
- `_verify_route`：通过、修复或降级三选一。

修复循环由代码限制为 1 次，不存在无限 Agent loop。

### 3.4 图的运行

`agent/jobs.py` 中执行：

```python
graph = build_advisor_graph()
out = await asyncio.wait_for(
    graph.ainvoke(state),
    timeout=remaining,
)
```

LangGraph 图本身当前没有 checkpointer。持久任务状态由图外 SQLite `agent_jobs` 管理；服务重启后未完成任务被标记失败，不会从图中间恢复。

## 4. LangChain 的用法

### 4.1 模型抽象与供应商隔离

`agent/llm.py` 的业务出口是：

```python
def make_model(*, node: str) -> BaseChatModel:
    ...
    return ChatOpenAI(**kwargs)
```

上层只依赖 `BaseChatModel`，当前实现通过 `ChatOpenAI` 的 OpenAI 兼容协议连接 EricAI。OAuth token 由自定义 `httpx.Auth` 注入，密钥只从挂载文件读取。

模型参数按节点集中配置：

- `intent`、`tool_loop`：`reasoning_effort="none"`；
- `synthesize`、`repair`：`reasoning_effort="low"`；
- 每个节点独立配置 token 上限和 timeout；
- SDK 重试限制为 1 次。

### 4.2 消息对象

路由和生成节点使用：

```python
from langchain_core.messages import HumanMessage, SystemMessage

await model.ainvoke([
    SystemMessage(content=system_prompt),
    HumanMessage(content=user_prompt),
])
```

历史对话没有直接转成 LangChain message history，而是作为受限状态进入任务合同，避免把全部历史无差别塞给模型。

### 4.3 结构化输出

综合和修复节点使用 Pydantic 契约 `AdvisorAnswer`：

```python
model = make_model(node=node).with_structured_output(
    AdvisorAnswer,
    method="json_schema",
)
resp = await model.ainvoke(messages)
```

随后仍做二次 `Pydantic` 校验。无内容、网关错误、JSON 解析失败或 schema 不合法统一转换为 `ModelEmptyError`，再由图路由到安全降级。

意图路由目前没有使用 `with_structured_output`，而是手工 `json.loads`；失败时不猜测，转为 `need_clarify`。

### 4.4 强类型工具

`agent/tools/__init__.py` 使用：

```python
StructuredTool.from_function(
    coroutine=func,
    name=name,
    description=desc,
    args_schema=SomePydanticArgs,
)
```

现有 7 个工具全部只读：

1. `locate_rank`
2. `search_candidates`
3. `get_unit_detail`
4. `get_school_profile`
5. `get_major_info`
6. `check_subject_req`
7. `rank_sensitivity`

每个工具遵循：Pydantic 入参校验 → 调内部 service → 写 `EvidenceLedger` → 返回 `{eid, data}`。

当前并未使用 `model.bind_tools()` 或 LangGraph `ToolNode`。工具由确定性节点通过 `tool.ainvoke(args)` 调用，模型不能任意决定工具、次数或参数。这是有意的安全设计，不是缺失实现。

## 5. 一次请求如何流转

以“按辽宁、吉林分别推荐稳档院校专业”为例：

1. `jobs.py` 创建持久任务并做并发、频率、日 token 预算检查；
2. `guard` 拦截提示注入、越界类别等输入；
3. `route_intent` 用 LangChain 模型只判断意图和语义 slots；
4. `harness.py` 仅接受原问题中可验证的值，生成最多 8 步计划；
5. `find_options` 按计划调用 LangChain `StructuredTool`；
6. 工具结果进入证据账本，并记录每个范围的 coverage；
7. `synthesize` 用 `with_structured_output(AdvisorAnswer)` 生成草稿；
8. `verify` 用程序检查引用和事实边界；
9. 不通过则修复一次，再不通过就输出纯证据降级结果；
10. `deliver` 由程序追加免责声明；`jobs.py` 保存答案和证据。

## 6. 当前架构的关键取舍

### 已做得比较好的地方

- 没有为固定业务流程引入自由 ReAct 循环；
- LLM 结果经过 Pydantic、证据引用和业务规则三层约束；
- 工具是窄能力、只读、强类型接口，不暴露 SQL/HTTP/shell；
- 有明确的修复次数、超时、并发、调用步数和安全降级；
- 推荐单元最终从工具证据重建，而不是信任模型生成；
- 使用假模型覆盖主图分支、修复和降级，无需真实供应商即可测试。

### 当前限制

1. **依赖未精确锁版本**：`langchain-core>=1`、`langchain-openai>=1`、`langgraph>=1.2` 可能导致构建漂移，生产部署宜锁定已验证版本。
2. **图每次请求重新 compile**：可在进程初始化时缓存已编译图；目前影响主要是小量开销。
3. **没有 LangGraph checkpoint/resume**：当前短任务和只读 MVP 可接受；若以后加入审批、长任务或写操作，应引入持久 checkpointer 和稳定 `thread_id`。
4. **任务持久化与图状态分离**：SQLite 保存任务终态，但不能恢复到具体图节点。
5. **usage 尚未完整累计**：`jobs.py` 读取 `state["usage"]`，但当前模型节点未系统写入 token usage，日预算数据可能偏低。
6. **意图输出仍手工解析 JSON**：可改成独立 Pydantic schema 的 `with_structured_output`，减少围栏清洗和宽松解析。
7. **没有节点级流式事件**：当前只在任务外层记录 queued/running/ready；如需更细进度，可使用 `astream` 或节点事件写入。
8. **`messages` state channel 当前闲置**：若不准备做图内对话消息累积，可删除以缩小状态；若要使用，则应统一消息策略。
9. **`httpx.AsyncClient` 生命周期**：`make_model()` 每次创建 client，未显式统一关闭；建议复用进程级 client 或在应用 shutdown 时关闭。

## 7. 推荐的改进优先级

### P0：可靠性与成本

- 精确锁定 LangChain/LangGraph 版本并纳入升级测试；
- 从 `AIMessage.usage_metadata` 或回调中累计 token，真正执行日预算；
- 复用 `AsyncClient` 和已编译 graph，避免请求级资源重复创建。

### P1：类型与可观测性

- 为 intent 定义 Pydantic 输出模型并使用 `with_structured_output`；
- 给模型、工具、图节点统一记录 latency、token、失败类别和版本；
- 将已存在的 `agent_traces` 表真正接入节点级 trace。

### P2：仅在需求出现时升级

- 需要跨重启恢复、人工审批或长流程时，再增加 LangGraph checkpointer；
- 只有当真实评测证明固定计划无法覆盖开放式问题时，才考虑有限 `bind_tools + ToolNode` 循环；
- 不建议仅为了“更像 Agent”改成通用 ReAct。

## 8. 常用开发入口

运行 Agent 测试应使用项目虚拟环境：

```bash
cd webapp/backend
.venv/bin/python -m pytest tests/agent -q
```

重点阅读顺序：

```text
state.py
→ graphs/advisor.py
→ graphs/find_options.py / graphs/explain.py
→ graphs/common.py
→ llm.py
→ tools/__init__.py
→ jobs.py
→ tests/agent/test_graph_fake_model.py
```
