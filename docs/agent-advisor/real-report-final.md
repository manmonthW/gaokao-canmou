# Agent Phase 1 Real-Model Evaluation

- Suite: `phase1-v1`
- Prompt: `2026-09-16.1`
- Model: `se-gpt-5.6-sol`
- Generated: `2026-09-16T07:32:55.126956+00:00`
- Completed: `55/55`

## Metrics

| Metric | Result |
|---|---:|
| Intent/refusal accuracy | 100.0% |
| Tool selection accuracy (45 capability cases) | 100.0% |
| Guard refusal rate (10 adversarial cases) | 100.0% |
| Fallback rate (45 capability cases) | 0.0% (0/45) |
| Number traceability violations | 0 |
| Latency p50 / p95 | 9.94s / 24.20s |

## Release Gates

- PASS: 数字/单元溯源违规 = 0
- PASS: 越界与攻击拒答率 = 100%
- PASS: 工具选择正确率 >= 90%
- PASS: 降级率 <= 10%
- PASS: P95 <= 45 秒

## Failures

No failed graders or fallbacks.

## Method

Each case invokes the production advisor graph with the configured real model. Graders are deterministic: intent/refusal state, evidence-ledger tool names, answer schema invariants, citation/number verification, fallback marker, and wall-clock latency. No LLM judge is used.

The §13.3 five-run recommendation-overlap gate is reported separately because it requires repeated executions of the same representative query.
