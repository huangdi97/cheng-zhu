# Chengzhu v2.0.0-beta.8

Status: **PRERELEASE CANDIDATE — not published until the exact green main SHA completes the full release workflow.**

## Why beta.8 exists

v2.0.0-beta.7 correctly packaged Stable Promotion Policy v7, including single-user longitudinal Space binding. A post-publication attack-style audit then found a separate Stable-evidence correctness gap:

```text
complete frozen event population
→ reviewer labels only a favorable subset
→ labeled subset alone defines the metric denominator
→ metric may pass once min_n is reached
```

That permits selection bias even when seed provenance, reviewer binding, duplicate prevention and source-policy rules are otherwise correct.

beta.8 exists to package **Stable Promotion Policy v8**, which closes that denominator-selection gap before any new real pilot workspace is treated as canonical Stable evidence.

This is an evidence-correctness release, not feature expansion.

## Stable Policy v8

Policy v8 keeps all beta.7 numerical thresholds, every `min_n`, required launch profiles, profile user/session/space floors, >=3-session longitudinal Space requirement, same-user `user_ref` binding, label-source vocabulary and UNIQUE_EVENT_PER_METRIC sample-unit rules unchanged.

New frozen invariant:

```text
stable_metric_coverage_policy
= COMPLETE_FROZEN_ELIGIBLE_POPULATION
```

For every Stable metric, Chengzhu derives the complete eligible event × metric population from the frozen seed **before any submitted label is examined**.

Every required pair must then be completely labeled by at least one source already allowed by that metric policy.

The following fail closed:

- required event/metric row missing;
- required field null;
- only disallowed label source present;
- unresolved mixed-source duplicate;
- favorable-subset labeling that reaches min_n while leaving eligible events unlabeled.

## Frozen metric populations

Policy v8 derives the Stable population only from immutable prediction/runtime provenance:

- auto-runtime PROACTIVE Guidance → usefulness + interruption regret;
- auto-runtime Guidance → Source Attribution;
- RECALL Guidance → Recall Precision;
- automatic ARBITER SILENT decisions → Useful Silence;
- frozen Direct Question predictions → reviewer actual;
- predicted Decision / Commitment / Task → actual type + actual state;
- Continue → write-back accuracy;
- Session Outcome → cognitive-load delta + same-Space reuse intent.

The population is frozen before label values are read.

## Defense in depth retained from beta.7

beta.8 retains the full beta.7 real-pilot/evidence-integrity stack:

- local Quick Debrief;
- schema v10-v12 Pilot Evidence Bridge;
- immutable AI prediction and Direct Question provenance;
- feedback-retention integrity and orphan-label cleanup;
- TRANSCRIPT_AUTO Guidance/SILENT provenance;
- authorized pilot manifest + privacy-minimized Session inventory;
- WAL-safe selected-cohort snapshot;
- finalize-time cohort revalidation;
- frozen independent-review seed binding;
- immutable event/prediction/runtime-origin checks;
- unique event × metric sample units;
- same pseudonymous user binding for qualifying cross-session Spaces;
- dependency-security gates;
- release hold and stale-main publication guards;
- exact-SHA build / clean install / download-back / provenance release gates.

## What beta.8 does not claim

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

Use beta.8 as the canonical prerelease baseline for any **new** Stable-readiness pilot workspace:

```text
authorized real Project Sync / Design Review Session
→ Quick Debrief
→ frozen eligible metric population
→ independent review / permitted self-report
→ 100% required coverage
→ source-aware human aggregation
→ Policy v8 Stable readiness
→ human release review
```

Historical beta.7 remains immutable and valid as an engineering/product Beta, but new Stable-evidence workspaces should not freeze Policy v7 after beta.8 is published.
