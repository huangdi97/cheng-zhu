# Chengzhu v2 Stable Promotion Evidence Gate
## From public beta.2 to stable-review eligibility

**Status**: CANONICAL ACCEPTANCE POLICY  
**Scope**: Project Sync + Design Review first  
**Important**: PASS does not publish a stable release and does not prove PMF.

---

## 1. Why a separate gate is required

beta.2 already proves:

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

| Metric | Gate | Minimum labeled n |
| --- | ---: | ---: |
| Opportunity Precision | >= 0.80 | 30 |
| Interruption Regret | <= 0.15 | 30 |
| Source Attribution Accuracy | >= 0.95 | 30 |
| Recall Precision | >= 0.90 | 20 |
| Useful Silence Rate | >= 0.80 | 30 |
| Direct Question Precision | >= 0.90 | 20 |
| Direct Question Recall | >= 0.85 | 20 |
| Decision/Commitment State Precision | >= 0.90 | 30 |
| Continue Write-back Accuracy | >= 0.95 | 20 |
| Mean Cognitive Load Delta | <= -0.25 | 15 |
| Space Reuse Intent Rate | >= 0.70 | 15 |

A metric below its sample floor is failure, not “N/A but okay”.

Thresholds are frozen in:

`docs/evals/V2_CONVERSATION_STABLE_PROMOTION_POLICY.json`

They must not be lowered after seeing a failing pilot merely to create a PASS.

---

## 5. Required attestations

The local pilot manifest must attest:

- AUTHORIZED_REAL_USE;
- NO_SYNTHETIC_ROWS_IN_HUMAN_EVAL;
- RAW_LABELS_KEPT_LOCAL;
- NO_CRITICAL_PRIVACY_INCIDENT;
- NO_KNOWN_DATA_LOSS.

Critical incidents must equal zero.

This remains a local/user-operated attestation boundary; the script does not verify human identity.

---

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
