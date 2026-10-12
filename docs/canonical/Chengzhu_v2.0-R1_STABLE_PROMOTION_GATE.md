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
- cross-session Spaces (>=3 sessions in same Space) >= 3

### Design Review
- distinct users >= 5
- real sessions >= 20
- cross-session Spaces (>=3 sessions in same Space) >= 3

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

Thresholds and metric populations are frozen in:

`docs/evals/V2_CONVERSATION_STABLE_PROMOTION_POLICY.json`

Current repository evaluator policy = `v2.0-R1-stable-promotion-5`. Numerical quality thresholds and the profile floors (5 users / 20 Sessions / 3 cross-session Spaces per launch profile) are unchanged from policy v4. v5 fixes one **pre-pilot cohort-semantics bug**: canonical always defined a cross-session Space as at least 3 authorized Sessions in that same Space, while the v4 evaluator implementation incorrectly counted 2-Session Spaces. v5 makes `cross_session_space_min_sessions = 3` machine-readable and fail-closed against lowering below 3. Published beta.5 provenance remains correctly bound to the packaged policy-v4 evaluator; this v5 correction is post-beta.5 source truth and must not be back-attributed to beta.5 binaries. Thresholds must not be lowered, and sample populations must not be broadened, after seeing a failing pilot merely to create a PASS.

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

## 6. Tooling

1. Export local label seed.
2. Human reviewers label real sessions.
3. Aggregate:

```bash
python scripts/v2_conversation_human_eval.py labels.jsonl --out human-report.json
```

4. Fill:

`docs/evals/v2_conversation_real_pilot_manifest.template.json`

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
