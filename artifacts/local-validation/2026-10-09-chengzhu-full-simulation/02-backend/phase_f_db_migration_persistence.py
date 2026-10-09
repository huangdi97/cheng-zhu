#!/usr/bin/env python3
"""Phase F — Product DB / Migration / Persistence local evidence.

Runs against an isolated temp data dir (never touches backend/data or the
developer's real stores). Modes:

  create   : fresh DB -> latest schema -> Conversation create/read/write
             for the full entity set (Space/Goal/Participant/Session/Pack/
             Decision/Commitment/OpenThread/Guidance/DraftAction/Reminder),
             then persists state ids to <data_dir>/state.json.
  verify   : new process re-opens the same DB and checks every entity still
             exists with identical content (restart persistence, D3).
  migrate  : builds a synthetic old schema (product migration v1 only,
             Interview-era goal row), migrates to LATEST (7), re-runs
             idempotently, verifies legacy rows + conversation tables.

Evidence outputs: JSON report printed to stdout (captured into the artifact).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[4] / "backend"
sys.path.insert(0, str(BACKEND))

import core.config as config_module  # noqa: E402
from services.product import conversations  # noqa: E402
from services.storage import product as product_store  # noqa: E402
from services.storage import intelligence as intel_store  # noqa: E402
from services.storage.product_migrations import (  # noqa: E402
    LATEST_SCHEMA_VERSION,
    ensure_schema,
)


def _isolate(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    product_store.DB_PATH = str(data_dir / "product.db")
    intel_store.DB_PATH = str(data_dir / "intelligence.db")
    for cache in ("_READY_PATHS", "_COLUMNS_CACHE"):
        if hasattr(product_store, cache):
            getattr(product_store, cache).clear()
    # Hermetic config: local-only STT (mirrors the product_env fixture).
    config_module._save_config = lambda cfg: True
    config_module._config = config_module._raw_config().model_copy(deep=True)
    config_module._config.stt_provider = "whisper"
    config_module._config.doubao_stt_api_key = ""
    config_module._config.doubao_stt_access_token = ""
    config_module._config.candidate_stt_provider = "whisper"
    config_module._config.candidate_remote_stt_enabled = False
    config_module._effective = None


def schema_version(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


def mode_create(data_dir: Path) -> dict:
    _isolate(data_dir)
    product_store.init_db()
    intel_store.init_db()  # expression profile / voice profile lives here
    db_path = Path(product_store.DB_PATH)
    report = {"mode": "create", "db_path": str(db_path), "schema_version": schema_version(db_path)}
    assert schema_version(db_path) == LATEST_SCHEMA_VERSION, "fresh DB must be at LATEST_SCHEMA_VERSION"
    assert LATEST_SCHEMA_VERSION == 7

    # D1: Conversation create / read / write via the real service layer.
    space = conversations.create_space("PhaseF Project Sync", "PROJECT_SYNC")
    goal = conversations.create_goal(space["id"], "完成 migration 上线", "migration window 内无回滚")
    participant = conversations.add_participant(
        space["id"],
        display_name="王工",
        role="CTO",
        organization="客户",
        explicit_priority="migration stability",
        explicit_concern="rollback risk",
        decision_authority="architecture approval",
        relationship_context="customer technical lead",
    )
    session = conversations.create_session(
        space["id"],
        title="周一同步",
        goal_ids=[goal["id"]],
        scheduled_at=0,  # past: not a reminder candidate
        capture_mode="NOTES_ONLY",
        processing_mode="LOCAL",
        consent_ack=True,
    )
    started = conversations.start_session(session["id"])
    pack_id = started["pack"]["id"]
    assert started["session"]["status"] == "ACTIVE", "session must be ACTIVE after start"
    assert bool(started["pack"]["payload"]), "pack must be frozen at start"
    # Items + review (Decision/Commitment/OpenThread) then resolve one thread.
    decision = conversations.add_item(
        session["id"], item_type="Decision", title="采用方案 B",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "我们决定采用方案 B"}],
    )
    decision = conversations.review_item(decision["id"], "CONFIRM")
    commitment = conversations.add_item(
        session["id"], item_type="Commitment", title="周五前完成 rollout plan",
        owner_id="王工", source_refs=[{"kind": "USER_NOTE", "excerpt": "我来补 rollout plan"}],
    )
    commitment = conversations.review_item(commitment["id"], "CONFIRM")
    thread = conversations.add_item(
        session["id"], item_type="OpenQuestion", title="migration window 够不够？",
        source_refs=[{"kind": "TRANSCRIPT", "excerpt": "主要风险是 migration window 太短"}],
    )
    thread = conversations.review_item(thread["id"], "CONFIRM")
    thread_row = conversations.space_detail(space["id"])["threads"][0]
    resolved = conversations.resolve_open_thread(thread_row["id"])

    # Guidance event (deterministic evaluate_guidance).
    guidance = conversations.evaluate_guidance(session["id"], {
        "candidate_text": "关于 migration 方案，我们之前确认过采用方案 B。",
        "source_refs": [{"kind": "DECISION", "id": decision["id"], "visibility": "PRIVATE"}],
        "relevance": 1, "novelty": 1, "provenance_strength": 1,
    })

    # DraftAction (external writeback default ON -> draft allowed).
    draft = conversations.create_draft_action(
        session["id"], kind="CREATE_TASK_DRAFT", title="整理 migration 回滚清单",
        content="由王工跟进", target="王工",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "我来补 rollout plan"}],
    )

    # Reminder candidate: future manually scheduled session.
    future = conversations.create_session(
        space["id"], title="周四项目同步", goal_ids=[goal["id"]],
        scheduled_at=1_700_000_000.0 + 86_400 * 2, capture_mode="NOTES_ONLY",
        processing_mode="LOCAL", consent_ack=True,
    )
    reminders = conversations.upcoming_reminders(now=1_700_000_000.0, horizon_days=30)

    ids = {
        "space_id": space["id"], "goal_id": goal["id"], "participant_id": participant["id"],
        "session_id": session["id"], "pack_id": pack_id, "decision_id": decision["id"],
        "commitment_id": commitment["id"], "thread_id": thread["id"],
        "resolved_thread_id": resolved["id"], "guidance_id": guidance["guidance"]["id"],
        "draft_id": draft["id"], "future_session_id": future["id"],
    }
    (data_dir / "state.json").write_text(json.dumps(ids, ensure_ascii=False, indent=2), encoding="utf-8")
    report.update({
        "entities_created": len(ids),
        "reminder_count": len(reminders),
        "reminder_has_future": any(r["session_id"] == future["id"] for r in reminders),
        "decision_state": decision["state"],
        "commitment_state": commitment["state"],
        "resolved_status": resolved["status"],
        "ids": ids,
    })
    return report


def mode_verify(data_dir: Path) -> dict:
    _isolate(data_dir)
    product_store.init_db()  # restart: schema ensure + reopen from disk
    intel_store.init_db()  # voice profile store must exist after restart too
    ids = json.loads((data_dir / "state.json").read_text(encoding="utf-8"))
    report = {"mode": "verify", "schema_version": schema_version(Path(product_store.DB_PATH))}

    space = conversations.require_space(ids["space_id"])
    assert space["title"] == "PhaseF Project Sync"
    from services.storage import product as _store
    goal = _store.get("conversation_goal", ids["goal_id"])
    assert goal is not None and goal["title"] == "完成 migration 上线"
    participant = _store.get("conversation_participant", ids["participant_id"])
    assert participant is not None and participant["role"] == "CTO"
    decision = conversations.require_item(ids["decision_id"])
    commitment = conversations.require_item(ids["commitment_id"])
    thread = conversations.require_item(ids["thread_id"])
    assert decision["state"] == "AGREED", decision["state"]
    assert commitment["state"] == "COMMITTED", commitment["state"]
    assert thread["state"] == "DONE", thread["state"]
    resolved_thread = _store.get("conversation_open_thread", ids["resolved_thread_id"])
    assert resolved_thread is not None and resolved_thread["status"] == "RESOLVED"
    assert thread["id"] == ids["thread_id"]
    guidance_history = conversations.guidance_history(ids["session_id"])
    drafts = conversations.list_draft_actions(space["id"])
    reminders = conversations.upcoming_reminders(now=1_700_000_000.0, horizon_days=30)
    history = conversations.conversation_history(limit=100)
    report.update({
        "session_status_after_restart": conversations.require_session(ids["session_id"])["status"],
        "space_persisted": True,
        "decision_persisted_state": decision["state"],
        "commitment_persisted_state": commitment["state"],
        "thread_persisted_state": thread["state"],
        "guidance_events_after_restart": len(guidance_history),
        "space_detail_lists_session": any(s["id"] == ids["session_id"] for s in conversations.space_detail(space["id"])["sessions"]),
        "history_only_ended_sessions": not any(h["id"] == ids["session_id"] for h in history),
        "draft_actions_after_restart": len(drafts),
        "reminder_after_restart": any(r["session_id"] == ids["future_session_id"] for r in reminders),
        "phase_after_restart": conversations.conversation_state(ids["session_id"])["phase"],
    })
    return report


def _table_exists(table: str, row_id: str) -> bool:
    from services.storage import product as _store
    row = _store.get(table, row_id)
    return row is not None


def mode_migrate(data_dir: Path) -> dict:
    _isolate(data_dir)
    db_path = Path(product_store.DB_PATH)
    # Build a synthetic OLD product.db: migration step v1 only (Interview-era
    # product layer: goal + goal_material tables).
    conn = sqlite3.connect(str(db_path))
    try:
        from services.storage import product_migrations as pm
        step, name = pm._MIGRATIONS[1]
        step(conn)
        conn.execute("PRAGMA user_version = 1")
        conn.execute(
            "INSERT INTO goal (id, company, role, jd, status, stage, created_at, updated_at) "
            "VALUES ('old_goal_1', 'MindRank', 'AIDD Agent Engineer', 'RAG+Agent', 'ACTIVE', 'interview', 1000, 1000)"
        )
        conn.commit()
        legacy_count = conn.execute("SELECT COUNT(*) FROM goal").fetchone()[0]
    finally:
        conn.close()
    before = schema_version(db_path)
    assert before == 1

    # Migration v1 -> LATEST.
    conn = sqlite3.connect(str(db_path))
    try:
        ensure_schema(conn)
        conn.commit()
        after = int(conn.execute("PRAGMA user_version").fetchone()[0])
        legacy = conn.execute("SELECT id, company, status FROM goal WHERE id='old_goal_1'").fetchone()
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()

    # Idempotent re-run: no error, version unchanged, no duplicate columns.
    conn = sqlite3.connect(str(db_path))
    try:
        ensure_schema(conn)
        conn.commit()
        again = int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()

    conv_tables = {t for t in tables if t.startswith("conversation_")}
    return {
        "mode": "migrate",
        "version_before": before,
        "version_after": after,
        "version_rerun": again,
        "legacy_goal_row_intact": list(legacy) if legacy else None,
        "legacy_rows_seeded": legacy_count,
        "conversation_tables": sorted(conv_tables),
        "idempotent_rerun_ok": after == again == LATEST_SCHEMA_VERSION,
        "latest_expected": LATEST_SCHEMA_VERSION,
    }


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "create"
    data_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("tmp_phase_f")
    if mode == "create":
        report = mode_create(data_dir)
    elif mode == "verify":
        report = mode_verify(data_dir)
    elif mode == "migrate":
        report = mode_migrate(data_dir)
    else:
        raise SystemExit(f"unknown mode {mode}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
