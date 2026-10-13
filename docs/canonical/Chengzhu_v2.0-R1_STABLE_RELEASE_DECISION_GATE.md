# Chengzhu v2 Stable Release Decision Gate

**Status**: SOURCE RUNTIME / RELEASE GOVERNANCE  
**Public Beta**: v2.0.0-beta.9  
**Stable v2**: NOT CLAIMED  
**REAL_USER_VALIDATED**: FALSE  
**PMF_PROVEN**: FALSE

This document defines the final release-governance boundary between a PASS real-pilot handoff and an actual Stable GitHub Release.

## 1. Why this gate exists

Before this gate, Chengzhu already separated:

```text
real pilot
→ human labels
→ Stable Promotion Policy
→ PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW
→ privacy-minimized Stable review handoff
```

However, the generic current-version publisher still treated any green non-prerelease version like an ordinary release candidate. A future version bump from `2.0.0-beta.9` to `2.0.0` could therefore have reached the Stable publication workflow without a machine-enforced human Stable release decision.

This gate closes that gap.

## 2. Two-commit Stable candidate model

A Stable approval cannot contain the SHA of the commit that contains the approval file itself. Chengzhu therefore uses an explicit two-commit model:

```text
C0 = exact Stable candidate
     version already = 2.x.y
     release notes/version surfaces frozen
     full CI + release review can inspect C0
     no Stable approval artifact exists yet

human Stable release review
+ Stable handoff v2

C1 = approval-only child of C0
     only changed file:
       .github/stable-release-approvals/v2.x.y.json

C1 full CI green
→ generic publisher validates C0 → C1
→ release.yml independently validates the same approval
→ only then may Stable publication continue
```

The release binaries are built from C1, but product source must be identical to C0 except for the approval JSON, which is release-governance metadata and is not product implementation.

## 3. Stable decision tool

Generate a human review template only after a valid handoff exists:

```bash
python scripts/v2_stable_release_approval.py template \
  --handoff-dir <LOCAL_PRIVATE_PATH>/pilot-stable-review \
  --candidate-sha <C0_FULL_SHA> \
  --candidate-version 2.0.0 \
  --out <LOCAL_PRIVATE_PATH>/stable-release-review-input.json
```

The template contains all 13 required release-review checks.

The human reviewer fills:

- `reviewer_ref` (a local reviewer reference; not identity proof);
- timezone-aware `reviewed_at`;
- every check state = `APPROVED` or `REJECTED`;
- a non-empty evidence reference/summary for every check;
- the frozen four review attestations.

Finalize:

```bash
python scripts/v2_stable_release_approval.py finalize \
  --handoff-dir <LOCAL_PRIVATE_PATH>/pilot-stable-review \
  --review <LOCAL_PRIVATE_PATH>/stable-release-review-input.json \
  --candidate-sha <C0_FULL_SHA> \
  --candidate-version 2.0.0 \
  --out .github/stable-release-approvals/v2.0.0.json
```

The tool refuses overwrite.

If any check is `REJECTED`, output status is:

```text
NO_GO
STABLE_RELEASE_PUBLICATION_AUTHORIZED = FALSE
```

Do not commit a NO_GO file as an approval.

Only all-APPROVED review yields:

```text
STABLE_RELEASE_APPROVED_FOR_EXACT_CANDIDATE
STABLE_RELEASE_PUBLICATION_AUTHORIZED = TRUE
V2_STABLE_RELEASE = FALSE
PMF_PROVEN = FALSE
```

Approval is authorization to enter publication; it is not proof that publication already happened.

## 4. Commit invariant

The committed approval is valid only when:

1. `candidate_source_sha` is a full SHA;
2. that candidate already reports the exact stable version in `desktop/package.json`;
3. the candidate does **not** already contain its approval artifact;
4. release source C1 has C0 as its direct parent;
5. `git diff C0..C1` contains exactly one path:

```text
.github/stable-release-approvals/v<version>.json
```

Any code, dependency, workflow, release-note or version change after human review invalidates the approval. Create/review a new Stable candidate instead.

## 5. Publisher behavior

For prereleases such as `v2.0.0-beta.9`:

```text
green exact current main
→ existing prerelease publication behavior
```

For a new v2+ Stable version:

```text
green current main
→ if already published: verify existing release truth and exit
→ if not published:
     require committed Stable approval
     validate exact candidate → approval-only child invariant
     only then dispatch release.yml
```

A green Stable candidate C0 **without** approval exits without publishing. This is expected behavior, not a failed product build.

The Windows `release.yml` publish path independently runs the same validator. Direct tag pushes or manual `publish=true` dispatch therefore cannot bypass the generic publisher gate.

PR release builds do not require Stable approval because a candidate must be buildable/testable before human release approval exists.

## 6. Evidence and identity boundary

The approval artifact is tamper-evident repository provenance, not a cryptographic identity signature.

It proves that the repository publication path requires a structured human release decision bound to an exact candidate and handoff hash. It does not independently prove:

- reviewer identity;
- reviewer competence;
- participant consent;
- real-user identity;
- PMF;
- that Stable has already been published.

Organizations that need stronger custody should combine this with protected branches / required reviewers / signed commits / protected GitHub Environments or an independently controlled archive.

## 7. Current truth

At introduction of this gate:

```text
PUBLIC_BETA = v2.0.0-beta.9
STABLE_HANDOFF_CONTRACT = v2.0-R1-stable-review-handoff-2
STABLE_RELEASE_APPROVAL_CONTRACT = v2.0-R1-stable-release-approval-1
GENERIC_V2_STABLE_AUTO_PUBLISH_WITHOUT_APPROVAL = BLOCKED
DIRECT_RELEASE_WORKFLOW_BYPASS_WITHOUT_APPROVAL = BLOCKED
V2_STABLE_RELEASE = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```
