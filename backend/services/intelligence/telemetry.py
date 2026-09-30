"""Unified observability events for the realtime interview path.

WHY: Telemetry must be fire-and-forget — a storage failure can never break
the realtime answering path. Sensitive data minimization applies: no resume
bodies, no full answers; question/guidance text is stored only in short
truncated form (<= 200 chars). No LLM calls here.
"""
from __future__ import annotations

from core.logger import get_logger
from services.intelligence.types import new_id

_log = get_logger(__name__)

_TEXT_TRUNCATE_LIMIT = 200


def _truncate(text: str, limit: int = _TEXT_TRUNCATE_LIMIT) -> str:
    return (text or "")[:limit]


def record_guidance_event(
    session_id: str,
    event: str,
    *,
    route: str = "",
    provider: str = "",
    model: str = "",
    latency_ms: int = 0,
    tokens: dict | None = None,
    context_ids: list | None = None,
    truth_flags: list | None = None,
) -> None:
    """Record one guidance/observability event. Failures are logged and
    swallowed: telemetry must never break the realtime path."""
    try:
        from services.storage.intelligence import save_guidance_event

        save_guidance_event({
            "id": new_id("ge-"),
            "session_id": session_id,
            "event": event,
            "route": route,
            "provider": provider,
            "model": model,
            "latency_ms": int(latency_ms),
            "tokens": tokens or {},
            "context_ids": context_ids or [],
            "truth_flags": truth_flags or [],
        })
    except Exception as exc:  # The ONE allowed broad exception: telemetry must never break the realtime path.
        _log.warning("guidance telemetry failed (session=%s event=%s): %s", session_id, event, exc)


def record_turn(
    session_id: str,
    seq: int,
    *,
    question_raw: str = "",
    question_resolved: str = "",
    question_type: str = "",
    route: str = "",
    guidance_text: str = "",
    truth_flags: list | None = None,
    latency_ms: int = 0,
) -> None:
    """Record one interview turn; question/guidance text truncated to <=200."""
    try:
        from services.storage.intelligence import save_interview_turn

        save_interview_turn({
            "id": new_id("turn-"),
            "session_id": session_id,
            "seq": seq,
            "question_raw": _truncate(question_raw),
            "question_resolved": _truncate(question_resolved),
            "question_type": question_type,
            "route": route,
            "guidance_text": _truncate(guidance_text),
            "truth_flags": truth_flags or [],
            "latency_ms": int(latency_ms),
        })
    except Exception as exc:  # The ONE allowed broad exception: telemetry must never break the realtime path.
        _log.warning("turn telemetry failed (session=%s seq=%s): %s", session_id, seq, exc)


def session_recovered(session_id: str) -> None:
    """Record a session-recovery observability event."""
    record_guidance_event(session_id, "session_recovered")
