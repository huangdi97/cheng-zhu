# Chengzhu v1.4.2 — Final Reality Report

> **Status:** RELEASE_READY_WITH_EXTERNAL_BLOCKERS
>
> v1.4.2 is the current public Windows release and the final reproducible baseline for the v1.3-R2 → v1.4 design-convergence cycle.
> This report distinguishes engineering/release evidence from real-user evidence. Synthetic/local evidence must not be described as PMF or real-interview transfer.

## 1. Final release facts

```text
CI-proven v1.4.2 release baseline / public tag / binary source:
ce72eb4068408fd22be8eb421503e7b1b59dc856

note:
main may advance after this release through docs-only truth-sync commits; that does not change the immutable v1.4.2 tag or binary provenance.

main CI:
run 37409763712
conclusion = success

release publish / download-back workflow:
run 37410110368
conclusion = success

release dispatcher:
publish-v1.4.2-on-green-main
run 37410098878
conclusion = success

tag:
v1.4.2
tag SHA = ce72eb4068408fd22be8eb421503e7b1b59dc856

GitHub Release:
published 2026-10-06T04:00:04Z
```

Public assets:

```text
Chengzhu-Setup-x64.exe
Chengzhu-Portable-x64.zip
SHA256SUMS.txt
LICENSE.txt
THIRD_PARTY_NOTICES.md
RELEASE_NOTES_v1.4.2.md
```

Release workflow artifacts:

```text
chengzhu-windows-release
chengzhu-runtime-ui-evidence
chengzhu-download-back-verification
```

The public v1.4.2 tag resolves to the exact same SHA that passed main CI and was checked out for the release build. This closes the moving-main provenance defect discovered in v1.4.1. Later docs-only main commits are not part of the already-published binary and are not allowed to rewrite that provenance.

---

## 2. Product baseline

v1.4.2 contains the complete released v1.3 Goal-centered Interview OS plus v1.4 Product Validation Hardening and the final v1.4.x product-craft/release-provenance closure.

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

Top-level IA:

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

No Meeting / Presentation / 1:1 top-level product is introduced in v1.4.2.

---

## 3. v1.3-R2 product design status

### Studio

- Action Home: PRODUCT_COMPLETE / CI-PROVEN / PACKAGED-PROVEN
- Goal Room: PRODUCT_COMPLETE / CI-PROVEN / PACKAGED-PROVEN
- Goal Prepare / Interviews / Offer: PRODUCT_COMPLETE
- Person Workspace / Fact Inbox / Stories / Skills / Expression: PRODUCT_COMPLETE
- Materials / Quick Notes / Question Banks: PRODUCT_COMPLETE
- Command Palette: PRODUCT_COMPLETE / PACKAGED-PROVEN
- History / Reflection: PRODUCT_COMPLETE
- Settings 3.0 / local validation UI: PRODUCT_COMPLETE
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
- Quick Notes: PRODUCT_COMPLETE
- Pin Moment: PRODUCT_COMPLETE
- Nudge / Open Thread: PRODUCT_COMPLETE
- Closing Mode: PRODUCT_COMPLETE
- Overlay 3.0: PRODUCT_COMPLETE within hosted-runner limits
- Human Coach policy boundary: PRODUCT_COMPLETE
- Share Privacy default OFF: PRODUCT_COMPLETE
- formal Live stop → product live/end → Reflection: PRODUCT_COMPLETE since v1.4.1

### Onboarding

- first Goal: PRODUCT_COMPLETE
- Guided First Practice: PRODUCT_COMPLETE
- Practice question → Fast Cue → own answer → Content/Delivery feedback: PRODUCT_COMPLETE
- hardware/provider fallback explicitly labelled: PRODUCT_COMPLETE

---

## 4. v1.4 validation hardening status

Six core validation questions:

| Question | Engineering path | Final truth |
| --- | --- | --- |
| A · Goal reused over time? | local ProductEvent + longitudinal synthetic continuity | ENGINEERING_PROVEN / REAL_USER_PENDING |
| B · Reflection changes next Prepare? | ReflectionAction → NextFocus → Goal/Practice | ENGINEERING_PROVEN |
| C · Fast Cue useful? | rendered / expanded / Deep / feedback / speech-after-cue signals | INSTRUMENTED / REAL_USER_PENDING |
| D · Practice transfers? | rubric linkage + synthetic/mock before/after | SYNTHETIC_OR_MOCK_ONLY / REAL_INTERVIEW_PENDING |
| E · Fact Inbox burden? | backlog / resolve / dismiss / reopen / time signals | INSTRUMENTED / REAL_USER_PENDING |
| F · Quick Notes / Pin valuable? | Pack use + Reflection write-back + Pin conversion | ENGINEERING_PROVEN / REAL_USER_PENDING |

Engineering continuity evidence includes:

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

These are engineering proofs only.

---

## 5. Frozen Verified Core

v1.4.2 preserves the authoritative v1.2/v1.3 core:

- Candidate/Person factual boundary;
- Provenance / User Assertion / Session Statement separation;
- frozen InterviewPack;
- Context Compiler authority;
- Question Understanding / Routing / Follow-up resolution;
- Fast Cue before Deep;
- Stream Truth Guard;
- Session Claim boundary;
- Human Assistance Policy;
- Share Privacy boundary;
- Windows packaged backend sidecar.

No final-design work weakened these contracts.

---

## 6. Release engineering

v1.4.2 closes the complete Windows release chain:

- backend / frontend / desktop tests: PASS
- typecheck/build: PASS
- functional Playwright: PASS
- visual regression: PASS
- accessibility/e2e gates: PASS
- packaged smoke: PASS
- Windows installer + portable: PASS
- runtime UI evidence: PASS
- clean-install replay: PASS
- SHA256 generation: PASS
- GitHub Release: PASS
- public download-back verification: PASS
- public tag SHA == release source SHA: PASS

The v1.4.1 moving-main race is explicitly superseded by v1.4.2 as the reproducible baseline.

---

## 7. Release provenance invariant

Required and now proven for v1.4.2:

```text
green main CI head SHA at release time
==
release source_sha
==
release checkout SHA
==
installer / portable source SHA
==
draft Release target SHA
==
public tag SHA
```

Concrete value:

```text
ce72eb4068408fd22be8eb421503e7b1b59dc856
```

This invariant is now part of the release workflow contract.

---

## 8. Public product truth

README, current public screenshots and product docs are aligned to the Goal-centered Interview OS.

Public screenshots represent the current product surfaces:

- Action Home
- Goal Room
- Practice
- Preflight
- Live Fast Cue
- Reflection
- Command Palette
- 390px Goal Prepare

Legacy module-first screenshots remain historical only and are not allowed to overwrite current product media.

---

## 9. Product-validation truth boundary

Strongest valid claims:

```text
V1_4_ENGINEERING_COMPLETE
PRODUCT_VALIDATION_INFRA_COMPLETE
RELEASE_READY_WITH_EXTERNAL_BLOCKERS
REAL_USER_EVIDENCE_PENDING
```

Not allowed without real participant evidence:

```text
PMF_PROVEN
REAL_INTERVIEW_TRANSFER_PROVEN
V1_4_REAL_VALIDATION_COMPLETE
```

---

## 10. Remaining external / non-design evidence

Not required for the Windows engineering release:

- code-signing certificate;
- macOS signing / notarization;
- public Human Coach relay;
- real paid-provider quality / latency / cost matrix;
- interactive native multi-monitor Overlay proof;
- real longitudinal users;
- real multi-hour human sessions.

These are not unfinished v1.3/v1.4 product-design tasks.

---

## 11. Personal Conversation Intelligence

The complete future Conversation Profile remains canonical and deliberately unproductized in v1.4.

Retained future concepts include:

- Person Representation;
- Conversation Goal / Conversation State;
- Counterparty State;
- Expression Planner;
- Recall;
- Talking Point;
- Answer Cue;
- Question;
- Risk / Contradiction;
- Delivery;
- Contribution Opportunity;
- Decision / Commitment / Task / OpenQuestion;
- Before / During / After;
- Desktop Sidecar;
- future Connector / MCP integration.

The correct current boundary remains:

```text
Interview = first proven product profile
Conversation = future second profile
```

---

## 12. Final verdict

```text
v1.3-R2 GOAL-CENTERED INTERVIEW OS = IMPLEMENTED / RELEASED
v1.4-R1 VALIDATION HARDENING = IMPLEMENTED / RELEASED
v1.4.2 FINAL DESIGN CONVERGENCE = PUBLIC RELEASE / REPRODUCIBLE BASELINE

MAIN CI = PASS
WINDOWS PACKAGED RELEASE = PASS
RUNTIME UI EVIDENCE = PASS
DOWNLOAD-BACK = PASS
PUBLIC TAG PROVENANCE = PASS

V1_4_ENGINEERING_COMPLETE = PASS
PRODUCT_VALIDATION_INFRA_COMPLETE = PASS
REAL_USER_EVIDENCE_PENDING = TRUE
PMF_PROVEN = FALSE
```

Unless a new real defect is found, further Interview work should be evidence-led rather than feature-count-led.
