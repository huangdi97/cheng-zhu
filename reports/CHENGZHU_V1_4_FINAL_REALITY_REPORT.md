# Chengzhu v1.4.0 — Final Reality Report

> **Status:** RELEASE_READY_WITH_EXTERNAL_BLOCKERS
>
> v1.4.0 is publicly released and its required engineering/release gates are closed.
> This report distinguishes engineering evidence from real-user evidence. Synthetic / local signals must not be described as PMF or real-interview transfer.

## 1. Final release facts

```text
main merge commit:
31c920ba159eb99d6c687b34aa282fe2b7062e6f

authoritative PR:
#11
feat/chengzhu-v1.4-final-hardening
merged = true

main CI:
run 37315468179
conclusion = success

release publish / download-back workflow:
run 37316020206
conclusion = success

tag:
v1.4.0

GitHub Release:
published 2026-10-05T13:37:12Z
```

Public assets:

```text
Chengzhu-Setup-x64.exe
Chengzhu-Portable-x64.zip
SHA256SUMS.txt
LICENSE.txt
THIRD_PARTY_NOTICES.md
RELEASE_NOTES_v1.4.0.md
```

The release workflow completed the release replay/download-back path rather than treating the local build directory as release evidence.

---

## 2. Product baseline

v1.4.0 hardens the released v1.3 Goal-centered Interview OS.

Frozen product loop:

```text
Goal
→ Next Focus
→ Prepare
→ Practice
→ Preflight
→ Live
→ Reflection
→ Next Focus
```

v1.4 does not add another top-level product.

Top-level IA remains:

```text
首页
求职目标
我的成竹
练习
资料库
历史
设置

                         [上场]
```

---

## 3. Product/UI status

### Studio

- Action Home: PRODUCT_COMPLETE
- Goal Room: PRODUCT_COMPLETE
- Goal Prepare: PRODUCT_COMPLETE
- Goal Interviews / Offer: PRODUCT_COMPLETE
- Person Workspace: PRODUCT_COMPLETE
- Fact Inbox: PRODUCT_COMPLETE
- Stories / Skills / Expression: PRODUCT_COMPLETE
- Materials / Quick Notes / Question Banks: PRODUCT_COMPLETE
- Command Palette: PRODUCT_COMPLETE
- Settings 3.0: PRODUCT_COMPLETE
- History / Reflection: PRODUCT_COMPLETE
- Goal progress trends: PRODUCT_COMPLETE without hire/readiness scores

### Practice

- Round / Persona / Demeanor / Difficulty / Sources: PRODUCT_COMPLETE
- Adaptive follow-up: PRODUCT_COMPLETE
- Question Banks: PRODUCT_COMPLETE
- Role-specific rubrics: PRODUCT_COMPLETE
- Panel / Multi-persona: PRODUCT_COMPLETE
- Content Coach × Delivery Coach: PRODUCT_COMPLETE
- Goal-scoped progress trends: PRODUCT_COMPLETE

### Live

- Preflight 3.0: PRODUCT_COMPLETE
- Question → Fast Cue → Source/Warning hierarchy: PRODUCT_COMPLETE
- Deep Answer secondary layer: PRODUCT_COMPLETE
- previous-turn disclosure: PRODUCT_COMPLETE
- Quick Notes: PRODUCT_COMPLETE
- Pin Moment: PRODUCT_COMPLETE
- Nudge / Open Thread: PRODUCT_COMPLETE
- Closing Mode: PRODUCT_COMPLETE
- Overlay 3.0: PRODUCT_COMPLETE within hosted-runner limits
- Human Coach policy boundary: PRODUCT_COMPLETE
- Share Privacy default OFF: PRODUCT_COMPLETE

### Onboarding

- first Goal: PRODUCT_COMPLETE
- Guided First Practice: PRODUCT_COMPLETE
- Practice question → Fast Cue → own answer → Content/Delivery feedback: PRODUCT_COMPLETE
- hardware/provider fallback explicitly labelled: PRODUCT_COMPLETE

---

## 4. Six v1.4 validation questions

| Question | Engineering path | Final v1.4 truth |
| --- | --- | --- |
| A · Goal reused over time? | local ProductEvent + longitudinal synthetic continuity | ENGINEERING_PROVEN / REAL_USER_PENDING |
| B · Reflection changes next Prepare? | ReflectionAction → NextFocus → Goal/Practice | ENGINEERING_PROVEN |
| C · Fast Cue useful? | rendered / expanded / Deep / feedback / speech-after-cue signals | INSTRUMENTED / REAL_USER_PENDING |
| D · Practice transfers? | rubric linkage + synthetic/mock before/after | SYNTHETIC_OR_MOCK_ONLY / REAL_INTERVIEW_PENDING |
| E · Fact Inbox burden? | backlog / resolve / dismiss / reopen / time signals | INSTRUMENTED / REAL_USER_PENDING |
| F · Quick Notes / Pin valuable? | Pack use + Reflection write-back + Pin conversion | ENGINEERING_PROVEN / REAL_USER_PENDING |

Required truth label:

```text
REAL_USER_EVIDENCE_PENDING
```

Not allowed:

```text
PMF_PROVEN
REAL_INTERVIEW_TRANSFER_PROVEN
V1_4_REAL_VALIDATION_COMPLETE
```

until real participant evidence exists.

---

## 5. Engineering validation

v1.4 includes deterministic evidence for:

```text
7-day synthetic continuity
30-session synthetic continuity
100-session synthetic reliability
3-hour-equivalent simulated soak
migration compatibility
export/delete integrity
no cross-Goal contamination
provider-failure recovery
bounded state / latency history
```

These prove engineering continuity only.

They do **not** simulate:

- real sleep/wake behavior;
- real audio-device switching;
- real network/provider incidents;
- human fatigue;
- real 3-hour interview participation;
- real longitudinal retention.

Those remain external evidence.

---

## 6. Local-first validation / privacy

ProductEvent is local-first.

Allowed event content is bounded metadata such as:

- IDs;
- counts;
- booleans;
- durations;
- bounded categories.

Rejected from validation events:

- full resume;
- raw audio;
- API keys;
- full transcript;
- full evidence documents;
- arbitrary high-risk free text.

Remote telemetry remains opt-in and is not required for engineering completion.

---

## 7. Frozen Verified Core

v1.4.0 preserves the v1.2/v1.3 Verified Core:

- frozen InterviewPack;
- Context Compiler authority;
- Provenance / Assertion / Session Statement separation;
- Question Routing;
- Fast Cue before Deep;
- Stream Truth Guard;
- Session Claim boundary;
- Human Assistance policy;
- Share Privacy boundary;
- packaged Windows sidecar.

Main CI and packaged release replay closed without weakening these gates.

---

## 8. Release engineering

Version-bearing surfaces agree on v1.4.0:

```text
frontend/package.json
frontend/package-lock.json
desktop/package.json
desktop/package-lock.json
backend/sidecar.py APP_VERSION
docs/RELEASE_NOTES_v1.4.0.md
```

Required release evidence is closed:

- backend suite: PASS
- frontend unit/typecheck/build: PASS
- desktop suite: PASS
- functional Playwright: PASS
- visual regression: PASS
- accessibility/e2e gates: PASS
- packaged smoke: PASS
- Windows installer + portable: PASS
- clean-install replay: PASS
- release SHA256 generation: PASS
- GitHub Release: PASS
- release download-back verification: PASS

---

## 9. Friction audit and v1.4.1 patch

After v1.4.0 release, a final interaction-path audit found one real product-loop defect:

```text
Live stop
→ Verified realtime core stopped
→ product-layer live/end was not guaranteed
→ Reflection routing / live_completed / session linkage could be missed
```

This does **not** invalidate the v1.4.0 release engineering evidence, but it is a product-loop defect and is being closed by:

```text
PR #12
fix/v1.4-live-reflection-closure
target v1.4.1
```

The patch makes the formal stop action:

```text
POST /api/stop
→ productApi.liveEnd(session_id)
→ close Goal/session linkage
→ clear session overrides
→ record live_completed
→ obtain reflection_ref
→ open Reflection
```

Until v1.4.1 is published, v1.4.0 remains the current stable release.

---

## 10. External blockers / non-claims

Not required for the Windows engineering release:

- code-signing certificate;
- macOS signing / notarization;
- public Human Coach relay;
- real paid-provider quality / latency / cost matrix;
- native multi-monitor Overlay proof on an interactive Windows desktop;
- real longitudinal users;
- real multi-hour human sessions.

Therefore the correct release statement is:

```text
V1_4_ENGINEERING_COMPLETE
PRODUCT_VALIDATION_INFRA_COMPLETE
RELEASE_READY_WITH_EXTERNAL_BLOCKERS
REAL_USER_EVIDENCE_PENDING
```

---

## 11. Personal Conversation Intelligence

Future Conversation Profile remains canonical but is intentionally **not productized** in v1.4.

Retained concepts:

- Recall;
- Talking Point;
- Answer Cue;
- Question;
- Risk / Contradiction;
- Delivery;
- Contribution Opportunity;
- Counterparty State;
- Expression Planner;
- Decision / Commitment / Task / OpenQuestion.

No Meeting / Presentation / 1:1 top-level navigation is added.

---

## 12. Final verdict

```text
v1.4.0 PUBLIC RELEASE = PASS
MAIN CI = PASS
WINDOWS PACKAGED RELEASE = PASS
DOWNLOAD-BACK = PASS
V1_4_ENGINEERING_COMPLETE = PASS
PRODUCT_VALIDATION_INFRA_COMPLETE = PASS
REAL_USER_EVIDENCE_PENDING = TRUE
PMF_PROVEN = FALSE
```

A later v1.4.1 patch may improve product-loop closure, but it must preserve the same evidence boundary.
