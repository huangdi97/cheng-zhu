"""Intelligence storage: SQLite persistence for the Intelligence Core.

 COMPATIBILITY:
  - intelligence.db is a fresh database file; existing user databases
    (prep/review/knowledge/resume_history/job_tracker) are never touched here.
  - House style follows the other storage modules: module-level path via
    storage.paths.sqlite_path, WAL, Row factory, threading.Lock, JSON payload
    stored in TEXT columns.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from core.logger import get_logger
from services.storage.paths import sqlite_path
from services.storage.intelligence_migrations import ensure_schema

_log = get_logger("storage.intelligence")

DB_PATH = sqlite_path("intelligence.db")
_LOCK = threading.Lock()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _LOCK:
        conn = _conn()
        try:
            ensure_schema(conn)
        finally:
            conn.close()


def backup_database() -> Optional[str]:
    """Snapshot intelligence.db (+wal/shm) before an upgrade; returns the path."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = f"{DB_PATH}.backup-{stamp}"
    try:
        with _LOCK:
            for suffix in ("", "-wal", "-shm"):
                src = Path(DB_PATH + suffix)
                if src.exists():
                    shutil.copy2(src, target + suffix)
        return target
    except OSError as exc:
        _log.warning("intelligence db backup failed: %s", exc)
        return None


def _write(statement: str, params: tuple) -> None:
    with _LOCK:
        conn = _conn()
        try:
            conn.execute(statement, params)
            conn.commit()
        finally:
            conn.close()


def _read(statement: str, params: tuple = ()) -> list[sqlite3.Row]:
    with _LOCK:
        conn = _conn()
        try:
            return list(conn.execute(statement, params).fetchall())
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Candidate representation
# ---------------------------------------------------------------------------

def save_candidate_profile(
    candidate_id: str,
    *,
    display_name: str = "",
    resume_history_id: Optional[int] = None,
    profile_text: str = "",
) -> None:
    now = time.time()
    _write(
        "INSERT INTO candidate_profile (id, display_name, resume_history_id, profile_text, schema_version, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name, resume_history_id=excluded.resume_history_id, "
        "profile_text=excluded.profile_text, updated_at=excluded.updated_at",
        (candidate_id, display_name, resume_history_id, profile_text, now, now),
    )


def get_candidate_profile(candidate_id: str) -> Optional[dict[str, Any]]:
    rows = _read("SELECT * FROM candidate_profile WHERE id = ?", (candidate_id,))
    return dict(rows[0]) if rows else None


def active_candidate_id() -> str:
    """Single-candidate local product: the active profile is the latest one."""
    rows = _read("SELECT id FROM candidate_profile ORDER BY updated_at DESC LIMIT 1")
    return str(rows[0]["id"]) if rows else ""


def save_claims(candidate_id: str, claims: list[dict[str, Any]]) -> int:
    """Replace the claim set for one rebuild batch. Returns rows written.

    Duplicate merge happens upstream (candidate_representation); here we
    upsert on id so re-running a rebuild never duplicates rows.
    """
    now = time.time()
    written = 0
    with _LOCK:
        conn = _conn()
        try:
            for claim in claims:
                conn.execute(
                    "INSERT INTO claim (id, candidate_id, type, text, source, truth_status, confidence, metadata_json, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET text=excluded.text, truth_status=excluded.truth_status, "
                    "confidence=excluded.confidence, metadata_json=excluded.metadata_json, updated_at=excluded.updated_at",
                    (
                        claim["id"],
                        candidate_id,
                        claim.get("type", "fact"),
                        claim["text"],
                        claim.get("source", "resume"),
                        claim.get("truth_status", "SUPPORTED"),
                        float(claim.get("confidence", 0.5)),
                        json.dumps(claim.get("metadata", {}), ensure_ascii=False),
                        now,
                        now,
                    ),
                )
                written += 1
            conn.commit()
        finally:
            conn.close()
    return written


def list_claims(candidate_id: str, limit: int = 500) -> list[dict[str, Any]]:
    rows = _read(
        "SELECT * FROM claim WHERE candidate_id = ? ORDER BY confidence DESC, updated_at DESC LIMIT ?",
        (candidate_id, limit),
    )
    return [dict(row) for row in rows]


def update_claim_status(claim_id: str, truth_status: str, confidence: Optional[float] = None) -> bool:
    params: list[Any] = [truth_status]
    query = "UPDATE claim SET truth_status = ?, updated_at = ?"
    if confidence is not None:
        query += ", confidence = ?"
        params.append(float(confidence))
    params.append(time.time())
    query += " WHERE id = ?"
    params.append(claim_id)
    with _LOCK:
        conn = _conn()
        try:
            cur = conn.execute(query, tuple(params))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def save_evidence_batch(candidate_id: str, evidences: list[dict[str, Any]], links: list[tuple[str, str]]) -> int:
    now = time.time()
    written = 0
    with _LOCK:
        conn = _conn()
        try:
            for item in evidences:
                conn.execute(
                    "INSERT INTO evidence (id, candidate_id, source, text, metadata_json, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, '{}', ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET text=excluded.text, updated_at=excluded.updated_at",
                    (item["id"], candidate_id, item.get("source", "resume"), item["text"], now, now),
                )
                written += 1
            for claim_id, evidence_id in links:
                conn.execute(
                    "INSERT OR IGNORE INTO claim_evidence (claim_id, evidence_id, created_at) VALUES (?, ?, ?)",
                    (claim_id, evidence_id, now),
                )
            conn.commit()
        finally:
            conn.close()
    return written


def list_evidence(candidate_id: str, limit: int = 500) -> list[dict[str, Any]]:
    rows = _read(
        "SELECT * FROM evidence WHERE candidate_id = ? ORDER BY created_at DESC LIMIT ?",
        (candidate_id, limit),
    )
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Job representation
# ---------------------------------------------------------------------------

def save_job_profile(job_id: str, fields: dict[str, Any]) -> None:
    now = time.time()
    _write(
        "INSERT INTO job_profile (id, company, title, level, jd_text, responsibilities_json, must_have_json, "
        "nice_to_have_json, technologies_json, competencies_json, likely_dimensions_json, alignment_json, "
        "schema_version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET company=excluded.company, title=excluded.title, level=excluded.level, "
        "jd_text=excluded.jd_text, responsibilities_json=excluded.responsibilities_json, "
        "must_have_json=excluded.must_have_json, nice_to_have_json=excluded.nice_to_have_json, "
        "technologies_json=excluded.technologies_json, competencies_json=excluded.competencies_json, "
        "likely_dimensions_json=excluded.likely_dimensions_json, alignment_json=excluded.alignment_json, "
        "updated_at=excluded.updated_at",
        (
            job_id,
            fields.get("company", ""),
            fields.get("title", ""),
            fields.get("level", ""),
            fields.get("jd_text", ""),
            json.dumps(fields.get("responsibilities", []), ensure_ascii=False),
            json.dumps(fields.get("must_have", []), ensure_ascii=False),
            json.dumps(fields.get("nice_to_have", []), ensure_ascii=False),
            json.dumps(fields.get("technologies", []), ensure_ascii=False),
            json.dumps(fields.get("competencies", []), ensure_ascii=False),
            json.dumps(fields.get("likely_interview_dimensions", []), ensure_ascii=False),
            json.dumps(fields.get("alignment", {}), ensure_ascii=False),
            now,
            now,
        ),
    )


def get_job_profile(job_id: str) -> Optional[dict[str, Any]]:
    rows = _read("SELECT * FROM job_profile WHERE id = ?", (job_id,))
    if not rows:
        return None
    row = dict(rows[0])
    for key in ("responsibilities", "must_have", "nice_to_have", "technologies", "competencies", "likely_interview_dimensions"):
        column = row.pop(f"{key}_json" if f"{key}_json" in row else key, "[]")
        try:
            row[key] = json.loads(row.get(f"_{key}_list", "[]") if column is None else column)
        except (json.JSONDecodeError, TypeError):
            row[key] = []
    try:
        row["alignment"] = json.loads(row.pop("alignment_json", "{}"))
    except (json.JSONDecodeError, TypeError):
        row["alignment"] = {}
    return row


def latest_job_id() -> str:
    rows = _read("SELECT id FROM job_profile ORDER BY updated_at DESC LIMIT 1")
    return str(rows[0]["id"]) if rows else ""


# ---------------------------------------------------------------------------
# Interview state / turns / telemetry
# ---------------------------------------------------------------------------

def save_state_snapshot(session_id: str, version: int, state_json: str) -> None:
    _write(
        "INSERT OR REPLACE INTO interview_state_snapshot (id, session_id, version, state_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (f"{session_id}-{version}", session_id, version, state_json, time.time()),
    )


def latest_state_snapshot(session_id: str) -> Optional[dict[str, Any]]:
    rows = _read(
        "SELECT * FROM interview_state_snapshot WHERE session_id = ? ORDER BY version DESC LIMIT 1",
        (session_id,),
    )
    if not rows:
        return None
    row = dict(rows[0])
    try:
        row["state"] = json.loads(row.pop("state_json"))
    except (json.JSONDecodeError, TypeError):
        return None
    return row


def save_interview_turn(fields: dict[str, Any]) -> None:
    _write(
        "INSERT INTO interview_turn (id, session_id, seq, question_raw, question_resolved, question_type, route, "
        "guidance_text, truth_flags_json, latency_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            fields["id"],
            fields["session_id"],
            int(fields.get("seq", 0)),
            fields.get("question_raw", ""),
            fields.get("question_resolved", ""),
            fields.get("question_type", ""),
            fields.get("route", ""),
            fields.get("guidance_text", ""),
            json.dumps(fields.get("truth_flags", []), ensure_ascii=False),
            int(fields.get("latency_ms", 0)),
            time.time(),
        ),
    )


def save_guidance_event(fields: dict[str, Any]) -> None:
    _write(
        "INSERT INTO guidance_event (id, session_id, event, route, provider, model, latency_ms, tokens_json, "
        "context_ids_json, truth_flags_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            fields["id"],
            fields["session_id"],
            fields["event"],
            fields.get("route", ""),
            fields.get("provider", ""),
            fields.get("model", ""),
            int(fields.get("latency_ms", 0)),
            json.dumps(fields.get("tokens", {}), ensure_ascii=False),
            json.dumps(fields.get("context_ids", []), ensure_ascii=False),
            json.dumps(fields.get("truth_flags", []), ensure_ascii=False),
            time.time(),
        ),
    )


def list_guidance_events(session_id: str, limit: int = 200) -> list[dict[str, Any]]:
    rows = _read(
        "SELECT * FROM guidance_event WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
        (session_id, limit),
    )
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Controlled long-term memory write-back
# ---------------------------------------------------------------------------

def upsert_memory_item(kind: str, text: str, *, candidate_id: str = "", session_id: str = "") -> None:
    """Only policy-approved kinds may call this (see intelligence/memory_policy)."""
    now = time.time()
    _write(
        "INSERT INTO memory_item (id, candidate_id, session_id, kind, text, confirmations, metadata_json, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 1, '{}', ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET text=excluded.text, confirmations=confirmations+1, updated_at=excluded.updated_at",
        (f"{kind}-{abs(hash(text)) % 10**12}", candidate_id, session_id, kind, text, now, now),
    )


def list_memory_items(kind: str, limit: int = 100) -> list[dict[str, Any]]:
    rows = _read(
        "SELECT * FROM memory_item WHERE kind = ? ORDER BY updated_at DESC LIMIT ?",
        (kind, limit),
    )
    return [dict(row) for row in rows]


def delete_memory_item(item_id: str) -> None:
    _write("DELETE FROM memory_item WHERE id = ?", (item_id,))


def save_voice_profile(candidate_id: str, profile_json: str, sample_count: int, enabled: bool) -> None:
    now = time.time()
    _write(
        "INSERT INTO voice_profile (id, candidate_id, profile_json, sample_count, enabled, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET profile_json=excluded.profile_json, sample_count=excluded.sample_count, "
        "enabled=excluded.enabled, updated_at=excluded.updated_at",
        (f"voice-{candidate_id}", candidate_id, profile_json, sample_count, int(enabled), now, now),
    )


def get_voice_profile(candidate_id: str) -> Optional[dict[str, Any]]:
    rows = _read("SELECT * FROM voice_profile WHERE candidate_id = ?", (candidate_id,))
    if not rows:
        return None
    row = dict(rows[0])
    try:
        row["profile"] = json.loads(row.pop("profile_json", "{}"))
    except (json.JSONDecodeError, TypeError):
        row["profile"] = {}
    return row


init_db()
