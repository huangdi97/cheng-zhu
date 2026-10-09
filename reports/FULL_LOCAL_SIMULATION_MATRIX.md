# FULL LOCAL SIMULATION MATRIX

取值仅允许: PASS / FAIL / BLOCKED_EXTERNAL / NOT_APPLICABLE

| 项 | 结果 | 证据 |
| --- | --- | --- |
| SOURCE_SHA | PASS | af709e5183ddd33071e27ee13680e93448f2e683 |
| REMOTE_MAIN_SHA | PASS | 383978fa480aac35d214dce3fa4e9fa5ebb17118 |
| BRANCH | PASS | test/chengzhu-v2-local-full-simulation-2026-10-09 |
| DIRTY_BEFORE | PASS | 已记录（7 modified + 3 untracked）→ stash 保护 |
| DIRTY_AFTER | PASS | stash 还原后与初始逐字节一致（见 Git 章节） |
| BACKEND_TESTS | PASS | 1223 passed / 0 failed（full-pytest-final.log） |
| FRONTEND_TESTS | PASS | 428 passed / 59 files |
| DESKTOP_TESTS | PASS | 36 passed |
| PLAYWRIGHT | PASS | 55 passed / 1 flaky-retry-pass / 3 designed skips |
| VISUAL | PASS | @visual 3/3 + 60 张自定义截图全无遮挡 |
| INTERVIEW_REGRESSION | PASS | backend 全量 + Interview E2E 全绿 |
| CONVERSATION_REGRESSION | PASS | 119 conversation + 6 connector tests（-vv 记录） |
| PROFILE_PROJECT_SYNC | PASS | 3 场 continuity + Scenario A 全绿 |
| PROFILE_DESIGN_REVIEW | PASS | 3 场 + supersession + Scenario B 全绿 |
| PROFILE_PRESENTATION | PASS | 2 场 + lane 隔离（TALKING_POINT 抑制） |
| PROFILE_1ON1 | PASS | 2 场 + DELIVERY 抑制 + CRITICAL_RISK override |
| PROFILE_CLIENT_CALL | PASS | 2 场 + ANSWER_CUE/直接问题 |
| PROFILE_NEGOTIATION | PASS | 2 场 + SOCIAL_RISK→SILENT |
| SESSION_PACK_IMMUTABILITY | PASS | digest 前后一致（J1） |
| TRUTH_PROVENANCE | PASS | J2 全负向通过 |
| OPEN_THREADS | PASS | 520+300 投影 + 无 phantom |
| CONVERSATION_STATE | PASS | derived only（J4） |
| MANUAL_ASK | PASS | 权威序 + frozen replacement + token 精确 |
| AUTO_GUIDANCE | PASS | 全部 lane 场景（-vv 记录） |
| AUDIO_CAPTURE | PASS | 隔离/互斥/drain/自麦降级（-vv 记录 + 设备枚举） |
| PROCESSING_PRIVACY | PASS | LOCAL/CLOUD/OFF + drift fail-closed |
| SCREEN_CONTEXT | PASS | MANUAL/AUTO 生命周期 + raw 不落盘 |
| SHARE_PRIVACY | PASS | proof 缺失拒绝 + 桌面 lifecycle（真机验证） |
| HUMAN_COACH | PASS | 最小权限 + 审计 + revoke + 过期拒绝 |
| TRANSPARENCY | PASS | 五态 + TRANSCRIPT+NOT_RECORDED warning |
| CONNECTOR_REGISTRY | PASS | 空 registry/未知/写能力拒绝 + fake provider |
| DRAFT_ACTIONS | PASS | DRAFT→APPROVE，external_execution=false |
| REMINDERS | PASS | opt-in/restart/稳定/dedupe/无泄露 |
| EXPORT_DELETE_RETENTION | PASS | 11 类目 + tombstone + 保留策略 |
| SEARCH | PASS | grounded + Space/Session/time/source |
| DIAGNOSTICS | PASS | 与 runtime 一致（本地工程项） |
| WINDOWS_DESKTOP_RUNTIME | PASS | 修复 P1 后窗口「成竹」/端口/layout/无残留 |
| PACKAGED_CANDIDATE | PASS | installer+portable 构建 + smoke + 双证据 harness |
| CLEAN_REPLAY | PASS | fresh userData first-run + 全流程 + restart |
| SOAK | PASS | soak_sim 3h + conversation soak |
| HUMAN_EVAL_TOOLING | PASS | INSUFFICIENT_EVIDENCE / NO_GO / TOOLING_ONLY |
| STABLE_PROMOTION_GATE | PASS | 最终状态符合契约（见下） |
| model_eval (LLM) | BLOCKED_EXTERNAL | 无 CHENGZHU_EVAL_API_KEY |
| real-user pilot / human audio | BLOCKED_EXTERNAL | 无真人授权参与者 |
| GitHub Releases API 资产核验 | BLOCKED_EXTERNAL | 未认证；git tags 已核验 |
| soak audio/sleep/network | BLOCKED_EXTERNAL | 脚本声明 |
| human_visual_acceptance | BLOCKED_EXTERNAL | 契约显式 false |

## Stable Promotion Gate 最终状态
```
REAL_CONVERSATION_USER_EVIDENCE_PENDING = TRUE
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
V2_STABLE_RELEASE = FALSE
PMF_PROVEN = FALSE
```
说明：stable_readiness 工具对「SYNTHETIC manifest」输出过 `PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW`，但该输入为合成数据（非真实用户），因此本报告层按契约将真实证据门禁保持 FALSE 并标记 TOOLING_ONLY。

## MANIFEST（§54 统计项）
- P0_COUNT = 0
- P1_COUNT = 1（已修复：packaged overlayLayout 启动崩溃）
- P2_COUNT = 1（已修复：delivery cue 未用 frozen 表达）
- P3_COUNT = 1（观察：E2E 时序 flake，retry 通过）
- BLOCKED_EXTERNAL = 5（model_eval、real-user pilot、Releases API、soak 三项、human_visual_acceptance）
- 测试基建修复（conftest STT 环境隔离）= 1
