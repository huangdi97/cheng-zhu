"""v2.0 Conversation Profile: real persistence, truth state, pack and guidance loop."""
import sqlite3

import pytest

from services.product import conversation_capture, conversations, materials
from services.storage import product as store


def test_v2_schema_is_additive_and_keeps_v1_tables(product_env):
    assert store.schema_version() == 3
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
    monkeypatch.setattr(pipeline, "start_nonblocking", lambda device, candidate=None: calls.append(("start", device, candidate)))
    monkeypatch.setattr(pipeline, "stop_interview_loop", lambda: calls.append(("stop",)))
    monkeypatch.setattr(pipeline, "pause_interview", lambda: calls.append(("pause",)))
    monkeypatch.setattr(pipeline, "unpause_interview", lambda device=None, candidate=None: calls.append(("resume", device, candidate)))

    previous = config_module.session_overlay()
    legacy = get_session()
    legacy.is_recording = False

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
    conversation_capture.resume(session["id"])
    stopped = conversation_capture.stop(session["id"])
    assert stopped["active"] is False
    assert calls[-3:] == [("pause",), ("resume", 1001, 1002), ("stop",)]
    assert config_module.session_overlay() == previous


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
    assert diag["schema_version"] == 3
    assert diag["runtime"]["spaces"] == 1
    assert diag["runtime"]["sessions"] == 1
    assert diag["runtime"]["pending_review_items"] == 1
    assert diag["evidence"]["real_conversation_user_evidence"] == "REAL_CONVERSATION_USER_EVIDENCE_PENDING"
    assert diag["evidence"]["pmf"] == "PMF_PROVEN_FALSE"
    assert diag["privacy"]["auto_external_writeback"] == "OFF"
