# Chengzhu v2.0-R1 — Conversation Intelligence Architecture

# 1. Pipeline

```text
Audio / Screen / Manual Input
        ↓
Capture + ASR
        ↓
Turn / Speaker / Topic Segmentation
        ↓
Conversation State Engine
        ↓
Intent / Direct Question / Item Candidates
        ↓
Context Compiler
        ↓
Retrieval + Provenance Filter
        ↓
Candidate Generators
        ├── Recall
        ├── Talking Point
        ├── Answer Cue
        ├── Question
        ├── Risk
        ├── Delivery
        └── Contribution Opportunity
        ↓
Expression Planner
        ↓
Guidance Eligibility + Scoring
        ↓
Guidance Arbiter
        ↓
ONE primary live guidance
        ↓
User action / speech feedback
        ↓
Continue / Memory Review
```

# 2. Conversation State Engine

维护：

- current topic；
- previous topics；
- direct question target；
- unresolved questions；
- proposals；
- objections；
- decisions；
- commitments；
- open threads；
- speaker turns；
- user speaking state；
- silence window；
- last rendered guidance；
- current assistance mode。

状态引擎不负责“相信”抽取内容，只负责保留 candidate + provenance。

# 3. Question / Addressing Detection

Conversation 里最重要的实时事件之一是：

> “这句话是不是在问我？”

必须综合：

- second-person / name mention；
- semantic question；
- previous turn；
- speaker transition；
- role/context；
- user manual trigger。

误把泛讨论当 direct question 会造成高干扰，因此 threshold 高于 Interview。

# 4. Retrieval

Retrieval 必须先做权限与来源过滤，再做相似度。

顺序：

```text
visibility gate
→ session/space/profile relevance
→ temporal relevance
→ semantic retrieval
→ provenance strength
→ stale/superseded filtering
```

不能“先召回所有东西，再让 LLM 自己决定权限”。

# 5. Context Compiler v2

仍然是唯一 context authority。

输入 bucket：

```text
Session Pack
Current Conversation State
Current Topic
Recent Turns
Selected Person Context
Selected Space Memory
Confirmed Conversation Items
Temporary Counterparty Observations
Quick Notes
Screen Context
Policy / Visibility
```

按 GuidanceKind 输出不同最小上下文。

Direct Answer Cue 优先 latency；Contribution Opportunity 优先 novelty/provenance。

# 6. Recall Generator

Recall 的目标不是“相关”，而是：

- relevant now；
- source-backed；
- not stale；
- not superseded；
- not already obvious；
- safe to surface。

Recall UI 必须带 source + date。

# 7. Talking Point Generator

Talking Point 可以来自：

- user-confirmed facts；
- current project state；
- quick note；
- selected source；
- prior confirmed conversation items。

低 provenance 的个人经历不得主动作为 Talking Point。

# 8. Answer Cue

沿用 v1 Fast Cue：

- 3–5 点；
- 先结论；
- source/warning；
- Deep secondary；
- direct question priority。

Conversation Answer Cue 新增：

- audience role；
- meeting goal；
- commitment risk；
- existing decision consistency。

# 9. Question Generator

Question 不是 generic “还有什么问题”。

来源：

- unresolved OpenQuestion；
- missing owner；
- missing deadline；
- conflicting proposal；
- unclear decision state；
- user goal gap；
- participant explicit concern。

# 10. Risk / Contradiction

Risk 类型：

- source contradiction；
- stale/superseded decision；
- commitment conflict；
- unsupported personal assertion；
- visibility/privacy risk；
- unclear owner/deadline；
- external action risk。

措辞：

```text
“可能与 9/20 的决定不一致”
```

而不是：

```text
“对方说错了”
```

# 11. Delivery

仅在用户表达期间/之后、价值明确时提示：

- conclusion-first；
- overlong；
- repeated；
- missing number；
- missing next step；
- pace。

不做 emotion/charisma/leadership score。

# 12. Contribution Opportunity Engine

## 12.1 Candidate generation

来源：

- confirmed memory；
- project material；
- prior session item；
- quick note；
- current screen context；
- user-created note。

## 12.2 Novelty

必须判断：

- 本场是否已经提过；
- 同义表达是否已出现；
- 别人是否已经覆盖；
- 当前 topic 是否还有效。

## 12.3 Score

内部可使用：

```text
benefit =
  relevance
+ novelty
+ provenance_strength
+ role_relevance
+ goal_relevance
+ urgency
+ decision_impact

cost =
  interruption_cost
+ uncertainty
+ social_risk
+ stale_context_risk
+ redundancy

opportunity_score = benefit - cost
```

分数不直接显示给用户。

## 12.4 Hard gates

任一满足则 suppress：

- user currently speaking；
- direct question unresolved；
- source visibility denied；
- provenance below profile threshold；
- source superseded；
- semantic duplicate；
- topic expired；
- suggestion budget exhausted；
- explicit Quiet mode；
- high social risk + low decision impact。

# 13. Expression Planner

输出动作：

- SILENT
- ANSWER
- RECALL
- ADD_TALKING_POINT
- ASK_QUESTION
- FLAG_RISK
- CLARIFY
- SUMMARIZE
- COMMIT_NEXT_STEP

Expression Planner 不能自行改变 source claim。

# 14. Guidance Arbiter

唯一负责 Live 排序。

建议优先级：

```text
P0 direct Answer Cue
P0 critical factual/privacy Risk
P1 high-confidence Recall
P1 high-impact Contribution Opportunity
P2 unresolved Question
P3 Talking Point
P4 Delivery
```

但最终优先级受 Profile / Mode 调整。

一次只 render 一个 primary guidance。

# 15. Suggestion Budget

默认建议：

- Quiet：无主动 suggestion；risk/direct question 除外；
- Balanced：主动 guidance 平均不高于 1 / 90s，必要时动态延长；
- Active：平均不高于 1 / 45s；
- Presentation：按 slide/section/Q&A event；
- 1:1：更低频、更高阈值。

这些是初始 engineering defaults，不是用户研究结论。

# 16. Feedback Loop

local events：

- guidance_candidate_created；
- guidance_suppressed；
- guidance_rendered；
- expanded；
- source_opened；
- pinned；
- dismissed；
- snoozed；
- user_spoke_after；
- semantic_use_detected；
- manual_ask；
- mode_changed。

不能把“用户说话了”直接等价为“采纳建议”。

# 17. Memory Write-back

只有以下可以进入长期：

- user confirmed；
- source confirmed；
- policy allowed；
- provenance retained。

Model inference 默认不写长期。

跨场记忆优先保存：

- confirmed Decision；
- confirmed Commitment；
- unresolved OpenQuestion；
- user Pin；
- user-authored Quick Note；
- explicit Counterparty fact。

# 18. Failure Modes

必须有 deterministic fallback：

- ASR down → manual notes / no fake live intelligence；
- provider down → transcript/local state continues；
- retrieval timeout → no stale guessed recall；
- speaker uncertain → no owner assignment；
- calendar disconnected → session can start manually；
- screen unavailable → continue without screen；
- inference uncertain → Unknown；
- connectivity loss → local queue + no fabricated external write-back。

# 19. Safety against self-reinforcing memory

禁止：

```text
AI inference
→ summary
→ memory
→ future retrieval
→ “source”
```

必须保持 source DAG，模型产物不能成为自己的最终证据。

# 20. Engineering test corpus

Golden scenarios 必须覆盖：

- proposal rejected；
- proposal accepted；
- ambiguous silence；
- commitment with/without owner；
- deadline ambiguous；
- decision superseded；
- conflicting historical source；
- user interrupted；
- direct question while opportunity pending；
- stale opportunity；
- private source not allowed；
- two similar facts；
- unknown speaker；
- 1:1 sensitive feedback；
- client promise risk；
- design objection unresolved；
- presentation Q&A；
- negotiation offer/counteroffer。

核心 Gate：state promotion 与 provenance 错误必须接近零容忍。
