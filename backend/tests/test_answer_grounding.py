from __future__ import annotations

from pathlib import Path
import sys

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.answer_grounding import (  # noqa: E402
    analyze_experience_grounding,
    enforce_experience_answer,
)


def test_technical_question_is_not_treated_as_personal_experience():
    result = analyze_experience_grounding("Redis 的 RDB 和 AOF 有什么区别？")

    assert result.applicable is False
    assert result.status == "not_applicable"


def test_open_project_prompt_uses_normal_resume_answering_not_object_guard():
    result = analyze_experience_grounding("你做过哪些项目？")

    assert result.applicable is False
    assert result.status == "not_applicable"


@pytest.mark.parametrize(
    "question",
    ["你用过什么缓存？", "你做过哪些数据库项目？", "Have you used any databases?"],
)
def test_open_ended_experience_question_uses_resume_answering_not_yes_no_guard(question: str):
    result = analyze_experience_grounding(question)

    assert result.applicable is False
    assert result.status == "not_applicable"


@pytest.mark.parametrize(
    "question",
    ["你有没有 Kafka 项目经验吗？", "你对 Kafka 有经验吗？", "你有 Kafka 的使用经验吗？"],
)
def test_experience_question_variants_lock_the_asked_subject(question: str):
    result = analyze_experience_grounding(question)

    assert result.applicable is True
    assert result.subject == "Kafka"
    assert result.status == "no_profile"


def test_experience_question_without_profile_is_conservative_and_locks_subject():
    result = analyze_experience_grounding("你做过 Redis 集群吗？")

    assert result.applicable is True
    assert result.status == "no_profile"
    assert result.subject == "Redis 集群"
    assert "当前被问对象：Redis 集群" in result.prompt_contract()
    assert "不能声称做过" in result.prompt_contract()
    assert "继续回答" in result.prompt_contract()


def test_unrelated_resume_does_not_authorize_affirmative_claim():
    result = analyze_experience_grounding(
        "你用过 Kafka 吗？",
        resume_text="负责订单系统开发，使用 MySQL 和 Redis。",
    )

    assert result.status == "unsupported"
    assert "MySQL" in result.evidence_excerpt
    assert "相近项目" in result.direct_answer()


def test_skill_list_is_related_only_not_project_proof():
    result = analyze_experience_grounding(
        "你做过 Kubernetes 吗？",
        resume_text="技能：Java、Kubernetes、Linux",
    )

    assert result.status == "related_only"


def test_project_action_with_subject_is_supported_evidence():
    result = analyze_experience_grounding(
        "你用过 Redis 吗？",
        resume_text="订单项目：使用 Redis 做热点缓存，并负责缓存一致性治理。",
    )

    assert result.status == "supported"
    assert "Redis" in result.evidence_excerpt


def test_composite_subject_requires_all_qualifiers_before_direct_support():
    result = analyze_experience_grounding(
        "你做过 Redis 集群吗？",
        resume_text="订单项目：使用 Redis 做热点缓存。",
    )

    assert result.status == "unsupported"
    assert "相近项目" in result.direct_answer()


def test_public_payload_does_not_expose_resume_evidence():
    result = analyze_experience_grounding(
        "你用过 Redis 吗？",
        resume_text="某客户私有项目：使用 Redis 做热点缓存。",
    )

    payload = result.public_payload()

    assert payload["status"] == "supported"
    assert payload["has_evidence"] is True
    assert "evidence_excerpt" not in payload
    assert "某客户" not in str(payload)


def test_negative_evidence_is_distinguished_from_missing_evidence():
    result = analyze_experience_grounding(
        "你做过 Flink 吗？",
        interview_notes="没有做过 Flink，只了解基本概念。",
    )

    assert result.status == "explicit_negative"


def test_missing_metric_does_not_negate_positive_project_evidence():
    result = analyze_experience_grounding(
        "你做过 Redis 吗？具体怎么做的？",
        resume_text=(
            "订单项目：我使用 Redis 做热点缓存，负责缓存一致性治理；"
            "没有提供线上规模或量化指标。"
        ),
    )

    assert result.status == "supported"
    answer = result.direct_answer()
    assert answer.startswith("做过，")
    assert "热点缓存" in answer
    assert "缓存旁路" not in answer


def test_guard_replaces_affirmative_or_unrelated_weak_model_answer():
    grounding = analyze_experience_grounding("你做过 Redis 吗？")

    answer, replaced = enforce_experience_answer(
        "我确实做过 Kafka 消息队列，线上吞吐量很高。",
        grounding,
    )

    assert replaced is True
    assert "没有直接做过 Redis" in answer
    assert "Redis" in answer
    assert "Kafka" not in answer


def test_guard_keeps_natural_model_answer_when_every_concrete_claim_is_in_evidence():
    grounding = analyze_experience_grounding(
        "你做过 Redis 吗？",
        resume_text="订单项目：使用 Redis 做热点缓存，并负责缓存一致性治理。",
    )

    answer, replaced = enforce_experience_answer(
        "做过，订单项目里我用 Redis 做过热点缓存，主要负责缓存一致性治理。",
        grounding,
    )

    assert replaced is False
    assert answer.startswith("做过，")
    assert "缓存一致性治理" in answer


def test_guard_falls_back_when_supported_model_adds_unlisted_technology_or_detail():
    grounding = analyze_experience_grounding(
        "你做过 Redis 吗？",
        resume_text="订单项目：使用 Redis 做热点缓存。",
    )

    answer, replaced = enforce_experience_answer(
        "做过，我在订单项目里用 Redis 和 Kafka 做缓存旁路，线上 QPS 达到 2 万。",
        grounding,
    )

    assert replaced is True
    assert "Kafka" not in answer
    assert "QPS" not in answer
    assert "热点缓存" in answer


def test_guard_renders_explicit_negative_from_fact_state():
    grounding = analyze_experience_grounding(
        "你做过 Redis 吗？",
        interview_notes="没有做过 Redis 的直接项目。",
    )

    answer, replaced = enforce_experience_answer(
        "我没有直接做过 Redis 项目，但了解缓存一致性的常见处理方式。",
        grounding,
    )

    assert replaced is False
    assert answer.startswith("我没有直接做过 Redis 项目")
    assert "缓存一致性" in answer


def test_guard_removes_internal_missing_resume_disclosure_and_unverified_skill_claim():
    grounding = analyze_experience_grounding("你做过 Redis 吗？")

    answer, replaced = enforce_experience_answer(
        "我这边没有挂载简历，不能替你确认。不过我掌握 Redis 的常用数据结构。",
        grounding,
    )

    assert replaced is True
    assert "Redis" in answer
    assert "挂载" not in answer
    assert "我掌握" not in answer
    assert "没有直接做过 Redis" in answer
    assert "通用方法" in answer


def test_unseen_topic_can_use_adjacent_resume_facts_without_claiming_direct_experience():
    grounding = analyze_experience_grounding(
        "你用过 Kafka 吗？",
        resume_text="负责订单系统开发，使用 MySQL 和 Redis。",
    )

    answer, replaced = enforce_experience_answer(
        "我没有直接做过 Kafka，但在订单系统里，我使用 MySQL 和 Redis。",
        grounding,
    )

    assert replaced is False
    assert "没有直接做过 Kafka" in answer
    assert "MySQL" in answer and "Redis" in answer
    assert "资料里没有" not in answer


def test_unseen_topic_rejects_unlisted_adjacent_detail_but_keeps_safe_fallback():
    grounding = analyze_experience_grounding(
        "你用过 Kafka 吗？",
        resume_text="负责订单系统开发，使用 MySQL 和 Redis。",
    )

    answer, replaced = enforce_experience_answer(
        "我没有直接做过 Kafka，但在 Redis 项目里做过双删和线上回滚。",
        grounding,
    )

    assert replaced is True
    assert "Kafka" in answer
    assert "双删" not in answer
    assert "Redis" in answer


def test_no_profile_fallback_continues_with_general_method_instead_of_refusing():
    grounding = analyze_experience_grounding("你做过 Redis 吗？")

    answer = grounding.direct_answer()

    assert "没有直接做过 Redis" in answer
    assert "通用方法" in answer
    assert "资料里没有" not in answer
    assert "请先补充" not in answer
