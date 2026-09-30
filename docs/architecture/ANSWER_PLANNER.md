# Answer Planner（Stage H）

> CURRENT · 对应 canonical 第 16、17、27、28 节。落点：`backend/services/intelligence/answer_planner.py`（吸收 `services/answer_depth.py` + `services/copilot_strategy.py`）。

## 1. 定位

Answer Planner 不直接写最终自然语言，它先决定（canonical 第 16 节）：

1. 这是什么题；2. 面试官可能在验证什么；3. 是否需要个人事实；4. 是否允许 open-world；
5. 有哪些 evidence；6. 哪些内容禁止声称；7. 回答需要什么结构；8. 深度到哪里；
9. 先显示 cue 还是完整答案；10. 下一步可能被追问什么。

**INVARIANT**（模块 docstring）：同一 LLM 不同题型 → 可见不同的结构，不再是"一个 prompt 回答一切"；planner 永不提供关于候选人的事实或 claim。

## 2. 结构化 plan 字段（`AnswerPlan`，`types.py:335`）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `mode` | `ResponseMode` | 11 种响应模式之一 |
| `intent` | list[str] | 当前问题意图（如 `architecture_tradeoff`） |
| `structure` | list[str] | 该模式的回答骨架（分段名序列） |
| `must_use_claim_ids` | list[str] | 必须使用的 claim |
| `forbidden_claim_ids` | list[str] | 禁止声称的 claim |
| `allow_world_knowledge` | bool | 是否允许通用知识（open-world 模式强制 True） |
| `allow_hypothesis` | bool | 是否允许假设表达（HYPOTHETICAL/OPEN_DESIGN/SYSTEM_DESIGN） |
| `depth` | str | `concise` / `structured` / `deep` / `compact_deep`（`DepthProfile`） |
| `surface` | str | 固定 `"cue_first"`（canonical 第 16 节示例） |
| `question_type` | str | 21 类题型原值 |
| `personal_fact_required` | bool | Truth Boundary 是否锁住被问对象 |
| `plan_prompt` | str | 注入 user prompt 的模式指令块 |
| `metadata` | dict | 含 `truth_status` |

## 3. Response Modes 表（canonical 第 17、27、28 节；`_MODE_STRUCTURES`，`answer_planner.py:23`）

| Mode | 结构 |
| --- | --- |
| `EXPERIENCE` | 结论 → 场景 → 我的职责 → 关键动作 → 为什么这样做 → 结果 → 反思 |
| `EXPERIENCE_KNOWLEDGE` | 结论 → 项目事实 → 技术原因 → trade-off |
| `KNOWLEDGE` | 直接回答 → 机制/因果 → 边界 → 验证 |
| `HYPOTHETICAL` | 条件重述 → 总体思路 → 分步设计 → 风险与验证 → 条件化结论 |
| `OPEN_DESIGN` | Clarify → Requirements → Architecture → Data → Scale → Reliability → Security → Observability → Cost → Trade-offs → Evolution |
| `BEHAVIORAL` | 情境 → 挑战 → 行动 → 结果 → 反思（STAR；无真实故事不编事件） |
| `EXPERIENCE_BOUNDARY_KNOWLEDGE` | 事实边界 → 相关经验 → 对该技术的理解 → 如果落地会怎么做 |
| `CODING` | Understand → Clarify → Approach → Complexity → Code → Edge Cases → Explain |
| `SYSTEM_DESIGN` | Clarify → FR → NFR → Capacity → API → Data → Architecture → Deep Dive → Scale → Reliability → Security → Observability → Cost → Trade-offs → Evolution |
| `CASE` | 澄清问题 → 框架 → 分析 → 建议 |
| `NEGOTIATION` | 立场 → 依据 → 条件 → 备选 |

每种模式另有中文 prompt 指令（`_MODE_PROMPTS`，`:62`）：如 KNOWLEDGE 模式明确"候选人没做过不代表不能回答"；HYPOTHETICAL 模式明确"不得把假设改写成'我们当时就是这么做的'"；BEHAVIORAL 模式明确"没有真实故事时提供找故事的方向，不编造事件"。

## 4. 路由表（canonical 第 40 节七轮对话；`_ROUTE_TABLE`，`answer_planner.py:38`）

| question_type | mode |
| --- | --- |
| SELF_INTRODUCTION / EXPERIENCE | EXPERIENCE |
| PROJECT_DEEP_DIVE | EXPERIENCE_KNOWLEDGE |
| BEHAVIORAL / ROLE_FIT / CAREER | BEHAVIORAL |
| KNOWLEDGE / OOD / DEBUGGING / PRODUCT / BUSINESS / COMPANY / META | KNOWLEDGE |
| CODING | CODING |
| SYSTEM_DESIGN | SYSTEM_DESIGN |
| HYPOTHETICAL | HYPOTHETICAL |
| CASE | CASE |
| SALARY / NEGOTIATION | NEGOTIATION |
| FOLLOW_UP / CLARIFICATION | EXPERIENCE_KNOWLEDGE |

路由是**确定性**的（无 LLM）。`route_for(qtype, personal_fact_boundary=)`（`:107`）：个人事实边界题（`personal_fact_required=True` 且 truth_status ∈ {UNKNOWN, INFERRED, CONTRADICTED}，典型如 Q6"你实际用过 Kubernetes 吗"无证据时）升级为 `EXPERIENCE_BOUNDARY_KNOWLEDGE`。

## 5. create_plan 流程（`answer_planner.py:115`）

```text
create_plan(qtype, resolved_question, intent, expected_depth, truth_status,
            personal_fact_required, must_use_claim_ids, forbidden_claim_ids,
            interviewer_state, open_world_allowed)
    ↓ boundary = personal_fact_required AND truth_status 非确定
    ↓ mode = route_for(qtype, personal_fact_boundary=boundary)
    ↓ allow_world = open_world_allowed OR mode ∈ {KNOWLEDGE, HYPOTHETICAL, OPEN_DESIGN, SYSTEM_DESIGN, CODING}
    ↓ structure = _MODE_STRUCTURES[mode]
    ↓ hint = planner_hint(interviewer_state)          # 概率性面试官提示
    ↓ plan_prompt = 模式指令 + 深度指令（DEEP 完整展开 / COMPACT_DEEP 每层 1-2 句）
        + intent 直达指令 + hint
    ↓ AnswerPlan(surface="cue_first", metadata={"truth_status": truth_status})
```

Open-world 边界（canonical 第 18 节）：`open_world_allowed=True` 或知识型 mode 下 `allow_world_knowledge` 恒为 True——"没有简历证据"绝不误判成"不能回答"（`test_open_world_routes_keep_answers_answerable`）。

## 6. 与 answer_depth / copilot_strategy 的吸收关系（canonical 第 33.5 节）

- `services/answer_depth.py`（深度契约：`classify_answer_depth` → CONCISE/STRUCTURED/DEEP/COMPACT_DEEP）→ `DepthProfile`（`types.py:110`，docstring 注明 mirror）+ `create_plan(expected_depth=)` 深度指令。
- `services/copilot_strategy.py`（interviewer focus 意图）→ `planner_hint(interviewer_state)`（来自 `interviewer_state.py`，只服务 planner）。
- 两个 legacy 模块保留运行（实时链路的深度判定仍由 `classify_answer_depth` 直接执行，`answer_worker.py:1109-1114`），planner 层在其上提供结构化 plan；不另造重复 parser/strategy。

## 7. 接线与 plan_prompt 注入

- `realtime_bridge.build_intelligence_layer` 调 `create_plan`（gated by `intelligence_answer_planner_v1`），payload 携带 `plan` / `plan_prompt` / `state_context`。
- `answer_worker.py:1132-1143` 把 `plan_prompt` 与 `state_context` 注入现有 user prompt（`intel_plan_prompt` / `intel_state_context`，written exam 场景只注入 state_context）。
- `answer_done` guidance payload 取 `plan.structure`（core_ideas）与 `plan.mode`/`intent`（见 REALTIME_PIPELINE.md）。

## 8. 测试覆盖（`backend/tests/test_intelligence_compiler_planner.py`）

- `test_create_plan_modes_and_structures_differ_by_question_type` — 同一 LLM 不同结构
- `test_planner_routes_claim_constraints_and_boundary_upgrade` — 路由 + claim 约束 + 边界升级
- `test_open_world_routes_keep_answers_answerable` — 简历外问题可回答
- eval 基线：route_accuracy 1.0 / type_accuracy 0.9（2026-09-25，见 `backend/evals/reports/route_eval_v1_2026-09-25.md`）。
