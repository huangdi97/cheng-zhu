# Development

## Layout

| Path | What |
|---|---|
| `backend/` | FastAPI + WebSocket backend, SQLite storage, intelligence core |
| `backend/services/intelligence/` | R2 semantics, InterviewPack, context compiler, fast cue, stream guard, session claims, latency clock |
| `backend/sidecar.py` | Packaged backend entry (PyInstaller) |
| `frontend/` | React + TypeScript + Vite + Zustand UI |
| `desktop/` | Electron main process, Share Privacy, backend launcher |
| `packaging/` | PyInstaller spec |
| `scripts/` | build, smoke, benchmark, soak, license tooling |
| `docs/canonical/Chengzhu_v1.2-R2_CANONICAL.md` | Product semantics source of truth |

## Run from source

Requires Python 3.11+ and Node 22.12+.

```bash
pip install -r backend/requirements.txt
cd frontend && npm ci && npm run build && cd ..
python start.py            # browser mode on http://localhost:18080
cd desktop && npm ci && npm start   # Electron, starts the backend itself
```

From source, data lives in `backend/data/` and config in `backend/config.json` (git-ignored; copied from `config.example.json` on first run). Set `CHENGZHU_HOME` to use a separate data root.

## Tests

```bash
cd backend && python -m ruff check . && python -m pytest -q
cd backend && python -m evals.r2_eval --check          # 20 mandatory cases + held-out gate
python scripts/generate_third_party_notices.py --check  # license gate
cd frontend && npx tsc -b --noEmit && npm test && npm run build
cd frontend && npx playwright test --config=playwright.config.mjs --grep-invert "@visual"
cd desktop && node --test *.test.js
```

Playwright runs against `vite preview` of `frontend/dist` — rebuild before e2e.

## Performance and soak

```bash
python scripts/bench_ttfug.py --repeats 3   # controlled TTFUG benchmark (Windows SAPI audio, local Whisper)
python scripts/soak_sim.py                  # simulated 2h/3h/5h sessions
```

## Build the Windows app

```bash
python scripts/build_sidecar.py --python <path-to-python3.11>   # clean venv + PyInstaller
python scripts/packaged_smoke.py --exe build/sidecar/chengzhu-backend/chengzhu-backend.exe --frontend-dist frontend/dist
cd desktop && npm run dist:win   # dist/desktop/Chengzhu-Setup-x64.exe + Chengzhu-Portable-x64.zip
```

If electron-builder fails with "cannot move the file to a different disk drive", set `ELECTRON_BUILDER_CACHE` and `TMP` to directories on the same drive.

## Rules that tests enforce

- The Live path never calls `latest_job_id()` / `active_candidate_id()`.
- `route_answer` is the only routing table.
- One logical context fragment appears at most once in a prompt.
- `guidance_fast` precedes the first `answer_chunk`.
- Share Privacy defaults to OFF; Human assistance defaults to practice-only.
- Status colors meet 4.5:1 on every theme surface.
