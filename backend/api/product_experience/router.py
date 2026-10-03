"""v1.3/v1.4 goal-centered product experience API."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.storage import prep_space, product_experience as px

router = APIRouter(prefix="/product")


class GoalMetaPatch(BaseModel):
    stage: Optional[str] = Field(default=None, max_length=40)
    interview_round: Optional[str] = Field(default=None, max_length=120)
    next_interview_at: Optional[float] = None
    next_focus: Optional[list[dict[str, Any]]] = None
    offer: Optional[dict[str, Any]] = None


class QuickNoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(default="", max_length=20000)
    scope: str = Field(default="GOAL", max_length=20)
    goal_id: Optional[int] = None
    pinned: bool = False


class QuickNotePatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    content: Optional[str] = Field(default=None, max_length=20000)
    scope: Optional[str] = Field(default=None, max_length=20)
    goal_id: Optional[int] = None
    pinned: Optional[bool] = None
    sort_order: Optional[int] = None


class QuestionBankCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    scope: str = Field(default="GLOBAL", max_length=30)
    role: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    source_type: str = Field(default="USER_ADDED", max_length=40)


class QuestionItemCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000)
    category: str = Field(default="general", max_length=60)
    difficulty: str = Field(default="standard", max_length=30)
    origin: str = Field(default="USER_ADDED", max_length=40)
    source_url: str = Field(default="", max_length=2000)


class PinCreate(BaseModel):
    session_id: str = Field(default="", max_length=200)
    goal_id: Optional[int] = None
    turn_id: str = Field(default="", max_length=200)
    label: str = Field(default="IMPORTANT", max_length=40)
    question: str = Field(default="", max_length=5000)
    transcript_excerpt: str = Field(default="", max_length=10000)
    note: str = Field(default="", max_length=5000)


class EventCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    goal_id: Optional[int] = None
    session_id: str = Field(default="", max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)


def _goal_projection(space: dict[str, Any]) -> dict[str, Any]:
    meta = px.get_goal_meta(int(space["id"]))
    next_focus = list(meta.get("next_focus") or [])
    if not next_focus:
        # Deterministic fallback: expose existing gap/insight state without
        # inventing a fake readiness percentage.
        fallback: list[dict[str, Any]] = []
        if not str(space.get("jd_text") or "").strip():
            fallback.append({"type": "material", "title": "补充岗位 JD", "reason": "当前 Goal 还没有 JD", "action": "ADD_JD"})
        if not str(space.get("resume_text") or "").strip():
            fallback.append({"type": "material", "title": "选择简历", "reason": "当前 Goal 还没有简历来源", "action": "ADD_RESUME"})
        if str(space.get("questions_status") or "") != "done":
            fallback.append({"type": "practice", "title": "生成岗位问题", "reason": "还没有可练习的问题集", "action": "GENERATE_QUESTIONS"})
        next_focus = fallback[:3]
    return {
        **space,
        "goal_id": int(space["id"]),
        "stage": meta.get("stage", "active"),
        "interview_round": meta.get("interview_round", ""),
        "next_interview_at": meta.get("next_interview_at"),
        "next_focus": next_focus,
        "offer": meta.get("offer") or {},
        "quick_note_count": len([n for n in px.list_quick_notes(int(space["id"])) if n.get("goal_id") == int(space["id"])]),
    }


@router.get("/goals")
async def list_goals():
    return {"items": [_goal_projection(space) for space in prep_space.list_spaces()]}


@router.get("/goals/{goal_id}")
async def get_goal(goal_id: int):
    space = prep_space.get_space(goal_id)
    if not space:
        raise HTTPException(404, "求职目标不存在")
    return _goal_projection(space)


@router.patch("/goals/{goal_id}")
async def patch_goal(goal_id: int, req: GoalMetaPatch):
    if not prep_space.get_space(goal_id):
        raise HTTPException(404, "求职目标不存在")
    return px.upsert_goal_meta(goal_id, **req.model_dump(exclude_unset=True))


@router.get("/quick-notes")
async def list_quick_notes(goal_id: Optional[int] = None):
    return {"items": px.list_quick_notes(goal_id)}


@router.post("/quick-notes")
async def create_quick_note(req: QuickNoteCreate):
    try:
        return px.create_quick_note(**req.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/quick-notes/{note_id}")
async def patch_quick_note(note_id: int, req: QuickNotePatch):
    item = px.update_quick_note(note_id, req.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(404, "Quick Note 不存在")
    return item


@router.delete("/quick-notes/{note_id}")
async def delete_quick_note(note_id: int):
    if not px.delete_quick_note(note_id):
        raise HTTPException(404, "Quick Note 不存在")
    return {"ok": True}


@router.get("/question-banks")
async def list_question_banks():
    return {"items": px.list_question_banks()}


@router.post("/question-banks")
async def create_question_bank(req: QuestionBankCreate):
    return px.create_question_bank(**req.model_dump())


@router.get("/question-banks/{bank_id}")
async def get_question_bank(bank_id: int):
    item = px.get_question_bank(bank_id)
    if not item:
        raise HTTPException(404, "题库不存在")
    return item


@router.post("/question-banks/{bank_id}/items")
async def add_question_item(bank_id: int, req: QuestionItemCreate):
    try:
        return px.add_question_item(bank_id, **req.model_dump())
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/pins")
async def list_pins(session_id: str = "", goal_id: Optional[int] = None):
    return {"items": px.list_pins(session_id=session_id, goal_id=goal_id)}


@router.post("/pins")
async def create_pin(req: PinCreate):
    return px.create_pin(**req.model_dump())


@router.post("/events")
async def record_event(req: EventCreate):
    px.record_event(req.name, goal_id=req.goal_id, session_id=req.session_id, payload=req.payload)
    return {"ok": True}


@router.get("/events/summary")
async def event_summary(goal_id: Optional[int] = None):
    return px.event_summary(goal_id)
