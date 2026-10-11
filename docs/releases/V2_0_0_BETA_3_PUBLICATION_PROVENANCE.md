# Chengzhu v2.0.0-beta.3 Publication Provenance

Date: 2026-10-11

## Status

```text
RELEASE_TAG = v2.0.0-beta.3
RELEASE_CHANNEL = PRERELEASE
PUBLIC_RELEASE = TRUE
DRAFT = FALSE
STABLE_LATEST = v1.4.2
SOURCE_SHA = b0cbfb628a5fc224c571288b92576992fa25dc77
TAG_SHA = b0cbfb628a5fc224c571288b92576992fa25dc77
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

This document records the observed GitHub publication truth for the third Conversation Beta. It does **not** promote v2 to stable and does not convert engineering evidence into real-user evidence.

## Source and channel invariants

Observed from the GitHub Release and tag APIs after publication:

- `refs/tags/v2.0.0-beta.3` points directly to commit `b0cbfb628a5fc224c571288b92576992fa25dc77`;
- the Release target is the same SHA;
- `prerelease = true`;
- `draft = false`;
- the GitHub stable `/releases/latest` remains `v1.4.2`;
- publication timestamp: `2026-10-11T13:39:24Z`.

Therefore beta.3 did not replace the stable Latest channel.

## Published assets

GitHub currently reports these public assets and digests:

| Asset | Size | GitHub digest |
| --- | ---: | --- |
| `Chengzhu-Setup-x64.exe` | 204,058,802 bytes | `sha256:8636d97dd2c64ae622c315e0ef708a898a13a0ed8302e6f3d2a400bbd3cb63b5` |
| `Chengzhu-Portable-x64.zip` | 270,595,577 bytes | `sha256:5f9bb1bde627e43509a950461c891a5dfa67260032898232df7306f53d0f6962` |
| `SHA256SUMS.txt` | 181 bytes | `sha256:74c0788d231e527dc9afc49fddcfe37b0ea1d5dc041fa4d6a1f52e5c1e95a98d` |
| `LICENSE.txt` | 1,087 bytes | `sha256:f9ce30ca6bb69bb231b38bcedb9e4ba0fe891c1093020dd3fcbd5c5f01560718` |
| `THIRD_PARTY_NOTICES.md` | 35,819 bytes | `sha256:3db48e6fd9958e6af1b5e8ceafcb66e728abfcdd19bb939b10a811d5cbe59e2e` |
| `RELEASE_NOTES_v2.0.0-beta.3.md` | 6,564 bytes | `sha256:ede25f19b744a53ab6752dcae4c8c26aba4771dd54d2ccedc4450e97db221955` |

## Release run #300: what passed

GitHub Actions run `38142855313` (`Release` #300) was dispatched against the exact source SHA above.

Before the job was marked failed, the log shows the release-critical path had already completed:

1. build/test/version/license gates;
2. Windows package generation;
3. clean-install replay;
4. draft GitHub Release creation targeted at the exact source SHA;
5. download-back of installer, portable and `SHA256SUMS.txt`;
6. downloaded-asset SHA256 verification;
7. silent install of the **downloaded** installer;
8. packaged smoke from the downloaded/installed resources;
9. packaged smoke result `passed = true`;
10. publication of the verified draft;
11. prerelease-channel verification;
12. Stable Latest verification (`v1.4.2`);
13. public tag/source SHA verification.

The downloaded-install packaged smoke observed, among other checks:

```text
version = 2.0.0-beta.3
frontend_served = true
fast_cue_before_deep = true
conversation_preflight_ready = true
conversation_pack_frozen = true
conversation_decision_reviewed = true
conversation_ask_grounded = true
conversation_global_search_grounded = true
conversation_continue_reviewed_truth = true
conversation_export_scoped = true
conversation_pack_persisted_after_restart = true
conversation_history_persisted = true
conversation_reviewed_truth_persisted = true
conversation_diagnostics_healthy = true
install_dir_unchanged = true
license_bundled = true
third_party_notices_bundled = true
passed = true
```

## Why the workflow still ended in failure

The failure occurred **after publication and after tag/source verification** while enriching the local `download-back-verification.json`.

The pre-publish JSON intentionally omitted publication-only fields such as `release_channel` and `is_prerelease`. PowerShell's `ConvertFrom-Json` returns a `PSCustomObject` with the source JSON's fixed property shape. The workflow then attempted direct assignment:

```powershell
$verification.release_channel = "PRERELEASE"
```

PowerShell raised:

```text
The property 'release_channel' cannot be found on this object.
Verify that the property exists and can be set.
```

This means the workflow conclusion `failure` is a **post-publish evidence-enrichment defect**, not a binary-build, download-back, installer, packaged-runtime, release-channel, or tag/source failure.

Because the job aborted at that point, the final `chengzhu-download-back-verification` Actions artifact was not uploaded for run #300. That missing uploaded evidence artifact must not be rewritten as if it existed.

## Corrective action

The release workflow is changed to use a dedicated PowerShell helper that enriches JSON through `Add-Member -Force`, which safely supports both existing and previously absent fields:

```text
tag_sha
release_channel
is_prerelease
```

A PR-stage regression fixture is also added to the Windows Release workflow so this exact PSCustomObject-shape bug is exercised before any future real publication.

## Current truth boundary

The following are supported:

```text
V2_BETA_PRERELEASE_PUBLISHED = TRUE
PUBLISHED_BETA_TAG = v2.0.0-beta.3
PUBLISHED_BETA_SOURCE_SHA = b0cbfb628a5fc224c571288b92576992fa25dc77
STABLE_LATEST = v1.4.2
```

The following remain unsupported and must stay false:

```text
V2_STABLE_RELEASE = FALSE
V2_PRODUCTIZED_RELEASE = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
GOOGLE_REAL_ACCOUNT_VALIDATED = FALSE
MICROSOFT_REAL_ACCOUNT_VALIDATED = FALSE
```
