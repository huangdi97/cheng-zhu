# Chengzhu v1.2-R2 — UI Acceptance

Evidence: 24 screenshots from the **real packaged app** (`dist/desktop/win-unpacked/Chengzhu.exe`, final build) in `artifacts/release-evidence/v1.2-r2/`, with `manifest.json` noting how each view's data was produced. The app ran with an isolated `--user-data-dir`, a local fake OpenAI-compatible provider (no real key), and data seeded through the app's own HTTP API. It attached to its own sidecar on port 18081 because another server already held 18080 on this machine, which exercises the instance-nonce fix. Automated coverage: Playwright e2e (21 specs incl. axe on 6 screens) and vitest (386).

| # | Acceptance item (canonical §44) | Result | Evidence |
|---|---|---|---|
| 1 | Home has no duplicate navigation | PASS | `home.png`; nav = 首页/我的成竹/求职/演练/上场/复盘/设置 (e2e asserts no 准备/能力分析 tab) |
| 2 | Prepare not duplicated with Job Prep | PASS | Prepare lives in 求职 → 岗位目标 (`job-goal.png`); 演练 is the mock hub (`rehearse.png`) |
| 3 | Facts = source status, not "certified truth" | PASS | `facts.png`: 有直接证据 / 有支持材料 chips; no 验证/真相 wording |
| 4 | User Confirmed ≠ Direct Evidence | PASS | separate chips per fact (`facts.png`); filters for both axes |
| 5 | Session Claim correctable | PASS (e2e) | `r2-live-cue.spec`: warning with 这是口误 / 继续但不要扩展细节 / 稍后确认; Review 2.0 panel confirm/deny/slip/forget. Not in the runtime screenshots (needs live candidate speech) |
| 6 | Pack traceable | PASS | `prepare-pack-frozen.png` (rev + hash + counts), `preflight-pack-bar.png`, revisions API |
| 7 | Job does not drift | PASS | Live bar shows the frozen job; Job A/B contamination test |
| 8 | Cue before Deep | PASS | `live-fast-cue.png`; e2e + packaged smoke assert `guidance_fast` precedes the first `answer_chunk` |
| 9 | Overlay uses Fast Cue | PASS (code + unit) | `InterviewOverlay` Cue Mode renders `buildLiveGuidance(qa).cue` with [展开]; overlay window screenshot not captured (preheated hidden window) |
| 10 | Cue source visible | PASS | `live-boundary-cue.png`: 个人来源 badges (icon + text) |
| 11 | World knowledge not disguised as personal fact | PASS | Stream guard + L1 parser drop unsourced first-person; boundary answer in `live-boundary-cue.png` ("我没有直接做过 Redis Cluster…") |
| 12 | Risk visible | PASS | `live-boundary-cue.png`: ⚠ 没有来源支持，不要说成“我做过/我负责” |
| 13 | Share Privacy default OFF | PASS | `settings-share-privacy-off.png`; `settings-share-privacy-on.png` records main-process state after switching |
| 14 | Human Coach default practice only | PASS | settings + pack bar (人工协助：仅练习); API refuses live coach sessions (test) |
| 15 | Live AI_ALLOWED does not enable Human Coach | PASS | `human_coach_allowed` ignores AI policy (tests) |
| 16 | Review separates actual speech from AI | PASS (code + API test) | Review 2.0 "你实际说的" vs "AI Fast Cue"; runtime capture shows the review hub (`review.png`) without a recorded session |
| 17 | Colors AA | PASS | `statusContrast.test.ts` (all themes × 3 surfaces ≥ 4.5:1); axe: no critical/serious on 6 screens |
| 18 | Keyboard | PASS | e2e keyboard nav; review rows expose a real button |
| 19 | 390px | PASS | `mobile-390-home.png`; no horizontal overflow measured at 390 px |
| 20 | Light / Dark | PASS | light screens + `dark-facts.png`, `dark-home.png` |
| 21 | Empty / error | PASS | `error.png` (unreachable provider → user-facing error), onboarding explains failures; empty facts/story states in components |

## Found through runtime evidence and fixed before release

1. The packaged window attached to **another server** on port 18080 (a dev backend). Fixed: connect-based port check + per-launch instance nonce.
2. 冻结并用于本场 waited behind a 90 s strategy LLM call. Fixed: freeze first, strategy in background.
3. New resume facts showed 暂无证据 (provenance not set on insert after migration). Fixed.
4. Boundary cue listed unrelated personal items. Fixed.

## Known UX limitations

- Knowledge questions with no KB match get a direction line but no content bullets from L0 (L0 never invents knowledge). The L1 fast model is off by default (`fast_cue_model_index=-1`) and has no settings UI yet.
- Overlay screenshots and a recorded Review session were not captured from the runtime (need real audio / a recorded session).
