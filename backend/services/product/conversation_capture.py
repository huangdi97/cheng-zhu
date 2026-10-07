"""Conversation Profile capture bridge.

Reuses the mature Assist audio/VAD/STT transport but isolates product meaning:
- no auto answer / interview fast-cue planner
- no Interview Review persistence
- no identity inference from audio channels
- transcript rows live only in Conversation namespace
- a live Interview owns audio devices and cannot be pre-empted

The two audio channels are intentionally named PRIMARY_AUDIO and SELF_MIC;
they are capture provenance, not inferred participant identities.
"""
from __future__ import annotations

import threading
from typing import Any, Optional

from core.config import session_overlay, set_session_overlay
from core.session import conversation_lock, get_session
from services.product import conversations
from services.storage import product as store

_lock = threading.RLock()
_active_session_id = ""
_stopping_session_id = ""
_previous_overlay: dict[str, Any] = {}
_device_id: Optional[int] = None
_candidate_mic_device_id: Optional[int] = None
_legacy_snapshot: dict[str, Any] = {}


def is_active() -> bool:
    with _lock:
        return bool(_active_session_id)


def status(session_id: str = "") -> dict[str, Any]:
    with _lock:
        active = bool(_active_session_id)
        legacy = get_session()
        return {
            "active": active,
            "session_id": _active_session_id,
            "owns_requested_session": bool(session_id and session_id == _active_session_id),
            "device_id": _device_id,
            "candidate_mic_device_id": _candidate_mic_device_id,
            "mode": "TRANSCRIPTION_ONLY" if active else "IDLE",
            "paused": bool(getattr(legacy, "is_paused", False)) if active else False,
            "stopping": bool(_stopping_session_id and _stopping_session_id == _active_session_id),
        }


def _session_state(session_id: str, **patch: Any) -> None:
    session = conversations.require_session(session_id)
    state = dict(session.get("state") or {})
    capture = dict(state.get("capture") or {})
    capture.update(patch)
    state["capture"] = capture
    store.update("conversation_session", session_id, {"state": state, "updated_at": store.now()})


def start(session_id: str, device_id: int, candidate_mic_device_id: Optional[int] = None) -> dict[str, Any]:
    global _active_session_id, _previous_overlay, _device_id, _candidate_mic_device_id, _legacy_snapshot
    session = conversations.require_session(session_id)
    if session["status"] != "ACTIVE":
        raise ValueError("只有已开始的 Conversation Session 可以启动转写")
    if session["capture_mode"] != "TRANSCRIPT":
        raise ValueError("本场记录方式不是 TRANSCRIPT")
    if not session["consent_ack"]:
        raise ValueError("启动转写前需要完成 Preflight 记录确认")
    processing = conversations.processing_runtime_status(
        session,
        include_self_mic=candidate_mic_device_id is not None,
    )
    if processing["blockers"]:
        raise ValueError(processing["blockers"][0])

    with _lock:
        if _active_session_id and _active_session_id != session_id:
            raise ValueError("另一场 Conversation 正在占用音频采集")
        legacy = get_session()
        if legacy.is_recording and not _active_session_id:
            raise ValueError("Interview Live 正在录音；Conversation 不会抢占其音频设备")
        if _active_session_id == session_id:
            return status(session_id)

        with conversation_lock:
            _legacy_snapshot = {
                "is_recording": bool(legacy.is_recording),
                "is_paused": bool(legacy.is_paused),
                "last_device_id": getattr(legacy, "last_device_id", 0),
                "last_candidate_mic_device_id": getattr(legacy, "last_candidate_mic_device_id", 0),
                "capture_is_loopback": bool(getattr(legacy, "capture_is_loopback", False)),
            }
        previous = session_overlay()
        overlay = {
            **previous,
            "assist_auto_answer_mode": "off",
            "auto_detect": False,
            "intelligence_early_cue": False,
            "assist_provisional_cue": False,
            "assist_final_provisional_cue": False,
            "review_enabled": False,
            "speech_adoption_analytics_live": False,
            "candidate_asr_enabled": candidate_mic_device_id is not None,
        }
        set_session_overlay(overlay)
        _previous_overlay = previous
        _active_session_id = session_id
        _device_id = int(device_id)
        _candidate_mic_device_id = int(candidate_mic_device_id) if candidate_mic_device_id is not None else None
        try:
            from api.assist.pipeline import start_nonblocking
            start_nonblocking(_device_id, _candidate_mic_device_id)
            # Candidate/self-mic capture is an optional degraded path. The
            # shared pipeline records 0 when opening it failed; expose that
            # actual state instead of echoing the requested device id.
            if _candidate_mic_device_id is not None:
                actual_candidate = int(getattr(legacy, "last_candidate_mic_device_id", 0) or 0)
                if actual_candidate <= 0:
                    _candidate_mic_device_id = None
        except Exception:
            with conversation_lock:
                for key, value in _legacy_snapshot.items():
                    setattr(legacy, key, value)
            _active_session_id = ""
            _previous_overlay = {}
            _device_id = None
            _candidate_mic_device_id = None
            _legacy_snapshot = {}
            set_session_overlay(previous)
            raise

        _session_state(
            session_id,
            active=True,
            mode="TRANSCRIPTION_ONLY",
            device_id=_device_id,
            candidate_mic_device_id=_candidate_mic_device_id,
        )
        return status(session_id)


def pause(session_id: str) -> dict[str, Any]:
    with _lock:
        if session_id != _active_session_id:
            raise ValueError("这场 Conversation 没有正在运行的音频采集")
        if _stopping_session_id == session_id:
            raise ValueError("这场 Conversation 正在停止音频采集")
    from api.assist.pipeline import pause_interview
    pause_interview()
    _session_state(session_id, paused=True)
    return {**status(session_id), "paused": True}


def resume(session_id: str) -> dict[str, Any]:
    with _lock:
        if session_id != _active_session_id:
            raise ValueError("这场 Conversation 没有正在运行的音频采集")
        if _stopping_session_id == session_id:
            raise ValueError("这场 Conversation 正在停止音频采集")
        device_id = _device_id
        candidate_mic_device_id = _candidate_mic_device_id
    from api.assist.pipeline import unpause_interview
    unpause_interview(device_id, candidate_mic_device_id)
    _session_state(session_id, paused=False)
    return {**status(session_id), "paused": False}


def stop(session_id: str) -> dict[str, Any]:
    global _active_session_id, _stopping_session_id, _previous_overlay, _device_id, _candidate_mic_device_id, _legacy_snapshot
    with _lock:
        if session_id != _active_session_id:
            return status(session_id)
        if _stopping_session_id == session_id:
            return status(session_id)
        _stopping_session_id = session_id
        previous = dict(_previous_overlay)
        legacy_snapshot = dict(_legacy_snapshot)

    # Do not hold the Conversation lock while draining shared ASR workers:
    # their final transcription callback re-enters record_transcription(), which
    # needs this lock. Keeping the lock here can deadlock stop↔worker and lose
    # the last utterance.
    try:
        from api.assist.pipeline import stop_interview_loop
        stop_interview_loop()
    finally:
        set_session_overlay(previous)
        legacy = get_session()
        with conversation_lock:
            for key, value in legacy_snapshot.items():
                setattr(legacy, key, value)
        _session_state(session_id, active=False, paused=False)
        with _lock:
            if _active_session_id == session_id:
                _active_session_id = ""
                _previous_overlay = {}
                _device_id = None
                _candidate_mic_device_id = None
                _legacy_snapshot = {}
            _stopping_session_id = ""
    return status(session_id)


def record_transcription(
    text: str,
    *,
    channel: str,
    provider: str = "",
    source: str = "",
    is_final: bool = True,
) -> Optional[dict[str, Any]]:
    """Persist a final ASR segment into the active Conversation session.

    Called by the shared ASR pipeline. It is a no-op when no Conversation
    capture owns the pipeline, so Interview behavior remains unchanged.
    """
    cleaned = str(text or "").strip()
    if not cleaned or not is_final:
        return None
    with _lock:
        session_id = _active_session_id
    if not session_id:
        return None
    session = conversations.require_session(session_id)
    if session["status"] != "ACTIVE":
        return None
    row = {
        "id": store.new_id("cts_"),
        "space_id": session["space_id"],
        "session_id": session_id,
        "channel": str(channel or "PRIMARY_AUDIO")[:80],
        "text": cleaned[:20_000],
        "provider": str(provider or "")[:80],
        "source": str(source or "")[:120],
        "is_final": True,
        "created_at": store.now(),
    }
    store.insert("conversation_transcript_segment", row)

    guidance = conversations.guidance_from_transcript(session_id, cleaned, channel=str(channel or "PRIMARY_AUDIO"))
    try:
        from api.realtime.ws import broadcast
        broadcast({"type": "conversation_transcription", "session_id": session_id, "segment": row})
        if guidance:
            broadcast({"type": "conversation_guidance", "session_id": session_id, "guidance": guidance})
    except Exception:
        pass
    return store.get("conversation_transcript_segment", row["id"]) or row


def transcript(session_id: str, limit: int = 100) -> list[dict[str, Any]]:
    conversations.require_session(session_id)
    limit = max(1, min(500, int(limit)))
    rows = store.select(
        "conversation_transcript_segment",
        where="session_id = ?",
        params=(session_id,),
        order="created_at DESC",
        limit=limit,
    )
    rows.reverse()
    return rows
