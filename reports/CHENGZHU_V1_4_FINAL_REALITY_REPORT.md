# Chengzhu v1.4.0 — Final Reality Report

> **Status:** RELEASE_CANDIDATE — final CI / packaged / publish gates pending.
>
> This report is evidence-led. Synthetic product-loop evidence may support engineering closure, but it must not be described as real-user validation or PMF.

## 1. Product baseline

v1.4.0 is a hardening release on top of the released v1.3.0 Goal-centered Interview OS.

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

No new top-level product is introduced in v1.4.

Current stable while this report is being finalized:

```text
v1.3.0
```

Target release:

```text
v1.4.0
```

## 2. Unified v1.4 implementation line

Authoritative PR:

```text
#11
feat/chengzhu-v1.4-final-hardening
```

Former PR #9 contained product/UI hardening. Its changes were merged into PR #11 and #9 was closed so v1.4 has one authoritative branch.

The unified branch includes:

- current Question / Fast Cue visually authoritative in Live;
- previous turns secondary/collapsed;
- Goal / Prepare / Reflection language rewritten for users rather than internal-system terminology;
- product-readable A–F validation UI;
- Goal progress trends without hire/readiness scores;
- local-first ProductEvent validation;
- Reflection → Next Focus;
- Reflection → Quick Note;
- Pin → Reflection → Next Focus;
- Fact Inbox burden loop;
- 7-day / 30-session / 100-session synthetic continuity;
- 3-hour-equivalent answer-worker soak;
- migration / export / delete integrity;
- v1.4 version and release consistency.

## 3. Six product-validation questions

| Question | Engineering path | Current truth |
| --- | --- | --- |
| A · Goal reused over time? | local ProductEvent + longitudinal synthetic continuity | ENGINEERING_PROVEN / REAL_USER_PENDING |
| B · Reflection changes next Prepare? | ReflectionAction → NextFocus → Goal/Practice | ENGINEERING_PROVEN |
| C · Fast Cue useful? | rendered / expanded / Deep / feedback / speech-after-cue signals | INSTRUMENTED / REAL_USER_PENDING |
| D · Practice transfers? | rubric linkage + synthetic/mock before/after | SYNTHETIC_OR_MOCK_ONLY / REAL_INTERVIEW_PENDING |
| E · Fact Inbox burden? | backlog / resolve / dismiss / reopen / time signals | INSTRUMENTED / REAL_USER_PENDING |
| F · Quick Notes / Pin valuable? | Pack use + Reflection write-back + Pin conversion | ENGINEERING_PROVEN / REAL_USER_PENDING |

Required evidence label remains:

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

## 4. Product/UI status

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

### Practice

- Round / Persona / Demeanor / Difficulty / Sources: PRODUCT_COMPLETE
- Adaptive follow-up: PRODUCT_COMPLETE
- Question Banks: PRODUCT_COMPLETE
- Role-specific rubrics: PRODUCT_COMPLETE
- Panel / Multi-persona: PRODUCT_COMPLETE
- Content Coach × Delivery Coach: PRODUCT_COMPLETE
- Progress trends: PRODUCT_COMPLETE

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
- hardware/provider fallback explicitly labelled: PRODUCT_COMPLETE

## 5. Frozen Verified Core

v1.4 must not regress:

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

Final verdict remains pending until the final branch/main CI proves these invariants.

## 6. Local-first validation and privacy

Allowed ProductEvent data is limited to minimal event metadata such as IDs, counts, booleans, durations and bounded categories.

Rejected from validation events:

- full resume;
- raw audio;
- API keys;
- full transcript;
- full evidence documents;
- arbitrary high-risk free text.

Remote telemetry remains opt-in and is not required for v1.4 engineering closure.

## 7. Reliability evidence

Required engineering evidence:

```text
7-day synthetic continuity
30-session synthetic continuity
100-session synthetic reliability
3-hour-equivalent simulated soak
export/delete integrity
migration compatibility
no cross-Goal contamination
provider-failure recovery
bounded state / latency history
```

Not simulated:

- real sleep/wake;
- real audio device switching;
- real network/provider incidents;
- human fatigue;
- real 3-hour interview participation.

Those stay external.

## 8. Version consistency

Required v1.4.0 version surfaces:

```text
frontend/package.json
frontend/package-lock.json
desktop/package.json
desktop/package-lock.json
backend/sidecar.py APP_VERSION
docs/RELEASE_NOTES_v1.4.0.md
```

The release-version gate verifies all version-bearing package/runtime surfaces agree before publication.

## 9. CI

Final PR #11 evidence:

```text
CI run: PENDING
backend: PENDING
frontend: PENDING
desktop: PENDING
Playwright functional: PENDING
Playwright visual: PENDING
e2e smoke: PENDING
Windows packaged smoke: PENDING
ci-gate: PENDING
```

This section must be updated from actual GitHub Actions results before merge.

## 10. Windows packaged / release evidence

Required before RELEASE_READY:

- bundled backend reports v1.4.0;
- fresh first run succeeds;
- frontend served;
- Fast Cue arrives before Deep;
- frozen InterviewPack survives restart;
- install directory stays unchanged;
- installer and portable build;
- runtime UI evidence artifact;
- clean installer replay;
- SHA256SUMS;
- download-back verification.

Current status:

```text
PENDING FINAL PR #11 RELEASE PREFLIGHT
```

## 11. Public release

Target:

```text
tag: v1.4.0
GitHub Release: PENDING
installer: PENDING
portable: PENDING
SHA256: PENDING
download-back: PENDING
```

Do not mark RELEASE_READY before these are real repository/release facts.

## 12. External blockers / non-claims

Not required for Windows engineering release, but still external:

- code-signing certificate;
- macOS signing / notarization;
- public Human Coach relay;
- real paid-provider quality / latency / cost matrix;
- native multi-monitor Overlay proof on an interactive Windows desktop;
- real longitudinal users;
- real multi-hour human sessions.

## 13. Personal Conversation Intelligence

Future Conversation Profile remains canonical but not productized in v1.4.

Retained future concepts:

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

## 14. Final verdict rules

### RELEASE_READY

Only if:

```text
PR #11 CI = green
PR #11 Release preflight = green
merged main = green
v1.4.0 Release exists
release assets exist
SHA256 exists
download-back / clean-install replay = green
version consistency = green
```

### RELEASE_READY_WITH_EXTERNAL_BLOCKERS

Allowed if every engineering/release gate above is green and only the explicitly external items in §12 remain.

### NOT_READY

Any red required gate, missing release asset, version drift, or failed clean-install replay means NOT_READY.

## 15. Truth statement

The strongest allowed statement before real-user research is:

```text
V1_4_ENGINEERING_COMPLETE
PRODUCT_VALIDATION_INFRA_COMPLETE
REAL_USER_EVIDENCE_PENDING
```

The report will be updated with exact SHAs, workflow IDs, artifact hashes and the public Release after final closure.
