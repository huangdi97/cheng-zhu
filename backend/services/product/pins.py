"""Pin Moment (canonical §13): the user decides what mattered.

Saved per pin: timestamp, session id, turn id, question, surrounding
transcript (a short excerpt kept locally), tag and user note. Reflection
lists pins first. A pin becomes Next Focus only through an explicit user
action (``promote_to_focus``) — never automatically.
"""
from __future__ import annotations

from typing import Any, Optional

from core.logger import get_logger
from services.product import events
from services.storage import product as store

_log = get_logger(__name__)

TAGS = ("IMPORTANT", "BAD_ANSWER", "COUNTERPARTY_INFO", "PREP_NEXT", "FACT_CHECK", "CUSTOM")
SESSION_KINDS = ("LIVE", "PRACTICE")
TAG_LABELS = {
    "IMPORTANT": "重要", "BAD_ANSWER": "没答好", "COUNTERPARTY_INFO": "对方透露的信息",
    "PREP_NEXT": "下次要准备", "FACT_CHECK": "事实待核对", "CUSTOM": "自定义",
}
_TAG_TO_FOCUS = {"BAD_ANSWER": "USER_PIN", "PREP_NEXT": "USER_PIN", "FACT_CHECK": "FACT_BOUNDARY",
                 "IMPORTANT": "USER_PIN", "COUNTERPARTY_INFO": "CLOSING_QUESTION", "CUSTOM": "USER_PIN"}
EXCERPT_CHARS = 600


class PinError(ValueError):
    pass


def _excerpt_from_session(session_id: str, turn_id: str) -> tuple[str, str]:
    """(question, surrounding transcript) from the live session store, best effort."""
    try:
        from services.storage import intelligence as intel_storage

        rows = intel_storage._read(  # noqa: SLF001 — read-only helper reuse
            "SELECT id, seq, question_raw, question_resolved FROM interview_turn WHERE session_id = ? "
            "ORDER BY seq DESC LIMIT 4",
            (session_id,),
        )
        turns = [dict(r) for r in rows][::-1]
    except Exception as exc:  # noqa: BLE001 — surrounding transcript is best-effort
        _log.debug("turns around pin %s unavailable: %s", session_id, exc)
        return "", ""
    if not turns:
        return "", ""
    latest = turns[-1]
    question = str(latest.get("question_resolved") or latest.get("question_raw") or "")
    excerpt = "\n".join(f"面试官: {t.get('question_raw', '')}" for t in turns if t.get("question_raw"))
    return question[:400], excerpt[-EXCERPT_CHARS:]


def create_pin(
    session_id: str,
    *,
    session_kind: str = "LIVE",
    tag: str = "IMPORTANT",
    turn_id: str = "",
    question: str = "",
    transcript_excerpt: str = "",
    note: str = "",
    goal_id: Optional[str] = None,
    ts: Optional[float] = None,
) -> dict[str, Any]:
    if not session_id:
        raise PinError("没有进行中的场次")
    if tag not in TAGS:
        raise PinError(f"未知标签：{tag}")
    if session_kind not in SESSION_KINDS:
        raise PinError(f"未知场次类型：{session_kind}")
    if session_kind == "LIVE" and not (question or transcript_excerpt):
        q, ex = _excerpt_from_session(session_id, turn_id)
        question, transcript_excerpt = question or q, transcript_excerpt or ex
    now = store.now()
    pin = {"id": store.new_id("pin_"), "session_kind": session_kind, "session_id": str(session_id),
           "turn_id": str(turn_id or ""), "goal_id": goal_id, "tag": tag, "question": (question or "")[:400],
           "transcript_excerpt": (transcript_excerpt or "")[-EXCERPT_CHARS:], "note": (note or "")[:500],
           "ts": ts or now, "used_in_reflection": False, "created_at": now}
    store.insert("pin_moment", pin)
    events.record("pin_created", goal_id=goal_id or "", session_id=session_id, tag=tag, kind=session_kind)
    return pin


def update_pin(pin_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    pin = store.get("pin_moment", pin_id)
    if pin is None:
        raise PinError("标记不存在")
    clean = {k: v for k, v in patch.items() if k in ("tag", "note")}
    if "tag" in clean and clean["tag"] not in TAGS:
        raise PinError(f"未知标签：{clean['tag']}")
    if clean:
        store.update("pin_moment", pin_id, clean)
    return store.get("pin_moment", pin_id) or pin


def delete_pin(pin_id: str) -> bool:
    return store.delete("pin_moment", pin_id)


def pins_for_session(session_id: str) -> list[dict[str, Any]]:
    pins = store.select("pin_moment", "session_id = ?", (str(session_id),), "ts ASC")
    for pin in pins:
        pin["tag_label"] = TAG_LABELS.get(pin["tag"], pin["tag"])
    return pins


def mark_used_in_reflection(session_id: str) -> int:
    pins = pins_for_session(session_id)
    unused = [p for p in pins if not p["used_in_reflection"]]
    if unused:
        with store.connect() as conn:
            conn.execute("UPDATE pin_moment SET used_in_reflection = 1 WHERE session_id = ?", (str(session_id),))
        for pin in unused:
            events.record("pin_used_in_reflection", goal_id=pin.get("goal_id") or "", session_id=session_id)
    return len(unused)


def promote_to_focus(pin_id: str, goal_id: Optional[str] = None) -> dict[str, Any]:
    pin = store.get("pin_moment", pin_id)
    if pin is None:
        raise PinError("标记不存在")
    target_goal = goal_id or pin.get("goal_id")
    if not target_goal:
        raise PinError("请选择这条标记属于哪个求职目标")
    from services.product.next_focus import set_user_focus

    title = pin["question"] or pin["note"] or TAG_LABELS.get(pin["tag"], "标记的时刻")
    reason = f"你在场次中标记了这一刻（{TAG_LABELS.get(pin['tag'], pin['tag'])}）" + (f"：{pin['note']}" if pin["note"] else "。")
    focus = set_user_focus(str(target_goal), _TAG_TO_FOCUS.get(pin["tag"], "USER_PIN"), title[:60], reason,
                           source_kind="PIN", source_ref=pin_id)
    events.record("next_focus_from_pin", goal_id=str(target_goal), session_id=pin["session_id"])
    return focus
