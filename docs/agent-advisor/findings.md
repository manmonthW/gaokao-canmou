# Findings & Decisions

## Requirements（用户原话提炼）
- 先修复 /match 缓存问题（2026-09-15 评审 P0-3）
- Agent 功能邀请制内测
- 模型必须可替换，给以后换成国内已备案模型留路
- 用 planning-with-files 辅助开发，进展实时更新进项目，便于后续跟进

## /match 缓存问题（重构前现状，`webapp/backend/app/services/match.py`）
- `_prepare_candidates` 的缓存键 = data_version + 全部入参（含 `rank`、省/市/层次/性质/类型、
  专业关键词、has_both_years、exclude_flags、electives、cfg）。
- 重的部分（主查询 → 按单元分组 → 历史统计 → 标准专业名映射 → 学科评估 → 趋势 → 选科查找）
  与 rank/筛选/再选科目**无关**，却因为键里带了这些参数而每次冷算。
- 每个用户位次不同 → 实际命中率接近 0；每条缓存保存整份候选列表，64 条上限可能占用大量内存。
- 分组、统计、选科查找等 CPU 计算直接跑在 `async def` 里，只有 DB 调用进了线程池 → 冷请求阻塞事件循环。
- `match()` 里 `filtered.sort(...)` 在 risk 为空时会原地排序缓存里的列表（共享可变状态）。
- 860–905 行先查 `major_strengths` 并写入 `major_strength`，912 行立刻清空、改用 eval5 → 死查询。

## 重构中发现并修复的旧 bug（2026-09-15，均有回归证据）
1. **层次筛选静默失效 / 结果被清空**：旧 `_prepare_candidates` 在选科查找循环里写
   `reqs, level, school_known = lookup_reqs(...)`，覆盖了函数参数 `level`（用户的「层次」筛选）。
   `keep()` 实际拿「最后一个单元的选科匹配级别」当层次：为 None 时筛选被忽略
   （物理本科批选「本科」仍返回 15,732 条，正确为 15,469），非 None 时把全部结果筛掉。
2. **艺术类匹配恒为 0 条**：即上条的后果（最后一个单元的匹配级别非空）。修复后按设计返回
   1,159 条「数据不足」（艺术类 2,123 行投档数据仅 5 行有位次）。
3. **结果依赖请求历史**：`match()` 在 risk 为空时原地排序缓存里的列表，之后同键请求的城市 facet
   并列项顺序随之改变（同样参数，冷/热缓存返回不同的字节）。新实现每次请求新建列表。

## 性能根因（实测）
- 旧实现 41 组调用 real 80s / user CPU 72s：耗时几乎全在 Python CPU，且跑在事件循环上
  （单个冷请求让事件循环停顿 1.4–3.1s，期间 /health 等所有接口都无响应）。
- 缓存条目很大（物理本科批 15,734 个单元约 62MB），全量 GC 每次都要重扫，
  关 GC 对照实验：热请求 0.35–0.58s → 0.24–0.31s，停顿 199ms → 31ms 以内 → 采用 `gc.freeze()`。

## 参考资料要点
- EricAI：aigw + SP client_credentials，scope `https://cognitiveservices.azure.com/.default`；
  endpoint 是前缀；带 tools 只能 `reasoning_effort=none`；5.6 不支持 `minimal`；空答当错误。
- PPT 项目：`create_chat_model()` 已支持 ericai / DeepSeek 两种 provider（可替换的先例）。

## Phase 0.3：模型接入技术验证（2026-09-16，在 EWS 容器内实测）
验证方式：本地写一次性探针脚本（不入业务代码、不入库）→ rsync 到 EWS /tmp → 用
`gaokao-ln-backend` 镜像跑一次性 `docker run --rm`（secret 只读 bind-mount、Azure 参数 inline，
**不碰运行中的 backend/db**）→ 验证完本地与 EWS 两份探针均删除。

**二选一已定：ChatOpenAI + httpx.Auth（非 AzureChatOpenAI）**——直接复用 PPT 项目已上线的接法。
base_url 拼到 `.../openai/deployments/{dep}/chat/completions`，`default_query={api-version}`，
token 由 `httpx.Auth.async_auth_flow` 注入 `Authorization: Bearer`。**实测确认网关容忍这种
路径形状**（无双拼接 404）。scope = `https://cognitiveservices.azure.com/.default`。

EWS 上的连接参数（从 `docker inspect nir-report-api` 确认，与设计文档一致）：
- endpoint `https://dev.eu.aigw.ericsson.net/v1/generativeai-model/azure/text`
- api_version `2024-12-01-preview`；tenant `92e84ceb-...`；client_id `1441db31-...`
- secret 挂载 `/var/lib/nir-report-secrets/azure-client-secret → /run/secrets/azure-client-secret`（0400/UID 10001）

六项能力探针结果（deployment=se-gpt-5.6-sol，reasoning_effort=none）：
| 能力 | 结果 | 延迟 |
|---|---|---|
| 普通对话 plain_chat | ✅ | 1.54s |
| JSON 结构化 json_mode（City schema） | ✅ 解析 `{city:沈阳, province:辽宁省}` | 1.22s |
| tools + reasoning_none（单工具 get_rank） | ✅ 命中 get_rank | 1.99s |
| 多工具并行 multi_tool | ✅ **num_calls=2**，一次响应同时返回 get_rank+get_batch | 1.54s |
| 并发 10 请求 concurrency_10 | ✅ 全部成功，wall 2.24s、p50 1.94s、**无 429** | — |
| sol/luna/terra 选型 shortlist | ✅ 三个部署均可调 | 见下 |

sol/luna/terra 同一问题对比（用三句话解释平行/顺序志愿区别）：
- **luna**：2.48s / 138 tok——最省 token、最快
- **terra**：2.43s / 171 tok
- **sol**：2.95s / 162 tok——输出最完整
选型候选：默认 sol（与 nir-report / 设计文档一致，输出最充实）；若后续对延迟/成本敏感可切 luna。

## Phase 1 第一批：模型工厂 + 只读工具层 + 证据账本（2026-09-16）
本批只落地三块地基（后续图层/接口/前端的共同依赖），单独验证，不走真实模型/不碰真库。

实现要点：
- **`make_model(*, node)`**：6 个节点参数（intent/tool_loop/synthesize/repair/single_read/policy_qa）。带 tools 的节点（intent/tool_loop）强制 `reasoning_effort=none`；绝不传 `minimal`（人为注入会 raise ValueError）；只用 `max_completion_tokens`；`max_retries=1`。
- **secret 只从文件读**：`AZURE_CLIENT_SECRET_FILE`（默认 `/run/secrets/azure-client-secret`），`_read_secret()` 去空白；值不入配置/日志。token 进程内缓存、120s 提前刷、asyncio.Lock 双重检查防并发刷。
- **provider 切换**：`LLM_PROVIDER != ericai` 现阶段 raise NotImplementedError（留路 deepseek/qwen，不阻塞本批）。
- **工具四步**：Pydantic 校验入参 → 调已有 service（进程内、无 HTTP、不暴露 SQL）→ EvidenceLedger 写入时内置裁剪 → 返 `{eid, data}`。`check_subject_req` 的 subject_requirements 行仅依年份内联 `db.fetch_all`（与 match.py 一致，无 `match.load_subject_reqs`）。

验证：`pytest tests/agent/ -q` 27 passed；`pytest tests/ -q` 94 passed（基线 67，无回退）。

## Phase 1 第二批：LangGraph 主图 + 子图 A/C（2026-09-16）
实现要点：
- **模型只做语义，程序做确定性**：route_intent 只分类、synthesize/repair 只写解读；guard/取证/verify/降级/免责声明均由程序确定性控。
- **子图 A/C 不走模型工具循环**（决策 3A）：避开网关 tools+reasoning 不稳，改为确定性取证（直接调 service + 写 ledger）；结构化合成集中在主图 synthesize_node。
- **位次门禁**：find_options 无 rank 也无 score 时，子图置 clarify 短路 END（不猜位次）。
- **修复预算**：`_MAX_REPAIRS=1`，由 `_verify_route` 把关（repairs<1 才 repair，否则 fallback）。

**坑：LangGraph 拒绝返回未声明为 channel 的 state key**——guarded 节点返回 `{"model_failed": True}` 时，必须先在 `AgentState` TypedDict 里声明 `model_failed: bool` channel，否则运行时报错。已补进 state.py。

**坑：`langgraph.__version__` 不存在**——查版本用 `pip show langgraph | grep -i version`（本地 1.2.11），不要 `import langgraph; langgraph.__version__`。

假模型测试要点：`make_model` 在 advisor.py 与 common.py 两处都是模块级 import，测试需 monkeypatch 两处引用，共享同一个 `_FakeModel` 实例（intent→synthesize→repair 按调用顺序消费同一回答队列）。

验证：`pytest tests/agent/ -q` 36 passed（基线 27）；`pytest tests/ -q` 103 passed（基线 94，无回退）。

## Phase 1 第三批：接口 + 任务存储（2026-09-16）
实现要点：
- **任务状态持久化而非内存表**：`agent.db` 存 job/event/trace/feedback，轮询可跨 worker；进程重启后未完成任务明确终止为 `failed(restart)`，不伪装继续执行。
- **最小后台执行模型**：POST 先落库再 `asyncio.create_task`；每 worker 信号量 4，60 秒硬超时。同用户已有 pending/running 时返回原任务，避免重复花费。
- **邀请制 fail closed**：必须同时满足 `AGENT_ENABLED=true`、已登录、用户 ID/邮箱/用户名命中 `AGENT_ALLOWLIST`；空白名单不开放任何用户。
- **所有权隔离**：轮询、取消、反馈全部带 `user_id` 查询，不允许通过 job_id 读取他人结果；持久错误只存安全分类与用户可见文案，不写原始异常。
- **取消语义**：pending 立即 cancelled；running 设置 `cancel_requested`，当前 LangGraph 调用结束后丢弃结果并标记 cancelled。当前版本不支持节点中途强杀或重启续跑，符合只读 MVP，但部署前需要在 UX 中说明。

验证：`pytest tests/agent/ -q` 47 passed（基线 36）；`pytest tests/ -q` 114 passed（基线 103，无回退）；OpenAPI 与 ASGITransport 请求均确认四条 Agent 路由可达。FastAPI 0.141 在 `app.routes` 中以 `_IncludedRouter` 保存 include 分支，不能再用旧版“逐项找 APIRoute”的方式判定是否装配。

## Phase 1 第四批：前端 + 评测资产（2026-09-16）
实现与决策：
- **上下文入口而非孤立聊天框**：顶栏支持自由问答；匹配行直接携带该单元的代码、档位、`risk_reason` 和历年位次，避免模型猜用户指的是哪一行。
- **一个状态层，两种交付形态**：桌面为右侧抽屉，手机为 `/advisor` 全屏页，二者复用 `useAdvisor` 和 `AdvisorPanel`；Agent 组件动态导入，独立 JS 约 4.63KB gzip。
- **结构化安全渲染**：回答、推荐单元和证据全部逐字段渲染；证据编号展开显示确定性工具返回，不使用 `v-html`。聊天摘要仅保留在 `ln-zhiyuan-advisor`，最多 20 轮，不加入账号云同步。
- **前端不复制白名单**：登录后显示入口，但真正授权仍由后端 `AGENT_ENABLED + allowlist` 决定；未邀请用户收到明确 403，避免白名单规则在两个端漂移。
- **评测资产先可离线验收**：55 条用 JSON-compatible YAML 保存，标准库即可检查，不为测试向生产 requirements 增加 PyYAML。真实模型评分仍必须在 EricAI 环境执行后才能宣称达到上线门槛。

验证：后端 `115 passed`；前端 build 通过；选校 30 + 解读 15 + 越界/攻击 10 共 55 条，ID 唯一且断言结构完整。真实模型质量门槛与 EWS HTTPS E2E 尚未执行。

## Phase 1 真实模型与 EWS 验收结论（2026-09-16）
- **原生 structured output 可用**：EricAI `se-gpt-5.6-sol` 可使用 `with_structured_output(..., method="json_schema")` 直接满足严格 `AdvisorAnswer` 契约；未知/截断/空响应仍必须统一走确定性安全降级，不能猜网关响应字段。
- **推荐集合必须由证据决定**：模型只写解释，`find_options` 的 `recommended_units` 从 `search_candidates` 证据账本确定性投影。否则即使单次答案正确，同题五次的模型选取仍会漂移。
- **模型 slots 不能直接成为严格检索条件**：同一句“辽宁省内稳档”可被模型抽成 `province=辽宁省内`、`risk=稳档` 等服务不支持的值，导致候选为空。可选筛选只接受可信结构化 profile；模型 slots 保留为语义提示，不下推到确定性匹配服务。
- **稳定性采用严格交并比**：五次推荐集合的共同交集除以总并集，而非宽松的平均两两重合。最终实测 100%。
- **序列化边界要覆盖数据库类型**：match 证据包含 PostgreSQL `Decimal`，标准库 `json.dumps` 会在任务完成落库时失败。任务持久化统一先过 FastAPI `jsonable_encoder`，测试覆盖 Decimal，正式域名复测成功。
- §13.3 最终结果：55/55；意图/工具/拒答均 100%；降级 0%；数字溯源违规 0；P95 24.20s；五次稳定性 100%。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 工厂测试异步用例改 `asyncio.run`（不引 pytest-asyncio） | `.venv` 未装 pytest-asyncio，且现有套件（test_locate 等）统一用 `asyncio.run`；保持一致、不新增测试依赖 |
| 工具层 profile 回退不强制（显式入参优先） | `_pick` 仅在入参未给时回退到考生上下文，减少模型重复传参；不遮蔽模型明确指定的值 |
| 三份跟踪文件放 `docs/agent-advisor/` | 与规划文档归在一起，不污染仓库根目录 |
| 缓存键 = (data_version, 类别, 学科类, 批次, 考生年, cfg) | 这是重计算真正依赖的全部输入；热点键仅个位数，命中率从≈0 变为≈100% |
| 选科查找结果随单元缓存（私有键 `_xk`），排除逻辑每次现算 | 查找只依赖院校名/专业名/学科类；再选科目是用户私有输入 |
| 返回值契约不变（`_prepare_candidates` 签名与五元组） | match / sensitivity / refresh 三个调用方零改动，降低回归面 |
| 保留旧库降级分支（schema_missing） | 本次只修缓存，不扩大改动；迁移体系改造另排期 |
| `gc.freeze()` 放在缓存建好之后 | 有对照实验支撑；单元数据无循环引用，淘汰后照常由引用计数释放 |
| 方案体检以后端 `plan_analysis.py` 为在线权威 | Agent 与工作台必须共用确定性规则；前端旧实现暂留作断网降级，后续稳定后可删除 |
| 生产配置 fail closed | `APP_ENV=production` 时拒绝 `CORS=*` 和弱 JWT，避免部署遗漏静默上线 |
| Phase 0 只预留 nginx Agent 限流 | Agent 接口尚未创建；Phase 1 还需按登录用户做任务/Token 级限流与全局预算 |
| 模型接入用 ChatOpenAI + httpx.Auth（非 AzureChatOpenAI） | 复用 PPT 已上线接法；实测网关容忍 base_url 拼到 /chat/completions，六项能力全通 |
| Phase 1 默认 deployment=se-gpt-5.6-sol | 与 nir-report/设计文档一致，输出最完整；luna 最省 token/最快，延迟敏感时可切 |
| 子图 A/C 确定性取证而非模型工具循环（决策 3A） | 网关对 tools+reasoning 不稳；直接调 service 取证可控可溯，把模型变量限在 route_intent 分类与 synthesize 写解读两处 |
| 主图而非单个大节点 | 确定性编排便于逐段降级与单测；synthesize/repair 包降级捕获（model_failed channel）使空答/拦截可路由到 fallback，不抛到调用端 |
| Agent 任务先用 SQLite + 进程内执行 | 单机邀请制 MVP 的最小可靠闭环；状态和轮询持久化，重启明确失败，不使用会跨 worker 丢失的内存任务表；容量增长后再换外部队列 |
| 空 allowlist 默认拒绝全部用户 | 邀请制必须 fail closed，避免只开 `AGENT_ENABLED` 就误向所有登录用户开放 |
| 推荐单元从证据账本确定性投影 | 推荐事实不能由生成模型增删；同时满足可溯源和同题稳定性门槛 |
| 模型生成 slots 不直接下推检索 | 自由文本值可能漂移或不符合 service 枚举；只信任结构化 profile 作为可选筛选来源 |
| Phase 1.1 采用 bounded workflow 而非自由 ReAct | 招生事实需要确定性和可追溯；吸收 Claude Code harness 的目标保持、计划、工具反馈、完成判断和分层修复，但不给模型任意 SQL/事实/无限循环权限 |
| `TaskSpec` 同时保存 validated constraints 与 semantic_slots | 原文/profile 可验证约束用于工具执行；模型 slots 保留语义信息供解释/澄清，避免既丢失理解又把幻觉下推数据库 |
| `empty` 是已完成，`not_run/failed` 是未完成 | “查过但没有结果”可以诚实回答；“根本没查/工具失败”必须作为部分结果或补查，不能由模型措辞掩盖 |
| Completion verifier 先于生成质量 verifier | 缺证据属于执行层错误，不能靠 repair 重写；只有引用、措辞、结构问题才进入 answer repair |
| Phase 1.2 继续使用条件工作流，不升级自由 ReAct | 城市/专业/层次/比较都能映射到现有只读 `search_candidates`；只需确定性验证、bounded fan-out 和一次 history replan，开放工具循环不会增加事实正确性 |
| 多维请求只按一个主维度 fan-out | 所有维度笛卡尔积会快速超过 8 次工具预算；按用户显式“分别/比较”或首个多值维度拆步，其余值作为共同约束，既保留目标又控制成本 |
| history 只恢复用户原问，不恢复助手结论 | 助手摘要可能压缩或遗漏条件，不能成为执行事实；最近一条可识别的用户选校任务只作为基础文本，与当前短跟进合并后重新走验证器 |
| 短跟进区分扩展与替换 | “那大连呢/再看大连”保留旧目标形成比较；“改成/换成大连”只覆盖当前明确提及的维度，其余基础约束继续继承 |
| `985/211/双一流` 不作为 `level` 下推 | match 服务对 `level` 做精确值比较，品牌标签不是同一枚举；误下推会产生假空结果，因此在专门筛选能力接入前明确追问 |
| 超预算目标必须澄清而非截断 | 静默取前 8 个会造成 coverage 合同遗漏；目标数超过 `MAX_PLAN_STEPS` 时要求用户缩小范围 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|

## Resources
- 规划：`docs/agent-advisor-plan.md`
- PPT 项目 LLM 客户端：`~/projects/ai-ppt-generator/backend/app/llm/client.py`
- GPT-5.6 直连：`~/ericsson-ai/gpt56_direct.py`
- EWS 部署经验：`webapp/docs/EWS_DEPLOY_LESSONS.md`（不入库）
