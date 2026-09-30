# Context Compiler（Stage G）

> CURRENT · 对应 canonical 第 14、15 节。落点：`backend/services/intelligence/context_compiler.py`、`retrieval.py`。
> 落地状态：已实现 + 单测（`test_intelligence_compiler_planner.py`）；`answer_worker` 尚无调用点，`intelligence_context_compiler_v1` flag 当前只定义未消费。

## 1. 定位

v1.0 最关键技术内核之一（canonical 第 14 节）：根据当前问题，从所有可能上下文中编译出**最小充分上下文包**（minimum sufficient context），而不是把资料全塞进去。实时面试要求低延迟、高相关、低冲突、低 token、低旧主题污染。

## 2. Provider 接口（canonical 第 14.3 节）

`ContextProvider` Protocol（`context_compiler.py:38`）：

```python
class ContextProvider(Protocol):
    source_type: ContextSource
    def collect(self, question_text: str, *, limit: int = 8) -> list[ContextItem]: ...
```

`ContextSource`（`types.py:119`）定义 9 个 provider 标识：`resume` / `candidate_graph` / `evidence` / `recent_dialogue` / `session_memory` / `job` / `kb` / `screen` / `world_knowledge`。

`context_compiler.py` 当前接线 7 个具体 Provider（全部对接现有本地数据）：

| Provider | source_type | 数据来源 | evidence_strength |
| --- | --- | --- | --- |
| `ResumeProvider` | resume | resume_text 行（每行截 400 字符，≤24 行） | 0.8 |
| `EvidenceProvider` | evidence | `storage.intelligence.list_evidence`（active candidate） | 0.9 |
| `SessionMemoryProvider` | session_memory | compact state（≤600）+ rolling memo（≤600） | 0.6 / 0.5 |
| `JobProvider` | job | job summary 或 requirements 前 8 条（≤500） | 0.7 |
| `KBProvider` | kb | 本地知识库命中（≤6 条） | 0.4 |
| `ScreenProvider` | screen | 屏幕题目（≤500） | 0.7 |
| `WorldKnowledgeProvider` | world_knowledge | 不产出 prompt item；用于路由记录 world knowledge 被允许 | — |

`candidate_graph` / `recent_dialogue` 已在 enum 保留，具体 Provider 待接入（dense/semantic 检索同样走该接口，不改调用方，`retrieval.py` docstring）。

## 3. ContextItem 字段（`types.py:287`）

| 字段 | 说明 |
| --- | --- |
| `id` | 稳定标识 |
| `source_type` | `ContextSource` 之一 |
| `text` | 内容（截 400-500 字符） |
| `entities` | 显式实体列表 |
| `timestamp` | 时间戳（recency 计算用） |
| `evidence_strength` | 证据强度 0-1 |
| `topic` | 主题标签 |
| `token_estimate` | token 估算（CJK 1/字符，ASCII 4/字符） |
| `metadata` | 自由 dict（评分后写入 `score` / `score_breakdown`） |

## 4. 评分公式（canonical 第 14.2 节；`retrieval.py:29` 默认权重）

```text
score(c) =
    w1 * semantic_relevance        0.28   # 话题词 Jaccard（bounded lexical-semantic）
  + w2 * lexical_entity_match      0.18   # ASCII tech token + 显式实体精确命中
  + w3 * evidence_strength         0.14
  + w4 * interview_recency         0.10   # 10 分钟线性衰减
  + w5 * topic_continuity          0.12
  + w6 * job_alignment             0.08
  + w7 * candidate_importance      0.05
  - w8 * contradiction_risk        0.10
  - w9 * redundancy                0.08   # 与已选项重叠
  - w10 * stale_topic_penalty      0.08   # 旧主题污染
```

权重 `ScoreWeights` 可配置、可观测（`score_breakdown` 逐项写入 metadata）；v1.0 用可解释规则，后续版本可基于 eval 学习权重。全部分量确定性、廉价（无云依赖）。

## 5. Hybrid Retrieval（canonical 第 15 节）

不能只用向量。当前实现覆盖：exact/entity match、BM25 式 lexical（CJK bigram/trigram + stopword 过滤）、recency、active-topic boost、contradiction 风险、redundancy、stale penalty；graph traversal 与 dense semantic 为 enum/接口保留项。本地优先阶段仍以 SQLite 为中心（现有 KB FTS5），不强行引入 Neo4j。

## 6. Token Budget（canonical 第 19 节）

| 路径 | 预算 | select 上限 |
| --- | --- | --- |
| Fast（实时第一屏） | `FAST_BUDGET_TOKENS = 1400` | 6 |
| Deep（深度展开） | `DEEP_BUDGET_TOKENS = 3200` | 12 |

`token_budget(deep=)` 统一入口；provider 每次 fetch 上限 `_PROVIDER_FETCH_LIMIT = 24`。

## 7. 编译流程（`ContextCompiler.compile`，`context_compiler.py:218`）

```text
collect  → 每个 provider.collect(question, limit=24)；单项失败记 warning 不丢整包
    ↓ score   → score_item(item, question, active_topic, job_requirements, already_selected, weights)
    ↓ rerank  → rerank(scored)
    ↓ budget  → 逐条裁剪，丢弃原因：select_limit / token_budget / score_floor（score ≤ 0）
    ↓ select  → 选中项 metadata 写入 score + score_breakdown
    ↓ CompiledContext(items, dropped, total_token_estimate, budget, latency_ms)
    ↓ telemetry.record_guidance_event(session_id, "context_compiled", latency_ms, context_ids)
```

`render_context_sections(context)`（`:293`）把选中项按 source 分组渲染为 prompt sections（`[resume]` / `[evidence]` / …，每组 ≤ 8 条）。

## 8. Telemetry 与性能预算

- `context_compiled` 事件记录 latency_ms 与 context_ids（`telemetry.py:22`，fire-and-forget，失败永不打断实时路径）。
- canonical 第 37 节预算：Context Compiler P50 < 300 ms、第一屏 useful cue P50 < 1.5 s。编译器为纯规则（无 LLM、无网络），延迟由 collect（本地 SQLite）主导，预算可由 `latency_ms` 直接观测。
- Sensitive data minimization：item 文本截 400-600 字符，不存 resume 正文（`telemetry.py` docstring）。

## 9. 测试覆盖（`backend/tests/test_intelligence_compiler_planner.py`）

- `test_retrieval_scores_bounded_and_stale_topic_penalized`、`test_score_item_breakdown_has_all_ten_keys_and_bounded_total`
- `test_compiler_select_limit_and_drops_with_latency`、`test_compiler_respects_token_budget`、`test_compiler_stale_topic_items_get_penalty_and_drop_when_budget_tight`
- `test_render_context_sections_groups_by_source`、`test_estimate_tokens_cjk_one_per_char_ascii_four_per_char`
- FakeProvider 测试边界（真实 data boundary——real providers 已在 CANDIDATE_REPRESENTATION/INTERVIEW_STATE 文档覆盖其数据源）。
