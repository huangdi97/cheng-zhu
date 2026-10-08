"""v2.0 Conversation Profile: real persistence, truth state, pack and guidance loop."""
import asyncio
import sqlite3
import threading

import pytest

from services.product import conversation_capture, conversation_screen, conversations, materials
from services.storage import product as store


def test_v2_schema_is_additive_and_keeps_v1_tables(product_env):
    assert store.schema_version() == 7
    conn = sqlite3.connect(store.DB_PATH)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"goal", "practice_session", "product_event"} <= tables
    assert {
        "conversation_space",
        "conversation_goal",
        "conversation_session",
        "conversation_session_pack",
        "conversation_participant",
        "conversation_item",
        "conversation_open_thread",
        "conversation_guidance_event",
        "conversation_draft_action",
        "conversation_transcript_segment",
        "conversation_provenance_tombstone",
        "conversation_screen_context",
    } <= tables
    conn = sqlite3.connect(store.DB_PATH)
    try:
        session_cols = {r[1] for r in conn.execute("PRAGMA table_info(conversation_session)")}
        participant_cols = {r[1] for r in conn.execute("PRAGMA table_info(conversation_participant)")}
        item_cols = {r[1] for r in conn.execute("PRAGMA table_info(conversation_item)")}
    finally:
        conn.close()
    assert "policy_json" in session_cols
    assert "counterparty_state_json" in participant_cols
    assert "time_semantics_json" in item_cols






def test_manual_screen_context_local_processing_requires_local_vision_route(product_env, monkeypatch):
    from types import SimpleNamespace

    remote = SimpleNamespace(
        name="remote-vision",
        model="vision-remote",
        api_base_url="https://vision.example.com/v1",
        api_key="test-key",
        enabled=True,
        supports_vision=True,
    )
    monkeypatch.setattr(conversation_screen, "_enabled_vision_models", lambda: [remote])

    space = conversations.create_space("Screen Privacy", "DESIGN_REVIEW")
    session = conversations.create_session(
        space["id"],
        capture_mode="NOTES_ONLY",
        processing_mode="LOCAL",
        consent_ack=True,
        policy={"screen_context": "MANUAL"},
    )
    check = conversations.preflight(session["id"])
    assert check["screen_runtime"]["route"] == "REMOTE"
    assert check["screen_runtime"]["available"] is False
    assert any(x["key"] == "screen_context_runtime" for x in check["blockers"])
    with pytest.raises(ValueError, match="本地视觉模型"):
        conversations.start_session(session["id"])


def test_manual_screen_context_persists_only_text_hash_and_model_provenance(product_env, monkeypatch):
    from types import SimpleNamespace
    from services.capture import screen_capture

    local = SimpleNamespace(
        name="local-vision",
        model="vision-local",
        api_base_url="http://127.0.0.1:8080/v1",
        api_key="local-key",
        enabled=True,
        supports_vision=True,
    )
    monkeypatch.setattr(conversation_screen, "_enabled_vision_models", lambda: [local])

    class Cfg:
        screen_capture_region = "left_half"
        screen_capture_max_long_edge = 1600

    monkeypatch.setattr(conversation_screen, "get_config", lambda: Cfg())
    fake_image = "data:image/png;base64,QUJDREVGRw=="
    monkeypatch.setattr(screen_capture, "capture_primary_region_data_url", lambda region, max_long_edge=1600: fake_image)
    monkeypatch.setattr(
        conversation_screen,
        "_analyze_image",
        lambda image, model: "截图可见：rollback owner = Alex；版本 v2；风险窗口 Friday.",
    )

    space = conversations.create_space("Manual Screen", "DESIGN_REVIEW")
    session = conversations.create_session(
        space["id"],
        capture_mode="NOTES_ONLY",
        processing_mode="LOCAL",
        consent_ack=True,
        policy={"screen_context": "MANUAL"},
    )
    preflight = conversations.preflight(session["id"])
    assert preflight["blockers"] == []
    assert preflight["screen_runtime"]["route"] == "LOCAL"
    assert preflight["screen_runtime"]["raw_image_persisted"] is False

    started = conversations.start_session(session["id"])
    frozen = started["pack"]["payload"]["screen_runtime"]
    assert frozen["fingerprint"] == preflight["screen_runtime"]["fingerprint"]

    saved = conversations.capture_screen_context(session["id"], region="left_half")
    assert saved["text"].startswith("截图可见")
    assert saved["vision_route"] == "LOCAL"
    assert saved["image_hash"]
    assert saved["vision_fingerprint"] == frozen["fingerprint"]
    assert "data:image" not in repr(saved)
    assert "QUJDREVGRw" not in repr(saved)

    row = store.get("conversation_screen_context", saved["id"])
    assert row is not None
    assert "data:image" not in repr(row)
    assert "QUJDREVGRw" not in repr(row)

    asked = conversations.ask(session["id"], "rollback owner Alex")
    assert asked["grounded"] is True
    match = next(x for x in asked["matches"] if x["kind"] == "SCREEN_CONTEXT")
    assert match["authority"] == "OBSERVED_NOT_CONFIRMED"
    assert match["source_refs"][0]["image_hash"] == saved["image_hash"]

    session_export = conversations.export_session(session["id"])
    assert session_export["screen_context_observations"][0]["id"] == saved["id"]
    space_export = conversations.export_space(space["id"])
    assert space_export["screen_context_observations"][0]["id"] == saved["id"]
    assert "data:image" not in repr(space_export["screen_context_observations"])


def test_manual_screen_context_rejects_vision_route_change_after_session_start(product_env, monkeypatch):
    from types import SimpleNamespace

    current = {
        "model": SimpleNamespace(
            name="local-a",
            model="vision-a",
            api_base_url="http://127.0.0.1:8080/v1",
            api_key="local-key",
            enabled=True,
            supports_vision=True,
        )
    }
    monkeypatch.setattr(conversation_screen, "_enabled_vision_models", lambda: [current["model"]])

    class Cfg:
        screen_capture_region = "left_half"
        screen_capture_max_long_edge = 1600

    monkeypatch.setattr(conversation_screen, "get_config", lambda: Cfg())

    space = conversations.create_space("Frozen Vision", "DESIGN_REVIEW")
    session = conversations.create_session(
        space["id"],
        capture_mode="NOTES_ONLY",
        processing_mode="LOCAL",
        consent_ack=True,
        policy={"screen_context": "MANUAL"},
    )
    started = conversations.start_session(session["id"])
    old_fp = started["pack"]["payload"]["screen_runtime"]["fingerprint"]

    current["model"] = SimpleNamespace(
        name="local-b",
        model="vision-b",
        api_base_url="http://127.0.0.1:9090/v1",
        api_key="local-key",
        enabled=True,
        supports_vision=True,
    )
    assert conversation_screen.vision_runtime_status(conversations.require_session(session["id"]))["fingerprint"] != old_fp
    with pytest.raises(ValueError, match="视觉模型/数据路径已在本场开始后变化"):
        conversations.capture_screen_context(session["id"])


def test_screen_context_retention_uses_transcript_window(product_env, monkeypatch):
    space = conversations.create_space("Screen Retention", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    base = store.now()
    store.insert("conversation_screen_context", {
        "id": "csc-old",
        "space_id": space["id"],
        "session_id": session["id"],
        "capture_mode": "MANUAL",
        "region": "left_half",
        "text": "old screen observation",
        "image_hash": "hash",
        "vision_model": "vision",
        "vision_route": "LOCAL",
        "vision_fingerprint": "fp",
        "source": "TEST",
        "created_at": base,
    })
    future = base + 31 * 24 * 60 * 60
    preview = conversations.retention_preview(space["id"], now=future)
    assert preview["would_delete"]["screen_context_observations"] == 1

    monkeypatch.setattr(store, "now", lambda: future)
    applied = conversations.apply_retention(space["id"], confirm=True)
    assert applied["deleted"]["screen_context_observations"] == 1
    assert store.get("conversation_screen_context", "csc-old") is None


def test_active_conversation_goals_default_into_new_session_and_old_pack_stays_frozen(product_env):
    space = conversations.create_space("Goal Continuity", "PROJECT_SYNC")
    first_goal = conversations.create_goal(
        space["id"], "决定 rollout strategy", outcome_definition="形成明确方案", priority=90,
    )
    second_goal = conversations.create_goal(
        space["id"], "确认 rollback owner", outcome_definition="owner 明确", priority=80,
    )
    assert conversations.require_space(space["id"])["default_goal"] == first_goal["title"]

    first_session = conversations.create_session(space["id"], consent_ack=True)
    assert first_session["goal_ids"] == [first_goal["id"], second_goal["id"]]
    first_pack = conversations.start_session(first_session["id"])["pack"]
    frozen_ids = [g["id"] for g in first_pack["payload"]["session_brief"]["goals"]]
    assert frozen_ids == [first_goal["id"], second_goal["id"]]

    conversations.update_goal(first_goal["id"], {"status": "RESOLVED"})
    resolved = store.get("conversation_goal", first_goal["id"])
    assert resolved["status"] == "RESOLVED"
    assert resolved["resolved_at"] is not None
    assert conversations.require_space(space["id"])["default_goal"] == second_goal["title"]

    # Existing Session Pack remains immutable.
    existing = conversations.session_context(first_session["id"])
    assert [g["id"] for g in existing["brief"]["goals"]] == frozen_ids

    second_session = conversations.create_session(space["id"], consent_ack=True)
    assert second_session["goal_ids"] == [second_goal["id"]]
    second_pack = conversations.start_session(second_session["id"])["pack"]
    assert [g["id"] for g in second_pack["payload"]["session_brief"]["goals"]] == [second_goal["id"]]
    assert second_pack["payload"]["session_brief"]["goal"] == second_goal["title"]

    reopened = conversations.update_goal(first_goal["id"], {"status": "ACTIVE"})
    assert reopened["status"] == "ACTIVE"
    assert reopened["resolved_at"] is None
    assert conversations.require_space(space["id"])["default_goal"] == first_goal["title"]

    renamed = conversations.update_goal(first_goal["id"], {"title": "决定最终 rollout strategy"})
    assert renamed["title"] == "决定最终 rollout strategy"
    assert conversations.require_space(space["id"])["default_goal"] == "决定最终 rollout strategy"






def test_legacy_default_goal_patch_writes_through_to_primary_goal_without_double_truth(product_env):
    space = conversations.create_space(
        "Goal Projection",
        "PROJECT_SYNC",
        default_goal="旧主目标",
    )
    goals = conversations.space_detail(space["id"])["goals"]
    assert len(goals) == 1
    primary_id = goals[0]["id"]

    updated = conversations.update_space(space["id"], {"default_goal": "新主目标"})
    assert updated["default_goal"] == "新主目标"
    assert store.get("conversation_goal", primary_id)["title"] == "新主目标"

    session = conversations.create_session(space["id"], consent_ack=True)
    check = conversations.preflight(session["id"])
    assert next(x for x in check["items"] if x["key"] == "goal")["value"] == "新主目标"
    started = conversations.start_session(session["id"])
    assert started["pack"]["payload"]["session_brief"]["goal"] == "新主目标"

    with pytest.raises(ValueError, match="Goal lifecycle"):
        conversations.update_space(space["id"], {"default_goal": ""})


def test_manual_scheduling_drives_next_session_without_calendar_connector(product_env, monkeypatch):
    clock = [2_000_000_000.0]
    monkeypatch.setattr(store, "now", lambda: clock[0])
    space = conversations.create_space("Manual Schedule", "PROJECT_SYNC")
    scheduled = conversations.create_session(
        space["id"],
        title="Tomorrow sync",
        scheduled_at=clock[0] + 3600,
        consent_ack=True,
    )

    summaries = conversations.list_space_summaries("")
    row = next(x for x in summaries if x["id"] == space["id"])
    assert row["next_session"]["id"] == scheduled["id"]
    assert row["next_session"]["title"] == "Tomorrow sync"

    check = conversations.preflight(scheduled["id"])
    schedule_item = next(x for x in check["items"] if x["key"] == "schedule")
    assert schedule_item["value"] == clock[0] + 3600
    started = conversations.start_session(scheduled["id"])
    assert started["pack"]["payload"]["session_brief"]["title"] == "Tomorrow sync"
    assert started["pack"]["payload"]["session_brief"]["scheduled_at"] == clock[0] + 3600


def test_space_prepare_session_pack_continue_real_loop(product_env):
    space = conversations.create_space(
        "PDIG · Android Architecture",
        "DESIGN_REVIEW",
        default_goal="决定 conflict merge strategy",
        selected_source_ids=["doc:benchmark"],
    )
    conversations.add_participant(space["id"], display_name="Alex", role="Backend")
    session = conversations.create_session(
        space["id"],
        title="Architecture Review",
        capture_mode="NOTES_ONLY",
        processing_mode="LOCAL",
        consent_ack=True,
    )
    assert conversations.preflight(session["id"])["blockers"] == []
    started = conversations.start_session(session["id"])
    assert started["session"]["status"] == "ACTIVE"
    assert started["pack"]["payload"]["space"]["id"] == space["id"]
    assert started["pack"]["digest"]

    source = [{"kind": "TRANSCRIPT_SEGMENT", "session_id": session["id"], "excerpt": "那我们就按 v2 做"}]
    decision = conversations.add_item(
        session["id"],
        item_type="Decision",
        title="采用 offline sync v2",
        source_refs=source,
        epistemic_status="OBSERVED",
    )
    assert decision["state"] == "PROPOSED"
    assert decision["review_status"] == "AI_EXTRACTED"

    confirmed = conversations.review_item(decision["id"], "CONFIRM")
    assert confirmed["state"] == "AGREED"
    summary = conversations.end_session(session["id"])
    assert summary["decisions"][0]["id"] == decision["id"]
    assert summary["session"]["status"] == "ENDED"


def test_transcript_preflight_requires_explicit_ack(product_env):
    space = conversations.create_space("Weekly", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], capture_mode="TRANSCRIPT", consent_ack=False)
    check = conversations.preflight(session["id"])
    assert check["blockers"] and check["blockers"][0]["key"] == "consent"
    with pytest.raises(ValueError, match="确认"):
        conversations.start_session(session["id"])






def test_conversation_pack_reuses_shared_expression_profile(product_env, monkeypatch):
    monkeypatch.setattr(
        conversations.intelligence_store,
        "get_voice_profile",
        lambda owner: {
            "profile": {
                "explicit_preferences": {
                    "conclusion_first": True,
                    "target_seconds": 45,
                    "language": "zh-CN",
                    "term_style": "keep_english_terms",
                    "shape": "bullet",
                    "banned_phrases": ["赋能"],
                }
            }
        },
    )
    space = conversations.create_space("Expression", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    check = conversations.preflight(session["id"])
    assert check["pack_preview"]["expression_profile"]["target_seconds"] == 45
    started = conversations.start_session(session["id"])
    expression = started["pack"]["payload"]["expression_profile"]
    assert expression["conclusion_first"] is True
    assert expression["shape"] == "bullet"
    assert expression["banned_phrases"] == ["赋能"]


def test_session_policy_is_normalized_frozen_and_enforced(product_env):
    space = conversations.create_space("Policy Review", "DESIGN_REVIEW")
    session = conversations.create_session(
        space["id"],
        consent_ack=True,
        policy={
            "ai_assistance": "AI_FORBIDDEN",
            "human_assistance": "HUMAN_FORBIDDEN",
            "screen_context": "OFF",
            "share_privacy": "OFF",
            "external_writeback": "OFF",
            "participant_consent_status": "USER_REPORTS_CONSENTED",
            "speaker_biometric_identity": "ON",
            "emotion_sentiment_profiling": "ON",
            "hidden_intent_claims": "ON",
        },
    )
    check = conversations.preflight(session["id"])
    assert check["blockers"] == []
    policy = check["policy"]
    assert policy["ai_assistance"] == "AI_FORBIDDEN"
    assert policy["human_assistance"] == "HUMAN_FORBIDDEN"
    assert policy["share_privacy"] == "OFF"
    assert policy["external_writeback"] == "OFF"
    assert policy["participant_consent_status"] == "USER_REPORTS_CONSENTED"
    assert check["pack_preview"]["participants_count"] == 0
    assert check["pack_preview"]["policy"]["ai_assistance"] == "AI_FORBIDDEN"
    assert check["resolved_ai_behavior"]["manual_ask"] is False
    assert check["resolved_ai_behavior"]["manual_guidance"] is False
    assert check["resolved_ai_behavior"]["automatic_transcript_guidance"] is False
    assert check["resolved_ai_behavior"]["automatic_candidate_extraction"] is False
    assert check["pack_preview"]["resolved_ai_behavior"] == check["resolved_ai_behavior"]
    assert policy["speaker_biometric_identity"] == "OFF"
    assert policy["emotion_sentiment_profiling"] == "OFF"
    assert policy["hidden_intent_claims"] == "OFF"

    started = conversations.start_session(session["id"])
    assert started["pack"]["payload"]["policy"]["ai_assistance"] == "AI_FORBIDDEN"
    assert started["pack"]["payload"]["policy"]["share_privacy"] == "OFF"
    assert started["pack"]["payload"]["resolved_ai_behavior"]["manual_ask"] is False
    assert conversations.session_context(session["id"])["resolved_ai_behavior"]["policy"] == "AI_FORBIDDEN"

    suppressed = conversations.evaluate_guidance(session["id"], {
        "direct_question": "现在要不要补充？",
        "source_refs": [{"kind": "USER_NOTE", "excerpt": "explicit"}],
    })
    assert suppressed["guidance"] is None
    assert suppressed["suppressed"] == "POLICY_AI_FORBIDDEN"

    with pytest.raises(ValueError, match="External Write-back"):
        conversations.followup_draft(session["id"])


def test_preflight_blocks_unwired_auto_screen_and_human_runtime(product_env):
    space = conversations.create_space("Truthful Preflight", "PROJECT_SYNC")
    session = conversations.create_session(
        space["id"],
        consent_ack=True,
        policy={"screen_context": "AUTO", "human_assistance": "HUMAN_ALLOWED"},
    )
    check = conversations.preflight(session["id"])
    keys = {item["key"] for item in check["blockers"]}
    assert {"screen_context_runtime", "human_assistance_runtime"} <= keys
    assert check["screen_runtime"]["mode"] == "AUTO"
    with pytest.raises(ValueError, match="自动 Screen Context"):
        conversations.start_session(session["id"])


def test_counterparty_state_persists_only_explicit_fields(product_env):
    space = conversations.create_space("Stakeholder", "CLIENT_CALL")
    participant = conversations.add_participant(
        space["id"],
        display_name="Alex",
        role="CTO",
        explicit_priority="上线稳定性",
        explicit_concern="迁移风险",
        stated_position="先灰度",
        decision_authority="架构方案批准人",
        relationship_context="客户技术负责人",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "Alex 明确说先灰度"}],
    )
    state = participant["counterparty_state"]
    assert state["known_explicit"]["priority"] == "上线稳定性"
    assert state["known_explicit"]["concern"] == "迁移风险"
    assert state["known_explicit"]["stated_position"] == "先灰度"
    assert state["temporary_inferences"] == []
    assert "emotion" not in state["known_explicit"]
    assert "hidden_intent" not in state["known_explicit"]




def test_counterparty_correction_updates_future_sessions_without_rewriting_frozen_pack(product_env):
    space = conversations.create_space("Counterparty Correction", "CLIENT_CALL")
    participant = conversations.add_participant(
        space["id"],
        display_name="Alex",
        role="CTO",
        explicit_priority="速度",
        explicit_concern="迁移风险",
        relationship_context="客户技术负责人",
    )

    first = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(first["id"])
    first_ctx = conversations.session_context(first["id"])
    frozen = first_ctx["participants"][0]["counterparty_state"]["known_explicit"]
    assert frozen["priority"] == "速度"
    assert frozen["concern"] == "迁移风险"

    corrected = conversations.update_participant(participant["id"], {
        "explicit_priority": "稳定性",
        "explicit_concern": "",
        "stated_position": "先灰度",
        "decision_authority": "架构方案批准人",
        "relationship_context": "客户技术负责人",
    })
    known = corrected["counterparty_state"]["known_explicit"]
    assert known["priority"] == "稳定性"
    assert "concern" not in known
    assert known["stated_position"] == "先灰度"
    assert "concern" in corrected["counterparty_state"]["unknown"]
    assert corrected["counterparty_state"]["temporary_inferences"] == []

    # Already-started session remains on the old frozen participant state.
    still_frozen = conversations.session_context(first["id"])
    assert still_frozen["participants"][0]["counterparty_state"]["known_explicit"]["priority"] == "速度"
    assert still_frozen["participants"][0]["counterparty_state"]["known_explicit"]["concern"] == "迁移风险"

    second = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(second["id"])
    second_ctx = conversations.session_context(second["id"])
    future = second_ctx["participants"][0]["counterparty_state"]["known_explicit"]
    assert future["priority"] == "稳定性"
    assert "concern" not in future
    assert future["stated_position"] == "先灰度"


def test_stakeholder_context_influences_score_without_hidden_inference(product_env):
    space = conversations.create_space("Design", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True, assistance_mode="BALANCED")
    conversations.start_session(session["id"])
    result = conversations.evaluate_guidance(session["id"], {
        "current_topic": "迁移稳定性",
        "candidate_text": "Q4 benchmark 证明迁移稳定性",
        "source_refs": [{"kind": "DOCUMENT", "id": "bench"}],
        "relevance": 1,
        "novelty": 1,
        "provenance_strength": 1,
        "goal_relevance": 0.8,
        "decision_impact": 0.8,
        "audience_role": "CTO",
        "audience_priority": "迁移稳定性",
        "audience_concern": "回滚风险",
        "decision_authority": "架构方案批准人",
        "relationship_context": "客户技术负责人",
    })
    assert result["guidance"] is not None
    assert result["guidance"]["score"]["role_relevance"] >= 1.0
    saved = conversations.require_session(session["id"])
    assert saved["state"]["audience_context"]["explicit_priority"] == "迁移稳定性"
    assert saved["state"]["audience_context"]["relationship_context"] == "客户技术负责人"
    assert "emotion" not in saved["state"]["audience_context"]
    assert "hidden_intent" not in saved["state"]["audience_context"]




def test_ai_forbidden_blocks_manual_ask_as_well_as_guidance(product_env):
    space = conversations.create_space("No AI", "PROJECT_SYNC")
    session = conversations.create_session(
        space["id"],
        consent_ack=True,
        policy={"ai_assistance": "AI_FORBIDDEN"},
    )
    conversations.start_session(session["id"])
    with pytest.raises(ValueError, match="AI Assistance 已禁用"):
        conversations.ask(session["id"], "之前为什么用 v2？")
    result = conversations.evaluate_guidance(session["id"], {"direct_question": "为什么？"})
    assert result["guidance"] is None
    assert result["suppressed"] == "POLICY_AI_FORBIDDEN"


def test_ai_limited_allows_manual_but_disables_proactive_transcript_guidance(product_env):
    space = conversations.create_space("Limited AI", "PROJECT_SYNC")
    prior = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(prior["id"])
    item = conversations.add_item(
        prior["id"],
        item_type="Decision",
        title="offline migration 使用 v2",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "明确使用 v2"}],
    )
    conversations.review_item(item["id"], "CONFIRM")
    conversations.end_session(prior["id"])

    live = conversations.create_session(
        space["id"],
        consent_ack=True,
        policy={"ai_assistance": "AI_LIMITED"},
    )
    limited_check = conversations.preflight(live["id"])
    behavior = limited_check["resolved_ai_behavior"]
    assert behavior["manual_ask"] is True
    assert behavior["manual_guidance"] is True
    assert behavior["automatic_transcript_guidance"] is False
    assert behavior["automatic_candidate_extraction"] is False
    started = conversations.start_session(live["id"])
    assert started["pack"]["payload"]["resolved_ai_behavior"] == behavior
    assert conversations.session_context(live["id"])["resolved_ai_behavior"] == behavior
    assert conversations.guidance_from_transcript(live["id"], "offline migration") is None

    manual = conversations.evaluate_guidance(live["id"], {
        "direct_question": "之前为什么用 v2？",
        "source_refs": [{"kind": "USER_NOTE", "excerpt": "明确使用 v2"}],
    })
    assert manual["guidance"]["kind"] == "ANSWER_CUE"

    store.insert("conversation_transcript_segment", {
        "id": "cts_limited_no_extract",
        "space_id": space["id"],
        "session_id": live["id"],
        "channel": "PRIMARY_AUDIO",
        "text": "我们决定改成 v3。",
        "provider": "test",
        "source": "TEST",
        "is_final": True,
        "created_at": store.now(),
    })
    assert conversations.extract_transcript_candidates(live["id"]) == []


def test_ai_expected_uses_allowed_engine_but_records_expectation_without_extra_capability(product_env):
    space = conversations.create_space("Expected AI", "DESIGN_REVIEW")
    session = conversations.create_session(
        space["id"],
        consent_ack=True,
        policy={"ai_assistance": "AI_EXPECTED"},
    )
    check = conversations.preflight(session["id"])
    behavior = check["resolved_ai_behavior"]
    assert behavior == {
        "policy": "AI_EXPECTED",
        "manual_ask": True,
        "manual_guidance": True,
        "automatic_transcript_guidance": True,
        "automatic_candidate_extraction": True,
        "expected_by_user_report": True,
        "engine": "LOCAL_DETERMINISTIC",
    }
    started = conversations.start_session(session["id"])
    assert started["pack"]["payload"]["resolved_ai_behavior"] == behavior


def test_continue_contains_what_changed_and_pinned_guidance(product_env):
    space = conversations.create_space("Continue", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    decision = conversations.add_item(
        session["id"],
        item_type="Decision",
        title="采用 v2",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "决定采用 v2"}],
    )
    conversations.review_item(decision["id"], "CONFIRM")
    shown = conversations.evaluate_guidance(session["id"], {
        "direct_question": "接下来？",
        "source_refs": [{"kind": "USER_NOTE", "excerpt": "next"}],
    })["guidance"]
    conversations.set_guidance_action(shown["id"], "PINNED")

    summary = conversations.end_session(session["id"])
    assert [x["id"] for x in summary["what_changed"]] == [decision["id"]]
    assert [x["id"] for x in summary["pins"]] == [shown["id"]]




def test_unreviewed_open_question_stays_in_review_queue_not_longitudinal_continuity(product_env):
    space = conversations.create_space("Continuity Guard", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], title="Sync", consent_ack=True)
    conversations.start_session(session["id"])

    candidate = conversations.add_item(
        session["id"],
        item_type="OpenQuestion",
        title="谁负责 rollback drill？",
        source_refs=[{"kind": "TRANSCRIPT_SEGMENT", "excerpt": "谁负责 rollback drill？"}],
        epistemic_status="OBSERVED",
    )

    # The candidate is visible for review, but must not escape into Home,
    # Prepare, summary counts or Next Focus before explicit review.
    detail = conversations.space_detail(space["id"])
    assert [x["id"] for x in detail["open_questions"]] == [candidate["id"]]
    assert detail["threads"] == []

    prepared = conversations.prepare_space(space["id"])
    assert prepared["open_questions"] == []
    assert prepared["open_threads"] == []
    assert "谁负责 rollback drill？" not in prepared["agenda"]
    assert "谁负责 rollback drill？" not in prepared["expected_questions"]

    home = conversations.home_summary()
    assert home["open_questions"] == []
    assert home["next_focus"] is None

    summaries = conversations.list_space_summaries("")
    row = next(x for x in summaries if x["id"] == space["id"])
    assert row["open_questions_count"] == 0

    before_review = conversations.continue_summary(session["id"])
    assert before_review["open_questions"] == []
    assert [x["id"] for x in before_review["candidates"]] == [candidate["id"]]
    assert before_review["review_required"] == 1
    assert before_review["next_focus"] is None

    reviewed = conversations.review_item(candidate["id"], "CONFIRM")
    assert reviewed["review_status"] == "USER_CONFIRMED"

    prepared_after = conversations.prepare_space(space["id"])
    assert [x["id"] for x in prepared_after["open_questions"]] == [candidate["id"]]
    assert prepared_after["open_threads"]
    assert "谁负责 rollback drill？" in prepared_after["agenda"]

    home_after = conversations.home_summary()
    assert [x["id"] for x in home_after["open_questions"]] == [candidate["id"]]
    assert home_after["next_focus"]["kind"] == "OPEN_QUESTION"

    after_review = conversations.continue_summary(session["id"])
    assert [x["id"] for x in after_review["open_questions"]] == [candidate["id"]]
    assert after_review["candidates"] == []
    assert after_review["next_focus"]["kind"] == "OPEN_QUESTION"
    assert after_review["next_focus"]["source_ref"] == candidate["id"]


def test_conversation_history_is_profile_native_and_counted(product_env):
    space = conversations.create_space("History Space", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], title="Review #1", consent_ack=True)
    conversations.start_session(session["id"])
    decision = conversations.add_item(
        session["id"],
        item_type="Decision",
        title="采用方案 A",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "确认 A"}],
    )
    conversations.review_item(decision["id"], "CONFIRM")
    conversations.add_item(
        session["id"],
        item_type="OpenQuestion",
        title="谁负责 rollback？",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "待确认"}],
    )
    conversations.end_session(session["id"])

    history = conversations.conversation_history()
    assert history[0]["id"] == session["id"]
    assert history[0]["space_title"] == "History Space"
    assert history[0]["space_profile"] == "DESIGN_REVIEW"
    assert history[0]["decisions_count"] == 1
    assert history[0]["open_questions_count"] == 0
    assert history[0]["review_required"] == 1




def test_local_transcript_fails_closed_when_shared_stt_can_go_remote(product_env, monkeypatch):
    from core import config as core_config

    class Cfg:
        stt_provider = "whisper"
        doubao_stt_api_key = "configured"
        doubao_stt_access_token = ""
        candidate_stt_provider = "whisper"
        candidate_remote_stt_enabled = False

    monkeypatch.setattr(core_config, "get_config", lambda: Cfg())
    space = conversations.create_space("Private Local", "PROJECT_SYNC")
    session = conversations.create_session(
        space["id"],
        capture_mode="TRANSCRIPT",
        processing_mode="LOCAL",
        consent_ack=True,
    )
    check = conversations.preflight(session["id"])
    assert any(x["key"] == "processing_runtime" for x in check["blockers"])
    assert check["processing_runtime"]["main_audio_remote_possible"] is True
    with pytest.raises(ValueError, match="Local Processing"):
        conversations.start_session(session["id"])


def test_capture_rechecks_processing_policy_after_preflight(product_env, monkeypatch):
    from core import config as core_config

    class LocalCfg:
        stt_provider = "whisper"
        doubao_stt_api_key = ""
        doubao_stt_access_token = ""
        candidate_stt_provider = "whisper"
        candidate_remote_stt_enabled = False

    class RemoteCfg:
        stt_provider = "doubao"
        doubao_stt_api_key = "configured"
        doubao_stt_access_token = ""
        candidate_stt_provider = "whisper"
        candidate_remote_stt_enabled = False

    current = {"cfg": LocalCfg()}
    monkeypatch.setattr(core_config, "get_config", lambda: current["cfg"])
    space = conversations.create_space("Config Change", "PROJECT_SYNC")
    session = conversations.create_session(
        space["id"],
        capture_mode="TRANSCRIPT",
        processing_mode="LOCAL",
        consent_ack=True,
    )
    assert conversations.preflight(session["id"])["blockers"] == []
    conversations.start_session(session["id"])

    current["cfg"] = RemoteCfg()
    with pytest.raises(ValueError, match="Local Processing"):
        conversation_capture.start(session["id"], 1001)


def test_unwired_share_privacy_and_connector_permissions_block_preflight(product_env):
    space = conversations.create_space("Privacy Truth", "CLIENT_CALL")
    session = conversations.create_session(
        space["id"],
        consent_ack=True,
        policy={
            "share_privacy": "PRIVATE_OVERLAY",
            "connector_permissions": ["calendar.read"],
        },
    )
    check = conversations.preflight(session["id"])
    keys = {x["key"] for x in check["blockers"]}
    assert {"share_privacy_runtime", "connector_runtime"} <= keys
    item_state = {x["key"]: x["ok"] for x in check["items"]}
    assert item_state["share"] is False
    assert item_state["connectors"] is False


def test_processing_off_requires_no_transcript_and_ai_forbidden(product_env):
    space = conversations.create_space("Processing Off", "ONE_ON_ONE")
    blocked = conversations.create_session(
        space["id"],
        capture_mode="TRANSCRIPT",
        processing_mode="OFF",
        consent_ack=True,
        policy={"ai_assistance": "AI_ALLOWED"},
    )
    check = conversations.preflight(blocked["id"])
    assert any("Processing=OFF" in x["message"] for x in check["blockers"])

    safe = conversations.create_session(
        space["id"],
        capture_mode="NOTES_ONLY",
        processing_mode="OFF",
        consent_ack=True,
        policy={"ai_assistance": "AI_FORBIDDEN"},
    )
    assert conversations.preflight(safe["id"])["blockers"] == []




def test_decision_supersession_direction_preserves_old_truth_and_confirms_new(product_env):
    space = conversations.create_space("Decision Chain", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    refs = [{"kind": "USER_NOTE", "excerpt": "明确方案变化", "visibility": "PRIVATE"}]

    old = conversations.add_item(
        session["id"],
        item_type="Decision",
        title="采用方案 A",
        source_refs=refs,
        epistemic_status="OBSERVED",
    )
    old = conversations.review_item(old["id"], "CONFIRM")
    assert old["state"] == "AGREED"

    new = conversations.add_item(
        session["id"],
        item_type="Decision",
        title="采用方案 B",
        source_refs=refs,
        epistemic_status="OBSERVED",
    )
    replacement = conversations.review_item(
        new["id"],
        "SUPERSEDE",
        {"supersedes_id": old["id"]},
    )
    previous = conversations.require_item(old["id"])

    assert replacement["state"] == "AGREED"
    assert replacement["review_status"] == "USER_CONFIRMED"
    assert replacement["supersedes_id"] == old["id"]
    assert previous["state"] == "SUPERSEDED"
    assert previous["supersedes_id"] == ""
    assert conversations.require_item(old["id"])["title"] == "采用方案 A"


def test_decision_supersession_rejects_cross_space_self_and_unsourced_replacement(product_env):
    left = conversations.create_space("Left", "DESIGN_REVIEW")
    right = conversations.create_space("Right", "DESIGN_REVIEW")
    left_session = conversations.create_session(left["id"], consent_ack=True)
    right_session = conversations.create_session(right["id"], consent_ack=True)
    conversations.start_session(left_session["id"])
    conversations.start_session(right_session["id"])

    old = conversations.add_item(
        left_session["id"],
        item_type="Decision",
        title="Left A",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "A"}],
    )
    old = conversations.review_item(old["id"], "CONFIRM")

    cross = conversations.add_item(
        right_session["id"],
        item_type="Decision",
        title="Right B",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "B"}],
    )
    with pytest.raises(ValueError, match="同一 Conversation Space"):
        conversations.review_item(cross["id"], "SUPERSEDE", {"supersedes_id": old["id"]})

    unsourced = conversations.add_item(
        left_session["id"],
        item_type="Decision",
        title="Left B without source",
    )
    with pytest.raises(ValueError, match="需要来源"):
        conversations.review_item(unsourced["id"], "SUPERSEDE", {"supersedes_id": old["id"]})

    with pytest.raises(ValueError, match="不同的旧 Decision"):
        conversations.review_item(unsourced["id"], "SUPERSEDE", {"supersedes_id": unsourced["id"]})




def test_end_session_extracts_only_review_candidates_from_explicit_transcript_language(product_env):
    space = conversations.create_space("Extraction", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], capture_mode="TRANSCRIPT", consent_ack=True)
    conversations.start_session(session["id"])
    now = store.now()
    segments = [
        ("PRIMARY_AUDIO", "那我们决定采用方案 B。谁负责 rollback drill？主要风险是 migration window 太短。"),
        ("SELF_MIC", "我来补 rollout plan，周五前完成。"),
    ]
    for index, (channel, text_value) in enumerate(segments):
        store.insert("conversation_transcript_segment", {
            "id": f"cts_extract_{index}",
            "space_id": space["id"],
            "session_id": session["id"],
            "channel": channel,
            "text": text_value,
            "provider": "test",
            "source": "TEST",
            "is_final": True,
            "created_at": now + index,
        })

    summary = conversations.end_session(session["id"])
    candidates = summary["candidates"]
    kinds = {item["type"] for item in candidates}
    assert {"Decision", "OpenQuestion", "Risk", "Commitment", "Deadline"} <= kinds
    assert summary["decisions"] == []
    assert summary["commitments"] == []
    assert summary["next_focus"] is None

    for item in candidates:
        assert item["state"] == "PROPOSED"
        assert item["review_status"] == "AI_EXTRACTED"
        assert item["epistemic_status"] == "INFERRED"
        assert item["source_refs"][0]["kind"] == "TRANSCRIPT_SEGMENT"

    commitment = next(item for item in candidates if item["type"] == "Commitment")
    assert commitment["owner_id"] == "me"
    deadline = next(item for item in candidates if item["type"] == "Deadline")
    assert deadline["source_refs"]

    # Review is still the authority transition.
    decision = next(item for item in candidates if item["type"] == "Decision")
    confirmed = conversations.review_item(decision["id"], "CONFIRM")
    assert confirmed["state"] == "AGREED"


def test_transcript_candidate_extraction_is_idempotent_and_policy_gated(product_env):
    space = conversations.create_space("Extraction Gate", "PROJECT_SYNC")
    allowed = conversations.create_session(space["id"], capture_mode="TRANSCRIPT", consent_ack=True)
    conversations.start_session(allowed["id"])
    store.insert("conversation_transcript_segment", {
        "id": "cts_once",
        "space_id": space["id"],
        "session_id": allowed["id"],
        "channel": "PRIMARY_AUDIO",
        "text": "我们决定采用 v2。",
        "provider": "test",
        "source": "TEST",
        "is_final": True,
        "created_at": store.now(),
    })
    first = conversations.extract_transcript_candidates(allowed["id"])
    second = conversations.extract_transcript_candidates(allowed["id"])
    assert len(first) == 1
    assert second == []
    assert len(store.select("conversation_item", where="session_id = ?", params=(allowed["id"],))) == 1

    forbidden = conversations.create_session(
        space["id"],
        capture_mode="TRANSCRIPT",
        consent_ack=True,
        policy={"ai_assistance": "AI_FORBIDDEN"},
    )
    conversations.start_session(forbidden["id"])
    store.insert("conversation_transcript_segment", {
        "id": "cts_forbidden",
        "space_id": space["id"],
        "session_id": forbidden["id"],
        "channel": "PRIMARY_AUDIO",
        "text": "我们决定采用 v3。",
        "provider": "test",
        "source": "TEST",
        "is_final": True,
        "created_at": store.now(),
    })
    assert conversations.extract_transcript_candidates(forbidden["id"]) == []
    conversations.end_session(forbidden["id"])
    assert store.select("conversation_item", where="session_id = ?", params=(forbidden["id"],)) == []


def test_primary_audio_commitment_does_not_infer_owner(product_env):
    space = conversations.create_space("Unknown Speaker", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], capture_mode="TRANSCRIPT", consent_ack=True)
    conversations.start_session(session["id"])
    store.insert("conversation_transcript_segment", {
        "id": "cts_primary_commit",
        "space_id": space["id"],
        "session_id": session["id"],
        "channel": "PRIMARY_AUDIO",
        "text": "我来补 benchmark。",
        "provider": "test",
        "source": "TEST",
        "is_final": True,
        "created_at": store.now(),
    })
    extracted = conversations.extract_transcript_candidates(session["id"])
    commitment = next(item for item in extracted if item["type"] == "Commitment")
    assert commitment["owner_id"] == ""
    with pytest.raises(ValueError, match="owner"):
        conversations.review_item(commitment["id"], "CONFIRM")




def test_all_conversation_profiles_have_distinct_runtime_playbooks(product_env):
    profiles = [
        "PROJECT_SYNC", "DESIGN_REVIEW", "PRESENTATION_QA",
        "ONE_ON_ONE", "CLIENT_CALL", "NEGOTIATION",
    ]
    objectives = set()
    for profile in profiles:
        space = conversations.create_space(f"Space {profile}", profile)
        prepared = conversations.prepare_space(space["id"])
        playbook = prepared["profile_playbook"]
        assert playbook["profile"] == profile
        assert playbook["success_conditions"]
        assert playbook["priority_truth_types"]
        assert playbook["prepare_prompts"]
        assert playbook["closing_objective"]
        assert playbook["boundaries"]
        objectives.add(playbook["closing_objective"])
    assert len(objectives) == len(profiles)


def test_profile_playbook_is_frozen_in_session_pack(product_env, monkeypatch):
    space = conversations.create_space("Design Freeze", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True)
    started = conversations.start_session(session["id"])
    frozen = started["pack"]["payload"]["profile_playbook"]
    assert frozen["profile"] == "DESIGN_REVIEW"
    original_objective = frozen["closing_objective"]

    mutated = dict(conversations.SPACE_PROFILES["DESIGN_REVIEW"]["playbook"])
    mutated["closing_objective"] = "NEW TEMPLATE OBJECTIVE"
    mutated["priority_truth_types"] = ["Status"]
    monkeypatch.setitem(conversations.SPACE_PROFILES["DESIGN_REVIEW"], "playbook", mutated)

    assert conversations.prepare_space(space["id"])["profile_playbook"]["closing_objective"] == "NEW TEMPLATE OBJECTIVE"
    context = conversations.session_context(session["id"])
    assert context["profile_playbook"]["closing_objective"] == original_objective
    assert context["profile_playbook"]["closing_objective"] != "NEW TEMPLATE OBJECTIVE"

    # Reviewing the ended Session is judged against its frozen Playbook,
    # even if the current Space template has changed its priorities.
    outcome = conversations.end_session(session["id"])["profile_outcome"]
    assert outcome["closing_objective"] == original_objective
    assert outcome["priority_truth_types"] == frozen["priority_truth_types"]


def test_continue_profile_outcome_is_reviewed_evidence_not_success_score(product_env):
    space = conversations.create_space("Design Evidence", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])

    decision = conversations.add_item(
        session["id"],
        item_type="Decision",
        title="采用方案 B",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "明确选择 B"}],
    )
    conversations.review_item(decision["id"], "CONFIRM")

    risk = conversations.add_item(
        session["id"],
        item_type="Risk",
        title="回滚窗口不足",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "明确指出回滚窗口不足"}],
    )
    conversations.review_item(risk["id"], "CONFIRM")

    # Unreviewed proposal must not inflate reviewed Profile evidence.
    conversations.add_item(
        session["id"],
        item_type="Proposal",
        title="也许改成方案 C",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "只是提议"}],
    )

    summary = conversations.end_session(session["id"])
    outcome = summary["profile_outcome"]
    assert outcome["profile"] == "DESIGN_REVIEW"
    assert outcome["reviewed_counts"]["Decision"] == 1
    assert outcome["reviewed_counts"]["Risk"] == 1
    assert outcome["reviewed_counts"]["Proposal"] == 0
    assert "score" not in outcome
    assert "not a meeting-quality or success score" in outcome["interpretation"]


def test_model_extraction_cannot_assert_agreement_or_commitment(product_env):
    space = conversations.create_space("Review", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    src = [{"kind": "TRANSCRIPT_SEGMENT", "excerpt": "就这样"}]

    with pytest.raises(ValueError, match="AGREED"):
        conversations.add_item(
            session["id"], item_type="Decision", title="方案 A",
            state="AGREED", source_refs=src, review_status="AI_EXTRACTED",
        )
    with pytest.raises(ValueError, match="owner"):
        conversations.add_item(
            session["id"], item_type="Commitment", title="补 benchmark",
            state="COMMITTED", source_refs=src, review_status="USER_CONFIRMED",
        )




def test_reviewed_open_items_project_into_longitudinal_threads_and_resolve(product_env):
    space = conversations.create_space("Threads", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    source = [{"kind": "USER_NOTE", "excerpt": "明确提出 rollback owner 仍未知"}]

    question = conversations.add_item(
        session["id"],
        item_type="OpenQuestion",
        title="谁负责 rollback drill？",
        source_refs=source,
    )
    assert conversations.space_detail(space["id"])["threads"] == []

    confirmed = conversations.review_item(question["id"], "CONFIRM")
    assert confirmed["review_status"] == "USER_CONFIRMED"
    threads = conversations.space_detail(space["id"])["threads"]
    assert len(threads) == 1
    thread = threads[0]
    assert thread["kind"] == "OpenQuestion"
    assert thread["text"] == "谁负责 rollback drill？"
    assert thread["status"] == "OPEN"
    assert thread["source_refs"][0]["kind"] == "CONVERSATION_ITEM"
    assert thread["source_refs"][0]["id"] == question["id"]

    prepared = conversations.prepare_space(space["id"])
    assert prepared["open_threads"][0]["id"] == thread["id"]
    assert "谁负责 rollback drill？" in prepared["agenda"]

    resolved_thread = conversations.resolve_open_thread(thread["id"])
    assert resolved_thread["status"] == "RESOLVED"
    assert resolved_thread["resolved_at"] is not None
    assert conversations.require_item(question["id"])["state"] == "DONE"
    assert conversations.space_detail(space["id"])["threads"] == []


def test_rejected_candidate_never_becomes_longitudinal_thread(product_env):
    space = conversations.create_space("Rejected Thread", "CLIENT_CALL")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    risk = conversations.add_item(
        session["id"],
        item_type="Risk",
        title="可能延期",
        source_refs=[{"kind": "TRANSCRIPT_SEGMENT", "excerpt": "可能会晚"}],
    )
    conversations.review_item(risk["id"], "REJECT")
    assert conversations.space_detail(space["id"])["threads"] == []




def test_conversation_state_is_derived_from_session_items_threads_and_guidance(product_env):
    space = conversations.create_space("Derived State", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])

    question = conversations.add_item(
        session["id"],
        item_type="OpenQuestion",
        title="谁负责 rollback drill？",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "owner 未确认"}],
        epistemic_status="OBSERVED",
    )
    conversations.review_item(question["id"], "CONFIRM")

    state = conversations.conversation_state(session["id"])
    assert state["phase"] == "PARTICIPATE"
    assert state["current_topic"] == ""
    assert state["open_threads"][0]["text"] == "谁负责 rollback drill？"
    assert state["items"][0]["id"] == question["id"]

    result = conversations.evaluate_guidance(session["id"], {
        "current_topic": "rollback drill",
        "user_speaking": True,
        "candidate_text": "补充 owner",
        "source_refs": [{"kind": "USER_NOTE", "excerpt": "owner 未确认"}],
    })
    assert result["suppressed"] == "USER_SPEAKING"

    updated = conversations.conversation_state(session["id"])
    assert updated["current_topic"] == "rollback drill"
    assert updated["user_speaking"] is True
    assert updated["last_guidance_id"] == ""

    direct = conversations.evaluate_guidance(session["id"], {"direct_question": "谁负责？"})
    assert direct["guidance"] is not None
    after_direct = conversations.conversation_state(session["id"])
    assert after_direct["direct_question_pending"] is False
    assert after_direct["last_guidance_id"] == direct["guidance"]["id"]

    conversations.end_session(session["id"])
    assert conversations.conversation_state(session["id"])["phase"] == "CONTINUE"


def test_guidance_arbiter_prefers_direct_question_and_can_stay_silent(product_env):
    space = conversations.create_space("Design Review", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True, assistance_mode="BALANCED")
    conversations.start_session(session["id"])

    direct = conversations.evaluate_guidance(session["id"], {
        "direct_question": "为什么选 v2？",
        "candidate_text": "可以补 benchmark",
        "source_refs": [{"kind": "DOCUMENT", "id": "bench"}],
        "relevance": 1, "novelty": 1, "provenance_strength": 1, "decision_impact": 1,
    })
    assert direct["guidance"]["kind"] == "ANSWER_CUE"
    assert direct["guidance"]["reason"] == "DIRECT_QUESTION"

    silent = conversations.evaluate_guidance(session["id"], {
        "user_speaking": True,
        "candidate_text": "可以补 benchmark",
        "source_refs": [{"kind": "DOCUMENT", "id": "bench"}],
        "relevance": 1, "novelty": 1, "provenance_strength": 1,
    })
    assert silent["guidance"] is None
    assert silent["suppressed"] == "USER_SPEAKING"
    assert silent["event"]["expression_action"] == "SILENT"






def test_reviewed_open_question_projects_to_longitudinal_thread_and_resolve_closes_it(product_env):
    space = conversations.create_space("Thread Continuity", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])

    candidate = conversations.add_item(
        session["id"],
        item_type="OpenQuestion",
        title="谁负责 rollback drill？",
        source_refs=[{"kind": "TRANSCRIPT_SEGMENT", "id": "seg-1", "excerpt": "rollback drill owner 还没定"}],
        epistemic_status="OBSERVED",
        review_status="AI_EXTRACTED",
    )
    # Review-only extraction must not create persistent continuity by itself.
    assert conversations.space_detail(space["id"])["threads"] == []

    confirmed = conversations.review_item(candidate["id"], "CONFIRM")
    assert confirmed["review_status"] == "USER_CONFIRMED"
    threads = conversations.space_detail(space["id"])["threads"]
    assert len(threads) == 1
    assert threads[0]["kind"] == "OpenQuestion"
    assert threads[0]["text"] == "谁负责 rollback drill？"
    assert threads[0]["status"] == "OPEN"
    assert any(ref["kind"] == "CONVERSATION_ITEM" and ref["id"] == candidate["id"] for ref in threads[0]["source_refs"])

    prepared = conversations.prepare_space(space["id"])
    assert prepared["open_threads"][0]["id"] == threads[0]["id"]
    assert "谁负责 rollback drill？" in prepared["agenda"]

    resolved = conversations.review_item(candidate["id"], "RESOLVE")
    assert resolved["state"] == "DONE"
    assert conversations.space_detail(space["id"])["threads"] == []


def test_rejected_open_thread_candidate_never_enters_long_term_continuity(product_env):
    space = conversations.create_space("Rejected Thread", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    candidate = conversations.add_item(
        session["id"],
        item_type="Risk",
        title="可能破坏 rollback window",
        source_refs=[{"kind": "TRANSCRIPT_SEGMENT", "id": "seg-2", "excerpt": "只是猜测"}],
        review_status="AI_EXTRACTED",
    )
    rejected = conversations.review_item(candidate["id"], "REJECT")
    assert rejected["state"] == "UNKNOWN"
    assert rejected["review_status"] == "USER_REJECTED"
    assert conversations.space_detail(space["id"])["threads"] == []


def test_deadline_requires_provenance(product_env):
    space = conversations.create_space("Deadline Truth", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])

    with pytest.raises(ValueError, match="Deadline 必须带来源"):
        conversations.add_item(
            session["id"],
            item_type="Deadline",
            title="周五前上线",
        )

    deadline = conversations.add_item(
        session["id"],
        item_type="Deadline",
        title="周五前上线",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "明确说周五前"}],
    )
    assert deadline["type"] == "Deadline"
    assert deadline["source_refs"]





def test_deadline_time_semantics_stay_review_only_until_datetime_and_timezone_are_explicit(product_env):
    space = conversations.create_space("Temporal Truth", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    deadline = conversations.add_item(
        session["id"],
        item_type="Deadline",
        title="下周五前上线",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "下周五前上线"}],
        time_semantics={
            "original_text": "下周五前上线",
            "normalized_datetime": "",
            "timezone": "",
            "ambiguity": "AMBIGUOUS",
        },
    )
    assert deadline["time_semantics"]["original_text"] == "下周五前上线"
    assert deadline["time_semantics"]["ambiguity"] == "AMBIGUOUS"
    assert deadline["state"] == "PROPOSED"
    assert deadline["review_status"] == "AI_EXTRACTED"

    with pytest.raises(ValueError, match="时间仍有歧义"):
        conversations.review_item(deadline["id"], "CONFIRM")

    confirmed = conversations.review_item(deadline["id"], "CONFIRM", {
        "due_at": "2026-10-16T18:00",
        "time_semantics": {
            "original_text": "下周五前上线",
            "normalized_datetime": "2026-10-16T18:00",
            "timezone": "Asia/Shanghai",
            "ambiguity": "EXACT",
        },
    })
    assert confirmed["state"] == "COMMITTED"
    assert confirmed["review_status"] == "USER_CONFIRMED"
    assert confirmed["due_at"] == "2026-10-16T18:00"
    assert confirmed["time_semantics"] == {
        "original_text": "下周五前上线",
        "normalized_datetime": "2026-10-16T18:00",
        "timezone": "Asia/Shanghai",
        "ambiguity": "EXACT",
    }


def test_transcript_deadline_candidate_preserves_original_time_text_as_ambiguous(product_env):
    space = conversations.create_space("Transcript Temporal", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], capture_mode="TRANSCRIPT", consent_ack=True)
    conversations.start_session(session["id"])
    store.insert("conversation_transcript_segment", {
        "id": "cts_deadline_time",
        "space_id": space["id"],
        "session_id": session["id"],
        "channel": "PRIMARY_AUDIO",
        "text": "我们周五前完成 rollout。",
        "provider": "test",
        "source": "TEST",
        "is_final": True,
        "created_at": store.now(),
    })
    candidates = conversations.extract_transcript_candidates(session["id"])
    deadline = next(item for item in candidates if item["type"] == "Deadline")
    assert deadline["time_semantics"]["original_text"] == "我们周五前完成 rollout"
    assert deadline["time_semantics"]["normalized_datetime"] == ""
    assert deadline["time_semantics"]["timezone"] == ""
    assert deadline["time_semantics"]["ambiguity"] == "AMBIGUOUS"
    with pytest.raises(ValueError, match="时间仍有歧义"):
        conversations.review_item(deadline["id"], "CONFIRM")


def test_session_delete_removes_projected_open_thread_but_keeps_tombstone(product_env):
    space = conversations.create_space("Thread Delete Boundary", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    item = conversations.add_item(
        session["id"],
        item_type="OpenQuestion",
        title="谁负责 rollback drill？",
        source_refs=[{"kind": "TRANSCRIPT_SEGMENT", "id": "seg-thread-delete", "excerpt": "owner 还没定"}],
        epistemic_status="OBSERVED",
    )
    conversations.review_item(item["id"], "CONFIRM")
    threads = conversations.space_detail(space["id"])["threads"]
    assert len(threads) == 1
    thread_id = threads[0]["id"]

    conversations.end_session(session["id"])
    result = conversations.delete_session(session["id"], confirmed_policy="TOMBSTONE")
    assert result["provenance_tombstones"] == 1
    assert result["removed_open_thread_projections"] == 1
    assert store.get("conversation_open_thread", thread_id) is None
    assert conversations.space_detail(space["id"])["threads"] == []
    tomb = store.select(
        "conversation_provenance_tombstone",
        where="original_item_id = ?",
        params=(item["id"],),
    )
    assert tomb and tomb[0]["title"] == "谁负责 rollback drill？"


def test_started_session_keeps_frozen_open_thread_after_space_thread_is_resolved(product_env):
    space = conversations.create_space("Frozen Thread Pack", "DESIGN_REVIEW")
    prior = conversations.create_session(space["id"], title="Prior review", consent_ack=True)
    conversations.start_session(prior["id"])
    item = conversations.add_item(
        prior["id"],
        item_type="Risk",
        title="rollback drill 还没有 owner",
        source_refs=[{"kind": "TRANSCRIPT_SEGMENT", "id": "seg-thread-pack", "excerpt": "owner unresolved"}],
        epistemic_status="OBSERVED",
    )
    conversations.review_item(item["id"], "CONFIRM")
    conversations.end_session(prior["id"])

    current = conversations.create_session(space["id"], title="Current review", consent_ack=True)
    started = conversations.start_session(current["id"])
    frozen_threads = started["pack"]["payload"]["session_brief"]["open_threads"]
    assert len(frozen_threads) == 1
    assert frozen_threads[0]["text"] == "rollback drill 还没有 owner"
    assert frozen_threads[0]["source_refs"]
    assert started["session"]["state"]["open_threads"] == [frozen_threads[0]["id"]]

    context_before = conversations.session_context(current["id"])
    assert context_before["brief"]["open_threads"][0]["id"] == frozen_threads[0]["id"]

    conversations.review_item(item["id"], "RESOLVE")
    assert conversations.space_detail(space["id"])["threads"] == []

    # The active Session remains a historical snapshot of what was known/open
    # when it started; resolving the Space thread cannot rewrite this Pack.
    context_after = conversations.session_context(current["id"])
    assert context_after["brief"]["open_threads"] == frozen_threads



def test_guidance_arbiter_critical_risk_visibility_duplicate_social_and_budget(product_env):
    space = conversations.create_space("Arbiter", "DESIGN_REVIEW")

    # Critical risk outranks user-speaking suppression when it has allowed provenance.
    risk_session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(risk_session["id"])
    risk = conversations.evaluate_guidance(risk_session["id"], {
        "critical_risk": "当前承诺会破坏 rollback window",
        "candidate_text": "普通补充",
        "user_speaking": True,
        "source_refs": [{"kind": "DOCUMENT", "id": "risk", "visibility": "PRIVATE"}],
    })
    assert risk["guidance"]["kind"] == "RISK"
    assert risk["guidance"]["reason"] == "CRITICAL_RISK"

    blocked_session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(blocked_session["id"])
    blocked = conversations.evaluate_guidance(blocked_session["id"], {
        "candidate_text": "只在隐藏来源里的信息",
        "source_refs": [{"kind": "DOCUMENT", "id": "hidden", "visibility": "NO_GUIDANCE"}],
        "relevance": 1, "novelty": 1, "provenance_strength": 1,
    })
    assert blocked["suppressed"] == "SOURCE_VISIBILITY_BLOCKED"

    social_session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(social_session["id"])
    social = conversations.evaluate_guidance(social_session["id"], {
        "candidate_text": "此刻不适合主动打断",
        "source_refs": [{"kind": "USER_NOTE", "excerpt": "context"}],
        "relevance": 1, "novelty": 1, "provenance_strength": 1,
        "social_risk": 2,
    })
    assert social["suppressed"] == "SOCIAL_RISK"

    dup_session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(dup_session["id"])
    body = {
        "candidate_text": "Q4 benchmark 证明 10x scale",
        "source_refs": [{"kind": "DOCUMENT", "id": "bench"}],
        "relevance": 1, "novelty": 1, "provenance_strength": 1,
    }
    first = conversations.evaluate_guidance(dup_session["id"], body)
    assert first["guidance"] is not None
    duplicate = conversations.evaluate_guidance(dup_session["id"], body)
    assert duplicate["suppressed"] == "DUPLICATE_GUIDANCE"

    budget_session = conversations.create_session(space["id"], consent_ack=True, assistance_mode="BALANCED")
    conversations.start_session(budget_session["id"])
    for index in range(3):
        shown = conversations.evaluate_guidance(budget_session["id"], {
            "candidate_text": f"独立建议 {index}",
            "source_refs": [{"kind": "DOCUMENT", "id": f"src-{index}"}],
            "relevance": 1, "novelty": 1, "provenance_strength": 1,
        })
        assert shown["guidance"] is not None
    exhausted = conversations.evaluate_guidance(budget_session["id"], {
        "candidate_text": "第四条独立建议",
        "source_refs": [{"kind": "DOCUMENT", "id": "src-4"}],
        "relevance": 1, "novelty": 1, "provenance_strength": 1,
    })
    assert exhausted["suppressed"] == "SUGGESTION_BUDGET"


def test_direct_question_cancels_stale_opportunity(product_env):
    space = conversations.create_space("Priority", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    opportunity = conversations.evaluate_guidance(session["id"], {
        "candidate_text": "先补充 benchmark",
        "source_refs": [{"kind": "DOCUMENT", "id": "bench"}],
        "relevance": 1, "novelty": 1, "provenance_strength": 1,
    })["guidance"]
    assert opportunity

    direct = conversations.evaluate_guidance(session["id"], {"direct_question": "为什么？"})
    assert direct["guidance"]["kind"] == "ANSWER_CUE"
    stored = conversations.guidance_history(session["id"], 10)
    old = next(x for x in stored if x["id"] == opportunity["id"])
    assert old["user_action"] == "CANCELLED_BY_DIRECT_QUESTION"




def test_proactive_recall_and_open_question_require_allowed_source_visibility(product_env):
    space = conversations.create_space("Visibility", "PROJECT_SYNC")

    prior = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(prior["id"])
    hidden = conversations.add_item(
        prior["id"],
        item_type="Decision",
        title="hidden migration fact",
        source_refs=[{"kind": "DOCUMENT", "id": "secret", "visibility": "NO_GUIDANCE"}],
    )
    conversations.review_item(hidden["id"], "CONFIRM")
    conversations.end_session(prior["id"])

    live = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(live["id"])
    result = conversations.evaluate_guidance(live["id"], {"current_topic": "hidden migration"})
    assert result["guidance"] is None

    open_item = conversations.add_item(
        live["id"],
        item_type="OpenQuestion",
        title="hidden owner question",
        source_refs=[{"kind": "DOCUMENT", "id": "secret-q", "visibility": "HIDDEN"}],
    )
    assert open_item["review_status"] == "AI_EXTRACTED"
    result2 = conversations.evaluate_guidance(live["id"], {"current_topic": "unrelated"})
    assert result2["guidance"] is None




def test_transcript_direct_question_is_first_class_even_in_quiet_and_self_mic_never_interrupts(product_env):
    space = conversations.create_space("Quiet Questions", "PROJECT_SYNC")
    prior = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(prior["id"])
    decision = conversations.add_item(
        prior["id"],
        item_type="Decision",
        title="offline migration 采用 v2",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "明确采用 v2", "visibility": "PRIVATE"}],
    )
    conversations.review_item(decision["id"], "CONFIRM")
    conversations.end_session(prior["id"])

    live = conversations.create_session(space["id"], consent_ack=True, assistance_mode="QUIET")
    conversations.start_session(live["id"])
    cue = conversations.guidance_from_transcript(
        live["id"],
        "为什么之前选择 offline migration v2？",
        channel="PRIMARY_AUDIO",
    )
    assert cue is not None
    assert cue["kind"] == "ANSWER_CUE"
    assert cue["reason"] == "TRANSCRIPT_DIRECT_QUESTION"
    assert "已确认历史" in cue["text"]
    assert cue["source_refs"]

    self_mic = conversations.guidance_from_transcript(
        live["id"],
        "为什么之前选择 offline migration v2？",
        channel="SELF_MIC",
    )
    assert self_mic is None


def test_transcript_can_surface_frozen_source_as_contribution_opportunity_without_promoting_notes(product_env):
    material = materials.create_material(
        "Q4 Benchmark",
        kind="PROJECT",
        usage="FACTS",
        text=("Q4 benchmark validated offline migration at 10x data scale with repeatable results. " * 3),
    )
    from services.product import quick_notes
    note = quick_notes.create_note("Q4 benchmark 只是提醒，不是证据。", title="Private reminder")
    space = conversations.create_space(
        "Source Opportunity",
        "DESIGN_REVIEW",
        selected_source_ids=[material["id"]],
        selected_quick_note_ids=[note["id"]],
    )
    live = conversations.create_session(space["id"], consent_ack=True, assistance_mode="BALANCED")
    conversations.start_session(live["id"])

    opportunity = conversations.guidance_from_transcript(
        live["id"],
        "现在讨论 Q4 benchmark data scale",
        channel="PRIMARY_AUDIO",
    )
    assert opportunity is not None
    assert opportunity["kind"] == "CONTRIBUTION_OPPORTUNITY"
    assert opportunity["reason"] == "TRANSCRIPT_SOURCE_OPPORTUNITY"
    assert opportunity["source_refs"][0]["version_id"]

    # A Quick Note remains queryable manually but is not eligible for automatic
    # proactive promotion.
    note_only_space = conversations.create_space(
        "Notes Only",
        "DESIGN_REVIEW",
        selected_quick_note_ids=[note["id"]],
    )
    note_session = conversations.create_session(note_only_space["id"], consent_ack=True)
    conversations.start_session(note_session["id"])
    assert conversations.guidance_from_transcript(
        note_session["id"],
        "Q4 benchmark 只是提醒",
        channel="PRIMARY_AUDIO",
    ) is None


def test_transcript_recall_obeys_visibility_and_suggestion_budget(product_env):
    space = conversations.create_space("Transcript Guard", "PROJECT_SYNC")
    prior = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(prior["id"])

    allowed = conversations.add_item(
        prior["id"],
        item_type="Decision",
        title="allowed architecture decision",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "明确决定", "visibility": "PRIVATE"}],
    )
    conversations.review_item(allowed["id"], "CONFIRM")
    hidden = conversations.add_item(
        prior["id"],
        item_type="Decision",
        title="hidden pricing decision",
        source_refs=[{"kind": "DOCUMENT", "id": "hidden", "visibility": "NO_GUIDANCE"}],
    )
    conversations.review_item(hidden["id"], "CONFIRM")
    conversations.end_session(prior["id"])

    live = conversations.create_session(space["id"], consent_ack=True, assistance_mode="BALANCED")
    conversations.start_session(live["id"])
    assert conversations.guidance_from_transcript(live["id"], "hidden pricing") is None

    # Fill the Balanced proactive budget with three distinct manual opportunities.
    for i in range(3):
        shown = conversations.evaluate_guidance(live["id"], {
            "candidate_text": f"budget item {i}",
            "source_refs": [{"kind": "DOCUMENT", "id": f"b-{i}", "visibility": "PRIVATE"}],
            "relevance": 1, "novelty": 1, "provenance_strength": 1,
        })
        assert shown["guidance"] is not None
    assert conversations.guidance_from_transcript(live["id"], "allowed architecture") is None


def test_frozen_pack_records_resolved_processing_route(product_env, monkeypatch):
    from core import config as core_config

    class Cfg:
        stt_provider = "whisper"
        doubao_stt_api_key = ""
        doubao_stt_access_token = ""
        candidate_stt_provider = "whisper"
        candidate_remote_stt_enabled = False

    monkeypatch.setattr(core_config, "get_config", lambda: Cfg())
    space = conversations.create_space("Pack Privacy", "PROJECT_SYNC")
    session = conversations.create_session(
        space["id"],
        capture_mode="TRANSCRIPT",
        processing_mode="LOCAL",
        consent_ack=True,
    )
    started = conversations.start_session(session["id"])
    runtime = started["pack"]["payload"]["processing_runtime"]
    assert runtime["mode"] == "LOCAL"
    assert runtime["configured_stt_provider"] == "whisper"
    assert runtime["main_audio_remote_possible"] is False
    assert runtime["data_path"] == {
        "capture": "LOCAL_DEVICE_CAPTURE",
        "stt": "LOCAL_ONLY",
        "inference": "LOCAL_DETERMINISTIC",
        "retention": "LOCAL_PRODUCT_DB",
        "writeback": "LOCAL_REVIEWED_DRAFT_ONLY",
        "audio_retention": "OFF",
        "transcript_retention": "SPACE_POLICY",
    }
    assert runtime["blockers"] == []






def test_resolved_data_path_distinguishes_no_capture_and_writeback_off(product_env, monkeypatch):
    from core import config as core_config

    class Cfg:
        stt_provider = "doubao"
        doubao_stt_api_key = "configured"
        doubao_stt_access_token = ""
        candidate_stt_provider = "doubao"
        candidate_remote_stt_enabled = True

    monkeypatch.setattr(core_config, "get_config", lambda: Cfg())
    space = conversations.create_space("No Capture", "PROJECT_SYNC")
    session = conversations.create_session(
        space["id"],
        capture_mode="NO_CAPTURE",
        processing_mode="LOCAL",
        consent_ack=True,
        policy={"external_writeback": "OFF"},
    )
    runtime = conversations.processing_runtime_status(session)
    assert runtime["blockers"] == []
    assert runtime["data_path"]["capture"] == "NO_CAPTURE"
    assert runtime["data_path"]["stt"] == "NOT_USED"
    assert runtime["data_path"]["inference"] == "LOCAL_DETERMINISTIC"
    assert runtime["data_path"]["retention"] == "LOCAL_PRODUCT_DB"
    assert runtime["data_path"]["writeback"] == "DISABLED"


def test_profile_aware_guidance_taxonomy_and_expression_delivery(product_env, monkeypatch):
    monkeypatch.setattr(
        conversations.intelligence_store,
        "get_voice_profile",
        lambda owner: {
            "profile": {
                "explicit_preferences": {
                    "conclusion_first": True,
                    "target_seconds": 45,
                    "shape": "bullet",
                }
            }
        },
    )
    src = [{"kind": "DOCUMENT", "id": "bench", "visibility": "PRIVATE"}]

    presentation_space = conversations.create_space("Demo", "PRESENTATION_QA")
    presentation = conversations.create_session(
        presentation_space["id"],
        consent_ack=True,
        assistance_mode="PRESENTATION",
    )
    conversations.start_session(presentation["id"])

    blocked = conversations.evaluate_guidance(presentation["id"], {
        "candidate_text": "主动补充一个销售式机会点",
        "source_refs": src,
        "relevance": 1, "novelty": 1, "provenance_strength": 1,
        "goal_relevance": 1, "decision_impact": 1,
    })
    assert blocked["guidance"] is None
    assert blocked["suppressed"] == "PROFILE_GUIDANCE_NOT_ALLOWED"

    delivery = conversations.evaluate_guidance(presentation["id"], {
        "delivery_focus": "回答 CTO 的 rollback concern",
        "audience_role": "CTO",
        "audience_concern": "rollback 风险",
    })
    assert delivery["guidance"]["kind"] == "DELIVERY"
    assert delivery["guidance"]["reason"] == "EXPRESSION_PLANNER"
    assert "先给结论" in delivery["guidance"]["text"]
    assert "45 秒" in delivery["guidance"]["text"]
    assert "CTO" in delivery["guidance"]["text"]
    assert "rollback 风险" in delivery["guidance"]["text"]
    assert delivery["guidance"]["source_refs"] == []

    one_on_one_space = conversations.create_space("1:1", "ONE_ON_ONE")
    one_on_one = conversations.create_session(
        one_on_one_space["id"],
        consent_ack=True,
        assistance_mode="ONE_ON_ONE",
    )
    conversations.start_session(one_on_one["id"])
    tp = conversations.evaluate_guidance(one_on_one["id"], {
        "candidate_text": "补充已经确认的下周行动项",
        "source_refs": src,
        "relevance": 1, "novelty": 1, "provenance_strength": 1,
        "goal_relevance": 1, "decision_impact": 1,
    })
    assert tp["guidance"]["kind"] == "TALKING_POINT"
    assert tp["guidance"]["reason"] == "HIGH_VALUE_TALKING_POINT"

    direct = conversations.evaluate_guidance(presentation["id"], {
        "direct_question": "为什么？",
    })
    assert direct["guidance"]["kind"] == "ANSWER_CUE"


def test_explicit_talking_point_requires_profile_permission_and_source(product_env):
    presentation_space = conversations.create_space("Demo", "PRESENTATION_QA")
    presentation = conversations.create_session(presentation_space["id"], consent_ack=True)
    conversations.start_session(presentation["id"])
    blocked = conversations.evaluate_guidance(presentation["id"], {
        "talking_point": "这里补充一个未经允许的 talking point",
        "source_refs": [{"kind": "DOCUMENT", "id": "src", "visibility": "PRIVATE"}],
    })
    assert blocked["suppressed"] == "PROFILE_GUIDANCE_NOT_ALLOWED"

    review_space = conversations.create_space("Review", "DESIGN_REVIEW")
    review = conversations.create_session(review_space["id"], consent_ack=True)
    conversations.start_session(review["id"])
    no_source = conversations.evaluate_guidance(review["id"], {
        "talking_point": "这个要点没有来源",
    })
    assert no_source["suppressed"] == "TALKING_POINT_WITHOUT_ALLOWED_SOURCE"

    shown = conversations.evaluate_guidance(review["id"], {
        "talking_point": "Q4 benchmark 已证明 10x data scale",
        "source_refs": [{"kind": "DOCUMENT", "id": "bench", "visibility": "PRIVATE"}],
    })
    assert shown["guidance"]["kind"] == "TALKING_POINT"
    assert shown["guidance"]["expression_action"] == "ADD_TALKING_POINT"


def test_direct_question_cancels_stale_proactive_talking_point(product_env):
    space = conversations.create_space("1:1", "ONE_ON_ONE")
    session = conversations.create_session(space["id"], consent_ack=True, assistance_mode="ONE_ON_ONE")
    conversations.start_session(session["id"])
    shown = conversations.evaluate_guidance(session["id"], {
        "candidate_text": "补充明确行动项",
        "source_refs": [{"kind": "DOCUMENT", "id": "task", "visibility": "PRIVATE"}],
        "relevance": 1, "novelty": 1, "provenance_strength": 1,
        "goal_relevance": 1, "decision_impact": 1,
    })["guidance"]
    assert shown["kind"] == "TALKING_POINT"

    direct = conversations.evaluate_guidance(session["id"], {"direct_question": "下一步是什么？"})
    assert direct["guidance"]["kind"] == "ANSWER_CUE"
    history = conversations.guidance_history(session["id"], 20)
    old = next(x for x in history if x["id"] == shown["id"])
    assert old["user_action"] == "CANCELLED_BY_DIRECT_QUESTION"




def test_unreviewed_open_question_never_becomes_proactive_cross_session_guidance(product_env):
    space = conversations.create_space("Review Boundary", "PROJECT_SYNC")
    prior = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(prior["id"])
    candidate = conversations.add_item(
        prior["id"],
        item_type="OpenQuestion",
        title="AI 只是猜测 rollback owner 未明确",
        source_refs=[{"kind": "TRANSCRIPT_SEGMENT", "id": "seg-unreviewed", "excerpt": "可能还没定"}],
        epistemic_status="INFERRED",
        review_status="AI_EXTRACTED",
    )
    conversations.end_session(prior["id"])

    current = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(current["id"])
    result = conversations.evaluate_guidance(current["id"], {})
    assert result["guidance"] is None
    assert result["suppressed"] == "NO_HIGH_VALUE_GUIDANCE"

    # The candidate still exists for review/history of the source session, but
    # it did not become long-term proactive truth.
    assert conversations.require_item(candidate["id"])["review_status"] == "AI_EXTRACTED"
    assert conversations.space_detail(space["id"])["threads"] == []


def test_client_call_does_not_enable_unlisted_talking_point_or_delivery_lanes(product_env):
    space = conversations.create_space("Client", "CLIENT_CALL")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    src = [{"kind": "DOCUMENT", "id": "client-brief", "visibility": "PRIVATE"}]

    talking = conversations.evaluate_guidance(session["id"], {
        "talking_point": "主动销售式 talking point",
        "source_refs": src,
    })
    assert talking["guidance"] is None
    assert talking["suppressed"] == "PROFILE_GUIDANCE_NOT_ALLOWED"

    delivery = conversations.evaluate_guidance(session["id"], {
        "delivery_focus": "把回答改成演示模式",
    })
    assert delivery["guidance"] is None
    assert delivery["suppressed"] == "PROFILE_GUIDANCE_NOT_ALLOWED"

    opportunity = conversations.evaluate_guidance(session["id"], {
        "candidate_text": "客户明确 concern 与 benchmark 之间有一个可补充事实",
        "source_refs": src,
        "relevance": 1,
        "novelty": 1,
        "provenance_strength": 1,
        "goal_relevance": 1,
        "decision_impact": 1,
    })
    assert opportunity["guidance"]["kind"] == "CONTRIBUTION_OPPORTUNITY"


def test_opportunity_needs_source_and_threshold(product_env):
    space = conversations.create_space("Sync", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True, assistance_mode="BALANCED")
    conversations.start_session(session["id"])

    no_source = conversations.evaluate_guidance(session["id"], {
        "candidate_text": "Q4 benchmark 已覆盖 10x data scale",
        "relevance": 1, "novelty": 1, "provenance_strength": 1,
    })
    assert no_source["suppressed"] == "NO_SOURCE"

    shown = conversations.evaluate_guidance(session["id"], {
        "candidate_text": "Q4 benchmark 已覆盖 10x data scale",
        "source_refs": [{"kind": "DOCUMENT", "id": "benchmark", "excerpt": "10x data scale"}],
        "relevance": 1,
        "novelty": 1,
        "provenance_strength": 1,
        "role_relevance": 0.5,
        "goal_relevance": 0.5,
        "decision_impact": 1,
    })
    assert shown["guidance"]["kind"] == "CONTRIBUTION_OPPORTUNITY"
    assert shown["guidance"]["score"]["value"] >= 2.5


def test_delete_space_cascades_conversation_runtime_only(product_env):
    space = conversations.create_space("Temp", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    conversations.add_item(
        session["id"], item_type="OpenQuestion", title="rollback owner 是谁？",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "待确认"}],
    )
    with pytest.raises(ValueError, match="明确确认"):
        conversations.delete_space(space["id"])
    assert conversations.delete_space(space["id"], confirm=True) is True
    assert store.get("conversation_session", session["id"]) is None
    assert store.select("goal") == []  # v1 Interview store remains independent


def test_source_aware_ask_does_not_promote_unconfirmed_items(product_env):
    space = conversations.create_space("Architecture", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    source = [{"kind": "USER_NOTE", "excerpt": "offline sync v2 uses conflict merge"}]
    proposed = conversations.add_item(
        session["id"], item_type="Decision", title="采用 offline sync v2",
        source_refs=source, source_excerpt="offline sync v2 uses conflict merge",
        epistemic_status="OBSERVED",
    )
    before = conversations.ask(session["id"], "offline sync v2")
    assert before["grounded"] is False
    conversations.review_item(proposed["id"], "CONFIRM")
    after = conversations.ask(session["id"], "offline sync v2")
    assert after["grounded"] is True
    assert after["matches"][0]["id"] == proposed["id"]






def test_session_context_is_minimal_and_frozen_at_start(product_env):
    material = materials.create_material(
        "Architecture Brief",
        kind="PROJECT",
        usage="FACTS",
        text=("Architecture source says rollback owner is unresolved and offline migration uses v2. " * 3),
    )
    space = conversations.create_space(
        "Architecture",
        "DESIGN_REVIEW",
        default_goal="决定 conflict merge strategy",
        selected_source_ids=[material["id"]],
    )

    prior = conversations.create_session(space["id"], title="Prior", consent_ack=True)
    conversations.start_session(prior["id"])
    prior_question = conversations.add_item(
        prior["id"],
        item_type="OpenQuestion",
        title="确认 rollback owner",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "owner 仍未确认"}],
    )
    conversations.review_item(prior_question["id"], "CONFIRM")
    conversations.end_session(prior["id"])

    live = conversations.create_session(space["id"], title="Live", consent_ack=True)
    started = conversations.start_session(live["id"])
    digest = started["pack"]["digest"]
    frozen_version = started["pack"]["payload"]["sources"][0]["version_id"]

    context = conversations.session_context(live["id"])
    assert context["brief"]["goal"] == "决定 conflict merge strategy"
    assert "确认 rollback owner" in context["brief"]["agenda"]
    assert context["pack_digest"] == digest
    assert context["sources"][0]["version_id"] == frozen_version
    assert "text" not in context["sources"][0]

    # Mutate the Space and source after start; the Live read model stays pinned
    # to the frozen Session Pack.
    conversations.update_space(space["id"], {"default_goal": "新目标不应进入旧会话"})
    materials.replace_material(
        material["id"],
        text=("Replacement source says a completely different architecture and owner. " * 3),
    )
    later = conversations.session_context(live["id"])
    assert later["brief"]["goal"] == "决定 conflict merge strategy"
    assert later["sources"][0]["version_id"] == frozen_version
    assert later["pack_digest"] == digest


def test_manual_ask_uses_frozen_ready_sources_not_latest_material(product_env):
    material = materials.create_material(
        "Q4 Benchmark",
        kind="PROJECT",
        usage="FACTS",
        text="Q4 benchmark: offline migration was validated at 10x data scale. rollback owner remained open.",
    )
    space = conversations.create_space(
        "Architecture",
        "DESIGN_REVIEW",
        selected_source_ids=[material["id"]],
    )
    session = conversations.create_session(space["id"], consent_ack=True)
    started = conversations.start_session(session["id"])
    frozen = started["pack"]["payload"]["sources"][0]
    frozen_version = frozen["version_id"]

    first = conversations.ask(session["id"], "10x data scale")
    assert first["grounded"] is True
    assert first["truth_confirmed"] is False
    assert first["matches"][0]["kind"] == "FROZEN_SOURCE"
    assert first["matches"][0]["authority"] == "PERSONAL_EVIDENCE"
    assert first["matches"][0]["source_refs"][0]["version_id"] == frozen_version

    materials.replace_material(
        material["id"],
        text="Replacement says 50x data scale and removes the old 10x wording.",
    )
    # The active material changed, but this already-started session still reads
    # the frozen v1 source text.
    still_frozen = conversations.ask(session["id"], "10x data scale")
    assert still_frozen["grounded"] is True
    assert still_frozen["matches"][0]["source_refs"][0]["version_id"] == frozen_version

    not_silently_refreshed = conversations.ask(session["id"], "50x data scale")
    assert not_silently_refreshed["grounded"] is False


def test_manual_ask_labels_quick_note_and_transcript_without_promoting_truth(product_env):
    from services.product import quick_notes

    note = quick_notes.create_note(
        "先确认 rollback owner，再讨论发布窗口。",
        title="Review reminder",
    )
    space = conversations.create_space(
        "Architecture",
        "DESIGN_REVIEW",
        selected_quick_note_ids=[note["id"]],
    )
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])

    note_result = conversations.ask(session["id"], "rollback owner")
    assert note_result["grounded"] is True
    assert note_result["truth_confirmed"] is False
    assert note_result["matches"][0]["kind"] == "QUICK_NOTE"
    assert note_result["matches"][0]["authority"] == "USER_NOTE_NOT_EVIDENCE"

    store.insert("conversation_transcript_segment", {
        "id": store.new_id("cts_"),
        "space_id": space["id"],
        "session_id": session["id"],
        "channel": "PRIMARY_AUDIO",
        "text": "刚才 Alex 提到发布时间可能是周五，但还没有形成确认。",
        "provider": "test",
        "source": "TEST",
        "is_final": True,
        "created_at": store.now(),
    })
    transcript_result = conversations.ask(session["id"], "发布时间 周五")
    assert transcript_result["grounded"] is True
    assert transcript_result["truth_confirmed"] is False
    assert transcript_result["matches"][0]["kind"] == "TRANSCRIPT_SEGMENT"
    assert transcript_result["matches"][0]["authority"] == "OBSERVED_NOT_CONFIRMED"


def test_topic_recall_and_live_mode_update(product_env):
    space = conversations.create_space("Architecture", "DESIGN_REVIEW")
    s1 = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(s1["id"])
    item = conversations.add_item(
        s1["id"], item_type="Decision", title="offline migration 采用 v2",
        source_refs=[{"kind": "TRANSCRIPT_SEGMENT", "excerpt": "offline migration 用 v2"}],
        epistemic_status="OBSERVED",
    )
    conversations.review_item(item["id"], "CONFIRM")
    conversations.end_session(s1["id"])

    s2 = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(s2["id"])
    shown = conversations.evaluate_guidance(s2["id"], {"current_topic": "offline migration"})
    assert shown["guidance"]["kind"] == "RECALL"
    assert shown["guidance"]["reason"] == "TOPIC_RECALL"

    updated = conversations.update_session(s2["id"], {"assistance_mode": "QUIET"})
    assert updated["assistance_mode"] == "QUIET"
    quiet = conversations.evaluate_guidance(s2["id"], {"current_topic": "offline migration"})
    assert quiet["guidance"] is None


@pytest.mark.parametrize("profile", [
    "PROJECT_SYNC", "DESIGN_REVIEW", "PRESENTATION_QA",
    "ONE_ON_ONE", "CLIENT_CALL", "NEGOTIATION",
])
def test_all_profile_templates_share_one_runtime_without_cross_space_leak(product_env, profile):
    space = conversations.create_space(f"{profile} Space", profile)
    first = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(first["id"])
    item = conversations.add_item(
        first["id"], item_type="OpenQuestion", title=f"{profile} unresolved",
        source_refs=[{"kind": "USER_NOTE", "excerpt": profile}],
        epistemic_status="OBSERVED",
    )
    assert item["space_id"] == space["id"]
    conversations.review_item(item["id"], "CONFIRM")
    conversations.end_session(first["id"])

    second = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(second["id"])
    result = conversations.evaluate_guidance(second["id"], {})
    # Only reviewed continuity is eligible. Quiet negotiation may still stay
    # silent because its default suggestion budget is zero; all other profiles
    # can surface the reviewed unresolved question through the shared runtime.
    if conversations.require_space(space["id"])["default_mode"] == "QUIET":
        assert result["guidance"] is None
    else:
        assert result["guidance"]["kind"] == "QUESTION"

    detail = conversations.space_detail(space["id"])
    assert all(row["space_id"] == space["id"] for row in detail["open_questions"])


def test_thirty_session_continuity_stays_bounded_and_traceable(product_env):
    space = conversations.create_space("Long-running project", "PROJECT_SYNC")
    for index in range(30):
        session = conversations.create_session(space["id"], title=f"Sync {index}", consent_ack=True)
        conversations.start_session(session["id"])
        if index % 5 == 0:
            item = conversations.add_item(
                session["id"], item_type="Decision", title=f"Decision {index}",
                source_refs=[{"kind": "TRANSCRIPT_SEGMENT", "excerpt": f"decide {index}"}],
                epistemic_status="OBSERVED",
            )
            conversations.review_item(item["id"], "CONFIRM")
        conversations.end_session(session["id"])

    detail = conversations.space_detail(space["id"])
    assert len(detail["sessions"]) == 30
    assert len([x for x in detail["decisions"] if x["state"] == "AGREED"]) == 6
    latest = conversations.create_session(space["id"], title="Sync 30", consent_ack=True)
    pack = conversations.start_session(latest["id"])["pack"]
    assert len(pack["payload"]["confirmed_items"]) == 6
    assert all(row["source_refs"] for row in pack["payload"]["confirmed_items"])




def test_preflight_warns_and_skips_selected_source_that_is_not_ready(product_env):
    broken = materials.create_material(
        "Broken Source",
        kind="PROJECT",
        usage="FACTS",
        text="x",
    )
    assert broken["lifecycle"]["state"] == "FAILED"
    space = conversations.create_space(
        "Architecture",
        "DESIGN_REVIEW",
        selected_source_ids=[broken["id"]],
    )
    session = conversations.create_session(space["id"], consent_ack=True)
    check = conversations.preflight(session["id"])

    assert check["blockers"] == []
    assert any(w["key"] == "source_not_ready" for w in check["warnings"])
    source_item = next(x for x in check["items"] if x["key"] == "sources")
    assert source_item["ok"] is False
    assert source_item["value"] == "0/1 Ready"
    assert check["pack_preview"]["sources"] == []
    assert check["pack_preview"]["skipped_sources"][0]["id"] == broken["id"]

    started = conversations.start_session(session["id"])
    assert started["pack"]["payload"]["sources"] == []
    assert started["pack"]["payload"]["skipped_sources"][0]["id"] == broken["id"]


def test_transcript_preflight_surfaces_unrecorded_participant_consent_as_warning(product_env):
    space = conversations.create_space("Consent State", "PROJECT_SYNC")
    session = conversations.create_session(
        space["id"],
        capture_mode="TRANSCRIPT",
        processing_mode="LOCAL",
        consent_ack=True,
        policy={"participant_consent_status": "NOT_RECORDED"},
    )
    check = conversations.preflight(session["id"])
    assert not any(x["key"] == "consent" for x in check["blockers"])
    assert any(x["key"] == "participant_consent_not_recorded" for x in check["warnings"])
    participant_item = next(x for x in check["items"] if x["key"] == "participant_consent")
    assert participant_item["ok"] is False



def test_transcript_preflight_surfaces_unrecorded_transparency_plan_as_warning(product_env):
    space = conversations.create_space("Transparency", "PROJECT_SYNC")
    session = conversations.create_session(
        space["id"],
        capture_mode="TRANSCRIPT",
        processing_mode="LOCAL",
        consent_ack=True,
        policy={
            "participant_consent_status": "USER_REPORTS_ALLOWED",
            "participant_transparency_plan": "NOT_RECORDED",
        },
    )
    check = conversations.preflight(session["id"])
    assert any(x["key"] == "participant_transparency_not_recorded" for x in check["warnings"])
    item = next(x for x in check["items"] if x["key"] == "participant_transparency")
    assert item["ok"] is False

    updated = conversations.update_session(
        session["id"],
        {"policy": {"participant_transparency_plan": "USER_WILL_NOTIFY_VERBALLY"}},
    )
    assert updated["policy"]["participant_transparency_plan"] == "USER_WILL_NOTIFY_VERBALLY"
    clean = conversations.preflight(session["id"])
    assert not any(x["key"] == "participant_transparency_not_recorded" for x in clean["warnings"])
    assert next(x for x in clean["items"] if x["key"] == "participant_transparency")["ok"] is True



def test_session_pack_freezes_ready_material_version_and_user_notes(product_env):
    material = materials.create_material(
        "Q4 Benchmark", kind="PROJECT", usage="FACTS",
        text="Q4 benchmark 已覆盖十倍数据规模，并记录了 offline migration 的测试结果。" * 3,
    )
    from services.product import quick_notes
    qn = quick_notes.create_note("提醒：先确认 rollback owner", title="Review reminder")
    space = conversations.create_space(
        "Architecture", "DESIGN_REVIEW",
        selected_source_ids=[material["id"]],
        selected_quick_note_ids=[qn["id"]],
    )
    session = conversations.create_session(space["id"], consent_ack=True)
    pack = conversations.start_session(session["id"])["pack"]
    assert pack["payload"]["sources"][0]["material_id"] == material["id"]
    assert pack["payload"]["sources"][0]["text"].startswith("Q4 benchmark")
    assert pack["payload"]["sources"][0]["is_personal_evidence"] is True
    assert pack["payload"]["quick_notes"][0]["kind"] == "USER_NOTE"
    assert pack["payload"]["quick_notes"][0].get("is_evidence") is None




def test_reviewed_derived_drafts_preserve_sources_and_never_claim_external_execution(product_env):
    space = conversations.create_space("Writeback", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    src = [{"kind": "USER_NOTE", "excerpt": "明确事项", "visibility": "PRIVATE"}]

    decision = conversations.add_item(
        session["id"], item_type="Decision", title="采用方案 B", source_refs=src,
        epistemic_status="OBSERVED",
    )
    conversations.review_item(decision["id"], "CONFIRM")

    commitment = conversations.add_item(
        session["id"], item_type="Commitment", title="补 rollout plan",
        owner_id="me", source_refs=src, epistemic_status="OBSERVED",
    )
    conversations.review_item(commitment["id"], "CONFIRM", {"owner_id": "me"})

    question = conversations.add_item(
        session["id"], item_type="OpenQuestion", title="谁负责 rollback drill？",
        source_refs=src, epistemic_status="OBSERVED",
    )
    question = conversations.review_item(question["id"], "CONFIRM")
    conversations.end_session(session["id"])

    decision_draft = conversations.derived_writeback_draft(session["id"], "UPDATE_DECISION_LOG_DRAFT")
    assert decision_draft["kind"] == "UPDATE_DECISION_LOG_DRAFT"
    assert "采用方案 B" in decision_draft["content"]
    assert decision_draft["source_refs"]
    assert decision_draft["payload"]["external_execution"] is False

    task_draft = conversations.derived_writeback_draft(session["id"], "CREATE_TASK_DRAFT")
    assert task_draft["kind"] == "CREATE_TASK_DRAFT"
    assert "补 rollout plan" in task_draft["content"]
    assert "owner=me" in task_draft["content"]

    issue_draft = conversations.derived_writeback_draft(session["id"], "CREATE_ISSUE_DRAFT")
    assert issue_draft["kind"] == "CREATE_ISSUE_DRAFT"
    assert "谁负责 rollback drill？" in issue_draft["content"]
    assert f"review={question['review_status']}" in issue_draft["content"]

    approved = conversations.review_draft_action(decision_draft["id"], "APPROVE")
    assert approved["status"] == "APPROVED"
    assert approved["payload"]["external_execution"] is False
    assert "sent" not in approved
    assert "external_id" not in approved


def test_adhoc_session_and_reviewed_followup_draft_never_claim_external_send(product_env):
    started = conversations.create_adhoc(title="临时设计讨论", profile="DESIGN_REVIEW")
    assert started["session"]["status"] == "ACTIVE"
    session_id = started["session"]["id"]
    decision = conversations.add_item(
        session_id, item_type="Decision", title="采用方案 B",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "明确采用 B"}],
        epistemic_status="OBSERVED",
    )
    conversations.review_item(decision["id"], "CONFIRM")
    candidate = conversations.add_item(
        session_id,
        item_type="OpenQuestion",
        title="AI candidate 不应进入 follow-up",
        source_refs=[{"kind": "TRANSCRIPT_SEGMENT", "id": "candidate-followup", "excerpt": "可能需要确认"}],
        epistemic_status="INFERRED",
        review_status="AI_EXTRACTED",
    )
    conversations.end_session(session_id)
    draft = conversations.followup_draft(session_id)
    assert draft["kind"] == "FOLLOWUP_EMAIL_DRAFT"
    assert draft["status"] == "DRAFT"
    assert "采用方案 B" in draft["content"]
    assert "AI candidate 不应进入 follow-up" not in draft["content"]
    assert draft["payload"]["excluded_unreviewed_item_ids"] == [candidate["id"]]
    assert draft["payload"]["external_execution"] is False
    approved = conversations.review_draft_action(draft["id"], "APPROVE")
    assert approved["status"] == "APPROVED"
    assert "sent" not in approved
    assert conversations.list_draft_actions(started["space"]["id"])[0]["id"] == draft["id"]


def test_conversation_capture_isolated_transcription_only_bridge(product_env, monkeypatch):
    import api.assist.pipeline as pipeline
    import core.config as config_module
    from core.session import get_session

    # The test never opens real audio. It verifies the exact ownership and
    # policy boundary around the reused pipeline.
    calls = []
    previous = config_module.session_overlay()
    legacy = get_session()
    legacy.is_recording = False

    def fake_start(device, candidate=None):
        calls.append(("start", device, candidate))
        legacy.is_recording = True
        legacy.is_paused = False
        legacy.last_device_id = int(device)
        legacy.last_candidate_mic_device_id = int(candidate) if candidate is not None else 0

    def fake_pause():
        calls.append(("pause",))
        legacy.is_paused = True

    def fake_resume(device=None, candidate=None):
        calls.append(("resume", device, candidate))
        legacy.is_paused = False

    def fake_stop():
        calls.append(("stop",))
        legacy.is_recording = False
        legacy.is_paused = False

    monkeypatch.setattr(pipeline, "start_nonblocking", fake_start)
    monkeypatch.setattr(pipeline, "stop_interview_loop", fake_stop)
    monkeypatch.setattr(pipeline, "pause_interview", fake_pause)
    monkeypatch.setattr(pipeline, "unpause_interview", fake_resume)

    space = conversations.create_space("Captured Review", "DESIGN_REVIEW")
    session = conversations.create_session(
        space["id"], capture_mode="TRANSCRIPT", processing_mode="LOCAL", consent_ack=True,
    )
    conversations.start_session(session["id"])

    started = conversation_capture.start(session["id"], 1001, 1002)
    assert started["active"] is True and started["owns_requested_session"] is True
    overlay = config_module.session_overlay()
    assert overlay["assist_auto_answer_mode"] == "off"
    assert overlay["auto_detect"] is False
    assert overlay["intelligence_early_cue"] is False
    assert overlay["review_enabled"] is False
    assert calls[0] == ("start", 1001, 1002)

    row = conversation_capture.record_transcription(
        "offline migration 继续使用 v2",
        channel="PRIMARY_AUDIO",
        provider="whisper",
        source="SYSTEM_LOOPBACK",
    )
    assert row and row["session_id"] == session["id"] and row["channel"] == "PRIMARY_AUDIO"
    assert conversation_capture.transcript(session["id"])[0]["text"] == "offline migration 继续使用 v2"

    conversation_capture.pause(session["id"])
    assert conversation_capture.status(session["id"])["paused"] is True
    conversation_capture.resume(session["id"])
    assert conversation_capture.status(session["id"])["paused"] is False
    stopped = conversation_capture.stop(session["id"])
    assert stopped["active"] is False
    assert calls[-3:] == [("pause",), ("resume", 1001, 1002), ("stop",)]
    assert config_module.session_overlay() == previous






def test_conversation_capture_reports_self_mic_degraded_state(product_env, monkeypatch):
    import api.assist.pipeline as pipeline
    from core.session import get_session

    legacy = get_session()
    legacy.is_recording = False
    legacy.is_paused = False
    legacy.last_candidate_mic_device_id = 0

    def degraded_start(device, candidate=None):
        legacy.is_recording = True
        legacy.last_device_id = int(device)
        legacy.last_candidate_mic_device_id = 0

    def degraded_stop():
        legacy.is_recording = False

    monkeypatch.setattr(pipeline, "start_nonblocking", degraded_start)
    monkeypatch.setattr(pipeline, "stop_interview_loop", degraded_stop)

    space = conversations.create_space("Degraded Self Mic", "PROJECT_SYNC")
    session = conversations.create_session(
        space["id"], capture_mode="TRANSCRIPT", processing_mode="LOCAL", consent_ack=True,
    )
    conversations.start_session(session["id"])

    status = conversation_capture.start(session["id"], 1001, 1002)
    assert status["active"] is True
    assert status["candidate_mic_device_id"] is None
    conversation_capture.stop(session["id"])



def test_conversation_capture_stop_allows_final_asr_callback_to_reenter(product_env, monkeypatch):
    import api.assist.pipeline as pipeline
    from core.session import get_session

    legacy = get_session()
    legacy.is_recording = False
    legacy.is_paused = False

    def fake_start(device, candidate=None):
        legacy.is_recording = True
        legacy.last_device_id = int(device)
        legacy.last_candidate_mic_device_id = 0

    callback_finished = threading.Event()

    def fake_stop():
        worker = threading.Thread(
            target=lambda: (
                conversation_capture.record_transcription(
                    "最后一句必须落盘",
                    channel="PRIMARY_AUDIO",
                    provider="test",
                    source="TEST_DRAIN",
                ),
                callback_finished.set(),
            ),
            daemon=True,
        )
        worker.start()
        worker.join(timeout=1.0)
        assert callback_finished.is_set(), "final ASR callback was blocked by Conversation capture lock"
        legacy.is_recording = False

    monkeypatch.setattr(pipeline, "start_nonblocking", fake_start)
    monkeypatch.setattr(pipeline, "stop_interview_loop", fake_stop)

    space = conversations.create_space("Drain Safety", "PROJECT_SYNC")
    session = conversations.create_session(
        space["id"], capture_mode="TRANSCRIPT", processing_mode="LOCAL", consent_ack=True,
    )
    conversations.start_session(session["id"])
    conversation_capture.start(session["id"], 1001)
    stopped = conversation_capture.stop(session["id"])

    assert stopped["active"] is False
    rows = conversation_capture.transcript(session["id"])
    assert rows[-1]["text"] == "最后一句必须落盘"

def test_conversation_capture_transport_never_owns_interview_review_lifecycle(product_env, monkeypatch):
    import api.assist.pipeline as pipeline

    monkeypatch.setattr(conversation_capture, "is_active", lambda: True)
    assert pipeline._conversation_capture_owns_pipeline() is True

    monkeypatch.setattr(conversation_capture, "is_active", lambda: False)
    assert pipeline._conversation_capture_owns_pipeline() is False

def test_conversation_capture_refuses_to_steal_live_interview_audio(product_env):
    from core.session import get_session
    legacy = get_session()
    legacy.is_recording = True
    try:
        space = conversations.create_space("No Steal", "PROJECT_SYNC")
        session = conversations.create_session(space["id"], capture_mode="TRANSCRIPT", consent_ack=True)
        conversations.start_session(session["id"])
        with pytest.raises(ValueError, match="不会抢占"):
            conversation_capture.start(session["id"], 1001)
    finally:
        legacy.is_recording = False




def test_interview_start_refuses_to_preempt_active_conversation_capture(product_env, monkeypatch):
    from api.assist.routes import api_start

    monkeypatch.setattr(conversation_capture, "is_active", lambda: True)
    with pytest.raises(Exception) as exc_info:
        asyncio.run(api_start({}))
    assert getattr(exc_info.value, "status_code", None) == 409
    assert "Conversation" in str(getattr(exc_info.value, "detail", ""))



def test_conversation_router_lifecycle_exit_stops_owned_capture(product_env, monkeypatch):
    from api.product.conversations_router import _stop_capture_for_session, _stop_capture_for_space

    space = conversations.create_space("Lifecycle", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], capture_mode="TRANSCRIPT", consent_ack=True)
    conversations.start_session(session["id"])

    stopped = []
    monkeypatch.setattr(
        conversation_capture,
        "status",
        lambda session_id="": {
            "active": True,
            "session_id": session["id"],
            "owns_requested_session": session_id == session["id"] if session_id else False,
        },
    )
    monkeypatch.setattr(conversation_capture, "stop", lambda session_id: stopped.append(session_id) or {"active": False})

    _stop_capture_for_session(session["id"])
    assert stopped == [session["id"]]

    stopped.clear()
    _stop_capture_for_space(space["id"])
    assert stopped == [session["id"]]

def test_transcript_topic_recall_is_sourced_deduped_and_quiet_respected(product_env):
    space = conversations.create_space("Continuity", "DESIGN_REVIEW")
    old = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(old["id"])
    decision = conversations.add_item(
        old["id"], item_type="Decision", title="offline migration 使用 v2",
        source_refs=[{"kind": "TRANSCRIPT_SEGMENT", "excerpt": "明确用 v2"}],
        epistemic_status="OBSERVED",
    )
    conversations.review_item(decision["id"], "CONFIRM")
    conversations.end_session(old["id"])

    live = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(live["id"])
    first = conversations.guidance_from_transcript(live["id"], "我们回到 offline migration")
    assert first and first["kind"] == "RECALL" and first["reason"] == "TRANSCRIPT_TOPIC_RECALL"
    assert conversations.guidance_from_transcript(live["id"], "offline migration 再说一下") is None

    conversations.update_session(live["id"], {"assistance_mode": "QUIET"})
    assert conversations.guidance_from_transcript(live["id"], "offline migration") is None


def test_conversation_diagnostics_reports_local_engineering_not_pmf(product_env):
    space = conversations.create_space("Diagnostic Space", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    conversations.add_item(
        session["id"], item_type="OpenQuestion", title="owner?",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "待确认"}],
    )
    diag = conversations.diagnostics()
    assert diag["schema_version"] == 7
    assert diag["runtime"]["spaces"] == 1
    assert diag["runtime"]["sessions"] == 1
    assert diag["runtime"]["pending_review_items"] == 1
    assert diag["evidence"]["real_conversation_user_evidence"] == "REAL_CONVERSATION_USER_EVIDENCE_PENDING"
    assert diag["evidence"]["pmf"] == "PMF_PROVEN_FALSE"
    assert diag["privacy"]["auto_external_writeback"] == "OFF"
    assert diag["health"]["session_pack_context"] == "AVAILABLE"
    assert diag["health"]["retrieval"] == "AVAILABLE"
    assert diag["health"]["state_engine"] == "AVAILABLE"
    assert diag["health"]["guidance_arbiter"] == "AVAILABLE"
    assert diag["health"]["export_delete_integrity"] == "AVAILABLE"
    assert diag["health"]["processing_policy"] == "AVAILABLE"
    assert diag["health"]["speaker_diarization"] == "LIMITED_CHANNEL_ONLY"




def test_diagnostics_separates_observed_proxies_from_human_label_metrics(product_env):
    space = conversations.create_space("Eval", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    shown = conversations.evaluate_guidance(session["id"], {
        "direct_question": "为什么？",
        "source_refs": [{"kind": "USER_NOTE", "excerpt": "source"}],
    })["guidance"]
    conversations.set_guidance_action(shown["id"], "USED")
    conversations.evaluate_guidance(session["id"], {
        "candidate_text": "没有来源的主动提示",
        "source_refs": [],
        "relevance": 1,
        "novelty": 1,
        "provenance_strength": 0,
    })

    diag = conversations.diagnostics()
    assert diag["runtime"]["guidance_adopted"] == 1
    assert diag["evaluation"]["observed_proxies"]["guidance_adoption_rate"] == 1.0
    assert "opportunity_precision" in diag["evaluation"]["requires_human_labels"]
    assert "interruption_regret" in diag["evaluation"]["requires_human_labels"]
    assert "not precision/quality/PMF" in diag["evaluation"]["interpretation"]
    assert diag["health"]["conversation_screen_context"] == "MANUAL_AVAILABLE_AUTO_BLOCKED"
    assert diag["health"]["conversation_human_coach"] == "BLOCKED_NOT_WIRED"
    assert diag["privacy"]["emotion_sentiment_profiling"] == "OFF"
    assert diag["privacy"]["hidden_intent_claims"] == "OFF"


def test_space_summaries_grouping_inputs_include_upcoming_and_open_counts(product_env):
    space = conversations.create_space("Roadmap", "PROJECT_SYNC")
    conversations.create_session(
        space["id"], title="Tomorrow", scheduled_at=store.now() + 86400,
        capture_mode="NOTES_ONLY", consent_ack=True,
    )
    active = conversations.create_session(space["id"], title="Today", consent_ack=True)
    conversations.start_session(active["id"])
    question = conversations.add_item(
        active["id"], item_type="OpenQuestion", title="launch date?",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "待确认"}],
    )
    conversations.review_item(question["id"], "CONFIRM")
    summaries = conversations.list_space_summaries("")
    row = next(x for x in summaries if x["id"] == space["id"])
    assert row["next_session"]["title"] == "Tomorrow"
    assert row["open_questions_count"] == 1
    assert row["open_commitments_count"] == 0




def test_unreviewed_commitment_never_enters_prepare_agenda_or_space_open_count(product_env):
    space = conversations.create_space("Commitment Boundary", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    candidate = conversations.add_item(
        session["id"],
        item_type="Commitment",
        title="AI 猜测我会补 rollout plan",
        owner_id="",
        source_refs=[{"kind": "TRANSCRIPT_SEGMENT", "id": "seg-commit-candidate", "excerpt": "可能我来补"}],
        epistemic_status="INFERRED",
        review_status="AI_EXTRACTED",
    )

    prepared = conversations.prepare_space(space["id"])
    assert prepared["open_commitments"] == []
    assert candidate["title"] not in prepared["agenda"]
    summary = next(x for x in conversations.list_space_summaries("") if x["id"] == space["id"])
    assert summary["open_commitments_count"] == 0

    reviewed = conversations.review_item(candidate["id"], "CONFIRM", {"owner_id": "me"})
    assert reviewed["state"] == "COMMITTED"
    prepared_after = conversations.prepare_space(space["id"])
    assert [x["id"] for x in prepared_after["open_commitments"]] == [candidate["id"]]
    assert candidate["title"] in prepared_after["agenda"]
    summary_after = next(x for x in conversations.list_space_summaries("") if x["id"] == space["id"])
    assert summary_after["open_commitments_count"] == 1


def test_issue_draft_cannot_bypass_open_question_item_review(product_env):
    space = conversations.create_space("Issue Review Boundary", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    candidate = conversations.add_item(
        session["id"],
        item_type="OpenQuestion",
        title="rollback owner 是否已经确定？",
        source_refs=[{"kind": "TRANSCRIPT_SEGMENT", "id": "seg-issue-candidate", "excerpt": "还要问"}],
        epistemic_status="INFERRED",
        review_status="AI_EXTRACTED",
    )
    conversations.end_session(session["id"])

    with pytest.raises(ValueError, match="当前没有可生成 Issue Draft"):
        conversations.derived_writeback_draft(session["id"], "CREATE_ISSUE_DRAFT")

    conversations.review_item(candidate["id"], "CONFIRM")
    draft = conversations.derived_writeback_draft(session["id"], "CREATE_ISSUE_DRAFT")
    assert candidate["title"] in draft["content"]
    assert "review=USER_CONFIRMED" in draft["content"]
    assert draft["payload"]["external_execution"] is False


def test_synthetic_demo_is_non_persistent_and_explicitly_labeled(product_env):
    before = conversations.list_spaces("")
    demo = conversations.synthetic_demo()
    after = conversations.list_spaces("")
    assert demo["evidence"] == "SYNTHETIC_DEMO"
    assert [step["kind"] for step in demo["steps"]] == [
        "PROPOSAL", "RECALL", "CONTRIBUTION_OPPORTUNITY", "SILENT", "CONTINUE",
    ]
    assert before == after




def test_space_complete_erase_requires_explicit_confirm_and_removes_tombstones(product_env):
    space = conversations.create_space("Erase Boundary", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    item = conversations.add_item(
        session["id"],
        item_type="Decision",
        title="temporary confirmed truth",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "confirmed"}],
        epistemic_status="OBSERVED",
    )
    conversations.review_item(item["id"], "CONFIRM")
    conversations.end_session(session["id"])
    conversations.delete_session(session["id"], confirmed_policy="TOMBSTONE")
    assert store.select("conversation_provenance_tombstone", where="space_id = ?", params=(space["id"],))

    with pytest.raises(ValueError, match="明确确认"):
        conversations.delete_space(space["id"])
    assert store.get("conversation_space", space["id"]) is not None

    assert conversations.delete_space(space["id"], confirm=True) is True
    assert store.get("conversation_space", space["id"]) is None
    assert store.select("conversation_provenance_tombstone", where="space_id = ?", params=(space["id"],)) == []


def test_session_delete_requires_tombstone_for_confirmed_truth(product_env):
    space = conversations.create_space("Delete Safety", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    item = conversations.add_item(
        session["id"], item_type="Decision", title="采用 v2",
        source_refs=[{"kind": "TRANSCRIPT_SEGMENT", "excerpt": "就按 v2"}],
        epistemic_status="OBSERVED",
    )
    conversations.review_item(item["id"], "CONFIRM")
    conversations.end_session(session["id"])
    with pytest.raises(ValueError, match="TOMBSTONE"):
        conversations.delete_session(session["id"])
    result = conversations.delete_session(session["id"], confirmed_policy="TOMBSTONE")
    assert result["deleted"] is True and result["provenance_tombstones"] == 1
    assert store.get("conversation_session", session["id"]) is None
    assert store.get("conversation_item", item["id"]) is None
    tomb = store.select("conversation_provenance_tombstone", where="original_item_id = ?", params=(item["id"],))
    assert tomb and tomb[0]["title"] == "采用 v2"
    assert tomb[0]["source_refs"][0]["kind"] == "TRANSCRIPT_SEGMENT"

    # Tombstones preserve deletion provenance only; they must not behave like
    # an undeletable memory source for future Conversation sessions.
    later = conversations.create_session(space["id"], title="After deletion", consent_ack=True)
    conversations.start_session(later["id"])
    asked = conversations.ask(later["id"], "采用 v2")
    assert asked["grounded"] is False
    assert conversations.guidance_from_transcript(
        later["id"], "继续讨论采用 v2", channel="PRIMARY_AUDIO",
    ) is None


def test_retention_preview_requires_confirmation_and_preserves_confirmed_truth(product_env, monkeypatch):
    clock = [1_000_000.0]
    monkeypatch.setattr(store, "now", lambda: clock[0])
    space = conversations.create_space("Retention", "PROJECT_SYNC")
    conversations.update_space(space["id"], {"retention_policy": {"preset": "MINIMUM"}})
    session = conversations.create_session(space["id"], capture_mode="NOTES_ONLY", consent_ack=True)
    conversations.start_session(session["id"])
    item = conversations.add_item(
        session["id"], item_type="Decision", title="Keep me",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "confirmed"}],
        epistemic_status="OBSERVED",
    )
    conversations.review_item(item["id"], "CONFIRM")
    store.insert("conversation_transcript_segment", {
        "id": store.new_id("cts_"), "space_id": space["id"], "session_id": session["id"],
        "channel": "PRIMARY_AUDIO", "text": "temporary transcript", "provider": "test",
        "source": "TEST", "is_final": True, "created_at": clock[0] - 1,
    })
    conversations.evaluate_guidance(session["id"], {"user_speaking": True})
    draft = conversations.create_draft_action(session["id"], kind="FOLLOWUP_EMAIL_DRAFT", title="draft")
    # MINIMUM intentionally keeps guidance/drafts for 7 days while
    # transcript_days=0. Advance beyond the longest configured window so this
    # test validates all three destructive categories against the real contract.
    clock[0] += 8 * 24 * 60 * 60

    preview = conversations.retention_preview(space["id"])
    assert preview["would_delete"]["transcript_segments"] == 1
    assert preview["would_delete"]["guidance_events"] == 1
    assert preview["would_delete"]["draft_actions"] == 1
    with pytest.raises(ValueError, match="明确确认"):
        conversations.apply_retention(space["id"], confirm=False)
    result = conversations.apply_retention(space["id"], confirm=True)
    assert result["deleted"] == {
        "transcript_segments": 1,
        "guidance_events": 1,
        "draft_actions": 1,
        "screen_context_observations": 0,
    }
    assert store.get("conversation_item", item["id"]) is not None
    assert store.get("conversation_draft_action", draft["id"]) is None


def test_export_is_categorized_and_keeps_truth_classes_separate(product_env):
    space = conversations.create_space("Export", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    confirmed = conversations.add_item(
        session["id"], item_type="Decision", title="confirmed decision",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "yes"}],
        epistemic_status="OBSERVED",
    )
    conversations.review_item(confirmed["id"], "CONFIRM")
    candidate = conversations.add_item(
        session["id"], item_type="OpenQuestion", title="candidate question",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "maybe"}],
        epistemic_status="OBSERVED",
    )
    reviewed_risk = conversations.add_item(
        session["id"], item_type="Risk", title="reviewed rollback risk",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "risk confirmed"}],
        epistemic_status="OBSERVED",
    )
    conversations.review_item(reviewed_risk["id"], "CONFIRM")

    exported = conversations.export_space(space["id"])
    assert "transcript" in exported and "source_manifest" in exported
    confirmed_ids = {x["id"] for x in exported["confirmed_items"]}
    assert {confirmed["id"], reviewed_risk["id"]} <= confirmed_ids
    assert [x["id"] for x in exported["unconfirmed_candidates"]] == [candidate["id"]]
    assert "confirmed_items" in exported["export_manifest"]["categories"]
    assert "open_threads" in exported["export_manifest"]["categories"]
    assert exported["open_threads"]
    assert exported["open_threads"] == exported["threads"]  # compatibility alias
    assert exported["open_threads"][0]["kind"] == "Risk"
    assert exported["open_threads"][0]["source_refs"]
    assert "session_packs" in exported["export_manifest"]["categories"]
    assert exported["session_packs"]
    assert exported["session_packs"] == exported["packs"]  # legacy alias, same local truth
    assert exported["session_packs"][0]["session_id"] == session["id"]


def test_one_hundred_session_state_reliability(product_env):
    space = conversations.create_space("100 Session Continuity", "PROJECT_SYNC")
    for index in range(100):
        session = conversations.create_session(space["id"], title=f"S{index}", consent_ack=True)
        conversations.start_session(session["id"])
        if index in {0, 25, 50, 75, 99}:
            item = conversations.add_item(
                session["id"], item_type="Decision", title=f"checkpoint {index}",
                source_refs=[{"kind": "USER_NOTE", "excerpt": f"checkpoint {index}"}],
                epistemic_status="OBSERVED",
            )
            conversations.review_item(item["id"], "CONFIRM")
        conversations.end_session(session["id"])
    detail = conversations.space_detail(space["id"])
    assert len(detail["sessions"]) == 100
    assert len([x for x in detail["decisions"] if x["state"] == "AGREED"]) == 5
    latest = conversations.create_session(space["id"], title="S100", consent_ack=True)
    pack = conversations.start_session(latest["id"])["pack"]
    ids = {x["id"] for x in pack["payload"]["confirmed_items"]}
    assert len(ids) == 5


def test_global_conversation_search_returns_grounded_space_session_and_source_context(product_env):
    space = conversations.create_space("Architecture", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], title="Review #42", consent_ack=True)
    conversations.start_session(session["id"])
    decision = conversations.add_item(
        session["id"],
        item_type="Decision",
        title="offline migration 采用 v2",
        detail="Q4 benchmark 已验证",
        source_refs=[{"kind": "DOCUMENT", "id": "bench", "visibility": "PRIVATE"}],
        epistemic_status="OBSERVED",
    )
    conversations.review_item(decision["id"], "CONFIRM")
    commitment = conversations.add_item(
        session["id"],
        item_type="Commitment",
        title="补 rollout plan",
        owner_id="me",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "我来补 rollout plan"}],
        epistemic_status="OBSERVED",
    )
    conversations.review_item(commitment["id"], "CONFIRM", {"owner_id": "me"})

    found = conversations.search_items(query="offline", item_type="Decision")
    assert len(found) == 1
    row = found[0]
    assert row["id"] == decision["id"]
    assert row["space_title"] == "Architecture"
    assert row["space_profile"] == "DESIGN_REVIEW"
    assert row["session_title"] == "Review #42"
    assert row["source_refs"][0]["kind"] == "DOCUMENT"
    assert row["review_status"] == "USER_CONFIRMED"

    commitments = conversations.search_items(item_type="Commitment")
    assert [x["id"] for x in commitments] == [commitment["id"]]

    assert conversations.search_items(query="does-not-exist", item_type="Decision") == []


def test_session_export_is_categorized_local_and_scoped_to_current_session(product_env):
    space = conversations.create_space("Export", "PROJECT_SYNC")
    first = conversations.create_session(space["id"], title="First", consent_ack=True)
    conversations.start_session(first["id"])
    item = conversations.add_item(
        first["id"],
        item_type="Decision",
        title="采用方案 A",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "明确 A"}],
        epistemic_status="OBSERVED",
    )
    conversations.review_item(item["id"], "CONFIRM")
    store.insert("conversation_transcript_segment", {
        "id": store.new_id("cts_"),
        "space_id": space["id"],
        "session_id": first["id"],
        "channel": "PRIMARY_AUDIO",
        "text": "这是一段本场转写",
        "provider": "test",
        "source": "TEST",
        "is_final": True,
        "created_at": store.now(),
    })
    conversations.end_session(first["id"])

    second = conversations.create_session(space["id"], title="Second", consent_ack=True)
    conversations.start_session(second["id"])
    conversations.add_item(
        second["id"],
        item_type="OpenQuestion",
        title="第二场的问题不应混入第一场导出",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "second"}],
    )

    exported = conversations.export_session(first["id"])
    assert exported["kind"] == "CONVERSATION_SESSION"
    assert exported["export_manifest"]["privacy"] == "LOCAL_EXPORT"
    assert exported["export_manifest"]["contains_external_secrets"] is False
    assert exported["session"]["id"] == first["id"]
    assert exported["space"]["id"] == space["id"]
    assert [x["id"] for x in exported["confirmed_items"]] == [item["id"]]
    assert [x["text"] for x in exported["transcript"]] == ["这是一段本场转写"]
    assert all(x["session_id"] == first["id"] for x in exported["guidance"])
    assert "第二场的问题不应混入第一场导出" not in str(exported)


def test_long_lived_space_open_thread_lookup_survives_over_500_other_threads(product_env):
    """Review and deletion must preserve the provenance of an older open thread."""
    space = conversations.create_space("Longitudinal Thread Stress", "PROJECT_SYNC")
    old_session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(old_session["id"])
    item = conversations.add_item(
        old_session["id"],
        item_type="OpenQuestion",
        title="Who owns rollback?",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "rollback owner unknown"}],
    )
    conversations.review_item(item["id"], "CONFIRM")
    original = conversations._thread_for_item(conversations.require_item(item["id"]))
    assert original and original["status"] == "OPEN"

    newer_session = conversations.create_session(space["id"], consent_ack=True)
    # Populate one Space with >500 more recent projections to reproduce the old
    # truncated latest-500 query, without generating unrelated AI/confirmed truth.
    with store.connect() as conn:
        for index in range(501):
            store.insert("conversation_open_thread", {
                "id": store.new_id("cot_"),
                "space_id": space["id"],
                "session_id": newer_session["id"],
                "kind": "Risk",
                "text": f"old resolved projection {index}",
                "owner_id": "",
                "status": "RESOLVED",
                "source_refs": [{"kind": "CONVERSATION_ITEM", "id": f"historic-{index}"}],
                "created_at": store.now() + index + 1,
                "resolved_at": store.now() + index + 1,
            }, conn=conn)

    found = conversations._thread_for_item(conversations.require_item(item["id"]))
    assert found and found["id"] == original["id"]

    conversations.review_item(item["id"], "EDIT", {"title": "Who owns the rollback drill?"})
    updated = conversations._thread_for_item(conversations.require_item(item["id"]))
    assert updated and updated["id"] == original["id"]
    assert updated["text"] == "Who owns the rollback drill?"

    conversations.end_session(old_session["id"])
    result = conversations.delete_session(old_session["id"], confirmed_policy="TOMBSTONE")
    assert result["removed_open_thread_projections"] == 1
    assert store.get("conversation_open_thread", original["id"]) is None
