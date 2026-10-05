# Chengzhu v1.4 Validation Hardening — Current Reality

> Updated after v1.3 Goal-centered Interview OS merged to main.
>
> This report distinguishes engineering proof, packaged/runtime proof, synthetic product-loop evidence, and evidence that still requires real users. It must not be read as a PMF claim.

## 1. Git / release baseline

- v1.3 merge commit on `main`: `48d06ffcdc5769332cba48e04577e6d787ad4f2d`
- v1.3 PR: #5 — merged
- v1.3 PR CI: `37285890890` — SUCCESS
- v1.3 PR Release preflight: `37285890873` — SUCCESS
- post-merge main CI: `37287635769` — SUCCESS
- current public stable release: `v1.3.0` — published 2026-10-05
- current v1.4 branch: `feat/chengzhu-v1.4-final-hardening`
- current v1.4 PR: #11
- former PR #9 product/UI hardening: merged into #11 and closed to keep one authoritative v1.4 line

v1.3 is therefore merged, CI-proven, packaged and publicly released. v1.4 now combines the product-craft changes from the earlier validation branch with version/release/canonical hardening in one PR.

## 2. v1.3 product status

The Goal-centered product implementation is integrated:

- Action Home
- Goal list / Goal Room / Prepare / Interviews / Offer
- Person Workspace / Fact Inbox / Stories / Skills / Expression
- Material taxonomy + Processing / Ready / Failed / Replacing
- Quick Notes
- Question Banks
- Command Palette
- Guided First Practice
- Practice 3.0
- Panel / Multi-persona practice
- Role-specific rubrics
- Content Coach × Delivery Coach
- Goal progress trends
- Preflight 3.0
- Live Cue-first hierarchy
- Pin Moment
- Nudge / Open Thread
- Closing Mode
- Overlay 3.0
- Reflection → Next Focus
- History
- Settings 3.0
- Data export/delete
- Accessibility / Light-Dark / 390px

Runtime UI evidence is recorded in `reports/CHENGZHU_V1_3_RUNTIME_UI_AUDIT.md`.

Hosted Windows evidence proves packaged frontend resources + packaged backend sidecar + real product API routes. Native interactive Electron window placement / multi-monitor overlay geometry remains honestly limited by the hosted runner's lack of an interactive desktop.

## 3. v1.3 core non-regression

The frozen v1.2-R2 Verified Interview Core remains authoritative:

- Frozen InterviewPack
- Context Compiler
- Provenance / User Assertion / Session Statement separation
- Question routing
- Fast Cue before Deep
- Stream Truth Guard
- Share Privacy boundary
- Human Coach policy boundary
- Windows sidecar/package path

Latest merged-main CI is green. Real-provider model evaluation is still external because CI has no user/provider credential.

## 4. v1.4 six validation questions

v1.4 does not add another large product area. It asks whether the v1.3 loop creates durable value.

| Question | Current engineering evidence | Truth status |
|---|---|---|
| A. Goal reuse | local ProductEvent metrics + deterministic 7-day / 30 / 100-session continuity | ENGINEERING-PROVEN |
| B. Reflection → Prepare | real ReflectionAction → NextFocus → practice-default write-back is exercised | ENGINEERING-PROVEN |
| C. Fast Cue usefulness | render / expand / speech-after-cue / Deep / user feedback signals separated | ENGINEERING-PROVEN, REAL USER PENDING |
| D. Practice transfer | before/after rubric linkage implemented; synthetic/mock evidence explicitly labelled | ENGINEERING-PROVEN, REAL INTERVIEW PENDING |
| E. Fact Inbox burden | backlog/open/resolve/dismiss/reopen/time-to-resolve metrics; dogfood now opens and resolves a real inbox item | ENGINEERING-PROVEN, REAL USER PENDING |
| F. Quick Notes / Pin value | live note usage + Reflection→Quick Note + Pin→Reflection + explicit Pin→NextFocus write-back | ENGINEERING-PROVEN, REAL USER PENDING |

No aggregate “hire score”, offer probability, percentile, or PMF badge is permitted.

## 5. Synthetic longitudinal evidence

CI runs an isolated local store and produces a `v1.4-engineering-validation` artifact.

Required synthetic gates:

- 7-day continuity
- 30-session continuity
- 100-session continuity
- export/delete integrity
- no cross-Goal contamination
- Reflection write-back
- Fact Inbox burden loop
- Reflection-created Quick Note
- Pin promoted to Next Focus
- Practice transfer remains labelled synthetic/mock

Evidence classification:

```text
PRODUCT_VALIDATION_INFRA_COMPLETE
REAL_USER_EVIDENCE_PENDING
PMF_PROVEN = false
```

## 6. Privacy

Product analytics remain local-first.

The event layer rejects raw or high-risk free text such as:

- resume text
- API keys
- raw transcript
- answer text

Synthetic evidence is marked so it cannot silently become “real-user” evidence.

## 7. Current v1.4 hardening delta

The unified v1.4 PR now contains both product craft and validation/release hardening:

1. Reflection explicitly creates a Goal-scoped Quick Note, while local ProductEvent provenance records `quick_note_from_reflection`.
2. Fact Inbox is opened and the deliberately over-strong “lead” claim is resolved to participation.
3. The user-created bad-answer Pin is explicitly promoted to Next Focus only after a Reflection action.
4. Validation metrics assert those actions are present rather than merely asserting that the event names exist.
5. Live keeps the current Question / Fast Cue authoritative while previous turns remain secondary.
6. Action Home / Goal Room / Prepare / Reflection use user-facing Chinese rather than exposing internal labels such as raw `Question Graph`, `InterviewPack` or validation status codes.
7. Goal Room hierarchy and Prepare copy are tightened around the user's next action.
8. Diagnostics renders A–F as product-readable cards while retaining raw metrics one level deeper.
9. Version/release gates require frontend, desktop and packaged backend sidecar to agree on `1.4.0`.
10. The v1.4 release workflow remains blocked until packaged smoke, runtime evidence and version consistency are green.

This closes both kinds of gap: “instrumentation exists but the loop was not exercised” and “the capability exists but the user still sees internal-system language.”

## 8. External / unresolved evidence

Still not proven by automation:

- real-user Goal reuse over time
- whether users perceive Fact Inbox as useful rather than annoying
- whether Fast Cue improves real interview performance
- real Interview-to-Interview transfer
- native overlay geometry and multi-monitor behavior on an interactive Windows desktop
- real paid-provider model quality / latency / cost
- code signing
- macOS signing/notarization
- public Human Coach relay

These remain `BLOCKED_EXTERNAL` or `REAL_USER_EVIDENCE_PENDING`, not failures of the implemented Windows/local product.

## 9. Release truth

Do not call v1.4 a new product feature release merely because these gates are green.

The valid engineering claim after CI is:

```text
V1_4_ENGINEERING_HARDENING = COMPLETE
PRODUCT_VALIDATION_INFRA_COMPLETE
REAL_USER_EVIDENCE_PENDING
```

The stronger claim:

```text
V1_4_REAL_VALIDATION_COMPLETE
```

requires real participant evidence and must not be generated by synthetic dogfood.
