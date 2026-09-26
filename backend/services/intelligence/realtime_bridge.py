"""Realtime bridge: one-call integration of the Intelligence Core into the
existing answer pipeline.

 INVARIANT:
  - Strictly additive: the existing deterministic grounding, follow-up and
    candidate-ASR safeguards keep running; this layer never replaces them.
  - Deterministic and latency-free (pure rules, no LLM calls); every failure
    degrades to the legacy path (empty payload) instead of breaking the
    realtime loop.
"""
from __future__ import annotations

from services.intelligence.followup_resolver import resolve_followup
from services.intelligence.interview_state import apply_event, compact_state_context, get_state
from services.intelligence.question_understanding import understand_question
from services.intelligence.truth_boundary import map_grounding_status
from services.intelligence.types import InterviewState

DEFAULT_SESSION_ID = "default"


def _session_id_of(session_ref) -> str:
    if session_ref is None:
        return DEFAULT_SESSION_ID
    return str(getattr(session_ref, "id", "") or "").strip() or DEFAULT_SESSION_ID


def build_intelligence_layer(
    question_text: str,
    *,
    previous_question: str = "",
    relation_to_previous: str = "",
    session_id: str = "",
    session_ref=None,
    grounding_status: str = "",
    interviewer_state_enabled: bool = True,
    open_threads: list[str] | None = None,
) -> dict:
    """Understand the question, update the interview state, and build the
    structured plan for the current turn.

    Returns a payload dict with keys ``understanding`` / ``plan`` /
    ``plan_prompt`` / ``state_context`` / ``state``; callers inject
    ``plan_prompt`` and ``state_context`` into the existing user prompt.
    """
    resolved_session_id = session_id or _session_id_of(session_ref)
    understanding = understand_question(
        question_text,
        previous_question=previous_question,
        relation_to_previous=relation_to_previous,
        open_threads=open_threads,
    )
    payload: dict = {"understanding": understanding.payload(), "plan": {}, "plan_prompt": "", "state_context": "", "state": {}}

    state = get_state(resolved_session_id)
    resolved_question = understanding.resolved_question
    if understanding.is_follow_up:
        state_view = state.payload()
        state_view["previous_question"] = previous_question
        resolved_question, target = resolve_followup(
            question_text,
            interview_state=state_view,
            previous_question=previous_question,
            open_threads=open_threads,
        )
        if target:
            understanding.resolved_question = resolved_question
            understanding.follow_up_target = target
            payload["understanding"] = understanding.payload()
        else:
            resolved_question = understanding.resolved_question

    apply_event(
        resolved_session_id,
        "question_received",
        {
            "question": question_text,
            "question_type": understanding.question_type.value,
            "intent": understanding.intent,
            "expected_depth": understanding.expected_depth.value,
            "is_follow_up": understanding.is_follow_up,
        },
    )
    state = get_state(resolved_session_id)
    payload["state"] = state.payload()
    payload["state_context"] = compact_state_context(state)

    if planner_enabled:
        from services.intelligence.answer_planner import create_plan

        plan = create_plan(
            understanding.question_type,
            resolved_question=resolved_question,
            intent=understanding.intent,
            expected_depth=understanding.expected_depth,
            truth_status=map_grounding_status(grounding_status).value,
            personal_fact_required=understanding.personal_fact_required,
            interviewer_state=(state if interviewer_state_enabled else None),
            open_world_allowed=understanding.open_world_allowed,
        )
        payload["plan"] = plan.payload()
        payload["plan_prompt"] = plan.plan_prompt
    return payload


def record_committed_turn(
    session_id: str,
    *,
    seq: int,
    question_raw: str,
    question_resolved: str = "",
    question_type: str = "",
    route: str = "",
    guidance_text: str = "",
    truth_flags: list[str] | None = None,
    latency_ms: int = 0,
    answer_plan: dict | None = None,
) -> None:
    """Persist one committed QA turn + claim events after the answer commit.

    Claims made by the CANDIDATE in their own spoken answer are state events;
    assistant guidance is never written as a candidate fact.
    """
    try:
        from services.intelligence.telemetry import record_turn

        record_turn(
            session_id,
            seq,
            question_raw=question_raw,
            question_resolved=question_resolved,
            question_type=question_type,
            route=route,
            guidance_text=guidance_text,
            truth_flags=truth_flags or [],
            latency_ms=latency_ms,
        )
    except Exception:  # noqa: BLE001
        # Telemetry must never break the realtime path.
        pass
    route_value = route or str((answer_plan or {}).get("mode", "") or "")
    if route_value:
        apply_event(session_id, "route_taken", {"route": route_value, "seq": seq})


def restore_session_state(session_id: str) -> InterviewState:
    """Crash recovery entry for the realtime path."""
    from services.intelligence.interview_state import restore_from_snapshot

    return restore_from_snapshot(session_id)
