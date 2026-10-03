"""Action Home (canonical §6): what is next, what is worth doing, what blocks.

No readiness percentage, no offer probability, no ranking without a reason.
System status (model / KB / CPU) is not part of the first screen; only a
real blocker (e.g. no answer model configured) is surfaced as an attention
item with its fix.
"""
from __future__ import annotations

from typing import Any, Optional

from core.logger import get_logger
from services.storage import product as store

_log = get_logger("product.home")


def _upcoming(now: float) -> Optional[dict[str, Any]]:
    rows = store.rows(
        "SELECT gi.*, g.company, g.role, g.status AS goal_status FROM goal_interview gi JOIN goal g ON g.id = gi.goal_id "
        "WHERE gi.status = 'UPCOMING' AND gi.scheduled_at IS NOT NULL AND gi.scheduled_at >= ? AND g.status = 'ACTIVE' "
        "ORDER BY gi.scheduled_at ASC LIMIT 1", (now - 3600,))
    return rows[0] if rows else None


def _model_blocker() -> Optional[dict[str, Any]]:
    try:
        from core.config import get_config

        cfg = get_config()
        models = list(cfg.models or [])
        active = models[cfg.active_model] if 0 <= cfg.active_model < len(models) else None
        key = str(getattr(active, "api_key", "") or "") if active else ""
        if not active or not key or key.startswith("YOUR_") or key == "sk-your-api-key-here":
            return {"kind": "MODEL", "text": "回答模型还没有配置", "action": {"key": "open_settings", "target": "models",
                                                                             "label": "去配置模型"}}
    except Exception as exc:  # noqa: BLE001
        _log.debug("model check failed: %s", exc)
    return None


def summary() -> dict[str, Any]:
    from services.product import fact_inbox, goals, next_focus
    from services.product.materials import list_materials
    from services.product.workspace import story_coverage, stories_list

    now = store.now()
    active = goals.list_goals("ACTIVE")
    upcoming = _upcoming(now)
    focus_goal = None
    if upcoming:
        focus_goal = goals.get_goal(upcoming["goal_id"])
    elif active:
        focus_goal = max(active, key=lambda g: float(g.get("last_opened_at") or g.get("updated_at") or 0))

    focus_items = next_focus.active_items(focus_goal["id"]) if focus_goal else []
    if focus_goal and not focus_items:
        try:
            focus_items = next_focus.recompute(focus_goal["id"])
        except Exception as exc:  # noqa: BLE001
            _log.warning("next focus recompute on home failed: %s", exc)

    attention: list[dict[str, Any]] = []
    blocker = _model_blocker()
    if blocker:
        attention.append(blocker)
    try:
        inbox = fact_inbox.inbox(limit=50)
        if inbox["count"]:
            attention.append({"kind": "FACT_INBOX", "count": inbox["count"], "text": f"{inbox['count']} 个事实待确认",
                              "action": {"key": "open_fact_inbox", "label": "去确认"}})
    except Exception as exc:  # noqa: BLE001
        _log.debug("fact inbox unavailable: %s", exc)
    try:
        missing = story_coverage(stories_list())["missing"]
        core_missing = [m for m in missing if m["key"] in ("Ownership", "Failure", "Conflict", "Difficult Problem")]
        if core_missing:
            attention.append({"kind": "STORY_GAP", "count": len(core_missing), "text": f"{len(core_missing)} 个 Story 缺口",
                              "action": {"key": "open_stories", "label": "补 Story"}})
    except Exception as exc:  # noqa: BLE001
        _log.debug("story coverage unavailable: %s", exc)
    failed = [m for m in list_materials() if m["lifecycle"]["state"] == "FAILED"]
    if failed:
        attention.append({"kind": "MATERIAL_FAILED", "count": len(failed), "text": f"{len(failed)} 份资料处理失败",
                          "action": {"key": "open_library", "label": "查看原因"}})
    if focus_goal and not str(focus_goal.get("jd") or "").strip():
        attention.append({"kind": "GOAL_NO_JD", "text": f"{focus_goal['title']} 还没有 JD",
                          "action": {"key": "open_goal", "goal_id": focus_goal["id"], "label": "补充 JD"}})

    recent = _recent_session()
    if not active:
        state = "NO_GOAL"
        primary = {"key": "create_goal", "label": "创建第一个求职目标"}
    elif recent is None:
        state = "GOAL_NO_SESSION"
        primary = {"key": "continue_prepare", "goal_id": focus_goal["id"], "label": "继续准备"}
    else:
        state = "ACTIVE"
        primary = {"key": "continue_prepare", "goal_id": focus_goal["id"], "label": "继续准备"}

    next_interview = None
    if upcoming:
        next_interview = {"goal_id": upcoming["goal_id"], "interview_id": upcoming["id"],
                          "title": " · ".join(x for x in (upcoming["company"], upcoming["round"]) if x),
                          "company": upcoming["company"], "role": upcoming["role"], "round": upcoming["round"],
                          "scheduled_at": upcoming["scheduled_at"],
                          "actions": [{"key": "continue_prepare", "label": "继续准备"},
                                      {"key": "start_practice", "label": "开始练习"},
                                      {"key": "preflight", "label": "Preflight"}]}
    return {
        "state": state,
        "primary_action": primary,
        "next_interview": next_interview,
        "focus_goal": {"id": focus_goal["id"], "title": focus_goal["title"]} if focus_goal else None,
        "next_focus": focus_items[:3],
        "needs_attention": attention,
        "recent_session": recent,
        "active_goal_count": len(active),
    }


def _recent_session() -> Optional[dict[str, Any]]:
    from services.product.history import list_history

    items = list_history(limit=1)
    return items[0] if items else None
