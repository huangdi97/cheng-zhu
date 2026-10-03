"""Local product analytics (v1.4 ProductEvent).

 INVARIANT (canonical §21):
  - Local only. Nothing here sends data anywhere; remote telemetry is a
    separate opt-in that does not exist yet.
  - Events carry IDs, counts, durations, booleans and hashed categories.
    Free text is never stored: string props longer than a short token are
    dropped, and keys that name sensitive payloads are rejected outright.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Optional

from core.logger import get_logger
from services.storage import product as store

_log = get_logger("product.events")

EVENT_NAMES = frozenset({
    "goal_created", "goal_opened", "goal_reopened",
    "next_focus_opened", "next_focus_completed", "next_focus_changed",
    "practice_started", "practice_completed",
    "preflight_started", "live_started", "live_completed",
    "fast_cue_rendered", "fast_cue_expanded", "fast_cue_helpful", "fast_cue_dismissed",
    "fast_cue_regenerated", "deep_opened", "speech_after_cue",
    "reflection_opened", "reflection_action",
    "fact_inbox_created", "fact_inbox_opened", "fact_resolved", "fact_dismissed", "fact_reopened",
    "quick_note_created", "quick_note_opened", "quick_note_used_in_pack", "quick_note_opened_in_live",
    "quick_note_from_reflection",
    "pin_created", "pin_used_in_reflection", "next_focus_from_pin", "story_from_pin", "fact_check_from_pin",
    "nudge_shown", "nudge_dismissed", "nudge_actioned", "nudge_disabled",
    "command_executed", "session_feedback",
    "material_added", "material_replaced", "material_failed",
    "guided_practice_completed", "onboarding_completed",
})

_FORBIDDEN_KEYS = re.compile(
    r"(resume|transcript|api_?key|token|secret|password|audio|evidence_text|content|answer_text|jd)", re.I
)
_SAFE_STR = re.compile(r"^[A-Za-z0-9_.:\-]{0,48}$")


def hash_category(value: str) -> str:
    return hashlib.sha256((value or "").strip().lower().encode("utf-8")).hexdigest()[:12]


def sanitize_props(props: Optional[dict[str, Any]]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in (props or {}).items():
        key = str(key)[:40]
        if _FORBIDDEN_KEYS.search(key):
            continue
        if isinstance(value, bool) or value is None:
            clean[key] = value
        elif isinstance(value, (int, float)):
            clean[key] = value
        elif isinstance(value, str):
            if _SAFE_STR.match(value):
                clean[key] = value
            else:
                clean[f"{key}_hash"] = hash_category(value)
        elif isinstance(value, (list, tuple)):
            clean[f"{key}_count"] = len(value)
    return clean


def record(name: str, goal_id: str = "", session_id: str = "", **props: Any) -> bool:
    """Record one local product event; never raises into the caller."""
    if name not in EVENT_NAMES:
        _log.debug("unknown product event dropped: %s", name)
        return False
    try:
        with store.connect() as conn:
            conn.execute(
                "INSERT INTO product_event (name, ts, goal_id, session_id, props_json) VALUES (?, ?, ?, ?, ?)",
                (name, store.now(), str(goal_id or "")[:64], str(session_id or "")[:64],
                 json.dumps(sanitize_props(props), ensure_ascii=False)),
            )
        return True
    except Exception as exc:  # noqa: BLE001 — analytics must never break a product action
        _log.warning("product event %s not recorded: %s", name, exc)
        return False


def list_events(name: str = "", goal_id: str = "", since: float = 0.0, limit: int = 500) -> list[dict[str, Any]]:
    where, params = ["ts >= ?"], [since]
    if name:
        where.append("name = ?")
        params.append(name)
    if goal_id:
        where.append("goal_id = ?")
        params.append(goal_id)
    return store.select("product_event", " AND ".join(where), tuple(params), "ts DESC", limit)


def counts(since: float = 0.0) -> dict[str, int]:
    out: dict[str, int] = {}
    with store.connect() as conn:
        for row in conn.execute(
            "SELECT name, COUNT(*) FROM product_event WHERE ts >= ? GROUP BY name", (since,)
        ).fetchall():
            out[str(row[0])] = int(row[1])
    return out


def clear() -> int:
    with store.connect() as conn:
        return conn.execute("DELETE FROM product_event").rowcount
