"""v2.0 Personal Conversation Intelligence product service.

This is the first real runtime path for Conversation Profile.  It is additive
to the v1 Interview product: no Interview table is renamed or rewritten.

Truth rules:
- AI extraction is a candidate, never agreement.
- Decision AGREED requires source + explicit review.
- Commitment/Task COMMITTED requires owner + source + explicit review.
- proactive guidance is allowed to return SILENT/suppressed.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from services.product.future_profile import (
    AssistanceMode,
    ConversationItemState,
    ConversationItemType,
    ExpressionAction,
    GuidanceKind,
    OpportunityScore,
)
from services.storage import product as store


SPACE_PROFILES = {
    "PROJECT_SYNC": {
        "label": "项目同步",
        "default_mode": "BALANCED",
        "guidance": ["RECALL", "QUESTION", "RISK", "CONTRIBUTION_OPPORTUNITY", "TALKING_POINT"],
    },
    "DESIGN_REVIEW": {
        "label": "设计评审",
        "default_mode": "BALANCED",
        "guidance": ["RECALL", "TALKING_POINT", "QUESTION", "RISK", "CONTRIBUTION_OPPORTUNITY"],
    },
    "PRESENTATION_QA": {
        "label": "演示 / Q&A",
        "default_mode": "PRESENTATION",
        "guidance": ["ANSWER_CUE", "RECALL", "QUESTION", "DELIVERY"],
    },
    "ONE_ON_ONE": {
        "label": "1:1",
        "default_mode": "ONE_ON_ONE",
        "guidance": ["RECALL", "QUESTION", "TALKING_POINT", "RISK"],
    },
    "CLIENT_CALL": {
        "label": "客户会",
        "default_mode": "BALANCED",
        "guidance": [k.value for k in GuidanceKind],
    },
    "NEGOTIATION": {
        "label": "谈判",
        "default_mode": "QUIET",
        "guidance": ["RECALL", "TALKING_POINT", "QUESTION", "RISK", "CONTRIBUTION_OPPORTUNITY"],
    },
}
ASSISTANCE_MODES = {m.value for m in AssistanceMode}
CAPTURE_MODES = {"TRANSCRIPT", "NOTES_ONLY", "NO_CAPTURE"}
PROCESSING_MODES = {"LOCAL", "CLOUD", "OFF"}
ITEM_TYPES = {t.value for t in ConversationItemType}
ITEM_STATES = {s.value for s in ConversationItemState}
REVIEW_STATUSES = {"AI_EXTRACTED", "USER_CONFIRMED", "USER_EDITED", "USER_REJECTED", "SOURCE_CONFIRMED"}
EPISTEMIC_STATUSES = {"OBSERVED", "USER_CONFIRMED", "SOURCE_CONFIRMED", "INFERRED", "UNKNOWN"}


def templates() -> list[dict[str, Any]]:
    return [{"key": key, **value} for key, value in SPACE_PROFILES.items()]


def _require_choice(value: str, allowed: set[str], label: str) -> str:
    value = str(value or "").upper()
    if value not in allowed:
        raise ValueError(f"{label} 不支持：{value}")
    return value


def require_space(space_id: str) -> dict[str, Any]:
    row = store.get("conversation_space", space_id)
    if not row:
        raise ValueError("对话空间不存在")
    return row


def require_session(session_id: str) -> dict[str, Any]:
    row = store.get("conversation_session", session_id)
    if not row:
        raise ValueError("对话会话不存在")
    return row


def require_item(item_id: str) -> dict[str, Any]:
    row = store.get("conversation_item", item_id)
    if not row:
        raise ValueError("对话事项不存在")
    return row


def create_space(
    title: str,
    profile: str = "PROJECT_SYNC",
    *,
    description: str = "",
    default_goal: str = "",
    default_mode: str = "",
    project_id: str = "",
    relationship_key: str = "",
    selected_source_ids: Optional[list[str]] = None,
    selected_quick_note_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    title = str(title or "").strip()
    if not title:
        raise ValueError("对话空间名称不能为空")
    profile = str(profile or "").upper()
    if profile not in SPACE_PROFILES:
        raise ValueError(f"对话模板不支持：{profile}")
    mode = (default_mode or SPACE_PROFILES[profile]["default_mode"]).upper()
    _require_choice(mode, ASSISTANCE_MODES, "帮助方式")
    ts = store.now()
    row = {
        "id": store.new_id("cs_"),
        "profile": profile,
        "title": title[:160],
        "description": str(description or "")[:4000],
        "status": "ACTIVE",
        "project_id": str(project_id or "")[:200],
        "relationship_key": str(relationship_key or "")[:200],
        "default_goal": str(default_goal or "")[:1000],
        "default_mode": mode,
        "selected_source_ids": list(selected_source_ids or []),
        "selected_quick_note_ids": list(selected_quick_note_ids or []),
        "retention_policy": {"preset": "STANDARD"},
        "created_at": ts,
        "updated_at": ts,
    }
    store.insert("conversation_space", row)
    if row["default_goal"]:
        create_goal(row["id"], row["default_goal"])
    return require_space(row["id"])


def list_spaces(status: str = "ACTIVE") -> list[dict[str, Any]]:
    where = ""
    params: tuple[Any, ...] = ()
    if status:
        where, params = "status = ?", (status.upper(),)
    return store.select("conversation_space", where=where, params=params, order="updated_at DESC")


def update_space(space_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    current = require_space(space_id)
    allowed = {
        "title", "description", "status", "project_id", "relationship_key", "default_goal",
        "default_mode", "selected_source_ids", "selected_quick_note_ids", "retention_policy",
    }
    clean = {k: v for k, v in patch.items() if k in allowed}
    if "title" in clean:
        clean["title"] = str(clean["title"] or "").strip()[:160]
        if not clean["title"]:
            raise ValueError("对话空间名称不能为空")
    if "default_mode" in clean:
        clean["default_mode"] = _require_choice(str(clean["default_mode"]), ASSISTANCE_MODES, "帮助方式")
    if "status" in clean:
        clean["status"] = str(clean["status"]).upper()
        if clean["status"] not in {"ACTIVE", "ARCHIVED"}:
            raise ValueError("对话空间状态不支持")
    clean["updated_at"] = store.now()
    if clean:
        store.update("conversation_space", space_id, clean)
    return require_space(space_id) if clean else current


def delete_space(space_id: str) -> bool:
    require_space(space_id)
    return store.delete("conversation_space", space_id)


def create_goal(space_id: str, title: str, outcome_definition: str = "", priority: int = 50) -> dict[str, Any]:
    require_space(space_id)
    title = str(title or "").strip()
    if not title:
        raise ValueError("对话目标不能为空")
    row = {
        "id": store.new_id("cg_"),
        "space_id": space_id,
        "title": title[:240],
        "outcome_definition": str(outcome_definition or "")[:2000],
        "status": "ACTIVE",
        "priority": max(0, min(100, int(priority))),
        "source": {"kind": "USER"},
        "created_at": store.now(),
        "resolved_at": None,
    }
    store.insert("conversation_goal", row)
    return store.get("conversation_goal", row["id"]) or row


def add_participant(
    space_id: str,
    *,
    display_name: str = "",
    role: str = "",
    organization: str = "",
    session_id: str = "",
    identity_source: str = "USER",
) -> dict[str, Any]:
    require_space(space_id)
    if session_id:
        require_session(session_id)
    ts = store.now()
    row = {
        "id": store.new_id("cp_"),
        "space_id": space_id,
        "session_id": session_id or None,
        "display_name": str(display_name or "")[:160],
        "role": str(role or "")[:160],
        "organization": str(organization or "")[:160],
        "identity_confidence": 1.0 if display_name else 0.0,
        "identity_source": str(identity_source or "USER")[:80],
        "visibility": "PRIVATE",
        "observations": [],
        "created_at": ts,
        "updated_at": ts,
    }
    store.insert("conversation_participant", row)
    return store.get("conversation_participant", row["id"]) or row


def create_session(
    space_id: str,
    *,
    title: str = "",
    goal_ids: Optional[list[str]] = None,
    scheduled_at: Optional[float] = None,
    capture_mode: str = "NOTES_ONLY",
    processing_mode: str = "LOCAL",
    assistance_mode: str = "",
    consent_ack: bool = False,
) -> dict[str, Any]:
    space = require_space(space_id)
    capture = _require_choice(capture_mode, CAPTURE_MODES, "记录方式")
    processing = _require_choice(processing_mode, PROCESSING_MODES, "处理方式")
    mode = _require_choice(assistance_mode or space["default_mode"], ASSISTANCE_MODES, "帮助方式")
    ts = store.now()
    row = {
        "id": store.new_id("cv_"),
        "space_id": space_id,
        "goal_ids": list(goal_ids or []),
        "template": space["profile"],
        "title": (str(title or "").strip() or space["title"])[:200],
        "scheduled_at": scheduled_at,
        "started_at": None,
        "ended_at": None,
        "capture_mode": capture,
        "processing_mode": processing,
        "assistance_mode": mode,
        "consent_ack": bool(consent_ack),
        "pack_id": "",
        "status": "UPCOMING",
        "state": {"current_topic": "", "open_threads": [], "last_guidance_id": ""},
        "source_calendar_event": {},
        "created_at": ts,
        "updated_at": ts,
    }
    store.insert("conversation_session", row)
    return require_session(row["id"])


def list_sessions(space_id: str) -> list[dict[str, Any]]:
    require_space(space_id)
    return store.select(
        "conversation_session", where="space_id = ?", params=(space_id,),
        order="COALESCE(started_at, scheduled_at, created_at) DESC",
    )


def preflight(session_id: str) -> dict[str, Any]:
    session = require_session(session_id)
    space = require_space(session["space_id"])
    blockers: list[dict[str, str]] = []
    if session["capture_mode"] == "TRANSCRIPT" and not session["consent_ack"]:
        blockers.append({"key": "consent", "label": "转写确认", "message": "开启转写前，请确认当前场景允许记录/转写。"})
    items = [
        {"key": "goal", "label": "本次目标", "value": space.get("default_goal") or "可在会中补充", "ok": True},
        {"key": "mode", "label": "帮助方式", "value": session["assistance_mode"], "ok": True},
        {"key": "capture", "label": "记录方式", "value": session["capture_mode"], "ok": not blockers},
        {"key": "processing", "label": "处理方式", "value": session["processing_mode"], "ok": True},
        {"key": "sources", "label": "带入来源", "value": len(space.get("selected_source_ids") or []), "ok": True},
    ]
    return {
        "session": session,
        "space": space,
        "items": items,
        "blockers": blockers,
        "privacy_note": "记录、转写与第三方数据应遵循当前场景、组织政策与适用规则；成竹不会把点击开始当作其他参与者的同意。",
    }


def _confirmed_context_items(space_id: str) -> list[dict[str, Any]]:
    return store.select(
        "conversation_item",
        where="space_id = ? AND review_status IN ('USER_CONFIRMED','USER_EDITED','SOURCE_CONFIRMED') "
              "AND state NOT IN ('SUPERSEDED')",
        params=(space_id,),
        order="created_at DESC",
        limit=100,
    )


def freeze_pack(session_id: str) -> dict[str, Any]:
    session = require_session(session_id)
    space = require_space(session["space_id"])
    existing = store.select("conversation_session_pack", where="session_id = ?", params=(session_id,), limit=1)
    if existing:
        return existing[0]
    selected_notes: list[dict[str, Any]] = []
    for note_id in space.get("selected_quick_note_ids") or []:
        note = store.get("quick_note", str(note_id))
        if note:
            selected_notes.append({"id": note["id"], "title": note.get("title", ""), "content": note.get("content", ""), "kind": "USER_NOTE"})
    participants = store.select("conversation_participant", where="space_id = ?", params=(space["id"],), order="created_at ASC")
    payload = {
        "contract": "v2.0-R1",
        "space": {"id": space["id"], "profile": space["profile"], "title": space["title"]},
        "goal_ids": session.get("goal_ids") or [],
        "selected_source_ids": space.get("selected_source_ids") or [],
        "quick_notes": selected_notes,
        "confirmed_items": _confirmed_context_items(space["id"]),
        "participants": participants,
        "policy": {
            "capture_mode": session["capture_mode"],
            "processing_mode": session["processing_mode"],
            "assistance_mode": session["assistance_mode"],
            "consent_ack": bool(session["consent_ack"]),
            "external_writeback": "REVIEW_REQUIRED",
        },
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    row = {
        "id": store.new_id("cpack_"),
        "session_id": session_id,
        "space_id": space["id"],
        "payload": payload,
        "digest": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "created_at": store.now(),
    }
    store.insert("conversation_session_pack", row)
    store.update("conversation_session", session_id, {"pack_id": row["id"], "updated_at": store.now()})
    return store.get("conversation_session_pack", row["id"]) or row


def start_session(session_id: str) -> dict[str, Any]:
    check = preflight(session_id)
    if check["blockers"]:
        raise ValueError(check["blockers"][0]["message"])
    session = check["session"]
    if session["status"] == "ENDED":
        raise ValueError("已结束的会话不能重新开始")
    pack = freeze_pack(session_id)
    ts = store.now()
    store.update("conversation_session", session_id, {"status": "ACTIVE", "started_at": session.get("started_at") or ts, "updated_at": ts})
    return {"session": require_session(session_id), "pack": pack}


def add_item(
    session_id: str,
    *,
    item_type: str,
    title: str,
    state: str = "PROPOSED",
    detail: str = "",
    owner_id: str = "",
    speaker_id: str = "",
    due_at: str = "",
    source_refs: Optional[list[dict[str, Any]]] = None,
    source_excerpt: str = "",
    confidence: float = 0.0,
    epistemic_status: str = "UNKNOWN",
    review_status: str = "AI_EXTRACTED",
    supersedes_id: str = "",
) -> dict[str, Any]:
    session = require_session(session_id)
    item_type = item_type if item_type in ITEM_TYPES else item_type.title()
    if item_type not in ITEM_TYPES:
        raise ValueError(f"事项类型不支持：{item_type}")
    state = _require_choice(state, ITEM_STATES, "事项状态")
    review_status = _require_choice(review_status, REVIEW_STATUSES, "审核状态")
    epistemic_status = _require_choice(epistemic_status, EPISTEMIC_STATUSES, "认知状态")
    refs = list(source_refs or [])
    if state == "AGREED" and not (refs and review_status in {"USER_CONFIRMED", "USER_EDITED", "SOURCE_CONFIRMED"}):
        raise ValueError("Decision 升级为 AGREED 需要来源与明确确认")
    if state == "COMMITTED" and not (owner_id and refs and review_status in {"USER_CONFIRMED", "USER_EDITED", "SOURCE_CONFIRMED"}):
        raise ValueError("Commitment 升级为 COMMITTED 需要 owner、来源与明确确认")
    title = str(title or "").strip()
    if not title:
        raise ValueError("事项内容不能为空")
    ts = store.now()
    row = {
        "id": store.new_id("ci_"),
        "space_id": session["space_id"],
        "session_id": session_id,
        "type": item_type,
        "state": state,
        "title": title[:1000],
        "detail": str(detail or "")[:5000],
        "speaker_id": str(speaker_id or "")[:120],
        "owner_id": str(owner_id or "")[:120],
        "due_at": str(due_at or "")[:120],
        "source_refs": refs,
        "source_excerpt": str(source_excerpt or "")[:3000],
        "confidence": max(0.0, min(1.0, float(confidence or 0.0))),
        "epistemic_status": epistemic_status,
        "review_status": review_status,
        "supersedes_id": str(supersedes_id or "")[:120],
        "visibility": "PRIVATE",
        "created_at": ts,
        "updated_at": ts,
    }
    store.insert("conversation_item", row)
    return require_item(row["id"])


def review_item(item_id: str, action: str, patch: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    item = require_item(item_id)
    action = str(action or "").upper()
    patch = dict(patch or {})
    update: dict[str, Any] = {}
    if action == "CONFIRM":
        update["review_status"] = "USER_CONFIRMED"
        if item["type"] == "Decision" and item["state"] == "PROPOSED":
            if not item.get("source_refs"):
                raise ValueError("Decision 确认前需要来源")
            update["state"] = "AGREED"
        elif item["type"] in {"Commitment", "Task"} and item["state"] == "PROPOSED":
            owner = str(patch.get("owner_id") or item.get("owner_id") or "")
            if not owner or not item.get("source_refs"):
                raise ValueError("Commitment 确认前需要 owner 与来源")
            update["owner_id"] = owner
            update["state"] = "COMMITTED"
    elif action == "EDIT":
        for key in ("title", "detail", "owner_id", "speaker_id", "due_at", "source_excerpt"):
            if key in patch:
                update[key] = patch[key]
        update["review_status"] = "USER_EDITED"
    elif action == "REJECT":
        update.update({"review_status": "USER_REJECTED", "state": "UNKNOWN"})
    elif action == "DONE":
        if item["state"] != "COMMITTED":
            raise ValueError("只有 COMMITTED 事项才能标记 DONE")
        update["state"] = "DONE"
        update["review_status"] = "USER_CONFIRMED"
    elif action == "SUPERSEDE":
        update["state"] = "SUPERSEDED"
        update["review_status"] = "USER_CONFIRMED"
        if patch.get("supersedes_id"):
            update["supersedes_id"] = str(patch["supersedes_id"])
    else:
        raise ValueError("审核动作不支持")
    update["updated_at"] = store.now()
    store.update("conversation_item", item_id, update)
    return require_item(item_id)


def continue_summary(session_id: str) -> dict[str, Any]:
    session = require_session(session_id)
    items = store.select("conversation_item", where="session_id = ?", params=(session_id,), order="created_at ASC")
    decisions = [i for i in items if i["type"] == "Decision" and i["state"] == "AGREED"]
    commitments = [i for i in items if i["type"] in {"Commitment", "Task"} and i["state"] in {"COMMITTED", "DONE"}]
    open_questions = [i for i in items if i["type"] == "OpenQuestion" and i["state"] not in {"DONE", "SUPERSEDED"}]
    candidates = [i for i in items if i["review_status"] == "AI_EXTRACTED"]
    next_focus = None
    if open_questions:
        next_focus = {"kind": "OPEN_QUESTION", "title": open_questions[0]["title"], "source_ref": open_questions[0]["id"]}
    else:
        owed = [i for i in commitments if i["state"] == "COMMITTED" and i.get("owner_id") in {"me", "SELF", "我"}]
        if owed:
            next_focus = {"kind": "COMMITMENT", "title": owed[0]["title"], "source_ref": owed[0]["id"]}
    return {
        "session": session,
        "decisions": decisions,
        "commitments": commitments,
        "open_questions": open_questions,
        "candidates": candidates,
        "next_focus": next_focus,
        "review_required": len(candidates),
    }


def end_session(session_id: str) -> dict[str, Any]:
    session = require_session(session_id)
    ts = store.now()
    if session["status"] != "ENDED":
        store.update("conversation_session", session_id, {"status": "ENDED", "ended_at": ts, "updated_at": ts})
    return continue_summary(session_id)


def _score(body: dict[str, Any]) -> OpportunityScore:
    keys = {
        "relevance", "novelty", "provenance_strength", "role_relevance", "goal_relevance", "urgency",
        "decision_impact", "interruption_cost", "already_mentioned", "uncertainty", "social_risk",
        "stale_context_risk",
    }
    values = {key: float(body.get(key) or 0.0) for key in keys}
    return OpportunityScore(**values)


def _persist_guidance(
    session_id: str,
    *,
    kind: str,
    action: str,
    text: str,
    source_refs: list[dict[str, Any]],
    status: str,
    reason: str = "",
    score: Optional[OpportunityScore] = None,
) -> dict[str, Any]:
    ts = store.now()
    row = {
        "id": store.new_id("ge_"),
        "session_id": session_id,
        "candidate_id": store.new_id("gc_"),
        "kind": kind,
        "expression_action": action,
        "text": text,
        "source_refs": source_refs,
        "status": status,
        "reason": reason,
        "score": {"value": score.value, **score.__dict__} if score else {},
        "user_action": "NONE",
        "rendered_at": ts if status == "SHOWN" else None,
        "created_at": ts,
    }
    store.insert("conversation_guidance_event", row)
    saved = store.get("conversation_guidance_event", row["id"]) or row
    session = require_session(session_id)
    state = dict(session.get("state") or {})
    if status == "SHOWN":
        state["last_guidance_id"] = row["id"]
        store.update("conversation_session", session_id, {"state": state, "updated_at": ts})
    return saved


def evaluate_guidance(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
    session = require_session(session_id)
    if session["status"] != "ACTIVE":
        raise ValueError("只有进行中的会话可以生成实时提示")
    state = dict(session.get("state") or {})
    current_topic = str(body.get("current_topic") or "").strip()[:500]
    if current_topic:
        state["current_topic"] = current_topic
        store.update("conversation_session", session_id, {"state": state, "updated_at": store.now()})

    source_refs = list(body.get("source_refs") or [])
    direct_question = str(body.get("direct_question") or "").strip()
    if direct_question:
        event = _persist_guidance(
            session_id,
            kind="ANSWER_CUE",
            action=ExpressionAction.ANSWER.value,
            text=str(body.get("answer_cue") or "先直接回答问题，再补一条有来源的事实。")[:1200],
            source_refs=source_refs,
            status="SHOWN",
            reason="DIRECT_QUESTION",
        )
        return {"guidance": event, "suppressed": None}

    if bool(body.get("user_speaking")):
        event = _persist_guidance(
            session_id, kind="CONTRIBUTION_OPPORTUNITY", action=ExpressionAction.SILENT.value,
            text="", source_refs=source_refs, status="SUPPRESSED", reason="USER_SPEAKING",
        )
        return {"guidance": None, "suppressed": "USER_SPEAKING", "event": event}

    mode = str(session.get("assistance_mode") or "BALANCED").upper()
    candidate_text = str(body.get("candidate_text") or "").strip()
    if candidate_text:
        if not source_refs:
            event = _persist_guidance(
                session_id, kind="CONTRIBUTION_OPPORTUNITY", action=ExpressionAction.SILENT.value,
                text="", source_refs=[], status="SUPPRESSED", reason="NO_SOURCE",
            )
            return {"guidance": None, "suppressed": "NO_SOURCE", "event": event}
        score = _score(body)
        threshold = {"QUIET": float("inf"), "BALANCED": 2.5, "ACTIVE": 1.5, "PRESENTATION": 2.5, "ONE_ON_ONE": 3.0}.get(mode, 2.5)
        if score.value < threshold:
            event = _persist_guidance(
                session_id, kind="CONTRIBUTION_OPPORTUNITY", action=ExpressionAction.SILENT.value,
                text="", source_refs=source_refs, status="SUPPRESSED", reason="BELOW_THRESHOLD", score=score,
            )
            return {"guidance": None, "suppressed": "BELOW_THRESHOLD", "event": event}
        event = _persist_guidance(
            session_id, kind="CONTRIBUTION_OPPORTUNITY", action=ExpressionAction.ADD_TALKING_POINT.value,
            text=candidate_text[:1200], source_refs=source_refs, status="SHOWN", reason="HIGH_VALUE_OPPORTUNITY", score=score,
        )
        return {"guidance": event, "suppressed": None}

    open_questions = store.select(
        "conversation_item",
        where="space_id = ? AND type = 'OpenQuestion' AND state NOT IN ('DONE','SUPERSEDED')",
        params=(session["space_id"],), order="created_at DESC", limit=1,
    )
    if mode != "QUIET" and open_questions:
        item = open_questions[0]
        event = _persist_guidance(
            session_id, kind="QUESTION", action=ExpressionAction.ASK_QUESTION.value,
            text=item["title"], source_refs=item.get("source_refs") or [], status="SHOWN", reason="OPEN_QUESTION",
        )
        return {"guidance": event, "suppressed": None}

    event = _persist_guidance(
        session_id, kind="RECALL", action=ExpressionAction.SILENT.value,
        text="", source_refs=[], status="SUPPRESSED", reason="NO_HIGH_VALUE_GUIDANCE",
    )
    return {"guidance": None, "suppressed": "NO_HIGH_VALUE_GUIDANCE", "event": event}


def set_guidance_action(guidance_id: str, action: str) -> dict[str, Any]:
    row = store.get("conversation_guidance_event", guidance_id)
    if not row:
        raise ValueError("实时提示不存在")
    action = str(action or "").upper()
    if action not in {"EXPANDED", "PINNED", "DISMISSED", "SNOOZED", "USED", "NONE"}:
        raise ValueError("提示动作不支持")
    store.update("conversation_guidance_event", guidance_id, {"user_action": action})
    return store.get("conversation_guidance_event", guidance_id) or row


def space_detail(space_id: str) -> dict[str, Any]:
    space = require_space(space_id)
    goals = store.select("conversation_goal", where="space_id = ?", params=(space_id,), order="priority DESC, created_at ASC")
    sessions = list_sessions(space_id)
    participants = store.select("conversation_participant", where="space_id = ?", params=(space_id,), order="created_at ASC")
    items = store.select("conversation_item", where="space_id = ?", params=(space_id,), order="created_at DESC", limit=200)
    threads = store.select("conversation_open_thread", where="space_id = ? AND status = 'OPEN'", params=(space_id,), order="created_at DESC")
    return {
        **space,
        "goals": goals,
        "sessions": sessions,
        "participants": participants,
        "decisions": [i for i in items if i["type"] == "Decision"],
        "commitments": [i for i in items if i["type"] in {"Commitment", "Task"}],
        "open_questions": [i for i in items if i["type"] == "OpenQuestion"],
        "threads": threads,
    }


def prepare_space(space_id: str) -> dict[str, Any]:
    detail = space_detail(space_id)
    active = [i for i in detail["commitments"] if i["state"] not in {"DONE", "SUPERSEDED"}]
    unresolved = [i for i in detail["open_questions"] if i["state"] not in {"DONE", "SUPERSEDED"}]
    decisions = [i for i in detail["decisions"] if i["state"] == "AGREED"]
    next_sessions = [s for s in detail["sessions"] if s["status"] == "UPCOMING"]
    next_sessions.sort(key=lambda s: s.get("scheduled_at") or float("inf"))
    return {
        "space": {k: detail[k] for k in ("id", "profile", "title", "description", "default_goal", "default_mode", "selected_source_ids", "selected_quick_note_ids")},
        "goals": detail["goals"],
        "next_session": next_sessions[0] if next_sessions else None,
        "open_commitments": active,
        "open_questions": unresolved,
        "related_decisions": decisions[:12],
        "participants": detail["participants"],
        "selected_sources": detail.get("selected_source_ids") or [],
        "selected_quick_notes": detail.get("selected_quick_note_ids") or [],
    }


def home_summary() -> dict[str, Any]:
    spaces = list_spaces("ACTIVE")
    if not spaces:
        return {
            "state": "EMPTY", "spaces": [], "next_session": None, "next_focus": None,
            "owed_by_me": [], "open_questions": [], "recent_change": None,
        }
    now = store.now()
    upcoming = store.select(
        "conversation_session",
        where="status = 'UPCOMING' AND scheduled_at IS NOT NULL AND scheduled_at >= ?",
        params=(now,), order="scheduled_at ASC", limit=1,
    )
    owed = store.select(
        "conversation_item",
        where="type IN ('Commitment','Task') AND state = 'COMMITTED' AND owner_id IN ('me','SELF','我')",
        order="created_at DESC", limit=8,
    )
    open_questions = store.select(
        "conversation_item",
        where="type = 'OpenQuestion' AND state NOT IN ('DONE','SUPERSEDED')",
        order="created_at DESC", limit=8,
    )
    changes = store.select(
        "conversation_item",
        where="review_status IN ('USER_CONFIRMED','USER_EDITED','SOURCE_CONFIRMED') "
              "AND state IN ('AGREED','COMMITTED','DONE','SUPERSEDED')",
        order="updated_at DESC", limit=1,
    )
    next_focus: Optional[dict[str, Any]] = None
    if upcoming:
        next_focus = {"kind": "PREPARE", "title": f"准备下一场：{upcoming[0]['title']}", "space_id": upcoming[0]["space_id"]}
    elif open_questions:
        next_focus = {"kind": "OPEN_QUESTION", "title": open_questions[0]["title"], "space_id": open_questions[0]["space_id"]}
    elif owed:
        next_focus = {"kind": "COMMITMENT", "title": owed[0]["title"], "space_id": owed[0]["space_id"]}
    return {
        "state": "ACTIVE",
        "spaces": spaces,
        "next_session": upcoming[0] if upcoming else None,
        "next_focus": next_focus,
        "owed_by_me": owed,
        "open_questions": open_questions,
        "recent_change": changes[0] if changes else None,
    }


def export_space(space_id: str) -> dict[str, Any]:
    detail = space_detail(space_id)
    return {
        "kind": "CONVERSATION_SPACE",
        "contract": "v2.0-R1",
        "space": {k: v for k, v in detail.items() if k not in {"goals", "sessions", "participants", "decisions", "commitments", "open_questions", "threads"}},
        "goals": detail["goals"],
        "sessions": detail["sessions"],
        "participants": detail["participants"],
        "items": store.select("conversation_item", where="space_id = ?", params=(space_id,), order="created_at ASC"),
        "threads": detail["threads"],
        "packs": store.select("conversation_session_pack", where="space_id = ?", params=(space_id,), order="created_at ASC"),
        "guidance": store.rows(
            "SELECT g.* FROM conversation_guidance_event g JOIN conversation_session s ON s.id = g.session_id "
            "WHERE s.space_id = ? ORDER BY g.created_at ASC",
            (space_id,),
        ),
    }
