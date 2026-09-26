# 成竹 Chengzhu v1.0 Performance Benchmark

**日期**：2026-09-26 | **runs**：200 | **判定**：PASS

| Stage | p50 ms | p95 ms | Budget |
| --- | --- | --- | --- |
| question_resolve (state update) | 12.195 | 14.082 | rules < 5 |
| question_understanding | 0.013 | 0.022 | rules < 5 |
| truth_boundary (pre-generation) | 0.017 | 0.021 | rules < 5 |
| answer_planner | 0.002 | 0.004 | rules < 5 |
| context_compiler (fast) | 2.061 | 3.224 | P50 < 300 |
| intelligence_layer (full bridge) | 12.705 | 14.185 | rules < 5 |

## 说明

- 本地 overhead 与 provider latency 分开报告；provider 延迟见 live pipeline 的 first_token_ms/total_ms（telemetry）。
- Fast path 第一可用提示 = ASR partial 更新 + deterministic 规则（<5ms）+ provider 首 token；LLM 首 token 延迟由 provider 主导。
- state update 含 interview_state_snapshot 的 SQLite 写入（WAL）。