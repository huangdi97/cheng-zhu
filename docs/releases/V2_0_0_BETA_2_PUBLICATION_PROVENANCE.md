# Chengzhu v2.0.0-beta.2 — Public Prerelease Provenance

**Verified:** 2026-10-09  
**Release:** `v2.0.0-beta.2`  
**Release type:** GitHub Prerelease  
**Stable Latest:** `v1.4.2`  
**Source / tag SHA:** `cac605edf413ec248babf02ea9f73da708d156f8`

---

## 1. Publication truth

GitHub release state:

```text
tag = v2.0.0-beta.2
draft = false
prerelease = true
published_at = 2026-10-09T02:10:24Z
tag SHA = cac605edf413ec248babf02ea9f73da708d156f8
target_commitish = cac605edf413ec248babf02ea9f73da708d156f8
Stable Latest = v1.4.2
```

This permits:

```text
V2_BETA_PRERELEASE_PUBLISHED = TRUE
```

It does **not** permit:

```text
V2_PRODUCTIZED_RELEASE = TRUE
V2_STABLE_RELEASE = TRUE
REAL_USER_VALIDATED = TRUE
PMF_PROVEN = TRUE
```

---

## 2. Published assets

| Asset | Size | GitHub digest |
| --- | ---: | --- |
| `Chengzhu-Setup-x64.exe` | 202,892,375 bytes | `sha256:30928c5413e065c7a262ef6f88be425864dd89b01c3581a4f99691e651332e5c` |
| `Chengzhu-Portable-x64.zip` | 269,121,446 bytes | `sha256:53b09e49cce90d97cf99cf6ba76d31948ebbdb26e2d59e335544d56d43ad4480` |
| `SHA256SUMS.txt` | 181 bytes | `sha256:7c48d5c79ccc40448adccf004f51cd415c9a6e3b0c24f89f13f7e0226af8142d` |
| `RELEASE_NOTES_v2.0.0-beta.2.md` | 7,415 bytes | `sha256:29d3229d12551dea559173e9274612a49830d1f850d152b893f865c7f05390ef` |
| `LICENSE.txt` | 1,087 bytes | `sha256:f9ce30ca6bb69bb231b38bcedb9e4ba0fe891c1093020dd3fcbd5c5f01560718` |
| `THIRD_PARTY_NOTICES.md` | 35,819 bytes | `sha256:3db48e6fd9958e6af1b5e8ceafcb66e728abfcdd19bb939b10a811d5cbe59e2e` |

---

## 3. Provenance invariant

The public tag resolves directly to the same commit recorded by the Release target:

```text
refs/tags/v2.0.0-beta.2
=
cac605edf413ec248babf02ea9f73da708d156f8
=
Release target_commitish
```

The release remains outside the Stable channel:

```text
GitHub Latest = v1.4.2
beta.2 prerelease = true
```

Therefore publishing the Beta did not replace the current Stable Latest release.

---

## 4. Product maturity boundary

beta.2 can support the claim that a **public, downloadable, provenance-pinned Conversation Beta prerelease exists**.

It still cannot establish:

- Opportunity Precision in real meetings;
- Interruption Regret in real meetings;
- Useful Silence quality;
- real cross-session value;
- real cognitive-load reduction;
- profile-specific behavior validation;
- stable v2 readiness;
- PMF.

The next maturity step is real dogfood / human-labeled evaluation, not another synthetic status upgrade.

---

## 5. Remaining explicit external/future gates

The following remain outside beta.2 publication truth:

- Calendar / Docs / Mail / project-tracker connectors;
- actual external email/task/issue/decision-log execution;
- automatic participant chat notice / watermark;
- organization/shared team truth registry;
- code signing;
- macOS signing/notarization;
- stable v2 release;
- real-user validation.

These must stay explicit rather than being represented by placeholders or simulated integrations.
