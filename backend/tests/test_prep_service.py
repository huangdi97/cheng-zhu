"""准备空间 LLM 服务测试（mock 模型客户端，不发真实请求）。"""

import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest

from services import prep_service


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return _Resp(self._content)


class _Client:
    def __init__(self, content):
        self.chat = SimpleNamespace(completions=_Completions(content))


@pytest.fixture
def fake_llm(monkeypatch):
    holder = {}

    def fake_get_active_llm_client():
        return _Client(holder["content"]), "fake-model"

    monkeypatch.setattr(prep_service, "get_active_llm_client", fake_get_active_llm_client)
    return holder


def test_extract_json_fenced():
    assert prep_service._extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_plain():
    assert prep_service._extract_json('{"b": 2}') == {"b": 2}


def test_generate_insight(fake_llm):
    fake_llm["content"] = (
        '{"markdown": "### 洞察", "focus_points": ["考察点1"], '
        '"strengths": ["亮点1"], "gaps": ["短板1"]}'
    )
    result = prep_service.generate_insight("后端开发", "某公司", "JD", "简历")
    assert result["markdown"] == "### 洞察"
    assert result["focus_points"] == ["考察点1"]
    assert result["gaps"] == ["短板1"]


def test_generate_skill_cards(fake_llm):
    fake_llm["content"] = (
        '{"projects": [{"name": "缓存优化", "background": "b", "my_role": "r", '
        '"tech_decisions": ["决策1"], "metrics": ["指标1"], "tradeoffs": ["取舍1"], '
        '"likely_follow_ups": ["追问1"]}]}'
    )
    cards = prep_service.generate_skill_cards("后端开发", "JD", "简历")
    assert len(cards) == 1
    assert cards[0]["name"] == "缓存优化"
    assert cards[0]["tech_decisions"] == ["决策1"]
    assert cards[0]["likely_follow_ups"] == ["追问1"]


def test_generate_questions(fake_llm):
    fake_llm["content"] = '{"questions": [{"question": "q1", "type": "project", "why": "w"}]}'
    qs = prep_service.generate_questions("后端开发", "公司", "JD", "简历", "# 洞察", [])
    assert len(qs) == 1
    assert qs[0]["question"] == "q1"
    assert qs[0]["type"] == "project"


def test_prep_configured_false_when_no_key(monkeypatch):
    class M:
        api_key = "YOUR_API_KEY_HERE"

    class Cfg:
        def get_review_model(self):
            return M()

    monkeypatch.setattr(prep_service, "get_config", lambda: Cfg())
    assert prep_service.prep_configured() is False


def test_prep_configured_true_when_key(monkeypatch):
    class M:
        api_key = "sk-real-key"

    class Cfg:
        def get_review_model(self):
            return M()

    monkeypatch.setattr(prep_service, "get_config", lambda: Cfg())
    assert prep_service.prep_configured() is True


def test_build_launch_pack_uses_only_existing_prep_evidence():
    pack = prep_service.build_launch_pack({
        "id": 3,
        "title": "后端面试",
        "role": "后端开发",
        "company": "示例公司",
        "jd_text": "高并发",
        "resume_text": "缓存项目",
        "insight_markdown": "### 重点\n- 缓存一致性",
        "questions": [{"question": "如何保证缓存一致性", "type": "technical"}],
        "skill_cards": [{
            "project_name": "缓存项目",
            "card": {
                "name": "缓存项目",
                "background": "降低数据库压力",
                "my_role": "负责缓存层",
                "tech_decisions": ["使用 Redis"],
                "metrics": ["延迟降低"],
                "likely_follow_ups": ["Redis 故障怎么办"],
            },
        }],
    })

    assert pack["readiness"] == {
        "has_jd": True,
        "has_resume": True,
        "project_count": 1,
        "question_count": 1,
    }
    assert pack["project_anchors"][0]["name"] == "缓存项目"
    assert pack["risk_prompts"] == ["Redis 故障怎么办"]
