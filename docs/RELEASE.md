# Release

## Artifacts

| File | What |
|---|---|
| `Chengzhu-Setup-x64.exe` | Per-user NSIS installer (choose directory; no admin needed) |
| `Chengzhu-Portable-x64.zip` | Unzip and run `Chengzhu.exe` |
| `SHA256SUMS.txt` | Checksums of both |
| `LICENSE.txt`, `THIRD_PARTY_NOTICES.md` | MIT + third-party licenses (no copyleft components; PDF rendering is pypdfium2, BSD-3/Apache-2.0) |

Neither artifact needs Python, Node, npm or pip on the target machine.

## Pipeline (`.github/workflows/release.yml`)

Triggered by a `v*` tag or manual dispatch (`publish=true` to create a Release):

1. backend lint + full tests, license gate
2. frontend type check, unit tests, build; desktop unit tests
3. backend sidecar in a clean venv (`scripts/build_sidecar.py`)
4. packaged smoke on the sidecar (fake provider, Fast Cue order, migrations, restart persistence, install dir untouched)
5. electron-builder → installer + portable
6. installed-layout smoke on `win-unpacked` (bundled LICENSE / notices)
7. SHA256SUMS, upload artifact, `gh release create`

## Checklist before tagging

- [ ] CI green on the PR, including `packaged-smoke`
- [ ] `python -m evals.r2_eval --check` passes
- [ ] `reports/CHENGZHU_V1_2_R2_FINAL_REALITY_REPORT.md` updated with real numbers
- [ ] Version `1.2.0` in `desktop/package.json`, `frontend/package.json`, `backend/sidecar.py`
- [ ] After publishing: download the installer from the Release page, verify SHA256, install on a clean Windows user profile, run first-run onboarding, restart, confirm data persists

## Not included (external)

- Code signing: installers are unsigned; Windows SmartScreen will warn until a certificate is available.
- macOS build / notarization: needs Apple hardware and a developer account.
