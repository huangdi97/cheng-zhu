"""v1.3 Settings layers + v1.4 validation, export/delete, integrity, future profile."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from api.product.common import domain_errors
from services.product import data_export, events, future_profile, settings_layers, validation

router = APIRouter(tags=["product-insights"])


@router.get("/settings/layers")
def get_layers(goal_id: str = "", session_id: str = ""):
    return {"items": settings_layers.resolve(goal_id, session_id), "origin_labels": settings_layers.ORIGIN_LABELS}


class LayerSet(BaseModel):
    scope: str
    scope_id: str
    key: str
    value: Any = None


@router.put("/settings/layers")
def set_layer(body: LayerSet):
    with domain_errors():
        return settings_layers.set_override(body.scope, body.scope_id, body.key, body.value)


@router.delete("/settings/layers")
def clear_layer(scope: str, scope_id: str, key: str = ""):
    return {"cleared": settings_layers.clear_override(scope, scope_id, key)}


@router.get("/validation")
def validation_report():
    return validation.report()


@router.get("/validation/transfer")
def validation_transfer(goal_id: str = ""):
    return validation.practice_transfer(goal_id)


@router.get("/events")
def list_events(name: str = "", goal_id: str = "", since: float = 0.0, limit: int = 200):
    return {"items": events.list_events(name, goal_id, since, min(limit, 2000)), "counts": events.counts(since)}


@router.delete("/events")
def clear_events():
    return {"deleted": events.clear()}


class ExportBody(BaseModel):
    kind: str
    goal_id: Optional[str] = None
    session_kind: Optional[str] = None
    session_ref: Optional[str] = None


@router.post("/export")
def export(body: ExportBody):
    with domain_errors():
        if body.kind == "person":
            out = data_export.export_person()
        elif body.kind == "goal":
            out = data_export.export_goal(str(body.goal_id or ""))
        elif body.kind == "session":
            out = data_export.export_session(str(body.session_kind or ""), str(body.session_ref or ""))
        elif body.kind == "reflection":
            out = data_export.export_reflection(str(body.session_kind or ""), str(body.session_ref or ""))
        elif body.kind == "quick_notes":
            out = data_export.export_quick_notes()
        elif body.kind == "question_banks":
            out = data_export.export_question_banks()
        else:
            raise ValueError(f"未知导出类型：{body.kind}")
    return out


@router.delete("/sessions/{session_kind}/{session_ref}")
def delete_session(session_kind: str, session_ref: str):
    with domain_errors():
        return data_export.delete_session(session_kind.upper(), session_ref)


@router.get("/integrity")
def integrity(repair: bool = False):
    return data_export.integrity(repair=repair)


@router.get("/future-profile")
def future_profile_contracts():
    return {
        "profiles": [{"key": p.key, "label": p.label, "productized": p.productized,
                      "guidance_kinds": [k.value for k in p.guidance_kinds]} for p in future_profile.PROFILES],
        "guidance_kinds": [k.value for k in future_profile.GuidanceKind],
        "conversation_item_types": [t.value for t in future_profile.ConversationItemType],
        "conversation_item_states": [s.value for s in future_profile.ConversationItemState],
        "status": "CANONICAL_RETAINED · NOT_PRODUCTIZED",
    }
