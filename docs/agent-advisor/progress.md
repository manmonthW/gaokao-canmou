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
