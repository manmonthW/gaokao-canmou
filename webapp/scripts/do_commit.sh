#!/usr/bin/env bash
cd /home/ekewang/projects/gaokao/ln
git add -A
git commit -m "A1–A4 算法层落地：保档安全边际回测固化、可信度公开、敏感度试算、口径统一 + 结果页可读性优化" -m "- A1: 保档收紧为 R<=best×0.85（margin 由 2025→2026 回测定参：覆盖率物理91.6%/历史92.4%）；best×0.85~best 降为稳；解释文案区间化
- A2: 回测报告固化 backtest_report.txt；classification_note 随响应公开方法/覆盖率/稳定性；改 MATCH_CONFIG 必须附回测
- A3: GET /match/sensitivity 位次±5%/±10% 五情景试算（单次取数内存重算）；前端一键试算
- A4: has_both_years 与 n_years 口径统一（rank_years 同源）；本科提前批 A/B 段代码层别名归一（BATCH_ALIASES + DB 过滤 ANY 展开，不改数据）
- 后端: 重构 _resolve_rank/_prepare_candidates/_totals_at_rank 共用；修复 rank 未定义与别名漏取两 bug
- 前端: 「分档规则与位次敏感度」①/② 两节布局；逐格白话解释（数字与表格逐格对应）；chips/表头悬停提示；院校/专业列左固定
- 测试: 新增 9 个纯函数单测（全套 23 过）；smoke_a1a4/smoke_a4_alias/smoke_a4_merge/restart_backend 脚本
- 文档: changelog-2026-08-08-a1-a4.md；roadmap 状态更新（阈值已回测固化、A1–A4 落地小节、下一步建议）"
git log -1 --stat | head -30
