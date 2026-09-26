"""Tests for services.intelligence.question_understanding + followup_resolver.

Pure-logic tests: no storage, no LLM calls. One behavior per test; fixtures
are behavior-descriptive. PROJECT_DEEP_DIVE is surfaced by the follow-up
resolver (classify_question_type_21 leaves it there), HYPOTHETICAL scaling by
intent/depth, ROLE_FIT routing by answer_planner (covered in
test_intelligence_compiler_planner.py).
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.intelligence.followup_resolver import (  # noqa: E402
    followup_target_type,
    is_bare_followup,
    resolve_followup,
)
from services.intelligence.question_understanding import (  # noqa: E402
    classify_question_type_21,
    detect_domain,
    detect_intent,
    understand_question,
)
from services.intelligence.types import DepthProfile, QuestionType  # noqa: E402

# One fixture per classifiable type of the 21-type taxonomy.
TYPE_FIXTURES = [
    ("请你先做一个自我介绍", QuestionType.SELF_INTRODUCTION),
    ("介绍一下你的项目背景", QuestionType.EXPERIENCE),
    ("请手写一个 LRU 缓存", QuestionType.CODING),
    ("设计一个高并发的秒杀系统", QuestionType.SYSTEM_DESIGN),
    ("谈谈面向对象设计的 SOLID 原则", QuestionType.OOD),
    ("线上服务突然变慢了，应该怎么排查", QuestionType.DEBUGGING),
    ("你期望的薪资范围是多少", QuestionType.SALARY),
    ("HR 说准备和你谈薪，你会怎么应对", QuestionType.NEGOTIATION),
    ("来做一道市场规模估算的咨询案例", QuestionType.CASE),
    ("谈谈你的产品思维是怎么形成的", QuestionType.PRODUCT),
    ("你如何理解 SaaS 产品的商业模式和盈利方式", QuestionType.BUSINESS),
    ("为什么想来我们这家公司工作", QuestionType.COMPANY),
    ("你未来五年的职业规划是什么", QuestionType.CAREER),
    ("讲一次你在团队里推动跨部门协作的经历", QuestionType.BEHAVIORAL),
    ("你实际用过 Redis Cluster 吗，说说细节", QuestionType.EXPERIENCE),
    ("Transformer 为什么需要位置编码", QuestionType.KNOWLEDGE),
    ("你是什么意思，我没太听清", QuestionType.CLARIFICATION),
    ("为什么不用那个", QuestionType.FOLLOW_UP),
]

# Bare cues that carry no subject of their own and must resolve against
# previous_question + interview state.
BARE_FOLLOWUPS = ["为什么？", "然后呢？", "为什么不用那个？", "如果再扩大呢？", "那线上怎么办？"]
STATE_DICT = {"current_topic": "缓存", "question_type": ""}
PREVIOUS_QUESTION = "你介绍一下你项目里的缓存设计"


@pytest.mark.parametrize(("question", "expected"), TYPE_FIXTURES)
def test_question_fixture_classifies_into_expected_type(question: str, expected: QuestionType):
    assert classify_question_type_21(question) == expected


def test_empty_input_classifies_as_meta():
    assert classify_question_type_21("") == QuestionType.META


def test_project_deep_dive_surfaces_via_followup_target_classification():
    assert followup_target_type("为什么不分片？") == QuestionType.PROJECT_DEEP_DIVE
    assert followup_target_type("这里有取舍吗") == QuestionType.KNOWLEDGE


def test_hypothetical_scaling_question_gets_deep_depth_and_conditional_intent():
    result = understand_question("如果流量增长 10 倍，现在的架构还撑得住吗？")

    assert result.intent == "hypothetical_scale"
    assert result.expected_depth == DepthProfile.DEEP


@pytest.mark.parametrize("cue", BARE_FOLLOWUPS)
def test_bare_followup_resolves_against_previous_question(cue: str):
    result = understand_question(
        cue,
        interview_state=STATE_DICT,
        previous_question=PREVIOUS_QUESTION,
    )

    assert result.is_follow_up is True
    assert result.resolved_question.strip() != ""
    assert "追问" in result.resolved_question


@pytest.mark.parametrize("cue", BARE_FOLLOWUPS)
def test_resolve_followup_returns_complete_question_with_target(cue: str):
    state = {
        "previous_question": PREVIOUS_QUESTION,
        "current_topic": "缓存",
        "open_threads": [],
        "candidate_claims": [],
    }

    resolved, target = resolve_followup(cue, interview_state=state, previous_question=PREVIOUS_QUESTION)

    assert is_bare_followup(cue) is True
    assert target != ""
    assert resolved != cue
    assert "追问" in resolved


def test_non_followup_question_passes_through_resolver_unchanged():
    resolved, target = resolve_followup("Redis 持久化有什么区别？")

    assert resolved == "Redis 持久化有什么区别？"
    assert target == ""


def test_experience_verification_requires_personal_fact():
    result = understand_question("你实际用过 Redis Cluster 吗")

    assert result.question_type == QuestionType.EXPERIENCE
    assert result.personal_fact_required is True


def test_knowledge_question_allows_open_world_without_personal_fact():
    result = understand_question("Transformer 为什么需要位置编码？")

    assert result.question_type == QuestionType.KNOWLEDGE
    assert result.personal_fact_required is False
    assert result.open_world_allowed is True


def test_topic_transition_detected_when_new_question_leaves_state_topic():
    result = understand_question(
        "Kafka 的顺序性是怎么保证的？",
        interview_state={"current_topic": "redis", "question_type": ""},
    )

    assert result.is_follow_up is False
    assert result.topic_transition is True


def test_question_staying_on_state_topic_is_not_a_topic_transition():
    result = understand_question(
        "Redis 持久化的两种方式有什么区别？",
        interview_state={"current_topic": "redis", "question_type": ""},
    )

    assert result.is_follow_up is False
    assert result.topic_transition is False


def test_question_without_state_topic_never_flags_topic_transition():
    result = understand_question("Kafka 的顺序性是怎么保证的？")

    assert result.topic_transition is False


def test_followup_gets_compact_deep_depth_and_salary_concise():
    followup = understand_question("为什么不用那个？", interview_state={"current_topic": "redis"})
    salary = understand_question("你期望的薪资范围是多少")

    assert followup.expected_depth == DepthProfile.COMPACT_DEEP
    assert salary.expected_depth == DepthProfile.CONCISE


def test_detect_intent_and_domain_reflect_question_semantics():
    assert detect_intent("为什么不用 Kafka 而用 RabbitMQ？") == "alternative_rejection"
    assert detect_intent("你怎么验证缓存的一致性？") == "verification"
    assert detect_domain("Kafka 消息队列的顺序性怎么保证？") == "message_queue"
    assert detect_domain("RAG 的检索召回率怎么评估？") == "ai_llm"
