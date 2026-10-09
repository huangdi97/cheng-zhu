# Static Gates (reproducing .github/workflows/ci.yml on origin/main 383978fa)

Ran on: 2026-10-09 17:23:07 +08:00 | source SHA: 06877537ea6c3317a6cf403ee34dc8a1c03412cc

| Gate | Command | Exit | Elapsed | Result |
| --- | --- | --- | --- | --- |
| C1 ruff | `ruff check .` (backend) | 0 | 1s | PASS — "All checks passed!" |
| C2 py_compile | `python -m py_compile main.py api/assist/pipeline.py api/common/router.py` | 0 | <1s | PASS |
| C3 npm ci | `npm ci` (frontend) | 0 | 79s | PASS (lock-based install) |
| C4 tsc | `npx tsc -b --noEmit` | 0 | 68s | PASS |
| C5 npm test | `npm test` | 0 | 106s | PASS — 59 files / 428 tests |
| C6 build | `npm run build` | 0 | 74s | PASS — "built in 35.49s" |
| C7 desktop ci | `npm ci --ignore-scripts` (desktop) | 0 | 24s | PASS |
| C8 desktop tests | `node --test *.test.js` | 0 | 1s | PASS — 35 tests / 0 fail |
| C9 release version | `python scripts/check_release_version.py` | 0 | <5s | PASS — {"ok":true,"version":"2.0.0-beta.2","release_channel":"PRERELEASE"} |
| C10 license | `python scripts/generate_third_party_notices.py --check` | 0 | <5s | PASS |

Notes:
- All gates pass on the actual `origin/main` checkout (branch test/chengzhu-v2-local-full-simulation-2026-10-09 @ 383978fa).
- C9 confirms version consistency across frontend/desktop/locks/sidecar = 2.0.0-beta.2 (PRERELEASE channel).
- Raw full outputs are visible in the session command log; exit codes above are exact.
