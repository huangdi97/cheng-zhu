from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services import copilot_strategy


def _tree() -> dict:
    return {
        "root_nodes": ["n1", "n2"],
        "nodes": {
            "n1": {
                "id": "n1",
                "label": "项目深挖",
                "intent": "project",
                "sample_questions": ["介绍一下你负责的支付项目", "项目里遇到最大的困难是什么", "这个项目你承担什么角色"],
                "children": ["n1a"],
                "high_risk": True,
                "risk_advice": "准备好指标、取舍与复盘",
                "advice": "先讲背景再讲动作",
            },
            "n1a": {
                "id": "n1a",
                "label": "高并发改造",
                "intent": "technical",
                "sample_questions": ["如果并发翻十倍你怎么改", "讲讲你们的高并发方案"],
                "children": [],
                "high_risk": True,
                "risk_advice": "准备限流/降级/缓存方案",
                "advice": "",
            },
            "n2": {
                "id": "n2",
                "label": "自我介绍",
                "intent": "opening",
                "sample_questions": ["先做个自我介绍", "介绍一下你自己"],
                "children": [],
                "high_risk": False,
                "risk_advice": "",
                "advice": "",
            },
        },
    }


def test_match_question_hits_most_similar_node():
    tree = _tree()
    copilot_strategy.reset_current_node()
    hint = copilot_strategy.match_question(tree, "你项目里遇到的最大困难是什么")
    assert hint.get("node_id") == "n1"
    assert hint.get("high_risk") is True
    assert hint.get("risk_advice") == "准备好指标、取舍与复盘"
    assert any(f.get("label") == "高并发改造" for f in hint.get("predicted_followups", []))


def test_match_question_followup_falls_back_to_previous_node():
    tree = _tree()
    copilot_strategy.reset_current_node()
    copilot_strategy.match_question(tree, "介绍一下你负责的支付项目")
    hint = copilot_strategy.match_question(tree, "然后呢")
    assert hint.get("node_id") == "n1"


def test_current_strategy_node_is_isolated_by_session():
    tree = _tree()
    copilot_strategy.reset_current_node("session-a")
    copilot_strategy.reset_current_node("session-b")
    first = copilot_strategy.match_question(tree, "介绍一下你负责的支付项目", "session-a")
    assert first.get("node_id") == "n1"

    unrelated = copilot_strategy.match_question(tree, "然后呢", "session-b")
    assert unrelated.get("inferred_from_previous") is not True

    followup = copilot_strategy.match_question(tree, "然后呢", "session-a")
    assert followup.get("node_id") == "n1"
    assert followup.get("inferred_from_previous") is True


def test_validate_tree_drops_invalid():
    assert copilot_strategy._validate_tree({"nodes": {"x": {}}}) is None
    assert copilot_strategy._validate_tree({"nodes": {"x": {"sample_questions": ["q"]}}}) is not None
    assert copilot_strategy._validate_tree(None) is None
