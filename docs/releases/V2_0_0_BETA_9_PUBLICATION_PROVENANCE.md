# Chengzhu v2.0.0-beta.9 Publication Provenance

Date: 2026-10-13

## Status

```text
RELEASE_TAG = v2.0.0-beta.9
RELEASE_CHANNEL = PRERELEASE
PUBLIC_RELEASE = TRUE
DRAFT = FALSE
STABLE_LATEST = v1.4.2
SOURCE_SHA = 146db913a4467e179d547b37fc006753f64655bb
TAG_SHA = 146db913a4467e179d547b37fc006753f64655bb
PACKAGED_STABLE_POLICY = v2.0-R1-stable-promotion-8
PACKAGED_PILOT_WORKSPACE_CONTRACT = v2.0-R1-pilot-workspace-5
PACKAGED_TOOLCHAIN_FINGERPRINT_CONTRACT = v2.0-R1-pilot-toolchain-1
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
V2_STABLE_RELEASE = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

This file records the authoritative publication truth for the ninth Conversation Beta. It does not promote v2 to Stable and it does not convert evaluator reproducibility or engineering evidence into real-user evidence.

## Source and channel invariants

Observed after publication from the GitHub tag and Release APIs:

- `refs/tags/v2.0.0-beta.9` points directly to `146db913a4467e179d547b37fc006753f64655bb`;
- the Release target is the same exact SHA;
- `prerelease = true`;
- `draft = false`;
- publication timestamp: `2026-10-13T15:10:45Z`;
- GitHub stable `/releases/latest` remains `v1.4.2`.

## Main CI #1021

The exact release source SHA completed all required main CI jobs successfully:

```text
dependency-security = SUCCESS
backend             = SUCCESS
frontend            = SUCCESS
desktop             = SUCCESS
e2e-playwright      = SUCCESS
e2e-visual          = SUCCESS
e2e-smoke           = SUCCESS
packaged-smoke      = SUCCESS
ci-gate             = SUCCESS
```

## Release #328

Release run #328 completed successfully on Windows. The authoritative release path passed:

1. exact source-SHA pinning;
2. backend tests;
3. release version consistency;
4. license gate;
5. frontend build + unit tests;
6. desktop unit tests;
7. clean backend sidecar build;
8. packaged smoke;
9. Electron installer + portable packaging;
10. packaged runtime UI evidence;
11. Conversation Beta packaged UI evidence contract;
12. independent Conversation packaged evidence;
13. clean installer replay;
14. installed-layout smoke;
15. release file collection + SHA256;
16. draft GitHub Release creation;
17. draft download-back verification;
18. final publish;
19. published Release body regression;
20. release-verification metadata regression;
21. download-back verification artifact upload.

No post-publication failure is being reclassified as success here; the GitHub workflow itself concluded SUCCESS.

## Published assets

GitHub currently reports:

| Asset | Size | GitHub digest |
| --- | ---: | --- |
| `Chengzhu-Setup-x64.exe` | 210,748,958 bytes | `sha256:dd0b091a4684f2c5c8f3b2519d307ab394db4479b9e778c2dd25d866b5414597` |
| `Chengzhu-Portable-x64.zip` | 270,667,106 bytes | `sha256:ef2275d1b9b0b7be70a37b719cd4006503c7d6d3c464e73a98b6d9c4c112f378` |
| `SHA256SUMS.txt` | 181 bytes | `sha256:ab7ddfa0c6b4357100c21bb3c34b6d0cf6c3f8c8f9e09aefb4034a2f85e4df4d` |
| `LICENSE.txt` | 1,087 bytes | `sha256:f9ce30ca6bb69bb231b38bcedb9e4ba0fe891c1093020dd3fcbd5c5f01560718` |
| `THIRD_PARTY_NOTICES.md` | 33,389 bytes | `sha256:4ea16e9f1b6a352ba649f8d827e8dd7b78195551690808a25777607c883ea7ac` |
| `RELEASE_NOTES_v2.0.0-beta.9.md` | 4,452 bytes | `sha256:b96cc35038eb925e079a8e0a9369bc9f949ec07d21574551f472b78ce4192f62` |

## What beta.9 packages

beta.9 retains the complete beta.8 Stable Policy v8 evidence-integrity stack and additionally packages Pilot Workspace contract v5 evaluator-toolchain provenance:

```text
STABLE_PROMOTION_POLICY = v2.0-R1-stable-promotion-8
PILOT_WORKSPACE_CONTRACT = v2.0-R1-pilot-workspace-5
PILOT_TOOLCHAIN_FINGERPRINT_CONTRACT = v2.0-R1-pilot-toolchain-1
EVALUATOR_TOOLCHAIN_SHA256_FREEZE = TRUE
TOOLCHAIN_DRIFT = FAIL_CLOSED
```

New Stable-readiness workspaces freeze SHA256 fingerprints for the workspace orchestrator, label seed, feedback exporter, human evaluator, pilot-manifest builder and Stable-readiness evaluator. Finalize/evaluate fail closed if the current evaluator toolchain no longer matches the frozen workspace.

This closes evaluator-implementation drift. It does not prove the human evidence itself is truthful or sufficient.

## Current truth boundary

Supported:

```text
V2_BETA_PRERELEASE_PUBLISHED = TRUE
PUBLISHED_BETA_TAG = v2.0.0-beta.9
PUBLISHED_BETA_SOURCE_SHA = 146db913a4467e179d547b37fc006753f64655bb
PUBLISHED_BETA_PACKAGED_POLICY = v2.0-R1-stable-promotion-8
PUBLISHED_BETA_WORKSPACE_CONTRACT = v2.0-R1-pilot-workspace-5
STABLE_LATEST = v1.4.2
```

Still unsupported:

```text
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
V2_STABLE_RELEASE = FALSE
REAL_USER_VALIDATED = FALSE
REAL_USER_IDENTITY_SYSTEM_VERIFIED = FALSE
REVIEWER_INDEPENDENCE_SYSTEM_VERIFIED = FALSE
PARTICIPANT_CONSENT_SYSTEM_VERIFIED = FALSE
PMF_PROVEN = FALSE
```

The next canonical action is not another Beta feature cycle. It is to create **new** authorized Project Sync / Design Review real-pilot workspaces on beta.9, complete Quick Debrief + permitted self-report + independent review with complete frozen Stable-metric coverage, run Policy v8 Stable readiness using the frozen evaluator toolchain, and then perform a separate human Stable release review if the gate passes.
