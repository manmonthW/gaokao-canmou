# Vercel 迁移进展（更新于 2026-10-21 16:10）

**状态：预览环境已部署并验证通过，等待切换正式版。**

- 预览地址：https://gaokao-canmou-c5byndd07-manmonthws-projects.vercel.app（开着 Vercel 部署保护，需要登录 Vercel 才能访问）
- 分支：`agent-advisor/phase0`，最新 commit `1da6d0e`，已推送到 GitHub。`main` 还没动。

## 数据同步（2026-10-21 15:24 从 EWS 导出）

| 数据 | 来源 | 目标 | 校验 |
|---|---|---|---|
| 分析库，26 张表，116MB | EWS `gaokao-ln-db` 容器的 `pg_dump` | Neon `gaokao-canmou-db`（sin1，PG 18） | 26 张表逐行内容指纹和 EWS 一致（统一用 UTC 比对） |
| 用户库：6 个用户 + 6 份存档，0 条回填 | EWS 后端容器的 `/app/data/users.db` | Neon `app` schema | 原 id、密码哈希、存档完整；EWS 签发的 token 在 Vercel 上直接有效 |
| 静态材料：485 个文件，329MB | 本地 `2026allmaterial/`（院校图已裁剪） | Blob `gaokao-canmou-assets`（hkg1，public） | 抽样 10 个文件 sha256 一致；清单已提交为 `backend/asset-manifest.json` |

- 本地备份（`backups/`，已 gitignore，**不进 GitHub**，因为仓库是公开的）：
  - `gaokao_ews_full_20261021_152404.sql`
  - `ews_users_20261021_152404.db`（权限 0600）
  - `ews_rowcounts_20261021_152404.txt`
- Agent 任务库（`agent.db`，24 条任务）没有迁：任务只保留 24 小时，是临时数据。

## Vercel 资源（团队 manmonthws-projects）

- **项目** `gaokao-canmou`（`prj_YMjMiVjtkUAj0Uqc6KblDnbSe7dU`）
  - 连接 GitHub `manmonthW/gaokao-canmou`，Root Directory 为 `webapp`，正式版分支 `main`，函数区域 hkg1。
- **Neon** `gaokao-canmou-db`
  - 两个角色：`gaokao_web_ro`（只读）和 `gaokao_app_rw`（只能访问 `app` schema），权限隔离逐条验证过。
- **Blob** `gaokao-canmou-assets`。
- **环境变量**（production 和 preview 都配了）
  - 敏感类（加密存储）：`GAOKAO_DSN`、`APP_DB_URL`、`JWT_SECRET`（沿用 EWS 的值）、`DEEPSEEK_API_KEY`
  - 其他：`APP_ENV=production`、`LLM_PROVIDER=deepseek`、`AGENT_ENABLED=true`、`AGENT_ALLOWLIST=ekewang`、`AGENT_JOB_TIMEOUT_SECONDS=120`、`ASSET_MANIFEST`、两个连接池上限 = 3、`CORS_ORIGINS=https://gaokao-canmou.vercel.app`
  - Neon 和 Blob 集成会自动注入它们自己的变量（`DATABASE_URL`、`BLOB_READ_WRITE_TOKEN` 等），应用不读这些。
- 本机凭证都在 `~/.config/gaokao-deploy/`（目录 0700，文件 0600），不在仓库里。

## 预览环境验证

- **19 个核心接口的 JSON 和 EWS 线上逐字节一致**，包括：
  - data-status、meta、搜索、专业字典与详情、热门院校、指南、分布图
  - 控制线、冷热趋势、选科要求、院校详情与实力
  - `/match` 智能匹配、`/locate`
- 5 类文件端点 302 跳转到 Blob，下载正常；指南 HTML 页正常。
- SPA 路由回退正常（`/match` 返回 index.html）。
- 登录：密码错误返回 401；用 EWS 签发的 token 能取到用户和全部存档。
- **Agent（DeepSeek）**：发起问答后**完全不轮询**，等 25 秒再查，任务已经 ready：4 个 section、10 个推荐单元，有证据链。说明响应返回后，后台任务没有被冻结。
- 冷启动后首次 `/match` 7.6 秒，其他接口 1–2 秒。EWS 是常驻进程，没有这个开销。

## 部署中修掉的问题（都已提交）

1. `vercel.json`：两个服务都要显式写 `framework`（vite / fastapi），否则构建报 `MULTIPLE_FRAMEWORKS_SERVICE`。
2. 函数包排除了 `.env`、`data/`（本机 SQLite 用户库）、`tests/`、`migrations/`；`maxDuration` 设为 300 秒。
3. **DeepSeek 结构化输出一直 400**：`deepseek-flash` 默认开思考模式，思考模式不接受强制 `tool_choice`。每次回答都悄悄降级成“AI 解读暂不可用”的模板。已加 `thinking: disabled`，测试也覆盖了。
4. **后台任务**：通过 `vercel-cache` 拿到运行时的 `wait_until` 钩子，把 Agent 任务挂上去，函数在返回 202 之后会继续跑完。EWS 上这个钩子不存在，代码直接跳过。
5. `AGENT_JOB_TIMEOUT_SECONDS` 从 60 改为 120（只改了 Vercel 上的配置）。DeepSeek 两次结构化调用约 17 秒，加上冷启动和 SQL 会接近 60 秒的上限。

测试：SQLite 模式 150 passed；PG 模式 13 passed。

## 还没做

1. **切换正式版**（需要确认）：把 `agent-advisor/phase0` 快进合并到 `main`，会自动发布 `gaokao-canmou.vercel.app`。
2. **国内域名**：你自己把域名 CNAME 到 Vercel，然后把域名加进 `CORS_ORIGINS`（目前只有 `*.vercel.app`）。前端和 API 同域时其实不依赖 CORS，但生产配置启动时要求这一项必须明确。
3. **Firewall 限流**：nginx 原来的 `/api/` 10r/s 和 Agent 写请求 10r/m，要在 Vercel 控制台配置；登录/注册已有应用层兜底。
4. **EWS 回退方案**：EWS 继续运行。切换之后 EWS 上新产生的用户数据不会同步到 Neon；正式切换前如果有新注册用户，需要用 `migrate_users.py` 再迁一次（目标表非空时脚本会拒绝执行，需要先清空 app 表）。
5. EWS nginx 的 XFF 追加问题（限流可被绕过），见上一版记录，还没修。

## 费用提醒
Hobby 计划只允许非商业用途。Blob 329MB 加上下载流量、Neon 116MB，都可能超出免费额度。
