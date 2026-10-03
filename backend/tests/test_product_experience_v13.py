from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.storage import product_experience as px  # noqa: E402
from services import practice_service  # noqa: E402


@pytest.fixture()
def product_db(tmp_path, monkeypatch):
    monkeypatch.setattr(px, "DB_PATH", str(tmp_path / "product_experience.db"))
    px.init_db()
    return tmp_path


def test_goal_meta_round_trip(product_db):
    value = px.upsert_goal_meta(
        7,
        stage="interview",
        interview_round="技术二面",
        next_interview_at=1234.5,
        next_focus=[{"title": "Ownership", "reason": "recent reflection"}],
        offer={"status": "none"},
    )
    assert value["space_id"] == 7
    assert value["stage"] == "interview"
    assert value["interview_round"] == "技术二面"
    assert value["next_focus"][0]["title"] == "Ownership"
    assert px.event_summary(7)["events"]["goal_meta_updated"] == 1


def test_quick_note_is_goal_scoped_but_global_notes_are_visible(product_db):
    global_note = px.create_quick_note(title="通用", content="先结论", scope="GLOBAL")
    goal_note = px.create_quick_note(title="MindRank", content="Redis", scope="GOAL", goal_id=9)
    other_note = px.create_quick_note(title="Other", content="Kafka", scope="GOAL", goal_id=10)

    visible = px.list_quick_notes(9)
    assert {n["id"] for n in visible} == {global_note["id"], goal_note["id"]}
    assert other_note["id"] not in {n["id"] for n in visible}

    updated = px.update_quick_note(goal_note["id"], {"pinned": True, "content": "Redis\n- TTL"})
    assert updated and updated["pinned"] == 1
    assert "TTL" in updated["content"]
    assert px.delete_quick_note(goal_note["id"]) is True


def test_question_bank_and_items(product_db):
    bank = px.create_question_bank(name="AI Agent", role="AI Engineer")
    item = px.add_question_item(
        bank["id"],
        question="RAG 与 fine-tuning 如何取舍？",
        category="technical",
        difficulty="standard",
        origin="USER_ADDED",
    )
    assert item["bank_id"] == bank["id"]
    detail = px.get_question_bank(bank["id"])
    assert detail and detail["items"][0]["question"].startswith("RAG")
    assert px.list_question_items([bank["id"]])[0]["id"] == item["id"]


def test_pin_and_local_event_summary(product_db):
    pin = px.create_pin(
        session_id="s1",
        goal_id=3,
        turn_id="q2",
        label="BAD_ANSWER",
        question="怎么扩容？",
        note="下一场重练",
    )
    assert pin["label"] == "BAD_ANSWER"
    assert px.list_pins(session_id="s1")[0]["id"] == pin["id"]
    summary = px.event_summary(3)["events"]
    assert summary["pin_created"] == 1


def test_practice_config_and_panel_turn_taking():
    cfg = practice_service._normalize_config(
        {
            "round_type": "system_design",
            "persona": "Tech Lead",
            "demeanor": "skeptical",
            "difficulty": "pressure",
            "panel_personas": [
                {"role": "Tech Lead", "demeanor": "skeptical"},
                {"role": "Hiring Manager", "demeanor": "neutral"},
            ],
        }
    )
    session = {"config": cfg, "turns": []}
    assert practice_service._persona_for_turn(session)["role"] == "Tech Lead"
    session["turns"].append({})
    assert practice_service._persona_for_turn(session)["role"] == "Hiring Manager"
    assert practice_service._pressure_followup("你怎么设计？", "很短", cfg)


def test_delivery_coach_is_actionable_not_one_composite_score():
    feedback = practice_service._delivery_feedback("因为背景很多。" * 80)
    assert "score" not in feedback
    assert feedback["answer_chars"] > 100
    assert isinstance(feedback["findings"], list)
