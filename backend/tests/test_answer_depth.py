"""Depth and continuity contracts for open-ended interview answers."""

from __future__ import annotations

from services.answer_depth import (
    build_answer_depth_contract,
    build_conversation_bridge,
    classify_answer_depth,
    topic_overlap,
)
from services.llm.prompts import build_system_prompt


def test_synthetic_data_opinion_is_deep_even_when_realtime_concise_is_default(monkeypatch):
    from core.config import get_config

    cfg = get_config()
    old = cfg.assist_realtime_concise_answer
    cfg.assist_realtime_concise_answer = True
    try:
        question = "你对合成数据有什么看法？"
        profile = classify_answer_depth(question)
        assert profile == "deep"
        prompt = build_system_prompt(
            mode="asr_realtime",
            question_text=question,
            answer_depth_profile=profile,
        )
    finally:
        cfg.assist_realtime_concise_answer = old

    assert "合成数据专项深度要求" in prompt
    assert "fidelity" in prompt
    assert "utility" in prompt
    assert "privacy/leakage" in prompt
    assert "100-150 字以内" not in prompt
    assert "验证指标" in prompt


def test_definition_remains_fast_and_high_churn_followup_keeps_multiple_dimensions():
    assert classify_answer_depth("Redis 默认端口是多少？") == "concise"
    assert classify_answer_depth("那如果要验证呢？", high_churn_short_answer=True) == "compact_deep"
    contract = build_answer_depth_contract(
        "那如果要验证呢？",
        profile="compact_deep",
        relation_to_previous="follow_up",
    )
    assert "至少覆盖 3 个不同维度" in contract
    assert "验证指标" in contract


def test_conversation_bridge_selects_related_previous_answer_and_candidate_words():
    previous = [
        {
            "question": "HTTP 和 HTTPS 有什么区别？",
            "answer": "HTTPS 在 HTTP 上增加 TLS。",
        },
        {
            "question": "讲讲你做过的风控规则引擎",
            "answer": "助手建议答案：规则按优先级匹配，并支持灰度发布和回滚。",
        },
    ]
    bridge = build_conversation_bridge(
        "风控规则冲突时怎么处理？",
        recent_qas=previous,
        candidate_answer="我实际讲了误杀率看板和规则回滚。",
    )
    assert bridge
    assert "风控规则引擎" in bridge
    assert "规则按优先级" in bridge
    assert "误杀率看板" in bridge
    assert "不等于候选人事实" in bridge
    assert "HTTP 和 HTTPS" not in bridge


def test_conversation_bridge_omits_unrelated_history():
    bridge = build_conversation_bridge(
        "MySQL 索引为什么使用 B+ 树？",
        recent_qas=[
            {
                "question": "讲讲你做过的风控项目",
                "answer": "规则引擎支持灰度发布。",
            }
        ],
        candidate_answer="我讲的是规则回滚。",
    )
    assert bridge == ""
    assert topic_overlap("MySQL 索引为什么使用 B+ 树", "风控项目 规则引擎") < 0.08
