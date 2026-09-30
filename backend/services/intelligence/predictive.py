"""Predictive Start (R2 Stage I, 12.3).

From the first meaningful partial ASR text, before the question is stable:
  - form a question hypothesis (type / domain / follow-up guess),
  - prefetch KB passages for the hypothesis.

Allowed only as read-only warm-up. Never commits interview state, never
records a claim, never produces an answer or an on-screen cue. The answer
worker reuses a prefetch only when the stable question still matches the
hypothesis closely; otherwise it retrieves normally (rollback).
"""
from __future__ import annotations

import threading
import time
from difflib import SequenceMatcher
from typing import Any, Optional

_MAX_AGE_SEC = 20.0
_MIN_SIMILARITY = 0.6
_MIN_CHARS = 6

_lock = threading.Lock()
_prefetch: dict[str, dict[str, Any]] = {}
_stats = {"partials": 0, "prefetches": 0, "hits": 0, "misses": 0}


def on_partial(session_id: str, text: str) -> None:
    value = (text or "").strip()
    if len(value) < _MIN_CHARS:
        return
    with _lock:
        _stats["partials"] += 1
        current = _prefetch.get(session_id)
        # Re-prefetch only when the partial has grown meaningfully.
        if current and len(value) - len(current.get("text", "")) < 6 and time.monotonic() - current["at"] < _MAX_AGE_SEC:
            return
        _prefetch[session_id] = {"text": value, "at": time.monotonic(), "hits": None, "hypothesis": {}}
    threading.Thread(target=_warm, args=(session_id, value), name="predictive-prefetch", daemon=True).start()


def _warm(session_id: str, text: str) -> None:
    hypothesis: dict[str, Any] = {}
    hits: Optional[list] = None
    try:
        from services.intelligence.question_understanding import classify_question_type_21, detect_domain

        hypothesis = {"question_type": classify_question_type_21(text).value, "domain": detect_domain(text)}
    except Exception:  # noqa: BLE001
        pass
    try:
        from core.config import get_config
        from services.kb.retriever import retrieve

        cfg = get_config()
        if bool(getattr(cfg, "kb_enabled", False)):
            hits = retrieve(text, k=int(getattr(cfg, "kb_top_k", 4) or 4), deadline_ms=120, mode="asr_realtime")
    except Exception:  # noqa: BLE001
        hits = None
    with _lock:
        entry = _prefetch.get(session_id)
        if entry and entry.get("text") == text:
            entry["hits"] = hits
            entry["hypothesis"] = hypothesis
            _stats["prefetches"] += 1


def take(session_id: str, stable_question: str) -> Optional[dict[str, Any]]:
    """Consume a prefetch if it still matches the stable question."""
    with _lock:
        entry = _prefetch.pop(session_id, None)
        if not entry or entry.get("hits") is None:
            _stats["misses"] += 1
            return None
        if time.monotonic() - entry["at"] > _MAX_AGE_SEC:
            _stats["misses"] += 1
            return None
        a, b = entry["text"], (stable_question or "").strip()
        similarity = SequenceMatcher(None, a, b[: max(len(a), 1) + 8]).ratio() if b else 0.0
        if not b.startswith(a[: max(4, len(a) // 2)]) and similarity < _MIN_SIMILARITY:
            _stats["misses"] += 1
            return None
        _stats["hits"] += 1
        return entry


def stats() -> dict[str, int]:
    with _lock:
        return dict(_stats)


def reset() -> None:
    with _lock:
        _prefetch.clear()
        for key in _stats:
            _stats[key] = 0
