# Evidence MANIFEST — 2026-10-09 Chengzhu Full Local Simulation

SOURCE_SHA: `af709e5183ddd33071e27ee13680e93448f2e683`
REMOTE_MAIN_SHA: `383978fa480aac35d214dce3fa4e9fa5ebb17118`
BRANCH: `test/chengzhu-v2-local-full-simulation-2026-10-09`
DIRTY_BEFORE: TRUE（已记录 7 modified + 3 untracked，见 00-environment/git-status-initial.txt + initial-working-tree.diff）
DIRTY_AFTER: FALSE（v1.3 分支 stash 还原，status+diff 与初始逐字节一致）

## 测试项
| 项 | 值 |
| --- | --- |
| BACKEND_TESTS | PASS（1223 passed / 0 failed / 0 skipped） |
| FRONTEND_TESTS | PASS（428 passed / 59 files） |
| DESKTOP_TESTS | PASS（36 passed） |
| PLAYWRIGHT | PASS（55 passed / 1 flaky-retry-pass / 3 designed skips） |
| VISUAL | PASS（@visual 3/3 + 60 截图无遮挡） |
| INTERVIEW_REGRESSION | PASS |
| CONVERSATION_REGRESSION | PASS（119 conversation + 6 connector tests） |

## 六 Profile
| 项 | 值 |
| --- | --- |
| PROFILE_PROJECT_SYNC | PASS |
| PROFILE_DESIGN_REVIEW | PASS |
| PROFILE_PRESENTATION | PASS |
| PROFILE_1ON1 | PASS |
| PROFILE_CLIENT_CALL | PASS |
| PROFILE_NEGOTIATION | PASS |

## 能力项
| 项 | 值 |
| --- | --- |
| SESSION_PACK_IMMUTABILITY | PASS |
| TRUTH_PROVENANCE | PASS |
| OPEN_THREADS | PASS |
| CONVERSATION_STATE | PASS |
| MANUAL_ASK | PASS |
| AUTO_GUIDANCE | PASS |
| AUDIO_CAPTURE | PASS |
| PROCESSING_PRIVACY | PASS |
| SCREEN_CONTEXT | PASS |
| SHARE_PRIVACY | PASS |
| HUMAN_COACH | PASS |
| TRANSPARENCY | PASS |
| CONNECTOR_REGISTRY | PASS |
| DRAFT_ACTIONS | PASS |
| REMINDERS | PASS |
| EXPORT_DELETE_RETENTION | PASS |
| SEARCH | PASS |
| DIAGNOSTICS | PASS |
| RESTART_RECOVERY | PASS |
| WINDOWS_DESKTOP_RUNTIME | PASS |
| PACKAGED_CANDIDATE | PASS |
| CLEAN_REPLAY | PASS |
| SOAK | PASS |
| HUMAN_EVAL_TOOLING | PASS |
| STABLE_PROMOTION_GATE | PASS（最终状态符合契约） |

## 计数
- P0_COUNT = 0
- P1_COUNT = 1（已修复: BUG-01 packaged overlayLayout）
- P2_COUNT = 1（已修复: BUG-02 delivery cue frozen expression）
- P3_COUNT = 1（观察: BUG-04 E2E 时序 flake）
- BLOCKED_EXTERNAL = model_eval（无 CHENGZHU_EVAL_API_KEY）；real-user pilot / human audio；GitHub Releases API 资产核验（未认证，git tags 已核验）；soak audio-switching/sleep-wake/real-network-loss；human_visual_acceptance

## 最终状态
- LOCAL_FULL_SIMULATION = GO
- ENGINEERING_RUNTIME_CONFIDENCE = HIGH
- REAL_USER_EVIDENCE_PENDING = TRUE
- V2_STABLE_RELEASE = FALSE；PMF_PROVEN = FALSE；REAL_USER_VALIDATED = FALSE
- LOCAL_PACKAGED_CANDIDATE = READY_FOR_DOGFOOD
