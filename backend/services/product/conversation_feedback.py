"""Local explicit feedback for Chengzhu Conversation pilot evaluation.

This module stores only user-entered labels on this device.  It never infers
quality labels from Pin/Use/Dismiss actions and it never upgrades a session to
"real user validated".  Reviewer kind is provenance metadata, not identity
proof.
"""
from __future__ import annotations

import math
from typing import Any

from services.storage import product as store


FEEDBACK_KINDS = {"GUIDANCE", "SILENCE", "CONTINUE", "SESSION_OUTCOME"}
REVIEWER_KINDS = {"SELF_USER"}
_AI_GUIDANCE_KINDS = {
    "RECALL",
    "TALKING_POINT",
    "ANSWER_CUE",
    "QUESTION",
    "RISK",
    "DELIVERY",
    "CONTRIBUTION_OPPORTUNITY",
}


def _session(session_id: str) -> dict[str, Any]:
    row = store.get("conversation_session", session_id)
    if not row:
        raise ValueError("Conversation Session 不存在")
    return row


def _guidance(session_id: str, guidance_id: str) -> dict[str, Any]:
    row = store.get("conversation_guidance_event", guidance_id)
    if not row or row.get("session_id") != session_id:
        raise ValueError("Guidance 不属于当前 Session")
    if str(row.get("kind") or "") not in _AI_GUIDANCE_KINDS:
        raise ValueError("该 Guidance 类型不进入 Conversation AI pilot 质量标注")
    return row


def _optional_bool(labels: dict[str, Any], key: str) -> bool | None:
    value = labels.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"{key} 必须是 true / false / null")
    return value


def _cognitive_delta(labels: dict[str, Any]) -> float | None:
    value = labels.get("cognitive_load_delta")
    if value is None:
        return None
    if type(value) not in (int, float):
        raise ValueError("cognitive_load_delta 必须是 -2 到 2 的数值")
    value = float(value)
    if not math.isfinite(value) or not -2 <= value <= 2:
        raise ValueError("cognitive_load_delta 必须是 -2 到 2 的有限数值")
    return value


def _normalize_labels(
    session: dict[str, Any],
    kind: str,
    target_id: str,
    raw: dict[str, Any],
) -> dict[str, Any]:
    labels = dict(raw or {})
    if kind == "GUIDANCE":
        event = _guidance(session["id"], target_id)
        if event.get("status") != "SHOWN" or event.get("expression_action") == "SILENT":
            raise ValueError("GUIDANCE feedback 只能标注实际显示的 Guidance")
        out = {
            "useful": _optional_bool(labels, "useful"),
            "interruption_regret": _optional_bool(labels, "interruption_regret"),
            "source_correct": _optional_bool(labels, "source_correct"),
            "recall_correct": _optional_bool(labels, "recall_correct"),
        }
        if event.get("kind") != "RECALL" and out["recall_correct"] is not None:
            raise ValueError("recall_correct 只适用于 RECALL Guidance")
        if not any(value is not None for value in out.values()):
            raise ValueError("至少填写一个 Guidance 人工标签")
        return out

    if kind == "SILENCE":
        event = _guidance(session["id"], target_id)
        if event.get("status") != "SUPPRESSED" and event.get("expression_action") != "SILENT":
            raise ValueError("SILENCE feedback 只能标注实际被抑制 / SILENT 的 Guidance 决策")
        value = _optional_bool(labels, "silence_correct")
        if value is None:
            raise ValueError("silence_correct 必填")
        return {"silence_correct": value}

    if session.get("status") != "ENDED":
        raise ValueError("会后反馈只能在 Session 结束后填写")

    if kind == "CONTINUE":
        value = _optional_bool(labels, "writeback_accurate")
        if value is None:
            raise ValueError("writeback_accurate 必填")
        return {"writeback_accurate": value}

    if kind == "SESSION_OUTCOME":
        cognitive = _cognitive_delta(labels)
        reuse = _optional_bool(labels, "would_reuse_space")
        if cognitive is None and reuse is None:
            raise ValueError("至少填写 cognitive_load_delta 或 would_reuse_space")
        return {
            "cognitive_load_delta": cognitive,
            "would_reuse_space": reuse,
        }

    raise ValueError("不支持的 feedback kind")


def upsert_feedback(
    session_id: str,
    *,
    kind: str,
    target_id: str = "",
    labels: dict[str, Any] | None = None,
    note: str = "",
    reviewer_kind: str = "SELF_USER",
) -> dict[str, Any]:
    session = _session(session_id)
    kind = str(kind or "").strip().upper()
    if kind not in FEEDBACK_KINDS:
        raise ValueError("不支持的 feedback kind")
    reviewer_kind = str(reviewer_kind or "").strip().upper()
    if reviewer_kind not in REVIEWER_KINDS:
        raise ValueError("reviewer_kind 不支持；产品 API 只记录本机 SELF_USER 自报")
    target_id = str(target_id or "").strip()
    if kind in {"GUIDANCE", "SILENCE"} and not target_id:
        raise ValueError("Guidance / Silence feedback 需要 target_id")
    if kind in {"CONTINUE", "SESSION_OUTCOME"}:
        target_id = ""

    normalized = _normalize_labels(session, kind, target_id, dict(labels or {}))
    now = store.now()
    existing = store.rows(
        "SELECT * FROM conversation_human_feedback "
        "WHERE session_id = ? AND kind = ? AND target_id = ? AND reviewer_kind = ? LIMIT 1",
        (session_id, kind, target_id, reviewer_kind),
    )
    if existing:
        row_id = existing[0]["id"]
        store.update("conversation_human_feedback", row_id, {
            "labels": normalized,
            "note": str(note or "")[:2000],
            "updated_at": now,
        })
    else:
        row_id = store.new_id("hf_")
        store.insert("conversation_human_feedback", {
            "id": row_id,
            "space_id": session["space_id"],
            "session_id": session_id,
            "kind": kind,
            "target_id": target_id,
            "reviewer_kind": reviewer_kind,
            "labels": normalized,
            "note": str(note or "")[:2000],
            "created_at": now,
            "updated_at": now,
        })
    return store.get("conversation_human_feedback", row_id) or {}


def list_feedback(session_id: str) -> list[dict[str, Any]]:
    _session(session_id)
    return store.select(
        "conversation_human_feedback",
        where="session_id = ?",
        params=(session_id,),
        order="created_at ASC",
    )


def review_queue(session_id: str, limit: int = 40) -> dict[str, Any]:
    session = _session(session_id)
    rows = list_feedback(session_id)
    feedback_by_key = {
        (str(row.get("kind") or ""), str(row.get("target_id") or "")): row
        for row in rows
        if row.get("reviewer_kind") == "SELF_USER"
    }
    events = store.select(
        "conversation_guidance_event",
        where="session_id = ?",
        params=(session_id,),
        order="created_at DESC",
        limit=max(1, min(100, int(limit))),
    )
    guidance: list[dict[str, Any]] = []
    silence: list[dict[str, Any]] = []
    for event in events:
        if str(event.get("kind") or "") not in _AI_GUIDANCE_KINDS:
            continue
        if event.get("status") == "SHOWN" and event.get("expression_action") != "SILENT":
            guidance.append({
                "event": event,
                "feedback": feedback_by_key.get(("GUIDANCE", event["id"])),
            })
        elif event.get("status") == "SUPPRESSED" or event.get("expression_action") == "SILENT":
            silence.append({
                "event": event,
                "feedback": feedback_by_key.get(("SILENCE", event["id"])),
            })

    return {
        "session_id": session_id,
        "space_id": session["space_id"],
        "session_status": session["status"],
        "reviewer_kind": "SELF_USER",
        "evidence_boundary": "LOCAL_EXPLICIT_SELF_REPORT_NOT_REAL_USER_IDENTITY_PROOF",
        "guidance": guidance,
        "silence": silence,
        "continue_feedback": feedback_by_key.get(("CONTINUE", "")),
        "session_outcome": feedback_by_key.get(("SESSION_OUTCOME", "")),
        "remote_telemetry": "OFF",
        "real_user_validated": False,
        "pmf_proven": False,
    }
