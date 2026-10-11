# Chengzhu v1.4 Engineering Validation Evidence

> Evidence type: SYNTHETIC_DOGFOOD. This is deterministic engineering evidence, not real-user evidence and not PMF proof.

## Gate summary

- 7-day continuity: PASS
- 30-session continuity: PASS
- 7-day integrity: PASS
- 30-session integrity: PASS
- 100-session continuity: PASS
- 100-session integrity: PASS
- real_user_validation: REAL_USER_VALIDATION_PENDING

## Seven-day continuity checks

- PASS: day2_next_focus_bounded
- PASS: day4_pack_has_goal_note
- PASS: day4_no_cross_goal_note
- PASS: day4_overlay_cleared
- PASS: day5_reflection_found_ownership
- PASS: day5_pin_first
- PASS: day5_reflection_can_create_quick_note
- PASS: day6_state_continuity
- PASS: day6_next_focus_is_reflection_ownership
- PASS: day6_material_still_ready
- PASS: day6_quick_note_kept
- PASS: day6_fact_inbox_has_lead_claim
- PASS: day6_fact_inbox_resolution_recorded
- PASS: day7_practice_starts_on_weakness
- PASS: day7_progress_visible
- PASS: no_cross_goal_focus
- PASS: transfer_measured
- PASS: day7_pin_can_become_next_focus
- PASS: day7_value_metrics_cover_reflection_note_and_pin

## Thirty-session continuity checks

- PASS: all_sessions_persisted
- PASS: every_session_linked_to_its_goal
- PASS: next_focus_bounded
- PASS: integrity_clean

## Hundred-session reliability checks

- PASS: all_sessions_persisted
- PASS: every_session_linked_to_its_goal
- PASS: next_focus_bounded
- PASS: integrity_clean

## A · Goal reuse

    {"goals": 2, "goal_reopen_rate": 0.5, "sessions_per_goal": 2.0, "median_goal_lifespan_days": 3.0, "median_return_interval_hours": 96.0, "next_focus_items": 7, "next_focus_action_rate": 0.143}

## B · Reflection → Prepare

    {"reflections_opened": 2, "reflection_actions": 3, "writeback_actions": 2, "next_focus_from_reflection": 2, "practices_started_on_reflection_focus": 1, "follow_through_rate": 0.5, "by_action": {"SET_NEXT_FOCUS": 2, "ADD_QUICK_NOTE": 1}}

## C · Fast Cue usefulness signals

    {"rendered": 1, "usefulness": {"session_feedback": {}, "helpful_marks": 1, "speech_after_cue_rate": 1.0}, "accuracy": {"regenerate_rate": 0.0, "dismiss_rate": 0.0}, "personal_fact_safety": {"fact_checks_from_pins": 0}, "latency": {"turns": 0, "qbd_ms": {"n": 0, "p50": null, "p95": null}, "ttfug_user_ms": {"n": 0, "p50": null, "p95": null}, "ttfug_predictive_ms": {"n": 0, "p50": null, "p95": null}, "ttfug_internal_ms": {"n": 0, "p50": null, "p95": null}, "ttfa_ms": {"n": 0, "p50": null, "p95": null}, "ttd_ms": {"n": 0, "p50": null, "p95": null}}, "readability": {"expand_rate": 1.0, "deep_open_rate": 1.0}, "over_specificity": {"dismissed": 0}, "note": "分维度代理信号，不合成单一分数；Live 持续语音分析默认关闭。"}

## D · Practice transfer

    {"links": [{"next_focus_id": "nf_83ab481bec1142d7", "goal_id": "g_faab379346394bcd", "dimensions": ["ownership", "impact"], "type": "OWNERSHIP", "before_level": 1.0, "after_level": 3.0, "after_sessions": 2, "evidence_type": "SYNTHETIC_TRANSFER"}], "improved": 1, "measured": 1, "note": "SYNTHETIC_TRANSFER 只是工程证据，不代表真实面试中的迁移。"}

## E · Fact Inbox burden

    {"inbox_created": 1, "opened": 1, "resolved": 1, "dismissed": 0, "handled": 1, "backlog_size": 0, "resolution_rate": 1.0, "dismiss_rate": 0.0, "median_time_to_resolve_s": 345600.0, "oldest_backlog_age_s": null, "reopened": 0, "policy": {"mode": "STANDARD", "reasons": []}, "items_generated_per_import_day": 1.0}

## F · Quick Notes / Pin value

    {"quick_notes": {"created": 3, "existing": 3, "selected_into_pack": 1, "opened_in_live": 1, "used_repeatedly_goals": 0, "converted_from_reflection": 1}, "pins": {"created": 1, "pins_per_session": 1.0, "used_in_reflection": 1, "next_focus_from_pin": 1, "story_from_pin": 0, "fact_check_from_pin": 0}}

## Product friction audit

    {"journeys": [{"key": "home_to_practice", "label": "Home → Practice", "designed_steps": 2, "budget": 3, "path": ["开始练习", "开始演练"], "completed": 3}, {"key": "goal_to_live", "label": "Goal → Go Live", "designed_steps": 2, "budget": 2, "path": ["上场", "冻结并开始"], "completed": 1}, {"key": "live_to_quick_note", "label": "Live → Quick Notes", "designed_steps": 1, "budget": 1, "path": ["打开速记"], "completed": 1}, {"key": "live_to_pin", "label": "Live → Pin", "designed_steps": 2, "budget": 2, "path": ["Ctrl+P", "保存标记"], "completed": 1}, {"key": "session_to_reflection", "label": "End Session → Reflection", "designed_steps": 0, "budget": 1, "path": ["自动进入 Reflection"], "completed": 2}, {"key": "reflection_to_next_practice", "label": "Reflection → Next Focus → Practice", "designed_steps": 2, "budget": 3, "path": ["练这个/设为 Next Focus", "开始演练"], "completed": 2}], "all_within_budget": true, "evidence_type": "DESIGN_PATH_PLUS_LOCAL_COMPLETION_SIGNAL", "note": "步数是产品交互预算；completed 只是本机完成信号，不是用户研究结论。"}

## Honest conclusion

- PRODUCT_VALIDATION_INFRA_COMPLETE: supported by the local event store, six-question report, continuity dogfood and integrity checks.
- REAL_USER_EVIDENCE_PENDING: still true.
- PMF PROVEN: must not be claimed from this artifact.
