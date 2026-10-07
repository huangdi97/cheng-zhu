"""v1.3 G2/G4/G5/G8: product.db migration, Goals, Action Home, Quick Notes."""
import sqlite3

import pytest

from services.product import events, goals, home, next_focus, quick_notes
from services.storage import product as store


def test_product_db_schema_is_versioned_and_idempotent(product_env):
    assert store.schema_version() == 5
    conn = sqlite3.connect(store.DB_PATH)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    for table in ("goal", "goal_material", "goal_interview", "goal_offer", "quick_note", "question_bank",
                  "question_bank_item", "practice_profile", "practice_session", "pin_moment", "nudge_event",
                  "closing_mode_event", "reflection_action", "next_focus", "material_version", "delivery_metrics",
                  "rubric_observation", "product_event", "setting_override", "conversation_space", "conversation_session",
                  "conversation_session_pack", "conversation_item", "conversation_guidance_event",
                  "conversation_draft_action", "conversation_transcript_segment", "conversation_provenance_tombstone"):
        assert table in tables, table
    from services.storage.product_migrations import LATEST_SCHEMA_VERSION, ensure_schema

    conn = sqlite3.connect(store.DB_PATH)
    assert ensure_schema(conn) == LATEST_SCHEMA_VERSION  # re-run is a no-op
    conn.close()


def test_v12_prep_spaces_become_goals_without_touching_v12_data(product_env):
    from services.storage import job_tracker, prep_space, review

    space_id = prep_space.create_space(title="MindRank · AIDD", role="AIDD Agent Engineer", company="MindRank",
                                       jd_text="任职要求：熟悉 RAG 与 Agent")
    app = job_tracker.create_application({"company": "MindRank", "position": "AIDD Agent Engineer", "stage": "interview"})
    rid = review.create_session(started_at=1.0, interviewer_enabled=True, candidate_enabled=False,
                                application_id=app["id"])
    before = prep_space.get_space(space_id)

    result = goals.backfill_from_legacy()
    assert result["goals_created"] == 1 and result["sessions_linked"] == 1
    goal = goals.goal_for_prep_space(space_id)
    assert goal and goal["company"] == "MindRank" and goal["application_id"] == app["id"]
    assert goals.goal_for_review_session(rid) == goal["id"]
    assert prep_space.get_space(space_id)["jd_text"] == before["jd_text"]  # untouched
    assert goals.backfill_from_legacy()["skipped"] == 1  # idempotent


def test_goal_lifecycle_interviews_offer_and_cascade(product_env):
    goal = goals.create_goal("MindRank", "AIDD Agent Engineer", "熟悉 Redis 高可用")
    assert goal["legacy_prep_space_id"] and goal["role_family"] == "AI_ML"
    gi = goals.add_interview(goal["id"], round_name="技术二面", scheduled_at=2_000_000_000.0)
    assert goals.require_goal(goal["id"])["next_interview_at"] == 2_000_000_000.0
    goals.update_interview(gi["id"], {"status": "DONE"})
    assert goals.require_goal(goal["id"])["next_interview_at"] is None
    offer = goals.set_offer(goal["id"], {"status": "RECEIVED", "comp": "40k*15"})
    assert offer["comp"] == "40k*15" and goals.require_goal(goal["id"])["offer_state"] == "RECEIVED"
    with pytest.raises(goals.GoalError):
        goals.set_offer(goal["id"], {"status": "PROBABLY"})

    note = quick_notes.create_note("想问团队规模", scope="GOAL", goal_id=goal["id"])
    from services.product import pins

    pin = pins.create_pin("live-1", tag="IMPORTANT", question="q", goal_id=goal["id"])
    goals.delete_goal(goal["id"])
    assert quick_notes.get_note(note["id"]) is None  # owned → deleted
    assert store.get("pin_moment", pin["id"])["goal_id"] is None  # referenced → detached


def test_goal_reopen_is_recorded_after_a_gap(product_env, monkeypatch):
    goal = goals.create_goal("A", "B")
    t = [1000.0]
    monkeypatch.setattr(store, "now", lambda: t[0])
    goals.open_goal(goal["id"])
    t[0] += 5 * 3600
    goals.open_goal(goal["id"])
    assert events.counts().get("goal_reopened") == 1
    assert events.counts().get("goal_opened") == 2


def test_action_home_states_and_no_pseudo_precision(product_env):
    s = home.summary()
    assert s["state"] == "NO_GOAL" and s["primary_action"]["label"] == "创建第一个求职目标"
    goal = goals.create_goal("MindRank", "AIDD Agent Engineer")
    goals.add_interview(goal["id"], round_name="技术二面", scheduled_at=store.now() + 86400)
    s = home.summary()
    assert s["state"] == "GOAL_NO_SESSION" and s["primary_action"]["label"] == "继续准备"
    assert s["next_interview"]["company"] == "MindRank"
    assert [a["label"] for a in s["next_interview"]["actions"]] == ["继续准备", "开始练习", "Preflight"]
    flat = repr(s)
    for forbidden in ("readiness", "probability", "percentile", "score"):
        assert forbidden not in flat.lower()


def test_quick_notes_crud_reorder_pin_scope_and_conflict(product_env):
    goal = goals.create_goal("A", "B")
    g1 = quick_notes.create_note("全局要点")
    g2 = quick_notes.create_note("目标要点", scope="GOAL", goal_id=goal["id"], pinned=True)
    other = goals.create_goal("C", "D")
    quick_notes.create_note("别的目标", scope="GOAL", goal_id=other["id"])
    visible = quick_notes.list_notes(goal["id"])
    assert [n["id"] for n in visible] == [g2["id"], g1["id"]]  # pinned first, other goal hidden
    quick_notes.reorder([g1["id"], g2["id"]])
    updated = quick_notes.update_note(g1["id"], {"content": "改过"}, base_revision=1)
    assert updated["revision"] == 2
    with pytest.raises(quick_notes.QuickNoteConflict):
        quick_notes.update_note(g1["id"], {"content": "旧版本覆盖"}, base_revision=1)
    with pytest.raises(quick_notes.QuickNoteError):
        quick_notes.create_note("", title="")
    assert quick_notes.delete_note(g1["id"]) is True


def test_quick_note_is_never_evidence(product_env):
    from services.storage import intelligence as intel

    before = intel.list_claims(intel.active_candidate_id() or "x")
    note = quick_notes.create_note("我做过 Redis Cluster")
    assert intel.list_claims(intel.active_candidate_id() or "x") == before
    goal = goals.create_goal("A", "B")
    goals.update_goal(goal["id"], {"selected_quick_note_ids": [note["id"]]})
    pack_notes = quick_notes.notes_for_pack(goals.require_goal(goal["id"]))
    assert pack_notes[0]["kind"] == "USER_NOTE" and pack_notes[0]["is_evidence"] is False


def test_compiler_renders_quick_notes_as_non_evidence(product_env):
    from services.intelligence.context_compiler import InterviewPackUserNoteProvider, render_context_sections
    from services.intelligence.interview_pack import InterviewPack
    from services.intelligence.types import CompiledContext

    pack = InterviewPack(id="p", session_id="s", revision=1, payload={
        "user_notes": [{"id": "qn1", "title": "Redis", "content": "我做过 Redis Cluster", "kind": "USER_NOTE"}]})
    items = InterviewPackUserNoteProvider(pack).collect("Redis Cluster 怎么做的")
    assert items and items[0].metadata["cue_source"] == "USER_NOTE"
    assert items[0].metadata["cue_source"] != "PERSONAL_EVIDENCE"
    rendered = render_context_sections(CompiledContext(items=items))
    assert "用户速记，不是证据" in rendered[0]


def test_next_focus_is_bounded_explained_and_user_items_win(product_env):
    goal = goals.create_goal("MindRank", "AIDD Agent Engineer", "任职要求：\n熟悉 Redis Cluster\n熟悉 Kafka\n系统设计能力")
    items = next_focus.recompute(goal["id"])
    assert 1 <= len(items) <= 3
    for item in items:
        assert item["reason"] and item["source_kind"] and item["actions"]
    user = next_focus.set_user_focus(goal["id"], "OWNERSHIP", "Ownership 表达", "复盘发现")
    top = next_focus.active_items(goal["id"])[0]
    assert top["id"] == user["id"] and len(next_focus.active_items(goal["id"])) <= 3
    assert goals.require_goal(goal["id"])["next_focus_id"] == user["id"]
    assert next_focus.practice_defaults(goal["id"])["round"] == "PROJECT_DEEP_DIVE"
