# Interview State（Stage E/F）

> CURRENT · 对应 canonical 第 11、12 节。落点：`backend/services/intelligence/interview_state.py`、`interviewer_state.py`、`backend/api/intelligence/router.py:253-271`、storage 表 `interview_state_snapshot`。

## 1. 定位

Interview State 表示"这场面试现在进行到了哪里"。**INVARIANT**（模块 docstring）：

- state 是 `InterviewEvent` 的 fold；LLM 每轮**不**重写整场（否则重新引入 topic pollution 与漂移）。
- 每个已提交版本持久化为 snapshot，崩溃恢复与会话切换可精确恢复到面试所在位置。

## 2. Versioned state 字段（`types.py:248-266`）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `session_id` | str | 会话标识 |
| `version` | int | 每次事件 fold +1 |
| `phase` | str | 阶段（`InterviewPhase` 9 值：opening/project_deep_dive/technical_deep_dive/coding/system_design/behavioral/role_fit/hr/closing），由 `_PHASE_HINTS` 关键词推断 |
| `topic_stack` | list[str] | 主题栈（`_MAX_TOPICS = 12`，新主题入栈） |
| `current_topic` / `previous_topic` | str | 确定性 topic 标签（首个 meaningful anchor chunk，≤24 字符） |
| `open_threads` | list[str] | 未闭合追问（≤12 条） |
| `question_type` / `intent` | str | 当前题型 / 意图 |
| `candidate_claims` | list[str] | 候选人已声称（≤24 条，去重） |
| `risk_flags` | list[str] | 风险标记（≤12 条，去重） |
| `screen_problem` | str | 屏幕题目（≤200 字符） |
| `language` | str | 默认 `zh-CN` |
| `expected_depth` | str | 期望深度 |
| `updated_at` | float | 最后事件时间 |

canonical 第 11 节示例状态（phase/topic_stack/current_topic/open_threads/risk_flags/language/expected_depth）与本 dataclass 一一对应。

## 3. 增量事件更新机制（`apply_event`，`interview_state.py:69`）

`apply_event(session_id, kind, payload)` 把一个事件 fold 进 state 并 bump version。支持的事件 kinds：

| kind | fold 行为 |
| --- | --- |
| `question_received` | 更新 current/previous topic（新主题入栈并清空 open_threads；follow-up 保持栈）、question_type、intent、expected_depth、phase 推断 |
| `topic_changed` | 显式换主题：previous 入栈，current 更新 |
| `claim_made` | 追加 candidate_claims（去重，cap 24） |
| `risk_flag_added` | 追加 risk_flags（去重，cap 12） |
| `thread_opened` | 追加 open_threads（去重，cap 12） |
| `thread_closed` | 移除指定 thread |
| `screen_problem` | 记录屏幕题目（≤200 字符） |
| `language_changed` | 更新 language |

未知的 kind 被忽略（前向兼容，`test_unknown_event_kind_is_ignored`）。事件序号 `_SEQ` 按会话单调递增；`threading.Lock` 保护并发 fold。

实时路径还通过 `realtime_bridge.record_committed_turn` 追加 `route_taken` 事件（路由决策回放用）。

## 4. save / restore / reset

| 操作 | 入口 | 说明 |
| --- | --- | --- |
| 保存 | `_persist_snapshot`（`interview_state.py:154`） | 每次事件 fold 后写 `storage.intelligence.save_state_snapshot(session_id, version, state_json)`；持久化是镜像不是事实源，失败只记 warning |
| 恢复 | `restore_from_snapshot`（`:165`）/ `realtime_bridge.restore_session_state` | **崩溃恢复**：从最新 `interview_state_snapshot` 重建内存 state |
| 重置 | `reset_state`（`:54`）/ `POST /api/intelligence/state/reset` | 新会话 / 显式 topic reset：清空 state 与 `_SEQ` |
| 丢弃 | `drop_session` | 会话切换时移除内存 state |

REST API（`api/intelligence/router.py:253-271`）：`GET /state`（当前 state + `compact_context`）、`POST /state/reset`、`POST /state/restore`。

`compact_state_context(state)`（`:184`）渲染 prompt-ready 小状态块（canonical 第 11 节）：`[面试状态：增量维护，仅作承接参考]` + 当前/上一主题 + 题型 + 意图 + 候选人已声称(前 5) + 未闭合追问(前 5) + 风险标记(前 4) + 屏幕题目；空 state 返回空字符串。

## 5. Interviewer State（Stage F，canonical 第 12 节）

`interviewer_state.py` 是**概率性**面试官状态 tracker：

```text
possible_focus:
    engineering_depth: 0.82   # 题型/intent 关键词命中，每次 +0.10（cap 0.95）
possible_concerns:
    rag_evaluation: 0.76      # 取舍/why_not 类 intent，每次 +0.12（cap 0.90）
accepted_signals: [...]       # cap 8
confidence: max(focus.values() + concerns.values())
```

约束与行为：

- **概率性、非事实**：`update_interviewer_state` 返回 NEW state（输入视为 immutable），全部概率在 [0, 0.95]。
- **每轮可衰减**：`decay(state, factor=0.85)` 把每个概率乘 0.85，低于噪声 floor 0.05 的键被丢弃，重算 confidence——无新信号时旧推断自动淡出。
- **只服务 planner**：`planner_hint(state)` 输出概率性提示（"面试官可能在验证：engineering_depth（0.8）"），措辞**永不是**确定性心理判决（"面试官认为你不行"），`test_planner_hint_stays_probabilistic_never_deterministic_verdict` 回归。
- **永不写入长期事实**：interviewer inference（possible_focus/possible_concerns/planner hints）不经过 `memory_policy.py`（其 docstring 明确禁止），不写 `memory_item` 表。
- UI 默认不展示确定性句子；可展示"当前追问可能在验证：工程深度 / 真实性"。
- gated by `interviewer_state_enabled`（默认 `True`）；关闭时 planner 收到 `None`，系统功能完全正常。

## 6. 测试覆盖（`backend/tests/test_intelligence_state.py` + `test_intelligence_compiler_planner.py`）

- 事件 fold：version bump / previous topic 保留 / 连续 follow-up 保持主题与 threads / 显式新主题重置 open_threads 并入栈 / claim 增量去重 / caps / thread 开闭 / unknown kind 忽略。
- 快照：`test_snapshot_roundtrip_restores_equivalent_state`、`test_reset_state_clears_state`。
- compact 渲染：prompt-ready block / 空 state 空串。
- Interviewer State：update 与 decay 有界（`test_interviewer_update_and_decay_stay_bounded`）、planner hint 概率性。
