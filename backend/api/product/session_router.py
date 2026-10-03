"""v1.3 Practice / Live / Reflection API."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.product.common import domain_errors
from services.product import closing, events, live, nudges, pins, practice, reflection
from services.product.rubrics import all_rubrics, rubric_for

router = APIRouter(tags=["product-sessions"])


# ---------------------------------------------------------------------------
# Practice 3.0
# ---------------------------------------------------------------------------


@router.get("/practice/options")
def practice_options(goal_id: str = ""):
    out = practice.options()
    if goal_id:
        from services.product.next_focus import practice_defaults

        with domain_errors():
            out["defaults"] = practice_defaults(goal_id)
    return out


class PracticeStart(BaseModel):
    goal_id: Optional[str] = None
    round: str = "TECHNICAL"
    personas: list[str] = Field(default_factory=list)
    demeanor: str = "NEUTRAL"
    difficulty: str = "STANDARD"
    sources: list[str] = Field(default_factory=lambda: ["GOAL_GRAPH", "RECENT_WEAKNESS", "ROLE_BANK"])
    questions: int = 5
    language: str = "zh"
    human_coach: bool = False
    focus: Optional[dict[str, Any]] = None
    guided: bool = False
    delivery_analytics: Optional[bool] = None
    closing: Optional[bool] = None


@router.post("/practice")
def start_practice(body: PracticeStart):
    raw = body.model_dump()
    if raw.get("delivery_analytics") is None:
        from core.config import get_config

        raw["delivery_analytics"] = bool(getattr(get_config(), "practice_delivery_analytics_enabled", True))
    if raw.get("closing") is None:
        raw.pop("closing")
    with domain_errors():
        return practice.start(raw)


class PracticeAnswer(BaseModel):
    answer: str = Field(max_length=20000)
    duration_ms: Optional[int] = None
    word_timestamps: Optional[list[dict[str, Any]]] = None


@router.post("/practice/{practice_id}/answer")
def answer_practice(practice_id: str, body: PracticeAnswer):
    with domain_errors():
        return practice.answer(practice_id, body.answer, duration_ms=body.duration_ms,
                               word_timestamps=body.word_timestamps)


@router.post("/practice/{practice_id}/finish")
def finish_practice(practice_id: str):
    with domain_errors():
        return practice.finish(practice_id)


@router.get("/practice/{practice_id}")
def get_practice(practice_id: str):
    with domain_errors():
        return practice.get(practice_id)


@router.get("/practice")
def list_practice(goal_id: str = ""):
    return {"items": practice.list_sessions(goal_id)}


@router.get("/rubrics")
def rubrics(role_family: str = ""):
    return rubric_for(role_family) if role_family else {"items": all_rubrics()}


# ---------------------------------------------------------------------------
# Live: preflight / start / end / pins / nudges / closing
# ---------------------------------------------------------------------------


class LiveRequest(BaseModel):
    goal_id: str
    overrides: dict[str, Any] = Field(default_factory=dict)


@router.post("/live/preflight")
def live_preflight(body: LiveRequest):
    with domain_errors():
        return live.preflight(body.goal_id, body.overrides)


@router.post("/live/start")
def live_start(body: LiveRequest):
    with domain_errors():
        return live.start(body.goal_id, body.overrides)


class LiveEnd(BaseModel):
    session_id: str = ""
    review_session_id: Optional[int] = None


@router.post("/live/end")
def live_end(body: LiveEnd):
    with domain_errors():
        return live.end(body.session_id, body.review_session_id)


class PinCreate(BaseModel):
    session_id: str = ""
    session_kind: str = "LIVE"
    tag: str = "IMPORTANT"
    turn_id: str = ""
    question: str = Field(default="", max_length=600)
    transcript_excerpt: str = Field(default="", max_length=2000)
    note: str = Field(default="", max_length=500)
    goal_id: Optional[str] = None


@router.post("/pins")
def create_pin(body: PinCreate):
    session_id = body.session_id
    if not session_id and body.session_kind == "LIVE":
        from core.session import session_id as current_session_id

        session_id = str(current_session_id() or "")
    with domain_errors():
        return pins.create_pin(session_id, session_kind=body.session_kind, tag=body.tag, turn_id=body.turn_id,
                               question=body.question, transcript_excerpt=body.transcript_excerpt, note=body.note,
                               goal_id=body.goal_id)


class PinPatch(BaseModel):
    tag: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=500)


@router.patch("/pins/{pin_id}")
def patch_pin(pin_id: str, body: PinPatch):
    with domain_errors():
        return pins.update_pin(pin_id, body.model_dump(exclude_unset=True))


@router.delete("/pins/{pin_id}")
def delete_pin(pin_id: str):
    return {"deleted": pins.delete_pin(pin_id)}


@router.get("/pins")
def list_pins(session_id: str):
    return {"items": pins.pins_for_session(session_id)}


class PinPromote(BaseModel):
    goal_id: Optional[str] = None


@router.post("/pins/{pin_id}/promote")
def promote_pin(pin_id: str, body: PinPromote):
    with domain_errors():
        return pins.promote_to_focus(pin_id, body.goal_id)


class NudgeEvaluate(BaseModel):
    session_id: str
    candidate_text: str = Field(default="", max_length=8000)
    question_type: str = ""
    candidate_speaking: bool = False
    new_question_pending: bool = False
    cue_state: str = ""
    fact_warnings: list[Any] = Field(default_factory=list)
    interviewer_recent: list[str] = Field(default_factory=list)


@router.post("/nudges/evaluate")
def evaluate_nudge(body: NudgeEvaluate):
    from core.config import get_config

    state = body.model_dump()
    state["proactive_enabled"] = bool(getattr(get_config(), "proactive_guidance_enabled", True))
    return nudges.evaluate(body.session_id, state)


@router.post("/nudges/disable")
def nudge_disable(session_id: str = ""):
    from core.config import update_config

    update_config({"proactive_guidance_enabled": False})
    nudges.record_disabled(session_id)
    return {"proactive_guidance_enabled": False}


class NudgeStatus(BaseModel):
    status: str


@router.post("/nudges/{nudge_id}")
def nudge_status(nudge_id: str, body: NudgeStatus):
    with domain_errors():
        return {"item": nudges.set_status(nudge_id, body.status)}


@router.post("/nudges/session/{session_id}/new-question")
def nudge_new_question(session_id: str):
    return {"cancelled": nudges.cancel_on_new_question(session_id)}


class ClosingRequest(BaseModel):
    session_id: str = ""
    goal_id: Optional[str] = None
    text: str = Field(default="", max_length=2000)
    transcript: list[dict[str, Any]] = Field(default_factory=list)
    open_threads: list[str] = Field(default_factory=list)


@router.post("/closing/suggest")
def closing_suggest(body: ClosingRequest):
    from services.product.goals import get_goal
    from services.product.quick_notes import ask_notes

    goal = get_goal(body.goal_id) if body.goal_id else None
    trigger = closing.detect(body.text) or "INTERVIEW_CLOSING"
    suggestions = closing.suggest(goal=goal, transcript=body.transcript, ask_notes=ask_notes(body.goal_id),
                                  open_threads=body.open_threads)
    if body.session_id:
        closing.record(body.session_id, trigger, suggestions)
    return {"trigger": trigger, "suggestions": suggestions}


@router.post("/closing/detect")
def closing_detect(body: ClosingRequest):
    return {"trigger": closing.detect(body.text)}


# ---------------------------------------------------------------------------
# Reflection
# ---------------------------------------------------------------------------


@router.get("/reflection/{session_kind}/{session_ref}")
def get_reflection(session_kind: str, session_ref: str):
    with domain_errors():
        return reflection.build(session_kind.upper(), session_ref)


class ReflectionActionBody(BaseModel):
    action: str
    finding: dict[str, Any] = Field(default_factory=dict)
    goal_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/reflection/{session_kind}/{session_ref}/actions")
def reflection_action(session_kind: str, session_ref: str, body: ReflectionActionBody):
    with domain_errors():
        return reflection.apply_action(body.action, session_kind=session_kind.upper(), session_ref=session_ref,
                                       finding=body.finding, goal_id=body.goal_id, payload=body.payload)


class FeedbackBody(BaseModel):
    question: str = "fast_cue_helpful"
    answer: str


@router.post("/reflection/{session_kind}/{session_ref}/feedback")
def reflection_feedback(session_kind: str, session_ref: str, body: FeedbackBody):
    with domain_errors():
        return reflection.record_feedback(session_kind.upper(), session_ref, body.question, body.answer)


# ---------------------------------------------------------------------------
# Client-side product events (cue expanded, deep opened, command executed …)
# ---------------------------------------------------------------------------


class EventBody(BaseModel):
    name: str
    goal_id: str = ""
    session_id: str = ""
    props: dict[str, Any] = Field(default_factory=dict)


@router.post("/events")
def record_event(body: EventBody):
    return {"recorded": events.record(body.name, goal_id=body.goal_id, session_id=body.session_id, **body.props)}
