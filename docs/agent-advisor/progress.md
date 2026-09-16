# Progress Log

## Session: 2026-09-15

### 规划
- 完成全面评审（结论见会话记录）与 Agent 实施规划 `docs/agent-advisor-plan.md`
- 用户确认：先修缓存；邀请制内测；模型可替换；用 planning-with-files 跟踪进度
- 建立 `docs/agent-advisor/` 三份跟踪文件

### Phase 0.1：/match 缓存重构
- **Status:** 代码完成、本地验证通过；未提交、未部署 EWS（待用户确认）
- Actions taken:
  - 启动本地 PG16（`sudo pg_ctlcluster 16 main start`）
  - 编写基线采集脚本：41 组调用覆盖 match（各档/各筛选/选科/偏好排序/区间模式/仅分数/无位次/
    专科/提前批别名/艺术类）、sensitivity 3 组、refresh_snapshots 2 组，输出保留键顺序用于逐字节比对；
    同一脚本跑两次逐字节一致 → 输出确定，可做回归基准
  - 重构 `match.py` 管线：`_group_units` / `_attach_subject_reqs` / `_build_units`（缓存段）、
    `_load_units`（缓存 + 单飞 + gc.freeze）、`_classify_units`（请求段）、`_summarize`、
    `_sensitivity_scenarios`；删除 major_strengths 死查询；`_prepare_candidates` 签名与返回值不变
  - 回归比对发现新旧差 2 组 → 追查确认为旧代码 bug（层次筛选被局部变量覆盖）；另发现旧缓存
    原地排序导致结果依赖请求历史 → 改用「旧代码每次清空缓存」作为公平基线再比对
  - 关 GC 对照实验定位剩余停顿来源 → 加 `gc.freeze()`
  - 起真实 uvicorn 做端到端验证；跑项目自带 golden 契约 `etl/smoke_strength.py`
- Files created/modified:
  - `webapp/backend/app/services/match.py`（重构）
  - `webapp/backend/tests/test_match_cache.py`（新增 6 个测试）
  - `docs/agent-advisor/*`、`docs/roadmap.md`（进度登记）

## Test Results
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| 重构前：冷请求 | 物理本科批 rank=30000 | — | 2.9s，事件循环停顿 1.44s | 基线 |
| 重构前：同参换位次 | rank=12000/45000/90000 | 应命中缓存 | 3.7–4.7s（未命中），停顿 1.4–1.9s | 问题复现 |
| 重构前：同参加筛选 | province / city | 应命中缓存 | 3.65–5.0s（未命中） | 问题复现 |
| 重构前：敏感度试算 | rank=33333 | — | 6.0s，停顿 3.1s | 基线 |
| 回归：输出一致性 | 41 组调用 vs 旧代码（每次清空缓存） | 逐字节一致 | 39/41 一致；2 组差异 = 修复的层次筛选 bug（phys_ben_level、art_ben） | ✅ |
| 重构后：冷请求 | 物理本科批 rank=30000 | 事件循环不被卡死 | 2.9–3.1s，最长停顿 157–181ms | ✅ |
| 重构后：换位次（热） | rank=12000/45000/90000 | <1s | 0.26–0.43s，停顿 12–31ms | ✅ |
| 重构后：加筛选（热） | city=沈阳 | <1s | 0.32–0.34s | ✅ |
| 重构后：敏感度试算 | rank=33333 | <1s | 0.36–0.40s，停顿 23–31ms | ✅ |
| 单飞 | 8 个并发冷请求（历史专科批，新键） | 只构建 1 次 | 构建 1 次，无遗留锁 | ✅ |
| 缓存内存 | 物理本科批（最大键） | — | 15,734 单元 ≈ 62MB；全库全部键合计估 ≈120MB（上限 16 键） | 记录 |
| HTTP 端到端：冷请求期间其他接口 | /health ×5、/meta | 不被阻塞 | /health 17–102ms，/meta 0.66s | ✅ |
| HTTP 端到端：热请求 | /match 三个位次、+level、/sensitivity | <1s | 0.37–0.48s；level=本科 → total 15,469 | ✅ |
| pytest | 全量 | 全过 | 58 passed | ✅ |
| golden 契约 | `etl/smoke_strength.py` | 键集合与顺序不变 | ALL PASS（warm 0.30s） | ✅ |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-09-15 | 新旧输出 12 组不一致 | 1 | 结构化 diff 定位：城市 facet 并列项顺序 + 层次筛选总数 + 艺术类条数 |
| 2026-09-15 | 同上 | 2 | 改用「旧代码每次清空缓存」为基线 → 只剩 2 组；确认为旧 bug（findings.md） |

### Phase 0.2：安全与 Agent 服务化前置
- **Status:** 代码完成，本地验证通过；尚未部署 EWS
- Actions taken:
  - 艺术类/体育类在 match/sensitivity/refresh 入口统一拦截，不再套用普通类冲稳保算法；前端显示限制提示；
  - 生产配置强制明确 CORS Origin 和至少 32 字符 JWT secret；compose 改由部署环境注入只读 DSN/JWT/CORS；
  - backend 镜像不再复制本地 data，切换到 UID/GID 10001；`.dockerignore` 排除 data 与 `.env`；
  - nginx 增加通用 API 限流和 Agent 路径预留限流；登录/注册增加应用层滑动窗口限流；
  - 将方案体检确定性规则迁到 `services/plan_analysis.py`，新增 `/api/v1/plan/analyze`；工作台在线使用后端结果，网络故障时本地规则降级。
- Validation:
  - `python3 -m pytest tests/ -q`：67 passed；
  - `npm run build`：通过（保留既有 1.23 MB 主 chunk 警告）；
  - `git diff --check`：通过；
  - 生产配置测试：明确 Origin + 强 JWT 可启动，`CORS=*` 或短 JWT 均按预期拒绝；
  - backend 镜像构建通过，容器 UID/GID 均为 10001，`/app/data` 可写且镜像内不含本地数据库；
  - compose YAML 解析与关键生产环境字段检查通过。本机无 Compose v2，完整 `docker compose config` 留待 EWS；
  - nginx 镜像因 Docker Hub 拉取超时未能本地执行 `nginx -t`，部署前仍需在 EWS 验证。

### Phase 0.1 + 0.2：EWS 部署与复测（2026-09-15）
- **Status:** 已部署 EWS 并复测通过（commit 230765f）
- Actions taken（均通过 `ssh ews`，过滤法律 banner）：
  - rsync 同步 `webapp/backend`、`webapp/frontend`、`docker-compose.ews.yml`（**不带 `--delete`**，防止误删 EWS `webapp/etl/` 67 个 ETL 脚本；本地 `webapp/etl/` 为空）；
  - EWS 新建 `webapp/.env`（600）：生产环境 + 只读 DSN + 明确 CORS Origin + 在 EWS 生成的 64 hex JWT_SECRET（从未进入对话）；旧 token 全部失效（用户确认 token 无问题）；
  - 预飞行：`docker compose config` + 在 `gaokao-ln_default` 网络内 `nginx -t` 均 OK（首次 host-not-found 为容器脱网的 DNS 假告警，限流语法已过）；
  - `docker compose build --no-cache backend frontend`；
  - **关键**：切非 root 后，对已有命名卷 `gaokao-ln_backend_user_data` 执行一次 chown 10001:10001（原 `users.db` 属 root），否则非 root 容器写不了内测用户库；
  - `docker compose up -d --no-deps backend frontend`（**绝不碰 db**）；铛 db 全程 `Up 5 weeks (healthy)` 未动。
- 复测（公网 `https://gaokao-ln.ims.ews.gic.ericsson.se`，自签证书用 `curl -k`）：
  - backend `healthy`（10001 非 root 可写 users.db）、frontend `healthy`；`/health` → 200 `ok`；
  - nginx Agent 层限流：`/api/v1/agent/` 前 4 穿透（404，burst=3+1）、第 5 起 429 ✅；
  - 应用层登录限流：`/api/v1/auth/login` 正确 body 前 10 次 401、第 11 起 429（10/60s）✅；
  - `category_unsupported`：`category=艺术类` 返回限制提示 + `error_code`；`普通类` 正常返回候选✅；
  - `/api/v1/plan/analyze`：空方案 `ok:false`；6 志愿均衡方案 `ok:true`、counts 精确✅。

## Session: 2026-09-16

### Phase 0.3：模型接入技术验证
- **Status:** 已在 EWS 容器内验证通过（六项能力全过）；探针为一次性，验证完本地/EWS 两份均删除
- Actions taken：
  - `webapp/backend/requirements.txt` 新增 `langchain-core>=1`、`langchain-openai>=1`、`httpx>=0.27`（Phase 1 必需的前置）
  - 本地写一次性探针 `probe_ericai_langchain.py`（不入业务代码、不入库，secret 只从挂载文件读、值不打印）
  - 在 EWS `docker compose build --no-cache backend` 重建镜像（含 langchain），`up -d --no-deps backend`（db 未动，Up 5 weeks healthy）
  - 用 `gaokao-ln-backend` 镜像跑一次性 `docker run --rm --network gaokao-ln_default`：secret 只读 bind-mount、Azure 参数 inline，不碰运行中的 backend/db
  - 二选一结论：ChatOpenAI + httpx.Auth（复用 PPT 已上线接法）；实测网关容忍 base_url 拼到 /chat/completions

## Test Results（Phase 0.3）
| Test | Deployment | Expected | Actual | Status |
|------|-----------|----------|--------|--------|
| 普通对话 plain_chat | sol | 非空回答 | ok，1.54s | ✅ |
| JSON 结构化 json_mode | sol | City schema 可解析 | `{city:沈阳, province:辽宁省}`，1.22s | ✅ |
| tools + reasoning_none | sol | 命中工具 | get_rank，1.99s | ✅ |
| 多工具并行 multi_tool | sol | 一次响应多 tool_calls | num_calls=2（get_rank+get_batch），1.54s | ✅ |
| 并发 10 请求 concurrency_10 | sol | 无 429 | 全过，wall 2.24s、p50 1.94s、无 429 | ✅ |
| 选型 sol | sol | 可调 | 2.95s / 162 tok，输出最完整 | ✅ |
| 选型 luna | luna | 可调 | 2.48s / 138 tok，最省/最快 | ✅ |
| 选型 terra | terra | 可调 | 2.43s / 171 tok | ✅ |
