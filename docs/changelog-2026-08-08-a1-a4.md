# 变更记录：A1–A4 算法层落地（2026-08-08）

落实 `docs/first-principles-review.md` §5.2 算法层建议（A1 P0 / A2 P1 / A3 P1 / A4 P2）。
前序记录：`docs/changelog-2026-08-08-d2-d5.md`（数据层 D2–D5）。

## 一、变更总览

| 建议 | 内容 | 状态 |
|------|------|------|
| A1 | 「保」档收紧为 `R <= best × safe_margin`，margin 回测定参；解释文案区间化 | ✅ |
| A2 | 回测报告固化 + `classification_note` 面向用户公开分档依据 | ✅ |
| A3 | `GET /api/v1/match/sensitivity` 位次 ±5%/±10% 一键试算 | ✅ |
| A4 | `has_both_years`/`n_years` 口径统一；本科提前批 A/B 段跨年别名归一 | ✅ |

## 二、A1：保档安全边际（margin=0.85，回测固化）

**回测定参过程**（`webapp/scripts/backtest_match.py`，报告固化于
`webapp/scripts/backtest_report.txt`）：

- 修复了原 `margin_sensitivity` 的退化缺陷：原版取 R=r25、best=r25，margin<1 时
  「保」分支永远无样本。重写为 q-scan（R = q×r25, q∈{0.90…1.10}）+
  `margin_coverage(m) = 1 − P(r26/r25 ≤ m)` 两个口径。
- 门槛年际比值分布：P10 ≈ 0.87（物理/历史一致）。
- margin=0.85 时「次年门槛不越过安全边际线」的比例：
  **物理学科类本科批 91.6%（n=7027）、历史学科类本科批 92.4%（n=1896）**；
  0.9 → 87.8%（偏低）、0.75 → 95.4%（过严，保档池收缩过多）。

**分类逻辑变化**（`backend/app/services/match.py` `_classify`）：

- 新增 `safe_line = int(best × safe_margin)`，随候选一并返回；
- `R <= safe_line` → 保（原 `R <= best` 即保，乐观偏差已修复）；
- `safe_line < R <= best` → **稳**（新增分支，文案提示「门槛年际变动可能吃掉这段领先」）；
- 全部档位解释文案改为区间语言：「历史门槛区间 [best, worst]」「明年门槛可能在该区间附近移动」，
  明确分档是**对明年的区间判断，不是对历史的事实陈述**。

## 三、A2：回测闭环制度化 + 用户可见可信度

- `CLASSIFICATION_NOTE` 常量固化回测数字（方法、margin、覆盖率、门槛年际稳定性、免责声明），
  每次 `/api/v1/match` 响应携带 `classification_note`。
- 代码注释与常量注释均要求：**调整 `MATCH_CONFIG` 任何参数必须重跑回测并同步更新说明**（spec §7.4）。
- 前端「智能匹配」页新增「分档依据 · 公开回测」卡片（默认折叠）：公开判定方法、
  安全边际、回测对、覆盖率与门槛稳定性。——「敢公开命中率，而不是编一个 78%」。

## 四、A3：位次敏感度试算

- 后端 `svc.sensitivity()`：与 `match()` 共用 `_prepare_candidates`（单次取数），
  对 ±10%/±5%/0/+5%/+10% 五个位次用 `_totals_at_rank` 在内存重算分档，不重复查库。
- 端点 `GET /api/v1/match/sensitivity`，参数与 match 一致（无 risk/分页）。
- 前端同卡片内「位次敏感度试算」按钮 → 情景 × 五档计数表 + 说明。

## 五、A4：口径统一

- `has_both_years` 改为基于 `rank_years`（有最低位次的年份），与 `n_years` 同源，
  消除「has_both_years=True 但 n_years=1」的展示矛盾。
- 本科提前批 A/B 段归一（**代码层别名映射，不做数据迁移**，与 0010 先例一致）：
  - `BATCH_ALIASES` + `_normalize_batch`：单元键归一，2026 A/B 段与 2025 本科提前批合并为同一单元；
  - `_batch_variants`：DB 过滤展开（`a.batch = ANY(...)`），查「本科提前批」自动纳入 A/B 段行；
  - 合并单元展示批次名优先用用户请求的批次名，数据行本身不改。
  - 验证：物理学科类本科提前批出现 50 个跨年两年单元（如陆军兵种大学 2025:22057 / 2026:28129）。

## 六、涉及文件

- `webapp/backend/app/services/match.py`（A1–A4 核心）
- `webapp/backend/app/routers/match.py`（+ `/match/sensitivity`）
- `webapp/backend/tests/test_match_classify.py`（新增 9 个纯函数单测，全套 23 过）
- `webapp/scripts/backtest_match.py`（margin_sensitivity 重写 + margin_coverage）
- `webapp/scripts/backtest_report.txt`（回测报告固化）
- `webapp/scripts/smoke_a1a4.sh`、`smoke_a4_alias.sh`、`smoke_a4_merge.sh`、`restart_backend.sh`
- `webapp/frontend/src/types.ts`、`api/client.ts`、`views/Match.vue`

## 七、验证记录

- pytest：23 passed（含 9 个新增 _classify/_normalize_batch/_batch_variants 单测）。
- 冒烟（`smoke_a1a4.sh`）：classification_note 完整；保档项位次均 ≤ safe_line；
  sensitivity 五情景单调合理（位次越好保档越多）；全部通过。
- A4：提前批合并后 total 108→310，50 个两年单元，`has_both_years=true ⇒ n_years=2` 恒成立。
- 前端 dev server（:5173）+ 后端（:8000）均在运行。

## 八、后续注意

- **任何 `MATCH_CONFIG` 参数调整**（safe_margin / high_vol_rel / break_multiplier 等）
  必须先跑 `webapp/scripts/run_backtest.sh` 并更新 `backtest_report.txt`、
  `CLASSIFICATION_NOTE`、本文件中的数字（spec §7.4，A2 制度化）。
- `CLASSIFICATION_NOTE` 内数字是**固化快照**；新一轮官方数据（2027）入库后需重跑回测刷新。
- 若未来批次命名再变（如提前批再分段），在 `BATCH_ALIASES` 追加即可；
  展示层与单元键已解耦。
- D1（补 2023/2024 数据）仍为下一优先：两年数据下 margin 回测样本有限，
  四年数据可将回测对扩到 3 对，显著提升参数稳健性。
