"""v2.0 Conversation Profile API, mounted under /api/product/conversation."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.product.common import domain_errors
from services.product import conversation_capture, conversations

router = APIRouter(prefix="/conversation", tags=["product-conversation"])


def _stop_capture_for_session(session_id: str) -> None:
    state = conversation_capture.status(session_id)
    if state.get("owns_requested_session"):
        conversation_capture.stop(session_id)


def _stop_capture_for_space(space_id: str) -> None:
    state = conversation_capture.status()
    active_session_id = str(state.get("session_id") or "")
    if not active_session_id:
        return
    try:
        session = conversations.require_session(active_session_id)
    except ValueError:
        return
    if session.get("space_id") == space_id:
        conversation_capture.stop(active_session_id)


class SpaceCreate(BaseModel):
    title: str = Field(max_length=160)
    profile: str = "PROJECT_SYNC"
    description: str = Field(default="", max_length=4000)
    default_goal: str = Field(default="", max_length=1000)
    default_mode: str = ""
    project_id: str = Field(default="", max_length=200)
    relationship_key: str = Field(default="", max_length=200)
    selected_source_ids: list[str] = Field(default_factory=list)
    selected_quick_note_ids: list[str] = Field(default_factory=list)


class SpacePatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=160)
    description: Optional[str] = Field(default=None, max_length=4000)
    status: Optional[str] = None
    default_goal: Optional[str] = Field(default=None, max_length=1000)
    default_mode: Optional[str] = None
    project_id: Optional[str] = Field(default=None, max_length=200)
    relationship_key: Optional[str] = Field(default=None, max_length=200)
    selected_source_ids: Optional[list[str]] = None
    selected_quick_note_ids: Optional[list[str]] = None
    retention_policy: Optional[dict[str, Any]] = None


@router.get("/templates")
def templates():
    return {"items": conversations.templates()}


@router.get("/home")
def home():
    return conversations.home_summary()


@router.get("/history")
def history(limit: int = 100):
    with domain_errors():
        return {"items": conversations.conversation_history(limit)}


@router.get("/search")
def search(query: str = "", item_type: str = "", limit: int = 50):
    with domain_errors():
        return {"items": conversations.search_items(query=query, item_type=item_type, limit=limit)}


@router.get("/diagnostics")
def diagnostics():
    return conversations.diagnostics()


@router.get("/demo")
def demo():
    return conversations.synthetic_demo()


class AdhocCreate(BaseModel):
    title: str = Field(default="临时对话", max_length=160)
    profile: str = "PROJECT_SYNC"
    assistance_mode: str = ""


@router.post("/adhoc")
def adhoc(body: AdhocCreate):
    with domain_errors():
        return conversations.create_adhoc(**body.model_dump())


@router.get("/spaces")
def spaces(status: str = ""):
    return {"items": conversations.list_space_summaries(status)}


@router.post("/spaces")
def create_space(body: SpaceCreate):
    with domain_errors():
        return conversations.create_space(**body.model_dump())


@router.get("/spaces/{space_id}")
def get_space(space_id: str):
    with domain_errors():
        return conversations.space_detail(space_id)


@router.patch("/spaces/{space_id}")
def patch_space(space_id: str, body: SpacePatch):
    with domain_errors():
        return conversations.update_space(space_id, body.model_dump(exclude_unset=True))


@router.delete("/spaces/{space_id}")
def delete_space(space_id: str, confirm: bool = False):
    with domain_errors():
        if confirm:
            _stop_capture_for_space(space_id)
        return {"deleted": conversations.delete_space(space_id, confirm=confirm)}


@router.get("/spaces/{space_id}/prepare")
def prepare(space_id: str):
    with domain_errors():
        return conversations.prepare_space(space_id)


@router.get("/spaces/{space_id}/export")
def export_space(space_id: str):
    with domain_errors():
        return conversations.export_space(space_id)


@router.get("/spaces/{space_id}/retention")
def retention_preview(space_id: str):
    with domain_errors():
        return conversations.retention_preview(space_id)


class RetentionApply(BaseModel):
    confirm: bool = False


@router.post("/spaces/{space_id}/retention/apply")
def retention_apply(space_id: str, body: RetentionApply):
    with domain_errors():
        return conversations.apply_retention(space_id, confirm=body.confirm)


class GoalCreate(BaseModel):
    title: str = Field(max_length=240)
    outcome_definition: str = Field(default="", max_length=2000)
    priority: int = Field(default=50, ge=0, le=100)


@router.post("/spaces/{space_id}/goals")
def add_goal(space_id: str, body: GoalCreate):
    with domain_errors():
        return conversations.create_goal(space_id, **body.model_dump())


class GoalPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=240)
    outcome_definition: Optional[str] = Field(default=None, max_length=2000)
    priority: Optional[int] = Field(default=None, ge=0, le=100)
    status: Optional[str] = None


@router.patch("/goals/{goal_id}")
def patch_goal(goal_id: str, body: GoalPatch):
    with domain_errors():
        return conversations.update_goal(goal_id, body.model_dump(exclude_unset=True))


class ParticipantCreate(BaseModel):
    display_name: str = Field(default="", max_length=160)
    role: str = Field(default="", max_length=160)
    organization: str = Field(default="", max_length=160)
    session_id: str = ""
    identity_source: str = "USER"
    explicit_priority: str = Field(default="", max_length=800)
    explicit_concern: str = Field(default="", max_length=1200)
    stated_position: str = Field(default="", max_length=1600)
    decision_authority: str = Field(default="", max_length=500)
    relationship_context: str = Field(default="", max_length=800)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/spaces/{space_id}/participants")
def add_participant(space_id: str, body: ParticipantCreate):
    with domain_errors():
        return conversations.add_participant(space_id, **body.model_dump())


class ParticipantPatch(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=160)
    role: Optional[str] = Field(default=None, max_length=160)
    organization: Optional[str] = Field(default=None, max_length=160)
    explicit_priority: Optional[str] = Field(default=None, max_length=800)
    explicit_concern: Optional[str] = Field(default=None, max_length=1200)
    stated_position: Optional[str] = Field(default=None, max_length=1600)
    decision_authority: Optional[str] = Field(default=None, max_length=500)
    relationship_context: Optional[str] = Field(default=None, max_length=800)
    source_refs: Optional[list[dict[str, Any]]] = None


@router.patch("/participants/{participant_id}")
def patch_participant(participant_id: str, body: ParticipantPatch):
    with domain_errors():
        return conversations.update_participant(participant_id, body.model_dump(exclude_unset=True))


class SessionCreate(BaseModel):
    title: str = Field(default="", max_length=200)
    goal_ids: list[str] = Field(default_factory=list)
    scheduled_at: Optional[float] = None
    capture_mode: str = "NOTES_ONLY"
    processing_mode: str = "LOCAL"
    assistance_mode: str = ""
    consent_ack: bool = False
    policy: dict[str, Any] = Field(default_factory=dict)


@router.post("/spaces/{space_id}/sessions")
def create_session(space_id: str, body: SessionCreate):
    with domain_errors():
        return conversations.create_session(space_id, **body.model_dump())


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    with domain_errors():
        return conversations.require_session(session_id)


@router.get("/sessions/{session_id}/context")
def get_session_context(session_id: str):
    with domain_errors():
        return conversations.session_context(session_id)


@router.get("/sessions/{session_id}/export")
def export_session(session_id: str):
    with domain_errors():
        return conversations.export_session(session_id)


class SessionDelete(BaseModel):
    confirmed_policy: str = "BLOCK"


@router.post("/sessions/{session_id}/delete")
def delete_session(session_id: str, body: SessionDelete):
    with domain_errors():
        _stop_capture_for_session(session_id)
        return conversations.delete_session(session_id, confirmed_policy=body.confirmed_policy)


class SessionPatch(BaseModel):
    assistance_mode: Optional[str] = None
    capture_mode: Optional[str] = None
    processing_mode: Optional[str] = None
    consent_ack: Optional[bool] = None
    policy: Optional[dict[str, Any]] = None


@router.patch("/sessions/{session_id}")
def patch_session(session_id: str, body: SessionPatch):
    with domain_errors():
        return conversations.update_session(session_id, body.model_dump(exclude_unset=True))


class AskBody(BaseModel):
    question: str = Field(max_length=2000)


@router.post("/sessions/{session_id}/ask")
def ask_session(session_id: str, body: AskBody):
    with domain_errors():
        return conversations.ask(session_id, body.question)


class CaptureStart(BaseModel):
    device_id: int
    candidate_mic_device_id: Optional[int] = None


@router.get("/sessions/{session_id}/capture")
def capture_status(session_id: str):
    with domain_errors():
        conversations.require_session(session_id)
        return conversation_capture.status(session_id)


@router.post("/sessions/{session_id}/capture/start")
def capture_start(session_id: str, body: CaptureStart):
    with domain_errors():
        return conversation_capture.start(session_id, body.device_id, body.candidate_mic_device_id)


@router.post("/sessions/{session_id}/capture/pause")
def capture_pause(session_id: str):
    with domain_errors():
        return conversation_capture.pause(session_id)


@router.post("/sessions/{session_id}/capture/resume")
def capture_resume(session_id: str):
    with domain_errors():
        return conversation_capture.resume(session_id)


@router.post("/sessions/{session_id}/capture/stop")
def capture_stop(session_id: str):
    with domain_errors():
        return conversation_capture.stop(session_id)


@router.get("/sessions/{session_id}/transcript")
def transcript(session_id: str, limit: int = 100):
    with domain_errors():
        return {"items": conversation_capture.transcript(session_id, limit)}


@router.get("/sessions/{session_id}/preflight")
def preflight(session_id: str):
    with domain_errors():
        return conversations.preflight(session_id)


@router.post("/sessions/{session_id}/start")
def start_session(session_id: str):
    with domain_errors():
        return conversations.start_session(session_id)


@router.post("/sessions/{session_id}/end")
def end_session(session_id: str):
    with domain_errors():
        _stop_capture_for_session(session_id)
        return conversations.end_session(session_id)


@router.get("/sessions/{session_id}/continue")
def continue_session(session_id: str):
    with domain_errors():
        return conversations.continue_summary(session_id)


class ItemCreate(BaseModel):
    item_type: str
    title: str = Field(max_length=1000)
    state: str = "PROPOSED"
    detail: str = Field(default="", max_length=5000)
    owner_id: str = Field(default="", max_length=120)
    speaker_id: str = Field(default="", max_length=120)
    due_at: str = Field(default="", max_length=120)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    source_excerpt: str = Field(default="", max_length=3000)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    epistemic_status: str = "UNKNOWN"
    review_status: str = "AI_EXTRACTED"
    supersedes_id: str = ""


@router.post("/sessions/{session_id}/items")
def add_item(session_id: str, body: ItemCreate):
    with domain_errors():
        return conversations.add_item(session_id, **body.model_dump())


class ReviewBody(BaseModel):
    action: str
    patch: dict[str, Any] = Field(default_factory=dict)


@router.post("/items/{item_id}/review")
def review_item(item_id: str, body: ReviewBody):
    with domain_errors():
        return conversations.review_item(item_id, body.action, body.patch)


@router.post("/threads/{thread_id}/resolve")
def resolve_open_thread(thread_id: str):
    with domain_errors():
        return conversations.resolve_open_thread(thread_id)


class DraftActionCreate(BaseModel):
    kind: str
    title: str = Field(default="", max_length=300)
    content: str = Field(default="", max_length=20000)
    target: str = Field(default="", max_length=500)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/sessions/{session_id}/draft-actions")
def create_draft_action(session_id: str, body: DraftActionCreate):
    with domain_errors():
        return conversations.create_draft_action(session_id, **body.model_dump())


@router.post("/sessions/{session_id}/followup-draft")
def create_followup_draft(session_id: str):
    with domain_errors():
        return conversations.followup_draft(session_id)


class DerivedDraftCreate(BaseModel):
    kind: str


@router.post("/sessions/{session_id}/derived-draft")
def create_derived_draft(session_id: str, body: DerivedDraftCreate):
    with domain_errors():
        return conversations.derived_writeback_draft(session_id, body.kind)


@router.get("/spaces/{space_id}/draft-actions")
def list_draft_actions(space_id: str, status: str = ""):
    with domain_errors():
        return {"items": conversations.list_draft_actions(space_id, status)}


class DraftActionReview(BaseModel):
    action: str


@router.post("/draft-actions/{action_id}/review")
def review_draft_action(action_id: str, body: DraftActionReview):
    with domain_errors():
        return conversations.review_draft_action(action_id, body.action)


class GuidanceBody(BaseModel):
    current_topic: str = Field(default="", max_length=500)
    direct_question: str = Field(default="", max_length=1200)
    answer_cue: str = Field(default="", max_length=1200)
    critical_risk: str = Field(default="", max_length=1200)
    talking_point: str = Field(default="", max_length=1200)
    delivery_focus: str = Field(default="", max_length=1200)
    candidate_text: str = Field(default="", max_length=1200)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    user_speaking: bool = False
    relevance: float = 0
    novelty: float = 0
    provenance_strength: float = 0
    role_relevance: float = 0
    goal_relevance: float = 0
    urgency: float = 0
    decision_impact: float = 0
    interruption_cost: float = 0
    already_mentioned: float = 0
    uncertainty: float = 0
    social_risk: float = 0
    stale_context_risk: float = 0
    audience_role: str = Field(default="", max_length=240)
    audience_priority: str = Field(default="", max_length=800)
    audience_concern: str = Field(default="", max_length=1200)
    decision_authority: str = Field(default="", max_length=500)
    relationship_context: str = Field(default="", max_length=800)


@router.post("/sessions/{session_id}/guidance/evaluate")
def evaluate_guidance(session_id: str, body: GuidanceBody):
    with domain_errors():
        return conversations.evaluate_guidance(session_id, body.model_dump())


class GuidanceAction(BaseModel):
    action: str


@router.get("/sessions/{session_id}/guidance")
def guidance_history(session_id: str, limit: int = 30):
    with domain_errors():
        return {"items": conversations.guidance_history(session_id, limit)}


@router.post("/guidance/{guidance_id}/status")
def guidance_action(guidance_id: str, body: GuidanceAction):
    with domain_errors():
        return conversations.set_guidance_action(guidance_id, body.action)
