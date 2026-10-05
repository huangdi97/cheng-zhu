"""v1.3 Library + Me API: materials, Quick Notes, Question Banks, Fact Inbox, Stories."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, File, Form, Query, UploadFile
from pydantic import BaseModel, Field

from api.product.common import domain_errors
from services.product import events, fact_inbox, materials, question_banks, quick_notes, workspace

router = APIRouter(tags=["product-library"])

MAX_UPLOAD_BYTES = 30 * 1024 * 1024


# ---------------------------------------------------------------------------
# Materials (taxonomy + lifecycle)
# ---------------------------------------------------------------------------


@router.get("/materials")
def list_materials(kind: str = ""):
    return {"items": materials.list_materials(kind)}


@router.post("/materials")
async def create_material(
    title: str = Form(default=""),
    kind: str = Form(default="PROJECT"),
    usage: str = Form(default="FACTS"),
    text: str = Form(default=""),
    file: Optional[UploadFile] = File(default=None),
    background: bool = Form(default=True),
):
    data = await file.read() if file is not None else None
    if data is not None and len(data) > MAX_UPLOAD_BYTES:
        return {"error": "文件超过 30MB"}
    with domain_errors():
        return materials.create_material(title, kind=kind, usage=usage, filename=file.filename if file else "",
                                         text=text, data=data, background=background)


@router.post("/materials/{material_id}/replace")
async def replace_material(material_id: str, text: str = Form(default=""),
                           file: Optional[UploadFile] = File(default=None), background: bool = Form(default=True)):
    data = await file.read() if file is not None else None
    with domain_errors():
        return materials.replace_material(material_id, filename=file.filename if file else "", text=text, data=data,
                                          background=background)


@router.post("/materials/{material_id}/retry")
async def retry_material(material_id: str, text: str = Form(default=""),
                         file: Optional[UploadFile] = File(default=None), background: bool = Form(default=True)):
    data = await file.read() if file is not None else None
    with domain_errors():
        return materials.retry_material(material_id, text=text, data=data, filename=file.filename if file else "",
                                        background=background)


@router.get("/materials/{material_id}")
def get_material(material_id: str):
    with domain_errors():
        return materials.require_material(material_id)


class UsagePatch(BaseModel):
    usage: str


@router.patch("/materials/{material_id}")
def patch_material(material_id: str, body: UsagePatch):
    with domain_errors():
        return materials.set_usage(material_id, body.usage)


@router.delete("/materials/{material_id}")
def delete_material(material_id: str):
    return {"deleted": materials.delete_material(material_id)}


# ---------------------------------------------------------------------------
# Quick Notes
# ---------------------------------------------------------------------------


class NoteCreate(BaseModel):
    content: str = Field(default="", max_length=4000)
    title: str = Field(default="", max_length=120)
    scope: str = "GLOBAL"
    goal_id: Optional[str] = None
    pinned: bool = False
    tags: list[str] = Field(default_factory=list)


class NotePatch(BaseModel):
    content: Optional[str] = Field(default=None, max_length=4000)
    title: Optional[str] = Field(default=None, max_length=120)
    scope: Optional[str] = None
    goal_id: Optional[str] = None
    pinned: Optional[bool] = None
    tags: Optional[list[str]] = None
    base_revision: Optional[int] = None


@router.get("/quick-notes")
def list_notes(goal_id: str = "", scope: str = "", context: str = ""):
    if context == "live":
        events.record("quick_note_opened_in_live", goal_id=goal_id)
    else:
        events.record("quick_note_opened", goal_id=goal_id)
    return {"items": quick_notes.list_notes(goal_id or None, scope=scope)}


@router.post("/quick-notes")
def create_note(body: NoteCreate):
    with domain_errors():
        return quick_notes.create_note(body.content, title=body.title, scope=body.scope, goal_id=body.goal_id,
                                       pinned=body.pinned, tags=body.tags)


@router.patch("/quick-notes/{note_id}")
def patch_note(note_id: str, body: NotePatch):
    patch = body.model_dump(exclude_unset=True)
    base = patch.pop("base_revision", None)
    with domain_errors():
        return quick_notes.update_note(note_id, patch, base_revision=base)


@router.delete("/quick-notes/{note_id}")
def delete_note(note_id: str):
    return {"deleted": quick_notes.delete_note(note_id)}


class Reorder(BaseModel):
    ids: list[str]


@router.post("/quick-notes/reorder")
def reorder_notes(body: Reorder):
    return {"changed": quick_notes.reorder(body.ids)}


# ---------------------------------------------------------------------------
# Question banks
# ---------------------------------------------------------------------------


class BankCreate(BaseModel):
    name: str = Field(max_length=80)
    scope: str = "USER"
    role: str = ""
    company: str = ""
    source_type: str = "USER_ADDED"
    goal_id: Optional[str] = None


class ItemCreate(BaseModel):
    text: str = Field(max_length=600)
    category: str = Field(default="", max_length=40)
    difficulty: str = "STANDARD"
    origin: str = "USER_ADDED"
    source_url: str = Field(default="", max_length=500)
    rounds: list[str] = Field(default_factory=list)


class ImportBody(BaseModel):
    lines: list[str]
    source_url: str = ""


@router.get("/question-banks")
def list_banks(role: str = "", goal_id: str = ""):
    return {"items": question_banks.list_banks(role, goal_id)}


@router.post("/question-banks")
def create_bank(body: BankCreate):
    with domain_errors():
        return question_banks.create_bank(**body.model_dump())


@router.get("/question-banks/{bank_id}/items")
def bank_items(bank_id: str):
    return {"items": question_banks.list_items(bank_id)}


@router.post("/question-banks/{bank_id}/items")
def add_item(bank_id: str, body: ItemCreate):
    with domain_errors():
        return question_banks.add_item(bank_id, body.text, category=body.category, difficulty=body.difficulty,
                                       origin=body.origin, source_url=body.source_url, rounds=body.rounds)


@router.post("/question-banks/{bank_id}/import")
def import_items(bank_id: str, body: ImportBody):
    with domain_errors():
        return {"imported": question_banks.import_items(bank_id, body.lines, body.source_url)}


@router.delete("/question-banks/{bank_id}")
def delete_bank(bank_id: str):
    with domain_errors():
        return {"deleted": question_banks.delete_bank(bank_id)}


@router.delete("/question-bank-items/{item_id}")
def delete_item(item_id: str):
    with domain_errors():
        return {"deleted": question_banks.delete_item(item_id)}


# ---------------------------------------------------------------------------
# Me: Fact Inbox + Stories coverage
# ---------------------------------------------------------------------------


@router.get("/fact-inbox")
def get_inbox(opened: bool = False, limit: int = Query(default=30, ge=1, le=200)):
    if opened:
        fact_inbox.mark_opened()
    return fact_inbox.inbox(limit=limit)


class InboxAction(BaseModel):
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


class BatchAction(BaseModel):
    ids: list[str]
    action: str


@router.post("/fact-inbox/batch")
def inbox_batch(body: BatchAction):
    with domain_errors():
        return fact_inbox.batch_resolve(body.ids, body.action)


@router.post("/fact-inbox/{claim_id}")
def inbox_action(claim_id: str, body: InboxAction):
    with domain_errors():
        return fact_inbox.resolve(claim_id, body.action, body.payload)


@router.get("/fact-inbox/metrics")
def inbox_metrics():
    return fact_inbox.metrics()


@router.get("/stories/coverage")
def stories_coverage():
    stories = workspace.stories_list()
    return {"stories": stories, **workspace.story_coverage(stories)}
