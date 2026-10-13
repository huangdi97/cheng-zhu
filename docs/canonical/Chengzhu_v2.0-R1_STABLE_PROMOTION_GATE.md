# Chengzhu v2 Stable Promotion Evidence Gate
## From public beta.5 to stable-review eligibility

**Status**: CANONICAL ACCEPTANCE POLICY  
**Scope**: Project Sync + Design Review first  
**Important**: PASS does not publish a stable release and does not prove PMF.

---

## 1. Why a separate gate is required

beta.5 already proves:

- public downloadable prerelease;
- exact-SHA release provenance;
- packaged Windows runtime;
- clean-install / download-back evidence;
- Conversation UI/runtime engineering closure.

Those facts cannot answer:

- are proactive opportunities correct often enough?
- is interruption regret acceptably low?
- is silence useful?
- does cross-session continuity reduce cognitive load?
- do users actually keep reusing the same Space?

Stable promotion therefore needs product evidence that CI cannot produce.

---

## 2. Gate layers

```text
Layer A — Engineering/release evidence
Layer B — Authorized real-use pilot
Layer C — Human-labeled quality metrics
Layer D — Stable release review
```

This evaluator covers **B + C** only.

Passing it returns:

```text
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW
```

It never returns:

```text
V2_STABLE_RELEASE = TRUE
PMF_PROVEN = TRUE
```

---

## 3. Pilot floor

Both launch-wedge profiles must independently satisfy:

### Project Sync
- distinct users >= 5
- real sessions >= 20
- cross-session Spaces (same Space + same pseudonymous user_ref + >=3 authorized Sessions) >= 3

### Design Review
- distinct users >= 5
- real sessions >= 20
- cross-session Spaces (same Space + same pseudonymous user_ref + >=3 authorized Sessions) >= 3

These are **release acceptance floors**, not scientific population estimates.

Synthetic, CI, mock and Dry Run sessions do not count.

---

## 4. Human-label thresholds

| Metric | Gate | Minimum labeled n | Stable-eligible label source |
| --- | ---: | ---: | --- |
| Opportunity Precision | >= 0.80 | 30 | self-report or independent review |
| Interruption Regret | <= 0.15 | 30 | local explicit self-report |
| Source Attribution Accuracy | >= 0.95 | 30 | independent human review |
| Recall Precision | >= 0.90 | 20 | independent human review |
| Useful Silence Rate | >= 0.80 | 30 | self-report or independent review |
| Direct Question Precision | >= 0.90 | 20 | independent human review |
| Direct Question Recall | >= 0.85 | 20 | independent human review |
| Decision/Commitment State Precision | >= 0.90 | 30 | independent human review |
| Continue Write-back Accuracy | >= 0.95 | 20 | independent human review |
| Mean Cognitive Load Delta | <= -0.25 | 15 | local explicit self-report |
| Space Reuse Intent Rate | >= 0.70 | 15 | local explicit self-report |

A metric below its sample floor is failure, not “N/A but okay”. Sample size and threshold are computed only from that metric's frozen `allowed_label_sources`; `UNSPECIFIED` rows and disallowed sources are ignored for Stable promotion even when the overall aggregate looks good.

Under policy v6, `n` is the number of **unique product event × metric observations**, not the number of reviewer annotations. If Alice and Bob both label the same Guidance event's usefulness, that is still one product event, not two samples. The Stable aggregate fails closed on duplicate event/metric observations until the operator resolves/selects a single label. This applies across reviewers **and** across allowed label sources, preventing self-report + independent review of the same metric/event from double-counting.

Thresholds and metric populations are frozen in:

`docs/evals/V2_CONVERSATION_STABLE_PROMOTION_POLICY.json`

Current repository evaluator policy = `v2.0-R1-stable-promotion-8`. Numerical quality thresholds, every `min_n` number, and the profile floors (5 users / 20 Sessions / 3 cross-session Spaces per launch profile) are unchanged from policy v6. v5 fixed the >=3-Session cross-session floor, v6 froze `UNIQUE_EVENT_PER_METRIC`, and v7 closes the remaining longitudinal-cohort ambiguity: one qualifying Conversation Space must bind to exactly one pseudonymous `user_ref` and contain >=3 authorized Sessions for that same user. A mixed-user Space fails cohort integrity and cannot count as continuity. Published beta.6 remains immutable and correctly contains policy v6; policy v7 is post-beta.6 source truth until a later release is explicitly justified. Thresholds/floors must not be lowered, and sample/cohort populations must not be broadened after seeing a failing pilot merely to create a PASS.

---

## 5. Required attestations

The local pilot manifest must attest:

- AUTHORIZED_REAL_USE;
- NO_SYNTHETIC_ROWS_IN_HUMAN_EVAL;
- RAW_LABELS_KEPT_LOCAL;
- NO_CRITICAL_PRIVACY_INCIDENT;
- NO_KNOWN_DATA_LOSS.

Critical incidents must equal zero.

Policy v5 continues to require manifest contract `v2.0-R1-pilot-cohort-2`. Instead of hand-entering `distinct_users / sessions / cross_session_spaces`, each required profile enumerates authorized real sessions:

```json
{
  "session_id": "cv_...",
  "space_id": "cs_...",
  "user_ref": "local-pseudonym-01"
}
```

The evaluator derives all three profile-floor counts from those rows. `user_ref` must be a stable **local pseudonym**, not a name/email and not a claim that Chengzhu verified identity. `AUTHORIZED_REAL_USE` remains the user/operator attestation that these rows actually came from authorized real conversations.

This remains a local/user-operated attestation boundary; the script does not verify human identity.

---

## 5.1 Pilot feedback evidence bridge

beta.3 之后的源码 runtime 增加了本机显式 feedback bridge，但它只减少真实 pilot 的采集摩擦，不降低本 Gate 的独立证据要求：

```text
Continue self-report
→ local conversation_human_feedback
→ explicit feedback exporter
→ human-eval aggregate
```

同时 AI_EXTRACTED item 在 schema v10 起冻结 immutable prediction snapshot，防止 Continue review 后的 state/type 被反向当成模型 prediction。

以下仍然不成立：

```text
SELF_USER feedback row == verified external user
USED / PINNED == useful
DISMISSED == wrong
reviewed final state == original prediction
human-report == authorized real pilot manifest
```

Stable review 仍必须同时有 authorized pilot manifest、足够的独立 human labels、零 critical incident，并满足 frozen policy thresholds。

## 5.2 Direct Question provenance gate

schema v11 closes the remaining Direct Question evaluation-replay gap.

```text
final transcript
→ freeze detector decision + detector_version + AI-assistance eligibility at capture time
→ only eligible=true rows enter the review population
→ label seed preserves predicted=true / false
→ independent reviewer supplies actual=true / false
→ human eval computes precision + recall
```

Stable review accepts Direct Question Precision / Recall only from `INDEPENDENT_HUMAN_REVIEW`. A versioned snapshot with `eligible=false` is explicitly outside the metric population (for example automatic transcript guidance was disabled by AI_LIMITED / AI_FORBIDDEN); it is not an evaluation failure. A transcript without a capture-time versioned prediction is `prediction_unavailable` and contributes to neither metric.

The following are explicitly forbidden:

```text
re-run current detector on old transcript
infer all negative predictions from absence of a Guidance event
replace missing predicted with reviewer actual
silently mix detector versions without preserving row-level provenance
```

This makes historical metrics reproducible when the detector evolves; it does not make the detector scientifically validated and does not change the real-user / PMF boundary.

## 5.3 Auto-runtime evidence + denominator integrity

schema v12 adds immutable `conversation_guidance_event.origin_json` so Stable review can distinguish the product's real automatic TRANSCRIPT path from the advanced/manual Guidance validation lab.

```text
final eligible PRIMARY_AUDIO transcript
→ exact transcript_segment_id
→ automatic Guidance decision
   ├─ SHOWN
   └─ SILENT
→ immutable origin.kind = TRANSCRIPT_AUTO
```

Stable population rules:

- Opportunity Precision / Interruption Regret / Source Attribution Accuracy / Recall Precision: only v12 `TRANSCRIPT_AUTO` Guidance rows with exact transcript provenance;
- Useful Silence: only `TRANSCRIPT_AUTO + decision_class=ARBITER`;
- `MODE_FORCED / PROFILE_FORCED / PROVENANCE_FORCED` silence is audit/policy evidence, not Useful Silence;
- manual Guidance Lab and pre-v12 unclassified Guidance are excluded;
- Decision/Commitment State Precision denominator = immutable predictions whose `predicted_type` is `Decision / Commitment / Task`; other predicted truth types cannot dilute the metric.

No threshold was lowered by this correction. Historical events are not reclassified from reason strings.

## 5.4 Authorized cohort + metric-profile binding

Policy v4 introduced authorized cohort + metric-profile binding; policy v5 preserves that contract and fixes the cross-session Space qualification bug before real pilot evidence is accepted.

Old failure mode:

```text
human-report from cohort A
+
manifest says "20 sessions / 5 users" for cohort B
+
good labels from an unrelated Conversation profile
→ structurally possible to satisfy independent checks
```

Current gate:

```text
human-label row
→ session_id + profile + space_id
→ HUMAN_EVAL report cohort contract v4
→ exact membership in authorized pilot manifest v2
→ only PROJECT_SYNC / DESIGN_REVIEW
→ only metric.allowed_label_sources
→ policy threshold
```

Hard rules:

- the same `session_id` cannot map to two profiles or Spaces;
- every human-report Session must match one enumerated manifest Session by `session_id + profile + space_id`;
- profile floors are derived from unique manifest Sessions, local pseudonymous `user_ref` values, and Spaces containing at least three authorized Sessions;
- labels from Presentation/Q&A, 1:1, Client Call, Negotiation or any other non-target profile cannot inflate the v2 Stable metric score;
- every Stable metric must have at least one policy-allowed sample from **both** Project Sync and Design Review; one launch profile cannot stand in for an entirely unmeasured other profile;
- a timezone-aware pilot period is mandatory;
- old count-only manifests fail closed under policy v4+; policy v5 additionally fails closed if `cross_session_space_min_sessions < 3`.

This is evidence consistency, not cryptographic identity attestation and not PMF proof.

## 5.5 Cross-session Space qualification integrity

Canonical pilot floor has always meant:

```text
cross-session Space
= one authorized Space with >= 3 authorized Sessions
```

The policy-v4 evaluator implementation accidentally used `len(session_ids) >= 2`. That could let three 2-Session Spaces satisfy `cross_session_spaces >= 3`, even though the canonical requirement was not met.

Policy v5 closes this before real pilot evidence is accepted:

```text
cross_session_space_min_sessions = 3
2-Session Space = NOT cross-session for Stable Gate
3+ Session Space = eligible
policy value < 3 = fail closed
```

No quality threshold, user floor, total Session floor or required cross-session-Space count is lowered. This is a denominator/cohort-definition correction, not a post-hoc attempt to create a PASS.

## 5.6 Cross-session user continuity integrity

Policy v7 tightens the meaning of longitudinal Conversation continuity without changing any numerical threshold:

```text
qualifying cross-session Space
=
same space_id
+ exactly one pseudonymous user_ref
+ >= 3 authorized Sessions for that user
```

The old policy-v6 failure mode was structurally possible:

```text
Space A
├─ Session 1 → pilot-user-01
├─ Session 2 → pilot-user-02
└─ Session 3 → pilot-user-03

old count: cross_session_spaces += 1
v7: cohort integrity failure
```

This matters because Chengzhu's continuity claim is personal/longitudinal. Three different people each using a shared Space once do not prove that any one user received cross-session value.

Hard rules:

- the Pilot Manifest builder rejects one `space_id` mapped to multiple `user_ref` values;
- Stable readiness independently rechecks the same invariant;
- mixed-user Spaces are not merely excluded from the count—they make cohort integrity fail closed;
- `user_ref` remains a local pseudonym, not verified identity;
- this correction changes evidence qualification only; it does not change beta.6 binaries, quality thresholds, `min_n`, profile floors, Stable status or PMF claims.

## 5.7 Recommended operator workflow

The low-level scripts remain canonical building blocks, but the recommended real-pilot path is now the fail-closed Pilot Workspace orchestrator:

```text
v2_conversation_pilot_workspace.py init
→ independent review
→ v2_conversation_pilot_workspace.py finalize
→ v2_conversation_pilot_workspace.py evaluate
```

It freezes the exact policy snapshot, limits exports to explicitly selected Sessions, records local source/evidence hashes, refuses frozen-input drift and refuses overwrite of an existing workspace/evaluation. It does not create new evidence semantics and does not verify identity, real-world authorization, participant consent or PMF.

Full operator procedure:

`docs/evals/V2_CONVERSATION_REAL_PILOT_RUNBOOK.md`

## 5.4 Complete Stable metric coverage / anti-selection-bias gate

Post-beta.7 attack-style audit found a material Stable-evidence correctness gap in Policy v7: frozen seed provenance and submitted-row binding were strong, but the evaluator still allowed the **labeled subset** to define a metric denominator. That leaves selection bias across both independent review and in-product self-report:

- an independent reviewer could omit unfavorable objective events;
- a user could leave high-regret Guidance unlabeled;
- only favorable Session Outcome / Quick Debrief rows could be completed;
- for metrics allowing either self-report or independent review, an operator could select whichever source produced the more favorable subset.

Policy v8 closes this without changing any numerical threshold, `min_n`, profile floor, label-source vocabulary, cross-session requirement or unique-event sample unit.

For **every Stable metric**, Chengzhu derives the full eligible event×metric population from the frozen seed **before human labels are examined**. Each required pair must then be covered by at least one label source already allowed by that metric:

```text
frozen eligible product event
→ derive Stable metric membership from immutable prediction/runtime provenance
→ look up that metric's allowed_label_sources
→ require the metric-specific human label fields
→ coverage only if one allowed source supplies a complete label
→ all required event×metric pairs covered before threshold/min_n evaluation
```

Examples:

- auto-runtime PROACTIVE Guidance → `useful` / `interruption_regret`;
- auto-runtime Guidance → `source_correct`;
- RECALL Guidance → `recall_correct`;
- ARBITER SILENT decision → `silence_correct`;
- Direct Question frozen prediction → `actual`;
- predicted Decision / Commitment / Task → `actual_type + actual_state`;
- Continue → `writeback_accurate`;
- Session Outcome → `cognitive_load_delta + would_reuse_space`.

A missing row, null required label, disallowed label source, or unresolved duplicate allowed-source observation remains **missing/invalid coverage**; it cannot disappear from the denominator merely because the operator stopped labeling after a favorable subset reached `min_n`.

The human report must carry:

```text
stable_metric_coverage.contract_version
= v2.0-R1-stable-metric-coverage-1

stable_metric_coverage.policy
= COMPLETE_FROZEN_ELIGIBLE_POPULATION

covered_event_metric_pairs == required_event_metric_pairs
missing_event_metric_pairs == 0
complete == true
```

Otherwise Stable readiness is `NO_GO`.

This closes denominator selection bias. It does **not** prove reviewer identity/independence, participant consent, real-world authorization, Stable release status or PMF.

## 6. Tooling

### Recommended

Use `scripts/v2_conversation_pilot_workspace.py` and the Real Pilot Runbook for end-to-end operator execution.

### Low-level / audit path

The low-level scripts remain useful for inspection/debugging, but under Policy v8 they are **not sufficient by themselves for a Stable PASS** because `stable_metric_coverage` must be derived from the frozen workspace seed + frozen policy before aggregation. The canonical Stable-review path is the workspace orchestrator above.

For audit/debug only:

1. Export local label seed.
2. Human reviewers label real sessions.
3. Aggregate:

```bash
python scripts/v2_conversation_human_eval.py labels.jsonl --out human-report.json
```

4. Generate a **draft** pilot manifest from exact local Session ids plus operator-supplied pseudonymous user refs:

```bash
python scripts/v2_conversation_pilot_manifest.py \
  --db <CHENGZHU_HOME>/data/product.db \
  --session cv_project_01=pilot-user-01 \
  --session cv_design_01=pilot-user-02 \
  --out pilot-manifest.draft.json
```

The draft deliberately cannot satisfy this gate. Review it locally, then rerun with the same authorized Session mapping plus `--finalize`, explicit `--critical-incidents`, and **all five** required `--attest` values.

The builder revalidates from `product.db`:

- `ENDED` status;
- Project Sync / Design Review launch profile;
- Session consent acknowledgement;
- matching Frozen Session Pack;
- exact Session → Space / Profile mapping;
- timezone-aware Session period.

It derives the operator progress summary using the same canonical policy-v5 cross-session rule: one Space counts only with **at least 3 selected authorized Sessions**. It does not verify human identity, real-world authorization, participant consent or PMF.

The static template `docs/evals/v2_conversation_real_pilot_manifest.template.json` is also fail-closed by default and should be treated as structure documentation, not a pre-attested manifest.

5. Evaluate:

```bash
python scripts/v2_conversation_stable_readiness.py \
  human-report.json \
  real-pilot.json \
  --out stable-readiness.json \
  --markdown-out stable-readiness.md
```

`NO_GO` exits non-zero.

---

## 7. What happens after PASS

PASS allows a **stable release review**.

A separate release decision still checks:

- current main CI;
- current packaged evidence;
- current installer/portable hashes;
- clean install;
- code-signing policy;
- known critical bugs;
- privacy/security incidents;
- release notes/public truth;
- rollback plan.

Stable release is a human product/release decision, not a metric script side effect.

---

## 8. PMF boundary

Even stable release does not prove PMF.

PMF needs longer-horizon evidence such as:

- repeat use beyond pilot;
- retention;
- willingness to rely on Chengzhu in important real conversations;
- willingness to pay / organizational adoption where applicable;
- durable value after novelty fades.

This gate intentionally does not model those as a boolean.
