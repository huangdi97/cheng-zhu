"""v2.0 Conversation Profile: real persistence, truth state, pack and guidance loop."""
import asyncio
import sqlite3
import threading

import pytest

from services.product import conversation_capture, conversations, materials
from services.storage import product as store


def test_v2_schema_is_additive_and_keeps_v1_tables(product_env):
    assert store.schema_version() == 5
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
    } <= tables
    conn = sqlite3.connect(store.DB_PATH)
    try:
        session_cols = {r[1] for r in conn.execute("PRAGMA table_info(conversation_session)")}
        participant_cols = {r[1] for r in conn.execute("PRAGMA table_info(conversation_participant)")}
    finally:
        conn.close()
    assert "policy_json" in session_cols
    assert "counterparty_state_json" in participant_cols


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
            "share_privacy": "PRIVATE_OVERLAY",
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
    assert policy["share_privacy"] == "PRIVATE_OVERLAY"
    assert policy["external_writeback"] == "OFF"
    assert policy["participant_consent_status"] == "USER_REPORTS_CONSENTED"
    assert check["pack_preview"]["participants_count"] == 0
    assert check["pack_preview"]["policy"]["ai_assistance"] == "AI_FORBIDDEN"
    assert policy["speaker_biometric_identity"] == "OFF"
    assert policy["emotion_sentiment_profiling"] == "OFF"
    assert policy["hidden_intent_claims"] == "OFF"

    started = conversations.start_session(session["id"])
    assert started["pack"]["payload"]["policy"]["ai_assistance"] == "AI_FORBIDDEN"
    assert started["pack"]["payload"]["policy"]["share_privacy"] == "PRIVATE_OVERLAY"

    suppressed = conversations.evaluate_guidance(session["id"], {
        "direct_question": "现在要不要补充？",
        "source_refs": [{"kind": "USER_NOTE", "excerpt": "explicit"}],
    })
    assert suppressed["guidance"] is None
    assert suppressed["suppressed"] == "POLICY_AI_FORBIDDEN"

    with pytest.raises(ValueError, match="External Write-back"):
        conversations.followup_draft(session["id"])


def test_preflight_blocks_unwired_conversation_screen_and_human_runtime(product_env):
    space = conversations.create_space("Truthful Preflight", "PROJECT_SYNC")
    session = conversations.create_session(
        space["id"],
        consent_ack=True,
        policy={"screen_context": "MANUAL", "human_assistance": "HUMAN_ALLOWED"},
    )
    check = conversations.preflight(session["id"])
    keys = {item["key"] for item in check["blockers"]}
    assert {"screen_context_runtime", "human_assistance_runtime"} <= keys
    with pytest.raises(ValueError, match="Screen Context runtime"):
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
    })
    assert result["guidance"] is not None
    assert result["guidance"]["score"]["role_relevance"] >= 1.0
    saved = conversations.require_session(session["id"])
    assert saved["state"]["audience_context"]["explicit_priority"] == "迁移稳定性"
    assert "emotion" not in saved["state"]["audience_context"]
    assert "hidden_intent" not in saved["state"]["audience_context"]


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
    conversations.start_session(live["id"])
    assert conversations.guidance_from_transcript(live["id"], "offline migration") is None

    manual = conversations.evaluate_guidance(live["id"], {
        "direct_question": "之前为什么用 v2？",
        "source_refs": [{"kind": "USER_NOTE", "excerpt": "明确使用 v2"}],
    })
    assert manual["guidance"]["kind"] == "ANSWER_CUE"


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
    assert history[0]["open_questions_count"] == 1
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
    assert conversations.delete_space(space["id"]) is True
    assert store.get("conversation_session", session["id"]) is None
    assert store.select("goal") == []  # v1 Interview store remains independent


def test_source_aware_ask_only_uses_confirmed_items(product_env):
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
    conversations.end_session(first["id"])

    second = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(second["id"])
    result = conversations.evaluate_guidance(second["id"], {})
    # Quiet negotiation may stay silent; all other profiles can surface the
    # unresolved question through the same shared runtime.
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
    conversations.end_session(session_id)
    draft = conversations.followup_draft(session_id)
    assert draft["kind"] == "FOLLOWUP_EMAIL_DRAFT"
    assert draft["status"] == "DRAFT"
    assert "采用方案 B" in draft["content"]
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
    assert diag["schema_version"] == 5
    assert diag["runtime"]["spaces"] == 1
    assert diag["runtime"]["sessions"] == 1
    assert diag["runtime"]["pending_review_items"] == 1
    assert diag["evidence"]["real_conversation_user_evidence"] == "REAL_CONVERSATION_USER_EVIDENCE_PENDING"
    assert diag["evidence"]["pmf"] == "PMF_PROVEN_FALSE"
    assert diag["privacy"]["auto_external_writeback"] == "OFF"




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
    assert diag["health"]["conversation_screen_context"] == "BLOCKED_NOT_WIRED"
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
    conversations.add_item(
        active["id"], item_type="OpenQuestion", title="launch date?",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "待确认"}],
    )
    summaries = conversations.list_space_summaries("")
    row = next(x for x in summaries if x["id"] == space["id"])
    assert row["next_session"]["title"] == "Tomorrow"
    assert row["open_questions_count"] == 1
    assert row["open_commitments_count"] == 0


def test_synthetic_demo_is_non_persistent_and_explicitly_labeled(product_env):
    before = conversations.list_spaces("")
    demo = conversations.synthetic_demo()
    after = conversations.list_spaces("")
    assert demo["evidence"] == "SYNTHETIC_DEMO"
    assert [step["kind"] for step in demo["steps"]] == [
        "PROPOSAL", "RECALL", "CONTRIBUTION_OPPORTUNITY", "SILENT", "CONTINUE",
    ]
    assert before == after


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
    tomb = store.select("conversation_provenance_tombstone", where="original_item_id = ?", params=(item["id"],))
    assert tomb and tomb[0]["title"] == "采用 v2"
    assert tomb[0]["source_refs"][0]["kind"] == "TRANSCRIPT_SEGMENT"


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
    assert result["deleted"] == {"transcript_segments": 1, "guidance_events": 1, "draft_actions": 1}
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
    exported = conversations.export_space(space["id"])
    assert "transcript" in exported and "source_manifest" in exported
    assert [x["id"] for x in exported["confirmed_items"]] == [confirmed["id"]]
    assert [x["id"] for x in exported["unconfirmed_candidates"]] == [candidate["id"]]
    assert "confirmed_items" in exported["export_manifest"]["categories"]


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
