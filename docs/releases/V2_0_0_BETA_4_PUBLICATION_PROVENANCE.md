# Chengzhu v2.0.0-beta.4 Publication Provenance

Date: 2026-10-11

## Status

```text
RELEASE_TAG = v2.0.0-beta.4
RELEASE_CHANNEL = PRERELEASE
PUBLIC_RELEASE = TRUE
DRAFT = FALSE
STABLE_LATEST = v1.4.2
SOURCE_SHA = 0e1d89ad381a93c1dcd9725418d9cbd5b3c71fcc
TAG_SHA = 0e1d89ad381a93c1dcd9725418d9cbd5b3c71fcc
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

This document records the observed GitHub publication truth for the fourth Conversation Beta. It does **not** promote v2 to stable and does not convert engineering / pilot-readiness evidence into real-user or PMF evidence.

## Source and channel invariants

Observed from the GitHub Release/tag APIs after publication and from Release run #304:

- `refs/tags/v2.0.0-beta.4` points directly to commit `0e1d89ad381a93c1dcd9725418d9cbd5b3c71fcc`;
- the Release target is the same SHA;
- `prerelease = true`;
- `draft = false`;
- publication timestamp: `2026-10-11T17:47:35Z`;
- GitHub stable `/releases/latest` remains `v1.4.2`;
- main CI #894 completed successfully on the same source SHA before the publisher dispatched the Release workflow.

Therefore beta.4 did not replace the stable Latest channel.

## Published assets

GitHub currently reports these public assets and digests:

| Asset | Size | GitHub digest |
| --- | ---: | --- |
| `Chengzhu-Setup-x64.exe` | 204,073,090 bytes | `sha256:9dc38e121aae030e74c21e12aad2b6800a0d02ed9ed9c2852cdb899f60716707` |
| `Chengzhu-Portable-x64.zip` | 270,610,212 bytes | `sha256:cfce61b3151f3bba749fe365549cb2d69042d3c828dab6be464757de1ff4360f` |
| `SHA256SUMS.txt` | 181 bytes | `sha256:af9fbdaf138da90feed0dbbf3754d1b5fb34c93d0ef12bb5d7657fc5f34db756` |
| `LICENSE.txt` | 1,087 bytes | `sha256:f9ce30ca6bb69bb231b38bcedb9e4ba0fe891c1093020dd3fcbd5c5f01560718` |
| `THIRD_PARTY_NOTICES.md` | 35,819 bytes | `sha256:3db48e6fd9958e6af1b5e8ceafcb66e728abfcdd19bb939b10a811d5cbe59e2e` |
| `RELEASE_NOTES_v2.0.0-beta.4.md` | 8,666 bytes | `sha256:e7e80c3cb46d39d5fff27daae5f857bcfc5218998ae0418d9607519cfb616b71` |

## Release run #304

Release workflow run `38159386198` / job `114528928757` was dispatched against the exact green-main source SHA above.

The run completed successfully. Its observed release-critical path included:

1. exact-SHA checkout of `0e1d89ad381a93c1dcd9725418d9cbd5b3c71fcc`;
2. backend lint + full test suite (`1361 passed, 3 skipped` in the release job);
3. release-version consistency for all distributable surfaces at `2.0.0-beta.4`;
4. third-party license gate;
5. frontend / desktop build and test path;
6. backend sidecar packaging and packaged smoke;
7. Windows installer + portable build;
8. clean-install / installed-layout validation;
9. draft GitHub Release creation explicitly targeted at the exact source SHA;
10. download-back of installer, portable and `SHA256SUMS.txt`;
11. SHA256 verification of downloaded assets;
12. installation of the **downloaded** installer;
13. packaged smoke using the downloaded/installed release files;
14. verified draft publication as a prerelease;
15. Stable Latest preservation (`v1.4.2`);
16. public tag/source equality check;
17. post-publish verification JSON enrichment;
18. the PowerShell release-verification metadata regression added after beta.3.

The log explicitly records:

```text
prerelease channel invariant: v2.0.0-beta.4 is prerelease; stable Latest remains v1.4.2
published release tag/source invariant: v2.0.0-beta.4 -> 0e1d89ad381a93c1dcd9725418d9cbd5b3c71fcc
```

Unlike the original beta.3 run, beta.4's post-publish verification path also completed successfully.

## What beta.4 adds over beta.3

beta.4 packages the post-beta.3 pilot-evidence and evaluation-integrity closure:

```text
PRODUCT_SCHEMA_VERSION = 12
IMMUTABLE_AI_ITEM_PREDICTION = TRUE
LOCAL_EXPLICIT_SELF_REPORT = TRUE
DIRECT_QUESTION_CAPTURE_TIME_PROVENANCE = TRUE
FEEDBACK_RETENTION_INTEGRITY = TRUE
AUTO_RUNTIME_GUIDANCE_ORIGIN_PROVENANCE = TRUE
AUTO_TURN_SHOWN_OR_SILENT_EVIDENCE = TRUE
STABLE_PROMOTION_POLICY = v2.0-R1-stable-promotion-3
REMOTE_PILOT_TELEMETRY = OFF
```

It therefore provides a packaged engineering basis for authorized Project Sync / Design Review pilot collection. It does **not** itself supply the required real pilot observations or independent human labels.

## Current truth boundary

Supported:

```text
V2_BETA_PRERELEASE_PUBLISHED = TRUE
PUBLISHED_BETA_TAG = v2.0.0-beta.4
PUBLISHED_BETA_SOURCE_SHA = 0e1d89ad381a93c1dcd9725418d9cbd5b3c71fcc
STABLE_LATEST = v1.4.2
PILOT_EVIDENCE_CAPTURE_RUNTIME = PACKAGED_BETA_AVAILABLE
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

Google Calendar / Drive / Gmail and Microsoft To Do still require the applicable real-account evidence; Gmail also retains its external OAuth sensitive-scope/publication gate. GitHub provider real-account replay evidence remains separate from beta.4 publication truth.

## Immutability

The beta.4 tag and published binaries remain bound to source SHA `0e1d89ad381a93c1dcd9725418d9cbd5b3c71fcc`.

Any later documentation, pilot or engineering commits on `main` must **not** move, rewrite or republish `v2.0.0-beta.4`. A future downloadable code change requires a new version/tag and a fresh exact-SHA release cycle.
