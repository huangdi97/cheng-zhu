# Chengzhu v1.3 → v1.4 Execution Checkpoint

Recorded 2026-10-02. This file exists so the next agent does **not** re-investigate; every
number below was produced by a command run in this session and can be re-run verbatim.

---

## 1. Git

| Item | Value |
|---|---|
| Worktree | `E:\AI\面试助手` (repo `huangdi97/cheng-zhu`) |
| Working branch | `feat/chengzhu-v1.3-goal-centered-experience` |
| Branch HEAD | `b98dbd8` |
| Working tree | **clean** (nothing uncommitted, nothing stashed) |
| `origin/main` | `a660f86` — **unchanged**, nothing has been pushed this session |
| Local commits added this session | `90c3d13`, `52c5023`, `b98dbd8` (on top of `ae6de0b`) |
| Open PRs | 0 |
| Tags | v1.2.0, v1.2.1, v1.2.2 (no new tag) |
| Latest release | 成竹 Chengzhu v1.2.2 (2026-09-30) — **no v1.3/v1.4 release exists** |
| Latest `main` CI | run 36727600400, success (pre-dates this session) |
| CI for the new branch | **not yet run** — the branch has never been pushed |

Commit chain on the branch:

```text
b98dbd8  test(e2e): migrate the Playwright suite to the v1.3 Goal-centered IA
52c5023  feat(os): v1.3 Goal-centered shell, OS pages, live cockpit and overlay layout
90c3d13  fix(product): surface degraded paths and prove v1.2.2 -> v1.3 migration safety
ae6de0b  feat(product): v1.3 Goal-centered product layer (backend)
98b3b3e  docs(canonical): v1.3-R2 Goal-centered Interview OS canonical; v1.2-R2 frozen verified core
b57bae6  docs(v1.3): preflight facts baseline
```

`gh` is authenticated as `huangdi97` with `repo` + `workflow` scopes (verified this session).

---

## 2. Test counts (all run in this session, on `b98dbd8` + clean tree)

| Suite | Command | Result | Baseline before this session |
|---|---|---|---|
| Backend | `cd backend; python -m pytest -q` | **1063 passed** | 994 passed |
| Backend lint | `cd backend; ruff check .` | **clean** | clean |
| Frontend unit | `cd frontend; npm test` | **405 passed / 55 files** | 390 passed |
| Frontend types | `cd frontend; npx tsc -b --noEmit` | **clean** | clean |
| Frontend build | `cd frontend; npm run build` | **ok** | ok |
| Playwright (functional) | `cd frontend; $env:CI="true"; npx playwright test --config=playwright.config.mjs --grep-invert "@visual" --reporter=line` | **21 passed / 3 skipped / 6 failed** | 3 passed / 3 skipped / **20 failed** |
| Playwright (visual `@visual`) | not re-run this session | unknown | 3 failed — win32 snapshot diffs, CI gates on linux baselines |
| Desktop | `cd desktop; node --test *.test.js` | **29 passed** | 23 passed |

Deltas are real test additions, not re-counted skips: +69 backend (66 product + 3 migration),
+15 frontend unit, +6 desktop, +18 passing Playwright.

---

## 3. Data / migration

| Store | State |
|---|---|
| `product.db` | **new file**, `PRAGMA user_version = 1`, 19 tables, tracked by `schema_migrations` |
| v1.2 stores (`prep` / `review` / `job_tracker` / `intelligence` / `knowledge` / `resume_history`) | never altered by the product layer; only referenced by id |
| `backend/pyproject.toml` | exists (ruff config). There is **no** pytest config anywhere — backend tests must be run from `backend/`. Running `pytest` from the repo root fails collection because root `test_review_api.py` collides with `backend/tests/test_review_api.py`. This is pre-existing. |

Migration safety is proven by `backend/tests/test_product_migration_compat.py` (3 tests,
all passing): a genuine v1.2.2 store set built through the v1.2.2 modules, every row of every
table asserted unchanged after the upgrade and after a re-run of the backfill, a pre-upgrade
snapshot asserted when an existing `product.db` is one version behind, and a full rollback
proven by deleting `product.db` and rebuilding the Goal view from v1.2 data.

---

## 4. Product surface — what is present and where

Backend (`backend/services/product/`, 24 modules; `backend/api/product/`, 4 routers) implements
Goal, Next Focus, Reflection write-back, Fact Inbox with burden metrics, material taxonomy +
lifecycle, Quick Notes with a non-evidence truth boundary, Question Banks (+5 origins),
per-role rubrics, Panel turn-taking, Content/Delivery coach split, Pin, Nudge + suppression,
Closing, five-layer language settings, Preflight, materials/export/delete integrity,
local `ProductEvent` analytics, six-question validation report, and synthetic 7-day /
30-session dogfood. Covered by 66 tests in `backend/tests/test_product_*.py`.

Frontend: `src/components/os/*` (29 files), `src/components/live/*`, `src/components/app/PageErrorBoundary.tsx`,
`src/lib/router.ts` (hash router + legacy `appMode` adapter), `src/lib/productApi.ts` (typed
client + payload normalisers), `src/lib/i18n.ts`, `src/stores/osStore.ts`, `src/stores/overlayLayoutStore.ts`,
plus `desktop/overlayLayout.js` for the Electron side.

---

## 5. Defects found and fixed this session

All four were found by making the suites prove behaviour, and all four were fixed in product
code rather than asserted away.

1. **The whole app shell could be blanked by one bad payload.** `HomePage` read
   `needs_attention.length` and `MePage` read `cards.filter` on payloads that a partial or
   unexpected response left undefined. An uncaught render error makes React unmount the root,
   so the window lost its nav rail, its session and every route. Fixed by normalising
   list-shaped payloads at the API boundary (`requestArray` in `src/lib/api.ts`, `itemsList`
   plus per-endpoint defaults in `src/lib/productApi.ts`, `withPracticeDefaults`) and by adding
   `PageErrorBoundary` so a screen failure keeps the shell and offers a retry.
2. **The document had no heading landmark.** `App.tsx` had downgraded the brand from
   `<h1>成竹</h1>` to `<span>`. Restored as `<h1>`.
3. **WCAG AA contrast failure in Settings.** The active group row dimmed its English hint with
   `opacity-70` on the primary-container background. Replaced with weight-only differentiation.
4. **Silent degraded paths in the product layer.** Ten handlers returned a neutral value with no
   log, including one bare `except: pass` that could leave a Goal interview marked `UPCOMING`
   after a live session. Now logged; return values unchanged.

Open observation, deliberately **not** changed: `services/storage/product.py::insert` returns the
caller's dict and `_encode` drops the `id`, so `store.insert("goal", {...})` without an id
silently creates a row with a NULL primary key (SQLite allows it for `TEXT PRIMARY KEY`). Every
domain service supplies an id, so nothing in production hits it. A guard would need a caller
audit.

---

## 6. Open gates

### G0 Baseline — DONE
Full baseline re-established and recorded in `reports/V1_3_V1_4_PREFLIGHT_FACTS.md` plus section 2 above.

### G1 Canonical — DONE
`docs/canonical/Chengzhu_v1.3-R2_CANONICAL.md` is in the repo; `Chengzhu_v1.2-R2_CANONICAL.md`
carries `Status: **FROZEN VERIFIED CORE**`; README states `Current Canonical = v1.3-R2`,
`Frozen Verified Core = v1.2-R2` and `Current Stable Release = v1.2.2`; the GitHub repo
description already reads 成竹 Chengzhu.

### G2 Migration — DONE (see section 3)

### G3–G21 v1.3 product surface — IMPLEMENTED / INTEGRATED, mostly CI-PROVEN
Backend behaviour for the whole surface has passing tests. Frontend screens exist and are
exercised by the rewritten a11y and critical-path specs. Not yet PRODUCT-COMPLETE because:

- **6 Playwright specs still drive the retired v1.2 module routes and fail:**
  `job-review-linkage.spec.mjs` (2), `job-workspace.spec.mjs` (2), `r2-live-cue.spec.mjs` (1,
  the rehearse-hub/coach test), `resume-linkage.spec.mjs` (1). They need the same treatment the
  a11y and critical-path specs got: re-point the locators at `/goals`, `/practice`, `/me`,
  `/history` and assert the v1.3 contract at equal strength.
- **The a11y spec is load-flaky.** Individual screens pass in isolation and the whole spec
  passed in the last full non-visual run, but under parallel load runner a screen can fail on a
  transient state. The violation text has not been captured yet because it does not reproduce in
  isolation — that is the next thing to nail down (see section 8).
- Not yet verified end-to-end at runtime: Goal Room tabs, Panel practice, Preflight → Live →
  Pin → Reflection across a real session, Overlay dock/interaction/size matrix, 390px, Light/Dark.

### G-UI Screenshots — NOT STARTED
`docs/screenshots/` still holds only v1.2-era images (`assist-mode.png`, `knowledge-map.png`,
`resume-optimizer.png`, the demo gif/webm). No `docs/screenshots/v1.3/` or `v1.4/`, no manifest.
The reusable capture harness is `frontend/scripts/capture-runtime-evidence.mjs` — it launches the
**built packaged app** (`dist/desktop/win-unpacked/Chengzhu.exe`) with an isolated
`--user-data-dir` and a local fake OpenAI-compatible provider, seeds data over the app's own HTTP
API, and writes a manifest. It currently targets `artifacts/release-evidence/v1.2-r2` and the v1.2
screen set, so it needs a v1.3 route/state list and a v1.3 output directory.

### G22–G24 v1.3 CI + package + release — NOT STARTED
Nothing pushed; no PR; no CI run for this branch; no tag; no release; no download-back; no
clean-install replay. The release pipeline itself is ready and unchanged:
`.github/workflows/release.yml` builds the sidecar in a clean venv, packages the installer and
portable zip, runs an installed-layout smoke, collects
`Chengzhu-Setup-x64.exe` / `Chengzhu-Portable-x64.zip` / `SHA256SUMS.txt` and publishes.

### G25–G34 v1.4 validation + hardening — BACKEND DONE, EVIDENCE REPORTS NOT WRITTEN
The instrumented surface is complete and tested: `ProductEvent` store (local-only, 25+ events,
privacy guard test asserts no free text), six-question validation report, Goal-reuse metrics,
Reflection→Prepare write-back proof, cue-usefulness proxy signals + post-session feedback,
practice→session transfer linkage (labelled `MOCK_TO_MOCK`), Fact Inbox burden metrics + hardening
rule, Quick Notes / Pin value metrics, friction audit data, 7-day and 30-session synthetic
dogfood, export/delete integrity. What is missing is the **written evidence** in `reports/`
(friction-audit numbers, dogfood run output, performance deltas, soak output) and the
`Real Interview transfer` distinction, which stays `BLOCKED_EXTERNAL`.

### G35–G36 v1.4 CI + release — NOT STARTED

### G-H Final reality report — NOT YET WARRANTED
`reports/CHENGZHU_V1_4_FINAL_REALITY_REPORT.md` has not been written, because the gates it is
supposed to summarise are not reached. Writing it now would mean either inventing CI/release
evidence or filling it with open gates. Do it after G22–G24 and G35–G36.

---

## 7. Status word

The only honest status right now is:

```text
V1_3_PRODUCT_COMPLETE      - NOT CLAIMED
V1_4_ENGINEERING_COMPLETE  - NOT CLAIMED
REAL_USER_VALIDATION_PENDING / REAL_USER_EVIDENCE_PENDING - still pending, as expected
PMF PROVEN                 - must never be written without real participants
```

---

## 8. Exact next steps

### Step 1 — finish the E2E migration (unblocks G22)

```powershell
cd E:\AI\面试助手\frontend
npm run build
$env:CI="true"; npx playwright test --config=playwright.config.mjs e2e/job-review-linkage.spec.mjs --reporter=line
```

`e2e/job-review-linkage.spec.mjs` and `e2e/job-workspace.spec.mjs` drive 求职 → `/goals` and the
Goal Room; `e2e/r2-live-cue.spec.mjs:148` (`rehearse hub offers a practice coach panel`) drives 演练
→ `/practice`; `e2e/resume-linkage.spec.mjs` drives 我的成竹 → `/me`. Re-point them the way
`e2e/a11y.spec.mjs` and `e2e/critical-paths.spec.mjs` were re-pointed: `getByRole('navigation', { name: '主导航' })`
plus `aria-current="page"` for navigation, hash routes for direct entry, and keep every assertion
at least as strong as the one it replaces.

### Step 2 — nail down the a11y load flake

Run the a11y spec with `--workers=1` and then with the default worker count, saving full output,
and diff the axe violation summaries. Prime suspect: a small-text contrast failure in the shared
loading/empty states (`components/os/ui.tsx` — `Loading` uses `text-xs text-text-muted`, so *every*
screen fails while loading and only some runs catch it). If that is the cause it is a real WCAG AA
defect and belongs in product code, not in a longer timeout.

### Step 3 — runtime screenshots (G-UI)

Extend `frontend/scripts/capture-runtime-evidence.mjs` with a v1.3 state list (the 32 screens in
canonical §82) and an output directory of `docs/screenshots/v1.3/`, then run it against a fresh
`npm run build` + packaged app. It already has the fake provider and isolated user-data support.

### Step 4 — v1.3 release (G22–G24)

```powershell
cd E:\AI\面试助手
git push -u origin feat/chengzhu-v1.3-goal-centered-experience
gh pr create --base main --title "成竹 Chengzhu v1.3 Goal-centered Experience" --body-file <notes>
gh run list --branch feat/chengzhu-v1.3-goal-centered-experience
```

Wait for CI green, then merge, tag the single 1.3 release, let `release.yml` publish, download the
assets back and verify SHA256, then replay the clean-install flow from the downloaded portable zip
with an isolated `--user-data-dir` (record the true clean-VM case as `BLOCKED_EXTERNAL`).

### Step 5 — v1.4 branch, evidence reports, release, final reality report

Per the goal document stages 43–66: write the six product-loop evidence reports into `reports/`,
record the friction audit and dogfood output, re-run performance/latency/soak, then
`feat/chengzhu-v1.4-validation-hardening`, CI, release, download-back, clean-install and finally
`reports/CHENGZHU_V1_4_FINAL_REALITY_REPORT.md`.

---

## 9. Files a successor should read first

```text
reports/V1_3_V1_4_PREFLIGHT_FACTS.md          baseline + starting reality
reports/V1_3_V1_4_EXECUTION_CHECKPOINT.md     this file
docs/canonical/Chengzhu_v1.3-R2_CANONICAL.md  current canonical (v1.3-R2)
docs/canonical/Chengzhu_v1.2-R2_CANONICAL.md  frozen verified core (must not regress)
frontend/src/App.tsx                          shell: header, nav rail, route switch, error boundary
frontend/src/lib/router.ts                    hash router + legacy appMode adapter
frontend/src/lib/productApi.ts                typed client + payload normalisers
frontend/e2e/a11y.spec.mjs                    the re-pointing pattern to copy
backend/tests/test_product_migration_compat.py migration safety proof
```
