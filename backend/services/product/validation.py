"""v1.4 Product-Market Validation — six loop questions over local data.

  A Goal reuse · B Reflection → Prepare · C Fast Cue usefulness ·
  D Practice → Session transfer · E Fact Inbox burden · F Quick Notes / Pin value

Everything is computed from the local product_event store and product.db
rows. The report never claims market proof: ``evidence_level`` says whether
the numbers come from no data, synthetic/dogfood runs or this device's own
usage, and real-user validation stays REAL_USER_VALIDATION_PENDING until
real participants exist.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Optional

from services.product import events
from services.storage import product as store

SYNTHETIC_MARKER = "dogfood_synthetic"


def _events(name: str) -> list[dict[str, Any]]:
    return events.list_events(name=name, limit=100000)


def _median(values: list[float]) -> Optional[float]:
    return round(statistics.median(values), 1) if values else None


def goal_reuse() -> dict[str, Any]:
    goals = store.select("goal")
    created = len(goals)
    reopened_ids = {e["goal_id"] for e in _events("goal_reopened")}
    opens: dict[str, list[float]] = defaultdict(list)
    for e in _events("goal_opened"):
        opens[e["goal_id"]].append(float(e["ts"]))
    intervals = []
    for ts in opens.values():
        ts.sort()
        intervals += [b - a for a, b in zip(ts, ts[1:]) if b - a >= 3600]
    links = store.select("goal_session_link")
    per_goal: dict[str, int] = defaultdict(int)
    for link in links:
        per_goal[link["goal_id"]] += 1
    lifespans = []
    for g in goals:
        last = max([float(g["updated_at"] or 0), *opens.get(g["id"], [0.0])])
        lifespans.append(max(0.0, last - float(g["created_at"])))
    focus = store.select("next_focus")
    acted = [f for f in focus if f["status"] == "DONE"]
    practice_with_focus = sum(1 for p in store.select("practice_session") if (p.get("config") or {}).get("focus"))
    return {
        "goals": created,
        "goal_reopen_rate": round(len(reopened_ids) / created, 3) if created else None,
        "sessions_per_goal": round(sum(per_goal.values()) / created, 2) if created else None,
        "median_goal_lifespan_days": _median([l / 86400 for l in lifespans]),
        "median_return_interval_hours": _median([i / 3600 for i in intervals]),
        "next_focus_items": len(focus),
        "next_focus_action_rate": round((len(acted) + practice_with_focus) / len(focus), 3) if focus else None,
    }


def reflection_loop() -> dict[str, Any]:
    actions = store.select("reflection_action")
    writeback = [a for a in actions if a["action"] in ("SET_NEXT_FOCUS", "PRACTICE_THIS")]
    reflection_focus = store.select("next_focus", "source_kind IN ('REFLECTION', 'PIN')")
    practices = store.select("practice_session")
    followed = 0
    for f in reflection_focus:
        if any((p.get("config") or {}).get("focus", {}) and (p["config"]["focus"] or {}).get("id") == f["id"]
               for p in practices):
            followed += 1
    return {
        "reflections_opened": len(_events("reflection_opened")),
        "reflection_actions": len(actions),
        "writeback_actions": len(writeback),
        "next_focus_from_reflection": len(reflection_focus),
        "practices_started_on_reflection_focus": followed,
        "follow_through_rate": round(followed / len(reflection_focus), 3) if reflection_focus else None,
        "by_action": _count(a["action"] for a in actions),
    }


def cue_usefulness() -> dict[str, Any]:
    c = events.counts()
    rendered = c.get("fast_cue_rendered", 0)
    feedback = store.select("session_feedback", "question = 'fast_cue_helpful'")
    dist = _count(f["answer"] for f in feedback)
    latency = None
    try:
        from services.intelligence import latency_clock

        summary = latency_clock.summary() if hasattr(latency_clock, "summary") else None
        latency = summary
    except Exception:  # noqa: BLE001
        latency = None

    def rate(name: str) -> Optional[float]:
        return round(c.get(name, 0) / rendered, 3) if rendered else None

    return {
        "rendered": rendered,
        "usefulness": {"session_feedback": dist, "helpful_marks": c.get("fast_cue_helpful", 0),
                       "speech_after_cue_rate": rate("speech_after_cue")},
        "accuracy": {"regenerate_rate": rate("fast_cue_regenerated"), "dismiss_rate": rate("fast_cue_dismissed")},
        "personal_fact_safety": {"fact_checks_from_pins": c.get("fact_check_from_pin", 0)},
        "latency": latency,
        "readability": {"expand_rate": rate("fast_cue_expanded"), "deep_open_rate": rate("deep_opened")},
        "over_specificity": {"dismissed": c.get("fast_cue_dismissed", 0)},
        "note": "分维度代理信号，不合成单一分数；Live 持续语音分析默认关闭。",
    }


def practice_transfer(goal_id: str = "") -> dict[str, Any]:
    """Weakness → Next Focus → later session, same rubric dimension, before/after."""
    from services.product.next_focus import _DIMENSION_TYPE  # noqa: PLC2701 — shared mapping

    type_dims: dict[str, list[str]] = defaultdict(list)
    for dim, type_ in _DIMENSION_TYPE.items():
        type_dims[type_].append(dim)
    where, params = ("goal_id = ?", (goal_id,)) if goal_id else ("", ())
    focus_rows = store.select("next_focus", where, params, "created_at ASC")
    obs = store.select("rubric_observation", where, params, "created_at ASC")
    links: list[dict[str, Any]] = []
    for f in focus_rows:
        dims = [f["source_ref"]] if f["source_ref"] in type_dims.get(f["type"], []) or f["source_kind"] == "PRACTICE" \
            else type_dims.get(f["type"], [])
        dims = [d for d in dims if d]
        if not dims:
            continue
        before = [o for o in obs if o["goal_id"] == f["goal_id"] and o["dimension"] in dims and o["created_at"] < f["created_at"]]
        after = [o for o in obs if o["goal_id"] == f["goal_id"] and o["dimension"] in dims and o["created_at"] >= f["created_at"]]
        if not before or not after:
            continue
        later_kinds = {o["session_kind"] for o in after}
        links.append({
            "next_focus_id": f["id"], "goal_id": f["goal_id"], "dimensions": dims, "type": f["type"],
            "before_level": round(sum(o["level"] for o in before) / len(before), 2),
            "after_level": round(sum(o["level"] for o in after) / len(after), 2),
            "after_sessions": len({o["session_ref"] for o in after}),
            "evidence_type": "REAL_INTERVIEW_TRANSFER" if "REAL" in later_kinds else "MOCK_TO_MOCK",
        })
    improved = [l for l in links if l["after_level"] - l["before_level"] >= 0.5]
    return {"links": links, "improved": len(improved), "measured": len(links),
            "note": "MOCK_TO_MOCK 只是工程证据，不代表真实面试中的迁移。"}


def fact_inbox_burden() -> dict[str, Any]:
    from services.product.fact_inbox import metrics

    m = metrics()
    created_events = _events("fact_inbox_created")
    by_day: dict[str, int] = defaultdict(int)
    import time as _time

    for e in created_events:
        by_day[_time.strftime("%Y-%m-%d", _time.localtime(float(e["ts"])))] += 1
    m["items_generated_per_import_day"] = _median([float(v) for v in by_day.values()])
    return m


def notes_and_pins() -> dict[str, Any]:
    c = events.counts()
    notes = store.select("quick_note")
    pins_rows = store.select("pin_moment")
    sessions_with_pins = {p["session_id"] for p in pins_rows}
    used_in_pack_by_goal = _count(e["goal_id"] for e in _events("quick_note_used_in_pack"))
    return {
        "quick_notes": {
            "created": c.get("quick_note_created", 0), "existing": len(notes),
            "selected_into_pack": c.get("quick_note_used_in_pack", 0),
            "opened_in_live": c.get("quick_note_opened_in_live", 0),
            "used_repeatedly_goals": sum(1 for v in used_in_pack_by_goal.values() if v >= 2),
            "converted_from_reflection": c.get("quick_note_from_reflection", 0),
        },
        "pins": {
            "created": c.get("pin_created", 0),
            "pins_per_session": round(len(pins_rows) / len(sessions_with_pins), 2) if sessions_with_pins else None,
            "used_in_reflection": c.get("pin_used_in_reflection", 0),
            "next_focus_from_pin": c.get("next_focus_from_pin", 0),
            "story_from_pin": c.get("story_from_pin", 0),
            "fact_check_from_pin": c.get("fact_check_from_pin", 0),
        },
    }


def nudge_metrics() -> dict[str, Any]:
    c = events.counts()
    return {k: c.get(f"nudge_{k}", 0) for k in ("shown", "dismissed", "actioned", "disabled")}


def evidence_level() -> str:
    if store.meta_get(SYNTHETIC_MARKER) == "1":
        return "SYNTHETIC_DOGFOOD"
    if not store.select("product_event", limit=1):
        return "NO_DATA"
    return "LOCAL_DEVICE_USAGE"


def report() -> dict[str, Any]:
    return {
        "evidence_level": evidence_level(),
        "real_user_validation": "REAL_USER_VALIDATION_PENDING",
        "A_goal_reuse": goal_reuse(),
        "B_reflection_to_prepare": reflection_loop(),
        "C_fast_cue_usefulness": cue_usefulness(),
        "D_practice_transfer": practice_transfer(),
        "E_fact_inbox_burden": fact_inbox_burden(),
        "F_quick_notes_and_pins": notes_and_pins(),
        "nudges": nudge_metrics(),
        "note": "本地产品分析，只在本机；远程遥测需用户主动开启。自动化测试或合成数据不能证明 PMF。",
    }


def _count(values) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for v in values:
        out[str(v)] += 1
    return dict(out)
