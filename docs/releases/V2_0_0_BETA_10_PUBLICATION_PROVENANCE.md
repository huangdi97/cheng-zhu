# Chengzhu v2.0.0-beta.10 Publication Provenance

Date: 2026-10-17

## Status

```text
RELEASE_TAG = v2.0.0-beta.10
RELEASE_CHANNEL = PRERELEASE
PUBLIC_RELEASE = TRUE
DRAFT = FALSE
STABLE_LATEST = v1.4.2
SOURCE_SHA = a6a673326f64e1b6b78e06992e1e2a196bab9076
TAG_SHA = a6a673326f64e1b6b78e06992e1e2a196bab9076

PACKAGED_STABLE_POLICY = v2.0-R1-stable-promotion-8
PACKAGED_PILOT_WORKSPACE_CONTRACT = v2.0-R1-pilot-workspace-7
PACKAGED_TOOLCHAIN_CONTRACT = v2.0-R1-pilot-toolchain-3
PACKAGED_RUNTIME_BASELINE_CONTRACT = v2.0-R1-pilot-runtime-baseline-2
PACKAGED_PYTHON_ARTIFACT_PROVENANCE = v2.0-R1-python-artifact-provenance-1
PACKAGED_STABLE_REPLAY_CONTRACT = v2.0-R1-stable-python-environment-replay-2
PACKAGED_STABLE_REVIEW_HANDOFF = v2.0-R1-stable-review-handoff-4
SIDE_CAR_PYTHON = 3.13.16

PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
V2_STABLE_RELEASE = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

This file records the authoritative publication truth for the tenth Conversation Beta. It does **not** promote v2 to Stable and it does not convert runtime/build reproducibility, packaged engineering evidence, or release authorization plumbing into real-user evidence.

## Source and channel invariants

Observed after publication from the GitHub tag and Release APIs:

- `refs/tags/v2.0.0-beta.10` points directly to `a6a673326f64e1b6b78e06992e1e2a196bab9076`;
- the Release target is the same exact SHA;
- `prerelease = true`;
- `draft = false`;
- publication timestamp: `2026-10-17T07:30:57Z`;
- GitHub stable `/releases/latest` remains `v1.4.2`.

The beta.10 tag is an immutable release source boundary. Later documentation commits on `main` must not move this tag or replace the published binaries.

## Main CI #1074

The exact release source SHA `a6a673326f64e1b6b78e06992e1e2a196bab9076` completed every required main CI job successfully:

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

The Windows packaged-smoke path rebuilt the backend sidecar and passed the packaged runtime checks on the exact merged main SHA.

## Release #404

Release run #404 completed successfully on Windows from the same exact source SHA.

The authoritative path passed:

1. exact source-SHA pinning;
2. backend tests;
3. release version consistency;
4. candidate runtime build provenance;
5. Stable green-main source wrapper regression;
6. Stable v2+ exact green-main source gate;
7. license gate;
8. frontend build + unit tests;
9. desktop unit tests;
10. exact pilot Python wheel-artifact replay;
11. clean-venv PyInstaller backend sidecar build;
12. embedded build-provenance equality against the candidate;
13. Stable v2+ release-authorization gate;
14. packaged sidecar smoke with restart/persistence;
15. Windows installer + portable packaging;
16. packaged runtime UI evidence;
17. Conversation Beta packaged UI evidence contract;
18. independent Conversation packaged evidence;
19. fresh Windows clean-installer replay;
20. installed-layout smoke;
21. release-file collection + SHA256;
22. draft GitHub Release creation targeted at the exact source SHA;
23. download-back verification from the GitHub draft assets;
24. final publication;
25. published Release-body regression;
26. release-verification metadata regression;
27. post-publish download-back verification artifact upload.

The workflow itself concluded **SUCCESS**. No post-publication failure is being reclassified as success.

## Published assets

GitHub currently reports:

| Asset | Size | GitHub digest |
| --- | ---: | --- |
| `BUILD_PROVENANCE.json` | 21,843 bytes | `sha256:b3729c0ca57545c819fef997246e078216a5131fbfc189a2d01d1bbdeae5249d` |
| `Chengzhu-Portable-x64.zip` | 270,720,398 bytes | `sha256:9e405edf6f94e45606c5bb4273727711858d7e68bf1b0cb3e893622e56bdca96` |
| `Chengzhu-Setup-x64.exe` | 210,527,372 bytes | `sha256:df1e66f5e0058c3e0301c16981312c1882f424d0cff18af386b47eaf9e5e0aeb` |
| `LICENSE.txt` | 1,087 bytes | `sha256:f9ce30ca6bb69bb231b38bcedb9e4ba0fe891c1093020dd3fcbd5c5f01560718` |
| `RELEASE_AUTHORIZATION.json` | 238 bytes | `sha256:18dead67be1c48e2abe3f4ce7491e32fbbc9c7b4eb993be4774c3943db484bf0` |
| `RELEASE_NOTES_v2.0.0-beta.10.md` | 6,961 bytes | `sha256:ab363824dd5639a4b7b25a9d9911b60cc44a687a6c5772b60426c025274f77db` |
| `SHA256SUMS.txt` | 362 bytes | `sha256:81b0ae5b90a218cd8a4c62f1a7491eed2478522a8fdbb5d47f3c771864df84ad` |
| `THIRD_PARTY_NOTICES.md` | 33,389 bytes | `sha256:4ea16e9f1b6a352ba649f8d827e8dd7b78195551690808a25777607c883ea7ac` |

`RELEASE_AUTHORIZATION.json` is part of the channel/release audit surface. For this **prerelease**, it must not be interpreted as a human Stable-v2 GO. Stable v2+ remains subject to the separate human release-review authorization path.

## What beta.10 packages

beta.10 keeps Stable Promotion Policy v8 unchanged while making the future Stable-pilot runtime baseline reproducible at a deeper level:

```text
STABLE_PROMOTION_POLICY = v2.0-R1-stable-promotion-8
PILOT_WORKSPACE_CONTRACT = v2.0-R1-pilot-workspace-7
PILOT_TOOLCHAIN_CONTRACT = v2.0-R1-pilot-toolchain-3
PILOT_RUNTIME_BASELINE_CONTRACT = v2.0-R1-pilot-runtime-baseline-2
PYTHON_ARTIFACT_PROVENANCE_CONTRACT = v2.0-R1-python-artifact-provenance-1
STABLE_PYTHON_REPLAY_CONTRACT = v2.0-R1-stable-python-environment-replay-2
STABLE_REVIEW_HANDOFF_CONTRACT = v2.0-R1-stable-review-handoff-4
```

The packaged runtime now freezes and can replay:

- exact source/build provenance;
- schema-v13 packaged runtime provenance;
- exact Python 3.13.16 interpreter baseline;
- resolved Python `name==version` environment;
- exact wheel filename + SHA256 artifact set;
- hash-checking replay with wheel-only, no-cache clean environments;
- post-build runtime/environment/artifact equivalence;
- Stable handoff and explicit human-GO release-control boundaries;
- current-green-main equality before future Stable publication.

These controls improve reproducibility and release integrity. They do not establish reviewer identity, participant consent, user value, or PMF.

## Historical compatibility boundary

beta.9 and earlier prereleases remain valid immutable historical releases, but they do not contain beta.10 capture-time runtime/wheel-artifact provenance.

Therefore:

```text
pre-beta.10 pilot/runtime
!=
workspace-v7 artifact-provenance baseline
```

Do not reconstruct an older pilot later from current package indexes and relabel it as if those hashes were captured by the older runtime.

## Current truth boundary

Supported:

```text
V2_BETA_PRERELEASE_PUBLISHED = TRUE
PUBLISHED_BETA_TAG = v2.0.0-beta.10
PUBLISHED_BETA_SOURCE_SHA = a6a673326f64e1b6b78e06992e1e2a196bab9076
PUBLISHED_BETA_PACKAGED_POLICY = v2.0-R1-stable-promotion-8
PUBLISHED_BETA_WORKSPACE_CONTRACT = v2.0-R1-pilot-workspace-7
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

## Next canonical action

The next canonical action is **not** another prerelease feature cycle.

Use beta.10 to create new authorized Project Sync / Design Review Stable-readiness workspaces, collect real sessions, complete Quick Debrief / permitted self-report / independent review with complete frozen eligible-population coverage, and run Stable Policy v8. Only a real PASS may enter the separate human Stable release-review path.

A new beta is justified only by a material product/evidence/release correctness issue discovered from that real pilot or by a deliberately scoped necessary fix.