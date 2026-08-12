# 辽宁志愿参谋 — 开发路径与进展（Roadmap）

> 本文档统一记录「开发方案（Phase 0–5）」与「当前开发进展」，便于随时对齐。
> 所有结论仅作参考，最终以辽宁省招考部门及院校官方信息为准。

---

## 一、开发路径总览（阶段 0–5）

| Phase | 名称 | 目标 | 状态 |
|-------|------|------|------|
| 0 | 数据可信化 + 工程基座 | 区分「无数据」与「尚未发布」；工程可启动 | ✅ 已完成 |
| 1 | 只读查询基础（数据中心 + 检索 + 详情 + 城市透视） | 用户可查全部已发布历史并看到来源 | ✅ 已完成 |
| 2 | 普通类智能匹配 MVP（核心闭环） | 分数+位次 → 定位 + 冲稳保候选，每项可解释 | ✅ 已完成 |
| 3 | 决策工作台（志愿草案 = 可填志愿表） | 用户独立完成 候选→方案 全流程 | ✅ 已完成 |
| 4 | 数据增强 | 补录 / 招生计划 / 选科要求 / 专业标准库 | 🔄 部分完成（D2–D5，见下） |
| 5 | 艺术体育 & 智能解释 | 艺术体育独立模型 + AI 数据解释 | ⬜ 待开始 |

---

## 二、各 Phase 具体步骤

### Phase 0 — 数据可信化 + 工程基座
**目标**：网站能可靠区分「无数据」与「尚未发布」；工程可启动。

- **配置安全整改（高优先）**：
  - 新建 `.env` 注入 `GAOKAO_DSN`，轮换数据库口令。
  - ETL/部署脚本移除硬编码口令；Web 使用只读账号（`gaokao_web_ro`）。
- **新增表 + migration**：`data_releases`、`admission_publication_status`（对齐 spec §5.2）。
- **固化质量与发布状态**：跑 `verify_all.py` → 写发布状态，明确标「2026 普通类专科批 待发布」。
- **工程脚手架**：FastAPI 分层（routers/services/db）+ Vue3+Vite 脚手架 + 共享 TS 类型 + env 加载。
- **基础接口**：
  - `GET /api/data-status`（版本/截止/待发布批次）
  - `GET /api/meta`（枚举：年份/科类/学科类/批次/层次/性质/类型/省份）

### Phase 1 — 只读查询基础
**目标**：用户能查全部已发布历史并看到来源。

- **定位服务（诊断器前半段先出）**：`score↔rank` 换算、省控线判断（用 `score_rank` + `batch_control_line`）。
- **搜索**：`GET /api/schools`（名称/简称/别名）、`GET /api/search?type=major`。
- **详情**：
  - 院校详情（画像 + 城市 + 历年招生专业）。
  - 院校专业详情（ECharts 位次趋势图，缺失年份不连线）。
- **数据中心页**：省控线、一分一段表、来源/更新时间、批次状态横幅（首页/匹配/详情页统一展示，不藏说明页）。
- **城市透视页**：用 `cities.note`（产业/发展标签）+ 该城招生院校。

### Phase 2 — 普通类智能匹配 MVP（核心闭环）★ 最关心的部分
**目标**：输入分数+位次 → 定位 + 冲稳保候选，每项可解释。

> **Phase 2 前置加固（已完成，2026-07-29）**：
> - 定位服务 `locate.py` 补 **15 个单测**（`backend/tests/test_locate.py`，pytest），覆盖顶部桶（含精确命中/高于）、分数缺口（紧邻区间）、位次超范围、无数据、省控线（本科+特控/艺术提示）等边界；并修正了缺口估计取「紧邻更高分」的精度问题。
> - `db.py` 改为**懒加载连接池 + FastAPI lifespan 启动/关闭钩子**（import 阶段不连库，便于单测），`main.py` 加 `init_pool`/`close_pool`。
> - 全部 API 加 **`/api/v1` 前缀**（旧 `/api` 已 404）。
> - 前端 `api/client.ts` 核心接口补**返回类型定义**（集中于 `src/types.ts`），并改为 `ORIGIN + /api/v1 + 相对路径` 结构，兼容 vite 代理与直连两种模式。

- **考生档案**：匿名本地保存（localStorage），`/api/profile`；可随时改条件重算。
- **匹配服务 `/api/match`（spec §7 六步）**：
  1. **资格过滤**：年份/类别/学科类/批次严格一致，常规≠征集，默认排最低位次空值。
  2. **构造候选单元** = 院校+专业+批次+志愿阶段（不按校聚合，避免掩盖同校专业位次差）。
  3. **历史统计**：覆盖年份数、近一年最低位次、最好/最差位次、中位位次、位次跨度/波动、是否连续招生、是否断档。
  4. **风险分类（阈值可配，已经回测固化）**：冲 / 稳 / 保 / 高波动 / 数据不足；保档含安全边际 margin=0.85（A1，2025→2026 回测定参），解释文案为区间语言。
- **结果页**：冲稳保…五 Tab + 筛选器（省/市/层次/性质/类型/专业/是否两年均有）+ 卡片/表格 + 解释（本人位次、历年位次、位次差、波动、依据、数据不足警告）。
- **回测脚本**：仅 2025→2026 一对，分物理/历史、本/专科统计各档实际覆盖，定阈值；回测稳定前不显示概率。✅ 回测结论已回灌（A1 margin=0.85）并制度化：改 MATCH_CONFIG 必须附回测报告；覆盖率数字经 `classification_note` 向用户公开（A2）。

### Phase 3 — 决策工作台（志愿草案 = 可填志愿表）
**目标**：用户独立完成 候选→方案 全流程。

- **收藏 + 对比中心**：同屏比 3–5 项（位次/波动/层次/城市/标签）。
- **多志愿方案**：创建多方案、拖动排序、按冲稳保分组、梯度分析（风险过度集中/数据缺失/重复提醒）。
- **导出志愿表（xlsx）**：列对齐辽宁「专业+学校」平行志愿结构——
  序号 / 档位 / 院校代码 / 院校名称 / 专业代码 / 专业名称 / 往年最低分 / 往年最低位次 / 位次差 / 层次 / 城市。
  - 方案条目保存**创建时数据版本快照**（防后续数据更新致用户困惑）。
- **方案分享（可选，待确认是否开放）**。

### Phase 4 — 数据增强
- 补 2023/2024 录取。⬜ 待开始（第一性评审 D1 定为最高优先）
- 招生计划（人数/学制/学费/校区/选科要求/体检限制）。⬜ 待开始
- 专业标准库 `majors`。⬜ 待开始
- 中外合作/定向/专项标签。✅ **已完成（2026-08-08，D2a）**：`flags` 列 + `flag_dictionary` 词表，1,595 行打标，详见 `docs/changelog-2026-08-08-d2-d5.md`
- 使系统从「历史匹配」升级为「资格过滤 + 历史匹配」。🔄 **基础设施已就绪**：选科要求表（0012）+ 匹配硬过滤门禁 + 资格自查页已落地；待 2027 官方选科要求入库后自动生效

### Phase 5 — 艺术体育 & 智能解释
- 艺术（按专业类别 + 专业分 + 综合分规则）、体育独立模型。
- AI 仅做数据解释/问答，不生成事实、不替代规则。

---

## 三、与「可填志愿表」的对接要点

- 辽宁普通类本科批为「专业+学校」平行志愿（近年 112 个），志愿表列即按此结构设计，导出后可直接对照填报系统。
- **「冲」用投档最低分判门槛，「稳保」叠加录取最低分**（库内录取分仅 373 行，兜底用投档分）。
- **570 行 `lowest_rank` 为空的专业**：匹配时降级为「分数对比」并在卡片标「数据不足」。

---

## 四、当前进展（截至 2026-08-12）

### ✅ Phase 0 — 已完成
- 配置安全整改：`.env` 注入 `GAOKAO_DSN`；数据库只读账号 `gaokao_web_ro` 已建并授权（`0000_role.sql` + `0003_grants.sql`）。
- 新增表：`data_releases`、`admission_publication_status`；固化发布状态（`0002_seed.sql`，已标 2026 普通类专科批待发布）。
- 工程脚手架：FastAPI 分层（routers/services/db/config/schemas）+ Vue3 + Vite + Element Plus + 共享 TS 类型 + env 加载。
- 基础接口：`GET /api/data-status`、`GET /api/meta` 已就绪并验证。

### ✅ Phase 1 — 已完成（含超出原计划的扩展）
**后端（已在 :8000 运行，全部接口实测 200）**
- 定位服务 `app/services/locate.py`：
  - `score↔rank` 换算（含顶部「X 分及以上」桶、分数缺口区间估计、百分位）。
  - 省控线判断（本科线 + 特控线 + 艺术/体育「仅文化课线」提示）。
  - 个人定位摘要（百分位、过线情况、跨年同位次分数对照）。
  - 接口：`/api/locate/score-to-rank`、`/rank-to-score`、`/control-line`、`/summary`。
- 检索 `app/services/search.py`：
  - 院校按名称/代码搜索，带 985/211/双一流 等画像标签。
  - 专业按名称搜索，展示招生院校数与分数/位次区间。
  - 接口：`/api/search/schools`、`/api/search/majors`。
- 院校与院校专业详情 `app/services/schools.py`：
  - 院校画像 + 城市画像 + 历年招生摘要 + 专业列表。
  - 院校专业详情：历年最低分/最低位次/批次/征集/数据来源逐条溯源。
  - 接口：`/api/schools/{code}`、`/api/schools/{code}/major`。
- 数据中心 `app/services/datacenter.py`：
  - 省控线、一分一段表（分页）、原始录取记录（多维筛选+分页）、源文件溯源、批次发布状态 五类视图。
  - 接口：`/api/datacenter/control-lines`、`/score-rank`、`/records`、`/source-files`、`/publication-status`。
- 查询性能索引：`migrations/0004_indexes.sql` + 只读角色授权补齐。

**前端（Vue3 + Element Plus + Stripe 适配设计 token）**
- 页面：我的定位（`Locate.vue`）、院校查询（`SchoolSearch.vue`）、专业查询（`MajorSearch.vue`）、院校详情（`SchoolDetail.vue`）、院校专业详情（`SchoolMajorDetail.vue`）、数据中心（`DataCenter.vue`）。
- 统一顶部数据状态横幅 `DataStatusBanner.vue`（待发布提示不藏说明页）。
- 路由（`router/index.ts`）、API 客户端（`api/client.ts`）、共享类型（`types.ts`）。
- `npm run build` 通过；dev 代理 `:5174 → :8000` 实测 200。

**踩坑记录（供后续 Phase）**
- `admission_publication_status` 实际列是 `official_published_at` / `system_updated_at`，已对齐。
- 院校专业里「计算机科学与技术」在大连理工仅以「电子信息类(…)」复合名存在，无独立行；空结果是数据真实情况，已在详情页给出说明而非报错。
- 一分一段表 `score_rank` 非每个整数分数都有行（存在分数缺口），换算时已做区间估计。
- 启动进程请用按端口精确 kill，避免 `pkill` 误伤其他会话；陈旧 dev server（5173）曾导致代理 401，清理后正常。

### ✅ Phase 2 — 已完成（2026-07-29）

按 spec §7 六步实现匹配服务 MVP，形成「输入分数+位次 → 冲稳保候选」核心闭环：

1. **考生档案**：`frontend/src/composables/useProfile.ts`（匿名 localStorage 单例，与「我的定位」共享；`/api/profile` 后端用户体系留待 Phase 3）。
2. **`/api/v1/match` 六步**（`backend/app/services/match.py` + `routers/match.py`）：
   - 输入校验（位次必填，仅有分数则借定位服务反查）；
   - 资格/数据过滤：类别/学科类/批次严格一致、常规≠征集、投档最低分门槛；
   - 候选单元 = 院校+专业+批次+志愿阶段（不按校聚合）；
   - 历史统计：覆盖年份、近一年位次、最好/最差/中位、跨度/波动、连续招生、断档；
   - 风险分类：冲/稳/保/高波动/数据不足，阈值集中于 `MATCH_CONFIG`（✅ 已回测固化，见 A1–A4）；
   - 偏好排序：风险优先、同档内按位次差升序。
3. **结果页**（`frontend/src/views/Match.vue`）：五 Tab（保/稳/冲/高波动/数据不足）+ 筛选器（省/层次/性质/类型/专业关键词/仅两年均有）+ 可解释表格（历年位次展开、本人位次差、依据、数据不足警告）。
4. **回测诊断脚本** `webapp/scripts/backtest_match.py`：量化 2025↔2026 跨年位次稳定性（物理本科中位变动 6.2%、P90 31%、高波动≥50% 占 4.7%），用于校准阈值；报告固化于 `webapp/scripts/backtest_report.txt`；**MVP 不显示概率**。

关键数据约束（已落地）：
- 库内录取分仅 373 行，远少于投档分（3.7 万），MVP 统一用**投档最低分**对应 `lowest_rank` 作门槛（后续补录取分可细化「稳/保」）。
- `lowest_rank` 为空的单元 → 归入「数据不足」档并显式标注（位次法不可用，仅分数参考）。
- 仅 1 年投档数据的单元：仍按该年分类，但附「仅1年、参考性有限」提示（不再像早期版本那样全部塞进数据不足）。

验证：后端 `/api/v1/match` 实测 200；物理本科批 rank=50000 → 保 6765 / 稳 177 / 冲 8353 / 高波动 275；前端 `npm run build` 通过，开发服务器 `/match` 与代理均 200。

### ✅ Phase 3 — 已完成（2026-07-29）

决策工作台（志愿草案 = 可填志愿表），用户可独立完成「候选→方案」全流程：

1. **收藏 / 对比 / 方案状态**：`frontend/src/composables/usePlanner.ts`（匿名 localStorage，spec §9.3）。
   - 候选加入时冻结为 **`CandidateSnapshot` 快照**（数据版本 + 风险 + 判定依据 + 本人位次），防后续数据更新致用户困惑（spec §5.2.6）。
   - 收藏可按风险档筛选；对比上限 5 项（加入对比自动收藏以保留快照）。
2. **匹配页接入**（`Match.vue`）：结果表新增操作列（☆收藏 / 对比 / +方案），加入方案支持选择已有方案或新建；底部吸底工作台快捷入口。
3. **决策工作台页**（`views/Workbench.vue`，路由 `/workbench`）三 Tab：
   - **收藏**：风险筛选 + 对比/加入方案/移除；
   - **对比中心**：2–5 项同屏属性对比表（风险/批次/城市/层次/近一年位次分/最好最差中位/波动/位次差/依据/数据版本）；
   - **我的方案**：多方案创建/删除、条目上下移排序、按冲→稳→保一键重排、逐条备注、**梯度分析**（冲占比>50%、无保底、无稳档、高波动偏高、数据缺失、重复院校+专业、版本不一致、超 112 上限等提醒）。
4. **导出志愿表 xlsx**：`POST /api/v1/plan/export`（`backend/app/services/plan_export.py` + `routers/plan.py`，openpyxl）。
   - 列对齐辽宁「专业+学校」平行志愿：序号/档位/院校代码/院校名称/专业代码/专业名称/往年最低分/往年最低位次/位次差/层次/城市/备注；
   - 抬头含考生条件、数据版本、创建/导出时间；档位按冲稳保着色；含免责声明；不含用户真实姓名（spec 隐私）。
   - 服务端无状态不落库，方案数据由前端快照传入，导出内容与用户所见一致。
5. **顺带修复**：`match.py` 第三步解包变量 `score` 遮蔽考生 score 参数的 bug（`examinee.score` 曾被覆盖为最后一行投档分）；并补 `last_year_score` 字段（导出「往年最低分」列所需）。

验证：`POST /plan/export` 直连与 vite 代理均 200，xlsx 用 openpyxl 回读表头/条目正确；`/workbench` 200；前端 `npm run build` 通过；后端 15 个单测全过。

方案分享（roadmap 中标注「可选，待确认」）未实现，待确认是否开放。

### 🔄 Phase 4 部分落地 — D2–D5 数据层实施（2026-08-08）

落实 `first-principles-review.md` §5.1 建议，完整记录见 **`docs/changelog-2026-08-08-d2-d5.md`**：

- **D2a 专业级标记**：迁移 0011（`flags TEXT[]` + GIN + `flag_dictionary` 词表）；`etl/load_major_flags.py` 幂等打标 1,595 行（中外合作 1,351 / 少数民族预科 111 / 异地校区 74 / 定向 67 / 民族班 29）；match 支持 `exclude_flags` 过滤；前端徽标 + 资格自查页（`/eligibility`）。
- **D2b 选科要求**：迁移 0012（`subject_requirements`）；`etl/load_subject_requirements.py` 骨架就绪；匹配侧硬过滤门禁已实现（仅当对应年份数据入库后启用，未收录专业给 `subject_unverified` 警告，永不默认「可报」）。
- **D3 口径审计**：`etl/audit_score_kind.py` 证实录取最低分仅 448 行且全在提前批 → 采用叙述方案（`batch_context.score_kind_note` + 导出免责声明），不做数据回填。
- **D4 发布矩阵**：`GET /api/v1/data-status/matrix`（批次×年份×科类，缺口高亮）；match 响应携带 `batch_context`（口径 + 发布进度 + 未登记批次警告）；数据中心新增「发布矩阵」标签页。
- **D5 发布流水线**：`etl/publish_release.py`（check → prepare → publish → rollback，prepare 自动跑 backfill + verify_all）。

### ✅ 算法层落地 — A1–A4（2026-08-08）

落实 `first-principles-review.md` §5.2，完整记录见 **`docs/changelog-2026-08-08-a1-a4.md`**：

- **A1 保档安全边际**：`R <= best × 0.85` 才判保（margin 由 2025→2026 回测定参：覆盖率物理 91.6% / 历史 92.4%）；best×0.85～best 区间降为「稳」；全部解释文案区间化（分档是对明年的区间判断）。
- **A2 回测闭环制度化**：回测报告固化（backtest_report.txt）；`classification_note` 随 match 响应向用户公开方法/覆盖率/门槛稳定性；改 MATCH_CONFIG 必须附回测报告。
- **A3 敏感度试算**：`GET /api/v1/match/sensitivity` 位次 ±5%/±10% 五情景重算分档（同一候选集，内存重算不重复查库）；前端一键试算表。
- **A4 口径统一**：`has_both_years` 与 `n_years` 同源（有位次的年份）；本科提前批 A/B 段代码层别名归一（BATCH_ALIASES + DB 过滤展开，不改数据），提前批出现 50 个跨年两年单元。

验证：match 冒烟（2026 物理学科类本科批 位次 12000）total 15,570，标记与 batch_context 输出正确；后端 py_compile 全过；本地部署 :5173/:8000 联调通过。

### ✅ 产品层落地 — P1–P6（2026-08-08）

落实 `first-principles-review.md` §5.3，完整记录见 **`docs/changelog-2026-08-08-p1-p6.md`**：

- **P1 备考期双模式（P0）**：`/match` 支持位次区间（rank_lo/rank_hi 双档判定 + totals/totals_lo）；线差法估位 `/locate/estimate-rank`（模考分−模考线 → 历史同年位次区间，±10% 外扩）；前端档案区间模式 + 定位页估位工具 + 匹配页双档展示。
- **P2 志愿表一等公民（P1）**：工作台 SVG 整表覆盖曲线（叠加考生位次线）；analyzePlan 升级为位置规则（尾部保底/位次倒挂/断层）；梯度模板一键生成（冲30/稳40/保30）。
- **P3 匿名优先（P1）**：取消强制登录守卫；匿名保留 localStorage 数据，登录时云端为空则上推合并；匿名也显示完整应用壳。
- **P4 反馈闭环（P1）**：SQLite `outcome_feedback` 表（刻意不碰只读 PG，无 0013 迁移）+ `POST /feedback`（匿名可用）+ 汇总接口 + 工作台自愿回填入口；2027 年 8 月录取结束后收集第一个真实标签集。
- **P5 偏好最小版（P2）**：`pref_sort` 同档内重排（确定性/院校层次/城市分级）；学费 ≤2 万/年以「中外合作」标记作代理过滤。
- **P6 往年征集参考（P2）**：`GET /datacenter/collection-reference`（位次带内征集记录 + 醒目免责 note）+ 数据中心标签页；match 依旧始终排除征集，两者不冲突。

验证：pytest 32 passed；重启后冒烟（`smoke_p1p6.sh`）六项能力全部输出正确（详见 changelog §九）。

### 🔄 Phase 4 继续落地 — 院校学科实力 / 专业强度一期（2026-08-12）

完整记录见 **`docs/changelog-2026-08-12-major-strength.md`**（migration 0014）：

- **五数据源入库**：school_disciplines 6,492（四轮学科评估 5,212 + 双一流学科 435 + 第五轮 A 类 verified 845）；major_strengths 42,039（软科 30,301 + 国一流 11,445 + 省一流 293）。
- **院校级实力标签**：`school_profiles.strength_tags`（GIN）+ strength_dictionary 词表，build_strength_tags.py 全量幂等重算，732 所命中；「软科」仅专业级明细、不挂校级标。
- **后端附加式**：match 单元附 strength_tags/major_strength；新增 `GET /schools/{code}/strength`；/meta 末尾附 strength_dictionary（契约只增不改，golden JSON 键序不变）。
- **前端 StrengthBadges**：Match/SchoolDetail/SchoolDrawer 三挂载点，非官方（五轮）/第三方（软科）角标与免责口径内置。
- **eval5a 门禁**：三重校验 + 用户签字 S1–S8，裁决 verified 845 / disputed 34（留档不入库）。

验证：pytest 47 passed、smoke 全过、admission_scores=66,959 不变量未动、/match ~5s 基线无劣化。下一迁移编号 **0015**。

---

## 五、环境运行方式

```bash
# 后端（监听 0.0.0.0:8000）
cd webapp/backend
cp .env.example .env          # 填入只读连接串 GAOKAO_DSN
pip install -r requirements.txt
./run.sh                      # 或 python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 前端开发（:5173，代理 /api → 8000）
cd webapp/frontend
npm install
npm run dev

# 前端生产
npm run build && npm run preview
```

**数据库迁移顺序**（以对应角色执行）：
```bash
psql -U postgres -h localhost -d gaokao -f backend/migrations/0000_role.sql
psql -U gaokao    -h localhost -d gaokao -f backend/migrations/0001_phase0_tables.sql
psql -U gaokao    -h localhost -d gaokao -f backend/migrations/0002_seed.sql
psql -U gaokao    -h localhost -d gaokao -f backend/migrations/0003_grants.sql
psql -U gaokao    -h localhost -d gaokao -f backend/migrations/0004_indexes.sql
# 0005–0010 见 migrations/ 目录（按编号顺序执行）
psql -U gaokao    -h localhost -d gaokao -f backend/migrations/0011_major_flags.sql
psql -U gaokao    -h localhost -d gaokao -f backend/migrations/0012_subject_requirements.sql
psql -U gaokao    -h localhost -d gaokao -f backend/migrations/0013_postgrad_rate.sql
psql -U gaokao    -h localhost -d gaokao -f backend/migrations/0014_major_strength.sql
```

> 下一个迁移编号：**0015**。schema 变更纪律与后续开发注意事项见 `docs/changelog-2026-08-08-d2-d5.md` §六。

---

## 六、下一步建议
按第一性评审优先级：**D1 补 2023/2024 录取数据**仍是最高优先（分档可信化先决条件；四年数据可将 margin 回测对扩到 3 对，P1 估位也能扩为多年参照）。算法层 A1–A4 与产品层 P1–P6 均已于 2026-08-08 落地（见 `docs/changelog-2026-08-08-a1-a4.md` / `docs/changelog-2026-08-08-p1-p6.md`）；2027 官方选科要求发布后运行 `load_subject_requirements.py` 即自动启用硬过滤；新数据入库后需重跑 `webapp/scripts/run_backtest.sh` 刷新 CLASSIFICATION_NOTE 固化数字；**2027 年 8 月录取结束后启动 P4 回填收集**（正式启用前先清空冒烟写入的测试行）。
