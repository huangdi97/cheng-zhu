"""v2.0 Conversation Profile: real persistence, truth state, pack and guidance loop."""
import sqlite3

import pytest

from services.product import conversations
from services.storage import product as store


def test_v2_schema_is_additive_and_keeps_v1_tables(product_env):
    assert store.schema_version() == 2
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
    } <= tables


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
