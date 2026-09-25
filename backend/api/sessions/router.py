"""多场面试会话隔离：新建/切换/删除/重命名独立会话。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.logger import get_logger
from core.session import (
    activate_session,
    create_session,
    delete_session,
    list_sessions,
    rename_session,
    session_id,
    snapshot_session,
)

router = APIRouter()
_log = get_logger("sessions.router")


class CreateSessionRequest(BaseModel):
    label: str = Field(default="", max_length=80)


class RenameSessionRequest(BaseModel):
    label: str = Field(default="", max_length=80)


def _broadcast_sessions() -> None:
    try:
        from api.realtime.ws import broadcast
        broadcast({"type": "sessions_changed", "items": list_sessions(), "active_id": session_id()})
    except Exception as e:  # noqa: BLE001
        _log.debug("sessions broadcast failed: %s", e)


@router.get("/sessions")
async def api_list_sessions():
    return {"items": list_sessions(), "active_id": session_id()}


@router.post("/sessions")
async def api_create_session(body: CreateSessionRequest):
    sess = create_session(label=body.label)
    snap = snapshot_session()
    _broadcast_sessions()
    try:
        from api.realtime.ws import broadcast
        broadcast({"type": "session_switched", **snap})
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "session_id": sess.session_id, **snap}


@router.post("/sessions/{sid}/activate")
async def api_activate_session(sid: str):
    target = activate_session(sid)
    if target is None:
        raise HTTPException(404, "会话不存在")
    snap = snapshot_session()
    _broadcast_sessions()
    try:
        from api.realtime.ws import broadcast
        broadcast({"type": "session_switched", **snap})
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "session_id": sid, **snap}


@router.patch("/sessions/{sid}")
async def api_rename_session(sid: str, body: RenameSessionRequest):
    if not rename_session(sid, body.label):
        raise HTTPException(404, "会话不存在")
    _broadcast_sessions()
    return {"ok": True}


@router.delete("/sessions/{sid}")
async def api_delete_session(sid: str):
    if not delete_session(sid):
        raise HTTPException(400, "无法删除当前激活会话或会话不存在")
    _broadcast_sessions()
    return {"ok": True}
