# PRIVACY FAILURE INJECTION REPORT

## 处理方式（Processing）fail-closed
- **LOCAL + 共享 STT remote-possible**: Preflight BLOCK；Capture start 二次 BLOCK（`processing_runtime_status` 在 start 时重查，防 config drift 静默越界）。证据: `conversations-connectors-vv.log.txt`（`test_local_transcript_fails_closed_when_shared_stt_can_go_remote`, `test_capture_rechecks_processing_policy_after_preflight`）、`phase_o_report.full.json` F6。
- **OFF**: TRANSCRIPT 不可用 + AI FORBIDDEN（Manual Ask 与 Guidance 均拒）。证据: `test_processing_off_requires_no_transcript_and_ai_forbidden`。
- **config drift**: Preflight 安全 → start 前改 remote → capture start 拒绝。证据: `test_capture_rechecks_processing_policy_after_preflight`。
- 无“UI 说 LOCAL 却静默走 remote”路径：`processing_runtime_status` 为唯一权威并在 pack 中冻结（`test_frozen_pack_records_resolved_processing_route`）。

## 故障注入矩阵（phase_o_report.full.json）
| 注入 | 结果 |
| --- | --- |
| F1 mic open fail（pipeline 抛错） | capture start 抛错、overlay 恢复、is_active=False —— truthful degrade |
| F3 database locked（EXCLUSIVE） | 写操作干净 OperationalError；读可用；无假成功 |
| F4 missing Quick Note / invalid material | preflight warning + pack 记录 skipped/missing ids；start 优雅继续 |
| F5 coach expired/revoked | revoke 后 active()=False，token 不可再用 |
| F6 remote STT while LOCAL / OFF | 阻断/fail-closed |
| F7 Electron content protection 不可用 | PRIVATE_OVERLAY start 拒绝（runtime proof 缺失） |
| self-mic（candidate）degraded | 暴露降级状态而非假成功（`test_conversation_capture_reports_self_mic_degraded_state`） |
| screen AUTO 连续错误 | 3 次真实错误 fail-stop（`test_auto_screen_blank_frame_is_not_a_failure_but_three_real_errors_fail_stop`） |
| duplicate / stale / social risk | SILENT 抑制（SOCIAL_RISK、DUPLICATE_GUIDANCE、STALE_CONTEXT） |
| connector 无 provider / 未知 / 写能力 | Preflight BLOCK / UNKNOWN_CAPABILITY / WRITE_REQUIRES_EXPLICIT_EXECUTION_FLOW |

## 隐私相关证据
- Share Privacy：web/browser 无 bridge → fail-closed；桌面端 start 前必须 verified Electron proof，结束恢复原全局设置（E2E `PRIVATE_OVERLAY verifies Electron protection before start and restores baseline after end` + 真机验证）。
- Screen Context：raw image 不持久化（`test_manual_screen_context_persists_only_text_hash_and_model_provenance`）；AUTO 需显式启动（`test_auto_screen_preflight_requires_explicit_consent_transparency_and_never_autostarts`）。
- Human Coach：transcript/AI cue 默认 OFF（`CoachPanel` conversation 默认 `{transcript:false, ai_cue:false, session_context:true}`，LAN OFF）；Helper 无 Interview Resume/JD/其他 Session 权限（coach registry 按 live_session 绑定 + revoke_for_target）。
- 参与者透明：TRANSCRIPT+NOT_RECORDED → warning（`test_transcript_preflight_surfaces_unrecorded_transparency_plan_as_warning`）；系统不声称自动通知/watermark（UI 分 current use / consent reported / transparency plan）。
- 敏感值：本报告与全部证据仅记录 `configured / missing`，未落盘任何 API key/token。

## 结论
- 无 silent privacy policy violation；无 fake success；无 crash entire product。
- 唯一 P1 级“打包启动崩溃”不属于隐私路径（BUG-01），已修复并验证。
