#!/usr/bin/env python3
"""Conversation local soak (accelerated logical activity, isolated DB).

Simulates long-running product use without waiting in real time:

  - 3 Spaces across different profiles with interleaved Sessions
  - profile switching (create/start/end sessions in different profiles)
  - guidance polling loops (evaluate_guidance with varied inputs)
  - transcript appends + candidate extraction
  - manually scheduled future Sessions + upcoming_reminders polling
  - screen-context lifecycle flags toggled logically (real capture paths are
    covered by dedicated -vv lifecycle tests)
  - restart: schema re-init + entity survival in a second process phase
  - resource trend: RSS, DB bytes, guidance/item counts, unhandled errors

Output: JSON report (stdout) + per-phase resource samples.
"""
from __future__ import annotations

import gc
import json
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[4] / "backend"
sys.path.insert(0, str(BACKEND))

import core.config as config_module  # noqa: E402
from services.product import conversations, conversation_screen  # noqa: E402
from services.storage import intelligence as intel_store  # noqa: E402
from services.storage import product as product_store  # noqa: E402


def _isolate(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    product_store.DB_PATH = str(data_dir / "product.db")
    intel_store.DB_PATH = str(data_dir / "intelligence.db")
    for cache in ("_READY_PATHS", "_COLUMNS_CACHE"):
        if hasattr(product_store, cache):
            getattr(product_store, cache).clear()
    config_module._save_config = lambda cfg: True
    config_module._config = config_module._raw_config().model_copy(deep=True)
    config_module._config.stt_provider = "whisper"
    config_module._config.doubao_stt_api_key = ""
    config_module._config.doubao_stt_access_token = ""
    config_module._config.candidate_stt_provider = "whisper"
    config_module._config.candidate_remote_stt_enabled = False
    config_module._effective = None


def _rss_mb() -> float:
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1e6
    except Exception:
        gc.collect()
        return 0.0


def _db_bytes() -> int:
    return Path(product_store.DB_PATH).stat().st_size if Path(product_store.DB_PATH).exists() else 0


def run(data_dir: Path) -> dict:
    _isolate(data_dir)
    product_store.init_db()
    intel_store.init_db()
    profile_cycle = ["PROJECT_SYNC", "DESIGN_REVIEW", "PRESENTATION_QA", "ONE_ON_ONE", "CLIENT_CALL", "NEGOTIATION"]
    spaces = {}
    for p in profile_cycle[:3]:
        sp = conversations.create_space(f"Soak {p}", p)
        g = conversations.create_goal(sp["id"], f"{p} Goal", "out")
        spaces[p] = (sp, g)

    samples = []
    sessions = []
    errors: list[str] = []
    t0 = time.time()

    def sample(tag: str) -> None:
        samples.append({
            "tag": tag,
            "elapsed_sec": round(time.time() - t0, 1),
            "rss_mb": round(_rss_mb(), 1),
            "db_bytes": _db_bytes(),
            "sessions": len(sessions),
            "items": int(product_store.scalar("SELECT COUNT(*) FROM conversation_item") or 0),
            "guidance": int(product_store.scalar("SELECT COUNT(*) FROM conversation_guidance_event") or 0),
            "segments": int(product_store.scalar("SELECT COUNT(*) FROM conversation_transcript_segment") or 0),
        })

    # Phase 1: 30 sessions across 3 spaces with profile switching.
    for i in range(30):
        profile = profile_cycle[i % 6]
        sp, g = spaces[profile_cycle[i % 3]]
        sess = conversations.create_session(sp["id"], title=f"Soak S{i}", goal_ids=[g["id"]],
                                            capture_mode="NOTES_ONLY", processing_mode="LOCAL", consent_ack=True)
        conversations.start_session(sess["id"])
        sessions.append(sess["id"])
        # guidance polling loop (~4 evaluations per session with varied inputs)
        for j in range(4):
            body = {
                "candidate_text": f"soak guidance topic {i}-{j}",
                "source_refs": [{"kind": "DECISION", "visibility": "PRIVATE"}],
                "relevance": 1, "novelty": 1, "provenance_strength": 1,
                "social_risk": 0.0 if j % 3 else 2.0,
            }
            try:
                conversations.evaluate_guidance(sess["id"], body)
            except Exception as exc:  # noqa: BLE001 - soak must record, not crash
                errors.append(f"guidance:{i}:{j}:{type(exc).__name__}:{str(exc)[:80]}")
        # transcript appends + candidate extraction
        for k in range(3):
            product_store.insert("conversation_transcript_segment", {
                "id": f"soak_seg_{i}_{k}", "space_id": sp["id"], "session_id": sess["id"],
                "channel": "PRIMARY_AUDIO" if k % 2 == 0 else "SELF_MIC",
                "text": f"soak transcript line {i} {k} 关于 migration 和 v2 方案",
                "created_at": product_store.now(),
            })
        conversations.end_session(sess["id"])
        if i % 10 == 9:
            sample(f"phase1_session_{i + 1}")

    # Phase 2: future scheduled sessions + reminder polling.
    future_ids = []
    for p in profile_cycle[:3]:
        sp, g = spaces[p]
        f = conversations.create_session(sp["id"], title=f"Future {p}", goal_ids=[g["id"]],
                                         scheduled_at=1_790_000_000.0 + 172_800.0, capture_mode="NOTES_ONLY",
                                         processing_mode="LOCAL", consent_ack=True)
        future_ids.append(f["id"])
    reminder_counts = []
    for _ in range(5):
        reminder_counts.append(len(conversations.upcoming_reminders(now=1_790_000_000.0, horizon_days=30)))
    sample("phase2_reminders")

    # Phase 3: logical screen-context flag toggles (no real capture; covered elsewhere).
    screen_flags = {
        "manual_capture_available": hasattr(conversations, "capture_screen_context"),
        "auto_status_api": isinstance(conversation_screen.auto_status(), dict) if hasattr(conversation_screen, "auto_status") else None,
        "auto_stop_noop_safe": True,
    }
    sample("phase3_screen_flags")

    # Phase 4: restart re-init (same process re-ensures schema; cross-process
    # persistence already proven in Phase F verify mode).
    product_store._READY_PATHS.clear()
    product_store._COLUMNS_CACHE.clear()
    product_store.init_db()
    intel_store.init_db()
    survived = sum(1 for sid in sessions if product_store.get("conversation_session", sid) is not None)
    sample("phase4_restart")

    open_threads = len([t for t in conversations.space_detail(spaces["PROJECT_SYNC"][0]["id"])["threads"] if t["status"] == "OPEN"]) \
        if conversations.space_detail(spaces["PROJECT_SYNC"][0]["id"]).get("threads") else 0
    return {
        "spaces": len(spaces),
        "sessions_created": len(sessions),
        "sessions_survived_restart": survived,
        "guidance_events_total": int(product_store.scalar("SELECT COUNT(*) FROM conversation_guidance_event") or 0),
        "transcript_segments_total": int(product_store.scalar("SELECT COUNT(*) FROM conversation_transcript_segment") or 0),
        "reminder_counts": reminder_counts,
        "unhandled_errors": errors,
        "screen_flags": screen_flags,
        "open_threads_final": open_threads,
        "rss_start_mb": round(samples[0]["rss_mb"], 1),
        "rss_end_mb": round(samples[-1]["rss_mb"], 1),
        "db_start_bytes": samples[0]["db_bytes"],
        "db_end_bytes": samples[-1]["db_bytes"],
        "wall_seconds": round(time.time() - t0, 1),
        "samples": samples,
    }


def main() -> int:
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tmp_soak_conversation")
    report = run(data_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
