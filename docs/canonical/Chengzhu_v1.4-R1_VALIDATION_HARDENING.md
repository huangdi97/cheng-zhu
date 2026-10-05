# Chengzhu v1.4-R1 Canonical Addendum
## Product Validation Hardening

**Status:** RELEASE CANDIDATE DESIGN  
**Base Canonical:** `Chengzhu_v1.3-R2_CANONICAL.md`  
**Frozen Verified Core:** `Chengzhu_v1.2-R2_CANONICAL.md`

---

# 0. Why v1.4 exists

v1.3 turns Chengzhu into a Goal-centered Interview OS.

v1.4 does **not** add another top-level product. It asks whether the v1.3 loop is actually durable and useful:

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

The design principle is:

> A complete workflow is not enough. The workflow must improve the user's next action without becoming another maintenance burden.

---

# 1. Product scope

v1.4 keeps the v1.3 information architecture unchanged:

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

No new first-level navigation is permitted for validation features.

Validation belongs in:

- Goal Room, when the signal helps the user's next action;
- Reflection, when it changes follow-up;
- Settings → Diagnostics, for local product evidence;
- internal reports / CI artifacts, for engineering evidence.

---

# 2. Six validation questions

## A. Is the Goal reused?

Signals:

- Goal reopened;
- sessions per Goal;
- return interval;
- Goal lifespan;
- Next Focus action rate.

Do not convert these into engagement gamification.

## B. Does Reflection change Prepare?

Required path:

```text
Session
→ Reflection finding
→ Reflection action
→ Next Focus
→ Goal Overview
→ next Practice / Prepare action
```

A Reflection page that only renders advice is not complete.

## C. Is Fast Cue actually useful?

Separate:

- rendered;
- expanded;
- Deep Answer opened;
- user marks helpful / not helpful;
- speech-after-cue proxy where locally permitted;
- regenerate / dismiss.

Do not infer usefulness from `cue_rendered` alone.

## D. Does Practice transfer?

Track the same rubric dimension before and after a Next Focus / Practice intervention.

Evidence types must be explicit:

```text
SYNTHETIC_TRANSFER
MOCK_TO_MOCK
REAL_INTERVIEW_TRANSFER
```

Only the final label may be used for actual real-interview evidence.

## E. Does Fact Inbox become maintenance work?

Track:

- generated items;
- backlog size;
- resolution rate;
- dismissal rate;
- median resolve time;
- backlog age / reopen where available.

Hardening rule:

> If backlog grows or dismissal rate is high, reduce generation, merge similar claims and batch review. Do not solve burden with more notifications.

## F. Do Quick Notes and Pin Moment create value?

Quick Notes:

- created;
- selected into Pack;
- opened in Live;
- reused;
- created from Reflection.

Pins:

- created;
- surfaced in Reflection;
- converted to Next Focus;
- converted to Story;
- converted to Fact Check.

---

# 3. Evidence hierarchy

v1.4 uses explicit evidence labels.

```text
NO_DATA
SYNTHETIC_DOGFOOD
LOCAL_DEVICE_USAGE
REAL_USER_EVIDENCE
```

Rules:

- synthetic runs prove engineering continuity only;
- local-device events prove that the product can observe its own loop without remote telemetry;
- neither proves product-market fit;
- real-user qualitative evidence remains separate.

The repository must keep:

```text
REAL_USER_EVIDENCE_PENDING
```

until real participants exist.

Never derive:

```text
PMF PROVEN
hire probability
candidate percentile
readiness score
```

from local analytics.

---

# 4. Local-first ProductEvent

Validation events are local-first and should store the minimum data necessary for product-loop analysis.

Allowed examples:

```text
goal_created
goal_opened
goal_reopened
next_focus_completed
practice_started
practice_completed
preflight_started
live_started
live_completed
fast_cue_rendered
fast_cue_expanded
deep_opened
reflection_opened
reflection_action
next_focus_changed
fact_inbox_opened
fact_resolved
fact_dismissed
quick_note_used_in_pack
pin_created
pin_used_in_reflection
nudge_shown
nudge_dismissed
nudge_actioned
```

Do not persist in validation events:

- full resume;
- raw audio;
- API keys;
- full transcript;
- full evidence documents.

Remote telemetry stays opt-in.

---

# 5. Product-readable validation

Diagnostics must answer A–F in ordinary product language.

It may show:

- counts;
- rates;
- continuity;
- evidence type;
- `REAL_USER_EVIDENCE_PENDING`.

It should not make the user inspect raw JSON first.

Raw metrics remain available under an expandable diagnostics layer.

---

# 6. Goal progress trends

Goal Room may show explainable trends only within the same Goal.

Examples:

```text
Technical depth      improving
Ownership clarity    repeating
Time to conclusion   improving
```

Every trend must explain its source and observation count.

No combined hire score.

---

# 7. Friction audit

Canonical journeys:

| Journey | Budget |
| --- | ---: |
| Home → Practice | <= 3 steps |
| Goal → Go Live | <= 2 |
| Live → Quick Notes | <= 1 |
| Live → Pin | <= 2 |
| End Session → Reflection | <= 1 |
| Reflection → Next Focus → Practice | <= 3 |

These are interaction budgets, not user research results.

The system should reduce duplicate entry points, modal stacking, dead ends and ambiguous back navigation before adding new permanent controls.

---

# 8. Longitudinal engineering evidence

Required deterministic engineering evidence:

```text
7-day synthetic continuity
30-session synthetic continuity
100-session synthetic reliability
3-hour-equivalent soak
```

The synthetic store must be isolated from the user's real Chengzhu data.

The soak must check at minimum:

- InterviewPack stability;
- bounded state;
- no context pollution;
- provider failure recovery;
- coach session cleanup;
- bounded latency history.

Not simulated:

- real sleep/wake;
- real device switching;
- real human fatigue;
- real network/provider behavior.

Those remain external evidence.

---

# 9. Migration and data integrity

Required:

```text
v1.2.2 → v1.3 → v1.4
```

No destructive loss.

Product entities with text primary keys must reject missing IDs instead of creating orphan rows.

Export / delete integrity must ensure:

- no broken Pack references;
- no dangling Reflection references;
- no orphan material references.

---

# 10. Performance boundary

v1.4 must not regress the frozen v1.2/v1.3 Live Core.

Key invariants:

- Fast Cue still precedes Deep;
- Goal / Library rendering cannot block Live;
- Context Compiler authority remains unchanged;
- InterviewPack remains frozen per session;
- migration work does not happen on the critical answer path.

If product-hardening changes touch the realtime path, rerun the controlled latency benchmark.

---

# 11. Reliability boundary

Engineering completion requires:

- full backend / frontend / desktop suites;
- Playwright functional;
- visual regression;
- accessibility;
- packaged smoke;
- clean-install replay;
- 100-session synthetic reliability;
- 3-hour-equivalent soak;
- runtime UI evidence.

Real multi-hour participant sessions remain external.

---

# 12. Release semantics

v1.4 may be released when engineering gates are green even while:

```text
REAL_USER_EVIDENCE_PENDING
```

remains true.

Allowed release statement:

```text
V1_4_ENGINEERING_COMPLETE
PRODUCT_VALIDATION_INFRA_COMPLETE
REAL_USER_EVIDENCE_PENDING
```

Not allowed without participants:

```text
V1_4_REAL_VALIDATION_COMPLETE
PMF PROVEN
REAL_INTERVIEW_TRANSFER PROVEN
```

---

# 13. Future Personal Conversation Intelligence

v1.4 does not productize Meeting.

The v1.3-R2 future-profile contracts remain authoritative:

```text
Interview Profile        current
Conversation Profile     future
```

Future-compatible concepts remain:

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

No Meeting top-level navigation is added in v1.4.

---

# 14. Definition of Done

`V1_4_ENGINEERING_COMPLETE` requires all of:

1. A–F validation signals implemented and locally inspectable;
2. Reflection → Next Focus authoritative;
3. friction audit within budgets;
4. 7-day / 30-session / 100-session synthetic continuity green;
5. 3-hour-equivalent soak green;
6. migration + export/delete integrity green;
7. no Verified Core regression;
8. full CI green;
9. packaged Windows build green;
10. clean-install replay green;
11. version-consistent v1.4.0 artifacts;
12. GitHub Release + SHA256;
13. final Reality Report.

Real-user evidence is a separate gate and must remain honest.
