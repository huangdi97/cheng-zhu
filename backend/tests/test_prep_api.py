"""准备空间 API 测试（直接调用端点函数 + mock LLM 服务）。"""

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.prep.router import (
    api_create_space,
    api_delete_space,
    api_generate_space,
    api_get_space,
    CreateSpaceRequest,
)
from services.storage import prep_space
from services import prep_service


def test_create_get_delete_space():
    req = CreateSpaceRequest(
        title="后端准备空间", role="后端开发", company="某公司",
        jd_text="JD", resume_text="简历",
    )
    space = asyncio.run(api_create_space(req))
    sid = space["id"]
    try:
        got = asyncio.run(api_get_space(sid))
        assert got["role"] == "后端开发"
        assert got["company"] == "某公司"
    finally:
        assert asyncio.run(api_delete_space(sid)) == {"ok": True}


def test_create_requires_some_content():
    req = CreateSpaceRequest()
    try:
        asyncio.run(api_create_space(req))
        assert False, "应拒绝空内容"
    except Exception as e:
        assert "请至少填写" in str(e)


def test_generate_runs_all_parts(monkeypatch):
    sid = prep_space.create_space(
        title="t", role="后端开发", company="c", jd_text="JD", resume_text="简历"
    )
    try:
        calls = []

        def fake_insight(*a, **k):
            calls.append("insight")
            return {"markdown": "### 洞察", "focus_points": [], "strengths": [], "gaps": []}

        def fake_cards(*a, **k):
            calls.append("cards")
            return [{
                "name": "项目A", "background": "b", "my_role": "r",
                "tech_decisions": [], "metrics": [], "tradeoffs": [],
                "likely_follow_ups": [],
            }]

        def fake_questions(*a, **k):
            calls.append("questions")
            return [{"question": "q1", "type": "technical", "why": "w"}]

        monkeypatch.setattr(prep_service, "prep_configured", lambda: True)
        monkeypatch.setattr(prep_service, "generate_insight", fake_insight)
        monkeypatch.setattr(prep_service, "generate_skill_cards", fake_cards)
        monkeypatch.setattr(prep_service, "generate_questions", fake_questions)

        space = asyncio.run(api_generate_space(sid))
        assert calls == ["insight", "cards", "questions"]
        assert space["insight_status"] == "done"
        assert space["insight_markdown"] == "### 洞察"
        assert len(space["skill_cards"]) == 1
        assert space["skill_cards"][0]["status"] == "done"
        assert space["questions"][0]["question"] == "q1"
    finally:
        prep_space.delete_space(sid)


def test_generate_records_partial_failure(monkeypatch):
    sid = prep_space.create_space(title="t", role="后端开发", jd_text="JD", resume_text="简历")
    try:
        def fake_insight(*a, **k):
            raise RuntimeError("模型不可用")

        def fake_cards(*a, **k):
            return []

        def fake_questions(*a, **k):
            return []

        monkeypatch.setattr(prep_service, "prep_configured", lambda: True)
        monkeypatch.setattr(prep_service, "generate_insight", fake_insight)
        monkeypatch.setattr(prep_service, "generate_skill_cards", fake_cards)
        monkeypatch.setattr(prep_service, "generate_questions", fake_questions)

        space = asyncio.run(api_generate_space(sid))
        assert space["insight_status"] == "failed"
        assert space["insight_error"] != ""
        assert space["questions_status"] == "done"
    finally:
        prep_space.delete_space(sid)