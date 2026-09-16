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

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
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

## Issues Encountered
| Issue | Resolution |
|-------|------------|

## Resources
- 规划：`docs/agent-advisor-plan.md`
- PPT 项目 LLM 客户端：`~/projects/ai-ppt-generator/backend/app/llm/client.py`
- GPT-5.6 直连：`~/ericsson-ai/gpt56_direct.py`
- EWS 部署经验：`webapp/docs/EWS_DEPLOY_LESSONS.md`（不入库）
