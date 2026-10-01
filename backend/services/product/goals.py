"""Goal — the long-lived job target the whole v1.3 product is organised around.

A Goal is not a UI alias of a prep space: it owns status, rounds, offer,
selections and Next Focus. For compatibility it keeps a link to the legacy
prep space (which still owns skill cards / generated questions) and to a
job-tracker application, so v1.2 data keeps working unchanged.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from core.logger import get_logger
from services.product import events
from services.storage import product as store

_log = get_logger("product.goals")

GOAL_STATUSES = ("ACTIVE", "PAUSED", "COMPLETED", "ARCHIVED")
OFFER_STATES = ("NONE", "PENDING", "RECEIVED", "NEGOTIATING", "ACCEPTED", "DECLINED")
INTERVIEW_KINDS = ("REAL", "MOCK")
INTERVIEW_STATUSES = ("UPCOMING", "DONE", "CANCELLED")
SESSION_KINDS = ("REAL", "PRACTICE", "MOCK", "GUIDED")
ROLE_FAMILIES = ("SWE", "AI_ML", "AI_PM", "DATA_ML", "PRODUCT")

_REOPEN_GAP_SECONDS = 3600.0

_EDITABLE = (
    "company", "role", "jd", "status", "stage", "next_interview_at", "interview_round", "goal_notes",
    "selected_resume_id", "selected_material_ids", "selected_kb_ids", "selected_quick_note_ids",
    "active_question_bank_ids", "offer_state", "role_family", "settings",
)


class GoalError(ValueError):
    pass


def infer_role_family(role: str, jd: str = "") -> str:
    text = f"{role} {jd[:400]}".lower()
    if re.search(r"(产品|product|pm\b)", text):
        if re.search(r"(ai|大模型|llm|agent|算法|ml)", text):
            return "AI_PM"
        return "PRODUCT"
    if re.search(r"(数据|data|分析|analyst|scientist)", text):
        return "DATA_ML"
    if re.search(r"(ai|算法|机器学习|ml\b|llm|大模型|agent|aidd|nlp|cv|深度学习)", text):
        return "AI_ML"
    return "SWE"


def _title(goal: dict[str, Any]) -> str:
    parts = [p for p in (goal.get("company"), goal.get("role")) if p]
    return " · ".join(parts) or "未命名目标"


def _decorate(goal: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if goal is None:
        return None
    goal["title"] = _title(goal)
    for key in ("selected_material_ids", "selected_kb_ids", "selected_quick_note_ids", "active_question_bank_ids"):
        if not isinstance(goal.get(key), list):
            goal[key] = []
    if not isinstance(goal.get("settings"), dict):
        goal["settings"] = {}
    return goal


def _validate(patch: dict[str, Any]) -> None:
    if "status" in patch and patch["status"] not in GOAL_STATUSES:
        raise GoalError(f"未知状态：{patch['status']}")
    if "offer_state" in patch and patch["offer_state"] not in OFFER_STATES:
        raise GoalError(f"未知 Offer 状态：{patch['offer_state']}")
    if "role_family" in patch and patch["role_family"] and patch["role_family"] not in ROLE_FAMILIES:
        raise GoalError(f"未知岗位族：{patch['role_family']}")


def create_goal(
    company: str = "",
    role: str = "",
    jd: str = "",
    *,
    stage: str = "",
    next_interview_at: Optional[float] = None,
    interview_round: str = "",
    goal_notes: str = "",
    selected_resume_id: Optional[int] = None,
    legacy_prep_space_id: Optional[int] = None,
    application_id: Optional[int] = None,
    create_prep_space: bool = True,
) -> dict[str, Any]:
    company, role = (company or "").strip(), (role or "").strip()
    if not company and not role:
        raise GoalError("请至少填写公司或岗位")
    if create_prep_space and legacy_prep_space_id is None:
        legacy_prep_space_id = _create_prep_space(company, role, jd)
    now = store.now()
    goal = {
        "id": store.new_id("g_"),
        "company": company,
        "role": role,
        "jd": jd or "",
        "status": "ACTIVE",
        "stage": stage,
        "next_interview_at": next_interview_at,
        "interview_round": interview_round,
        "goal_notes": goal_notes,
        "selected_resume_id": selected_resume_id,
        "selected_material_ids": [],
        "selected_kb_ids": [],
        "selected_quick_note_ids": [],
        "active_question_bank_ids": [],
        "offer_state": "NONE",
        "role_family": infer_role_family(role, jd),
        "legacy_prep_space_id": legacy_prep_space_id,
        "application_id": application_id,
        "settings": {},
        "created_at": now,
        "updated_at": now,
    }
    store.insert("goal", goal)
    if next_interview_at:
        add_interview(goal["id"], round_name=interview_round, scheduled_at=next_interview_at)
    events.record("goal_created", goal_id=goal["id"], has_jd=bool(jd), has_schedule=bool(next_interview_at))
    return get_goal(goal["id"]) or goal


def _create_prep_space(company: str, role: str, jd: str) -> Optional[int]:
    try:
        from services.storage import prep_space

        title = " · ".join(p for p in (company, role) if p) or "未命名目标"
        return prep_space.create_space(title=title, role=role, company=company, jd_text=jd)
    except Exception as exc:  # noqa: BLE001 — a Goal must not fail because legacy prep is unavailable
        _log.warning("prep space for goal not created: %s", exc)
        return None


def get_goal(goal_id: str) -> Optional[dict[str, Any]]:
    return _decorate(store.get("goal", goal_id))


def require_goal(goal_id: str) -> dict[str, Any]:
    goal = get_goal(goal_id)
    if goal is None:
        raise GoalError("求职目标不存在")
    return goal


def list_goals(status: str = "") -> list[dict[str, Any]]:
    if status:
        rows = store.select("goal", "status = ?", (status,), "updated_at DESC")
    else:
        rows = store.select("goal", "", (), "CASE status WHEN 'ACTIVE' THEN 0 WHEN 'PAUSED' THEN 1 ELSE 2 END, "
                            "COALESCE(next_interview_at, 9e18) ASC, updated_at DESC")
    return [g for g in (_decorate(r) for r in rows) if g]


def update_goal(goal_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    require_goal(goal_id)
    clean = {k: v for k, v in patch.items() if k in _EDITABLE}
    _validate(clean)
    if "role" in clean and "role_family" not in clean:
        current = require_goal(goal_id)
        clean["role_family"] = infer_role_family(clean["role"], clean.get("jd", current.get("jd", "")))
    clean["updated_at"] = store.now()
    store.update("goal", goal_id, clean)
    _sync_prep_space(goal_id, clean)
    return require_goal(goal_id)


def _sync_prep_space(goal_id: str, patch: dict[str, Any]) -> None:
    if not any(k in patch for k in ("company", "role", "jd")):
        return
    goal = get_goal(goal_id)
    space_id = goal.get("legacy_prep_space_id") if goal else None
    if not space_id:
        return
    try:
        from services.storage import prep_space

        with prep_space._db_lock:  # noqa: SLF001 — prep_space has no generic update helper
            conn = prep_space._conn()  # noqa: SLF001
            conn.execute(
                "UPDATE prep_spaces SET title = ?, company = ?, role = ?, jd_text = ?, updated_at = ? WHERE id = ?",
                (goal["title"], goal["company"], goal["role"], goal["jd"], store.now(), int(space_id)),
            )
            conn.commit()
            conn.close()
    except Exception as exc:  # noqa: BLE001
        _log.warning("prep space sync failed for goal %s: %s", goal_id, exc)


def delete_goal(goal_id: str) -> dict[str, Any]:
    """Delete a Goal and everything it owns; detach what it only referenced.

    Owned (cascade): interviews, offer, session links, Next Focus, goal-scoped
    quick notes, goal materials links. Referenced (detached, kept): pins,
    practice sessions, reflection actions, review sessions (their own store).
    """
    goal = require_goal(goal_id)
    with store.connect() as conn:
        notes = conn.execute("DELETE FROM quick_note WHERE scope = 'GOAL' AND goal_id = ?", (goal_id,)).rowcount
        for table in ("pin_moment", "practice_session", "reflection_action", "rubric_observation",
                      "delivery_metrics", "question_bank"):
            conn.execute(f"UPDATE {table} SET goal_id = NULL WHERE goal_id = ?", (goal_id,))
        conn.execute("DELETE FROM setting_override WHERE scope = 'GOAL' AND scope_id = ?", (goal_id,))
        conn.execute("DELETE FROM goal WHERE id = ?", (goal_id,))
    return {"deleted": True, "goal_id": goal_id, "quick_notes_deleted": notes,
            "legacy_prep_space_id": goal.get("legacy_prep_space_id")}


def open_goal(goal_id: str) -> dict[str, Any]:
    goal = require_goal(goal_id)
    now = store.now()
    last = goal.get("last_opened_at")
    store.update("goal", goal_id, {"last_opened_at": now})
    events.record("goal_opened", goal_id=goal_id)
    if last and now - float(last) >= _REOPEN_GAP_SECONDS:
        events.record("goal_reopened", goal_id=goal_id, gap_s=int(now - float(last)))
    goal["last_opened_at"] = now
    return goal


# ---------------------------------------------------------------------------
# Interviews / offer / session links
# ---------------------------------------------------------------------------


def add_interview(
    goal_id: str,
    round_name: str = "",
    scheduled_at: Optional[float] = None,
    kind: str = "REAL",
    notes: str = "",
) -> dict[str, Any]:
    require_goal(goal_id)
    if kind not in INTERVIEW_KINDS:
        raise GoalError(f"未知面试类型：{kind}")
    now = store.now()
    row = {"id": store.new_id("gi_"), "goal_id": goal_id, "round": round_name, "kind": kind,
           "status": "UPCOMING", "scheduled_at": scheduled_at, "notes": notes,
           "created_at": now, "updated_at": now}
    store.insert("goal_interview", row)
    _refresh_next_interview(goal_id)
    return row


def update_interview(interview_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    row = store.get("goal_interview", interview_id)
    if row is None:
        raise GoalError("面试轮次不存在")
    clean = {k: v for k, v in patch.items() if k in ("round", "kind", "status", "scheduled_at", "notes")}
    if "status" in clean and clean["status"] not in INTERVIEW_STATUSES:
        raise GoalError(f"未知面试状态：{clean['status']}")
    clean["updated_at"] = store.now()
    store.update("goal_interview", interview_id, clean)
    _refresh_next_interview(row["goal_id"])
    return store.get("goal_interview", interview_id) or row


def delete_interview(interview_id: str) -> bool:
    row = store.get("goal_interview", interview_id)
    if row is None:
        return False
    store.delete("goal_interview", interview_id)
    _refresh_next_interview(row["goal_id"])
    return True


def list_interviews(goal_id: str) -> list[dict[str, Any]]:
    return store.select("goal_interview", "goal_id = ?", (goal_id,), "COALESCE(scheduled_at, 9e18) ASC")


def _refresh_next_interview(goal_id: str) -> None:
    upcoming = store.select(
        "goal_interview", "goal_id = ? AND status = 'UPCOMING' AND scheduled_at IS NOT NULL",
        (goal_id,), "scheduled_at ASC", 1,
    )
    patch: dict[str, Any] = {"updated_at": store.now()}
    if upcoming:
        patch["next_interview_at"] = upcoming[0]["scheduled_at"]
        patch["interview_round"] = upcoming[0]["round"]
    else:
        patch["next_interview_at"] = None
    store.update("goal", goal_id, patch)


def get_offer(goal_id: str) -> dict[str, Any]:
    require_goal(goal_id)
    return store.get("goal_offer", goal_id, key="goal_id") or {
        "goal_id": goal_id, "status": "NONE", "comp": "", "deadline": None, "notes": "", "updated_at": None,
    }


def set_offer(goal_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    require_goal(goal_id)
    clean = {k: v for k, v in patch.items() if k in ("status", "comp", "deadline", "notes")}
    if "status" in clean and clean["status"] not in OFFER_STATES:
        raise GoalError(f"未知 Offer 状态：{clean['status']}")
    clean["updated_at"] = store.now()
    if store.get("goal_offer", goal_id, key="goal_id") is None:
        store.insert("goal_offer", {"goal_id": goal_id, **clean})
    else:
        store.update("goal_offer", goal_id, clean, key="goal_id")
    if "status" in clean:
        store.update("goal", goal_id, {"offer_state": clean["status"], "updated_at": store.now()})
    return get_offer(goal_id)


def link_session(
    goal_id: str,
    session_kind: str,
    *,
    review_session_id: Optional[int] = None,
    practice_id: str = "",
    live_session_id: str = "",
    goal_interview_id: str = "",
    round_name: str = "",
) -> dict[str, Any]:
    require_goal(goal_id)
    if session_kind not in SESSION_KINDS:
        raise GoalError(f"未知场次类型：{session_kind}")
    existing = None
    if review_session_id is not None:
        found = store.select("goal_session_link", "review_session_id = ?", (int(review_session_id),), limit=1)
        existing = found[0] if found else None
    elif practice_id:
        found = store.select("goal_session_link", "practice_id = ?", (practice_id,), limit=1)
        existing = found[0] if found else None
    if existing:
        patch = {"goal_id": goal_id, "practice_id": practice_id or existing["practice_id"],
                 "review_session_id": review_session_id if review_session_id is not None else existing["review_session_id"]}
        store.update("goal_session_link", existing["id"], patch)
        return {**existing, **patch}
    row = {"id": store.new_id("gs_"), "goal_id": goal_id, "session_kind": session_kind,
           "review_session_id": review_session_id, "practice_id": practice_id,
           "live_session_id": live_session_id, "goal_interview_id": goal_interview_id,
           "round": round_name, "created_at": store.now()}
    store.insert("goal_session_link", row)
    if goal_interview_id and session_kind == "REAL":
        try:
            update_interview(goal_interview_id, {"status": "DONE"})
        except GoalError:
            pass
    store.update("goal", goal_id, {"updated_at": store.now()})
    return row


def attach_review_to_practice(practice_id: str, review_session_id: int) -> None:
    found = store.select("goal_session_link", "practice_id = ?", (practice_id,), limit=1)
    if found:
        store.update("goal_session_link", found[0]["id"], {"review_session_id": int(review_session_id)})


def goal_for_review_session(review_session_id: int) -> Optional[str]:
    found = store.select("goal_session_link", "review_session_id = ?", (int(review_session_id),), limit=1)
    return found[0]["goal_id"] if found else None


def goal_for_prep_space(space_id: int) -> Optional[dict[str, Any]]:
    found = store.select("goal", "legacy_prep_space_id = ?", (int(space_id),), limit=1)
    return _decorate(found[0]) if found else None


def session_links(goal_id: str = "") -> list[dict[str, Any]]:
    if goal_id:
        return store.select("goal_session_link", "goal_id = ?", (goal_id,), "created_at DESC")
    return store.select("goal_session_link", "", (), "created_at DESC")


# ---------------------------------------------------------------------------
# v1.2 → v1.3 data upgrade
# ---------------------------------------------------------------------------

_BACKFILL_KEY = "legacy_backfill_v1"


def backfill_from_legacy(force: bool = False) -> dict[str, int]:
    """Create one Goal per legacy prep space (idempotent, non-destructive).

    Matching job-tracker applications (same company + position) are linked;
    review sessions already linked to that application are linked to the Goal.
    """
    if not force and store.meta_get(_BACKFILL_KEY) == "done":
        return {"goals_created": 0, "sessions_linked": 0, "skipped": 1}
    created = linked = 0
    try:
        from services.storage import prep_space

        spaces = prep_space.list_spaces()
    except Exception as exc:  # noqa: BLE001
        _log.warning("legacy prep spaces unreadable, backfill skipped: %s", exc)
        spaces = []
    applications = _legacy_applications()
    for space in spaces:
        if goal_for_prep_space(int(space["id"])) is not None:
            continue
        full = _legacy_space(int(space["id"])) or space
        company = str(full.get("company") or "").strip()
        role = str(full.get("role") or "").strip() or str(full.get("title") or "").strip()
        app = _match_application(applications, company, role)
        goal = create_goal(
            company or str(full.get("title") or ""), role, str(full.get("jd_text") or ""),
            legacy_prep_space_id=int(space["id"]),
            application_id=int(app["id"]) if app else None,
            stage=str(app.get("stage") or "") if app else "",
            create_prep_space=False,
        )
        store.update("goal", goal["id"], {"created_at": float(full.get("created_at") or store.now())})
        created += 1
        if app:
            linked += _link_application_reviews(goal["id"], int(app["id"]))
    store.meta_set(_BACKFILL_KEY, "done")
    _log.info("legacy backfill: goals_created=%d sessions_linked=%d", created, linked)
    return {"goals_created": created, "sessions_linked": linked, "skipped": 0}


def _legacy_space(space_id: int) -> Optional[dict[str, Any]]:
    try:
        from services.storage import prep_space

        return prep_space.get_space(space_id)
    except Exception:  # noqa: BLE001
        return None


def _legacy_applications() -> list[dict[str, Any]]:
    try:
        from services.storage import job_tracker

        result = job_tracker.list_applications()
        return list(result.get("items", result) if isinstance(result, dict) else result)
    except Exception as exc:  # noqa: BLE001
        _log.warning("legacy applications unreadable: %s", exc)
        return []


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


def _match_application(apps: list[dict[str, Any]], company: str, role: str) -> Optional[dict[str, Any]]:
    if not company:
        return None
    for app in apps:
        if _norm(app.get("company", "")) == _norm(company) and (
            not role or _norm(app.get("position", "")) == _norm(role)
        ):
            return app
    return None


def _link_application_reviews(goal_id: str, application_id: int) -> int:
    try:
        from services.storage import review

        rows = review.list_reviews_for_application(application_id)
    except Exception as exc:  # noqa: BLE001
        _log.warning("legacy reviews unreadable for application %s: %s", application_id, exc)
        return 0
    count = 0
    for row in rows:
        sid = row.get("id") or row.get("session_id")
        if sid is None:
            continue
        kind = "PRACTICE" if str(row.get("source") or "") == "practice" else "REAL"
        link_session(goal_id, kind, review_session_id=int(sid))
        count += 1
    return count
