# Chengzhu v2 Real Pilot Operator Runbook

**Status**: BETA.10 PUBLISHED · CANONICAL STABLE-PILOT BASELINE · STABLE POLICY v8 · WORKSPACE v7  
**Public Beta**: v2.0.0-beta.10  
**Published source/tag SHA**: `a6a673326f64e1b6b78e06992e1e2a196bab9076`  
**Stable v2**: NOT CLAIMED  
**REAL_USER_VALIDATED**: FALSE  
**PMF_PROVEN**: FALSE

This runbook defines the operator path from a real Conversation pilot to a Stable Promotion evidence review.

For a continuous local-Agent execution handoff that preserves the same evidence and release boundaries, use [`V2_BETA10_REAL_PILOT_LOCAL_AGENT_GOAL.md`](./V2_BETA10_REAL_PILOT_LOCAL_AGENT_GOAL.md). The GOAL is subordinate to this runbook and current repository/release truth.

It does not change any release or evidence claim by itself.

## 1. Preconditions

The canonical participant-facing/runtime baseline for **new Stable-readiness pilots is now `v2.0.0-beta.10`**, published from exact source/tag SHA `a6a673326f64e1b6b78e06992e1e2a196bab9076`.

Do not initialize a new Stable-readiness workspace from beta.9 or earlier if you expect it to enter the current Stable handoff. Those releases predate the complete packaged runtime / wheel-artifact provenance baseline and remain immutable historical evidence.

beta.10 packages all of the following together:

```text
Stable Policy = v2.0-R1-stable-promotion-8
Product schema >= v13
Pilot Workspace = v2.0-R1-pilot-workspace-7
Pilot Toolchain = v2.0-R1-pilot-toolchain-3
Pilot Runtime Baseline = v2.0-R1-pilot-runtime-baseline-2
Python Artifact Provenance = v2.0-R1-python-artifact-provenance-1
Stable Handoff = v2.0-R1-stable-review-handoff-4
Stable Authorization = v2.0-R1-stable-release-authorization-3
```

Workspace v7 freezes evaluator implementation, exact packaged runtime/source provenance, resolved Python package versions **and the SHA256 of every installed wheel artifact**. A pre-v7 workspace or pre-artifact packaged Session remains valid historical evidence but cannot be upgraded after the fact into this baseline. **beta.10 is the first public prerelease that packages this canonical baseline and should be used for fresh Stable-readiness evidence unless a later prerelease explicitly preserves or strengthens the same contracts.**

This runbook represents an operator workflow, not ordinary participant-facing Conversation UI, and its availability does not turn structurally selectable Sessions into authorized real use.

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

Policy and runtime provenance are frozen into each workspace. Historical workspace contracts v1-v6 remain historical evidence; do **not** edit or “upgrade” their frozen policy/runtime/toolchain in place. For a new Stable-readiness pilot under current source, create a fresh Workspace v7 only from Sessions produced by a prerelease that actually embeds runtime-baseline v2 and wheel-artifact provenance.

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
- Workspace v7 freezes Pilot Toolchain v3 SHA256 fingerprints, including the runtime-fingerprint implementation plus workspace orchestrator, label-seed, self-report export, human-eval, pilot-manifest and stable-readiness tools;
- Workspace v7 also freezes Runtime Baseline v2: normalized product runtime, exact Python environment and exact wheel artifact SHA256 set;
- finalize/evaluate fail closed if evaluator toolchain, selected runtime, resolved package versions or wheel artifact set differs from initialization;
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

Policy v8 additionally computes the complete Stable-eligible event×metric population from that frozen seed **before** inspecting labels. Every eligible event must be covered by at least one label source already allowed for that metric. This applies to independent-review metrics, self-report-only metrics, and metrics allowing either source. Do not stop labeling when a favorable subset reaches `min_n`; omitted rows, null required fields, or disallowed sources make Stable readiness `NO_GO`.

The seed is not evidence until reviewed, and a reviewer file is not accepted merely because its Session belongs to the authorized cohort.

Stable Policy v8 preserves the v7 cohort/sample-unit rules and adds complete frozen Stable metric coverage:

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
→ frozen Stable policy v8
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

For new Workspace v7 workspaces, provenance freezes evidence inputs, evaluator implementation, packaged runtime/source identity, resolved Python package versions **and wheel artifact SHA256 provenance**. The workflow refuses to continue when the evaluator toolchain SHA256 set differs from initialization; use the exact original checkout/toolchain or create a new workspace rather than silently recalculating old evidence under changed code.

The workflow also refuses to continue when any frozen input hash changes:

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

## 9.1 Packaged Python artifact provenance

For current-source Stable-readiness evidence, package versions alone are insufficient.

The prerelease packaged build must freeze:

```text
Python exact patch version
+ normalized pip freeze name==version set
+ one wheel filename + SHA256 per installed distribution
```

Pilot Workspace v7 requires all selected Sessions to share the same environment SHA **and** the same artifact-set SHA. Same package versions with different wheel bytes are treated as different runtime baselines.

Stable build replay uses hash-checking requirements:

```text
--require-hashes
--only-binary :all:
--no-cache-dir
```

The Stable release authorization is bound to the pilot artifact-set SHA and the release workflow independently recomputes the built artifact-set SHA before publication.

This is build reproducibility provenance, not package-signature verification, reviewer identity verification, real-user evidence or PMF.

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

## 12.1 Freeze the Stable release-review handoff

After and only after `evaluate` returns:

```text
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW
```

create a privacy-minimized handoff bundle:

```bash
python scripts/v2_conversation_stable_review_handoff.py \
  --workspace <LOCAL_PRIVATE_PATH>/pilot-2026-10 \
  --out-dir <LOCAL_PRIVATE_PATH>/pilot-2026-10-stable-review
```

The tool fails closed when:

- the Stable gate is `NO_GO`;
- any frozen workspace/evaluation input no longer matches its SHA256 provenance;
- workspace / finalization / evaluation contract or evaluator-toolchain metadata disagree;
- selected-cohort physical or canonical-logical hashes disagree across workspace / finalization / evaluation;
- Stable policy version/hash disagree across workspace / finalization / evaluation / stable-readiness;
- evaluation claims disagree with `stable-readiness.json`;
- evaluation Stable metric coverage disagrees with the coverage frozen into `human-report.json`;
- the Stable evaluator tries to claim `V2_STABLE_RELEASE=true` or `PMF_PROVEN=true`;
- the output directory already exists.

The handoff contains only hashes, cohort/evaluation summaries, checkout context and pending release-review obligations. It does **not** copy transcript text, Guidance text, reviewer notes or direct identifiers.

Current source Handoff v4 additionally requires Workspace v7 / Toolchain v3 / Runtime Baseline v2 and treats `evaluation-manifest.json` as a summary that must agree with independently frozen workspace/finalization/human/stable artifacts; it is not allowed to self-assert a different toolchain, claims set or Stable-coverage summary. Reviewer input JSONL files themselves remain evaluation-time local inputs: if they are no longer present, the handoff does not pretend to re-open or re-authenticate them. Their hashes remain evaluation-manifest provenance only.

This is still local tamper-evident provenance, **not** a cryptographic signature/WORM archive. A coordinated rewrite of every local evidence file is outside the system-verification boundary; operators who need stronger custody should preserve the finalized workspace in an independently controlled read-only/archive layer.

Expected output:

```text
stable-review-handoff.json
stable-review-handoff.md
SHA256.json
```

Every release item is intentionally emitted as:

```text
PENDING_HUMAN_RELEASE_REVIEW
```

The handoff does not auto-verify current main CI, packaging, download-back, privacy/security incidents, rollback, release notes or code-signing policy. Those belong to the separate human release decision.

Therefore:

```text
Stable Gate PASS
→ review handoff ready
!= Stable release approved
!= Stable published
!= identity/consent independently verified
!= PMF
```

## 13. Current product truth

After beta.10 publication:

```text
PUBLIC_BETA = v2.0.0-beta.10
PUBLIC_BETA_SOURCE_SHA = a6a673326f64e1b6b78e06992e1e2a196bab9076
PILOT_RUNTIME_AVAILABLE = TRUE
PILOT_EVIDENCE_CAPTURE_RUNTIME = TRUE
AUTHORIZED_PILOT_MANIFEST_BUILDER = TRUE
PILOT_WORKSPACE_ORCHESTRATOR = AVAILABLE
PILOT_SESSION_INVENTORY = PRIVACY_MINIMIZED
PUBLIC_BETA_PACKAGED_STABLE_POLICY = v2.0-R1-stable-promotion-8
PUBLIC_BETA_PACKAGED_WORKSPACE_CONTRACT = v2.0-R1-pilot-workspace-7
PUBLIC_BETA_PACKAGED_TOOLCHAIN_CONTRACT = v2.0-R1-pilot-toolchain-3
PUBLIC_BETA_PACKAGED_RUNTIME_BASELINE = v2.0-R1-pilot-runtime-baseline-2
PUBLIC_BETA_PACKAGED_PYTHON_ARTIFACT_PROVENANCE = v2.0-R1-python-artifact-provenance-1
CURRENT_OPERATOR_STABLE_POLICY = v2.0-R1-stable-promotion-8
EVALUATOR_TOOLCHAIN_AND_RUNTIME_FINGERPRINT = REQUIRED_FOR_NEW_V7_WORKSPACES
PRODUCT_VALIDATION_INFRA_COMPLETE = TRUE
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
V2_STABLE_RELEASE = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

Publication provenance: `docs/releases/V2_0_0_BETA_10_PUBLICATION_PROVENANCE.md`.

Workspace v7, Toolchain v3, Runtime Baseline v2 and Python Artifact Provenance v1 are now **published beta.10 truth**. New Stable-readiness workspaces should be initialized from beta.10 (or a later prerelease explicitly retaining/elevating these contracts). beta.9 and earlier prereleases remain immutable historical evidence and must not be rewritten as if they had beta.10 capture-time runtime / wheel-artifact provenance.


### Finalize 的双重 cohort revalidation

`finalize` 不是“先检查一次、然后相信后续 live DB 不再变化”。它会：

```text
revalidate selected cohort against frozen snapshot
→ build final manifest from live DB
→ revalidate selected cohort again
→ only then persist pilot-manifest.final.json / finalization.json
```

因此，如果选中 Session / Frozen Session Pack 在 final manifest 的独立 DB 读取窗口内发生漂移，finalize 必须失败，而且不能留下半成品 final evidence。与 cohort 无关的其他 Session/WAL 增长仍允许。


---

## Stable release review → publication authorization

当 Stable evaluator 返回 `PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW` 后，仍不能直接把版本改成 Stable 并依赖 generic publisher。当前 release governance 强制把最后的人类决策与发布动作拆开：

```text
PASS workspace
→ v2_conversation_stable_review_handoff.py
→ v2_stable_release_review_decision.py init
→ human reviews every required check
→ finalize
→ GO / NO_GO
```

GO 必须绑定：

- exact candidate source SHA；
- stable SemVer（无 prerelease suffix）；
- handoff JSON/Markdown/checksum provenance；
- 完整 release-review check set；
- 每项 PASS 的非敏感 evidence_ref；
- clean candidate checkout + version match。

GO 只会生成本地 privacy-minimized `stable-release-authorization.b64`。它不包含 transcript、Guidance text 或 reviewer notes，也不自动发布。

Stable v2+ 的 generic publisher 被硬编码为 no-op。真正发布必须由人工手动触发 `Release` workflow，并将该 authorization token 作为 `stable_review_authorization_b64` 输入；workflow 在构建前与最终 publish 前都会 fail-closed 复核 source SHA / version / GO 状态，并把 `RELEASE_AUTHORIZATION.json` 纳入 SHA256 + download-back audit。

因此：

```text
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = prerequisite
HUMAN_STABLE_RELEASE_REVIEW_GO = publication authorization
V2_STABLE_RELEASE = only after verified public Stable Release
PMF_PROVEN = still FALSE unless separately established
```


### Stable release source invariant

When the pilot/evaluation chain eventually produces a PASS handoff and a human GO authorization, do not dispatch Stable from an arbitrary checkout. The authorized SHA must already be the current `main` tip and must have a successful main push CI run.

The Release workflow checks this before packaging and again immediately before publication. Any intervening main commit invalidates the release attempt; review/release must be rebound to the new exact candidate rather than publishing a stale SHA.
