# Task Plan：AI 参谋助手（Agentic）+ 阶段 0 前置修复

> 设计依据：[../agent-advisor-plan.md](../agent-advisor-plan.md)（§ 编号均指该文档）
> 配套：[findings.md](findings.md)（发现与决策）、[progress.md](progress.md)（会话日志与测试结果）
> 跟进方式：每完成一个子任务就更新本文件的状态与 progress.md；新会话先读这三份文件再动手。

## Goal
在不改变任何既有匹配结果的前提下修掉 /match 缓存与事件循环阻塞问题，然后按规划分阶段交付
「AI 参谋助手」：邀请制内测、模型可替换（为国内已备案模型留路）、所有结论可溯源。

## Current Phase
Phase 0.3 — 模型接入技术验证：**已在 EWS 容器内验证通过（六项能力全过，探针已删）**
下一步：进入 Phase 1 MVP（选校问答 + 单条解读）

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
- **Status:** pending

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
