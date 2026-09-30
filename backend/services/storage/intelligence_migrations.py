"""Versioned migrations for the Intelligence storage layer.

 INVARIANT:
  - Migrations are additive-only and idempotent; existing user data in other
    databases is never touched (intelligence.db is a fresh file).
  - Schema version is tracked in ``PRAGMA user_version``; every migration step
    records its id/name/applied_at in ``schema_migrations`` for traceability.
  - Fresh installs bootstrap to the latest version in one pass; old installs
    upgrade stepwise. Rollback = restore the intelligence.db backup taken
    before upgrade (see storage/intelligence.py:backup_database).
"""
from __future__ import annotations

import sqlite3
from typing import Callable

from core.logger import get_logger

_log = get_logger("storage.intelligence_migrations")

LATEST_SCHEMA_VERSION = 3

# Step 1: initial Intelligence Core schema (master doc section 32).
_V1_TABLES: tuple[str, ...] = (
    # --- candidate representation ---
    """
    CREATE TABLE IF NOT EXISTS candidate_profile (
        id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL DEFAULT '',
        resume_history_id INTEGER,
        profile_text TEXT NOT NULL DEFAULT '',
        schema_version INTEGER NOT NULL DEFAULT 1,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS experience (
        id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'work',
        title TEXT NOT NULL DEFAULT '',
        organization TEXT NOT NULL DEFAULT '',
        period TEXT NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '',
        truth_status TEXT NOT NULL DEFAULT 'SUPPORTED',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project (
        id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL,
        name TEXT NOT NULL,
        summary TEXT NOT NULL DEFAULT '',
        period TEXT NOT NULL DEFAULT '',
        truth_status TEXT NOT NULL DEFAULT 'SUPPORTED',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS claim (
        id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'fact',
        text TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'resume',
        truth_status TEXT NOT NULL DEFAULT 'SUPPORTED',
        confidence REAL NOT NULL DEFAULT 0.5,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evidence (
        id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'resume',
        text TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS claim_evidence (
        claim_id TEXT NOT NULL,
        evidence_id TEXT NOT NULL,
        created_at REAL NOT NULL,
        PRIMARY KEY (claim_id, evidence_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS skill (
        id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL,
        name TEXT NOT NULL,
        level TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL DEFAULT 'resume',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS story (
        id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL,
        title TEXT NOT NULL,
        situation TEXT NOT NULL DEFAULT '',
        challenge TEXT NOT NULL DEFAULT '',
        action TEXT NOT NULL DEFAULT '',
        result TEXT NOT NULL DEFAULT '',
        reflection TEXT NOT NULL DEFAULT '',
        tags_json TEXT NOT NULL DEFAULT '[]',
        truth_status TEXT NOT NULL DEFAULT 'SUPPORTED',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    # --- job representation ---
    """
    CREATE TABLE IF NOT EXISTS job_profile (
        id TEXT PRIMARY KEY,
        company TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL DEFAULT '',
        level TEXT NOT NULL DEFAULT '',
        jd_text TEXT NOT NULL DEFAULT '',
        responsibilities_json TEXT NOT NULL DEFAULT '[]',
        must_have_json TEXT NOT NULL DEFAULT '[]',
        nice_to_have_json TEXT NOT NULL DEFAULT '[]',
        technologies_json TEXT NOT NULL DEFAULT '[]',
        competencies_json TEXT NOT NULL DEFAULT '[]',
        likely_dimensions_json TEXT NOT NULL DEFAULT '[]',
        alignment_json TEXT NOT NULL DEFAULT '{}',
        schema_version INTEGER NOT NULL DEFAULT 1,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS candidate_job_alignment (
        id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL,
        requirement_text TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'UNKNOWN',
        evidence_claim_ids_json TEXT NOT NULL DEFAULT '[]',
        explanation TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    # --- interview state ---
    """
    CREATE TABLE IF NOT EXISTS interview_session (
        id TEXT PRIMARY KEY,
        external_session_id TEXT,
        phase TEXT NOT NULL DEFAULT 'opening',
        ai_policy_mode TEXT NOT NULL DEFAULT 'AI_ALLOWED',
        started_at REAL NOT NULL,
        ended_at REAL,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS interview_turn (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        seq INTEGER NOT NULL,
        question_raw TEXT NOT NULL DEFAULT '',
        question_resolved TEXT NOT NULL DEFAULT '',
        question_type TEXT NOT NULL DEFAULT '',
        route TEXT NOT NULL DEFAULT '',
        guidance_text TEXT NOT NULL DEFAULT '',
        truth_flags_json TEXT NOT NULL DEFAULT '[]',
        latency_ms INTEGER NOT NULL DEFAULT 0,
        created_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS interview_state_snapshot (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        state_json TEXT NOT NULL,
        created_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS guidance_event (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        event TEXT NOT NULL,
        route TEXT NOT NULL DEFAULT '',
        provider TEXT NOT NULL DEFAULT '',
        model TEXT NOT NULL DEFAULT '',
        latency_ms INTEGER NOT NULL DEFAULT 0,
        tokens_json TEXT NOT NULL DEFAULT '{}',
        context_ids_json TEXT NOT NULL DEFAULT '[]',
        truth_flags_json TEXT NOT NULL DEFAULT '[]',
        created_at REAL NOT NULL
    )
    """,
    # --- memory / voice ---
    """
    CREATE TABLE IF NOT EXISTS memory_item (
        id TEXT PRIMARY KEY,
        candidate_id TEXT,
        session_id TEXT,
        kind TEXT NOT NULL,
        text TEXT NOT NULL,
        confirmations INTEGER NOT NULL DEFAULT 1,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS voice_profile (
        id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL,
        profile_json TEXT NOT NULL DEFAULT '{}',
        sample_count INTEGER NOT NULL DEFAULT 0,
        enabled INTEGER NOT NULL DEFAULT 0,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
)

_V1_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_claim_candidate ON claim(candidate_id)",
    "CREATE INDEX IF NOT EXISTS idx_evidence_candidate ON evidence(candidate_id)",
    "CREATE INDEX IF NOT EXISTS idx_turn_session ON interview_turn(session_id, seq)",
    "CREATE INDEX IF NOT EXISTS idx_state_snapshot_session ON interview_state_snapshot(session_id, version)",
    "CREATE INDEX IF NOT EXISTS idx_guidance_event_session ON guidance_event(session_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_memory_kind ON memory_item(kind)",
)

def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _migrate_v2(conn: sqlite3.Connection) -> None:
    """R2: three-axis claim semantics, frozen InterviewPack, session claims.

    Backfill maps the legacy single-axis truth_status:
      SUPPORTED (resume action line)   -> DIRECT_EVIDENCE
      INFERRED  (熟悉/了解 self-rating)  -> SUPPORTING_EVIDENCE
      VERIFIED  (user clicked confirm) -> USER_CONFIRMED + DIRECT/NO by evidence link
      CONTRADICTED -> CONFLICTING_EVIDENCE, UNKNOWN -> NO_EVIDENCE
    The old column is kept (read-only) so a downgrade still opens the file.
    """
    existing = _column_names(conn, "claim")
    additions = {
        "provenance_status": "TEXT NOT NULL DEFAULT 'NO_EVIDENCE'",
        "user_assertion_status": "TEXT NOT NULL DEFAULT 'UNREVIEWED'",
        "structured_json": "TEXT NOT NULL DEFAULT '{}'",
        "source_ids_json": "TEXT NOT NULL DEFAULT '[]'",
    }
    for column, ddl in additions.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE claim ADD COLUMN {column} {ddl}")
    conn.execute(
        "UPDATE claim SET provenance_status = CASE truth_status "
        "WHEN 'SUPPORTED' THEN 'DIRECT_EVIDENCE' "
        "WHEN 'INFERRED' THEN 'SUPPORTING_EVIDENCE' "
        "WHEN 'CONTRADICTED' THEN 'CONFLICTING_EVIDENCE' "
        "WHEN 'VERIFIED' THEN CASE WHEN EXISTS (SELECT 1 FROM claim_evidence ce WHERE ce.claim_id = claim.id) "
        "THEN 'DIRECT_EVIDENCE' ELSE 'NO_EVIDENCE' END "
        "ELSE 'NO_EVIDENCE' END"
    )
    conn.execute("UPDATE claim SET user_assertion_status = 'USER_CONFIRMED' WHERE truth_status = 'VERIFIED'")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS interview_pack (
            id TEXT PRIMARY KEY,
            pack_group_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            revision INTEGER NOT NULL DEFAULT 1,
            parent_id TEXT NOT NULL DEFAULT '',
            job_id TEXT NOT NULL DEFAULT '',
            pack_json TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pack_session ON interview_pack(session_id, revision)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_claim (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            pack_id TEXT NOT NULL DEFAULT '',
            text TEXT NOT NULL,
            normalized TEXT NOT NULL,
            session_status TEXT NOT NULL DEFAULT 'SESSION_STATED',
            provenance_status TEXT NOT NULL DEFAULT 'NO_EVIDENCE',
            review_state TEXT NOT NULL DEFAULT 'PENDING',
            qa_id TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_session_claim_session ON session_claim(session_id)")


def _migrate_v3(conn: sqlite3.Connection) -> None:
    """R2 Review 2.0: one trace row per answered turn (what the candidate saw)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS turn_trace (
            qa_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            pack_id TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_turn_trace_session ON turn_trace(session_id, created_at)")


_MIGRATIONS: dict[int, tuple[Callable[[sqlite3.Connection], None], str]] = {
    1: (lambda conn: _apply_statements(conn, _V1_TABLES + _V1_INDEXES), "initial intelligence core schema"),
    2: (_migrate_v2, "r2 provenance axes, interview pack, session claims"),
    3: (_migrate_v3, "r2 turn trace for review 2.0"),
}


def _apply_statements(conn: sqlite3.Connection, statements: tuple[str, ...]) -> None:
    for statement in statements:
        conn.execute(statement)


def ensure_schema(conn: sqlite3.Connection) -> int:
    """Bring an intelligence.db connection to LATEST_SCHEMA_VERSION.

    Returns the version before this call so callers can log upgrades.
    Idempotent: re-running on an up-to-date database is a no-op.
    """
    before = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if before >= LATEST_SCHEMA_VERSION:
        return before
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at REAL NOT NULL)"
    )
    import time

    for version in sorted(_MIGRATIONS):
        if version <= before:
            continue
        apply_step, name = _MIGRATIONS[version]
        apply_step(conn)
        conn.execute(
            "INSERT OR REPLACE INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (version, name, time.time()),
        )
        conn.execute(f"PRAGMA user_version = {int(version)}")
        _log.info("intelligence migration applied: v%s %s", version, name)
    conn.commit()
    return before
