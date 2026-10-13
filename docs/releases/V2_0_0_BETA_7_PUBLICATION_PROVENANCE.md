# Chengzhu v2.0.0-beta.7 Publication Provenance

Date: 2026-10-13

## Status

```text
RELEASE_TAG = v2.0.0-beta.7
RELEASE_CHANNEL = PRERELEASE
PUBLIC_RELEASE = TRUE
DRAFT = FALSE
STABLE_LATEST = v1.4.2
SOURCE_SHA = dc2188cd6b796b5dca9baf0eac2372da7be5bbf2
TAG_SHA = dc2188cd6b796b5dca9baf0eac2372da7be5bbf2
PACKAGED_STABLE_POLICY = v2.0-R1-stable-promotion-7
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
V2_STABLE_RELEASE = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

This document freezes the observed publication truth for the seventh Conversation Beta. It does **not** promote v2 to stable and does not convert pilot infrastructure or engineering evidence into real-user evidence.

## Source and channel invariants

Observed independently after publication from the GitHub Release/tag APIs and Release run #324:

- `refs/tags/v2.0.0-beta.7` points directly to commit `dc2188cd6b796b5dca9baf0eac2372da7be5bbf2`;
- the public Release target is the same exact SHA;
- `prerelease = true`;
- `draft = false`;
- GitHub stable `/releases/latest` remains `v1.4.2`;
- publication timestamp: `2026-10-13T11:09:49Z`.

Therefore beta.7 did not replace the Stable Latest channel.

## Exact-main and Release gates

The beta.7 freeze PR passed CI #991 and Windows Release PR-mode #323 before merge.

The merged release-candidate main SHA `dc2188cd6b796b5dca9baf0eac2372da7be5bbf2` then passed exact-main CI #992, including:

- Backend;
- Frontend;
- Desktop;
- dependency-security;
- Playwright;
- visual;
- e2e smoke;
- packaged smoke;
- aggregate `ci-gate`.

The generic publisher then validated all distributable version surfaces as `2.0.0-beta.7` and dispatched the real Release workflow from that exact green main SHA.

## Release run #324

GitHub Actions run `38386050799` completed successfully against the exact source SHA above.

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
18. final public prerelease publication;
19. published Release-body regression;
20. post-publish verification-metadata regression;
21. upload of the download-back verification artifact.

The GitHub Release page now begins with an authoritative generated status block stating:

```text
Published = TRUE
Channel = PRERELEASE
Tag/source = v2.0.0-beta.7 -> dc2188cd6b796b5dca9baf0eac2372da7be5bbf2
Stable Latest = v1.4.2
```

The original release-note body remains immutable historical evidence and may still contain candidate/future-tense wording; the generated published-status block and this provenance document are authoritative for current publication state.

## Published assets

GitHub currently reports:

| Asset | Size | GitHub digest |
| --- | ---: | --- |
| `Chengzhu-Setup-x64.exe` | 210,750,130 bytes | `sha256:61ac86c4a0093b4b33dafacbae4e64f9b96bc2720958821eb562e8b26c90ec6b` |
| `Chengzhu-Portable-x64.zip` | 270,666,842 bytes | `sha256:0e8ecf563f416d3df7f4d899a39445189197761fddb718af450957a428dc06ce` |
| `SHA256SUMS.txt` | 181 bytes | `sha256:39607f34724e661514b15b5fbb7a8c8e9497a206e1ee7968d75ff8ebd6024f52` |
| `LICENSE.txt` | 1,087 bytes | `sha256:f9ce30ca6bb69bb231b38bcedb9e4ba0fe891c1093020dd3fcbd5c5f01560718` |
| `THIRD_PARTY_NOTICES.md` | 33,389 bytes | `sha256:4ea16e9f1b6a352ba649f8d827e8dd7b78195551690808a25777607c883ea7ac` |
| `RELEASE_NOTES_v2.0.0-beta.7.md` | 3,926 bytes | `sha256:df2d411b3c3ff1219d15406fde5b527140420941fb7d281bcd0d8ef4fbfd0675` |

## What beta.7 packages

beta.7 is a **Stable-evidence correctness prerelease**, not a feature-expansion release.

It preserves the beta.6 real-pilot operationalization stack:

- Quick Debrief;
- schema v10-v12 Pilot Evidence Bridge;
- immutable AI prediction / Direct Question provenance;
- feedback-retention integrity;
- TRANSCRIPT_AUTO Guidance / SILENT provenance;
- privacy-minimized Session inventory;
- authorized pilot manifest and fail-closed workspace orchestration;
- WAL-safe selected-cohort logical snapshots;
- finalize-time double cohort revalidation;
- frozen independent-review seed binding;
- unique-event-per-metric Stable sample units;
- scope-aware dependency-security gates;
- stale-main and explicit release-hold protections.

Its material correction is packaged Stable Promotion Policy v7:

```text
QUALIFYING_CROSS_SESSION_SPACE =
  same space_id
  + exactly one pseudonymous user_ref
  + >= 3 authorized Sessions for that same user

MIXED_USER_SPACE = FAIL_CLOSED
```

No numerical quality threshold, `min_n`, profile user/session/space floor, label-source rule or unique-event sample-unit rule was relaxed from v6.

## Current truth boundary

Supported:

```text
V2_BETA_PRERELEASE_PUBLISHED = TRUE
PUBLISHED_BETA_TAG = v2.0.0-beta.7
PUBLISHED_BETA_SOURCE_SHA = dc2188cd6b796b5dca9baf0eac2372da7be5bbf2
PUBLISHED_BETA_PACKAGED_POLICY = v2.0-R1-stable-promotion-7
STABLE_LATEST = v1.4.2
PRODUCT_VALIDATION_INFRA_COMPLETE = TRUE
```

Still unsupported:

```text
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
V2_STABLE_RELEASE = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
REAL_USER_IDENTITY_SYSTEM_VERIFIED = FALSE
REVIEWER_INDEPENDENCE_SYSTEM_VERIFIED = FALSE
PARTICIPANT_CONSENT_SYSTEM_VERIFIED = FALSE
```

The correct next phase is the first authorized real Project Sync / Design Review pilot under packaged Policy v7. A beta.8 is not justified merely to create visible progress; another prerelease should require a real pilot/runtime defect, material evidence-correctness issue, or distributable provider/runtime change.
