# Task Plan：AI 参谋助手（Agentic）+ 阶段 0 前置修复

> 设计依据：[../agent-advisor-plan.md](../agent-advisor-plan.md)（§ 编号均指该文档）
> 配套：[findings.md](findings.md)（发现与决策）、[progress.md](progress.md)（会话日志与测试结果）
> 跟进方式：每完成一个子任务就更新本文件的状态与 progress.md；新会话先读这三份文件再动手。

## Goal
在不改变任何既有匹配结果的前提下修掉 /match 缓存与事件循环阻塞问题，然后按规划分阶段交付
「AI 参谋助手」：邀请制内测、模型可替换（为国内已备案模型留路）、所有结论可溯源。

## Current Phase
Phase 1 MVP — 第四批（前端 + 评测资产）：**代码完成、本地验证通过；未提交**
下一步：配置邀请名单与 EricAI secret 后跑真实模型评测并部署 EWS 灰度

## 已确认的决策（2026-09-15，用户）
| 决策 | 结论 |
|---|---|
| 使用范围（Gate 0） | **邀请制内测**：Agent 放在功能开关 + 登录白名单后面，公开页面不暴露入口 |
| 模型 | **必须可替换**：业务代码只依赖 LangChain `BaseChatModel`，提供方由配置切换（ericai / 国内已备案模型） |
| 开发顺序 | 先修缓存（阶段 0 前置），再做 Agent |
| 进度跟踪 | planning-with-files：本目录三份文件随开发实时更新 |

## Phases

### Phase 0.1：/match 缓存重构（§1.2 第 1 项）
- [x] 采集重构前基线：41 组调用（match / sensitivity / refresh）输出落盘，两次采集逐字节一致
- [x] 采集重构前性能：冷 2.9s、换位次 3.3s、换筛选 3.65s（均未命中）
- [x] 拆分缓存：单元集合按「数据版本 + 类别/学科类/批次/考生年 + cfg」缓存（上限 16）
- [x] 分档、选科排除、偏好筛选每次请求现算（`_classify_units`）
- [x] CPU 段移入线程池（分组统计、选科查找、分档筛选、汇总、敏感度）；同键冷启动单飞
- [x] 缓存建好后 `gc.collect()+gc.freeze()`（实测去掉热请求上百毫秒的 GC 停顿）
- [x] 删除被覆盖的 major_strengths 死查询
- [x] 回归：与「旧代码每次清空缓存」输出比对 39/41 逐字节一致，另 2 组为修复的旧 bug（见 findings）；
      pytest 58 passed（新增 `tests/test_match_cache.py` 6 个）；`etl/smoke_strength.py` golden 契约 ALL PASS
- [x] 记录重构后性能与缓存内存占用（见 progress.md）
- [x] 按 `EWS_DEPLOY_LESSONS.md` 部署 EWS（重建 backend/frontend，无迁移）并在 EWS 复测
- **Status:** 已部署 EWS 并复测通过（与 Phase 0.2 同批上线，commit 230765f）

### Phase 0.1 衍生待办
- [x] 艺术类/体育类不套用普通类位次分档：后端统一返回 `category_unsupported`，前端展示限制说明和历史查询入口

### Phase 0.2：其余前置修复（§1.2）
- [x] 限流（nginx 通用/Agent 预留限流 + 应用层登录/注册防爆破）
- [x] compose 安全（只读 DSN/JWT/CORS 改为部署必填；生产启动强校验；删 `COPY data`；`.dockerignore` 排除 data/.env）
- [x] 后端容器非 root（UID 10001）；部署时仍需对已有用户数据卷执行一次 chown
- [x] 方案体检规则迁到后端（`/plan/analyze`），前端在线调用，网络失败时本地规则只作降级
- [x] 本地全量验证：后端 67 tests、前端 build、diff check、配置 fail-closed、镜像 UID/data 检查通过
- [x] EWS 注入强 JWT、明确 CORS、只读 DSN，执行数据卷 chown；运行 Compose v2 config 与 nginx -t 后部署验证
- **Status:** 已提交（230765f）、已部署 EWS、复测全部通过（health / 限流 429 / category_unsupported / plan/analyze）

### Phase 0.3：模型接入技术验证（§5、§16 阶段 0）
- [ ] 模型工厂：provider 可配置（ericai / openai 兼容的国内模型），业务只拿 BaseChatModel（归 Phase 1，本阶段只验证接法）
- [x] 在 EWS backend 容器内验证：普通对话、json_mode 结构化输出、tools + reasoning none、多工具调用（num_calls=2）、并发 10 请求（无 429）
- [x] AzureChatOpenAI vs ChatOpenAI+httpx.Auth 二选一 → **定 ChatOpenAI+httpx.Auth**（实测网关容忍 base_url 拼到 /chat/completions）
- [x] sol / luna / terra 选型：三个部署均可调；luna 最省 token/最快，sol 输出最完整（Phase 1 默认 sol）
- **Status:** 已完成（2026-09-16，在 EWS 容器内实测六项全过；探针本地/EWS 两份均删；详见 findings.md / progress.md）

### Phase 1：MVP——选校问答 + 单条解读（§16 阶段 1）
分批交付（用户定 1A）：每批停下来等过目。默认 deployment=se-gpt-5.6-sol。

#### 第一批：模型工厂 + 只读工具层 + 证据账本
- [x] `agent/config.py` — Agent 专属配置（仅 env；`AGENT_ENABLED`/`LLM_PROVIDER`/Azure 连接参/`AGENT_DB_PATH`；生产 fail-closed）
- [x] `agent/llm.py` — `make_model(*, node)` 产 `BaseChatModel`（ChatOpenAI + httpx.Auth）；`TokenProvider` 进程内缓存 token（120s 提前刷 + asyncio.Lock）；6 个节点参数；拒 minimal；带 tools 强制 reasoning=none；provider≠ericai raise NotImplementedError
- [x] `agent/evidence.py` — `EvidenceLedger`（eid 自增 E1/E2…、add/get/all/render_for_prompt、长列表截断）
- [x] `agent/contracts.py` — 回答契约（AdvisorAnswer 等）+ 7 个工具入参 schema（Pydantic v2）
- [x] `agent/tools/` — 7 个只读工具（校验→调 service（进程内）→裁剪→写证据）；`build_tools(ledger, profile)`
- [x] `requirements.txt` 补 `azure-identity>=1.19`
- [x] 单测：`tests/agent/test_evidence.py`(7)、`test_llm_factory.py`(8)、`test_tools.py`(12) — 均不走网络/不碰真库
- [x] 验证：`pytest tests/agent/ -q` 27 passed；`pytest tests/ -q` 94 passed（无回退，基线 67）；`make_model`/`build_tools` import 无错
- **Status:** 代码完成、本地验证通过；**未提交**（等用户过目——1A 分批停）

#### 第二批：LangGraph 主图 + 子图 A（选校问答）/ C（单条解读）
- [x] `state.py` — `AgentState`（TypedDict, total=False）；events reducer 追加；新增 `model_failed` channel（synthesize/repair 空答转 fallback）
- [x] `guards.py` — `input_guard`（注入/越界类别）、`verify_answer`（forbidden_phrase/missing_citation/invalid_citation/number_not_traceable/unit_not_in_evidence/status_omitted）、`append_disclaimer`（幂等）
- [x] `graphs/common.py` — synthesize/repair/verify/deliver/fallback 节点；`_verify_route`（repairs<1）；`ModelEmptyError`；`_normalize_answer`
- [x] `graphs/find_options.py`（子图A）/ `graphs/explain.py`（子图C）— 确定性取证（直接调 service，不走模型工具循环）；位次缺失置 clarify
- [x] `graphs/advisor.py` — 主图：guard→load_context→route_intent→{子图/clarify/refuse}→synthesize→verify→{deliver/repair/fallback}；synthesize/repair 包降级捕获
- [x] `prompts/` — ROUTE_INTENT_SYSTEM / CLARIFY_GENERIC / REFUSE_OUT_OF_SCOPE 等；PROMPTS_VERSION=`2026-09-16.1`
- [x] `requirements.txt` 补 `langgraph>=1.2`（本地 1.2.11）
- [x] 单测：`tests/agent/test_graph_fake_model.py`(9) — 假模型驱动全路由分支（guard 短路/位次门禁/正常链路/修复回环/降级/解析失败），不走真模型/不碰真库
- [x] 验证：`pytest tests/agent/ -q` 36 passed（基线 27）；`pytest tests/ -q` 103 passed（基线 94，无回退）
- **Status:** 代码完成、本地验证通过；**未提交**（等用户过目——1A 分批停）

#### 第三批：接口 + 任务存储
- [x] `jobs.py` + 独立 `agent.db`：jobs/events/traces/feedback 表；WAL；启动时将残留 pending/running 标为 failed(restart)；按保留期清理
- [x] `routers/agent.py`：创建 202、按事件序号轮询、软取消、反馈四个接口；Pydantic 限制消息 500 字/历史 6 轮
- [x] Gate 0：`AGENT_ENABLED` + 登录 + allowlist（用户 ID/邮箱/用户名），空白名单 fail closed
- [x] 控制面：同用户单进行中任务复用、30 次/小时、每日 token 预算、每 worker 并发 4、任务 60 秒超时、所有权隔离、用户可见错误脱敏
- [x] 生命周期与部署配置：启动建库/恢复残留任务；`.env.example`、EWS compose 补 Agent 参数与 secret 文件路径
- [x] 测试：新增 `test_jobs.py` 5 个、`test_agent_api.py` 6 个（含真实 ASGI 路由可达性）；Agent 47 passed，全量 114 passed（基线 103，无回退）
- **Status:** 代码完成、本地验证通过；**未提交**（等用户过目——1A 分批停）

#### 第四批：前端 + 评测
- [x] 懒加载桌面 `AdvisorDrawer` + 手机全屏 `/advisor`，共享 `AdvisorPanel`；顶栏登录用户入口与匹配结果“为什么这档”入口
- [x] `useAdvisor.ts`：提交、每秒增量轮询、取消、反馈、本机最多 20 轮历史；退出长期云同步范围
- [x] 安全结构化渲染：结论、分段解释、证据编号展开、推荐单元、注意事项、固定免责声明；不使用 `v-html`
- [x] 匹配解读携带当前单元事实；桌面直接传 page_context，手机用 sessionStorage 跨路由传递
- [x] Phase 1 评测资产 55 条：选校 30 + 解读 15 + 越界/攻击 10；JSON-compatible YAML，无新增生产依赖；静态完整性测试
- [x] 本地验证：后端 115 passed；前端 build 通过；Agent 懒加载 JS 约 4.63KB gzip（Panel 3.67 + Drawer 0.47 + page 0.49），主包入口增量保持目标范围
- [ ] 真实 se-gpt-5.6-sol 跑 55 条评测并按 §13.3 出报告（需要 EricAI 凭证/可访问环境）
- [ ] EWS 白名单部署和 HTTPS 浏览器 E2E（需要部署凭证、allowlist、Azure secret 文件）
- **Status:** 前端与离线评测资产完成；真实模型评测和部署待环境，**未提交**

### Phase 2：方案体检 Agent（§16 阶段 2）
- **Status:** pending

### Phase 3：政策问答（§16 阶段 3）
- **Status:** pending

### Phase 4：灰度、压测与高峰保障（2027-01 至 07）
- **Status:** pending

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| 本机 `docker compose` 不支持 compose 子命令，`docker-compose` v1 又不支持顶层 `name` | 1–2 | 用 YAML 解析和镜像级检查覆盖本地语法/运行验证；EWS 的 Compose v2 部署时再跑 `config` |
| nginx:alpine 拉取 Docker Hub 超时 | 1 | 属外网镜像拉取问题；改用本机已有 nginx/项目镜像或在 EWS 构建时执行 `nginx -t` |
| backend 首次镜像构建 120s 超时 | 1 | pip 首次下载依赖尚未完成；延长构建超时后重试，复用 Docker 层缓存 |
| 第三批首次静态检查发现 `main.py` 路由缩进错误 | 1 | 修正缩进后用 `py_compile` 重跑 |
| 系统 `python3` 未安装 Phase 1 的 LangChain/LangGraph 依赖 | 1 | 按 Phase 1 既有约定改用 `backend/.venv/bin/python` 执行 Agent 测试 |
| FastAPI 0.141 的 `app.routes` 使用 `_IncludedRouter`，旧式直接枚举误判为路径未装配 | 1–3 | OpenAPI 显示四条路径；新增 ASGITransport 请求测试确认 `/api/v1/agent/jobs` 可达并返回预期 401 |
