"""v1.3 Goal / Home / History / Next Focus API (mounted under /api/v3)."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from api.product.common import domain_errors
from services.product import goals, history, home, next_focus, trends, workspace

router = APIRouter(tags=["product-goals"])


class GoalCreate(BaseModel):
    company: str = Field(default="", max_length=120)
    role: str = Field(default="", max_length=120)
    jd: str = Field(default="", max_length=40000)
    stage: str = Field(default="", max_length=40)
    next_interview_at: Optional[float] = None
    interview_round: str = Field(default="", max_length=60)
    goal_notes: str = Field(default="", max_length=4000)
    selected_resume_id: Optional[int] = None


class GoalPatch(BaseModel):
    company: Optional[str] = Field(default=None, max_length=120)
    role: Optional[str] = Field(default=None, max_length=120)
    jd: Optional[str] = Field(default=None, max_length=40000)
    status: Optional[str] = None
    stage: Optional[str] = Field(default=None, max_length=40)
    goal_notes: Optional[str] = Field(default=None, max_length=4000)
    selected_resume_id: Optional[int] = None
    selected_material_ids: Optional[list[str]] = None
    selected_kb_ids: Optional[list[str]] = None
    selected_quick_note_ids: Optional[list[str]] = None
    active_question_bank_ids: Optional[list[str]] = None
    offer_state: Optional[str] = None
    role_family: Optional[str] = None


@router.get("/home")
def get_home():
    return home.summary()


@router.get("/goals")
def list_goals(status: str = ""):
    return {"items": goals.list_goals(status)}


@router.post("/goals")
def create_goal(body: GoalCreate):
    with domain_errors():
        goal = goals.create_goal(**body.model_dump())
        next_focus.recompute(goal["id"])
        return goals.require_goal(goal["id"])


@router.get("/goals/{goal_id}")
def get_goal(goal_id: str, opened: bool = False):
    with domain_errors():
        goal = goals.open_goal(goal_id) if opened else goals.require_goal(goal_id)
        return {
            **goal,
            "interviews": goals.list_interviews(goal_id),
            "offer": goals.get_offer(goal_id),
            "next_focus": next_focus.active_items(goal_id),
            "sessions": history.list_history(goal_id=goal_id, limit=50),
        }


@router.patch("/goals/{goal_id}")
def patch_goal(goal_id: str, body: GoalPatch):
    with domain_errors():
        patch = body.model_dump(exclude_unset=True)
        goal = goals.update_goal(goal_id, patch)
        if any(k in patch for k in ("jd", "role")):
            next_focus.recompute(goal_id)
        return goal


@router.delete("/goals/{goal_id}")
def delete_goal(goal_id: str):
    with domain_errors():
        result = goals.delete_goal(goal_id)
    from services.product.data_export import integrity

    result["integrity"] = integrity(repair=True)
    return result


@router.get("/goals/{goal_id}/prepare")
def goal_prepare(goal_id: str):
    with domain_errors():
        goal = goals.require_goal(goal_id)
    ws = workspace.goal_workspace(goal)
    from services.product.materials import materials_for_pack
    from services.product.quick_notes import notes_for_pack

    stories = workspace.stories_list()
    return {
        "goal_id": goal_id,
        "next_focus": next_focus.active_items(goal_id),
        "gap_map": ws.get("gap_map", []),
        "attack_surface": ws.get("attack_surface", []),
        "question_graph": ws.get("question_graph", []),
        "stories": {**(ws.get("stories") or {}), "coverage": workspace.story_coverage(stories)},
        "has_jd": ws.get("has_jd", False),
        "materials": materials_for_pack(goal) | {"selected_ids": goal.get("selected_material_ids", [])},
        "pack_preview": {"quick_notes": notes_for_pack(goal), "materials": materials_for_pack(goal)["included"],
                         "legacy_prep_space_id": goal.get("legacy_prep_space_id")},
    }


class InterviewCreate(BaseModel):
    round: str = Field(default="", max_length=60)
    scheduled_at: Optional[float] = None
    kind: str = "REAL"
    notes: str = Field(default="", max_length=2000)


class InterviewPatch(BaseModel):
    round: Optional[str] = Field(default=None, max_length=60)
    scheduled_at: Optional[float] = None
    kind: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


@router.post("/goals/{goal_id}/interviews")
def add_interview(goal_id: str, body: InterviewCreate):
    with domain_errors():
        return goals.add_interview(goal_id, round_name=body.round, scheduled_at=body.scheduled_at, kind=body.kind,
                                   notes=body.notes)


@router.patch("/interviews/{interview_id}")
def patch_interview(interview_id: str, body: InterviewPatch):
    with domain_errors():
        return goals.update_interview(interview_id, body.model_dump(exclude_unset=True))


@router.delete("/interviews/{interview_id}")
def delete_interview(interview_id: str):
    return {"deleted": goals.delete_interview(interview_id)}


class OfferPatch(BaseModel):
    status: Optional[str] = None
    comp: Optional[str] = Field(default=None, max_length=2000)
    deadline: Optional[float] = None
    notes: Optional[str] = Field(default=None, max_length=4000)


@router.get("/goals/{goal_id}/offer")
def get_offer(goal_id: str):
    with domain_errors():
        return goals.get_offer(goal_id)


@router.put("/goals/{goal_id}/offer")
def put_offer(goal_id: str, body: OfferPatch):
    with domain_errors():
        return goals.set_offer(goal_id, body.model_dump(exclude_unset=True))


class LinkSession(BaseModel):
    session_kind: str = "REAL"
    review_session_id: Optional[int] = None
    practice_id: str = ""
    round: str = ""


@router.post("/goals/{goal_id}/sessions")
def link_session(goal_id: str, body: LinkSession):
    with domain_errors():
        return goals.link_session(goal_id, body.session_kind, review_session_id=body.review_session_id,
                                  practice_id=body.practice_id, round_name=body.round)


# ---------------------------------------------------------------------------
# Next Focus
# ---------------------------------------------------------------------------


@router.get("/goals/{goal_id}/next-focus")
def get_next_focus(goal_id: str, refresh: bool = False):
    from services.product import events

    with domain_errors():
        goals.require_goal(goal_id)
        items = next_focus.recompute(goal_id) if refresh else next_focus.active_items(goal_id)
    events.record("next_focus_opened", goal_id=goal_id)
    return {"items": items, "practice_defaults": next_focus.practice_defaults(goal_id)}


class FocusCreate(BaseModel):
    type: str
    title: str = Field(max_length=120)
    reason: str = Field(default="", max_length=400)
    source_kind: str = "USER"
    source_ref: str = ""


@router.post("/goals/{goal_id}/next-focus")
def set_next_focus(goal_id: str, body: FocusCreate):
    with domain_errors():
        return next_focus.set_user_focus(goal_id, body.type, body.title, body.reason or "你手动设定的重点",
                                         source_kind=body.source_kind, source_ref=body.source_ref)


@router.post("/next-focus/{focus_id}/complete")
def complete_focus(focus_id: str):
    return {"item": next_focus.complete(focus_id)}


@router.post("/next-focus/{focus_id}/dismiss")
def dismiss_focus(focus_id: str):
    return {"item": next_focus.dismiss(focus_id)}


# ---------------------------------------------------------------------------
# History / trends
# ---------------------------------------------------------------------------


@router.get("/history")
def get_history(goal_id: str = "", type: str = "", round: str = "",  # noqa: A002 — query names
                since: Optional[float] = None, until: Optional[float] = None,
                limit: int = Query(default=100, ge=1, le=500)):
    return {"items": history.list_history(goal_id=goal_id, type_=type, round_name=round, since=since, until=until,
                                          limit=limit)}


@router.post("/history/{review_session_id}/goal")
def link_history_goal(review_session_id: int, body: dict[str, Any]):
    with domain_errors():
        return history.link_review_to_goal(review_session_id, str(body.get("goal_id") or ""),
                                           str(body.get("kind") or "REAL"), str(body.get("round") or ""))


@router.get("/trends")
def get_trends(goal_id: str = "", window: int = Query(default=5, ge=2, le=30)):
    return trends.trends(goal_id or None, window)


@router.post("/goals/backfill")
def backfill(force: bool = False):
    return goals.backfill_from_legacy(force=force)
