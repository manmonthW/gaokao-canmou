# 辽宁志愿参谋 · 本地部署指南

基于本机实测状态整理（2026-07-30）。应用分层：FastAPI 后端（只读 PostgreSQL 16）+ Vue3 前端静态产物。

## 现状核查（部署前必读）

- **PostgreSQL 16 本地集群**：当前默认 `down`，需手动启动。数据目录 `/var/lib/postgresql/16/main`，库名 `gaokao`，10 张表已建好（admission_scores / schools / score_rank / batch_control_line / school_profiles / cities / source_files / raw_texts / data_releases / admission_publication_status），只读账号 `gaokao_web_ro` 可连。
- **后端**：`backend/run.sh` + `backend/.env` 已配好（`.env` 中 `GAOKAO_DSN` 指向只读角色，**禁止用写库 gaokao 拥有者口令**）。
- **前端**：`frontend/dist` 已构建，API 基址**写死为 `http://127.0.0.1:8000`**（来源 `frontend/.env` 的 `VITE_API_BASE` 与 `vite.config.ts` 的 proxy）。
- **端口冲突**：`8000` 目前被另一个项目 `/home/ekewang/eea/.venv/bin/uvicorn` 占用，gaokao 后端若直接起会失败。本机**无 nginx**。

## 部署步骤

### 1. 启动 PostgreSQL（需 sudo，当前未运行）

```bash
sudo pg_ctlcluster 16 main start
pg_isready          # 期望输出 "accepting connections"
```

> 仅本次会话有效；如需开机自启：`sudo systemctl enable postgresql`（系统有 systemd 时）。

### 2. 启动后端（已采用虚拟环境，规避 PEP 668）

本机系统 Python 受 PEP 668 管控，已建好 `backend/.venv` 虚拟环境并装好依赖。`run.sh` 已改为使用 venv，并支持 `PORT` 环境变量覆盖端口。

```bash
cd /home/ekewang/projects/gaokao/ln/webapp/backend
# 首次或依赖变更时：在 venv 内安装
./.venv/bin/pip install -r requirements.txt
chmod +x run.sh
./run.sh                       # 默认 0.0.0.0:8000
# 或指定端口（推荐，避开被占用的 8000）：
PORT=8011 ./run.sh
# 等价于：
PORT=8011 nohup ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8011 >/tmp/gaokao8011.log 2>&1 & disown
```

⚠️ **端口 8000 被另一个项目 `/home/ekewang/eea` 占用**，gaokao 后端默认 8000 会冲突。建议直接用 **8011**（非破坏性，无需动 eea）：

- 后端跑 8011：`PORT=8011 ./run.sh`
- 前端需指向 8011（见步骤 3 的「换端口」说明），即 `VITE_API_BASE=http://127.0.0.1:8011 npm run build`。

若坚持用 8000（方案 A）：先 `ss -ltnp | grep ':8000'` 找到 eea 的 pid 并 `kill` 掉，再 `./run.sh`，前端 dist 无需改动。

### 3. 启动前端（三选一）

```bash
cd /home/ekewang/projects/gaokao/ln/webapp/frontend
npm install            # 首次需安装依赖（node v24 / npm 11 已就绪）

npm run dev            # 开发服务器：http://localhost:5173，经 vite 代理转发 /api → 8000
npm run preview        # 预览构建产物：http://localhost:4173，浏览器直连 dist 中写死的 API 基址
# 或纯静态托管已构建的 dist/
python3 -m http.server 8080 -d dist
```

> **换端口时（如后端用 8011）需重建 dist**，让前端 API 基址对齐：
> ```bash
> VITE_API_BASE=http://127.0.0.1:8011 npm run build
> # 再 npm run preview 或托管 dist/
> ```
> 当前已按此方式构建，dist 内 API 基址已为 `http://127.0.0.1:8011`。

### 4. 验证

```bash
curl -s http://127.0.0.1:8000/api/v1/data-status | head -c 200
# 期望返回当前发布版本等 JSON；浏览器打开前端页面可正常查询即部署成功
```

## 接口一览（统一前缀 /api/v1）

- `GET /data-status` 发布版本 + 待发布批次 + 数据覆盖
- `GET /meta` 筛选枚举
- 定位：`/locate/score-to-rank`、`/locate/rank-to-score`、`/locate/control-line`、`/locate/summary`
- 检索：`/search/schools`、`/search/majors`
- 院校：`/schools/{code}`、`/schools/{code}/major`
- 智能匹配：`GET /match`（年份/类别/学科类/批次/位次必填）
- 方案导出：`POST /plan/export`（前端传方案快照，返回 xlsx；服务端无状态）
- 数据中心：`/datacenter/control-lines`、`/datacenter/score-rank`、`/datacenter/records`、`/datacenter/source-files`、`/datacenter/publication-status`

## 安全与权限

- 后端仅使用只读角色 `gaokao_web_ro`（CONNECT/USAGE/SELECT），与 ETL 的 `gaokao` 拥有者分离。
- 连接串通过 `backend/.env` 的 `GAOKAO_DSN` 注入，不硬编码写库口令（见 `app/config.py`）。
- `MAX_PAGE_SIZE`（默认 500）限制单接口最大返回行数，防止批量抓取拖垮服务。
- `.env` 已纳入 `webapp/.gitignore`，不会入库。

## 持久化（可选）

- PostgreSQL 开机自启：`sudo systemctl enable postgresql`。
- 后端常驻：用 `nohup uvicorn ... &` 或写 systemd unit，避免终端关闭即停。
- 局域网访问：后端已监听 `0.0.0.0`，前端 dev/preview 也可加 `--host 0.0.0.0`；注意 `CORS_ORIGINS` 按需收紧。
