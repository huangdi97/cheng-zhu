# Chengzhu v2.0-R1 — Design Reality Report

> **Status:** V2_DESIGN_COMPLETE_CANDIDATE / V2_CONTRACT_COMPLETE_CANDIDATE
>
> 本报告只描述本 PR 已经真实完成的“设计与可执行 contract”事实，不把设计文档、类型定义或单元测试冒充成 v2 产品 runtime。

## 1. Baseline

v2 设计启动基线：

```text
stable release:
v1.4.2

main at v2 branch creation:
d2d564fba32fbcdff3b70c0da726f2377c83a502

branch:
feat/chengzhu-v2-personal-conversation-intelligence

PR:
#17
```

v1.4.2 Interview 产品继续是当前已发布、可安装、可复现的 Windows baseline。

## 2. Why v2 exists

v1 已经解决：

- Person/Candidate factual boundary；
- Goal-centered preparation；
- frozen Pack；
- Context Compiler；
- realtime audio/ASR；
- Fast Cue before Deep；
- Live/Reflection continuity；
- local-first product analytics；
- Windows release engineering。

v2 不重做这些能力，而是把它们泛化为：

> **Personal Conversation Intelligence：在真实专业对话里，帮助用户知道什么值得说、为什么值得说、对谁说，以及什么时候应该保持沉默。**

## 3. Design set present

当前 PR 已有：

```text
docs/canonical/Chengzhu_v2.0-R1_PERSONAL_CONVERSATION_INTELLIGENCE.md

docs/canonical/v2.0-R1-master/
├── 01_Research_Product_Strategy.md
├── 02_Objects_Data_Provenance.md
├── 03_Conversation_Intelligence_Architecture.md
├── 04_UIUX_Conversation_Profile.md
├── 05_Privacy_Integrations_Evaluation.md
├── 06_Onboarding_Operations_Business_Acceptance.md
└── README.md

docs/goals/
└── CHENGZHU_V2_0_IMPLEMENTATION_MASTER_GOAL.md
```

设计范围已经覆盖：

- product definition；
- market positioning；
- launch wedge；
- all profile templates；
- object/data/provenance；
- Conversation State；
- Counterparty State；
- Expression Planner；
- Contribution Opportunity；
- Guidance Arbiter；
- Before/During/After；
- IA / UI / UX；
- onboarding / upgrade；
- privacy / consent / retention；
- connectors / MCP；
- delete/export；
- evaluation；
- rollout；
- business boundary；
- operations / diagnostics；
- engineering implementation stages；
- final acceptance matrix。

## 4. Product decisions frozen by the design

### One Core, Profiles — not six apps

```text
Interview
Conversation
  ├── Project Sync
  ├── Design Review
  ├── Presentation / Q&A
  ├── 1:1
  ├── Client Call
  └── Negotiation
```

Only Profile changes priorities, surface language and evaluation.

### Launch wedge

```text
Project Sync
+
Design Review
```

chosen because they best reuse current Project/Provenance/Screen/Fast Cue infrastructure while directly testing Contribution Opportunity.

### Live hierarchy

```text
Current Topic
→ ONE primary Guidance
→ Source / Confidence / Warning
```

Transcript and full history remain secondary.

### Differentiator

```text
Contribution Opportunity
+
Provenance-aware Continuity
+
Stakeholder-aware Expression
+
SILENT / interruption control
```

## 5. Executable contract truth

`backend/services/product/future_profile.py` is no longer only a vocabulary placeholder. It now defines the v2 design contract for:

- Conversation profile kinds；
- Assistance modes；
- Guidance kinds；
- Expression actions including SILENT；
- Conversation item taxonomy/states；
- epistemic/review states；
- capture/processing modes；
- SourceRef；
- ConversationSpace / Goal；
- CounterpartyObservation；
- ConversationItem；
- ConversationState；
- OpportunityScore；
- GuidanceCandidate。

It deliberately does **not** create DB tables, routes or UI and therefore does not imply v2 runtime exists.

## 6. Truth invariants encoded in tests

The PR tests require:

- only Interview remains `productized=True` today；
- model extraction alone cannot promote a Decision to AGREED；
- Commitment promotion requires owner + source + confirmation；
- proactive opportunity value is reduced by interruption / uncertainty / stale context；
- v1 Interview Goal still maps into the general Conversation contract。

## 7. What this PR may claim when CI is green

```text
CHENGZHU_V2_0_R1_DESIGN = COMPLETE
CHENGZHU_V2_0_R1_CONTRACT = COMPLETE
V1_INTERVIEW_RELEASE_BASELINE = UNCHANGED
```

## 8. What this PR cannot claim

```text
V2_ENGINEERING_COMPLETE = FALSE
V2_RUNTIME_COMPLETE = FALSE
V2_WINDOWS_RELEASED = FALSE
REAL_CONVERSATION_VALUE_PROVEN = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

No real users currently exist for v2.

## 9. Next engineering truth

The implementation sequence is authoritative in:

`docs/goals/CHENGZHU_V2_0_IMPLEMENTATION_MASTER_GOAL.md`

Engineering must prove:

```text
Space
→ Prepare
→ Frozen Session Pack
→ Conversation State
→ Guidance
→ Continue
→ Next Focus
```

with:

- real DB/API path；
- real runtime UI；
- real provenance/state transitions；
- real Contribution Opportunity suppression；
- Interview non-regression；
- full CI；
- packaged Windows evidence；
- delete/export；
- release provenance。

## 10. Final verdict at design stage

Until final PR CI is green:

```text
V2_DESIGN_COMPLETE_CANDIDATE = TRUE
V2_CONTRACT_COMPLETE_CANDIDATE = TRUE
```

After green CI, these may advance to:

```text
V2_DESIGN_COMPLETE = PASS
V2_CONTRACT_COMPLETE = PASS
```

Everything beyond that remains implementation or real-user evidence.
