# Chengzhu v2.0.0-beta.5 Publication Provenance

Date: 2026-10-12

## Status

```text
RELEASE_TAG = v2.0.0-beta.5
RELEASE_CHANNEL = PRERELEASE
PUBLIC_RELEASE = TRUE
DRAFT = FALSE
STABLE_LATEST = v1.4.2
SOURCE_SHA = 3c29112b6256d78f26c7d70670b558c6c24d6a3b
TAG_SHA = 3c29112b6256d78f26c7d70670b558c6c24d6a3b
MAIN_CI = 923 / SUCCESS
RELEASE_RUN = 316 / SUCCESS
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

This document records the observed GitHub publication truth for the fifth Conversation Beta. It does **not** promote v2 to stable and does not convert release / security / evaluator engineering evidence into real-user or PMF evidence.

## Source and channel invariants

Observed from the GitHub Release/tag APIs after publication and Release run #316:

- `refs/tags/v2.0.0-beta.5` points directly to commit `3c29112b6256d78f26c7d70670b558c6c24d6a3b`;
- the Release target is the same SHA;
- `prerelease = true`;
- `draft = false`;
- publication timestamp: `2026-10-12T06:55:08Z`;
- GitHub stable `/releases/latest` remains `v1.4.2`;
- main CI #923 completed successfully on the same source SHA before the generic publisher dispatched Release #316.

Therefore beta.5 did not replace the stable Latest channel.

## Published assets

GitHub currently reports these public assets and digests:

| Asset | Size | GitHub digest |
| --- | ---: | --- |
| `Chengzhu-Setup-x64.exe` | 210,736,744 bytes | `sha256:b054886b0283609a49fc2b12badd270843fe4ea093cf63dc10d9ad8971fe5a47` |
| `Chengzhu-Portable-x64.zip` | 270,656,191 bytes | `sha256:6b8242795fda3eb8f68ab2ef991d782099252c144282a237f5a55135054d7156` |
| `SHA256SUMS.txt` | 181 bytes | `sha256:0d370a7e0f31a63ad3e786792826f9caaa245825b7dbad3ecce527a6cda65a4d` |
| `LICENSE.txt` | 1,087 bytes | `sha256:f9ce30ca6bb69bb231b38bcedb9e4ba0fe891c1093020dd3fcbd5c5f01560718` |
| `THIRD_PARTY_NOTICES.md` | 33,389 bytes | `sha256:4ea16e9f1b6a352ba649f8d827e8dd7b78195551690808a25777607c883ea7ac` |
| `RELEASE_NOTES_v2.0.0-beta.5.md` | 8,017 bytes | `sha256:17748f019be51795766cb19a143c9d32459efd6013b25204c710633660685ead` |

## Release run #316

Release workflow run `38213054753` / Windows job `114691368641` was dispatched against the exact green-main source SHA above.

Every release-critical step completed successfully:

1. exact-SHA checkout and source pinning;
2. backend tests;
3. release-version consistency;
4. license gate;
5. frontend build + unit tests;
6. desktop unit tests;
7. clean-venv backend sidecar build;
8. packaged sidecar smoke;
9. installer + portable build;
10. packaged runtime Conversation UI evidence;
11. packaged UI evidence contract;
12. independent packaged evidence;
13. clean installer replay;
14. installed-layout smoke;
15. release-file collection + SHA256;
16. draft GitHub Release creation targeted at the exact source SHA;
17. draft download-back verification;
18. SHA256 verification of downloaded assets;
19. installation of the **downloaded** installer;
20. packaged smoke using the downloaded / installed files;
21. verified draft publication;
22. prerelease-channel verification;
23. Stable Latest preservation;
24. public tag/source equality;
25. post-publish verification-metadata regression;
26. upload of the download-back verification artifact.

The release log explicitly records:

```text
prerelease channel invariant: v2.0.0-beta.5 is prerelease; stable Latest remains v1.4.2
published release tag/source invariant: v2.0.0-beta.5 -> 3c29112b6256d78f26c7d70670b558c6c24d6a3b
```

The downloaded-install packaged smoke finished with `passed = true`.

## What beta.5 adds over beta.4

beta.5 is a post-beta.4 hardening rebuild. It keeps the beta.4 Conversation product surface while packaging the current hardened main:

```text
PRODUCT_SCHEMA_VERSION = 12
PILOT_EVIDENCE_BRIDGE = PACKAGED
DIRECT_QUESTION_PROVENANCE = PACKAGED
GUIDANCE / SILENT AUTO_RUNTIME_PROVENANCE = PACKAGED
FEEDBACK_RETENTION_INTEGRITY = PACKAGED

FRONTEND_VITE = 6.4.4
ELECTRON_BUILDER = 26.17.0
FRONTEND_PRODUCTION_HIGH_CRITICAL_AUDIT = 0
DESKTOP_BUILD_TOOLCHAIN_HIGH_CRITICAL_AUDIT = 0

STABLE_PROMOTION_POLICY = v2.0-R1-stable-promotion-4
PILOT_COHORT_BINDING = REQUIRED
STABLE_METRIC_PROFILES = PROJECT_SYNC + DESIGN_REVIEW
EACH_STABLE_METRIC_REQUIRES_BOTH_LAUNCH_PROFILES = TRUE
```

The security gate is scope-aware: remaining frontend full-graph findings are dev/build-tool findings and are not silently relabeled as packaged-runtime vulnerabilities.

The policy-v4 evaluator binds human evidence to the enumerated authorized pilot cohort and blocks out-of-scope profile score inflation. It does not relax numerical thresholds.

## Current truth boundary

Supported:

```text
V2_BETA_PRERELEASE_PUBLISHED = TRUE
PUBLISHED_BETA_TAG = v2.0.0-beta.5
PUBLISHED_BETA_SOURCE_SHA = 3c29112b6256d78f26c7d70670b558c6c24d6a3b
STABLE_LATEST = v1.4.2
PILOT_EVIDENCE_CAPTURE_RUNTIME = PACKAGED_BETA_AVAILABLE
STABLE_PROMOTION_POLICY = v2.0-R1-stable-promotion-4
```

Still unsupported:

```text
V2_STABLE_RELEASE = FALSE
V2_PRODUCTIZED_RELEASE = FALSE
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
GOOGLE_REAL_ACCOUNT_VALIDATED = FALSE
MICROSOFT_REAL_ACCOUNT_VALIDATED = FALSE
```

Google Calendar / Drive / Gmail and Microsoft To Do still require the applicable real-account evidence; Gmail also retains its external OAuth sensitive-scope / publication gate. GitHub provider real-account replay evidence remains separate from beta.5 publication truth.

## Immutability

The beta.5 tag and published binaries remain bound to source SHA `3c29112b6256d78f26c7d70670b558c6c24d6a3b`.

Any later documentation, pilot or engineering commits on `main` must **not** move, rewrite or republish `v2.0.0-beta.5`. A later downloadable code change requires a new version/tag and a fresh exact-SHA release cycle.
