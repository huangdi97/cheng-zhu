# Chengzhu v2.0.0-beta.6 Publication Provenance

Date: 2026-10-12

## Status

```text
RELEASE_TAG = v2.0.0-beta.6
RELEASE_CHANNEL = PRERELEASE
PUBLIC_RELEASE = TRUE
DRAFT = FALSE
STABLE_LATEST = v1.4.2
SOURCE_SHA = 38a70b719b2d5b0c9e8273e6a908fed9229ab706
TAG_SHA = 38a70b719b2d5b0c9e8273e6a908fed9229ab706
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

This document freezes the observed publication truth for the sixth Conversation Beta. It does **not** promote v2 to stable and does not convert engineering/pilot infrastructure into real-user evidence.

## Source and channel invariants

Observed after publication from the GitHub Release/tag APIs and Release run #318:

- `refs/tags/v2.0.0-beta.6` points directly to commit `38a70b719b2d5b0c9e8273e6a908fed9229ab706`;
- the public Release target is the same exact SHA;
- `prerelease = true`;
- `draft = false`;
- GitHub stable `/releases/latest` remains `v1.4.2`;
- publication timestamp: `2026-10-12T18:19:56Z`.

Therefore beta.6 did not replace the stable Latest channel.

## Release run #318

GitHub Actions run `38287966647` completed successfully against the exact source SHA above.

The Windows release path passed:

1. exact source-SHA checkout/pin;
2. Backend tests;
3. release-version consistency;
4. license gate;
5. Frontend build + unit tests;
6. Desktop unit tests;
7. clean backend-sidecar build;
8. packaged smoke with restart/persistence;
9. installer + portable packaging;
10. packaged runtime UI evidence capture;
11. Conversation packaged UI evidence contract;
12. independent Conversation packaged evidence;
13. clean installer replay;
14. installed-layout smoke;
15. release file collection + SHA256;
16. draft GitHub Release creation targeted at the exact source SHA;
17. download-back verification from the draft Release;
18. downloaded-asset SHA256 verification;
19. downloaded installer replay + packaged smoke;
20. final public prerelease publication;
21. Stable Latest preservation;
22. public tag/source equality;
23. post-publish verification-metadata regression;
24. upload of the download-back verification artifact.

The workflow explicitly reported:

```text
draft release target/source invariant:
v2.0.0-beta.6 -> 38a70b719b2d5b0c9e8273e6a908fed9229ab706

prerelease channel invariant:
v2.0.0-beta.6 is prerelease; stable Latest remains v1.4.2

published release tag/source invariant:
v2.0.0-beta.6 -> 38a70b719b2d5b0c9e8273e6a908fed9229ab706
```

The final `chengzhu-download-back-verification` Actions artifact was successfully uploaded by Release #318.

## Published assets

GitHub currently reports:

| Asset | Size | GitHub digest |
| --- | ---: | --- |
| `Chengzhu-Setup-x64.exe` | 210,738,741 bytes | `sha256:f8b26c2ef010f0cbc105f61a58ef7c3f1d1c97e4ecad6602afaeb934885b8fda` |
| `Chengzhu-Portable-x64.zip` | 270,657,725 bytes | `sha256:3ee994219d9d5c16c537351eab15e7ddc3ad7b80ad141bb5864095893ce8bb36` |
| `SHA256SUMS.txt` | 181 bytes | `sha256:5bec3f184d30b2a4a967cf2ce3c865c58c9b7b50fa5794011f1449c264495fe2` |
| `LICENSE.txt` | 1,087 bytes | `sha256:f9ce30ca6bb69bb231b38bcedb9e4ba0fe891c1093020dd3fcbd5c5f01560718` |
| `THIRD_PARTY_NOTICES.md` | 33,389 bytes | `sha256:4ea16e9f1b6a352ba649f8d827e8dd7b78195551690808a25777607c883ea7ac` |
| `RELEASE_NOTES_v2.0.0-beta.6.md` | 11,621 bytes | `sha256:a5ca9ee93e4d10a6ef46d6ac48f1a8aac2cf317b3d884378b39a6efb3d75fdc3` |

## What beta.6 actually packages

beta.6 is the **real-pilot operationalization** prerelease. Relative to beta.5, the packaged/user-facing delta includes the immediate post-Session Quick Debrief while preserving the existing detailed Guidance/SILENT review path.

The exact beta.6 source also includes the current fail-closed real-pilot evidence chain present at source SHA `38a70b7...`, including:

- Stable Promotion Policy v6 cohort/sample-unit contract;
- authorized pilot manifest/workspace orchestration;
- privacy-minimized Session inventory;
- selected-cohort provenance and WAL-safe logical snapshot validation;
- finalize-time TOCTOU revalidation;
- independent-review rows bound to the frozen seed/event/prediction provenance;
- unique-event-per-metric Stable sample-unit enforcement.

These mechanisms make pilot evidence more reproducible. They do **not** verify human identity, real-world authorization, reviewer independence, participant consent truth, or PMF by themselves.

## Historical release-notes boundary

The published `RELEASE_NOTES_v2.0.0-beta.6.md` asset was authored while beta.6 was still a candidate and therefore contains candidate/future-tense wording. That asset is part of the immutable release evidence and must not be silently rewritten after publication.

Current publication truth belongs in this provenance document and current canonical/release status documents, while the original release-notes bytes remain unchanged.

## Current truth boundary

Supported:

```text
V2_BETA_PRERELEASE_PUBLISHED = TRUE
PUBLISHED_BETA_TAG = v2.0.0-beta.6
PUBLISHED_BETA_SOURCE_SHA = 38a70b719b2d5b0c9e8273e6a908fed9229ab706
STABLE_LATEST = v1.4.2
PRODUCT_VALIDATION_INFRA_COMPLETE = TRUE
```

Still unsupported:

```text
V2_STABLE_RELEASE = FALSE
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
GOOGLE_REAL_ACCOUNT_VALIDATED = FALSE
MICROSOFT_REAL_ACCOUNT_VALIDATED = FALSE
```

The correct next phase is authorized Project Sync / Design Review pilot execution and independent review under the frozen policy—not another feature-expansion Beta by default.
