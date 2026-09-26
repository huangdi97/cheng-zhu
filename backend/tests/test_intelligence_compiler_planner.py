"""Tests for retrieval scoring, ContextCompiler, Answer Planner, open-world
routing, interviewer state, voice profile and memory policy.

ContextCompiler runs against fake ContextProviders (the real data boundary —
providers are plain data sources); everything else is pure logic. No LLM calls.
"""
from __future__ import annotations

import time
from pathlib import Path
import sys

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.intelligence.answer_planner import create_plan, route_for  # noqa: E402
from services.intelligence.context_compiler import (  # noqa: E402
    ContextCompiler, render_context_sections, token_budget,
)
from services.intelligence.interviewer_state import decay, planner_hint, update_interviewer_state  # noqa: E402
from services.intelligence.memory_policy import can_write_back, write_back_memory  # noqa: E402
from services.intelligence.retrieval import (  # noqa: E402
    DEFAULT_WEIGHTS, contradiction_risk, estimate_tokens, interview_recency,
    lexical_entity_match, redundancy, score_item, semantic_relevance, topic_continuity,
)
from services.intelligence.types import (  # noqa: E402
    CompiledContext, ContextItem, ContextSource, InterviewerState, QuestionType, ResponseMode, VoiceProfileData,
)
from services.intelligence.voice_profile import apply_voice, build_voice_profile  # noqa: E402
from services.intelligence.world_reasoning import expected_mode, route_open_world  # noqa: E402


class FakeProvider:
    """Fake ContextProvider: the real boundary — a plain in-memory data source."""

    def __init__(self, source_type: ContextSource, items: list[ContextItem]):
        self.source_type, self._items = source_type, items

    def collect(self, question_text: str, *, limit: int = 8) -> list[ContextItem]:
        return self._items[:limit]


def _item(item_id: str, text: str, *, source: ContextSource = ContextSource.EVIDENCE,
          topic: str = "", tokens: int = 40, strength: float = 0.8, metadata: dict | None = None) -> ContextItem:
    return ContextItem(id=item_id, source_type=source, text=text, timestamp=time.time(),
                       evidence_strength=strength, topic=topic, token_estimate=tokens, metadata=metadata or {})


def test_retrieval_scores_bounded_and_stale_topic_penalized():
    now = time.time()
    question = "Redis 缓存的一致性怎么保证？"
    on_topic = _item("i1", "使用 Redis 缓存保证一致性", topic="redis")
    off_topic = _item("i2", "Kafka 顺序性和分区策略", topic="kafka")
    on_scored = score_item(on_topic, question=question, active_topic="redis")
    off_scored = score_item(off_topic, question=question, active_topic="redis")

    assert 0.0 <= semantic_relevance("Redis 缓存怎么用", "我用 Redis 做缓存") <= 1.0
    assert semantic_relevance("Kafka 顺序性", "完全无关的一段内容") == 0.0
    assert lexical_entity_match("Redis Cluster 分片", "使用 Redis Cluster", ["Redis"]) == 1.0
    assert interview_recency(now, now=now) == 1.0 and interview_recency(now - 700, now=now) == 0.0
    assert topic_continuity("redis", "redis") == 1.0 and 0.0 <= topic_continuity("kafka", "redis") < 1.0
    assert contradiction_risk(_item("i3", "x", metadata={"truth_status": "CONTRADICTED"})) == 1.0
    assert redundancy("我用 Redis 做缓存了", ["我用 Redis 做缓存"]) > 0.5
    assert redundancy("Kafka 顺序性", ["我用 Redis 做缓存"]) == 0.0
    assert [on_scored.breakdown["stale_topic_penalty"], off_scored.breakdown["stale_topic_penalty"]] == [0.0, 0.5]
    assert off_scored.score < on_scored.score


def test_score_item_breakdown_has_all_ten_keys_and_bounded_total():
    item = _item("i1", "使用 Redis 缓存保证一致性", topic="redis", strength=0.9, metadata={"importance": 0.8})

    scored = score_item(item, question="Redis 缓存的一致性怎么保证？", active_topic="redis")

    assert set(scored.breakdown.keys()) == set(DEFAULT_WEIGHTS.keys())
    assert all(0.0 <= value <= 1.0 for value in scored.breakdown.values()) and -0.5 <= scored.score <= 1.0


def test_compiler_select_limit_and_drops_with_latency():
    items = [_item(f"i-{n}", f"使用 Redis 缓存保证一致性 第{n}条") for n in range(10)]
    compiler = ContextCompiler([FakeProvider(ContextSource.EVIDENCE, items)])

    context = compiler.compile("Redis 缓存的一致性怎么保证？")

    assert len(context.items) == 6 and len(context.dropped) == 4
    assert {dropped["reason"] for dropped in context.dropped} == {"select_limit"}
    assert all(dropped["id"] and dropped["score"] is not None for dropped in context.dropped)
    assert context.latency_ms >= 0


def test_compiler_respects_token_budget():
    items = [_item(f"i-{n}", f"使用 Redis 缓存保证一致性 第{n}条", tokens=800) for n in range(3)]
    compiler = ContextCompiler([FakeProvider(ContextSource.EVIDENCE, items)])

    context = compiler.compile("Redis 缓存的一致性怎么保证？")

    assert context.budget == token_budget(deep=False)
    assert context.total_token_estimate <= context.budget
    assert len(context.items) == 1 and any(dropped["reason"] == "token_budget" for dropped in context.dropped)


def test_compiler_stale_topic_items_get_penalty_and_drop_when_budget_tight():
    on_topic = [
        _item("on-1", "使用 Redis 缓存保证一致性，读写分离降低延迟", topic="redis", tokens=600),
        _item("on-2", "Redis 集群分片与一致性哈希的设计", topic="redis", tokens=600),
    ]
    stale = [_item(f"stale-{n}", f"Kafka 消息队列顺序性与分区策略 第{n}条", topic="kafka", tokens=400) for n in range(3)]
    compiler = ContextCompiler([FakeProvider(ContextSource.EVIDENCE, on_topic + stale)])

    context = compiler.compile("Redis 缓存的一致性怎么保证？", active_topic="redis")

    assert {item.topic for item in context.items} == {"redis"}
    stale_dropped = [dropped for dropped in context.dropped if dropped["id"].startswith("stale-")]
    assert len(stale_dropped) == 3 and all(dropped["reason"] == "token_budget" for dropped in stale_dropped)


def test_render_context_sections_groups_by_source():
    context = CompiledContext(items=[
        _item("i-1", "使用 Redis 缓存保证一致性", source=ContextSource.EVIDENCE),
        _item("i-2", "熟悉 Kafka，了解 Flink", source=ContextSource.RESUME),
    ])
    sections = render_context_sections(context)

    assert any(section.startswith("[evidence]") for section in sections)
    assert any(section.startswith("[resume]") for section in sections)


def test_estimate_tokens_cjk_one_per_char_ascii_four_per_char():
    assert estimate_tokens("") == 0 and estimate_tokens("一二三四五六") == 6
    assert estimate_tokens("abcdefgh") == 2 and estimate_tokens("一二三四abcd") == 5


def test_create_plan_modes_and_structures_differ_by_question_type():
    plans = [
        create_plan(QuestionType.KNOWLEDGE), create_plan(QuestionType.EXPERIENCE),
        create_plan(QuestionType.HYPOTHETICAL), create_plan(QuestionType.CODING),
        create_plan(QuestionType.SYSTEM_DESIGN),
    ]
    assert len({plan.mode for plan in plans}) == 5 and len({tuple(plan.structure) for plan in plans}) == 5

    # Knowledge mode never blocks world knowledge, evidence or not.
    knowledge_plan = create_plan(QuestionType.KNOWLEDGE, open_world_allowed=False, truth_status="")
    assert knowledge_plan.allow_world_knowledge is True


def test_planner_routes_claim_constraints_and_boundary_upgrade():
    plan = create_plan(
        QuestionType.EXPERIENCE, resolved_question="介绍一下你的项目", intent="role_clarification",
        must_use_claim_ids=["cl-1", "cl-2"], forbidden_claim_ids=["cl-3"],
    )
    assert plan.must_use_claim_ids == ["cl-1", "cl-2"] and plan.forbidden_claim_ids == ["cl-3"]

    boundary_plan = create_plan(QuestionType.EXPERIENCE, personal_fact_required=True, truth_status="UNKNOWN", open_world_allowed=False)
    assert boundary_plan.mode == ResponseMode.EXPERIENCE_BOUNDARY_KNOWLEDGE
    assert boundary_plan.allow_world_knowledge is False
    assert route_for(QuestionType.KNOWLEDGE, personal_fact_boundary=True) == ResponseMode.EXPERIENCE_BOUNDARY_KNOWLEDGE
    assert route_for(QuestionType.KNOWLEDGE, personal_fact_boundary=False) == ResponseMode.KNOWLEDGE


def test_open_world_routes_keep_answers_answerable():
    knowledge = route_open_world(QuestionType.KNOWLEDGE, has_personal_evidence=False)
    boundary_route = route_open_world(QuestionType.EXPERIENCE, has_personal_evidence=False, personal_fact_required=True)
    hypothetical = route_open_world(QuestionType.HYPOTHETICAL, has_personal_evidence=False, hypothetical=True)

    # No resume evidence is NOT the same as no answer.
    assert knowledge.deny_answer is False and knowledge.allow_world_knowledge is True
    assert boundary_route.deny_answer is False
    assert expected_mode(boundary_route, ResponseMode.KNOWLEDGE) == ResponseMode.EXPERIENCE_BOUNDARY_KNOWLEDGE
    assert hypothetical.deny_answer is False and hypothetical.allow_reasoning is True
    assert expected_mode(hypothetical, ResponseMode.KNOWLEDGE) == ResponseMode.HYPOTHETICAL


def test_interviewer_update_and_decay_stay_bounded():
    state = update_interviewer_state(InterviewerState(session_id="s-int"), question_type="KNOWLEDGE")
    assert state.possible_focus["engineering_depth"] == pytest.approx(0.1)

    repeated = state
    for _ in range(10):
        repeated = update_interviewer_state(repeated, question_type="KNOWLEDGE")
    assert max(repeated.possible_focus.values()) <= 0.95
    assert repeated.possible_focus["engineering_depth"] == pytest.approx(0.95)

    decayed = decay(InterviewerState(session_id="s-int", possible_focus={"engineering_depth": 0.05, "coding": 0.5}))
    assert "engineering_depth" not in decayed.possible_focus
    assert decayed.possible_focus["coding"] == pytest.approx(0.425) and decayed.confidence == pytest.approx(0.425)


def test_planner_hint_stays_probabilistic_never_deterministic_verdict():
    concerned = InterviewerState(session_id="s-int", possible_focus={"engineering_depth": 0.8}, possible_concerns={"缓存": 0.9})
    hint = planner_hint(concerned)
    focus_hint = planner_hint(InterviewerState(session_id="s-int", possible_focus={"coding": 0.5}))

    assert "面试官认为" not in hint and "疑虑" in hint
    assert "面试官认为" not in focus_hint and "验证" in focus_hint
    assert planner_hint(None) == "" and planner_hint(InterviewerState(session_id="s-int")) == ""


def test_voice_profile_build_from_samples_computes_stats():
    samples = ["我用了 Redis 做分片。", "我负责订单系统的整体架构设计。", "那个当时的背景是流量涨了。"]
    profile = build_voice_profile(samples, candidate_id="cand-voice")

    assert profile.sample_count == 3 and profile.answer_length_hint == "short"
    assert profile.first_sentence_style == "conclusion_first" and profile.directness == pytest.approx(2 / 3)
    assert 0.0 < profile.technical_density <= 1.0 and 0.0 <= profile.filler_tendency <= 1.0
    assert profile.language == "zh-CN" and profile.enabled is False


def test_apply_voice_respects_enabled_flag_and_fact_boundary():
    profile = build_voice_profile(["我用了 Redis 做分片。"], candidate_id="cand-voice")
    assert apply_voice(profile, "先讲结论") == "先讲结论" and apply_voice(None, "先讲结论") == "先讲结论"

    profile.enabled = True
    result = apply_voice(profile, "先讲结论")

    assert result.startswith("先讲结论") and "[表达风格要求]" in result  # fact content preserved
    assert "不得改变事实边界与个人经历的真实性" in result


def test_memory_policy_denies_unconfirmed_facts_unknown_kinds_and_denied_write_back():
    assert can_write_back("user_confirmed_fact") is False
    assert can_write_back("llm_inferred_guess") is False
    assert can_write_back("knowledge_weakness") is True
    assert can_write_back("user_confirmed_fact", user_confirmed=True) is True
    assert write_back_memory("llm_inferred_guess", "候选人可能熟悉 Kafka") is False
