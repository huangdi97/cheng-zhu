"""History (canonical §18): Real Interviews · Practice Sessions · Reflections.

One list over the owning stores — review_sessions (real + legacy practice)
and practice_session (Practice 3.0) — joined with goal_session_link for the
Goal. Nothing is copied: a Goal's session list and History read the same rows.
"""
from __future__ import annotations

from typing import Any, Optional

from core.logger import get_logger
from services.storage import product as store

_log = get_logger("product.history")

TYPES = ("REAL", "PRACTICE")


def _goal_titles() -> dict[str, str]:
    return {g["id"]: " · ".join(x for x in (g["company"], g["role"]) if x) for g in store.select("goal")}


def list_history(
    goal_id: str = "",
    type_: str = "",
    round_name: str = "",
    since: Optional[float] = None,
    until: Optional[float] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    links = store.select("goal_session_link")
    by_review = {int(l["review_session_id"]): l for l in links if l.get("review_session_id") is not None}
    by_practice = {l["practice_id"]: l for l in links if l.get("practice_id")}
    titles = _goal_titles()
    items: list[dict[str, Any]] = []

    practice_rows = store.select("practice_session", "status = 'DONE'", (), "started_at DESC", 500)
    practice_review_ids = {int(p["review_session_id"]) for p in practice_rows if p.get("review_session_id") is not None}
    for p in practice_rows:
        link = by_practice.get(p["id"], {})
        gid = p.get("goal_id") or link.get("goal_id") or ""
        cfg = p.get("config") or {}
        items.append({"key": f"practice:{p['id']}", "type": "PRACTICE", "guided": bool(p.get("guided")),
                      "reflection_ref": {"session_kind": "PRACTICE", "session_ref": p["id"]},
                      "review_session_id": p.get("review_session_id"), "goal_id": gid, "goal_title": titles.get(gid, ""),
                      "round": cfg.get("round", ""), "title": "练习", "panel": len(cfg.get("personas") or []) > 1,
                      "started_at": p["started_at"], "ended_at": p.get("ended_at")})

    try:
        from services.storage import review as review_storage

        page = review_storage.list_sessions(page=1, page_size=200)
        reviews = page.get("items") or page.get("sessions") or []
    except Exception as exc:  # noqa: BLE001
        _log.warning("review sessions unavailable: %s", exc)
        reviews = []
    for r in reviews:
        rid = int(r["id"])
        if rid in practice_review_ids:
            continue  # the Practice 3.0 row above is the same session
        link = by_review.get(rid, {})
        gid = link.get("goal_id") or ""
        kind = "PRACTICE" if str(r.get("source") or "") == "practice" else "REAL"
        items.append({"key": f"review:{rid}", "type": kind, "guided": False,
                      "reflection_ref": {"session_kind": "REVIEW", "session_ref": str(rid)},
                      "review_session_id": rid, "goal_id": gid, "goal_title": titles.get(gid, ""),
                      "round": link.get("round", ""), "title": r.get("title") or ("面试" if kind == "REAL" else "练习"),
                      "panel": False, "started_at": r.get("started_at"), "ended_at": r.get("ended_at"),
                      "turn_count": r.get("turn_count"), "status": r.get("status")})

    def keep(item: dict[str, Any]) -> bool:
        if goal_id and item["goal_id"] != goal_id:
            return False
        if type_ and item["type"] != type_:
            return False
        if round_name and item["round"] != round_name:
            return False
        started = float(item.get("started_at") or 0)
        if since is not None and started < since:
            return False
        if until is not None and started > until:
            return False
        return True

    filtered = [i for i in items if keep(i)]
    filtered.sort(key=lambda i: float(i.get("started_at") or 0), reverse=True)
    reflected = {(r["session_kind"], r["session_ref"]) for r in store.select("reflection_action")}
    for item in filtered:
        ref = item["reflection_ref"]
        item["has_reflection_actions"] = (ref["session_kind"], ref["session_ref"]) in reflected
    return filtered[:limit]


def link_review_to_goal(review_session_id: int, goal_id: str, kind: str = "REAL", round_name: str = "") -> dict[str, Any]:
    from services.product.goals import link_session

    return link_session(goal_id, kind, review_session_id=int(review_session_id), round_name=round_name)
