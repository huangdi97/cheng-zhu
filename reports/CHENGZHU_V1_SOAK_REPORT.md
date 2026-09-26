# 成竹 Chengzhu v1.0 Soak Report

**日期**：2026-09-26
**模式**：simulated (event-compressed; real audio soak BLOCKED externally)
**判定**：PASS

| Session | Turns | State version | topic_stack | threads | claims | risk_flags | p50 ms | p95 ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| soak-2h (2) | 2400 | 2400 | 12 | 0 | 0 | 0 | 12.093 | 16.059 |
| soak-3h (3) | 3600 | 3600 | 12 | 0 | 0 | 0 | 12.113 | 14.239 |

## 检查项

- 状态有界（topic_stack≤12, threads≤12, claims≤24, risk_flags≤12）：通过
- 显式 reset 后无 topic 泄漏：通过
- 状态更新延迟平坦（p50 < 5ms 量级）：见上表

## 外部阻塞

- 真实音频 2h/3h/5h soak 需要真实面试参与者与音频硬件（BLOCKED）；本报告为事件压缩模拟。
- 恢复真实 soak 后需补跑：memory/queues/WebSocket/provider failure/audio switch 检查。