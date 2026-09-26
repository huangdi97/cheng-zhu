"""Tests for services.intelligence.interview_state (versioned event fold).
apply_event persists snapshots to services.storage.intelligence; intel_db
redirects DB_PATH to a tmp SQLite file so the real DB file is untouched.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import services.storage.intelligence as intel_storage  # noqa: E402
from services.intelligence import interview_state  # noqa: E402
from services.intelligence.types import InterviewState  # noqa: E402


@pytest.fixture()
def intel_db(tmp_path, monkeypatch):
    """Redirect the intelligence DB to a tmp file, then (re-)init it."""
    db_path = str(tmp_path / "intelligence.db")
    monkeypatch.setattr(intel_storage, "DB_PATH", db_path)
    intel_storage.init_db()
    return intel_storage


def test_question_received_bumps_version_and_sets_topic(intel_db):
    sid = "s-question-received"
    interview_state.reset_state(sid)

    state = interview_state.apply_event(
        sid, "question_received", {"question": "Redis 集群和一致性是怎么保证的？", "question_type": "KNOWLEDGE"}
    )

    assert state.version == 1
    assert state.current_topic == "redis"
    assert state.previous_topic == ""
    assert state.question_type == "KNOWLEDGE"


def test_new_topic_event_preserves_previous_topic(intel_db):
    sid = "s-previous-topic"
    interview_state.reset_state(sid)
    interview_state.apply_event(sid, "question_received", {"question": "Redis 集群和一致性是怎么保证的？"})

    state = interview_state.apply_event(sid, "question_received", {"question": "Kafka 消息队列的顺序性怎么保证？"})

    assert state.current_topic == "kafka"
    assert state.previous_topic == "redis"
    assert state.version == 2


def test_consecutive_followup_keeps_topic_and_threads(intel_db):
    sid = "s-followup-keep"
    interview_state.reset_state(sid)
    interview_state.apply_event(sid, "question_received", {"question": "Redis 集群和一致性是怎么保证的？"})
    interview_state.apply_event(sid, "thread_opened", {"thread": "为什么不分片"})

    state = interview_state.apply_event(
        sid, "question_received",
        {"question": "那 Redis 的缓存一致性怎么办？", "is_follow_up": True, "question_type": "FOLLOW_UP"},
    )

    assert state.current_topic == "redis"
    assert state.open_threads == ["为什么不分片"]


def test_explicit_new_topic_resets_open_threads_and_pushes_topic_stack(intel_db):
    sid = "s-new-topic"
    interview_state.reset_state(sid)
    interview_state.apply_event(sid, "question_received", {"question": "Redis 集群和一致性是怎么保证的？"})
    interview_state.apply_event(sid, "thread_opened", {"thread": "为什么不分片"})

    state = interview_state.apply_event(sid, "question_received", {"question": "Kafka 消息队列的顺序性怎么保证？"})

    assert state.current_topic == "kafka"
    assert state.topic_stack == ["redis"]
    assert state.open_threads == []


def test_claim_made_updates_incrementally_and_ignores_duplicates(intel_db):
    sid = "s-claims"
    interview_state.reset_state(sid)

    state = interview_state.apply_event(sid, "claim_made", {"claim": "我使用 Redis Cluster 做分片"})
    state = interview_state.apply_event(sid, "claim_made", {"claim": "我负责订单系统架构"})
    state = interview_state.apply_event(sid, "claim_made", {"claim": "我使用 Redis Cluster 做分片"})

    assert state.candidate_claims == ["我使用 Redis Cluster 做分片", "我负责订单系统架构"]
    assert state.version == 3


def test_state_caps_claims_and_risk_flags(intel_db):
    sid = "s-caps"
    interview_state.reset_state(sid)

    for index in range(30):
        state = interview_state.apply_event(sid, "claim_made", {"claim": f"claim-{index}"})
    assert len(state.candidate_claims) == 24

    for index in range(15):
        state = interview_state.apply_event(sid, "risk_flag_added", {"flag": f"flag-{index}"})
    assert len(state.risk_flags) == 12


def test_thread_opened_then_closed_removes_thread(intel_db):
    sid = "s-threads"
    interview_state.reset_state(sid)

    state = interview_state.apply_event(sid, "thread_opened", {"thread": "为什么不分片"})
    state = interview_state.apply_event(sid, "thread_opened", {"thread": "线上怎么迁移"})
    state = interview_state.apply_event(sid, "thread_closed", {"thread": "为什么不分片"})

    assert state.open_threads == ["线上怎么迁移"]


def test_compact_state_context_renders_prompt_ready_block(intel_db):
    sid = "s-compact"
    interview_state.reset_state(sid)
    state = interview_state.apply_event(
        sid, "question_received",
        {"question": "Redis 集群和一致性是怎么保证的？", "question_type": "KNOWLEDGE", "intent": "verification"},
    )
    state = interview_state.apply_event(sid, "thread_opened", {"thread": "为什么不分片"})

    block = interview_state.compact_state_context(state)

    assert "面试状态" in block
    assert "当前主题：redis" in block
    assert "当前题型：KNOWLEDGE" in block
    assert "未闭合追问：为什么不分片" in block


def test_compact_state_context_empty_state_renders_empty_string():
    assert interview_state.compact_state_context(None) == ""
    assert interview_state.compact_state_context(InterviewState(session_id="s-empty")) == ""


def test_snapshot_roundtrip_restores_equivalent_state(intel_db):
    sid = "s-roundtrip"
    interview_state.reset_state(sid)
    interview_state.apply_event(sid, "question_received", {"question": "Kafka 顺序性怎么保证？", "question_type": "KNOWLEDGE"})
    last = interview_state.apply_event(sid, "claim_made", {"claim": "我使用 Redis Cluster 做分片"})

    interview_state.drop_session(sid)
    restored = interview_state.restore_from_snapshot(sid)

    assert restored.payload() == last.payload()


def test_reset_state_clears_state(intel_db):
    sid = "s-reset"
    interview_state.reset_state(sid)
    interview_state.apply_event(sid, "question_received", {"question": "Redis 集群和一致性是怎么保证的？"})
    interview_state.apply_event(sid, "claim_made", {"claim": "我使用 Redis Cluster 做分片"})

    state = interview_state.reset_state(sid)

    assert state.version == 0
    assert state.current_topic == ""
    assert state.candidate_claims == []
    assert state.question_type == ""


def test_unknown_event_kind_is_ignored(intel_db):
    sid = "s-unknown"
    interview_state.reset_state(sid)

    state = interview_state.apply_event(
        sid, "mystery_kind", {"question": "Redis 集群和一致性是怎么保证的？", "claim": "我使用 Redis Cluster 做分片"}
    )

    # Unknown kinds leave state fields untouched; only the version bumps.
    assert state.current_topic == ""
    assert state.candidate_claims == []
    assert state.question_type == ""
    assert state.version == 1
