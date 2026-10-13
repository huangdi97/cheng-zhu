# Chengzhu v2.0.0-beta.9

Status: **PUBLISHED PRERELEASE** · exact source/tag SHA `146db913a4467e179d547b37fc006753f64655bb` · Main CI #1021 SUCCESS · Release #328 SUCCESS · Stable Latest remains `v1.4.2`.

## Why beta.9 exists

v2.0.0-beta.8 correctly packages Stable Promotion Policy v8 and requires complete frozen eligible event×metric coverage. A post-publication audit then found a separate reproducibility gap in the real-pilot workspace:

```text
workspace freezes policy/cohort/seed/self-report
→ evaluator implementation later changes
→ same frozen evidence can be re-evaluated by different code
→ result may differ without the workspace proving evaluator drift
```

beta.9 exists to package **pilot evaluator toolchain provenance** before new real-pilot evidence is treated as canonical Stable-readiness evidence.

This is an evidence-reproducibility release, not feature expansion.

## Pilot workspace contract v5

New Stable-readiness workspaces freeze:

```text
PILOT_WORKSPACE_CONTRACT = v2.0-R1-pilot-workspace-5
PILOT_TOOLCHAIN_FINGERPRINT_CONTRACT = v2.0-R1-pilot-toolchain-1
STABLE_PROMOTION_POLICY = v2.0-R1-stable-promotion-8
```

The workspace records SHA256 for the exact evaluator toolchain used at initialization:

- `scripts/v2_conversation_pilot_workspace.py`
- `scripts/v2_conversation_label_seed.py`
- `scripts/v2_conversation_feedback_export.py`
- `scripts/v2_conversation_human_eval.py`
- `scripts/v2_conversation_pilot_manifest.py`
- `scripts/v2_conversation_stable_readiness.py`

## Drift behavior

Finalize and evaluate now fail closed when the current evaluator toolchain differs from the frozen workspace fingerprint:

```text
frozen workspace toolchain
!= current evaluator toolchain
→ NO RE-EVALUATION
→ use the exact original checkout/toolchain
  or create a new workspace
```

Historical workspaces are not silently upgraded.

The evaluation manifest records the toolchain provenance used for the result so a future reviewer can distinguish evidence drift from evaluator drift.

## Stable Policy v8 remains unchanged

beta.9 does **not** alter:

- numerical quality thresholds;
- `min_n` values;
- required launch profiles;
- per-profile user/session/Space floors;
- >=3 Session longitudinal Space requirement;
- same pseudonymous `user_ref` binding;
- allowed label-source rules;
- `UNIQUE_EVENT_PER_METRIC` sample unit;
- `COMPLETE_FROZEN_ELIGIBLE_POPULATION` coverage requirement.

beta.9 only makes the evaluator implementation itself part of frozen provenance.

## Defense in depth retained from beta.8

beta.9 retains the full beta.8 real-pilot/evidence-integrity stack:

- local Quick Debrief;
- schema v10-v12 Pilot Evidence Bridge;
- immutable AI prediction and Direct Question provenance;
- feedback-retention integrity and orphan-label cleanup;
- TRANSCRIPT_AUTO Guidance/SILENT provenance;
- authorized pilot manifest + privacy-minimized Session inventory;
- WAL-safe selected-cohort snapshot;
- finalize-time cohort revalidation;
- frozen independent-review seed binding;
- unique event × metric sample units;
- single-user longitudinal Space binding;
- complete frozen Stable metric coverage;
- dependency-security gates;
- explicit release hold + stale-main publication guard;
- exact-SHA Windows build / clean install / download-back / tag-source provenance gates.

## What beta.9 does not claim

```text
V2_STABLE_RELEASE = FALSE
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
REAL_USER_IDENTITY_SYSTEM_VERIFIED = FALSE
REVIEWER_INDEPENDENCE_SYSTEM_VERIFIED = FALSE
PARTICIPANT_CONSENT_SYSTEM_VERIFIED = FALSE
```

A future Stable Gate PASS means only:

```text
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW
```

It still requires a separate human release decision and does not prove PMF.

## Intended next step

After beta.9 is published, use it as the canonical prerelease baseline for **new** Stable-readiness pilot workspaces:

```text
authorized real Project Sync / Design Review Sessions
→ Quick Debrief
→ workspace v5 freezes cohort + policy + seed + evaluator toolchain
→ independent review / permitted self-report
→ complete Stable metric coverage
→ Policy v8 Stable readiness
→ human release review
```

Existing beta.8 workspaces remain historical evidence. Do not mutate them to claim workspace-v5 toolchain provenance after the fact.
