# Chengzhu v2.0 — Personal Conversation Intelligence 全量实现总 Goal
## 目标：从 v1.4.2 Verified Interview Product 演进到第二 Profile，但不破坏 Interview Core

> 本 Goal 不是“尽量做”。执行时应持续推进直到工程 Gate 收口，除非遇到真实外部 blocker（凭证、签名、第三方 API 权限、真实用户）。

# 0. 基线

- stable release：v1.4.2；
- main baseline at v2 design start：`d2d564fba32fbcdff3b70c0da726f2377c83a502`；
- v2 branch：`feat/chengzhu-v2-personal-conversation-intelligence`；
- canonical：`docs/canonical/Chengzhu_v2.0-R1_PERSONAL_CONVERSATION_INTELLIGENCE.md`。

禁止：

- reset 到旧 v1.3 feature；
- 重写 Interview Core；
- 把 Meeting 做成一级功能堆；
- 把 transcript/summary 当核心价值；
- 自动把 Proposal 升级 Decision；
- sentiment/engagement/personality scoring；
- auto-send / auto-write external systems；
- 为 UI 漂亮破坏 Fast Cue；
- 无真实用户就写 PMF proven。

# 1. Stage 0 — Forensic Baseline

记录：

- main / tags / latest release；
- DB schema / migrations；
- future_profile contracts；
- current IA；
- Context Compiler；
- Live pipeline；
- Overlay；
- export/delete；
- packaged runtime；
- test counts。

输出：

`reports/V2_0_PREFLIGHT_FACTS.md`

全量 baseline 必须绿。

# 2. Stage 1 — Contract Freeze

把 v2 canonical contract 固化：

- ConversationSpace；
- ConversationGoal；
- ConversationSession；
- ConversationSessionPack；
- Participant；
- CounterpartyObservation；
- Topic；
- OpenThread；
- ConversationItem；
- GuidanceCandidate/Event；
- AssistanceMode；
- ExpressionAction。

只做 additive contracts。

# 3. Stage 2 — Additive DB Migration

新增独立 conversation namespace tables。

必须支持：

- migration from clean；
- migration from v1.4.2 data；
- restart；
- rollback/recovery；
- export/delete；
- no Interview contamination。

# 4. Stage 3 — Product API

实现：

- spaces CRUD；
- goals；
- sessions；
- participants；
- items；
- continue review；
- quick notes selection；
- pack freeze；
- decisions；
- commitments；
- open questions；
- profile preferences。

API errors 必须 product-readable。

# 5. Stage 4 — Profile Shell

加入 Profile Switcher：

- Interview；
- Conversation Beta。

Interview IA 视觉/行为不可 regression。

Conversation IA：

- 首页；
- 对话空间；
- 我的成竹；
- 资料库；
- 历史；
- 设置。

# 6. Stage 5 — Conversation Home

完成：

- next session；
- next focus；
- owed by me；
- waiting/open；
- recent change；
- create/start action。

无 productivity score。

# 7. Stage 6 — Conversation Space

完成：

- Overview；
- Prepare；
- Sessions；
- Decisions。

支持所有 empty/loading/error。

# 8. Stage 7 — Prepare / Brief

实现：

- last session delta；
- open commitments；
- open questions；
- decisions；
- participants；
- agenda；
- selected sources；
- Quick Notes；
- session goal；
- pack preview。

Calendar 未接入时可手动。

# 9. Stage 8 — Session Pack

冻结：

- selected sources；
- confirmed decisions；
- commitments；
- quick notes；
- participant context；
- policy；
- language。

运行中新增内容走 delta，不改原 pack。

# 10. Stage 9 — Conversation State Engine

实现：

- turns；
- topic；
- direct question；
- open threads；
- proposal；
- objection；
- candidate decision；
- candidate commitment；
- user speaking state。

状态必须 provenance-backed。

# 11. Stage 10 — Conversation Item Extractor

重点测试：

- Proposed != Agreed；
- Commitment requires owner；
- Deadline ambiguity；
- Superseded chain；
- unknown speaker；
- AI summary not source。

# 12. Stage 11 — Continue Review

会后：

- What changed；
- Decision candidates；
- Commitment candidates；
- Tasks；
- Risks；
- Open Questions；
- Pins；
- Next Focus。

长期写回必须 review。

# 13. Stage 12 — Manual Ask

source-aware meeting Q&A。

必须支持：

- past confirmed decisions；
- prior commitments；
- current session；
- source opening。

不能把模型总结当原始证据。

# 14. Stage 13 — Recall

实现 candidate + provenance + TTL + stale/superseded filtering。

# 15. Stage 14 — Risk / Contradiction

实现：

- conflicting source；
- stale decision；
- unsupported claim；
- commitment risk；
- privacy/visibility risk。

语气保持“可能/来源”。

# 16. Stage 15 — Contribution Opportunity

两阶段：

```text
candidate generation
→ eligibility/scoring
```

必须有：

- relevance；
- novelty；
- provenance；
- role/goal；
- decision impact；
- interruption；
- already mentioned；
- uncertainty；
- social risk；
- stale。

# 17. Stage 16 — Expression Planner

支持：

- SILENT；
- ANSWER；
- RECALL；
- ADD_TALKING_POINT；
- ASK_QUESTION；
- FLAG_RISK；
- CLARIFY；
- SUMMARIZE；
- COMMIT_NEXT_STEP。

# 18. Stage 17 — Guidance Arbiter

唯一 authority。

规则：

- direct question first；
- critical risk；
- recall/opportunity；
- one primary guidance；
- user speaking suppression；
- duplicate suppression；
- TTL；
- suggestion budget；
- new-question cancellation。

# 19. Stage 18 — Assistance Modes

- Quiet；
- Balanced；
- Active；
- Presentation；
- 1:1。

Mode 只调 priority/cadence，不调事实。

# 20. Stage 19 — Preflight

必须展示：

- Session goal；
- participants；
- sources；
- historical items；
- assistance mode；
- capture mode；
- processing mode；
- retention；
- consent acknowledgement；
- screen；
- external action policy。

# 21. Stage 20 — Live Cockpit

第一层：

```text
topic
→ one guidance
→ source/warning
```

secondary：

- transcript；
- notes；
- source；
- manual ask；
- threads。

# 22. Stage 21 — Overlay

复用 v1 Overlay 基础。

v2 新增：

- guidance kind；
- source；
- snooze；
- pause proactive；
- mode。

Hosted runner 无 interactive desktop 时要诚实标 blocked，不造证据。

# 23. Stage 22 — Profile Templates

实现配置：

- Project Sync；
- Design Review；
- Presentation/Q&A；
- 1:1；
- Client Call；
- Negotiation。

它们共享 runtime，不复制页面。

# 24. Stage 23 — Calendar Read-only

可选 connector。

用于：

- upcoming detection；
- title；
- time；
- participants；
- agenda link。

Disconnected 必须不阻塞手动流程。

# 25. Stage 24 — Connector Source Layer

先 read-only。

source visibility 必须进入 Context Compiler gate。

# 26. Stage 25 — Draft Actions

实现本地 DraftAction：

- follow-up email；
- task；
- issue；
- decision log。

没有 connector credential 也可生成本地 draft。

不自动执行。

# 27. Stage 26 — MCP Boundary

先设计/实现 read-only server surface：

- confirmed decisions；
- commitments；
- approved notes；
- session summary；
- source refs。

transcript/private notes 默认不暴露。

# 28. Stage 27 — Product Events

local-first：

- guidance candidate/render/use/dismiss/snooze；
- mode change；
- source opened；
- item confirmed/rejected；
- continue completed；
- space reused；
- manual ask。

# 29. Stage 28 — Synthetic Eval Corpus

覆盖：

- 6 profile templates；
- ambiguous agreement；
- rejected proposal；
- superseded decision；
- unknown owner；
- stale memory；
- private source；
- duplicate opportunity；
- direct question interrupt；
- low-value suggestion；
- social-risk silence。

# 30. Stage 29 — Reliability

- 7-day synthetic；
- 30-session continuity；
- 100-session state；
- long-session soak；
- provider failure；
- offline/reconnect；
- bounded memory；
- no cross-space leak。

# 31. Stage 30 — UI Visual Acceptance

截图至少：

- profile switcher；
- conversation home；
- space empty/active；
- overview；
- prepare；
- decisions；
- preflight；
- live recall；
- live opportunity；
- risk；
- question；
- manual ask；
- pause proactive；
- continue；
- item review；
- presentation；
- 1:1；
- client；
- negotiation；
- light/dark；
- 390px；
- high DPI。

逐页人工 review。

# 32. Stage 31 — Accessibility

- keyboard；
- focus；
- ARIA；
- reduced motion；
- contrast；
- screen reader；
- no hover-only；
- scaling。

# 33. Stage 32 — Privacy / Delete / Export

完整验证：

- delete session；
- delete space；
- derived memory cascade；
- source tombstone；
- export classification；
- token exclusion；
- screen data；
- retention policy。

# 34. Stage 33 — Interview Non-regression

v1 全量：

- Interview Goal；
- Practice；
- Preflight；
- Live；
- Reflection；
- Fast Cue；
- Pack；
- Context Compiler；
- Windows packaged release。

v2 不能以“平台化”为理由破坏 v1。

# 35. Stage 34 — Windows Packaging

必须：

- packaged smoke；
- runtime UI evidence；
- installer；
- portable；
- clean install；
- download-back；
- exact source/tag provenance。

# 36. Stage 35 — Reality Report

输出：

`reports/CHENGZHU_V2_0_FINAL_REALITY_REPORT.md`

只能基于真实证据写：

- DESIGN；
- CONTRACT；
- IMPLEMENTED；
- CI；
- PACKAGED；
- INTERNAL_DOGFOOD；
- REAL_USER_PENDING。

# 37. Engineering Done

只有以下全部成立：

- Conversation data path real；
- Space→Prepare→Session→Continue real；
- item provenance real；
- Contribution Opportunity real；
- SILENT/suppression real；
- one-guidance live real；
- all templates real；
- delete/export real；
- Interview no regression；
- CI green；
- runtime screenshots reviewed；
- packaged Windows green；
- release provenance green。

才能写：

```text
V2_ENGINEERING_COMPLETE
```

仍不能写：

```text
REAL_CONVERSATION_VALUE_PROVEN
PMF_PROVEN
```
