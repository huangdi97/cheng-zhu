# v1.2-R2 Preflight Facts (recorded before any R2 change)

Recorded 2026-09-30 at the start of the R2 run.

## Git

| Item | Value |
|---|---|
| Repo | huangdi97/cheng-zhu |
| Branch | feat/chengzhu-v1-interview-intelligence |
| HEAD | 4ebbe5f4d3308b91a57620bb712062639646b1c0 |
| origin/main | 6dfa47520246a35350cfb5090a5abbc22a84739d |
| Ahead / behind main | 21 / 0 |
| Worktree | clean |
| Tags / Releases | none |
| Open PR | none known locally (GitHub MCP not authorized; `gh` used for push/PR later) |

## Code facts

| Item | Value |
|---|---|
| License | CC BY-NC 4.0 (root `LICENSE`, README badge) |
| `api/assist/pipeline.py` | 2415 lines |
| `api/assist/answer_worker.py` | 1812 lines |
| Intelligence modules | 21 files in `services/intelligence/` |
| Intelligence schema | v1 (`intelligence.db`, `PRAGMA user_version`) |
| Frontend nav | 首页 / 我的成竹 / 岗位 / 演练 / 上场 / 复盘 / 能力分析 |
| Package versions | frontend 1.0.0, desktop 1.0.0 |
| Desktop packaging | none; Electron spawns system `python start.py --mode network` (binds 0.0.0.0) |
| User data location | `backend/data/`, `backend/config.json`, `log/` (inside the repo) |
| Content protection | forced ON for main window + overlay; main window hidden from the Windows taskbar |

## Known R1 gaps confirmed in code

- `answer_worker` read `intel_storage.latest_job_id()` on the Live path.
- Context Compiler output was added on top of the legacy prompt; resume / KB / memo / JD were still injected by `build_system_prompt`; the compact state appeared twice.
- TTFUG telemetry recorded the first model token.
- `realtime_bridge._session_id_of` read `session.id` (the attribute is `session_id`), so every session collapsed to `default`.
- `GuidanceFirstScreen` received `qa.guidance` but parsed it as the whole `answer_done` message, so it never rendered.
- `ConfigUpdate` did not accept `ai_policy_mode`.
- Eval route matching accepted alias leniency (`OPEN_DESIGN` passed as `SYSTEM_DESIGN`).

## Baseline tests

| Suite | Result |
|---|---|
| Backend `pytest -q` | 818 passed, 4 skipped |
| Backend `ruff check .` | clean |
| Frontend `tsc -b --noEmit` | clean |
| Frontend `vitest` | 49 files, 352 tests passed |
| Frontend `vite build` | ok |
| Desktop `node --test` | 13 passed |
| Latest full CI (per repo docs) | run 36575912875, success, on 8db2912 |
