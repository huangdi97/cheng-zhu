"""v1.4 G25–G34: local analytics privacy, validation report, transfer, export/delete, integrity,
longitudinal synthetic dogfood, future-profile boundary."""
import json

from services.product import data_export, dogfood, events, future_profile, goals, practice, quick_notes, validation
from services.storage import product as store


def test_events_are_local_and_never_carry_free_text(product_env):
    assert events.record("goal_created", goal_id="g1", resume_text="张三 简历全文", api_key="sk-x", transcript="原话",
                         answer_text="回答", count=3, ok=True, note="这是一段很长的自由文本，不应该被原样记录下来")
    row = events.list_events("goal_created")[0]
    props = row["props"]
    assert "resume_text" not in props and "api_key" not in props and "transcript" not in props
    assert "answer_text" not in props and props["count"] == 3 and props["ok"] is True
    assert "note" not in props and len(props["note_hash"]) == 12
    assert events.record("not_a_real_event") is False


def test_validation_report_covers_the_six_questions_and_never_claims_pmf(product_env):
    goal = goals.create_goal("A", "B")
    s = practice.start({"goal_id": goal["id"], "round": "TECHNICAL", "sources": ["ROLE_BANK"], "questions": 1,
                        "closing": False})
    practice.answer(s["practice_id"], "我们做了缓存。")
    report = validation.report()
    for key in ("A_goal_reuse", "B_reflection_to_prepare", "C_fast_cue_usefulness", "D_practice_transfer",
                "E_fact_inbox_burden", "F_quick_notes_and_pins"):
        assert key in report
    assert report["real_user_validation"] == "REAL_USER_VALIDATION_PENDING"
    assert report["evidence_level"] == "LOCAL_DEVICE_USAGE"
    assert "PMF proven" not in json.dumps(report, ensure_ascii=False)
    cue = report["C_fast_cue_usefulness"]
    assert {"usefulness", "accuracy", "personal_fact_safety", "latency", "readability", "over_specificity"} <= set(cue)
    assert "score" not in json.dumps(cue).lower()


def test_export_and_delete_keep_integrity(product_env):
    goal = goals.create_goal("A", "B")
    note = quick_notes.create_note("n", scope="GOAL", goal_id=goal["id"])
    goals.update_goal(goal["id"], {"selected_quick_note_ids": [note["id"]]})
    s = practice.start({"goal_id": goal["id"], "round": "TECHNICAL", "sources": ["ROLE_BANK"], "questions": 1,
                        "closing": False})
    report = practice.answer(s["practice_id"], "我们做了缓存。")["report"]
    for kind, args in (("goal", (goal["id"],)), ("session", ("PRACTICE", s["practice_id"])),
                       ("reflection", ("PRACTICE", s["practice_id"]))):
        out = getattr(data_export, f"export_{kind}")(*args)
        assert out["path"].endswith(".json") and json.load(open(out["path"], encoding="utf-8"))
    assert data_export.export_quick_notes()["data"]["quick_notes"]
    data_export.export_question_banks()

    # a dangling ref (note deleted behind the goal's back) is detected and repaired
    store.delete("quick_note", note["id"])
    found = data_export.integrity()
    assert not found["ok"] and found["issues"][0]["kind"] == "GOAL_DANGLING_REF"
    assert data_export.integrity(repair=True)["repaired"] and data_export.integrity()["ok"]

    removed = data_export.delete_session("PRACTICE", s["practice_id"])
    assert removed["review_deleted"] is True and removed["integrity"]["ok"]
    assert not goals.session_links(goal["id"])
    from services.storage import review

    assert review.get_session_detail(report["review_session_id"]) is None


def test_practice_transfer_is_labelled_mock_to_mock(product_env):
    from services.product import next_focus

    goal = goals.create_goal("A", "B")
    for answer in ("我们一起做的。", "我们一起做的。"):
        s = practice.start({"goal_id": goal["id"], "round": "PROJECT_DEEP_DIVE", "sources": ["ROLE_BANK"],
                            "questions": 1, "closing": False})
        practice.answer(s["practice_id"], answer)
    next_focus.set_user_focus(goal["id"], "OWNERSHIP", "Ownership", "复盘")
    s = practice.start({"goal_id": goal["id"], "round": "PROJECT_DEEP_DIVE", "sources": ["ROLE_BANK"], "questions": 1,
                        "closing": False})
    practice.answer(s["practice_id"], "结论是我负责重排模块，我设计了方案并推动上线。")
    t = validation.practice_transfer(goal["id"])
    assert t["measured"] >= 1 and t["links"][0]["evidence_type"] == "MOCK_TO_MOCK"
    assert t["links"][0]["after_level"] > t["links"][0]["before_level"]


def test_seven_day_synthetic_continuity(product_env, monkeypatch):
    out = dogfood.run_week(lambda clock: monkeypatch.setattr(store, "now", clock))
    failed = [k for k, v in out["checks"].items() if not v]
    assert not failed, failed
    assert validation.evidence_level() == "SYNTHETIC_DOGFOOD"


def test_thirty_session_synthetic_continuity(product_env, monkeypatch):
    out = dogfood.run_sessions(30, lambda clock: monkeypatch.setattr(store, "now", clock))
    failed = [k for k, v in out["checks"].items() if not v]
    assert not failed, failed


def test_future_profile_is_retained_but_not_productized():
    keys = {k.value for k in future_profile.GuidanceKind}
    assert keys == {"RECALL", "TALKING_POINT", "ANSWER_CUE", "QUESTION", "RISK", "DELIVERY", "CONTRIBUTION_OPPORTUNITY"}
    states = {s.value for s in future_profile.ConversationItemState}
    assert states == {"PROPOSED", "AGREED", "COMMITTED", "DONE", "SUPERSEDED", "UNKNOWN"}
    conversation = next(p for p in future_profile.PROFILES if p.key == "conversation")
    assert conversation.productized is False
    goal = future_profile.interview_goal_as_conversation_goal({"id": "g", "title": "MindRank · AIDD", "company": "MindRank"})
    assert goal.profile == "interview" and "job" not in goal.attributes


def test_shared_product_layer_does_not_hard_code_job():
    """Future Profile gate: v1.3 shared tables use Goal/Person vocabulary, not job."""
    from services.storage.product_migrations import _V1_TABLES

    shared = [t for t in _V1_TABLES if any(name in t for name in ("quick_note", "pin_moment", "next_focus",
                                                                    "product_event", "reflection_action"))]
    assert shared and all("job_id" not in t for t in shared)
