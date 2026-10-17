# Chengzhu v2.0.0-beta.10

Status: **PUBLISHED PRERELEASE** · exact source/tag SHA `a6a673326f64e1b6b78e06992e1e2a196bab9076` · Main CI #1074 SUCCESS · Release #404 SUCCESS · Stable Latest remains `v1.4.2`.

## Why beta.10 exists

`v2.0.0-beta.9` is the current public Conversation Beta and correctly freezes Stable Promotion Policy v8 plus Pilot Workspace v5 evaluator-toolchain provenance.

Post-beta.9 audit then closed a deeper Stable-promotion reproducibility gap:

```text
same runtime source
+ same Python package name==version set
!= necessarily same packaged Python artifact bytes
```

A real-pilot runtime and a later Stable build could theoretically resolve different wheel artifacts that advertise the same distribution name and version. Version equality alone is therefore insufficient as a Stable runtime-baseline proof.

beta.10 exists to package the **runtime/build provenance and exact Python wheel-artifact replay chain** before any new Stable-readiness pilot evidence is treated as canonical.

This is a release/evidence reproducibility prerelease, not feature expansion.

## What beta.10 packages

### Stable Policy

```text
STABLE_PROMOTION_POLICY = v2.0-R1-stable-promotion-8
NUMERICAL_THRESHOLDS_CHANGED = FALSE
MIN_N_CHANGED = FALSE
PROFILE_FLOORS_CHANGED = FALSE
COMPLETE_FROZEN_ELIGIBLE_POPULATION = REQUIRED
```

### Pilot / evaluator contracts

```text
PILOT_WORKSPACE_CONTRACT = v2.0-R1-pilot-workspace-7
PILOT_TOOLCHAIN_CONTRACT = v2.0-R1-pilot-toolchain-3
PILOT_RUNTIME_BASELINE_CONTRACT = v2.0-R1-pilot-runtime-baseline-2
PYTHON_ARTIFACT_PROVENANCE_CONTRACT = v2.0-R1-python-artifact-provenance-1
```

New workspace-v7 evidence requires selected pilot Sessions to share the same:

- normalized product runtime fingerprint;
- packaged source/build provenance;
- exact Python interpreter family / architecture;
- resolved `name==version` Python environment SHA;
- exact wheel artifact-set SHA256.

Historical prerelease runtime without capture-time artifact provenance is not silently upgraded into workspace v7.

## Packaged runtime provenance

The sidecar build is now pinned to exact Python:

```text
Python = 3.13.16
clean venv = required
pip cache = disabled
wheel-only install = required
```

The clean packaged build records a pip installation report and freezes every final Python distribution as:

```text
normalized distribution name
version
wheel filename
wheel sha256
```

The artifact set must exactly equal the final `pip freeze --all` distribution set. Missing/extra distributions, version drift, source distributions, direct/VCS/local installs, yanked artifacts or missing SHA256 fail closed.

## Stable handoff and human authorization

beta.10 packages the post-beta.9 Stable release-control chain:

```text
Stable readiness PASS
→ privacy-minimized Stable handoff
→ cross-verified workspace/finalization/evaluation/human-report provenance
→ explicit human release review
→ exact candidate source SHA + version GO
→ privacy-minimized Stable authorization
```

Contracts:

```text
STABLE_REVIEW_HANDOFF_CONTRACT = v2.0-R1-stable-review-handoff-4
STABLE_RELEASE_REVIEW_DRAFT / DECISION / AUTHORIZATION = v3
STABLE_RUNTIME_EQUIVALENCE_CONTRACT = v2.0-R1-stable-runtime-equivalence-3
```

A Stable v2+ version cannot be auto-published merely because a version bump reaches green main. Human GO is necessary, but still not publication.

## Exact current-main publication gate

For unpublished Stable v2+:

```text
authorized candidate SHA
==
release source SHA
==
current main tip
```

The exact source SHA must also have successful main push CI. The equality is verified before packaging and again immediately before publication. If main advances during the release window, Stable publication fails closed and requires a new review cycle.

Prerelease beta.10 remains on the normal prerelease path and does not require a Stable authorization token.

## Exact wheel replay for future Stable

Stable replay no longer relies on ordinary version-only constraints.

Authorization-derived inputs are complete hash-checking requirement sets:

```text
name==version --hash=sha256:<pilot-wheel-sha>
```

The Stable build must use:

```text
--require-hashes
--only-binary :all:
--no-cache-dir
clean venv
```

After installation it independently recomputes:

- runtime fingerprint SHA;
- Python environment SHA;
- Python artifact provenance SHA.

All must match the authorized pilot baseline before packaging/publication may continue.

## Why a new pilot baseline is required

beta.9 remains valid historical prerelease evidence, but it does **not** contain capture-time Python wheel-artifact provenance or workspace v7 runtime-baseline contracts.

Therefore:

```text
pre-beta.10 pilot runtime
!= workspace-v7 artifact-provenance baseline
```

Do not reconstruct beta.9 artifact provenance later from current package indexes and relabel it as if it was captured by beta.9.

After beta.10 is actually published, new Stable-readiness pilots should use beta.10 (or a later prerelease that explicitly preserves/elevates these contracts).

## Existing Conversation Beta protections retained

beta.10 retains the beta.9/beta.8 evidence-integrity stack, including:

- Quick Debrief and local explicit self-report;
- schema v10–v13 evidence/runtime provenance;
- immutable AI prediction and Direct Question provenance;
- feedback-retention integrity and orphan-label cleanup;
- authorized real-pilot manifest/workspace;
- privacy-minimized Session inventory;
- WAL-safe selected-cohort snapshot;
- finalize-time TOCTOU revalidation;
- independent-review frozen seed binding;
- unique event × metric sample units;
- single-user longitudinal Space binding;
- complete frozen eligible event×metric coverage;
- evaluator-toolchain SHA256 freeze;
- dependency-security gates;
- explicit release hold + stale-main guard;
- exact-SHA Windows build / clean-install / download-back / tag-source gates.

## What beta.10 does not claim

```text
V2_STABLE_RELEASE = FALSE
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
REAL_USER_IDENTITY_SYSTEM_VERIFIED = FALSE
REVIEWER_INDEPENDENCE_SYSTEM_VERIFIED = FALSE
PARTICIPANT_CONSENT_SYSTEM_VERIFIED = FALSE
```

A future Stable Policy v8 PASS only means:

```text
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW
```

It still requires a separate human release review, exact-current-main authorization, successful Stable release workflow and public tag/assets. PMF remains a separate longer-horizon question.

## Publication boundary

Until the full beta.10 release workflow succeeds:

```text
CURRENT_PUBLIC_BETA = v2.0.0-beta.9
NEXT_BETA_CANDIDATE = v2.0.0-beta.10
STABLE_LATEST = v1.4.2
```

Do not rewrite public/downloadable truth to beta.10 from a version bump or green PR alone.
