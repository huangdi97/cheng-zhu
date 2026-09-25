"""模拟面试练习 API 测试（mock practice_service）。"""

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.prep.router import (
    api_practice_start,
    api_practice_answer,
    api_practice_finish,
    StartPracticeRequest,
    PracticeAnswerRequest,
)
from services import practice_service, prep_service


def _mock_services(monkeypatch):
    monkeypatch.setattr(prep_service, "prep_configured", lambda: True)
    monkeypatch.setattr(
        practice_service, "start_session",
        lambda space_id, rounds: {
            "practice_id": "p1", "rounds": rounds,
            "question": {"question": "q1", "type": "technical", "why": "w"},
        },
    )
    monkeypatch.setattr(
        practice_service, "submit_answer",
        lambda pid, answer: {
            "done": False, "answered": 1,
            "feedback": {"strengths": ["s"]},
            "next_question": {"question": "追问", "type": "follow_up", "why": ""},
        },
    )
    monkeypatch.setattr(
        practice_service, "finish_session",
        lambda pid: {"done": True, "report": {"turn_count": 1}},
    )


def test_practice_start(monkeypatch):
    _mock_services(monkeypatch)
    r = asyncio.run(api_practice_start(StartPracticeRequest(space_id=1, rounds=3)))
    assert r["practice_id"] == "p1"
    assert r["rounds"] == 3


def test_practice_answer(monkeypatch):
    _mock_services(monkeypatch)
    r = asyncio.run(api_practice_answer("p1", PracticeAnswerRequest(answer="我的回答")))
    assert r["done"] is False
    assert r["feedback"]["strengths"] == ["s"]


def test_practice_finish(monkeypatch):
    _mock_services(monkeypatch)
    r = asyncio.run(api_practice_finish("p1"))
    assert r["done"] is True
    assert r["report"]["turn_count"] == 1


def test_practice_start_requires_key(monkeypatch):
    monkeypatch.setattr(prep_service, "prep_configured", lambda: False)
    try:
        asyncio.run(api_practice_start(StartPracticeRequest(space_id=1, rounds=3)))
        assert False, "应拒绝未配置模型"
    except Exception as e:
        assert "API Key" in str(e)