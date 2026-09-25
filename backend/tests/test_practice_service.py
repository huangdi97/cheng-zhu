"""模拟面试练习服务测试（mock LLM 分析与复盘落库）。"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest

from services import practice_service


def _space(questions=None):
    return {
        "id": 1, "title": "t", "role": "后端开发", "company": "某公司",
        "jd_text": "JD", "resume_text": "简历", "insight_markdown": "# 洞察",
        "questions": questions if questions is not None else [
            {"question": "q1", "type": "technical", "why": "w1"},
            {"question": "q2", "type": "project", "why": "w2"},
        ],
        "skill_cards": [],
    }


@pytest.fixture
def env(monkeypatch):
    calls = {"create_session": [], "add_turn": [], "end_session": []}

    monkeypatch.setattr(practice_service.prep_storage, "get_space", lambda sid: _space())
    monkeypatch.setattr(practice_service.prep_storage, "update_questions", lambda *a, **k: None)

    def fake_analyze(question, answer, reference_answer="", apply_asr_correction=True, review_source="assist"):
        return {
            "strengths": ["亮点1"],
            "risks": ["风险1"],
            "scorecard": {"准确性": 8, "深度": 7},
            "evidence": {
                "improvement_advice": "建议补充一个踩坑",
                "follow_up_questions": ["追问1", "追问2"],
                "tags": ["Redis"],
            },
        }

    monkeypatch.setattr(practice_service.review_analysis, "analyze_turn", fake_analyze)

    def fake_summary(turns, review_source="assist"):
        return {
            "summary_markdown": "## 整体总结",
            "strong_points": ["表达清晰"],
            "weak_points": ["深度不足"],
        }

    monkeypatch.setattr(practice_service.review_analysis, "generate_summary", fake_summary)
    monkeypatch.setattr(
        practice_service.review_storage, "create_session",
        lambda *a, **kw: calls["create_session"].append((a, kw)) or 100,
    )
    monkeypatch.setattr(
        practice_service.review_storage, "add_turn",
        lambda *a, **kw: calls["add_turn"].append((a, kw)) or 1,
    )
    monkeypatch.setattr(
        practice_service.review_storage, "end_session",
        lambda *a, **kw: calls["end_session"].append((a, kw)),
    )
    return calls


def test_start_session_returns_first_question(env):
    r = practice_service.start_session(1, rounds=3)
    assert r["practice_id"]
    assert r["question"]["question"] == "q1"
    assert r["rounds"] == 3


def test_start_session_generates_questions_when_missing(monkeypatch):
    monkeypatch.setattr(practice_service.prep_storage, "get_space", lambda sid: _space(questions=[]))
    generated = [{"question": "g1", "type": "technical", "why": "w"}]
    monkeypatch.setattr(
        practice_service.prep_service, "generate_questions",
        lambda *a, **k: generated,
    )
    updated = {}
    monkeypatch.setattr(
        practice_service.prep_storage, "update_questions",
        lambda sid, qs, status, error="": updated.update({"sid": sid, "qs": qs}),
    )
    r = practice_service.start_session(1, rounds=2)
    assert r["question"]["question"] == "g1"
    assert updated["qs"] == generated


def test_submit_answer_follows_up_then_finishes(env):
    r = practice_service.start_session(1, rounds=2)
    pid = r["practice_id"]

    a1 = practice_service.submit_answer(pid, "我的回答1")
    assert a1["done"] is False
    assert a1["answered"] == 1
    assert a1["feedback"]["strengths"] == ["亮点1"]
    assert a1["feedback"]["improvement_advice"] != ""
    assert a1["next_question"]["type"] == "follow_up"
    assert a1["next_question"]["question"] == "追问1"

    a2 = practice_service.submit_answer(pid, "我的回答2")
    assert a2["done"] is True
    assert a2["report"]["review_session_id"] == 100
    assert a2["report"]["turn_count"] == 2
    assert a2["report"]["avg_score"] == 7.5
    assert a2["report"]["summary_markdown"] == "## 整体总结"
    assert len(env["add_turn"]) == 2
    assert env["end_session"][0][1]["strong_points"] == ["表达清晰"]


def test_finish_early(env):
    r = practice_service.start_session(1, rounds=5)
    pid = r["practice_id"]
    practice_service.submit_answer(pid, "答")
    rep = practice_service.finish_session(pid)
    assert rep["done"] is True
    assert rep["report"]["turn_count"] == 1
    assert len(env["add_turn"]) == 1
    assert env["end_session"][0][1]["summary_markdown"] == "## 整体总结"


def test_empty_answer_rejected(env):
    r = practice_service.start_session(1, rounds=2)
    with pytest.raises(ValueError):
        practice_service.submit_answer(r["practice_id"], "   ")


def test_submit_after_finish_rejected(env):
    r = practice_service.start_session(1, rounds=1)
    practice_service.submit_answer(r["practice_id"], "答")
    with pytest.raises(ValueError):
        practice_service.submit_answer(r["practice_id"], "再答")