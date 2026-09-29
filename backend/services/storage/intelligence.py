"""Intelligence storage: SQLite persistence for the Intelligence Core.

 COMPATIBILITY:
  - intelligence.db is a fresh database file; existing user databases
    (prep/review/knowledge/resume_history/job_tracker) are never touched here.
  - House style follows the other storage modules: module-level path via
    storage.paths.sqlite_path, WAL, Row factory, threading.Lock, JSON payload
    stored in TEXT columns.
"""
from __future__ import annotations

import hashlib
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
    """Single-candidate local product: the active profile is the latest one.

    Used when BUILDING an InterviewPack (prepare time). The Live path must
    read the frozen pack instead and never call this.
    """
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
                    "ON CONFLICT(id) DO UPDATE SET candidate_id=excluded.candidate_id, text=excluded.text, truth_status=excluded.truth_status, "
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
    # Params follow the SQL placeholder order: status, updated_at,
    # [confidence], id — appending confidence before updated_at would swap
    # the two values silently.
    params: list[Any] = [truth_status, time.time()]
    query = "UPDATE claim SET truth_status = ?, updated_at = ?"
    if confidence is not None:
        query += ", confidence = ?"
        params.append(float(confidence))
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
    """Most recently analyzed job. Prepare-side convenience only.

    INVARIANT: never call from the Live answer path — a job analyzed after a
    pack was frozen must not leak into that session (R2 Stage F).
    """
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

def _memory_item_id(kind: str, text: str) -> str:
    # hashlib (not builtin hash, which is salted per process): the same
    # learning signal must upsert across app restarts so confirmations count.
    digest = hashlib.sha1(f"{kind}|{text}".encode("utf-8")).hexdigest()[:12]
    return f"{kind}-{digest}"


def upsert_memory_item(kind: str, text: str, *, candidate_id: str = "", session_id: str = "") -> None:
    """Only policy-approved kinds may call this (see intelligence/memory_policy)."""
    now = time.time()
    _write(
        "INSERT INTO memory_item (id, candidate_id, session_id, kind, text, confirmations, metadata_json, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 1, '{}', ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET text=excluded.text, confirmations=confirmations+1, updated_at=excluded.updated_at",
        (_memory_item_id(kind, text), candidate_id, session_id, kind, text, now, now),
    )


def list_memory_items(kind: str, limit: int = 100) -> list[dict[str, Any]]:
    rows = _read(
        "SELECT * FROM memory_item WHERE kind = ? ORDER BY updated_at DESC LIMIT ?",
        (kind, limit),
    )
    return [dict(row) for row in rows]


def delete_memory_item(item_id: str) -> None:
    _write("DELETE FROM memory_item WHERE id = ?", (item_id,))


_STORY_FIELDS = ("title", "situation", "challenge", "action", "result", "reflection")


def save_story(story_id: str, candidate_id: str, fields: dict[str, Any], tags: Optional[list[str]] = None) -> None:
    """User-authored Story (S/C/A/R/Reflection). Never AI-invented."""
    now = time.time()
    values = [str(fields.get(key, "") or "") for key in _STORY_FIELDS]
    _write(
        "INSERT INTO story (id, candidate_id, title, situation, challenge, action, result, reflection, tags_json, truth_status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'SUPPORTED', ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET title=excluded.title, situation=excluded.situation, challenge=excluded.challenge, "
        "action=excluded.action, result=excluded.result, reflection=excluded.reflection, tags_json=excluded.tags_json, updated_at=excluded.updated_at",
        (story_id, candidate_id, *values, json.dumps(tags or [], ensure_ascii=False), now, now),
    )


def delete_story(story_id: str) -> bool:
    with _LOCK:
        conn = _conn()
        try:
            cur = conn.execute("DELETE FROM story WHERE id = ?", (story_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def list_all_stories(limit: int = 200) -> list[dict[str, Any]]:
    """Local single-user product: stories belong to the user, not to one
    resume rebuild, so they survive a new candidate_id."""
    rows = _read("SELECT * FROM story ORDER BY updated_at DESC LIMIT ?", (limit,))
    return [dict(row) for row in rows]


def list_stories(candidate_id: str, limit: int = 50) -> list[dict[str, Any]]:
    rows = _read(
        "SELECT * FROM story WHERE candidate_id = ? ORDER BY updated_at DESC LIMIT ?",
        (candidate_id, limit),
    )
    return [dict(row) for row in rows]


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


# ---------------------------------------------------------------------------
# R2 claim axes (provenance / user assertion are independent columns)
# ---------------------------------------------------------------------------

def update_claim_axes(
    claim_id: str,
    *,
    provenance_status: Optional[str] = None,
    user_assertion_status: Optional[str] = None,
    structured: Optional[dict[str, Any]] = None,
    source_ids: Optional[list[str]] = None,
) -> bool:
    sets: list[str] = ["updated_at = ?"]
    params: list[Any] = [time.time()]
    if provenance_status is not None:
        sets.append("provenance_status = ?")
        params.append(provenance_status)
    if user_assertion_status is not None:
        sets.append("user_assertion_status = ?")
        params.append(user_assertion_status)
    if structured is not None:
        sets.append("structured_json = ?")
        params.append(json.dumps(structured, ensure_ascii=False))
    if source_ids is not None:
        sets.append("source_ids_json = ?")
        params.append(json.dumps(source_ids, ensure_ascii=False))
    params.append(claim_id)
    with _LOCK:
        conn = _conn()
        try:
            cur = conn.execute(f"UPDATE claim SET {', '.join(sets)} WHERE id = ?", tuple(params))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def claim_evidence_ids(claim_id: str) -> list[str]:
    rows = _read("SELECT evidence_id FROM claim_evidence WHERE claim_id = ?", (claim_id,))
    return [str(row["evidence_id"]) for row in rows]


def delete_claim(claim_id: str) -> bool:
    with _LOCK:
        conn = _conn()
        try:
            conn.execute("DELETE FROM claim_evidence WHERE claim_id = ?", (claim_id,))
            cur = conn.execute("DELETE FROM claim WHERE id = ?", (claim_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# InterviewPack (immutable rows; a revision is a new row)
# ---------------------------------------------------------------------------

def insert_interview_pack(fields: dict[str, Any]) -> None:
    _write(
        "INSERT INTO interview_pack (id, pack_group_id, session_id, revision, parent_id, job_id, pack_json, content_hash, reason, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            fields["id"],
            fields["pack_group_id"],
            fields["session_id"],
            int(fields.get("revision", 1)),
            fields.get("parent_id", ""),
            fields.get("job_id", ""),
            fields["pack_json"],
            fields["content_hash"],
            fields.get("reason", ""),
            float(fields.get("created_at") or time.time()),
        ),
    )


def _pack_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    try:
        data["pack"] = json.loads(data.pop("pack_json"))
    except (json.JSONDecodeError, TypeError):
        data["pack"] = {}
    return data


def latest_interview_pack(session_id: str) -> Optional[dict[str, Any]]:
    rows = _read(
        "SELECT * FROM interview_pack WHERE session_id = ? ORDER BY revision DESC, created_at DESC LIMIT 1",
        (session_id,),
    )
    return _pack_row(rows[0]) if rows else None


def get_interview_pack(pack_id: str) -> Optional[dict[str, Any]]:
    rows = _read("SELECT * FROM interview_pack WHERE id = ?", (pack_id,))
    return _pack_row(rows[0]) if rows else None


def list_interview_pack_revisions(session_id: str) -> list[dict[str, Any]]:
    rows = _read(
        "SELECT id, pack_group_id, session_id, revision, parent_id, job_id, content_hash, reason, created_at "
        "FROM interview_pack WHERE session_id = ? ORDER BY revision ASC",
        (session_id,),
    )
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Session claims (said aloud this session; never long-term facts by themselves)
# ---------------------------------------------------------------------------

def upsert_session_claim(fields: dict[str, Any]) -> None:
    now = time.time()
    _write(
        "INSERT INTO session_claim (id, session_id, pack_id, text, normalized, session_status, provenance_status, review_state, qa_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET text=excluded.text, session_status=excluded.session_status, "
        "provenance_status=excluded.provenance_status, review_state=excluded.review_state, updated_at=excluded.updated_at",
        (
            fields["id"],
            fields["session_id"],
            fields.get("pack_id", ""),
            fields["text"],
            fields["normalized"],
            fields.get("session_status", "SESSION_STATED"),
            fields.get("provenance_status", "NO_EVIDENCE"),
            fields.get("review_state", "PENDING"),
            fields.get("qa_id", ""),
            now,
            now,
        ),
    )


def list_session_claims(session_id: str) -> list[dict[str, Any]]:
    rows = _read("SELECT * FROM session_claim WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
    return [dict(row) for row in rows]


def get_session_claim(claim_id: str) -> Optional[dict[str, Any]]:
    rows = _read("SELECT * FROM session_claim WHERE id = ?", (claim_id,))
    return dict(rows[0]) if rows else None


# ---------------------------------------------------------------------------
# Turn trace (Review 2.0)
# ---------------------------------------------------------------------------

def save_turn_trace(qa_id: str, session_id: str, pack_id: str, payload: dict[str, Any]) -> None:
    _write(
        "INSERT OR REPLACE INTO turn_trace (qa_id, session_id, pack_id, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (qa_id, session_id, pack_id, json.dumps(payload, ensure_ascii=False, default=str), time.time()),
    )


def get_turn_traces(qa_ids: list[str]) -> dict[str, dict[str, Any]]:
    ids = [str(q) for q in qa_ids if q]
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = _read(f"SELECT * FROM turn_trace WHERE qa_id IN ({placeholders})", tuple(ids))
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            out[row["qa_id"]] = {**json.loads(row["payload_json"] or "{}"), "session_id": row["session_id"], "pack_id": row["pack_id"]}
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def list_session_claims_by_qa(qa_ids: list[str]) -> list[dict[str, Any]]:
    ids = [str(q) for q in qa_ids if q]
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = _read(f"SELECT * FROM session_claim WHERE qa_id IN ({placeholders}) ORDER BY created_at ASC", tuple(ids))
    return [dict(row) for row in rows]


init_db()
