# Chengzhu v2.0.0-beta.8 Publication Provenance

Date: 2026-10-13

## Status

```text
RELEASE_TAG = v2.0.0-beta.8
RELEASE_CHANNEL = PRERELEASE
PUBLIC_RELEASE = TRUE
DRAFT = FALSE
STABLE_LATEST = v1.4.2
SOURCE_SHA = 9442e9891453aff3b1e482933056593b893f6288
TAG_SHA = 9442e9891453aff3b1e482933056593b893f6288
PACKAGED_STABLE_POLICY = v2.0-R1-stable-promotion-8
REAL_USER_VALIDATED = FALSE
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
V2_STABLE_RELEASE = FALSE
PMF_PROVEN = FALSE
```

This file records the authoritative publication truth for the eighth Conversation Beta. It does not promote v2 to Stable and it does not convert engineering/evaluator correctness into real-user evidence.

## Source and channel invariants

Observed from the GitHub Release API after publication:

- `v2.0.0-beta.8` targets exact source SHA `9442e9891453aff3b1e482933056593b893f6288`;
- `prerelease = true`;
- `draft = false`;
- publication timestamp: `2026-10-13T13:04:59Z`;
- GitHub stable `/releases/latest` remains `v1.4.2`.

The exact main SHA passed CI run #1015 before release dispatch.

## Main CI #1015

All required jobs completed successfully:

```text
dependency-security = SUCCESS
backend             = SUCCESS
frontend            = SUCCESS
desktop             = SUCCESS
e2e-visual          = SUCCESS
e2e-playwright      = SUCCESS
packaged-smoke      = SUCCESS
e2e-smoke           = SUCCESS
ci-gate             = SUCCESS
```

## Release #326

Release run #326 completed successfully on Windows. The release pipeline passed:

1. exact source-SHA pinning;
2. backend tests;
3. version consistency;
4. license gate;
5. frontend build + unit tests;
6. desktop unit tests;
7. clean backend sidecar build;
8. packaged smoke;
9. Electron installer + portable packaging;
10. packaged runtime UI evidence;
11. Conversation Beta packaged UI evidence contract;
12. independent packaged evidence;
13. clean installer replay;
14. installed-layout smoke;
15. release file collection + SHA256;
16. draft GitHub Release creation;
17. draft download-back verification;
18. final publish;
19. published Release body regression;
20. release-verification metadata regression;
21. download-back verification artifact upload.

Therefore beta.8 does not inherit the beta.3 post-publish metadata failure: the corrected publication/provenance path itself passed.

## Published assets

GitHub reports these public assets and digests:

| Asset | Size | GitHub digest |
| --- | ---: | --- |
| `Chengzhu-Setup-x64.exe` | 210,749,700 bytes | `sha256:6c83344e7084cbee98b6848778608dd4e036377103ebca5264e4e9f53df2caa8` |
| `Chengzhu-Portable-x64.zip` | 270,667,737 bytes | `sha256:0306243d929d66ddb27d9a17316f7ae092f2226f1ccf7a2d5894712cd289b6fe` |
| `SHA256SUMS.txt` | 181 bytes | `sha256:64ee28af1eea7bb5901875068d0567399a172d6e680ceeaa0bfd6831fe467c54` |
| `LICENSE.txt` | 1,087 bytes | `sha256:f9ce30ca6bb69bb231b38bcedb9e4ba0fe891c1093020dd3fcbd5c5f01560718` |
| `THIRD_PARTY_NOTICES.md` | 33,389 bytes | `sha256:4ea16e9f1b6a352ba649f8d827e8dd7b78195551690808a25777607c883ea7ac` |
| `RELEASE_NOTES_v2.0.0-beta.8.md` | 4,526 bytes | `sha256:9aaed7f12cd23346d766b6a276de90e9e0852823c53b599e783d1e841c25f60d` |

## What beta.8 packages

beta.8 is the canonical public prerelease baseline for new Stable-readiness workspaces because it packages Stable Promotion Policy v8:

```text
STABLE_PROMOTION_POLICY = v2.0-R1-stable-promotion-8
STABLE_METRIC_COVERAGE_POLICY = COMPLETE_FROZEN_ELIGIBLE_POPULATION
STABLE_METRIC_COVERAGE_CONTRACT = v2.0-R1-stable-metric-coverage-1
```

Policy v8 requires complete coverage of the frozen eligible event × metric population before numerical thresholds and `min_n` can pass. This closes favorable-subset / denominator-selection bias; it does not raise the maturity claim.

beta.8 also retains the earlier v2 pilot/evidence hardening stack, including:

- immutable Conversation Item prediction snapshots;
- Direct Question capture-time prediction provenance;
- Guidance/SILENT runtime-origin provenance;
- feedback-retention referential integrity;
- scope-aware dependency-security gates;
- authorized pilot manifest/workspace orchestration;
- privacy-minimized Session inventory;
- WAL-safe cohort provenance and finalize TOCTOU protection;
- frozen-seed independent-review event binding;
- unique-event-per-metric Stable sample unit;
- single-user cross-session Space binding.

## Current truth boundary

Supported:

```text
V2_BETA_PRERELEASE_PUBLISHED = TRUE
PUBLISHED_BETA_TAG = v2.0.0-beta.8
PUBLISHED_BETA_SOURCE_SHA = 9442e9891453aff3b1e482933056593b893f6288
PUBLISHED_BETA_PACKAGED_POLICY = v2.0-R1-stable-promotion-8
STABLE_LATEST = v1.4.2
```

Still unsupported:

```text
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
V2_STABLE_RELEASE = FALSE
REAL_USER_VALIDATED = FALSE
REAL_USER_IDENTITY_SYSTEM_VERIFIED = FALSE
PMF_PROVEN = FALSE
```

The next canonical action is to create **new** authorized Project Sync / Design Review pilot workspaces on beta.8 (or a later prerelease that explicitly packages the same or stricter policy), complete Quick Debrief + independent review, and run the frozen Policy v8 Stable-readiness evaluator. No further Beta feature expansion is justified merely to manufacture progress.
