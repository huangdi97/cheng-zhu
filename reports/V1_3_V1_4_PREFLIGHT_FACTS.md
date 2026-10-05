# v1.3 → v1.4 Preflight Facts (recorded before any v1.3 change)

Recorded 2026-10-01 at the start of the v1.3/v1.4 run, on a clean `main`.

## Git / release / CI

| Item | Value |
|---|---|
| Repo | huangdi97/cheng-zhu |
| main HEAD | a660f86255babc07b9749749ca5178be433bd601 |
| Tags | v1.2.0, v1.2.1, v1.2.2 |
| Latest release | 成竹 Chengzhu v1.2.2 (Latest, 2026-09-30) |
| Latest main CI | run 36727600400, success |
| Last release-verify run | 36716495128, failure (workflow_dispatch, pre-existing; tracked in the v1.2-R2 closure checkpoint) |
| Open PRs | 0 |
| Worktree | clean |
| New branch | feat/chengzhu-v1.3-goal-centered-experience (from main a660f86) |

## Package versions

| Package | Version |
|---|---|
| frontend `cheng-zhu-frontend` | 1.2.2 |
| desktop `cheng-zhu-desktop` | 1.2.2 |

## Data

| Store | File | Schema |
|---|---|---|
| Intelligence core | `data/intelligence.db` | `PRAGMA user_version` = 3 (`schema_migrations`: v1 core, v2 provenance axes + InterviewPack + session claims, v3 turn trace) |
| Prep spaces (current "Job Goal") | `data/prep.db` | `prep_spaces`, `prep_skill_cards` (unversioned `CREATE IF NOT EXISTS`) |
| Applications / offers | `data/job_tracker.db` | `applications`, `offers` |
| Review | `data/review.db` | `review_sessions`, `review_turns`, `review_profile_snapshots` |
| Knowledge / question records | `data/knowledge.db` | `question_records` |
| KB | `data/kb.sqlite` | `kb_doc`, `kb_chunk`, `kb_attachment` |
| Resume history | `data/resume_history.db` | `resume_entries` |

A Goal is not a first-class object yet: it is spread across a `prep_spaces` row (int id),
an intelligence `job_profile` (text id) and a job-tracker `applications` row (int id), with no
link between them. Practice sessions are in-memory until finished and land in `review_sessions`
with `source='practice'`.

## Current IA (frontend `appMode` in `uiPrefsStore`)

Top level: 首页 `home` / 我的成竹 `resume-opt` / 求职 `job-tracker` (岗位目标 = PrepSpace, 投递看板 = JobTracker) /
演练 `prep` (RehearseHub → PracticePanel) / 上场 `assist` / 复盘 `review` (场次复盘 + 能力分析) / 设置 (drawer).
No URL router; the mode is persisted in localStorage.

- Home (`HomeScreen.tsx`): module tiles + system status (model / KB docs / resume / CPU) in the main area.
- Practice: question pool from the prep space + recent weak points + gap focus; follow-ups come from the
  previous turn's analysis. No persona / round / demeanor / difficulty / question banks / panel.
- Overlay: `InterviewOverlay.tsx` (791 lines), Electron overlay window with content protection.
- Onboarding: `OnboardingWizard.tsx`; no guided first practice.
- Settings: drawer with tabs (Models, Speech, Preferences, ...), no search, no Goal/Session override layer.

Backend: 149 route handlers across 15 routers.

## Baseline tests

| Suite | Result | Classification |
|---|---|---|
| Backend `pytest -q` | 994 passed | — |
| Backend `ruff check .` | clean | — |
| Frontend `vitest run` | 51 files, 390 passed, 1 failed | `SoundTest > starts real preflight…` fails only under full-suite load and passes 6/6 alone twice: **pre-existing timing flake** |
| Frontend `tsc -b --noEmit` | clean | — |
| Frontend `vite build` | ok | — |
| Frontend `playwright test` | 23 passed, 3 skipped, 3 failed | the 3 failures are `@visual` win32 snapshots (assist / knowledge / resume); CI gates on the linux baselines: **platform** |
| Desktop `node --test` | 23 passed | — |

## Inputs

- The v1.3-R2 Canonical document named in the Goal (`成竹 Chengzhu v1.3-R2 Goal-centered Interview Operating
  System …`) was **not present** next to the Goal file. `docs/canonical/Chengzhu_v1.3-R2_CANONICAL.md` is
  therefore assembled from the v1.3→v1.4 Goal document (2026-10-01), which carries the full v1.3/v1.3.x/v1.4
  product design, plus the v1.2-R2 Canonical as the frozen core. Replace it with the original if it is supplied.
