# Release

## Release truth

A successful local build is **not** a release.

A release is complete only when GitHub contains the published assets and the workflow has downloaded them back, verified them and replayed installation/smoke from the downloaded files.

## Windows artifacts

| File | Purpose |
|---|---|
| `Chengzhu-Setup-x64.exe` | per-user NSIS installer |
| `Chengzhu-Portable-x64.zip` | portable app |
| `SHA256SUMS.txt` | checksums |
| `LICENSE.txt` | root MIT license |
| `THIRD_PARTY_NOTICES.md` | third-party licensing |
| `RELEASE_NOTES_vX.Y.Z.md` | version-specific release notes |

Target machines do not require Python, Node, npm or pip.

## Release pipeline

`.github/workflows/release.yml` is the authoritative package/release gate.

Required path:

1. checkout;
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
15. create draft GitHub Release when publishing;
16. download assets back from GitHub;
17. verify SHA256 on downloaded assets;
18. reinstall the downloaded installer;
19. rerun packaged smoke from downloaded/installed files;
20. publish the verified Release.

A failing clean-install or download-back gate is a release failure.

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

Before release, all version-bearing surfaces must agree:

```text
frontend/package.json
frontend/package-lock.json
desktop/package.json
desktop/package-lock.json
backend/sidecar.py APP_VERSION
docs/RELEASE_NOTES_vX.Y.Z.md
```

Never hardcode the release checklist to an old version number.

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
- version-specific publish dispatcher / tag points at the intended main SHA;
- GitHub Release exists;
- expected assets exist;
- release download-back verification succeeds.

Only after this may the version become Current Stable.

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
