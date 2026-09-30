"""User-perceived latency clock (R2 Stage I).

Time points (time.monotonic seconds):

  E  = estimated interviewer speech end (VAD flush minus trailing silence)
  Q0 = first meaningful partial ASR text
  Q1 = stable resolved question reaches the answer worker
  G0 = first usable cue emitted (guidance_fast)
  A0 = first deep answer token
  D0 = deep answer complete

Metrics:

  QBD               = Q1 - E
  TTFUG_user        = G0 - E     <- the primary user metric
  TTFUG_predictive  = G0 - Q0
  TTFUG_internal    = G0 - Q1
  TTFA              = A0 - Q1
  TTD               = D0 - Q1

 INVARIANT:
  - The first model token is A0, never "TTFUG".
  - When E is unknown (manual text, screenshot) TTFUG_user is None — it is
    never back-filled from another clock.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Optional

# E / Q0 older than this before Q1 belong to a previous turn.
_MAX_PENDING_AGE_SEC = 30.0
_HISTORY = 500

_lock = threading.Lock()
_pending: dict[str, dict[str, float]] = {}
_turns: dict[str, dict[str, Any]] = {}
_history: deque[dict[str, Any]] = deque(maxlen=_HISTORY)


def _now() -> float:
    return time.monotonic()


def mark_speech_end(session_id: str, mono: Optional[float] = None) -> None:
    with _lock:
        _pending.setdefault(session_id or "default", {})["E"] = float(mono if mono is not None else _now())


def mark_first_partial(session_id: str, mono: Optional[float] = None) -> None:
    """Only the first partial of a turn counts (Q0)."""
    with _lock:
        pending = _pending.setdefault(session_id or "default", {})
        pending.setdefault("Q0", float(mono if mono is not None else _now()))


def start_turn(
    session_id: str,
    qa_id: str,
    *,
    q1: Optional[float] = None,
    source: str = "",
    provisional: bool = False,
) -> None:
    """Start the turn clock at Q1.

    A provisional cue (stable streaming partial) starts the turn early and
    keeps E; the later authoritative confirmation on the same qa_id only
    moves Q1 (QBD stays "speech end -> question confirmed") and never
    resets E or an already recorded G0.
    """
    q1_value = float(q1 if q1 is not None else _now())
    with _lock:
        existing = _turns.get(qa_id)
        if existing is not None:
            if existing.get("provisional") and not provisional:
                existing["provisional"] = False
                existing["P1"] = existing.get("Q1")
                existing["Q1"] = q1_value
            return
        pending = _pending.pop(session_id or "default", {})
        turn: dict[str, Any] = {"qa_id": qa_id, "session_id": session_id, "source": source, "Q1": q1_value, "provisional": provisional}
        for key in ("E", "Q0"):
            value = pending.get(key)
            if value is not None and 0 <= q1_value - value <= _MAX_PENDING_AGE_SEC:
                turn[key] = value
        _turns[qa_id] = turn


def mark(qa_id: str, point: str, mono: Optional[float] = None) -> None:
    """Record G0 / A0 / D0 once per turn (the first occurrence wins)."""
    if point not in {"G0", "A0", "D0"}:
        raise ValueError(point)
    with _lock:
        turn = _turns.get(qa_id)
        if turn is not None and point not in turn:
            turn[point] = float(mono if mono is not None else _now())


def _ms(a: Optional[float], b: Optional[float]) -> Optional[int]:
    if a is None or b is None:
        return None
    return int(round((a - b) * 1000))


def metrics(qa_id: str) -> dict[str, Optional[int]]:
    with _lock:
        turn = dict(_turns.get(qa_id) or {})
    return _metrics_of(turn)


def _metrics_of(turn: dict[str, Any]) -> dict[str, Optional[int]]:
    e, q0, q1 = turn.get("E"), turn.get("Q0"), turn.get("Q1")
    g0, a0, d0 = turn.get("G0"), turn.get("A0"), turn.get("D0")
    return {
        "qbd_ms": _ms(q1, e),
        "ttfug_user_ms": _ms(g0, e),
        "ttfug_predictive_ms": _ms(g0, q0),
        "ttfug_internal_ms": _ms(g0, q1),
        "ttfa_ms": _ms(a0, q1),
        "ttd_ms": _ms(d0, q1),
    }


def finish_turn(qa_id: str) -> dict[str, Optional[int]]:
    with _lock:
        turn = _turns.pop(qa_id, None)
    if not turn:
        return {}
    result = {**_metrics_of(turn), "qa_id": qa_id, "source": turn.get("source", ""), "session_id": turn.get("session_id", "")}
    with _lock:
        _history.append(result)
    return result


def recent(limit: int = 200) -> list[dict[str, Any]]:
    with _lock:
        return list(_history)[-limit:]


def percentile(values: list[int], pct: float) -> Optional[int]:
    clean = sorted(v for v in values if v is not None)
    if not clean:
        return None
    k = max(0, min(len(clean) - 1, int(round((pct / 100.0) * (len(clean) - 1)))))
    return clean[k]


def summary(rows: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
    rows = rows if rows is not None else recent(_HISTORY)
    out: dict[str, Any] = {"turns": len(rows)}
    for key in ("qbd_ms", "ttfug_user_ms", "ttfug_predictive_ms", "ttfug_internal_ms", "ttfa_ms", "ttd_ms"):
        values = [r.get(key) for r in rows if r.get(key) is not None]
        out[key] = {"n": len(values), "p50": percentile(values, 50), "p95": percentile(values, 95)}
    return out


def reset() -> None:
    with _lock:
        _pending.clear()
        _turns.clear()
        _history.clear()
