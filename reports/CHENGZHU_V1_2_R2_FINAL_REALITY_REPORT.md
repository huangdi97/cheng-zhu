# Chengzhu v1.2-R2 — Final Reality Report

Date: 2026-09-30. Status vocabulary per canonical §8. Nothing below uses a bare "PASS" in place of these levels.

## Verdict

**NOT_READY → pending release steps.** The core local product is complete and verified on the packaged build, but the GitHub Release, download-back and clean-install verification have not happened yet (they need merge / tag / publish, which the maintainer confirms). One release SLO (TTFUG_user) is measured and **not met** on CPU-only STT.

Of the canonical NOT_READY conditions (§47), the following are now false: Live uses latest job · compiler not authoritative · Fast Cue waits for answer_done · TTFUG by first token · provenance posing as verification · session claims reinforcing unsourced facts · share privacy "undetectable" by default · no independent human policy · installer needs Python. Still open: *GitHub release downloaded and run* (not yet published) and *CI green* (see §Tests).

## Git

| Item | Value |
|---|---|
| Branch | `feat/chengzhu-v1-interview-intelligence` |
| Start HEAD | `4ebbe5f` (main `6dfa475`) |
| Current HEAD | `88a63ba` (+ this report commit) |
| PR | https://github.com/huangdi97/cheng-zhu/pull/1 (draft) |
| Tag / Release | not created |
| Worktree | clean after commit |

## License

| Item | Status |
|---|---|
| Root LICENSE = MIT, README/package metadata/NOTICE/About updated | AUTHORITATIVE, CI-PROVEN (license smoke + notices `--check`) |
| THIRD_PARTY_NOTICES generated from lockfiles/installed metadata; PyMuPDF AGPL-3.0 flagged with source pointer | IMPLEMENTED |
| LICENSE + notices bundled in the installer | verified in installed-layout smoke |
| Provenance note: NOTICE records a possible earlier `interview-assistant` origin; all commits are by huangdi97 | the maintainer should confirm no third-party-owned code remains |

## Product capabilities

| Capability | Level | Evidence |
|---|---|---|
| Candidate / resume rebuild, verdict carry-over | PRODUCT-COMPLETE | tests; runtime `facts.png` |
| Provenance (3 axes, assertion policy) | AUTHORITATIVE | semantics tests, migration v2 backfill test |
| Claims UI (事实与来源) | PRODUCT-COMPLETE | runtime screenshots |
| Story Builder / Voice prefs → pack → prompt | PRODUCT-COMPLETE | tests; runtime screenshots |
| Skill Cards (draft → user review → pack) | INTEGRATED | review toggle; pack only takes reviewed cards |
| Job Goal + Prepare + freeze | PRODUCT-COMPLETE | runtime `prepare-pack-frozen.png` |
| InterviewPack (immutable, revisions, no latest reads) | AUTHORITATIVE | Job A/B fixture through the real worker; restart persistence in packaged smoke |
| Context Compiler (only authority, dedupe) | AUTHORITATIVE | dedupe gate tests; soak shows no context growth |
| Question routing (single function) | AUTHORITATIVE | Eval 2.0: 20/20 mandatory; held-out v2 exact 0.833 (0.792 before a disclosed safety fix); v1 frozen 0.679 |
| Rehearse / Mock | INTEGRATED | existing gap-driven mock under 演练 |
| Preflight | INTEGRATED | pack bar + `/preflight`; formal-session gating is shown, not enforced as a hard block for practice |
| Fast Cue (L0) before Deep; early cue at question confirm | AUTHORITATIVE | e2e, packaged smoke, runtime screenshot |
| Fast Cue L1 (fast model) | IMPLEMENTED | off by default; no settings UI |
| Overlay Cue Mode | INTEGRATED | shared view model; not captured at runtime |
| Deep answer + Stream Truth Guard + post-audit | AUTHORITATIVE | tests; runtime boundary answer |
| Review 2.0 (trace, session-claim decisions) | INTEGRATED | API + component; no recorded session in runtime evidence |
| Controlled memory | AUTHORITATIVE (unchanged policy, now frozen into packs) | tests |
| Share Privacy (OFF default, per-session, tray indicator) | PRODUCT-COMPLETE | runtime on/off screenshots, desktop tests |
| Human Coach (practice-first, LAN helper, tokens) | PRODUCT-COMPLETE locally; public relay BLOCKED-EXTERNAL | coach tests, e2e |
| Onboarding + diagnostics | PRODUCT-COMPLETE | runtime `onboarding*.png`, e2e |
| Accessibility (AA colors, axe, keyboard) | CI-PROVEN locally | contrast test, axe e2e |

## Runtime

| Item | Status |
|---|---|
| Installer / portable build without system Python/Node | REAL-PROVEN on the build machine (sidecar starts with interpreter dirs stripped from PATH) |
| Data in `%APPDATA%\Chengzhu`, install dir untouched | verified by smoke |
| Restart persistence | verified by smoke |
| Clean Windows 11 VM install from the GitHub Release | **not done** (no release yet) |

## Metrics (controlled benchmark, CPU Whisper-base; `CHENGZHU_V1_2_R2_PERFORMANCE.md`)

| Metric | Baseline | R2 | SLO |
|---|---|---|---|
| QBD p50 / p95 | 5040 / 5660 ms | 3620 / 5680 ms | 500 / 900 ms — **not met** |
| TTFUG_user p50 / p95 | 6244 / 6863 ms | 3622 / 5682 ms | 1200 / 2000 ms — **not met** |
| TTFUG_internal (packaged, fake provider) | — | 156 ms | |
| TTFA / TTD (fake provider) | — | 531 / 672 ms | |
| Compiler | — | 2–3 ms | |
| L0 cue compute | — | 2–3 ms | |

Remaining gap: VAD 1.2 s + CPU batch STT ~1.6–2 s + confirm 0.45 s. Needs streaming ASR and adaptive VAD end-of-turn.

## Tests (real numbers, local, final code)

| Suite | Result |
|---|---|
| Backend pytest | 908 passed |
| Backend ruff | clean |
| Eval 2.0 `--check` | 20/20 mandatory, held-out v2 ≥ 0.75 gate |
| Frontend vitest | 386 passed (50 files) |
| Frontend tsc / build | clean |
| Playwright functional + a11y | 21 passed, 3 skipped (pre-existing live-backend specs) |
| Desktop node tests | 23 passed |
| Packaged smoke (installed layout) | all checks true |
| Simulated soak 2h / 3h / 5h | pass |
| GitHub CI on `88a63ba` | see PR checks (first run on `313f442`: backend 2 failures → fixed; visual baselines regenerated) |

## External / not done

- Code signing certificate (SmartScreen warning) — BLOCKED-EXTERNAL
- macOS build + notarization — BLOCKED-EXTERNAL
- Real-provider model eval (no key used) — BLOCKED-EXTERNAL
- Public coach relay — BLOCKED-EXTERNAL (`COACH_PUBLIC_BASE_URL` adapter only)
- Real multi-hour sessions with real audio / people — BLOCKED-EXTERNAL
- Merge, tag `v1.2.0`, GitHub Release, download-back, clean install — **pending maintainer confirmation**
