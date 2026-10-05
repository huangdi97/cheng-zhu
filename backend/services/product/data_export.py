"""Data & Export (canonical v1.4 §Data): export and user-initiated deletion.

Exports are written to the exports directory as JSON and returned. Deletes
remove the owned rows and then run ``integrity`` so no Goal points at a
deleted note / material / bank, no link points at a deleted session and no
reflection action keeps a dangling goal.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

from core.logger import get_logger
from services.storage import product as store
from services.storage.paths import exports_dir

_log = get_logger("product.export")

KINDS = ("person", "goal", "session", "reflection", "quick_notes", "question_banks")


class ExportError(ValueError):
    pass


def _write(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    name = f"chengzhu-{kind}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    path = os.path.join(exports_dir(), name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
    return {"kind": kind, "path": path, "filename": name, "data": payload}


def export_person() -> dict[str, Any]:
    from services.storage import intelligence as intel

    cid = intel.active_candidate_id()
    return _write("person", {
        "exported_at": time.time(), "candidate_id": cid,
        "profile": intel.get_candidate_profile(cid) if cid else None,
        "claims": intel.list_claims(cid, limit=5000) if cid else [],
        "evidence": intel.list_evidence(cid, limit=5000) if cid else [],
        "stories": intel.list_all_stories(limit=1000),
    })


def export_goal(goal_id: str) -> dict[str, Any]:
    from services.product import goals, next_focus, quick_notes

    goal = goals.require_goal(goal_id)
    return _write("goal", {
        "exported_at": time.time(), "goal": goal, "interviews": goals.list_interviews(goal_id),
        "offer": goals.get_offer(goal_id), "next_focus": next_focus.active_items(goal_id),
        "quick_notes": quick_notes.list_notes(goal_id, include_global=False),
        "sessions": goals.session_links(goal_id),
        "reflection_actions": store.select("reflection_action", "goal_id = ?", (goal_id,)),
    })


def export_session(session_kind: str, session_ref: str) -> dict[str, Any]:
    if session_kind == "PRACTICE":
        from services.product.practice import get

        data = get(session_ref)
    elif session_kind == "REVIEW":
        from services.storage import review

        data = review.get_session_detail(int(session_ref))
        if data is None:
            raise ExportError("场次不存在")
    else:
        raise ExportError("未知场次类型")
    data = {**data, "pins": store.select("pin_moment", "session_id = ?", (str(session_ref),))}
    return _write("session", {"exported_at": time.time(), "session_kind": session_kind, "session": data})


def export_reflection(session_kind: str, session_ref: str) -> dict[str, Any]:
    from services.product.reflection import build

    return _write("reflection", {"exported_at": time.time(), "reflection": build(session_kind, session_ref),
                                 "actions": store.select("reflection_action", "session_ref = ?", (str(session_ref),))})


def export_quick_notes() -> dict[str, Any]:
    return _write("quick_notes", {"exported_at": time.time(), "quick_notes": store.select("quick_note")})


def export_question_banks() -> dict[str, Any]:
    from services.product.question_banks import list_banks, list_items

    banks = [b for b in list_banks() if not b["builtin"]]
    return _write("question_banks", {"exported_at": time.time(),
                                     "banks": [{**b, "items": list_items(b["id"])} for b in banks]})


# ---------------------------------------------------------------------------
# Deletes + integrity
# ---------------------------------------------------------------------------


def delete_session(session_kind: str, session_ref: str) -> dict[str, Any]:
    removed: dict[str, Any] = {}
    if session_kind == "PRACTICE":
        row = store.get("practice_session", session_ref)
        if row is None:
            raise ExportError("练习不存在")
        review_id = row.get("review_session_id")
        with store.connect() as conn:
            conn.execute("DELETE FROM practice_turn WHERE practice_id = ?", (session_ref,))
            conn.execute("DELETE FROM practice_session WHERE id = ?", (session_ref,))
            conn.execute("DELETE FROM goal_session_link WHERE practice_id = ?", (session_ref,))
            conn.execute("DELETE FROM rubric_observation WHERE session_ref = ?", (session_ref,))
            conn.execute("DELETE FROM delivery_metrics WHERE session_ref = ?", (session_ref,))
            conn.execute("DELETE FROM pin_moment WHERE session_id = ?", (session_ref,))
        removed["practice"] = session_ref
        if review_id is not None:
            removed.update(_delete_review(int(review_id)))
    elif session_kind == "REVIEW":
        removed.update(_delete_review(int(session_ref)))
    else:
        raise ExportError("未知场次类型")
    removed["integrity"] = integrity(repair=True)
    return removed


def _delete_review(review_id: int) -> dict[str, Any]:
    from services.storage import review

    links = store.select("goal_session_link", "review_session_id = ?", (review_id,))
    with store.connect() as conn:
        for link in links:
            if link.get("live_session_id"):
                conn.execute("DELETE FROM pin_moment WHERE session_id = ?", (link["live_session_id"],))
                conn.execute("DELETE FROM nudge_event WHERE session_id = ?", (link["live_session_id"],))
                conn.execute("DELETE FROM closing_mode_event WHERE session_id = ?", (link["live_session_id"],))
        conn.execute("DELETE FROM goal_session_link WHERE review_session_id = ?", (review_id,))
        conn.execute("DELETE FROM rubric_observation WHERE session_ref = ?", (f"review:{review_id}",))
        conn.execute("DELETE FROM pin_moment WHERE session_id = ?", (str(review_id),))
    return {"review_session": review_id, "review_deleted": review.delete_session(review_id)}


def integrity(repair: bool = False) -> dict[str, Any]:
    """Find (and optionally clear) dangling references across product.db."""
    issues: list[dict[str, Any]] = []
    notes = {r["id"] for r in store.select("quick_note")}
    mats = {r["id"] for r in store.select("material")}
    banks = {r["id"] for r in store.select("question_bank")}
    goals = store.select("goal")
    goal_ids = {g["id"] for g in goals}
    for g in goals:
        for field, valid in (("selected_quick_note_ids", notes), ("selected_material_ids", mats),
                             ("active_question_bank_ids", banks)):
            bad = [i for i in (g.get(field) or []) if i not in valid]
            if bad:
                issues.append({"kind": "GOAL_DANGLING_REF", "goal_id": g["id"], "field": field, "ids": bad})
                if repair:
                    store.update("goal", g["id"], {field: [i for i in g.get(field) or [] if i in valid]})
    review_ids = _review_ids()
    for link in store.select("goal_session_link"):
        rid = link.get("review_session_id")
        if rid is not None and review_ids is not None and int(rid) not in review_ids:
            issues.append({"kind": "LINK_TO_MISSING_REVIEW", "link_id": link["id"], "review_session_id": rid})
            if repair:
                store.update("goal_session_link", link["id"], {"review_session_id": None})
    for row in store.select("reflection_action"):
        if row.get("goal_id") and row["goal_id"] not in goal_ids:
            issues.append({"kind": "REFLECTION_ACTION_MISSING_GOAL", "id": row["id"]})
            if repair:
                store.update("reflection_action", row["id"], {"goal_id": None})
    for row in store.select("practice_session"):
        if row.get("goal_id") and row["goal_id"] not in goal_ids:
            issues.append({"kind": "PRACTICE_MISSING_GOAL", "id": row["id"]})
            if repair:
                store.update("practice_session", row["id"], {"goal_id": None})
    return {"ok": not issues, "issues": issues, "repaired": repair and bool(issues)}


def _review_ids() -> Optional[set[int]]:
    try:
        from services.storage import review

        with review._db_lock:  # noqa: SLF001 — read-only id scan
            conn = review._conn()  # noqa: SLF001
            ids = {int(r[0]) for r in conn.execute("SELECT id FROM review_sessions").fetchall()}
            conn.close()
        return ids
    except Exception as exc:  # noqa: BLE001
        _log.debug("review ids unavailable: %s", exc)
        return None
