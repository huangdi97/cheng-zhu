# Release

## Release truth

A successful local build is **not** a release.

A release is complete only when GitHub contains the published assets and the workflow has downloaded them back, verified them and replayed installation/smoke from the downloaded files.

## Release channels

Chengzhu has two independent public channels:

```text
Stable
Prerelease / Beta
```

Rules:

- a stable SemVer such as `1.4.2` publishes as a normal GitHub Release and may become `Latest`;
- a SemVer prerelease such as `2.0.0-beta.2` publishes with `prerelease=true` and `latest=false`;
- publishing a Beta must never replace the current stable `/releases/latest`;
- a Beta uses the same exact-SHA, clean-install, SHA256, download-back and provenance gates as stable;
- a public Beta proves productization engineering, not real-user value or PMF.

Current channel truth:

```text
Stable Latest = v1.4.2
Conversation Beta Published = v2.0.0-beta.9
Published Beta tag/source SHA = 146db913a4467e179d547b37fc006753f64655bb
Published Beta packaged Stable Policy = v2.0-R1-stable-promotion-8
Published Pilot Workspace Contract = v2.0-R1-pilot-workspace-5
Published Toolchain Fingerprint Contract = v2.0-R1-pilot-toolchain-1
V2_BETA_PRERELEASE_PUBLISHED = TRUE
Stable v2 = NOT CLAIMED
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

Published beta.9 provenance is recorded in `docs/releases/V2_0_0_BETA_9_PUBLICATION_PROVENANCE.md`. beta.9 is the current **public** Stable-evidence reproducibility prerelease. It packages Stable Policy v8 plus Pilot Workspace contract v5 / toolchain fingerprint contract v1, so new Stable-readiness workspaces freeze the evaluator implementation SHA256 set as well as cohort/policy/seed evidence. beta.9 was published from exact green main SHA `146db913a4467e179d547b37fc006753f64655bb` after CI #1021 and Release #328 completed successfully; Stable Latest remains `v1.4.2`.

beta.8 / beta.7 / beta.6 / beta.5 / beta.4 / beta.3 remain immutable historical prereleases. Do not rewrite older workspaces/releases as if they had workspace-v5 evaluator-toolchain provenance.

beta.8 was published from exact green main/tag SHA `9442e9891453aff3b1e482933056593b893f6288` through main CI #1015 and Release run #326 after dependency-security, Backend/Frontend/Desktop gates, Windows build, packaged UI evidence, clean-install replay, installed-layout smoke, draft download-back, SHA256 verification, final publish, Release-page truth regression, Stable-Latest preservation, tag/source equality and post-publish verification-artifact upload all completed successfully. It retains beta.7's single-user cross-session Space binding and further packages **Stable Policy v8** complete frozen eligible-population coverage. Numerical quality thresholds, min_n values and profile floors remain unchanged. beta.7 / beta.6 / beta.5 / beta.4 / beta.3 remain immutable historical releases and must not be rewritten as containing beta.8 changes.

The generic publisher is `.github/workflows/publish-current-version-on-green-main.yml`. It reads the version from the exact green main SHA and dispatches `release.yml` against that immutable SHA. Historical version-specific publishers may remain for release provenance; they must no-op when the current version does not match their pinned version.

Two additional fail-closed controls apply before dispatch:

- **current-main guard**: the green CI `head_sha` must still equal the current `main` tip. A stale green main SHA is reproducible, but it is not eligible to publish an unpublished version after main has advanced.
- **explicit release hold**: while `.github/RELEASE_HOLD` exists in the green source SHA, the generic publisher must no-op. Removing the hold creates a new main SHA which must pass CI again before release dispatch.

Use the hold for a confirmed release-blocking issue discovered after a release candidate version has already landed on main. Do not bypass it by manually dispatching an older SHA.


## Windows artifacts

| File | Purpose |
|---|---|
| `Chengzhu-Setup-x64.exe` | per-user NSIS installer |
| `Chengzhu-Portable-x64.zip` | portable app |
| `SHA256SUMS.txt` | checksums |
| `LICENSE.txt` | root MIT license |
| `THIRD_PARTY_NOTICES.md` | third-party licensing |
| `RELEASE_NOTES_vX.Y.Z.md` | version-specific release notes |
| `RELEASE_AUTHORIZATION.json` | channel authorization audit: Beta = not required; Stable v2+ = verified human Stable-review GO |

Target machines do not require Python, Node, npm or pip.

## Stable v2+ publication authorization

Stable major version 2 and later is **never** auto-published merely because a version bump reached green `main`.

The enforced path is:

```text
authorized real pilot
→ frozen Stable evaluator PASS
→ stable-review-handoff
→ explicit human review of every release check
→ GO decision bound to exact candidate SHA + stable version
→ privacy-minimized authorization token
→ manual Release workflow
→ authorization recheck
→ build / clean-install / download-back / tag-source verification
→ Stable publish
```

The generic publisher explicitly no-ops for unpublished Stable v2+ versions. Manual `release.yml` publication must provide `stable_review_authorization_b64`; the workflow validates it with `scripts/verify_stable_release_authorization.py` and writes `RELEASE_AUTHORIZATION.json` into the release evidence/assets. A tag-push path cannot bypass this requirement.

Generate the decision only after a PASS handoff and on the exact clean candidate checkout:

```bash
python scripts/v2_stable_release_review_decision.py init \
  --handoff-dir <stable-handoff> \
  --candidate-source-sha <40-char-sha> \
  --candidate-version 2.0.0 \
  --out stable-release-review.draft.json

# Human reviewer edits every check to PASS/FAIL and supplies non-sensitive evidence_ref.

python scripts/v2_stable_release_review_decision.py finalize \
  --handoff-dir <stable-handoff> \
  --draft stable-release-review.draft.json \
  --out-dir stable-release-review-decision
```

Only a fully reviewed GO emits `stable-release-authorization.b64`. A NO_GO decision never emits a usable release token.

Important truth boundary:

```text
HUMAN_RELEASE_REVIEW_GO != V2_STABLE_RELEASE
AUTHORIZATION_TOKEN != PUBLICATION
STABLE_WORKFLOW_SUCCESS + PUBLIC TAG/ASSETS = RELEASE FACT
PMF_PROVEN remains separate
```

The authorization mechanism prevents accidental/process bypass. It does not cryptographically prove reviewer identity, real-world authorization, participant consent, or reviewer independence; those remain explicit human evidence boundaries.

## Release pipeline

`.github/workflows/release.yml` is the authoritative package/release gate.

Required path:

1. pin the exact CI-proven source SHA and checkout that SHA;
2. Python / Node setup;
3. backend tests + strict eval;
4. version consistency;
5. license gate;
6. frontend typecheck/unit/build;
7. desktop unit tests;
8. build backend sidecar in clean venv;
9. packaged sidecar smoke;
10. build installer + portable;
11. capture packaged runtime UI evidence;
12. clean installer replay on a fresh Windows runner;
13. installed-layout smoke;
14. collect assets + SHA256;
15. create draft GitHub Release with the tag explicitly targeted at the same source SHA used for the binaries;
16. verify public tag SHA = binary source SHA, then download assets back from GitHub;
17. verify SHA256 on downloaded assets;
18. reinstall the downloaded installer;
19. rerun packaged smoke from downloaded/installed files;
20. re-check tag SHA = binary source SHA and publish the verified Release;
21. enrich and upload the post-publish verification JSON without changing the release itself.

A failing clean-install, download-back or source/tag provenance gate is a release failure. A failure **after** publication must be classified by step: do not automatically treat an already-published artifact as corrupt when the failed step only writes evidence metadata. The public tag, release channel, target SHA and downloadable assets must be independently re-verified before deciding whether to withdraw or republish.

### Conversation packaged UI evidence visibility

Conversation Beta captures from `frontend/scripts/capture-v20-conversation-packaged-evidence.mjs` use the built Windows backend sidecar and built `frontend-dist`. They are **packaged web-runtime screenshots**, not proof of native Electron window ergonomics or human visual acceptance.

Before every Home / Space / Prepare / Live / Sessions / History screenshot, the harness must assert that no `aria-modal` dialog or full-screen dimming backdrop obstructs the surface. If the Interview model drawer or any other blocking dialog appears, save a clearly marked `-BLOCKED.png` diagnostic and **fail** the evidence gate. A screenshot+SHA256 of an obscured page is not acceptable UI evidence.

The Conversation Beta local deterministic runtime must be accessible with no Interview model API key; Interview's first-run model-setup nudge cannot automatically hijack Conversation routes. The manifest explicitly records `surface_visibility = UNOBSTRUCTED_BY_MODAL` and `human_visual_acceptance = false`. Native Windows interactive visual acceptance remains a separate real-desktop evidence gate.


## NSIS hosted-runner reliability

Hosted Windows runners can occasionally fail before target files are written.

A bounded retry is allowed only when:

- every attempt uses a fresh target directory;
- exit codes are recorded;
- the gate still requires a real successful install;
- installed resources must exist;
- packaged smoke must then pass.

Retry must never become “ignore installer failure”.

## Version consistency

Before release, all version-bearing surfaces must agree. The version may be stable (`X.Y.Z`) or prerelease (`X.Y.Z-<label>`); release notes must use the exact same version string.



```text
frontend/package.json
frontend/package-lock.json
desktop/package.json
desktop/package-lock.json
backend/sidecar.py APP_VERSION
docs/RELEASE_NOTES_vX.Y.Z.md
```

Never hardcode the release checklist to an old version number.

## Exact source / tag provenance

The release must be reproducible from one immutable commit:

```text
main CI head SHA
==
Release checkout SHA
==
installer / portable source SHA
==
public tag SHA
```

For automated publishing, the `workflow_run.head_sha` that just passed main CI is passed to `release.yml` as `source_sha`. The Release workflow checks out that SHA, exports it as `CHENGZHU_RELEASE_SOURCE_SHA`, creates the tag using an explicit `--target`, and checks the tag again before download-back and before final publish.

Do not create a release tag from a moving `main` branch after a long package build. A release where the tag points to newer source than the binary build is not a valid reproducible release, even if both commits individually pass CI.

## Before merge

Required:

- PR CI green;
- PR Release preflight green;
- functional Playwright green;
- visual regression green;
- accessibility/e2e smoke green;
- strict Intelligence eval green;
- packaged smoke green;
- migration/integrity gates green;
- Reality Report reflects actual repository facts.

## After merge

Required:

- main CI green;
- auto-publisher uses the exact green main CI `head_sha`, not a later moving `main`;
- public tag resolves to the exact SHA used to build the release binaries;
- GitHub Release exists;
- expected assets exist;
- release download-back verification succeeds.

Only after this may a **stable-channel** version become Current Stable. A prerelease that passes the same gate becomes a verified public Beta, remains `prerelease=true`, and must not become GitHub Latest.

## Evidence boundary

Engineering/release evidence can support:

```text
ENGINEERING_COMPLETE
RELEASE_READY
PRODUCT_VALIDATION_INFRA_COMPLETE
```

It cannot by itself support:

```text
PMF_PROVEN
REAL_INTERVIEW_TRANSFER_PROVEN
REAL_USER_VALIDATION_COMPLETE
```

Real-user evidence remains separate.

## External items

Not required for unsigned Windows engineering release:

- code signing certificate;
- macOS signing / notarization;
- public Human Coach relay;
- paid-provider field matrix;
- native multi-monitor Overlay proof on an interactive desktop;
- real longitudinal participants;
- real multi-hour human sessions.

Unsigned Windows releases must state the SmartScreen limitation.


### Stable v2+ source provenance gate

Human Stable GO is necessary but not sufficient for publication.

For every unpublished Stable version with major >= 2, `release.yml` must verify twice:

```text
authorization candidate SHA
==
release source SHA
==
current main SHA
```

and the exact source SHA must have at least one successful **main push CI** run.

The first check runs before release packaging; the second runs immediately before the verified draft is published. If main advances during the Windows build/download-back window, the Stable publish fails closed and requires a new candidate/review cycle. Prereleases and legacy v1 Stable releases keep their existing paths.
