# Chengzhu v1.2-R2 — Packaging

## Artifacts (local build of the final commit)

| File | Size |
|---|---|
| `dist/desktop/Chengzhu-Setup-x64.exe` | ~214 MB (NSIS, per-user, unsigned) |
| `dist/desktop/Chengzhu-Portable-x64.zip` | ~283 MB |
| Sidecar `resources/backend/` (PyInstaller onedir) | ~315 MB unpacked |

Built with `scripts/build_sidecar.py` (clean Python 3.11 venv containing only `backend/requirements.txt` + PyInstaller) and electron-builder 25. The CI release workflow builds the same way on `windows-latest`.

## Runtime layout

| Location | Content |
|---|---|
| install dir `resources/backend/chengzhu-backend.exe` | backend sidecar (no system Python, no pip) |
| install dir `resources/frontend-dist/` | prebuilt UI (no npm) |
| install dir `resources/LICENSE`, `THIRD_PARTY_NOTICES.md` | MIT + third-party licenses |
| `%APPDATA%\Chengzhu\data` | SQLite DBs, KB, strategy trees |
| `%APPDATA%\Chengzhu\config\config.json` | settings (created from the bundled example on first run) |
| `%APPDATA%\Chengzhu\logs`, `cache`, `exports` | logs, model cache (Whisper downloads), exports |

The sidecar binds `127.0.0.1` on the first free port from 18080 (connect + bind check) and must echo a per-launch nonce before the window attaches.

## Packaged smoke (`scripts/packaged_smoke.py`, final build, installed layout)

| Check | Result |
|---|---|
| Cold start / restart | 2.6 s / 2.5 s |
| Starts with interpreter directories stripped from PATH | yes |
| `/api/options`, `/api/config`, version `1.2.0` | ok |
| Instance nonce echo | ok |
| Intelligence schema after first start | v3 |
| Prebuilt frontend served | yes |
| Fast Cue before first deep chunk (fake provider, real WS) | yes |
| InterviewPack persists across restart | yes |
| Install dir unchanged after running | yes |
| LICENSE (MIT) + THIRD_PARTY_NOTICES bundled | yes |

Report JSON: `reports/perf/installed-layout-smoke.json`.

## Real packaged app driven by Playwright

`frontend/scripts/capture-runtime-evidence.mjs` launched `Chengzhu.exe` with an isolated user-data dir: onboarding on a fresh config, seeded data, freezing, Live Fast Cue + deep answer, settings, error, dark, 390 px. See `CHENGZHU_V1_2_R2_UI_ACCEPTANCE.md`.

## Not done / external

- **Clean Windows VM install from the GitHub Release download**: pending the release (see final reality report).
- **Code signing**: no certificate → SmartScreen warning. BLOCKED-EXTERNAL.
- **macOS**: no build/notarization. BLOCKED-EXTERNAL.
- PyMuPDF is AGPL-3.0; the installer ships with a source pointer (THIRD_PARTY_NOTICES).
