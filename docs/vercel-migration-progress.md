# Vercel 迁移进展（更新于 2026-10-21 下午）

目标：通过 GitHub 自动把应用部署到 Vercel，数据库也放到 Vercel 上对应的服务（Marketplace 开通的 Neon Postgres，图片和 PDF 放 Vercel Blob）。

## 已定的决策

1. **国内访问**：由用户自己把国内域名指到 Vercel。
2. **AI 模型**：从 EricAI 换成 DeepSeek，走 OpenAI 兼容接口，`base_url=https://api.deepseek.com`，模型 `deepseek-flash`。API key 由用户提供，只放在环境变量里，不写进代码。
3. **项目结构**：一个 Vercel 项目，用 Services 方式部署。根目录设为 `webapp`，前端（Vite 静态站）和后端（FastAPI）各是一个服务，`/api/*` 路由给后端。推到 `main` 自动发布正式版，其他分支和 PR 自动生成预览版。
4. **两种部署并存**：每项改动都有开关，不设就是原来的行为，EWS 部署和现有测试不受影响。
   - `APP_DB_URL`：设了用 Postgres，没设用 SQLite。
   - `ASSET_MANIFEST`：设了文件走 Blob 302 跳转，没设读本地 `2026allmaterial/`。
5. **Neon 上两个角色**（`scripts/neon/roles.sql`）
   - `gaokao_web_ro`：只读 `public` 下的分析表，会话强制只读，对应 `GAOKAO_DSN`。
   - `gaokao_app_rw`：只拥有 `app` schema（用户、任务、限流），读不到分析表，对应 `APP_DB_URL`。
   - 只读角色读不到 `app.users` 里的密码哈希。

## 已完成（都还没提交，在分支 `agent-advisor/phase0` 的工作区里）

| 项 | 内容 | 文件 |
|---|---|---|
| DeepSeek | 上午完成，见 git diff | `agent/config.py`、`agent/llm.py`、`agent/graphs/common.py` |
| 可写库支持 PG | 上午完成 | `app/sqlstore.py`、`user_db.py`、`agent/jobs.py` |
| 1. PG 模式实测 | ✅ 见下方验证 | `tests/test_sqlstore_pg.py` |
| 2. 连接池 | 两个池的上限都可配（`GAOKAO_DB_POOL_MAX` 默认 12，`APP_DB_POOL_MAX` 默认 3）；池满时排队等待（psycopg2 原本直接抛错）；连接空闲超过 60 秒，取出前先探活，断了就重连（应对 Neon 空闲挂起） | `sqlstore.make_blocking_pool`、`db.py` |
| 3. vercel.json | `web`（frontend/，SPA 回退到 index.html）+ `api`（backend/，`app.main:app`）；`/api/*` 和 `/health` 走后端 | `webapp/vercel.json` |
| 4. Blob | 5 个路由在 Blob 模式下改成 302 跳转，文件是否存在、大小都从清单读；院校图上传前先裁剪好，和线上返回的一致；`GUIDE_HTML_DIR` 默认路径改成相对 `backend/` 推算（Vercel 上只有 backend/） | `app/assets.py`、5 个 router、`scripts/blob/` |
| 5. 限流 | PG 模式下登录/注册限流的计数存进 `app.rate_limit_hits`，多实例共享；SQLite 模式还是内存计数 | `app/rate_limit.py` |
| 7. Neon 导入 | 导入脚本 + 角色脚本 + 用户迁移脚本 | `scripts/neon/` |

### 验证情况
- ✅ SQLite 模式：149 passed（`.venv/bin/python -m pytest tests -q`），PG 和 Blob 用例在未配置时会跳过。
- ✅ PG 模式：13 passed（`TEST_APP_DB_URL=... pytest tests/test_sqlstore_pg.py`），用的是本机临时 PG 16，覆盖：
  - 注册、登录、存档、回填
  - 任务的生命周期、取消、反馈
  - 多实例冷启动并发建表
  - 重新建表不误伤正在跑的任务
  - 池满时排队
  - 连接被服务端断开后重连
  - 跨实例共享限流
- ✅ PG 模式下用 TestClient 走真实 HTTP 路由（注册 → 重复注册 409 → 登录 → me → 存档 → 回填）。不触发 lifespan，首次访问时会自动建表。
- ✅ 以 `gaokao_app_rw` 角色、`search_path=app` 再跑一遍 PG 用例，13 passed。ro/rw 的权限隔离逐条确认过。
- ✅ Blob 模式：`tests/test_assets_blob.py`，外加用全量 485 个文件的清单走 HTTP，16 个 PDF、31 张分布图、12 个组合图都显示可用，跳转正常。本地模式没有回归。
- ✅ `prepare_assets.py` 对真实材料跑通：485 个文件，328.8 MB，没有缺文件，耗时约 70 秒。
- ✅ `import.sh` 对临时库跑通（用非超级用户的 owner，模拟 Neon）。
- ✅ `migrate_users.py` 对 users.db 的副本跑通：6 个用户、19 条回填；保留原 id 和密码哈希；新注册的 id 接着往后排；重复执行会被拒绝。
- ✅ 前端 `vite build` 通过。
- ❌ 没有真实部署过：Vercel、Neon、Blob 都还没开通，`vercel.json` 只做了格式检查。

## ⚠️ 发现的问题

1. **备份不完整，不能直接用。** `backups/gaokao_backup_20260811_090348.sql` 导出时，迁移 0014–0017 和对应的 ETL 都还没执行，缺这 7 张表：
   - `major_admission_summary`、`major_name_map`、`major_eval_map`
   - `major_strengths`、`school_disciplines`
   - `major_trend`、`major_trend_alias`

   也缺 `school_profiles.strength_tags` 列。用它导入，专业字典、学科实力、冷热趋势会显示为空，或走 `schema_missing` 降级。
   **处理办法**：在当前正式库（EWS 上的 gaokao 库）重新导一份完整备份：`pg_dump -F p --no-owner --no-privileges --clean --if-exists`。本机 5432 上的 PG 没在运行，我这边导不了。
2. **EWS 的限流可以被绕过（原来就有的问题，这次没改）。** nginx 用的是 `$proxy_add_x_forwarded_for`，它是往后追加，不是覆盖，客户端伪造 XFF 的第一跳就能绕过登录限流。改法：`proxy_set_header X-Forwarded-For $remote_addr;`。Vercel 会覆盖这个头，不受影响。

## 剩下的工作

需要用户操作或提供凭证的标 👤。

1. 👤 **重新导出完整的分析库**（见上面问题 1）。
2. 👤 **开通 Neon**：通过 Vercel Marketplace 开通，区域选新加坡。
   - 导入：`NEON_OWNER_URL=<直连串> RO_PASSWORD=... RW_PASSWORD=... webapp/scripts/neon/import.sh <完整 dump>`，最后输出的检查表里不能有“缺表”或 0。
   - 用户迁移：`APP_DB_URL=<rw 的 pooler 串> .venv/bin/python ../scripts/neon/migrate_users.py data/users.db`，建议先加 `--dry-run` 跑一遍。迁的应该是 EWS 容器卷里的 users.db，不是本机这份。
3. 👤 **开通 Blob 并上传**
   ```bash
   cd webapp/backend && .venv/bin/python ../scripts/blob/prepare_assets.py ../../2026allmaterial /tmp/blob-staging
   cd ../scripts/blob && npm ci && BLOB_READ_WRITE_TOKEN=... node upload.mjs /tmp/blob-staging ../../backend/asset-manifest.json
   ```
   然后提交 `backend/asset-manifest.json`，在 Vercel 上设 `ASSET_MANIFEST=asset-manifest.json`。清单里只有公开文件的 URL，没有密钥，可以入库。
4. 👤 **配置 Vercel**
   - 导入 GitHub 仓库 `manmonthW/gaokao-canmou`，Root Directory 设为 `webapp`，正式版分支设为 `main`，函数区域设为 `hkg1`。
   - 正式版和预览版分开配环境变量：
     - 数据库：`GAOKAO_DSN`（ro，pooler 串，加 `?sslmode=require`）、`APP_DB_URL`（rw，pooler 串）、`GAOKAO_DB_POOL_MAX=3`
     - 应用：`JWT_SECRET`（沿用 EWS 上的值，已登录用户就不会掉线）、`CORS_ORIGINS`、`APP_ENV=production`、`ASSET_MANIFEST`
     - Agent：`LLM_PROVIDER=deepseek`、`DEEPSEEK_API_KEY`、`AGENT_ENABLED`、`AGENT_ALLOWLIST`
   - 打开 Neon 的“每个预览部署建一个数据库分支”功能。
5. **在预览环境实测**（代码改不了，只能上环境看）
   - Python 运行时能否识别 `entrypoint: app.main:app`；如果不识别，就在 `backend/pyproject.toml` 加 `[tool.vercel] entrypoint`。
   - **Agent 后台任务**：`jobs.create` 用 `asyncio.create_task` 在响应返回后继续跑。Vercel Python SDK 没有 `wait_until`，函数在响应发出后可能被挂起。实测方法：发起一次问答后轮询，看状态能不能走到 ready。走不到就要改用 Vercel Queues / Workflow，是比较大的改动。
   - 函数包大小：`backend/` 下只有代码、`static/guides`（476K）和清单，应该远低于 500MB。
6. **限流（Vercel Firewall）**：nginx 原来的 `/api/` 10r/s 和 `/api/v1/agent/` 写请求 10r/m，要在 Vercel 控制台 Firewall → Rate Limiting 里配。登录/注册已由应用层用 PG 共享计数兜底。
7. **正式切换**：确认预览环境没问题后，提交并快进合并到 `main`。EWS 那套先保留，作为回退方案。

## 费用提醒
Vercel 的 Hobby 计划只允许非商业用途。Blob 实际要存 329MB，加上图片和 PDF 的下载流量，Blob 和 Neon 都可能超出免费额度。院校图走 Blob 后不再经过函数，函数调用量会比 EWS 时少。
