"""交互式技能卡工作台测试（mock LLM 与存储）。"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest

from services import skill_builder


def _space():
    return {
        "id": 1, "title": "t", "role": "后端开发", "company": "某公司",
        "jd_text": "JD", "resume_text": "简历：做过订单履约中台重构、缓存优化两个项目。",
        "questions": [], "skill_cards": [],
    }


def _fake_llm(monkeypatch, saved_cards=None):
    """按调用次数返回：projects -> plan -> card(s)。"""
    calls = {"n": 0}

    def fake_chat_json(system, prompt, max_tokens=1600):
        calls["n"] += 1
        if "名称列表" in prompt:
            return {"projects": ["订单履约中台重构", "缓存优化"]}
        if "设计 6 条追问" in prompt or "设计 6 条追问" in system:
            return {"questions": [f"追问{i}" for i in range(1, 7)]}
        return {
            "name": "订单履约中台重构", "background": "单体架构瓶颈",
            "my_role": "核心开发", "tech_decisions": ["Kafka 削峰"],
            "metrics": ["吞吐提升5倍"], "tradeoffs": ["最终一致"],
            "likely_follow_ups": ["消息乱序怎么处理"],
        }

    monkeypatch.setattr(skill_builder, "_chat_json", fake_chat_json)
    monkeypatch.setattr(skill_builder.prep_storage, "get_space", lambda sid: _space())
    store = {"cards": []}
    monkeypatch.setattr(
        skill_builder.prep_storage, "add_skill_card",
        lambda space_id, name: (store["cards"].append({"name": name}), 100 + len(store["cards"]))[1],
    )
    monkeypatch.setattr(
        skill_builder.prep_storage, "update_skill_card",
        lambda card_id, card, status, error="": store["cards"].append(card),
    )
    return calls, store


def test_start_session_returns_first_question(monkeypatch):
    calls, _ = _fake_llm(monkeypatch)
    r = skill_builder.start_session(1)
    assert r["builder_id"]
    assert r["project"] == "订单履约中台重构"
    assert r["question_total"] == 6
    assert r["question_index"] == 1
    assert calls["n"] >= 2  # 提取项目 + 问题清单


def test_answer_through_project_and_move_next(monkeypatch):
    calls, store = _fake_llm(monkeypatch)
    r = skill_builder.start_session(1)
    bid = r["builder_id"]
    for i in range(6):
        r = skill_builder.answer(bid, f"回答{i + 1}")
    assert r["done"] is False
    assert r["card_saved"]["name"] == "订单履约中台重构"
    assert r["project"] == "缓存优化"
    assert r["question_index"] == 1
    assert len(store["cards"]) >= 2  # add + update 都记录


def test_answer_all_projects_done(monkeypatch):
    calls, store = _fake_llm(monkeypatch)
    r = skill_builder.start_session(1)
    bid = r["builder_id"]
    # 第一个项目 6 问
    for i in range(6):
        r = skill_builder.answer(bid, f"a{i}")
    # 第二个项目 6 问
    for i in range(6):
        r = skill_builder.answer(bid, f"b{i}")
    assert r["done"] is True
    assert r["card_saved"]["name"] == "订单履约中台重构"


def test_skip_finalizes_current(monkeypatch):
    calls, store = _fake_llm(monkeypatch)
    r = skill_builder.start_session(1)
    bid = r["builder_id"]
    skill_builder.answer(bid, "只答了第一问")
    r = skill_builder.skip(bid)
    assert r["done"] is False
    assert r["card_saved"] is not None
    assert r["project"] == "缓存优化"


def test_empty_answer_rejected(monkeypatch):
    calls, store = _fake_llm(monkeypatch)
    r = skill_builder.start_session(1)
    with pytest.raises(ValueError):
        skill_builder.answer(r["builder_id"], "   ")


def test_start_requires_resume(monkeypatch):
    monkeypatch.setattr(skill_builder.prep_storage, "get_space", lambda sid: {** _space(), "resume_text": "太短"})
    with pytest.raises(ValueError):
        skill_builder.start_session(1)