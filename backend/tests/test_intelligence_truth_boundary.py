"""Tests for services.intelligence.truth_boundary (unified Truth Boundary).

Deterministic only: grounding analysis, output-space classification, legacy
status mapping, claim policy text and the post-generation checker. No storage,
no LLM calls.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.answer_grounding import ExperienceGrounding  # noqa: E402
from services.intelligence.truth_boundary import (  # noqa: E402
    analyze_truth_boundary,
    check_generated_answer,
    claim_policy_text,
    classify_output_space,
    map_grounding_status,
)
from services.intelligence.types import OutputSpace, TruthStatus  # noqa: E402

REDIS_CLUSTER_QUESTION = "你有没有 Redis Cluster 的项目经验？"
SUPPORTED_RESUME = "使用 Redis Cluster 支撑日均 3 万 QPS 的订单查询链路"


def test_experience_verification_with_matching_resume_locks_personal_fact_space():
    boundary = analyze_truth_boundary(REDIS_CLUSTER_QUESTION, resume_text=SUPPORTED_RESUME)

    assert boundary.applicable is True
    assert boundary.output_space == OutputSpace.PERSONAL_FACT
    assert boundary.truth_status == TruthStatus.SUPPORTED


def test_experience_verification_without_resume_stays_hypothetical_and_unknown():
    boundary = analyze_truth_boundary(REDIS_CLUSTER_QUESTION, resume_text="")

    assert boundary.applicable is True
    assert boundary.output_space == OutputSpace.HYPOTHETICAL
    assert boundary.truth_status == TruthStatus.UNKNOWN


def test_non_experience_question_is_knowledge_judgment():
    boundary = analyze_truth_boundary("Redis 的 RDB 和 AOF 有什么区别？")

    assert boundary.applicable is False
    assert boundary.output_space == OutputSpace.KNOWLEDGE_JUDGMENT
    assert boundary.truth_status == TruthStatus.UNKNOWN


def test_unsupported_personal_claim_on_unknown_boundary_is_rewritten():
    boundary = analyze_truth_boundary(REDIS_CLUSTER_QUESTION, resume_text="")
    answer = "我用过 Redis Cluster 做了分片，效果很好。"

    result = check_generated_answer(answer, boundary=boundary, evidence_texts=[], question_text="")

    kinds = [violation["kind"] for violation in result.violations]
    assert "unsupported_personal_claim" in kinds
    assert result.passed is False
    assert result.fallback_used is True
    assert result.final_text != result.original_text


def test_honest_negation_passes_the_post_generation_check():
    boundary = analyze_truth_boundary(REDIS_CLUSTER_QUESTION, resume_text="")
    answer = "我没有直接做过 Redis Cluster 项目，但我了解相关基础，可以从通用方案讲起。"

    result = check_generated_answer(answer, boundary=boundary, evidence_texts=[], question_text="")

    assert result.passed is True
    assert result.fallback_used is False
    assert result.final_text == result.original_text


def test_unexpected_metric_on_supported_boundary_is_flagged_and_rewritten():
    boundary = analyze_truth_boundary(REDIS_CLUSTER_QUESTION, resume_text=SUPPORTED_RESUME)
    answer = "做过，我们用 Redis Cluster 支撑了日均 5 万 QPS。"

    result = check_generated_answer(
        answer, boundary=boundary, evidence_texts=[], question_text=REDIS_CLUSTER_QUESTION
    )

    kinds = [violation["kind"] for violation in result.violations]
    assert "unexpected_metric" in kinds
    assert result.passed is False
    assert result.fallback_used is True


def test_internal_leakage_in_answer_is_detected():
    boundary = analyze_truth_boundary(REDIS_CLUSTER_QUESTION, resume_text=SUPPORTED_RESUME)
    answer = "简历里没有提供线上规模数据，所以我不太确定。"

    result = check_generated_answer(
        answer, boundary=boundary, evidence_texts=[], question_text=REDIS_CLUSTER_QUESTION
    )

    kinds = [violation["kind"] for violation in result.violations]
    assert "internal_system_leakage" in kinds
    assert result.passed is False
    assert result.fallback_used is True


@pytest.mark.parametrize(
    ("legacy", "expected"),
    [
        ("supported", TruthStatus.SUPPORTED),
        ("related_only", TruthStatus.INFERRED),
        ("explicit_negative", TruthStatus.CONTRADICTED),
        ("unsupported", TruthStatus.UNKNOWN),
        ("no_profile", TruthStatus.UNKNOWN),
        ("not_applicable", TruthStatus.UNKNOWN),
    ],
)
def test_legacy_grounding_status_maps_to_unified_truth_status(legacy: str, expected: TruthStatus):
    assert map_grounding_status(legacy) == expected


@pytest.mark.parametrize("status", list(TruthStatus))
def test_claim_policy_text_is_non_empty_for_every_status(status: TruthStatus):
    assert claim_policy_text(status).strip() != ""


def test_claim_policy_falls_back_for_unknown_status_string():
    assert claim_policy_text("NOT_A_STATUS") == claim_policy_text(TruthStatus.UNKNOWN)


def test_output_space_classification_from_raw_grounding():
    assert classify_output_space(ExperienceGrounding(False, "not_applicable")) == OutputSpace.KNOWLEDGE_JUDGMENT
    assert classify_output_space(ExperienceGrounding(True, "supported", "Kafka")) == OutputSpace.PERSONAL_FACT
    assert classify_output_space(ExperienceGrounding(True, "related_only", "Kafka")) == OutputSpace.KNOWLEDGE_JUDGMENT


def test_boundary_prompt_contract_appends_output_space_line():
    boundary = analyze_truth_boundary(REDIS_CLUSTER_QUESTION, resume_text=SUPPORTED_RESUME)

    contract = boundary.prompt_contract()

    assert contract != ""
    assert "输出空间" in contract
    assert claim_policy_text(boundary.truth_status) in contract
