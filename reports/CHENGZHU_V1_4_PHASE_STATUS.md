# 成竹 Chengzhu — v1.4 Phase Status Report

Status recorded 2026-10-02 at branch `feat/chengzhu-v1.3-goal-centered-experience` HEAD `b98dbd8`.

> This is **not** the final v1.4 Reality Report. The gates it would summarise (v1.3 release,
> v1.4 release, download-back, clean-install) are not reached, so writing it in final form would
> mean either inventing CI/release evidence or filling it with open gates. This file records what
> is actually true today, with the evidence for each claim. Operational detail and exact next
> commands live in `reports/V1_3_V1_4_EXECUTION_CHECKPOINT.md`.

---

## Git

```text
main HEAD              a660f86 (unchanged this session)
branch HEAD            b98dbd8
worktree               clean
tags                   v1.2.0, v1.2.1, v1.2.2
releases               成竹 Chengzhu v1.2.2 (2026-09-30) — latest
PRs                    0 open
latest main CI         run 36727600400, success
branch CI              never run (branch never pushed)
```

## Test evidence

```text
backend  pytest -q        1063 passed        (baseline 994)
backend  ruff check .     clean
frontend npm test         405 passed / 55 files (baseline 390)
frontend tsc -b --noEmit  clean
frontend npm run build    ok
playwright (non-visual)   21 passed / 3 skipped / 6 failed  (baseline 3 passed / 20 failed)
desktop  node --test      29 passed          (baseline 23)
playwright (@visual)      not re-run; baseline 3 win32 snapshot diffs (CI gates on linux)
```

## Product capability status

| Capability | Status | Evidence |
|---|---|---|
| v1.2 Verified Core (Context Compiler, InterviewPack, Provenance, Truth, Session policy) | AUTHORITATIVE — **no regression** | 1063 backend tests green, including the existing intelligence/R2 suites |
| v1.2.2 → v1.3 → v1.4 migration compatibility | CI-PROVEN | `backend/tests/test_product_migration_compat.py` (3 tests): every row of every v1.2.2 table unchanged, pre-upgrade snapshot asserted, deletion = full rollback |
| Goal-centered IA (nav rail, 上场 as global action, object-centric routes, appMode adapter) | INTEGRATED | `frontend/e2e/critical-paths.spec.mjs` + `e2e/a11y.spec.mjs` assert the seven destinations, `aria-current="page"`, absence of 准备/复盘/上场 from the rail, and the legacy-mode landing route |
| Action Home / Goal Room / Person Workspace / Fact Inbox / Materials / Quick Notes / Command Palette / Practice 3.0 / Panel / Rubrics / Question Banks / Content+Delivery Coach / Pin / Nudge / Closing / Language layers / Preflight / Live Cockpit / Overlay layout / Reflection write-back / Settings 3.0 / History | INTEGRATED, backend CI-PROVEN | 66 tests in `backend/tests/test_product_*.py` cover the backend contract of each; frontend screens exist and render. **Not runtime-verified end-to-end yet** for Goal Room tabs, Panel practice, Preflight→Live→Pin→Reflection in one session, Overlay dock/interaction/size matrix, 390px, Light/Dark |
| Accessibility (keyboard, ARIA, contrast, reduced motion, 390px) | INTEGRATED, partially CI-PROVEN | a11y axe suite green in the last full non-visual run; two real defect classes found and fixed (missing heading landmark, Settings contrast). The suite is load-flaky, so it is not yet reliable evidence |
| v1.4 local ProductEvent analytics + six-question validation report | CI-PROVEN (backend) | `test_events_are_local_and_never_carry_free_text`, `test_validation_report_covers_the_six_questions_and_never_claims_pmf`, `test_seven_day_synthetic_continuity`, `test_thirty_session_synthetic_continuity`, `test_practice_transfer_is_labelled_mock_to_mock` |
| Future Profile boundary (Conversation\*, CounterpartyState, ExpressionIntent, GuidanceKind) | Canonical retained, **not productized** | `test_future_profile_is_retained_but_not_productized`, `test_shared_product_layer_does_not_hard_code_job`; no Meeting UI, no Meeting top-level nav |
| Windows installer / portable / release | **NOT REACHED** | no tag, no release; pipeline ready in `.github/workflows/release.yml` |
| download-back / clean-install replay | **NOT REACHED** | — |
| Runtime UI screenshots (32 states, Light/Dark, 390px) | **NOT REACHED** | `docs/screenshots/` still v1.2-era; harness exists in `frontend/scripts/capture-runtime-evidence.mjs` |
| Real-user product validation | `REAL_USER_EVIDENCE_PENDING` | no real participants; nothing here is evidence of product-market fit |

## Defects found and fixed (all in product code, none asserted away)

1. A partial API payload could blank the **entire** app: `HomePage`/`MePage` assumed complete
   payloads and, with no error boundary, React unmounted the root. Fixed by normalising payloads
   at the API boundary plus a page-level `PageErrorBoundary`.
2. The brand heading had been downgraded `<h1>` → `<span>`, removing the document's only heading landmark.
3. Active Settings group dimmed its English hint with `opacity-70` → WCAG AA contrast failure.
4. Ten product-layer handlers degraded silently (one bare `except: pass`), hiding real failures.

Recorded but **not** changed: `services/storage/product.py::insert` silently allows a NULL primary
key when no `id` is supplied (no production caller does this).

## Honest status words

```text
V1_3_PRODUCT_COMPLETE      NOT CLAIMED
V1_4_ENGINEERING_COMPLETE  NOT CLAIMED
PRODUCT_VALIDATION_INFRA_COMPLETE  backend instrumentation only; evidence reports not written
REAL_USER_EVIDENCE_PENDING         yes
PMF PROVEN                         never — no real participants
```

## Blockers

- **Engineering (in scope, not external):** 6 Playwright specs still drive the retired v1.2 module
  routes (`job-review-linkage` ×2, `job-workspace` ×2, `r2-live-cue` ×1, `resume-linkage` ×1); the
  a11y suite is load-flaky; screenshots, release and clean-install replay not started.
- **`BLOCKED_EXTERNAL` (cannot be resolved from this machine):** real-user recruitment, a truly
  clean Windows VM (a portable + isolated `--user-data-dir` replay is available instead), paid real
  provider key, code-signing certificate, macOS signing/notarization, public Coach relay, real
  long-duration human sessions.
