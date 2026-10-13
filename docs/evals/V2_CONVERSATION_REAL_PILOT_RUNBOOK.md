# Chengzhu v2 Real Pilot Operator Runbook

**Status**: BETA.7 PUBLISHED · REAL-PILOT OPERATOR WORKFLOW · STABLE POLICY v7  
**Public Beta**: v2.0.0-beta.7  
**Published source/tag SHA**: `dc2188cd6b796b5dca9baf0eac2372da7be5bbf2`  
**Stable v2**: NOT CLAIMED  
**REAL_USER_VALIDATED**: FALSE  
**PMF_PROVEN**: FALSE

This runbook defines the operator path from a real Conversation pilot to a Stable Promotion evidence review.

It does not change any release or evidence claim by itself.

## 1. Preconditions

Use the published `v2.0.0-beta.7` runtime/source with product schema >= v12.

The currently published participant-facing/runtime product is `v2.0.0-beta.7`, which packages Stable Policy v7. New Stable-readiness pilot workspaces should therefore freeze Policy v7 directly from beta.7/current source; historical workspaces initialized under older policies remain historical evidence and must not be rewritten. This runbook represents an operator workflow, not ordinary participant-facing Conversation UI, and its availability does not turn structurally selectable Sessions into authorized real use.

Required launch profiles:

- PROJECT_SYNC
- DESIGN_REVIEW

Stable policy currently requires each profile to satisfy:

- >= 5 distinct pseudonymous users;
- >= 20 authorized real Sessions;
- >= 3 cross-session Spaces;
- each qualifying cross-session Space contains >= 3 authorized Sessions **for the same pseudonymous user_ref**;
- one Space mapped to multiple pilot user_ref values is a cohort-integrity failure, not longitudinal evidence.

These are acceptance floors, not scientific sample-size claims.

## 2. Evidence boundaries

The workflow separates four different facts:

```text
runtime facts
human labels
operator authorization attestations
stable-release decision
```

None substitutes for another.

In particular:

```text
Session exists != authorized real use
consent_ack != system-verified participant consent
user_ref != verified identity
self-report != independent review
Stable Gate PASS != stable release
Stable release != PMF
```

Raw review material may contain transcript/source excerpts and must stay local.

## 3. Inspect machine-verifiable Session structure

Before choosing a cohort, first inspect the local database without opening transcript text or manually querying SQLite:

```bash
python scripts/v2_conversation_pilot_workspace.py inspect \
  --db <CHENGZHU_HOME>/data/product.db
```

To show only rows that pass the manifest builder's machine-verifiable structural checks:

```bash
python scripts/v2_conversation_pilot_workspace.py inspect \
  --db <CHENGZHU_HOME>/data/product.db \
  --eligible-only
```

The inventory intentionally exposes only:

- `session_id`;
- `space_id`;
- frozen profile;
- Session status and UTC start/end time;
- whether Session consent acknowledgement is recorded;
- whether the matching Frozen Session Pack is verifiable;
- structural blockers;
- explicit local self-report counts and 3-field Quick Debrief completion.

It intentionally does **not** export:

- Session / Space titles;
- participant names;
- transcript text;
- Guidance text;
- source excerpts;
- user pseudonyms.

Important:

```text
structurally_selectable
!= authorized real use
!= verified identity
!= independently verified participant consent
!= real-user validation
```

The inventory never assigns `user_ref`; that mapping remains an explicit operator action.

## 4. Select the pilot cohort

Only select real, ended Project Sync / Design Review Sessions that you are authorized to use for evaluation.

Assign each real participant a stable local pseudonymous key, for example:

```text
pilot-user-01
pilot-user-02
pilot-user-03
```

Do not use names, email addresses or other direct identifiers as `user_ref`.

For longitudinal evidence, keep the mapping stable at the Space level:

```text
one space_id → exactly one pseudonymous user_ref
```

If different pilot participants used the same local Space, do not combine those Sessions as one continuity Space. Create/separate participant-specific Spaces or exclude the mixed Space from that cohort; the current builder/evaluator fail closed on mixed-user assignment.

A Session may be selected only when the local database confirms:

- Session status = ENDED;
- launch profile is PROJECT_SYNC or DESIGN_REVIEW;
- Session consent acknowledgement exists;
- Frozen Session Pack exists and belongs to that Session.

## 5. Initialize a frozen workspace

Recommended command:

```bash
python scripts/v2_conversation_pilot_workspace.py init \
  --db <CHENGZHU_HOME>/data/product.db \
  --session cv_project_001=pilot-user-01 \
  --session cv_project_002=pilot-user-01 \
  --session cv_design_001=pilot-user-02 \
  --out-dir <LOCAL_PRIVATE_PATH>/pilot-2026-10
```

The command creates a new directory and refuses to overwrite an existing one.

Policy is frozen into each workspace. A workspace initialized under policy v6 remains historical v6 evidence; do **not** edit its frozen policy to v7. After this post-beta.6 correction, create a fresh workspace under current source so `stable-promotion-policy.json` freezes policy v7 and the same-user Space binding is auditable from initialization onward.

Expected files:

```text
workspace.json
selected-cohort.snapshot.json
stable-promotion-policy.json
pilot-manifest.draft.json
independent-review.seed.jsonl
self-report.jsonl
README.md
```

Important properties:

- only explicitly selected Sessions enter the seed/export;
- unrelated Sessions are not copied;
- the absolute product.db path is not recorded;
- `selected-cohort.snapshot.json` freezes selected Session structure + local pseudonymous `user_ref` + Frozen Session Pack identity/digest（并重新计算 payload canonical digest 校验 stored digest）, without transcript / participant / Guidance / source text;
- the SQLite main-file SHA256 is advisory only; Chengzhu uses WAL, so the main file alone is not the logical database-state anchor;
- the exact Stable Promotion policy bytes are frozen;
- the draft manifest is deliberately not Stable-eligible;
- self-report remains explicit local self-report only;
- `REAL_USER_VALIDATED`, `V2_STABLE_RELEASE` and `PMF_PROVEN` remain false.

## 6. Independent review

Never edit `independent-review.seed.jsonl` in place.

Make a reviewer-specific copy, for example:

```text
reviewer-a.jsonl
reviewer-b.jsonl
```

The reviewer must fill:

- `reviewer`;
- `label_source=INDEPENDENT_HUMAN_REVIEW` where policy requires it;
- the metric-specific actual/quality labels;
- optional human `notes`.

The reviewer must **not** change or invent any frozen seed provenance. In particular, keep unchanged:

- `session_id / space_id / profile / event_id / timestamp`;
- `predicted / predicted_type / predicted_state / prediction_unavailable`;
- Guidance class and all `system` provenance, including transcript/runtime origin;
- source refs, detector version and frozen prediction payloads.

At `evaluate`, Chengzhu re-verifies the byte hash of `independent-review.seed.jsonl`, binds every independent-review row to the exact frozen `(session_id, kind, event_id)` seed row, and compares every non-human field. An invented event, altered prediction, altered runtime origin, unknown extra field, changed profile/Space, or edited source provenance fails closed before aggregation.

The seed is not evidence until reviewed, and a reviewer file is not accepted merely because its Session belongs to the authorized cohort.

Stable Policy v7 preserves the v6 sample-unit rule:

```text
min_n = unique product event × metric observations
not reviewer annotation rows
```

Different reviewers may annotate the same event for inter-rater analysis, but the same event cannot contribute the same Stable metric twice. Duplicate event/metric labels across reviewers or label sources fail closed and must be resolved/selected before Stable aggregation. Different metric dimensions on the same event may still be reviewed separately.

Stable live-guidance metrics use only v12 TRANSCRIPT_AUTO provenance.

Direct Question metrics use only v11 capture-time frozen predictions.

Reviewed post-hoc truth must never be copied back into prediction fields.

## 7. Finalize the authorized cohort

Review the draft cohort locally first.

Finalization requires explicit operator declarations. Example:

```bash
python scripts/v2_conversation_pilot_workspace.py finalize \
  --db <CHENGZHU_HOME>/data/product.db \
  --workspace <LOCAL_PRIVATE_PATH>/pilot-2026-10 \
  --critical-incidents 0 \
  --attest AUTHORIZED_REAL_USE \
  --attest NO_SYNTHETIC_ROWS_IN_HUMAN_EVAL \
  --attest RAW_LABELS_KEPT_LOCAL \
  --attest NO_CRITICAL_PRIVACY_INCIDENT \
  --attest NO_KNOWN_DATA_LOSS
```

This creates:

```text
pilot-manifest.final.json
finalization.json
```

The command revalidates the selected Sessions against product.db.

It does not system-verify:

- participant identity;
- real-world authorization;
- participant consent;
- the truth of operator attestations;
- PMF.

If any frozen policy/draft/selected-cohort snapshot hash has changed, finalization fails closed.

Finalization also recomputes the selected cohort's logical structure from current SQLite rows and requires exact equality with the frozen snapshot. Unrelated new Sessions or WAL activity are allowed; changes to a selected Session's Space/profile/status/start/end/consent or Frozen Session Pack identity/digest（并重新计算 payload canonical digest 校验 stored digest） are rejected.

If cohort membership, selected Session structure or attestations must change, create a new workspace instead of rewriting the old one.

## 8. Run the evidence gate

After independent review files are complete:

```bash
python scripts/v2_conversation_pilot_workspace.py evaluate \
  --workspace <LOCAL_PRIVATE_PATH>/pilot-2026-10 \
  --review reviewer-a.jsonl \
  --review reviewer-b.jsonl
```

The command automatically combines:

```text
explicit local self-report
+
independent human review
→ human-label report
→ frozen Stable policy v7
→ stable-readiness report
```

It creates:

```text
evaluation/
  human-report.json
  human-report.md
  stable-readiness.json
  stable-readiness.md
  evaluation-manifest.json
```

The evaluation directory is immutable-by-convention: the tool refuses to overwrite it.

To rerun with changed labels/cohort/rules, preserve the old workspace and create a new one.

## 9. Hash and mutation rules

Workspace provenance protects against accidental evidence drift.

The workflow refuses to continue when any frozen input hash changes:

- `selected-cohort.snapshot.json`;
- `stable-promotion-policy.json`;
- `pilot-manifest.draft.json`;
- `independent-review.seed.jsonl`;
- `self-report.jsonl`;
- `pilot-manifest.final.json`.

The selected-cohort snapshot is additionally recomputed from logical SQLite rows at finalization. This avoids false drift from unrelated WAL-backed database changes while still failing closed on selected Session/Pack drift.

Independent reviewer files are external inputs and their SHA256 values are recorded in `evaluation-manifest.json`. The manifest also records the frozen seed SHA256, seed row count, verified independent-review row count, and `EVENT_LEVEL_IMMUTABLE_PROVENANCE_VERIFIED`.

The reviewer binding proves only that the human label is attached to a real frozen local review event/prediction. It does **not** prove the reviewer's identity, independence, competence, authorization, or honesty.

This is tamper-evident local provenance, not a cryptographic identity/authorization system.

## 10. Retention interaction

Guidance/Silence feedback follows its Guidance target lifecycle.

When retention deletes a Guidance event:

- dependent GUIDANCE/SILENCE feedback is deleted in the same confirmed cleanup boundary;
- legacy orphan feedback is previewed and repaired;
- Session-level CONTINUE / SESSION_OUTCOME feedback remains until Session/Space deletion.

Pilot operators should export/review privacy-sensitive transcript-dependent evidence before the authorized local retention window removes it.

Do not disable privacy retention merely to increase metric sample size.

## 11. Interpreting NO_GO

`NO_GO` is the expected result until the real pilot is large and strong enough.

Do not respond to NO_GO by:

- lowering thresholds;
- changing cross-session definition;
- mixing manual Guidance Lab events into automatic runtime populations;
- counting forced silence as Useful Silence;
- relabeling self-report as independent review;
- adding synthetic/CI Sessions;
- re-running newer detectors over historical transcript to manufacture predictions.

Fix the product or gather more legitimate evidence.

## 12. Interpreting PASS

A PASS means only:

```text
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW
```

It still does not mean:

```text
V2_STABLE_RELEASE = TRUE
PMF_PROVEN = TRUE
REAL_USER_VALUE_UNIVERSALLY_PROVEN = TRUE
```

A separate release review must still verify current main, current packaged artifacts, privacy/security incidents, installer provenance, rollback and release notes.

## 13. Current product truth

After beta.7 publication:

```text
PUBLIC_BETA = v2.0.0-beta.7
PUBLIC_BETA_SOURCE_SHA = dc2188cd6b796b5dca9baf0eac2372da7be5bbf2
PILOT_RUNTIME_AVAILABLE = TRUE
PILOT_EVIDENCE_CAPTURE_RUNTIME = TRUE
AUTHORIZED_PILOT_MANIFEST_BUILDER = TRUE
PILOT_WORKSPACE_ORCHESTRATOR = AVAILABLE
PILOT_SESSION_INVENTORY = PRIVACY_MINIMIZED
PUBLIC_BETA_PACKAGED_STABLE_POLICY = v2.0-R1-stable-promotion-7
CURRENT_OPERATOR_STABLE_POLICY = v2.0-R1-stable-promotion-7
PRODUCT_VALIDATION_INFRA_COMPLETE = TRUE
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
V2_STABLE_RELEASE = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

Publication provenance: `docs/releases/V2_0_0_BETA_7_PUBLICATION_PROVENANCE.md`.


### Finalize 的双重 cohort revalidation

`finalize` 不是“先检查一次、然后相信后续 live DB 不再变化”。它会：

```text
revalidate selected cohort against frozen snapshot
→ build final manifest from live DB
→ revalidate selected cohort again
→ only then persist pilot-manifest.final.json / finalization.json
```

因此，如果选中 Session / Frozen Session Pack 在 final manifest 的独立 DB 读取窗口内发生漂移，finalize 必须失败，而且不能留下半成品 final evidence。与 cohort 无关的其他 Session/WAL 增长仍允许。
