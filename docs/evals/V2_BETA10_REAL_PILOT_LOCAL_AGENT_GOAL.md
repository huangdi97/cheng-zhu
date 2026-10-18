# Chengzhu v2.0.0-beta.10 Real Pilot → Stable Readiness Local Agent GOAL

**Status**: CANONICAL LOCAL EXECUTION HANDOFF  
**Public pilot runtime**: `v2.0.0-beta.10`  
**Published source/tag SHA**: `a6a673326f64e1b6b78e06992e1e2a196bab9076`  
**Stable Policy**: `v2.0-R1-stable-promotion-8`  
**Pilot Workspace**: `v2.0-R1-pilot-workspace-7`  
**Product schema**: `v13`

This handoff exists for the phase that cannot be completed by repository-only engineering:

```text
packaged Beta
→ authorized real Project Sync / Design Review use
→ explicit self-report + independent human review
→ frozen Workspace v7
→ Stable Policy v8
→ NO_GO defect/evidence report
or
→ PASS Stable release-review handoff
```

It does **not** authorize a new feature cycle, a new prerelease, Stable publication, or any real-user / PMF claim.

## 1. Truth boundary

Always preserve:

```text
Session exists != authorized real use
consent_ack != independently verified consent
user_ref != verified identity
self-report != independent review
Stable Gate PASS != Stable release
Stable release != PMF
```

Never manufacture:

```text
REAL_USER_VALIDATED = TRUE
V2_STABLE_RELEASE = TRUE
PMF_PROVEN = TRUE
```

## 2. Verify repository and release truth first

Before modifying code:

```bash
git fetch --all --tags --prune
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
git tag --points-at a6a673326f64e1b6b78e06992e1e2a196bab9076
```

Verify:

- `frontend/package.json` still expresses the current public Beta truth;
- `docs/releases/V2_0_0_BETA_10_PUBLICATION_PROVENANCE.md` exists;
- `docs/evals/V2_CONVERSATION_REAL_PILOT_RUNBOOK.md` remains the operator source of truth;
- product schema is 13;
- no uncommitted/local source changes are mixed into evidence tooling.

If repository truth differs from this file, reconcile against current `main` + release provenance instead of forcing this file to be true.

## 3. Use the packaged beta.10 runtime for participants

Participant-facing Sessions must use the **published beta.10 packaged Windows runtime**.

Do not substitute:

- dev server;
- source-only Electron runtime;
- older Beta;
- locally modified binary;
- synthetic Sessions.

Verify the downloaded package against the published SHA256/provenance and preserve that package identity in pilot records.

## 4. Pilot profiles and acceptance floors

Only:

```text
PROJECT_SYNC
DESIGN_REVIEW
```

For **each profile**, current Stable Policy requires at least:

```text
>= 5 distinct pseudonymous users
>= 20 authorized real Sessions
>= 3 cross-session Spaces
>= 3 authorized Sessions in each qualifying cross-session Space
same Space -> same pseudonymous user_ref
```

A mixed-user Space is not longitudinal evidence. Split or exclude it.

## 5. Privacy and participant discipline

For each real participant:

1. assign a stable local pseudonym such as `pilot-user-01`;
2. never use name/email/phone/direct identifiers in `user_ref`;
3. obtain real-world authorization/consent as required outside the product;
4. do not describe product `consent_ack` as independently verified consent;
5. keep raw transcripts, source excerpts and reviewer files on the authorized local path;
6. do not disable retention to increase sample counts.

## 6. Before every Session

- use the correct participant-specific Conversation Space;
- choose the intended profile;
- select intended Sources / Quick Notes / connector snapshots only;
- run Preflight;
- freeze the Session Pack;
- verify Pack ↔ Session identity;
- verify intended audio/capture path and AI-assistance/privacy policy;
- start Live only after these checks.

The Frozen Session Pack must not mutate silently after Start.

## 7. During Session

Preserve:

```text
Confirmed Truth
!= AI Candidate / Inference
!= Quick Note
!= Guidance
!= Human Coach Advice
```

`SILENT` remains a first-class product decision.

Do not mix manual Guidance-Lab events into automatic runtime metric populations. Do not rewrite capture-time Direct Question predictions or Guidance-origin provenance.

## 8. Immediately after Session

Complete the in-product Quick Debrief while memory is fresh.

Only explicit user-entered labels are human self-report. Do not convert clicks, pins, dismissals or other behavioral proxies into quality labels.

Objective metrics remain bound to the label sources allowed by Stable Policy v8, generally `INDEPENDENT_HUMAN_REVIEW`.

## 9. Inspect cohort structure

```bash
python scripts/v2_conversation_pilot_workspace.py inspect \
  --db <CHENGZHU_HOME>/data/product.db

python scripts/v2_conversation_pilot_workspace.py inspect \
  --db <CHENGZHU_HOME>/data/product.db \
  --eligible-only
```

Use this for ended/active status, profile, consent acknowledgement, Frozen Session Pack verification, Quick Debrief completeness and structural blockers.

Do not open raw transcript text merely to decide cohort membership.

## 10. Run local migration/tooling sanity

```bash
python scripts/v2_local_migration_matrix.py \
  --out artifacts/validation/v2-migration-matrix.json
```

Require:

```text
latest_schema_version = 13
passed = true
```

This is engineering evidence only.

## 11. Freeze Workspace v7

After selecting a legitimate real cohort:

```bash
python scripts/v2_conversation_pilot_workspace.py init \
  --db <CHENGZHU_HOME>/data/product.db \
  --session <SESSION_A>=pilot-user-01 \
  --session <SESSION_B>=pilot-user-01 \
  --session <SESSION_C>=pilot-user-02 \
  --out-dir <LOCAL_PRIVATE_PATH>/pilot-YYYY-MM
```

Never overwrite an existing workspace.

Expected core files:

```text
workspace.json
selected-cohort.snapshot.json
stable-promotion-policy.json
pilot-manifest.draft.json
independent-review.seed.jsonl
self-report.jsonl
README.md
```

Workspace v7 must freeze cohort structure, Pack identity/digest, policy bytes/hash, evaluator toolchain fingerprints, packaged runtime/source provenance, Python exact patch version, resolved packages and exact wheel SHA256 set.

If provenance drifts, fail closed. Do not regenerate old evidence under new code.

## 12. Independent review

Never edit `independent-review.seed.jsonl` in place.

Create reviewer copies such as:

```text
reviewer-a.jsonl
reviewer-b.jsonl
```

Reviewers may edit only human fields allowed by the schema. They must not change session/space/profile/event/timestamp, predictions, source refs, detector version, Guidance origin, runtime provenance or frozen system payloads.

Where policy requires it:

```text
label_source = INDEPENDENT_HUMAN_REVIEW
```

Policy v8 requires complete coverage of the frozen Stable-eligible event × metric population. Do not stop labeling when a favorable subset reaches `min_n`.

## 13. Finalize authorized cohort

Only when the operator can make every attestation truthfully:

```bash
python scripts/v2_conversation_pilot_workspace.py finalize \
  --db <CHENGZHU_HOME>/data/product.db \
  --workspace <LOCAL_PRIVATE_PATH>/pilot-YYYY-MM \
  --critical-incidents 0 \
  --attest AUTHORIZED_REAL_USE \
  --attest NO_SYNTHETIC_ROWS_IN_HUMAN_EVAL \
  --attest RAW_LABELS_KEPT_LOCAL \
  --attest NO_CRITICAL_PRIVACY_INCIDENT \
  --attest NO_KNOWN_DATA_LOSS
```

The agent must not make an attestation on behalf of a human when it cannot establish it.

If cohort membership or selected Session structure changed, create a new workspace.

## 14. Evaluate Stable Policy v8

```bash
python scripts/v2_conversation_pilot_workspace.py evaluate \
  --workspace <LOCAL_PRIVATE_PATH>/pilot-YYYY-MM \
  --review reviewer-a.jsonl \
  --review reviewer-b.jsonl
```

Expected immutable output:

```text
evaluation/
  human-report.json
  human-report.md
  stable-readiness.json
  stable-readiness.md
  evaluation-manifest.json
```

Archive the entire workspace as one evidence unit.

## 15. NO_GO behavior

`NO_GO` is expected until the real pilot is large and strong enough.

Do **not** respond by:

- lowering thresholds;
- changing cross-session definitions;
- relabeling self-report as independent review;
- adding synthetic Sessions;
- disabling retention;
- re-running newer detectors on historical transcript;
- copying reviewed truth into prediction fields;
- mixing manual Guidance Lab into automatic populations;
- producing beta.11 merely because beta.10 did not pass.

Instead classify the blocker:

```text
A. product-quality defect
B. evidence coverage deficit
C. cohort-size deficit
D. privacy/authorization blocker
E. runtime/provenance mismatch
F. reviewer disagreement / label-quality problem
```

Only a material product/correctness/release defect should trigger a scoped source fix and a fresh decision on whether another prerelease is justified.

## 16. PASS behavior

A PASS means only:

```text
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW
```

Then:

```bash
python scripts/v2_conversation_stable_review_handoff.py \
  --workspace <LOCAL_PRIVATE_PATH>/pilot-YYYY-MM \
  --out-dir <LOCAL_PRIVATE_PATH>/pilot-YYYY-MM-stable-review
```

Expected:

```text
stable-review-handoff.json
stable-review-handoff.md
SHA256.json
```

Do not publish Stable.

## 17. Human Stable release boundary

The next step remains human-controlled:

```text
PASS handoff
→ v2_stable_release_review_decision.py init
→ human reviews every required check
→ finalize
→ GO / NO_GO
```

The agent may prepare evidence and identify missing checks. It must not invent human review evidence or silently issue GO.

Any later `main` commit invalidates an exact-candidate Stable authorization and requires re-binding/review.

## 18. External connector evidence

For every provider, report independently:

```text
PROVIDER_CODE_AVAILABLE
REAL_ACCOUNT_REPLAY
REQUIRED_SCOPES
READ_SYNC
WRITE_EXECUTION
UNKNOWN_OUTCOME_RECONCILIATION
```

If real credentials/accounts are unavailable, report the exact blocker (for example `BLOCKED_ACCOUNT`). Mock/test PASS is not `REAL_ACCOUNT_VALIDATED`.

Never expose secrets in logs, screenshots, artifacts or Git commits.

## 19. Source-code rule during one frozen cohort

Default: **do not change product code while collecting one frozen cohort**.

If a material defect appears:

1. preserve failing evidence;
2. reproduce outside the frozen workspace;
3. create a narrowly scoped branch/PR;
4. add regression coverage;
5. run full CI;
6. merge only when green;
7. explicitly decide whether the defect requires a new prerelease;
8. never mix pre-fix and post-fix runtime evidence as if homogeneous.

## 20. Human-only stop conditions

Stop and report precisely when blocked by:

- real participant recruitment;
- real authorization/consent;
- real Windows audio/GUI behavior;
- real meeting content;
- independent reviewer judgment;
- external account credentials / OAuth publication gates;
- human Stable release GO;
- legal/privacy decisions outside repository truth.

A precise human blocker is a successful stop; do not fabricate completion.

## 21. Required final local-Agent report

Return:

```text
1. exact repo HEAD + origin/main
2. beta.10 package identity + verified SHA256
3. product schema version
4. migration-matrix result
5. participant-facing runtime used
6. Project Sync cohort counts
7. Design Review cohort counts
8. cross-session Space/user mapping summary
9. Quick Debrief completion counts
10. independent-review coverage counts
11. workspace/toolchain/runtime provenance
12. finalize result
13. Stable Policy v8 result
14. failed metrics / thresholds if NO_GO
15. handoff hashes if PASS
16. privacy/security incidents
17. connector real-account status
18. blockers requiring human action
19. whether a source-code fix was required
20. whether a new prerelease is actually justified
```

End with exactly one of:

```text
REAL_PILOT_NOT_STARTED
REAL_PILOT_IN_PROGRESS
REAL_PILOT_BLOCKED_HUMAN_INPUT
STABLE_READINESS_NO_GO
STABLE_READINESS_PASS_HANDOFF_READY
```

Never end with `V2_STABLE_RELEASE = TRUE` unless a separately verified public Stable release has actually occurred.
