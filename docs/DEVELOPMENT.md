# Development

## Source of truth

Use these in order:

1. runtime / repository / CI facts;
2. `docs/canonical/Chengzhu_v1.3-R2_CANONICAL.md` — current product Canonical;
3. `docs/canonical/Chengzhu_v1.4-R1_VALIDATION_HARDENING.md` — current validation/hardening addendum;
4. `docs/canonical/Chengzhu_v1.2-R2_CANONICAL.md` — frozen Verified Core.

Do not rebuild the product from v1.0 / old Stage docs.

## Layout

| Path | What |
|---|---|
| `backend/` | FastAPI + WebSocket backend, SQLite storage, product + intelligence services |
| `backend/services/intelligence/` | frozen InterviewPack, Context Compiler, routing, truth, fast cue, stream guard |
| `backend/services/product/` | Goal, Next Focus, materials, practice, reflection, validation, future-profile contracts |
| `backend/sidecar.py` | packaged backend entry |
| `frontend/` | React + TypeScript + Vite + Zustand Goal-centered UI |
| `frontend/src/components/os/` | Action Home, Goal Room, Practice, Library, History, Settings, Reflection |
| `frontend/src/components/live/` | Live Cockpit / companions |
| `desktop/` | Electron main process, Overlay / Share Privacy, backend launcher |
| `packaging/` | PyInstaller spec |
| `scripts/` | build, smoke, benchmark, soak, release/validation tooling |

## Product architecture rule

Current top-level IA:

```text
首页
求职目标
我的成竹
练习
资料库
历史
设置

                         [上场]
```

Do not add a top-level page for an internal subsystem.

The product loop is:

```text
Goal → Next Focus → Prepare → Practice → Preflight → Live → Reflection → Next Focus
```

Verified Core must remain independent from the Studio UI.

## Run from source

Requires Python 3.11+ and Node 22.12+.

```bash
pip install -r backend/requirements.txt
cd frontend && npm ci && npm run build && cd ..
python start.py
```

Electron development:

```bash
cd desktop
npm ci
npm start
```

Use `CHENGZHU_HOME` to isolate development data.

## Tests

Backend:

```bash
cd backend
python -m ruff check .
python -m pytest -q
python -m evals.r2_eval --check
```

Frontend:

```bash
cd frontend
npx tsc -b --noEmit
npm test
npm run build
npx playwright test --config=playwright.config.mjs --grep-invert "@visual"
npx playwright test --config=playwright.config.mjs --grep "@visual"
```

Desktop:

```bash
cd desktop
node --test *.test.js
```

License:

```bash
python scripts/generate_third_party_notices.py --check
```

## Product-loop validation

v1.4 local-first engineering validation includes:

```text
A Goal reuse
B Reflection → Next Focus
C Fast Cue usefulness signals
D Practice transfer
E Fact Inbox burden
F Quick Notes / Pin value
```

Deterministic engineering evidence:

```bash
python scripts/v14_validation_evidence.py
```

Do not describe synthetic output as real-user evidence.

## Performance / reliability

Realtime regressions must preserve:

```text
Fast Cue before Deep
InterviewPack frozen
Context Compiler authoritative
Truth Boundary
Session Claim boundary
```

Representative tools:

```bash
python scripts/bench_ttfug.py --repeats 3
python scripts/soak_sim.py
```

v1.4 additionally requires 7-day / 30-session / 100-session synthetic continuity and 3-hour-equivalent soak evidence.

## Windows package

```bash
python scripts/build_sidecar.py --python <path-to-python3.11>
python scripts/packaged_smoke.py \
  --exe build/sidecar/chengzhu-backend/chengzhu-backend.exe \
  --frontend-dist frontend/dist

cd desktop
npm run dist:win
```

Expected:

```text
dist/desktop/Chengzhu-Setup-x64.exe
dist/desktop/Chengzhu-Portable-x64.zip
```

The public release is not proven by local build output. See `docs/RELEASE.md`.

## Engineering rules

Tests enforce, among other things:

- Live does not use latest-job / active-candidate drift;
- `route_answer` remains authoritative;
- one logical context fragment appears at most once;
- `guidance_fast` precedes Deep;
- Share Privacy defaults OFF;
- Human assistance defaults practice-only;
- Quick Notes never become Evidence automatically;
- KB reference never becomes personal evidence;
- Goal/session linkage survives restart;
- Reflection actions write through the real product loop;
- synthetic evidence never becomes a PMF claim.

## Future Conversation Profile

Meeting / Presentation / 1:1 are not current top-level products.

v1.x should retain future-compatible contracts without building a parallel Meeting app.

See the Personal Conversation Intelligence sections in v1.3-R2 Canonical.
