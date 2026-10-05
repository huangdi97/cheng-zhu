# Chengzhu v1.4 — Friction Audit

> Evidence type: **CODE-PATH + AUTOMATED-TESTABLE INTERACTION CONTRACT**.
>
> This audit verifies the interaction budgets frozen in `docs/canonical/Chengzhu_v1.4-R1_VALIDATION_HARDENING.md`.
> It is not user research and does not claim that the flows *feel* effortless to real users.

## Canonical budgets

| Journey | Budget | Current designed path | Status |
| --- | ---: | --- | --- |
| Home → Practice | <= 3 | Home `开始练习` → Practice | PASS · 1 action |
| Goal → Go Live | <= 2 | Goal Room `上场` → Preflight `开始上场` | PASS · 2 actions |
| Live → Quick Notes | <= 1 | Live Cockpit `速记` | PASS · 1 action |
| Live → Pin | <= 2 | Live `标记` / Ctrl+P → choose tag + save | PASS · 2 actions |
| End Session → Reflection | <= 1 | `结束面试` → stop core → close Goal session → auto-open Reflection | PASS · 0 extra actions after stop |
| Reflection → Next Focus → Practice | <= 3 | Reflection `练这个` → server write-back/defaults → Practice | PASS · 1 action |

## 1. Home → Practice

Primary Home paths call the contextual `start_practice` action directly:

- next interview → `开始练习`;
- empty recent-session state → `开始练习`.

The user does not have to open a separate module chooser.

**Designed actions:** 1  
**Budget:** <= 3

## 2. Goal → Go Live

Goal Room exposes two clear actions:

1. `上场` opens the Goal-scoped Preflight;
2. `开始上场` freezes the session content and enters Live.

The Preflight is intentional policy/content confirmation, not accidental navigation friction.

**Designed actions:** 2  
**Budget:** <= 2

## 3. Live → Quick Notes

Live Cockpit contains the `速记` action in the single live companion bar. It opens the Goal-scoped drawer directly and remains read-only during Live.

**Designed actions:** 1  
**Budget:** <= 1

## 4. Live → Pin

Two equivalent entry paths exist:

- click `标记`, then choose/save the Pin;
- Ctrl+P, then choose/save the Pin.

Pin remains a deliberate user judgment rather than an automatic AI annotation.

**Designed actions:** 2  
**Budget:** <= 2

## 5. End Session → Reflection

### Gap found during final audit

Before this closure patch, the formal Live stop button only called legacy `POST /api/stop`.
That correctly stopped the Verified Live Core and closed the review row, but it did **not** call the v1.3 product-layer `POST /api/product/live/end`.

Consequences:

- the Goal session link could remain unfinished;
- session overrides could remain uncleared at the product layer;
- `live_completed` product evidence could be missing;
- the UI did not automatically use the already-available `reflection_ref`;
- the canonical friction budget was not actually closed by the formal Live path.

### Closure

The stop action now performs:

```text
POST /api/stop
→ productApi.liveEnd(live.sessionId)
→ Goal/session linkage closure
→ session-layer cleanup
→ live_completed evidence
→ reflection_ref
→ navigate directly to Reflection
```

If the review row is not available yet, the product falls back to the Goal's Interviews view with an explicit “复盘正在生成” message rather than pretending Reflection exists.

If the product-link call itself fails after recording has already stopped, the UI does not falsely claim that stopping failed; it clears stale Live UI, opens History and surfaces an actionable linkage warning.

**Normal designed path:** 0 extra actions after pressing `结束面试`  
**Budget:** <= 1

## 6. Reflection → Next Focus → Practice

Reflection's primary `练这个` action is not a cosmetic link.

It sends a real `PRACTICE_THIS` Reflection action, receives server-computed practice defaults and navigates directly to Goal-scoped Practice with the focus preselected.

The separate `设为下一步重点` action remains available when the user wants to update the Goal without immediately practicing.

**Designed actions for direct practice:** 1  
**Budget:** <= 3

## 7. Non-claims

This audit does **not** prove:

- that real users perceive these paths as low-friction;
- that the CTA labels are universally understood;
- that real interview stress does not change interaction cost;
- PMF;
- real-user longitudinal retention.

Those remain part of:

```text
REAL_USER_EVIDENCE_PENDING
```

## 8. Regression evidence required

The Live closure patch is not complete until CI proves:

- ControlBar unit test: stop → `liveEnd` → Reflection;
- fallback when the review row is not yet available;
- existing stop failure behavior unchanged;
- frontend typecheck/unit suite green;
- functional Playwright green;
- Verified Live Core / packaged release paths remain green.

## Verdict

```text
V1_4_FRICTION_AUDIT = PASS (DESIGNED / ENGINEERING PATH)
REAL_USER_FRICTION_VALIDATION = PENDING
```
