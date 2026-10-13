# Chengzhu v2.0.0-beta.7

Status: **PRERELEASE CANDIDATE — not published until the exact green main SHA completes the release workflow.**

## Why beta.7 exists

v2.0.0-beta.6 completed the real-pilot operationalization path, but post-publication Stable Gate audit found one longitudinal cohort correctness defect in packaged Policy v6:

```text
same Space
+ >= 3 authorized Sessions
+ different pseudonymous user_ref values
→ could still count as one cross-session Space
```

That is not valid evidence of Personal Conversation Intelligence continuity for one user.

beta.7 freezes the current hardened main so the public prerelease and the operator-side Stable Gate use the same corrected **Stable Promotion Policy v7** before any real pilot is treated as Stable-review evidence.

This is a correctness release, not feature expansion.

## Stable Policy v7

Policy v7 keeps all v6 numerical quality thresholds, every `min_n`, required launch profiles, profile user/session/space floors, label-source rules, unique-event-per-metric sample units, and evidence-integrity requirements unchanged.

The correction is:

```text
QUALIFYING_CROSS_SESSION_SPACE =
  same space_id
  + same pseudonymous user_ref
  + >= 3 authorized Sessions

MIXED_USER_SPACE = FAIL_CLOSED
```

The rule is enforced twice:

- the authorized pilot manifest builder rejects one Space assigned to multiple `user_ref` values;
- the Stable readiness evaluator independently revalidates the same invariant.

`user_ref` remains a local pseudonymous key. Chengzhu does not verify human identity, reviewer independence, real-world authorization, or participant consent.

## Included beta.6 validation infrastructure

beta.7 retains the beta.6 real-pilot path:

- local Quick Debrief immediately after Session end;
- schema v10-v12 Pilot Evidence Bridge;
- immutable AI prediction and Direct Question provenance;
- feedback retention integrity;
- TRANSCRIPT_AUTO Guidance/SILENT provenance;
- authorized pilot manifest + privacy-minimized Session inventory;
- selected-cohort logical snapshots that are WAL-safe;
- finalize-time double cohort revalidation;
- frozen independent-review seed binding;
- immutable event/prediction/runtime-origin checks;
- unique-event-per-metric Stable sample units;
- scope-aware frontend / Electron dependency-security gates;
- fail-closed release hold and stale-main publication guards.

## Release-page truth hardening

The release pipeline also includes the post-beta.6 publication-page correction: after publication, the GitHub Release page is rendered from authoritative public tag/source/channel facts rather than leaving candidate/future-tense status as the visible release truth.

Already-published historical tags remain immutable.

## What beta.7 does not claim

```text
V2_STABLE_RELEASE = FALSE
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
REAL_USER_IDENTITY_SYSTEM_VERIFIED = FALSE
REVIEWER_INDEPENDENCE_SYSTEM_VERIFIED = FALSE
PARTICIPANT_CONSENT_SYSTEM_VERIFIED = FALSE
```

A Stable Gate PASS, when real evidence eventually exists, means only:

```text
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW
```

A separate human release decision is still required.

## Intended next step

Use beta.7 for the first authorized real Project Sync / Design Review pilot:

```text
real Session
→ Quick Debrief
→ privacy-minimized cohort selection
→ frozen policy-v7 workspace
→ independent review bound to frozen seed
→ source-aware human aggregation
→ policy-v7 Stable readiness
→ human release review
```

Do not create beta.8 merely to manufacture progress. A later prerelease is justified only by a real pilot/runtime defect, new provider evidence that changes the distributable product, or another material release/evidence correctness fix.
