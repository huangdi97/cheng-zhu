# Realtime Pipeline（Stage J/Q）

> CURRENT · 对应 canonical 第 19、21、37、38 节。落点：`backend/api/assist/pipeline.py`、`answer_worker.py`、`backend/services/intelligence/realtime_bridge.py`、`telemetry.py`。

## 1. 现有实时链路（baseline audit 第 2 节，已实现并保留）

```text
System Audio / Microphone（双通道：面试官线路 + 候选人麦克风）
    ↓ Audio Capture（services/capture/）
    ↓ VAD（单段最长 18s / 最短 0.3s）
    ↓ InterviewerSegment → ASR worker（transcribe_with_fallback，远端 STT + Whisper fallback）
    ↓ AssistAsrStateMachine merge（partial/final，合并 gap 2.0s / 最长 12s）
    ↓ PendingASRGroup → parse_question_turn（question cleanup + LLM correction）
    ↓ submit_answer_task → scheduler claim_next_dispatch → _process_question_parallel
    ↓ answer_worker.process_question_parallel（上下文组装 + 多模型并行生成）
    ↓ chat_stream_single_model → WS answer_chunk → ordered commit
```

并行支线：Screen / Region Capture → Vision / OCR → Screen Context（截图审题、写入 `screen_problem` 状态事件）。

## 2. Intelligence 接入点（`answer_worker.py`）

**DI seam**：`AnswerWorkerDeps`（`answer_worker.py:39-55`，仅在 `pipeline.py:2349-2396` 构造）——新 Intelligence Core 的接入点。接入**严格增量**（canonical 第 33.1 节）：既有确定性 grounding、follow-up、candidate-ASR 保护继续运行，本层永不替换它们；每次失败降级到 legacy path（空 payload），永不打断实时循环（`realtime_bridge.py` docstring）。

| 接入点 | 位置 | Flag | 行为 |
| --- | --- | --- | --- |
| Intelligence layer 调用 | `answer_worker.py:1115-1146` | `intelligence_answer_planner_v1` | `build_intelligence_layer(question, previous_question, relation, session_ref, grounding_status, interviewer_state_enabled)` → understanding + state 事件 + plan |
| plan_prompt / state_context 注入 | `answer_worker.py:1132-1143` | 同上 | `intel_state_context` 与 `intel_plan_prompt` 按序插入 user prompt（written exam 只注入 state_context） |
| Truth check | `answer_worker.py:1445-1475` | 同上 | 严格 grounding 替换后再跑 `check_generated_answer`（6 类 violation）；`fallback_used` 时替换 full_answer 并记 `TRUTH_BOUNDARY_REWRITE` |
| TTFUG telemetry | `answer_worker.py:1409-1424` | `intelligence_live_cue_v1` | 首 token 即首条 useful guidance：`record_guidance_event("first_useful_guidance", route, provider, model, latency_ms=first_token_ms)` |
| Guidance payload | `answer_worker.py:1584-1598` | 同上 | `answer_done` 事件携带 `guidance: {core_ideas, evidence, mode, intent, resolved_question, state_context}` |
| Committed turn | `answer_worker.py:1600-1618` | 同上 | `record_committed_turn(seq, question_raw[:200], question_resolved[:200], question_type, route, guidance_text[:200], latency_ms, answer_plan)` + `route_taken` 状态事件 |

`build_intelligence_layer`（`realtime_bridge.py:28`）内部流程：`understand_question` → （follow-up 时 `resolve_followup` 对 state/上一问/open_threads 消解）→ `apply_event("question_received", …)` → `compact_state_context` → `create_plan`（plan_prompt）。

## 3. realtime_bridge.py 一键接入 API

| 入口 | 用途 |
| --- | --- |
| `build_intelligence_layer(...)` | 理解问题 + 更新 state + 构建当前轮 plan；返回 `understanding` / `plan` / `plan_prompt` / `state_context` / `state` |
| `record_committed_turn(...)` | 答案 commit 后持久化一轮 QA + claim 事件 + route_taken；telemetry 永不打断实时路径 |
| `restore_session_state(session_id)` | 崩溃恢复入口（从最新 `interview_state_snapshot` 重建） |

约束：纯规则、无 LLM 调用、无延迟；`DEFAULT_SESSION_ID = "default"` 兜底。

## 4. 统一事件集（canonical 第 21/38 节）

**State 事件**（`apply_event`，fold 进 versioned InterviewState）：

```text
question_received · topic_changed · claim_made · risk_flag_added
· thread_opened · thread_closed · screen_problem · language_changed
· route_taken（record_committed_turn 追加）
```

**Telemetry 事件**（`telemetry.py`，fire-and-forget，落 `guidance_event` 表）：

```text
first_useful_guidance（TTFUG） · context_compiled（Context Compiler） · session_recovered
```

**Turn 记录**（`interview_turn` 表）：`question_raw` / `question_resolved` / `question_type` / `route` / `guidance_text`（均截 200 字符）/ `truth_flags` / `latency_ms` / `seq`。

observability 要求（canonical 第 38 节）：每个 guidance 记录 question_raw→resolved→type→route→context→scores→plan→model→ttfug→truth_flags；提供 replay 基础（`session_id` + `seq` + 事件序号）。Sensitive data minimization：无 resume 正文、无完整答案。

## 5. 双路径生成（Fast Path + Deep Path，canonical 第 19 节）

- **Fast Path**：先给"能用的第一屏"——一句话结论 + 3-5 个关键词 + 回答骨架；surface 固定 `cue_first`（`AnswerPlan`）。
- **Deep Path**：并行继续 evidence / trade-off / 详细推理 / full answer / follow-up prediction / caution；UI progressive disclosure。
- 现有链路：多模型并行生成（`max_parallel_answers`）+ 健康状态 + fallback 已实现；深度由 `classify_answer_depth` + planner depth 指令控制。

## 6. 性能预算（canonical 第 37 节）

| 阶段 | 预算 |
| --- | --- |
| ASR partial 更新感知 | < 300 ms |
| boundary（truth boundary，纯规则） | < 300 ms |
| Context Compiler P50 | < 300 ms（纯规则无 LLM；`context_compiled.latency_ms` 直接观测） |
| 第一屏 useful cue（TTFUG）P50 | < 1.5 s（`first_useful_guidance.latency_ms` 记录首 token） |
| 深度答案 | 允许异步继续流式 |

## 7. 落地状态与已知风险

- Intelligence layer / truth check / TTFUG / guidance payload / committed turn 已接线并 gated by flag；Context Compiler（Stage G）已实现但尚未接入本链路。
- `realtime_bridge.py` 无直接单测覆盖；其异常会降级到 legacy path（`answer_worker.py:1144-1146` 记 warning `intelligence layer failed`）——计划中的 plan 注入依赖该层正常返回。
- telemetry / interview state snapshot 的失败均被设计为"镜像降级"，不影响实时回答（canonical 第 38 节 observability 不阻塞主链路）。
