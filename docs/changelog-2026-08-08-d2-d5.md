# D2–D5 数据层实施记录（2026-08-08）

> 落实 `first-principles-review.md` §5.1 数据层建议 D2–D5 的实施记录与后续开发注意事项。
> 迁移文件即决策记录：本次新增 `0011`、`0012`（均已执行），**下一个迁移编号为 0013**。

---

## 一、数据库迁移（已执行）

### 0011_major_flags.sql
- `admission_scores` 新增 `flags TEXT[] NOT NULL DEFAULT '{}'` + GIN 索引 `idx_scores_flags`。
- 新建 `flag_dictionary` 标记词表（flag / label / severity / note），种子 5 类：
  | flag | label | severity |
  |---|---|---|
  | 中外合作 | 中外合作办学 | warn |
  | 定向 | 定向就业 | warn |
  | 少数民族预科 | 少数民族预科 | warn |
  | 民族班 | 民族班 | warn |
  | 异地校区 | 异地校区 | notice |
- `GRANT SELECT ON flag_dictionary TO gaokao_web_ro`（延续 0003 模式）。

### 0012_subject_requirements.sql
- 新建 `subject_requirements`（year / school_code / school_name / major_name / major_code / group_code / first_req / re_req / raw_text / src_id→source_files / loaded_at）。
- 索引：(year, school_code)、(school_name, major_name)；已授只读角色 SELECT。
- **当前为空表**：2027 官方选科要求发布后由 `etl/load_subject_requirements.py` 入库。

## 二、ETL 新增脚本（etl/）

| 脚本 | 用途 | 状态 |
|---|---|---|
| `load_major_flags.py` | 全库专业级打标（D2a），幂等全量重算 | ✅ 已执行，标记 1,595 行 |
| `audit_score_kind.py` | 审计录取最低分分布（D3 决策依据） | ✅ 已执行 |
| `load_subject_requirements.py` | 2027 选科要求入库骨架（D2b） | 骨架就绪，待官方数据 |
| `publish_release.py` | 发布流水线 check→prepare→publish→rollback（D5） | 就绪 |

- 打标结果：中外合作 1,351 / 少数民族预科 111 / 异地校区 74 / 定向 67 / 民族班 29。
- 防误伤规则（写死在脚本，改动前先看探测结果）：
  - 只匹配「中外合作办学」全称，不匹配裸「合作」；
  - 民族班只认 `(民族班)` 括号形式（避免误标「民族学」专业）；
  - 异地校区要求括号城市名前存在 `schools` 表内的母体校名（正确排除「香港中文大学(深圳)」等独立院校）；
  - 「预科班」同时覆盖少数民族预科班与边防军人子女预科班。
- `etl/config.py` 的 `DATA_DIRS` 已增加 `"2027"`。

### D3 审计结论（重要）
全库「录取最低分」共 448 行，**全部位于提前批**（2025 本科提前批 166 / 专科提前批 128；2026 本科提前批A段 79 / 专科提前批 75）；普通批官方只发布投档线。
→ **D3 采用叙述方案**：不回填数据、不叠加「稳保」逻辑，在 `batch_context.score_kind_note` 与导出免责声明中说明投档线口径的可靠性（「专业+学校」无校内调剂，投档≈录取的近似度高）。`use_admission_for_safe` 无限期搁置。

## 三、后端变更

- **`/api/v1/match`**（`services/match.py` + `routers/match.py`）：
  - 新参数 `exclude_flags`（逗号分隔）、`electives`（再选科目，逗号分隔）；
  - 单元输出新增 `flags`；响应新增 `excluded_by_subject`、`subject_requirements_loaded`、`examinee.electives`；
  - **`batch_context`**（D4）：`score_kind` + `score_kind_note` 口径叙述 + `publication`（各阶段发布状态，来自 `admission_publication_status`）+ `warning`（批次未登记发布状态时警告）。
  - **选科校验门禁**：仅当 `subject_requirements` 存在对应 year 数据时才启用硬过滤；专业级要求 > 院校级回退；未收录专业给 `subject_unverified` 警告——**永不默认「可报」**。
- **`/api/v1/meta`**：新增 `major_flags`（来自词表，前端徽标文案唯一来源）。
- **`GET /api/v1/data-status/matrix`**（D4）：批次×年份×科类发布矩阵；`gap` = 声称已发布但库内 0 条；另返回 `unregistered`（有数据但无发布登记）。
- **院校详情**（`services/schools.py`）：专业列表聚合 flags（`array_agg(DISTINCT unnest)`）。
- **导出 xlsx**（`services/plan_export.py`）：新增第 7 列「报考标记」；免责声明追加标记核实条款。

## 四、前端变更

- **Match.vue**：排除标记多选（tooltip 显示词表说明）、考生档案再选科目多选（上限 2 科）、batch_context 提示条（未登记批次黄色警告）、结果行标记徽标、`excluded_by_subject` 计数说明。
- **Eligibility.vue（新页，路由 `/eligibility`）**：D2c 资格自查清单（选科/体检/单科/特殊标记/其他硬条件），标记段由 `/meta.major_flags` 动态渲染。
- **DataCenter.vue**：新增「发布矩阵」标签页（矩阵表 + 缺口高亮 + 未登记批次表）。
- **Workbench.vue**：`analyzePlan` 对含标记志愿给核实提醒；导出 payload 携带 flags。
- **SchoolDetail.vue**：专业行显示标记徽标。
- **useProfile.ts**：档案新增 `electives`（默认 `[]`，旧 localStorage 数据带迁移守卫）。
- **types.ts / client.ts**：`MajorFlagDef`、`BatchContext`、`MatrixRow`、`DataStatusMatrix` 等类型与 `dataStatusMatrix()` 端点。

## 五、验证结果（2026-08-08 实测）

- `meta.major_flags` 返回 5 类词表；`data-status/matrix` 返回 55 行矩阵、0 未登记。
- `match`（2026 普通类 物理学科类 本科批，位次 12000）：total 15,570（保 12,752 / 稳 91 / 冲 2,452 / 高波动 275）；标记正确（「边防军人子女预科班」→少数民族预科、「运动康复(中外合作办学)」→中外合作）；`batch_context` 输出投档最低分口径与常规/征集发布状态。
- 后端全部文件 `py_compile` 通过；前端 dev server 正常启动。

---

## 六、后续开发注意事项 ★

1. **迁移纪律**：下一个迁移编号 **0013**；所有 schema 变更走 `webapp/backend/migrations/`，新表必须在同一迁移内 `GRANT SELECT TO gaokao_web_ro`；禁止手工 ALTER。
2. **2027 选科要求入库**：官方要求发布后执行 `python etl/load_subject_requirements.py --file <源文件> --year 2027`。入库后匹配自动切换为硬过滤（前端已有文案与再选科目表单，无需改代码）。入库前**不要**在 match 里加任何选科默认假设。
3. **flags 是派生数据**：新增/重导录取数据后重跑 `python etl/load_major_flags.py`（幂等）。新增标记类别需三处同步：`flag_dictionary` 种子行（新迁移）+ `load_major_flags.py` 规则 + 前端自动生效（读词表，无需改）。改规则前先 dry-run 抽样人工核验（防误伤历史见 §二）。
4. **match 向后兼容底线**：新过滤维度一律可选参数 + 安全默认；既有 `score_kind='投档最低分'` 主口径不变，除非显式 opt-in 叠加。
5. **发布流水线**：数据更新走 `publish_release.py check → prepare --version X → publish`（prepare 自动跑 backfill_lowest_rank + verify_all）；不要绕过 verify 直接插 `data_releases`。
6. **D1 仍是最高优先**：补 2023/2024 录取数据是分档算法可信化的先决条件；补录后重跑打标与 verify。
7. **待办/搁置**：`use_admission_for_safe`（搁置，见 D3 结论）；体检/单科硬校验（仅静态清单页提醒，未做数据化）；roadmap Phase 4 其余项（招生计划、专业标准库）。

## 七、环境操作备忘

- PostgreSQL 16（WSL Ubuntu-24.04）：若连接拒绝，`sudo service postgresql start`（docker 守护进程不可用）。
- 后端：`webapp/backend/run.sh`（venv uvicorn :8000，DSN 见 `backend/.env`，只读角色）。
- 前端：`npm run dev`（:5173，代理 /api→8000）。
- WSL 命令陷阱：PowerShell 内联 `wsl -- bash -c "..."` 会被引号改写，**一律写成 bash 脚本文件再执行**；后台进程需 `setsid nohup`，否则 WSL 会话结束即被杀。
- 维度取值：`subject` 为「物理学科类/历史学科类」（不是「物理类」）；`category` 为 普通类/艺术类/体育类。
