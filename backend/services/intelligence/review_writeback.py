"""Review → Intelligence write-back (Stage L4).

 INVARIANT:
  - Review never auto-writes LLM inference into Candidate Facts. Only the
    policy-approved kinds pass through memory_policy (knowledge weakness,
    repeated topic, communication profile); user-confirmed new facts require
    explicit user confirmation and are handled by the user-facing API, not
    here.
"""
from __future__ import annotations

import re

from core.logger import get_logger
from services.intelligence.memory_policy import write_back_memory

_log = get_logger("intelligence.review_writeback")

_TOPIC_TOKEN = re.compile(r"[\u4e00-\u9fff]{2,}|[a-zA-Z][a-zA-Z0-9+#.\-/]{2,}")
_MAX_WEAK_POINTS = 8


def _topic_of(text: str) -> str:
    match = _TOPIC_TOKEN.search((text or "").lower())
    return match.group()[:24] if match else ""


def write_back_after_review(
    session_id: int,
    summary_result: dict,
    analyzed_turns: list[dict],
) -> dict:
    """Write policy-approved learning results after a review completes.

    Returns per-kind counts actually written (denied attempts are logged by
    memory_policy and not counted).
    """
    written = {"knowledge_weakness": 0, "repeated_topic": 0, "communication_profile": 0}
    session_key = str(session_id)

    for point in (summary_result.get("weak_points") or [])[:_MAX_WEAK_POINTS]:
        text = str(point or "").strip()
        if text and write_back_memory("knowledge_weakness", text[:200], session_id=session_key):
            written["knowledge_weakness"] += 1

    topic_counts: dict[str, int] = {}
    for turn in analyzed_turns:
        topic = _topic_of(str(turn.get("question_text", "") or ""))
        if topic:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
    for topic, count in topic_counts.items():
        if count >= 2 and write_back_memory("repeated_topic", topic, session_id=session_key):
            written["repeated_topic"] += 1

    comm_scores: list[float] = []
    for turn in analyzed_turns:
        scorecard = turn.get("scorecard") or {}
        value = scorecard.get("communication")
        if value is not None:
            try:
                comm_scores.append(float(value))
            except (TypeError, ValueError):
                continue
    if comm_scores:
        avg = sum(comm_scores) / len(comm_scores)
        profile_text = f"沟通表达均分 {avg:.1f}/10（{len(comm_scores)} 题样本）"
        if write_back_memory("communication_profile", profile_text, session_id=session_key):
            written["communication_profile"] += 1

    _log.info(
        "review write-back session=%s knowledge_weakness=%d repeated_topic=%d communication=%d",
        session_key,
        written["knowledge_weakness"],
        written["repeated_topic"],
        written["communication_profile"],
    )
    return written
