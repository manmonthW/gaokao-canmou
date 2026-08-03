# 辽宁志愿参谋 · Web 应用

基于辽宁省往年高考录取数据，帮助考生完成「定位位次 → 发现院校专业 → 比较 → 形成志愿草案」的决策辅助工具。
产品/设计基线见 [`ln/docs/product-plan.md`](../../docs/product-plan.md) 与 [`ln/docs/development-spec.md`](../../docs/development-spec.md)。

> 当前进度：**Phase 0 — 数据可信化 + 工程基座已完成；Phase 1 — 只读查询基础已完成**。
> 所有结论仅作参考，最终以辽宁省招考部门及院校官方信息为准。

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI + psycopg2（连接池）+ PostgreSQL 16（**只读账号** `gaokao_web_ro`） |
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + ECharts |
| 部署 | 后端 `uvicorn`（本机/局域网）；前端 `vite build` 静态产物 |

## 目录结构

```
webapp/
  backend/
    app/
      config.py          # 仅从环境变量读取 DSN，禁止硬编码写库口令
      db.py              # psycopg2 连接池 + 线程池异步包装
      schemas.py         # pydantic 响应模型
      routers/           # data-status, meta, locate, search, schools, datacenter
      services/          # 数据访问逻辑
      main.py            # FastAPI 入口（CORS）
    migrations/
      0000_role.sql      # 创建只读角色（以 postgres 超级用户执行）
      0001_phase0_tables.sql  # data_releases / admission_publication_status
      0002_seed.sql     # 固化数据版本与批次发布状态
      0003_grants.sql   # 补齐只读角色 SELECT 权限（以 gaokao 执行）
      0004_indexes.sql  # Phase 1 查询性能索引
    quality_report.py    # 生成数据质量与发布状态报告
    requirements.txt
    .env.example / .env  # .env 不入库
    run.sh
  frontend/
    src/
      styles/tokens.css  # 设计 Token（基于 Stripe 适配：可信蓝 / 等宽数字 / 中文栈）
      api/client.ts
      views/DataStatus.vue
      ...
```

## 快速开始

### 1. 数据库（仅需一次）

```bash
# 只读角色（postgres 超级用户）
sudo -u postgres psql -d gaokao -f backend/migrations/0000_role.sql
# 表 + 种子 + 权限（gaokao 拥有者）
export PGPASSWORD=gaokao123
psql -U gaokao -h localhost -d gaokao -f backend/migrations/0001_phase0_tables.sql
psql -U gaokao -h localhost -d gaokao -f backend/migrations/0002_seed.sql
psql -U gaokao -h localhost -d gaokao -f backend/migrations/0003_grants.sql
psql -U gaokao -h localhost -d gaokao -f backend/migrations/0004_indexes.sql
```

### 2. 后端

```bash
cd backend
cp .env.example .env        # 填入只读连接串
pip install -r requirements.txt
./run.sh                    # 监听 0.0.0.0:8000，热重载
# 或：python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

接口（已就绪，统一前缀 `/api/v1`）：
- `GET /api/v1/data-status` — 当前发布版本 + 待发布批次 + 数据覆盖
- `GET /api/v1/meta` — 筛选枚举（年份/科类/学科类/批次/层次/性质/类型/省份）
- 定位：`GET /api/v1/locate/score-to-rank`、`/rank-to-score`、`/control-line`、`/summary`
- 检索：`GET /api/v1/search/schools`、`/search/majors`
- 院校：`GET /api/v1/schools/{code}`、`/api/v1/schools/{code}/major`
- 智能匹配：`GET /api/v1/match`（年份/类别/学科类/批次/位次必填，支持省/市/层次/性质/类型/专业关键词/`has_both_years`/`risk` 过滤与分页）
- 方案导出：`POST /api/v1/plan/export`（前端传方案快照，返回对齐辽宁「专业+学校」平行志愿列结构的 xlsx；服务端无状态）
- 数据中心：`GET /api/v1/datacenter/control-lines`、`/score-rank`、`/records`、`/source-files`、`/publication-status`

### 测试

```bash
cd backend
pip install pytest --break-system-packages   # 系统 Python 受 PEP668 限制时需此参数
python3 -m pytest tests/ -q
```

### 3. 前端

```bash
cd frontend
npm install
npm run dev        # 开发：http://localhost:5173（经 VITE_API_BASE 直连 8000 的 /api/v1）
npm run build      # 产物输出 dist/
npm run preview    # 预览构建产物（默认连接 http://127.0.0.1:8000）
```

> 前端 `VITE_API_BASE` 默认在 `.env` 中设为 `http://127.0.0.1:8000`；接口路径前缀统一为 `/api/v1`（见 `src/api/client.ts`）。

## 安全与权限

- Web 后端使用**只读角色** `gaokao_web_ro`（仅 `CONNECT/USAGE/SELECT`），与 ETL 的 `gaokao` 拥有者角色分离。
- 连接串通过 `backend/.env` 的 `GAOKAO_DSN` 注入，不硬编码写库口令（见 `app/config.py`）。
- `.env` 已纳入 `webapp/.gitignore`，不会入库。

## Phase 0 交付物

- [x] 数据发布版本 `data_releases` + 批次发布状态 `admission_publication_status` 两表
- [x] 固化质量与发布状态（当前版本 `2026.1`；2026 普通类专科批标记为**待发布**，可区分「无数据」与「尚未发布」）
- [x] 常规/征集隔离验证（常规 36,787 / 征集 956）
- [x] 配置安全整改（只读角色 + `.env` 注入）
- [x] 数据质量报告：`backend/../docs/quality-report.md`（位次回填率 2025 98.7% / 2026 98.3%；院校画像关联 92.8%）
- [x] 工程基座：FastAPI 分层 + Vue3 脚手架 + Stripe 适配设计 token + 数据状态页

## Phase 1 交付物（只读查询基础）

- [x] **定位服务**：分数↔位次换算（含顶部「及以上」桶、分数缺口区间估计、百分位）、省控线判断（本科线 + 特控线 + 艺术/体育提示）、个人定位摘要（含跨年同位次分数对照）。后端 `app/services/locate.py`。
- [x] **院校/专业检索**：院校按名称/代码搜索并展示画像标签；专业按名称搜索并展示招生院校数与分数/位次区间。后端 `app/services/search.py`。
- [x] **院校与院校专业详情**：院校画像 + 城市画像 + 历年招生摘要 + 专业列表；点开专业查看历年最低分/位次/批次/征集/数据来源逐条溯源。后端 `app/services/schools.py`。
- [x] **数据中心**：省控线、一分一段表（分页）、原始录取记录（多维筛选+分页）、源文件溯源、批次发布状态五类视图。后端 `app/services/datacenter.py`。
- [x] **前端页面**：我的定位、院校查询、专业查询、院校详情、院校专业详情、数据中心（含顶部数据状态横幅与待发布提示）。
- [x] 查询性能索引（`0004_indexes.sql`）+ 只读角色授权。

完成标准达成：**用户可查询全部已发布历史数据并看到来源**。

## 下一步（Phase 4+）

- Phase 4：补 2023/2024 录取、招生计划（人数/学费/选科要求）、专业标准库、合作/定向/专项标签。
- Phase 5：艺术体育独立模型；AI 数据解释。

> Phase 2 已完成：普通类智能匹配（冲/稳/保/高波动/数据不足），见 `src/views/Match.vue` 与 `app/services/match.py`。
> Phase 3 已完成：决策工作台（收藏/对比中心/多方案+梯度分析/xlsx 导出），见 `src/views/Workbench.vue`、`src/composables/usePlanner.ts` 与 `app/services/plan_export.py`。
