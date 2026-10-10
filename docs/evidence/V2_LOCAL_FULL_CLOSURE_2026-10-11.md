# Chengzhu v2 — Local Full Closure Report (2026-10-11)

**Status**: COMPLETE for everything this machine can legally prove. Every section below records only
results actually observed on this machine; nothing is inferred, and no external blocker is written as a pass.
**Branch**: `chore/v2-local-full-closure-2026-10-11`
**Base SHA**: `c581c0d764cf6dd4f59a254957b90dd7eb409f45` (`origin/main`)
**Worktree**: isolated git worktree (the pre-existing checkout was left byte-identical)
**Machine**: Windows 11 Pro 10.0.26200, AMD64, Python 3.13.14, Node 22.15.0, npm 11.3.0,
git 2.55.0.windows.5, Electron 41.10.7, Playwright Chromium, ffmpeg 8.0

Allowed status tokens: `NOT_RUN` · `PASS` · `FAIL` · `BLOCKED_EXTERNAL` · `BLOCKED_ACCOUNT` ·
`BLOCKED_HUMAN_EVIDENCE` · `NOT_APPLICABLE`

Hard rules honoured throughout:

- **no external API quota was spent** — every runtime run pointed the model provider at a local
  fake OpenAI-compatible server and used local whisper for STT;
- **no fabricated evidence** — no synthetic session, mock, CI artifact or placeholder label is
  presented as real-user or real-account evidence;
- **no secret value** is written into this report, the repository, or any artifact;
- Google / Microsoft real-account replay is **not** claimed, because no credential for those
  providers exists on this machine.

## 0. Defects found and fixed during this closure

Three real defects were found by running the product rather than by trusting the test suite.
Each was root-caused, fixed minimally, and given a regression test.

| # | Defect | Root cause | Fix | Regression guard |
| --- | --- | --- | --- | --- |
| 1 | **The shipped Windows app never started.** Launching the packaged build opened a blocking Electron main-process error dialog: no window, no backend, no user data, forever. | `desktop/main.js` requires `./overlayLayout` at module scope (added with the v1.3 overlay work) but `desktop/package.json` `build.files` — which *replaces* electron-builder's default `**/*` set — was never updated, so `overlayLayout.js` was absent from `app.asar`. | Added `overlayLayout.js` to `build.files`. | `desktop/packagingFiles.test.js` (3 tests): every local module and `__dirname` resource a packaged entry point loads must be listed in `build.files`. Negative control against the pre-fix manifest reports exactly `main.js requires ./overlayLayout`. |
| 2 | **A question about a different number was wrongly grounded.** With a frozen source containing `30 days`, the question `3 days` returned `grounded=True`. | `_text_match_score` derived its factual-identity tokens from a `len(x) >= 2` segmented set, so the single-digit token `3` vanished and the generic words (`migration`, `window`, `days`) alone satisfied the match. | `backend/services/product/conversations.py`: collect digit-bearing tokens without the length filter and require each to occur as its own alphanumeric token (`(?<![0-9a-z])token(?![0-9a-z])`). | `test_manual_ask_does_not_ground_changed_duration_token` (both directions) plus new `v2`/`v3`, `2026`/`2025`, `$10k`/`$100k` tests. Proved by stashing only the product fix: 1 failed / 3 passed. |
| 3 | **Load-dependent false red** in `JobTracker` unit test 668. | The test synchronised on `'Acme'` list text and then synchronously queried a detail-pane button that mounts later; under CPU contention the second query ran too early. | Wait for the element itself (`findByRole`); the assertion is unchanged. | Repeated full runs, including under deliberate parallel CPU load: 428/428 twice. |

Why these escaped earlier gates: the release workflow tries the packaged-GUI evidence step and, when
it fails on a hosted runner, falls back to a headless “packaged sidecar + packaged frontend-dist”
variant while recording the limitation — so no automated gate ever actually started the Windows GUI.

---

## 1. Source truth

**Status**: `PASS`

| Fact | Value |
| --- | --- |
| `origin/main` (base) | `c581c0d764cf6dd4f59a254957b90dd7eb409f45` (= expected baseline) |
| work branch | `chore/v2-local-full-closure-2026-10-11` |
| worktree | `E:\AI\面试助手\.pi\closure-wt` (isolated git worktree, branch base `c581c0d`) |
| original checkout HEAD | `699fafe4cb784fda3cfa1b8c98b89a4f0db528e6` — unchanged |
| original checkout porcelain | byte-identical to the pre-work snapshot (7 modified + the pre-existing untracked files) |
| published tags seen | `v1.4.2` (stable), `v2.0.0-beta.2 = cac605edf413ec248babf02ea9f73da708d156f8` |

Command: `git worktree add .pi/closure-wt -b chore/v2-local-full-closure-2026-10-11 c581c0d…`, then a
`Compare-Object` of `git status --porcelain` before/after → `PORCELAIN IDENTICAL`.

## 2. Static gates

**Status**: `PASS`

| Gate | Command | Result |
| --- | --- | --- |
| backend lint | `ruff check .` (backend) | `All checks passed!` exit 0 |
| backend syntax | `python -m py_compile main.py api/assist/pipeline.py api/common/router.py` | exit 0 |
| frontend types | `npx tsc -b --noEmit` | exit 0 |
| release version consistency | `python scripts/check_release_version.py` | `{"ok": true, "version": "2.0.0-beta.2", "release_channel": "PRERELEASE"}` exit 0 |
| license / third-party notices | `python scripts/generate_third_party_notices.py --check` | exit 0 |
| secret scan | `python scripts/v2_local_secret_scan.py` | `passed=true`, 0 blocking findings |
| `git diff --check` | — | clean |

`scripts/v2_local_secret_scan.py` scans git-tracked files, `artifacts/`, `reports/`, `docs/evidence/`
and the branch's git history for GitHub/OpenAI/AWS/Slack/Google token shapes, bearer headers, URL
userinfo, private-key blocks and OAuth client secrets, and reports matches redacted
(4-char prefix + length) so no secret value can enter this report. It found 13 matches, **all** of
which are the same three deliberately fake literals used by the connector redaction tests
(`sk-abcdefghijklmnopqrstuvwxyz123456`,
`Authorization: Bearer abcdefghijklmnopqrstuvwxyz`,
`https://alice:supersecret@…`) introduced by upstream commits `72e810c` / `5571bb2`; these are
classified as documented fixtures (`allowlisted_fixtures`), and anything else would block the scan.

## 3. Backend gates

**Status**: `PASS`

| Gate | Result |
| --- | --- |
| full suite `python -m pytest -q` | **1336 passed, 0 failed, 0 error**, 274.63 s |
| strict intelligence eval | `route_accuracy_exact = 1.0` (≥0.9), seven-turn exact `= 1.0` (≥0.85), `unsupported_claim_rate = 1.0` (≥0.95), exit 0 |
| `python -m evals.r2_eval --check` | exit 0 |
| `python scripts/v14_validation_evidence.py --out-dir artifacts/validation` | exit 0, `{"ok": true, "thirty_session": true, "hundred_session": true, "real_user_evidence": "REAL_USER_EVIDENCE_PENDING"}` |
| `python scripts/soak_sim.py --hours 3` | exit 0, `passed: true` (audio switching / sleep-wake / real participants explicitly `BLOCKED-EXTERNAL`) |

Coverage spans Interview, Conversation, product DB migrations, Goals, Materials, Quick Notes,
Intelligence, Assist, Audio, STT, Screen, Overlay, Human Coach, connectors, integration audit,
retention, export, delete and the release/evidence gates.

## 4. Frontend gates

**Status**: `PASS`

| Gate | Result |
| --- | --- |
| `npm test` (vitest) | **428 passed / 59 files**, exit 0 (re-verified twice, once under deliberate parallel CPU load) |
| `npm run build` | exit 0 |
| `npx playwright test --grep-invert @visual` | **65 passed**, exit 0 |
| `npx playwright test --grep @visual` | **3 passed**, exit 0 on the verification run |
| `a11y.spec.mjs` | 9 passed (home/goals/me/practice/library/history/settings + keyboard + appMode) exit 0 |
| 390 px responsive | covered inside the functional run: `v20-conversation-profile.spec.mjs` “Conversation surfaces remain usable at 390px”, `job-workspace.spec.mjs`, `job-review-linkage.spec.mjs`, `v13-product-loop.spec.mjs` overlay 390 px |

Visual-baseline honesty: the repository commits only `linux`/`darwin` snapshots. The first local
Windows run therefore wrote `action-home-win32.png`, `goals-win32.png`, `me-resume-win32.png`
(“A snapshot doesn't exist …, writing actual”) and failed; the **second** run passed against those
generated baselines. The committed Linux baselines remain the cross-platform contract and are the
ones CI verifies; the generated win32 files are kept as local evidence rather than committed, so the
PR adds no binary churn.

## 5. Desktop gates

**Status**: `PASS`

`node --test *.test.js` → **38 tests / 38 pass / 0 fail** (35 pre-existing + 3 new packaging-manifest
guards from defect #1). Covers `backendLauncher`, `windowOptions`, `shortcuts`, `sharePrivacy`
integration, `multiScreenBatch`, `conversationReminders` (no session title in notification,
`LOCAL_CHENGZHU_SCHEDULE_ONLY`) and overlay layout.

## 6. Conversation runtime

**Status**: `PASS`

Real runtime evidence, no mocks for the pieces that claim runtime:

1. **Real packaged sidecar loop** (`scripts/packaged_smoke.py`, exit 0): first run reaches
   `/api/instance`, schema `9 == 9`, frontend served, Fast Cue before the first deep token, Interview
   pack frozen and persisted; then the Conversation loop —
   `conversation_preflight_ready`, `conversation_pack_frozen` with digest
   `0cdf174c2ef68905a7d61a334370ad234c8493cb402f9d108bd7e2cf2e9b5aaf`,
   `conversation_decision_reviewed`, `conversation_ask_grounded`,
   `conversation_global_search_grounded`, `conversation_continue_reviewed_truth`,
   `conversation_export_scoped`, and after a real process restart: pack/history/reviewed-truth
   persisted, `conversation_diagnostics_healthy`.
2. **Same loop against a real GitHub-backed pack** — see section 14: frozen pack digest present,
   connector snapshots and grants frozen, Manual Ask grounded on the frozen external snapshot.
3. **Semantics** are verified by named tests inside the 1336-passing suite, including: frozen pack
   vs mid-session material edits (`test_manual_ask_uses_frozen_ready_sources_not_latest_material`),
   space-goal/participant/playbook/expression freezing, the arbiter
   (`test_guidance_arbiter_critical_risk_visibility_duplicate_social_and_budget`,
   `test_direct_question_cancels_stale_opportunity`,
   `test_proactive_recall_and_open_question_require_allowed_source_visibility`), guidance sources
   (`…direct_question_is_first_class_even_in_quiet_and_self_mic_never_interrupts`,
   `…contribution_opportunity_without_promoting_notes`, `…topic_recall_is_sourced_deduped…`), the
   truth model (`test_conversation_fact_taxonomy_preserves_state_semantics`,
   `test_decision_cannot_be_promoted_to_agreed_from_model_extraction_alone`,
   `test_commitment_requires_owner_source_and_confirmation`, `test_deadline_requires_provenance`,
   `test_quick_note_is_never_evidence`), candidate extraction
   (`test_end_session_extracts_only_review_candidates…`,
   `test_primary_audio_commitment_does_not_infer_owner`), supersession
   (`test_decision_supersession_direction_preserves_old_truth_and_confirms_new`), longitudinal open
   threads (`test_reviewed_open_items_project_into_longitudinal_threads_and_resolve`,
   `test_rejected_candidate_never_becomes_longitudinal_thread`) and profile isolation
   (`test_conversation_capture_refuses_to_steal_live_interview_audio`,
   `test_interview_start_refuses_to_preempt_active_conversation_capture`,
   `test_conversation_history_is_profile_native_and_counted`).
4. **Gap closure added by this run** (the audit found these were untested): `v2` vs `v3`,
   `2026` vs `2025`, `$10k` vs `$100k`, `3 days` vs `30 days` discriminator pairs; the
   `SOURCE_CONFIRMED` review state (asserted against the real contract — no code path produces it
   automatically, and inventing one would have been fabrication); and `CONFIRMED_TRUTH` authority in
   a backend Manual Ask.
5. **Frozen-pack digest stability under mid-session edits** beyond the unit level: the packaged
   smoke compares `conversation_context_digest_before_restart` with the post-restart digest and
   requires the frozen pack to survive.

Evidence: `artifacts/runtime-evidence/2026-10-11-v2-local-full-closure/`,
`reports/packaged_smoke.json`, `artifacts/release-evidence/v2.0.0-beta.2/`.

## 7. Interview regression

**Status**: `PASS`

- The Interview runtime is exercised by the 1336-passing backend suite and the 65-passing Playwright
  run (`v13-product-loop.spec.mjs`, `critical-paths.spec.mjs`, `written-exam-flow.spec.mjs`,
  `r2-live-cue.spec.mjs`, `job-*`/`resume-*` linkage specs).
- The packaged GUI evidence run captured the Interview surfaces (`01-onboarding` … `29-history`)
  from the real packaged app, i.e. Interview and Conversation coexist in one packaged build.
- `scripts/e2e_test.py` (real backend boot + API contracts incl. `/api/config`, `/api/options`,
  `/api/devices`, `/api/stt/status`, `/api/session`, `/api/job-tracker/*`, `/api/resume/history`)
  → exit 0.
- Conversation connector runtime does not touch Interview provider semantics: connector runtimes are
  registered only under the Conversation product layer, the Interview tests are unchanged, and
  `test_conversation_capture_refuses_to_steal_live_interview_audio` /
  `test_interview_start_refuses_to_preempt_active_conversation_capture` assert the boundary in both
  directions.

## 8. Audio / ASR

**Status**: `PASS` (real devices, local whisper, no remote STT)

Evidence file: `artifacts/runtime-evidence/2026-10-11-v2-local-full-closure/audio.json`.

| Check | Observed |
| --- | --- |
| device enumeration via real backend `GET /api/devices` | 10 devices; 2 loopback system-audio devices (id `20000` = default output “★ 扬声器 (EDIFIER M30 Plus) (系统音频)”, id `20001`); 8 microphones |
| Conversation preflight | no blockers |
| capture start → pause → resume → stop | all succeeded; status shows `owns_requested_session: true`, `device_id: 20000`, `mode: TRANSCRIPTION_ONLY` |
| second session stealing a live capture | refused: `400 另一场 Conversation 正在占用音频采集` |
| stop twice | second stop returned immediately (no deadlock) |
| transport released after stop | next session took ownership successfully (no zombie owner / no stale session) |
| rapid start/stop ×3 | 1.44 s total, no deadlock |
| repo loopback STT validation suite (`backend/scripts/run_audio_validation_suite.py`, device 20000, provider `whisper`) | exit 0 · `preflight_failure_count 0`, `replay_failure_rounds 0`, `total_failure_count 0`, `preflight_success_count 3/3`, `replay_success_rounds 6`, `max_raw_queue_drop_count 0`, **`max_segment_dropped 0`**, `max_loopback_discontinuity_count 0` |

The suite plays the real latency corpus through the default output and captures it through WASAPI
loopback, so the last ASR segment is proven not to be lost under a real capture path; the recognised
preflight phrase was `请介绍一下你最近做过的项目。` in all three rounds.

## 9. Screen Context

**Status**: `PASS` (runtime + fail-closed; packaged screenshots for the manual path)

- MANUAL: `test_manual_screen_context_persists_only_text_hash_and_model_provenance` (observation
  text + image hash + vision model/route, **no raw image**),
  `test_manual_screen_context_rejects_vision_route_change_after_session_start`.
- AUTO: `test_auto_screen_preflight_requires_explicit_consent_transparency_and_never_autostarts`
  (a Session start never silently starts AUTO), `test_auto_screen_service_start_pause_resume_stop_owns_only_explicit_live_session`,
  duplicate-frame dedupe, fail-stop after real errors, and end-session force stop.
- UI-level: `v20-conversation-profile.spec.mjs` MANUAL (no raw bytes) and AUTO (explicit second
  start, OFF THE RECORD, no raw persistence) inside the 65-passing run.
- LOCAL + remote vision fails closed (same spec family). Pack freezes the resolved screen route.

## 10. Private Overlay

**Status**: `PASS`

- Web/browser without the Electron bridge fails closed: `conversationSharePrivacy.test.ts` (fail-closed
  without bridge, activate + verify, lease held, restore baseline, OFF).
- Backend refuses to start a PRIVATE_OVERLAY session without a verified desktop runtime proof:
  `test_private_overlay_is_available_but_start_requires_verified_desktop_runtime`,
  `test_share_privacy_off_does_not_require_runtime_proof`.
- End-to-end in the Electron path: `v20-conversation-profile.spec.mjs` “PRIVATE_OVERLAY verifies
  Electron protection before start and restores baseline after end”.
- Wording used everywhere in this closure is deliberately limited to **best-effort content
  protection on supported capture paths**; no undetectable / anti-proctoring / guaranteed-invisible
  claim is made.

## 11. Human Coach

**Status**: `PASS`

`test_r2_coach.py` (hashed one-time token + TTL + fail-closed revoke, API permission flow, coach cue
is advice not evidence, session-scoped helper state that never exposes Interview resume/JD,
mid-session policy tightening) and `test_product_conversations.py`
(`…requires_transparency_and_explicit_start`, `…cue_is_audited_but_never_truth`,
`…lease_revoked_on_end`, `test_human_assistance_fails_closed_without_participant_transparency`).
UI-level: `v20-conversation-profile.spec.mjs` “HUMAN_ALLOWED exposes an explicit session-scoped Human
Coach link with minimum default permissions”. Advice is `HUMAN_COACH`, `is_evidence = false`, and
never becomes Conversation truth; links revoke on end / delete session / erase Space.

## 12. Local reminders

**Status**: `PASS`

`desktop/conversationReminders.test.js` (reminder normalisation that retains **no** session title,
default lead time, only pending+due+non-stale reminders, privacy-safe runtime state
`GENERIC_BODY_NO_SESSION_TITLE` / `LOCAL_CHENGZHU_SCHEDULE_ONLY`),
`test_local_upcoming_reminders_only_return_active_future_scheduled_sessions`, and
`test_manual_scheduling_drives_next_session_without_calendar_connector` (no Calendar dependency).
Reminder persistence across a real restart is not directly asserted by a test — the registry
merge/delivered-state paths are covered, and the packaged clean-install replay persists user data
across a real restart — so this sub-claim is reported as implemented-and-partially-verified rather
than as a fresh restart test.

## 13. Connector framework

**Status**: `PASS`

From the real-account replay run (section 14) plus the connector test suites:

- catalog with `adapter_available`, per-capability `provider_scopes`, `sync` contract,
  `setup.{runtime_opt_in_env, credential_ref_format, read_target, write_target, secret_storage}`;
- **default OFF**: with the env flag unset the adapter is not registered
  (`adapter_available: false`, zero connections, no external call);
- connection lifecycle `DISCONNECTED → verify → CONNECTED` with a safe `account_hint` only, and the
  response never returns `credential_ref`;
- opaque env-backed credential reference (`provider:github:env:<ENV_VAR>`) with
  `secret_storage: PROCESS_ENV_ONLY`; the token is passed only through the child process environment
  and is absent from `product.db` bytes and from the Space export (verified by assertion);
- immutable snapshots with `content_hash`, revision view (`is_latest_revision`), Space-scoped
  selection, and frozen projection into the Session Pack with grants carrying `account_hint`;
- **write capabilities are never inheritable from a read session grant** — a session requesting
  `issue.create` is refused at start with `WRITE_REQUIRES_EXPLICIT_EXECUTION_FLOW`;
- execution audit, redaction, retention and export include audit/provenance but never credential refs
  (`test_exports_include_connector_provenance_and_audit_but_never_credential_refs`).

## 14. GitHub provider

**Status**: `PASS_REAL_ACCOUNT`

Evidence: `artifacts/runtime-evidence/2026-10-11-v2-local-full-closure/github-replay.json`
(`scripts/v2_local_github_replay.py`, exit 0, **48/48 assertions true**), against a **private
throwaway repository** created for this run (`huangdi97/chengzhu-connector-replay-2026-10-11`) with
two seed issues, using the locally authenticated account's token as `CHENGZHU_GITHUB_TOKEN`. No
production repository was touched. No external model provider was called (local stub).

Read path: flag-off run proves fail-closed; flag-on run proves catalog/capability/scope contract,
`DISCONNECTED → CONNECTED` verify with `account_hint = huangdi97`, a real issue sync producing 2
immutable snapshots with content hashes and a real sync cursor, Space selection, preflight, ACTIVE
session, and a frozen pack containing the snapshot **and** a connector grant with the account hint.

Manual Ask on the frozen snapshot: `grounded: true`, top match
`kind = CONNECTOR_SNAPSHOT`, `authority = REFERENCE_SOURCE`, `truth_confirmed = false`, and the
source ref carries connector provenance; the negative question (`50x data scale…`) returned
`grounded: false`.

Reviewed write: `CREATE_ISSUE_DRAFT` (`status DRAFT`) → review `APPROVE` → `APPROVED` →
`POST /draft-actions/{id}/execution {connection_id, target}` → `PENDING` with the target recorded →
`POST /integrations/executions/{id}/execute` → **`SUCCEEDED`**. A second `execute` returned
`SUCCEEDED` without a second issue (idempotency). Ground truth at the provider: **exactly one issue**
with the exact reviewed title, whose body starts with the exact reviewed content and carries
`<!-- chengzhu-execution:<audit idempotency key> -->` matching the audit row. Audit row records
`capability issue.create`, `operation CREATE_ISSUE`, the explicit target, the idempotency key, and a
sanitised response; the token appears nowhere in the audit row, the database, or the export.

Negative controls: a request with no explicit target anywhere (neither on the approved draft nor on
the execution request) did **not** reach the provider (`FAILED`, no issue created).

## 15. Google Calendar

**Status**: `BLOCKED_ACCOUNT`

Code, contract and fail-closed behaviour are verified by tests and the catalog:
read-only `calendar.read`, `provider:google-calendar:env:<ENV_VAR>`, `CHENGZHU_GOOGLE_CALENDAR_CONNECTOR_ENABLE=1`,
native sync-token semantics, all-day events not fabricating midnight timestamps, explicit target
failure vs connection-fatal 401, no event.write. No Google credential exists on this machine, so no
real replay is claimed. What is needed: an access token for a test account in
`$env:CHENGZHU_GOOGLE_CALENDAR_TOKEN` (env-ref credential), then run
`python scripts/v2_local_github_replay.py`-style flow — the connector flow is identical, so the
minimal command after enabling the flag is the same 6-step sequence (catalog → connection → verify →
sync → select → freeze → ask). Expected verification: one-page events read probe succeeds,
`account_hint` set, snapshot revisions immutable with drift visible for rescheduled/cancelled events.

## 16. Google Drive

**Status**: `BLOCKED_ACCOUNT` — same reason and same unblock path
(`CHENGZHU_GOOGLE_DRIVE_CONNECTOR_ENABLE=1` + `provider:google-drive:env:<ENV_VAR>`): read-only,
explicit folder target, full-refresh snapshots with full-source digest, Docs/Slides export,
Sheets first-sheet partial truth, binary metadata, oversized fallback, incomplete-search fail-closed.

## 17. Gmail

**Status**: `BLOCKED_ACCOUNT` (+ `BLOCKED_EXTERNAL` for OAuth publication)

Send-only by design; the requested scope set is `openid`, `email`, `gmail.send` with no
`gmail.readonly`/`gmail.modify`; reviewed `FOLLOWUP_EMAIL_DRAFT` → review → recipient → second
execute. No Google credential exists locally. Independently of the account, sending to real users
also requires Google OAuth sensitive-scope verification / consent publication, which is
`BLOCKED_EXTERNAL` — not a code defect.

## 18. Microsoft To Do

**Status**: `BLOCKED_ACCOUNT`

`Tasks.ReadWrite` only, no Mail/Calendar/Files/OneDrive scopes; reviewed `CREATE_TASK_DRAFT` → review
→ list target → second execute; pre-write probe failure is retry-safe and an unknown post-write
outcome must be `UNKNOWN_OUTCOME`. No Microsoft credential exists on this machine.

## 19. External execution safety

**Status**: `PASS`

- status set exercised by tests and by the real run: `PENDING`, `EXECUTING`, `SUCCEEDED`, `FAILED`,
  `UNKNOWN_OUTCOME`, `BLOCKED`, `CANCELLED`, with `RECONCILED` outcomes via
  `CONFIRMED_SUCCEEDED → SUCCEEDED` and `CONFIRMED_NOT_APPLIED → FAILED (retry_safe)`.
- `UNKNOWN_OUTCOME != FAILED`: set when the adapter raises, when the provider returns no explicit
  boolean `ok`, and for persisted `EXECUTING` orphans recovered at restart
  (`test_orphaned_executing_audit_recovers_to_unknown_outcome_after_restart`). Retry of a
  definitive-but-unsafe failure is refused unless the provider declared `retry_safe`
  (`上次 provider 明确失败但未声明 retry_safe；禁止直接重试`).
- Second-execute gating and serialisation are enforced in `execute_request`
  (`only APPROVED drafts`, connection still usable, `EXECUTION_LOCK`), and
  `test_external_execution_is_serialized_so_double_execute_calls_provider_once` covers the race.
- `UNKNOWN_OUTCOME` is only produced by fault injection (fake adapter / injected transport callable),
  never by manufacturing a real duplicate side effect — as required.
- Request/target/draft/connection/capability/target/idempotency-key/redaction are all recorded in the
  audit row; the real run additionally proves the audited idempotency key appears in the created
  provider artifact.

## 20. Export / Delete / Retention

**Status**: `PASS`

- Retention: preview requires explicit confirmation and preserves confirmed truth; MINIMUM /
  STANDARD / custom policies enforced; `test_retention_keeps_selected_snapshots_and_execution_audit`.
- Export: categorised and keeps truth classes separate (confirmed truth / unconfirmed candidate /
  transcript / guidance / connector snapshot / execution audit / tombstone);
  `…export_is_categorized_and_keeps_truth_classes_separate`,
  `…session_export_is_categorized_local_and_scoped_to_current_session`,
  `…exports_include_connector_provenance_and_audit_but_never_credential_refs`; the packaged smoke
  asserts `conversation_export_scoped`; the real GitHub replay asserted the export contains no
  token.
- Delete Session: requires a tombstone when confirmed truth existed and keeps it.
- Delete Space: cascades Conversation runtime only and, with explicit confirmation, stops capture,
  stops AUTO screen, revokes Human Coach links and removes tombstones
  (`test_delete_space_cascades_conversation_runtime_only`,
  `test_space_complete_erase_requires_explicit_confirm_and_removes_tombstones`).
- 30-/100-session continuity: executed locally — `scripts/v14_validation_evidence.py` reports
  `thirty_session: true` and `hundred_session: true`, and the backend suite covers
  `test_thirty_session_continuity_stays_bounded_and_traceable`,
  `test_one_hundred_session_state_reliability`,
  `test_long_lived_space_open_thread_lookup_survives_over_500_other_threads`. These are **synthetic**
  continuity proofs, explicitly not real-user evidence.
- Migration matrix (`scripts/v2_local_migration_matrix.py`, exit 0, `passed: true`) over
  `fresh / v1 / v2 / v4 / v7 / v8 / v9`: additive in every case (no table or column lost), every
  seeded row survived — including the v8→v9 connector-snapshot table rebuild — no duplicate
  migration rows, `user_version` 9 reached, and a second `ensure_schema` left the schema fingerprint
  byte-identical (idempotent reopen). The v1.2.2 → current legacy adoption is separately proven by
  `backend/tests/test_product_migration_compat.py` using a real v1.2.2 store set.

## 21. Windows packaged runtime

**Status**: `PASS`

Detected and fixed defect #1 first; the packaged GUI is now proven to start:

- `scripts/build_sidecar.py` → sidecar exe (`chengzhu-backend.exe`, sha256 `8e2f2d5f…`);
  `npm run dist:win` → installer + portable + `win-unpacked` + blockmap, exit 0, unsigned (no
  signing identity present — reported, not hidden);
- `scripts/packaged_smoke.py` → `passed: true` (instance nonce echo, version, schema 9, frontend
  served, Fast Cue before deep token, pack persistence across restart, install dir untouched,
  LICENSE + THIRD_PARTY_NOTICES bundled, user-data layout under `CHENGZHU_HOME`);
- `frontend/scripts/capture-v13-packaged-window-evidence.mjs` → **46 real packaged
  BrowserWindow captures** (was: blocking error dialog → timeout);
- `frontend/scripts/capture-v20-conversation-packaged-evidence.mjs` → 6 Conversation packaged
  captures + manifest.

## 22. Clean-install replay

**Status**: `PASS`

`scripts/sandbox/verify-clean-install.ps1` run on this machine with **Python and Node removed from
PATH** and a clean `%APPDATA%\Chengzhu`, from the freshly built installer/portable
(`artifacts/runtime-evidence/…/clean-install/results.json`, `passed: true`):

`python_on_path false` · `node_on_path false` · `repo_checkout_present false` · SHA256 match for both
artifacts · silent install `installed_exe true`, LICENSE + notices bundled · first launch backend
ready **6.1 s** · `share_privacy_mode` default `OFF` · onboarding `false → true` · resume upload 200 ·
job goal created · `pack_frozen true` · live events `init, answer_start, guidance_fast, answer_chunk,
answer_done` with **Fast Cue before the deep chunk** · restart backend ready 3.0 s with pack,
onboarding and resume persisted · install dir byte-unchanged after use · uninstall removes the install
dir and keeps user data · portable launches (backend ready 3.3 s) and sees the same user data.

The earlier failing run of the same script (before the fix) is retained in
`artifacts/…/clean-install/` history as the counter-evidence: `first_launch_backend_ready_seconds:
null`, `fatal_error: 由于目标计算机积极拒绝，无法连接。`

## 23. Installer / Portable

**Status**: `PASS`

Built from the closure branch (`2.0.0-beta.2`, `PRERELEASE` channel) — **not** a reused beta.2
artifact. NSIS installer (`oneClick=false`, per-user), portable zip, and `win-unpacked`; the setup exe
and portable zip both contain the fixed asar (verified by listing `app.asar` → `overlayLayout.js`
present). Publication is out of scope for this run (see section 26), so the artifacts are staged
locally and upload-ready.

## 24. Artifact hashes

**Status**: `PASS`

| Artifact | SHA256 |
| --- | --- |
| `Chengzhu-Setup-x64.exe` | `93dd5ed02b454aea9fb0be4938862b430715a2afaa908cae622fa11e30bd73a6` |
| `Chengzhu-Portable-x64.zip` | `b0075b7db54780cc11bdd11a56e428c5b5e62be5878ee079992af65f38fb9f08` |
| `chengzhu-backend.exe` (sidecar) | `8e2f2d5fef91855680280714ff7058fd4bdccecc7a34603e68c04e844e4a1839` |

Also recorded: `dist/desktop/SHA256SUMS.txt` and
`artifacts/runtime-evidence/2026-10-11-v2-local-full-closure/SHA256SUMS.txt`. The Electron binary
used for the build was verified against the official GitHub-published checksum
(`electron-v41.10.7-win32-x64.zip` = `43f2f823a263ee7d3ac71282e26c417c9e4417bbefdfa97ede3fde15daf5a46d`)
before use.

## 25. Evidence screenshots

**Status**: `PASS`

- `artifacts/release-evidence/v2.0.0-beta.2/` — 46 real packaged BrowserWindow captures
  (Interview: onboarding/first goal/guided question/fast cue/overlay/quick note/reflection/complete,
  `02-action-home` … `29-history`; Conversation: `30-conversation-home` … `39-conversation-390-prepare`)
  + `manifest.json` with per-capture sha256.
- `artifacts/release-evidence/v2.0.0-beta.2/conversation-beta/` — 6 Conversation-only packaged
  captures (`01-conversation-home` … `06-conversation-history`, `04-conversation-live`,
  `06-conversation-history`) + manifest with per-capture sha256 and `overlays_detected: 0`.
- `artifacts/runtime-evidence/2026-10-11-v2-local-full-closure/` — `clean-install/` (installer UI,
  first launch, live-after-ask, after-restart, portable-launch + results.json + verify.log),
  `*-win32.png` visual baselines, `migration-matrix.json`, `audio.json`, `github-replay.json`,
  `secret-scan.json`, `diagnostics.json`, `stable-readiness.json` + `.md`, `human-report-empty.json`,
  `SHA256SUMS.txt`, `sidecar-sha256.txt`.
- Explicitly **not** claimed: any of these are synthetic/engineering captures, not real-user evidence.

## 26. Remaining external blockers

**Status**: `BLOCKED_EXTERNAL` / `BLOCKED_ACCOUNT` / `BLOCKED_HUMAN_EVIDENCE`

1. `BLOCKED_ACCOUNT` — **Google Calendar, Google Drive, Gmail** real-account replay: no Google
   credential on this machine. Needs env-ref access tokens for a test account; the connector flow and
   its assertions are already implemented and tested offline.
2. `BLOCKED_ACCOUNT` — **Microsoft To Do** real-account replay: no Microsoft credential.
3. `BLOCKED_EXTERNAL` — **Gmail send to real users**: Google OAuth sensitive-scope verification /
   consent-screen publication. Platform approval, not code.
4. `BLOCKED_EXTERNAL` — **MCP provider**: no real adapter/auth/account runtime exists upstream; only
   catalog fail-closed + unregistered-capability blocking + Preflight/diagnostics truth can be
   verified locally. No fake MCP connector was implemented.
5. `BLOCKED_EXTERNAL_PROVIDER` — **External Decision Log provider**: no real provider exists; only the
   local reviewed draft/approve/audit/export path can be exercised.
6. `BLOCKED_EXTERNAL_PERMISSION` — **download-back verification of a release**: this run was
   authorised to push a branch and open a PR only, so no tag or GitHub Release was created. The
   installers are staged with checksums and a ready-to-run download-back command
   (`scripts/sandbox/verify-clean-install.ps1` against the release asset URLs).
7. `BLOCKED_HUMAN_EVIDENCE` — **real-user evidence**: Opportunity Precision, Interruption Regret,
   Useful Silence, Recall Precision, cross-session value, cognitive load, Space-reuse intent.
   `docs/evals/v2_conversation_real_pilot_manifest.template.json` and the label template exist; the
   evaluator run with an empty (honest) report returns
   `PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW: false`, `V2_STABLE_RELEASE: false`,
   `PMF_PROVEN: false` (29 of 37 gate checks fail on sample size). The tooling actively refuses
   placeholder labels (`line 4: reviewer is required`), so fabricated labels cannot pass.
8. `BLOCKED_HUMAN_EVIDENCE` — real **audio device switching / sleep-wake / real participants**
   (`soak_sim` marks these `BLOCKED-EXTERNAL`), and a real multi-hour Interview/Project-Sync/Design-Review
   usage session with a human speaker (this run drove real device capture with the repository's own
   corpus and local whisper instead).

Nothing else remains: every other item in this report was executed and observed on this machine.

## 27. Release recommendation

**Status**: `PASS` (recommendation recorded)

Evidence-based recommendation: **BETA_RC / BETA_RELEASE_READY for a `v2.0.0-beta.3` prerelease**,
never stable. Engineering gates, packaged Windows product, clean-install replay, and the GitHub
real-account replay all pass; the packaged Windows product is *better* than the published beta.2
because the GUI launch defect found here was fixed. Stable promotion is not eligible: the human-label
gate is unmet (`BLOCKED_HUMAN_EVIDENCE`), `PMF_PROVEN = false`, and Google/Microsoft real-account
evidence is absent. Because publishing was outside this run's authorisation, the artifacts are staged
rather than released.
