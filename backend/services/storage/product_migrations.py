"""Versioned schema for product.db (v1.3 Goal-centered product layer).

 COMPATIBILITY:
  - product.db is a new file. The v1.2 Verified Core databases
    (intelligence / prep / review / job_tracker / kb / knowledge) are never
    altered by these migrations; product rows only *reference* their ids.
  - Every step is additive and idempotent (CREATE ... IF NOT EXISTS,
    ALTER ... ADD COLUMN guarded by PRAGMA table_info), tracked by
    PRAGMA user_version + schema_migrations like intelligence_migrations.
  - Rollback plan: product.db is backed up before any upgrade
    (product.backup_database); deleting product.db returns the app to v1.2
    behaviour with no loss of v1.2 data.
"""
from __future__ import annotations

import sqlite3
import time
from typing import Callable

from core.logger import get_logger

_log = get_logger("storage.product_migrations")

LATEST_SCHEMA_VERSION = 9

_V1_TABLES: tuple[str, ...] = (
    # --- Goal (long-lived job target) ---
    """
    CREATE TABLE IF NOT EXISTS goal (
        id TEXT PRIMARY KEY,
        company TEXT NOT NULL DEFAULT '',
        role TEXT NOT NULL DEFAULT '',
        jd TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        stage TEXT NOT NULL DEFAULT '',
        next_interview_at REAL,
        interview_round TEXT NOT NULL DEFAULT '',
        goal_notes TEXT NOT NULL DEFAULT '',
        selected_resume_id INTEGER,
        selected_material_ids_json TEXT NOT NULL DEFAULT '[]',
        selected_kb_ids_json TEXT NOT NULL DEFAULT '[]',
        selected_quick_note_ids_json TEXT NOT NULL DEFAULT '[]',
        active_question_bank_ids_json TEXT NOT NULL DEFAULT '[]',
        next_focus_id TEXT NOT NULL DEFAULT '',
        offer_state TEXT NOT NULL DEFAULT 'NONE',
        role_family TEXT NOT NULL DEFAULT '',
        legacy_prep_space_id INTEGER,
        application_id INTEGER,
        job_profile_id TEXT NOT NULL DEFAULT '',
        settings_json TEXT NOT NULL DEFAULT '{}',
        last_opened_at REAL,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS goal_material (
        id TEXT PRIMARY KEY,
        goal_id TEXT NOT NULL REFERENCES goal(id) ON DELETE CASCADE,
        material_id TEXT NOT NULL,
        created_at REAL NOT NULL,
        UNIQUE(goal_id, material_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS goal_interview (
        id TEXT PRIMARY KEY,
        goal_id TEXT NOT NULL REFERENCES goal(id) ON DELETE CASCADE,
        round TEXT NOT NULL DEFAULT '',
        kind TEXT NOT NULL DEFAULT 'REAL',
        status TEXT NOT NULL DEFAULT 'UPCOMING',
        scheduled_at REAL,
        notes TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS goal_offer (
        goal_id TEXT PRIMARY KEY REFERENCES goal(id) ON DELETE CASCADE,
        status TEXT NOT NULL DEFAULT 'NONE',
        comp TEXT NOT NULL DEFAULT '',
        deadline REAL,
        notes TEXT NOT NULL DEFAULT '',
        updated_at REAL NOT NULL
    )
    """,
    # Sessions are never copied: a link row points at the owning store
    # (review_sessions for real/practice reflections, practice_session here).
    """
    CREATE TABLE IF NOT EXISTS goal_session_link (
        id TEXT PRIMARY KEY,
        goal_id TEXT NOT NULL REFERENCES goal(id) ON DELETE CASCADE,
        session_kind TEXT NOT NULL,
        review_session_id INTEGER,
        practice_id TEXT NOT NULL DEFAULT '',
        live_session_id TEXT NOT NULL DEFAULT '',
        goal_interview_id TEXT NOT NULL DEFAULT '',
        round TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL
    )
    """,
    # --- Materials + lifecycle ---
    """
    CREATE TABLE IF NOT EXISTS material (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL DEFAULT 'PROJECT',
        usage TEXT NOT NULL DEFAULT 'FACTS',
        title TEXT NOT NULL DEFAULT '',
        active_version_id TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS material_version (
        id TEXT PRIMARY KEY,
        material_id TEXT NOT NULL REFERENCES material(id) ON DELETE CASCADE,
        version INTEGER NOT NULL,
        filename TEXT NOT NULL DEFAULT '',
        content_text TEXT NOT NULL DEFAULT '',
        content_hash TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'PROCESSING',
        error TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    # --- Quick Notes ---
    """
    CREATE TABLE IF NOT EXISTS quick_note (
        id TEXT PRIMARY KEY,
        scope TEXT NOT NULL DEFAULT 'GLOBAL',
        goal_id TEXT,
        title TEXT NOT NULL DEFAULT '',
        content TEXT NOT NULL DEFAULT '',
        pinned INTEGER NOT NULL DEFAULT 0,
        sort_order INTEGER NOT NULL DEFAULT 0,
        tags_json TEXT NOT NULL DEFAULT '[]',
        revision INTEGER NOT NULL DEFAULT 1,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    # --- Question banks ---
    """
    CREATE TABLE IF NOT EXISTS question_bank (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        scope TEXT NOT NULL DEFAULT 'USER',
        role TEXT NOT NULL DEFAULT '',
        company TEXT NOT NULL DEFAULT '',
        source_type TEXT NOT NULL DEFAULT 'USER_ADDED',
        goal_id TEXT,
        builtin INTEGER NOT NULL DEFAULT 0,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS question_bank_item (
        id TEXT PRIMARY KEY,
        bank_id TEXT NOT NULL REFERENCES question_bank(id) ON DELETE CASCADE,
        text TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT '',
        difficulty TEXT NOT NULL DEFAULT 'STANDARD',
        origin TEXT NOT NULL DEFAULT 'USER_ADDED',
        source_url TEXT NOT NULL DEFAULT '',
        rounds_json TEXT NOT NULL DEFAULT '[]',
        created_at REAL NOT NULL
    )
    """,
    # --- Practice 3.0 ---
    """
    CREATE TABLE IF NOT EXISTS practice_profile (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        config_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS practice_session (
        id TEXT PRIMARY KEY,
        goal_id TEXT,
        config_json TEXT NOT NULL DEFAULT '{}',
        state_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        review_session_id INTEGER,
        guided INTEGER NOT NULL DEFAULT 0,
        started_at REAL NOT NULL,
        ended_at REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS practice_turn (
        id TEXT PRIMARY KEY,
        practice_id TEXT NOT NULL REFERENCES practice_session(id) ON DELETE CASCADE,
        seq INTEGER NOT NULL,
        persona_id TEXT NOT NULL DEFAULT '',
        move TEXT NOT NULL DEFAULT 'OPEN',
        question TEXT NOT NULL,
        question_source TEXT NOT NULL DEFAULT '',
        answer TEXT NOT NULL DEFAULT '',
        answer_duration_ms INTEGER,
        content_json TEXT NOT NULL DEFAULT '{}',
        delivery_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL,
        answered_at REAL
    )
    """,
    # Per-dimension rubric observations feed ProgressTrend (derived, not stored).
    """
    CREATE TABLE IF NOT EXISTS rubric_observation (
        id TEXT PRIMARY KEY,
        goal_id TEXT,
        session_kind TEXT NOT NULL,
        session_ref TEXT NOT NULL,
        turn_ref TEXT NOT NULL DEFAULT '',
        dimension TEXT NOT NULL,
        level INTEGER NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS delivery_metrics (
        id TEXT PRIMARY KEY,
        session_kind TEXT NOT NULL,
        session_ref TEXT NOT NULL,
        turn_ref TEXT NOT NULL DEFAULT '',
        goal_id TEXT,
        metrics_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL
    )
    """,
    # --- Live: pins, nudges, closing ---
    """
    CREATE TABLE IF NOT EXISTS pin_moment (
        id TEXT PRIMARY KEY,
        session_kind TEXT NOT NULL DEFAULT 'LIVE',
        session_id TEXT NOT NULL,
        turn_id TEXT NOT NULL DEFAULT '',
        goal_id TEXT,
        tag TEXT NOT NULL DEFAULT 'IMPORTANT',
        question TEXT NOT NULL DEFAULT '',
        transcript_excerpt TEXT NOT NULL DEFAULT '',
        note TEXT NOT NULL DEFAULT '',
        ts REAL NOT NULL,
        used_in_reflection INTEGER NOT NULL DEFAULT 0,
        created_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS nudge_event (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        text TEXT NOT NULL DEFAULT '',
        topic_key TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'SHOWN',
        reason TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS closing_mode_event (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        trigger TEXT NOT NULL DEFAULT 'INTERVIEW_CLOSING',
        suggestions_json TEXT NOT NULL DEFAULT '[]',
        created_at REAL NOT NULL
    )
    """,
    # --- Reflection + Next Focus ---
    """
    CREATE TABLE IF NOT EXISTS next_focus (
        id TEXT PRIMARY KEY,
        goal_id TEXT NOT NULL REFERENCES goal(id) ON DELETE CASCADE,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        topic_key TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        source_kind TEXT NOT NULL DEFAULT '',
        source_ref TEXT NOT NULL DEFAULT '',
        actions_json TEXT NOT NULL DEFAULT '[]',
        priority INTEGER NOT NULL DEFAULT 50,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        origin TEXT NOT NULL DEFAULT 'DERIVED',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reflection_action (
        id TEXT PRIMARY KEY,
        goal_id TEXT,
        session_kind TEXT NOT NULL DEFAULT '',
        session_ref TEXT NOT NULL DEFAULT '',
        finding_id TEXT NOT NULL DEFAULT '',
        finding_kind TEXT NOT NULL DEFAULT '',
        action TEXT NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        result_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL
    )
    """,
    # --- Settings layering (Global / Goal / Session) ---
    """
    CREATE TABLE IF NOT EXISTS setting_override (
        scope TEXT NOT NULL,
        scope_id TEXT NOT NULL DEFAULT '',
        key TEXT NOT NULL,
        value_json TEXT NOT NULL,
        updated_at REAL NOT NULL,
        PRIMARY KEY(scope, scope_id, key)
    )
    """,
    # --- v1.4 local product analytics ---
    """
    CREATE TABLE IF NOT EXISTS product_event (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        ts REAL NOT NULL,
        goal_id TEXT NOT NULL DEFAULT '',
        session_id TEXT NOT NULL DEFAULT '',
        props_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS session_feedback (
        id TEXT PRIMARY KEY,
        session_kind TEXT NOT NULL,
        session_ref TEXT NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        created_at REAL NOT NULL,
        UNIQUE(session_kind, session_ref, question)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS product_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
)

_V1_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_goal_status ON goal(status, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_goal_interview_goal ON goal_interview(goal_id, scheduled_at)",
    "CREATE INDEX IF NOT EXISTS idx_goal_session_goal ON goal_session_link(goal_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_goal_session_review ON goal_session_link(review_session_id)",
    "CREATE INDEX IF NOT EXISTS idx_material_version ON material_version(material_id, version)",
    "CREATE INDEX IF NOT EXISTS idx_quick_note_scope ON quick_note(scope, goal_id, sort_order)",
    "CREATE INDEX IF NOT EXISTS idx_bank_item_bank ON question_bank_item(bank_id)",
    "CREATE INDEX IF NOT EXISTS idx_practice_goal ON practice_session(goal_id, started_at)",
    "CREATE INDEX IF NOT EXISTS idx_practice_turn ON practice_turn(practice_id, seq)",
    "CREATE INDEX IF NOT EXISTS idx_rubric_goal ON rubric_observation(goal_id, dimension, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_pin_session ON pin_moment(session_id, ts)",
    "CREATE INDEX IF NOT EXISTS idx_nudge_session ON nudge_event(session_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_next_focus_goal ON next_focus(goal_id, status, priority)",
    "CREATE INDEX IF NOT EXISTS idx_reflection_action_goal ON reflection_action(goal_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_product_event_name ON product_event(name, ts)",
    "CREATE INDEX IF NOT EXISTS idx_product_event_goal ON product_event(goal_id, ts)",
)



# --- v2.0 Personal Conversation Intelligence (additive; v1 tables untouched) ---
_V2_TABLES: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS conversation_space (
        id TEXT PRIMARY KEY,
        profile TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        project_id TEXT NOT NULL DEFAULT '',
        relationship_key TEXT NOT NULL DEFAULT '',
        default_goal TEXT NOT NULL DEFAULT '',
        default_mode TEXT NOT NULL DEFAULT 'BALANCED',
        selected_source_ids_json TEXT NOT NULL DEFAULT '[]',
        selected_quick_note_ids_json TEXT NOT NULL DEFAULT '[]',
        retention_policy_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_goal (
        id TEXT PRIMARY KEY,
        space_id TEXT NOT NULL REFERENCES conversation_space(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        outcome_definition TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        priority INTEGER NOT NULL DEFAULT 50,
        source_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL,
        resolved_at REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_session (
        id TEXT PRIMARY KEY,
        space_id TEXT NOT NULL REFERENCES conversation_space(id) ON DELETE CASCADE,
        goal_ids_json TEXT NOT NULL DEFAULT '[]',
        template TEXT NOT NULL DEFAULT 'PROJECT_SYNC',
        title TEXT NOT NULL DEFAULT '',
        scheduled_at REAL,
        started_at REAL,
        ended_at REAL,
        capture_mode TEXT NOT NULL DEFAULT 'NOTES_ONLY',
        processing_mode TEXT NOT NULL DEFAULT 'LOCAL',
        assistance_mode TEXT NOT NULL DEFAULT 'BALANCED',
        consent_ack INTEGER NOT NULL DEFAULT 0,
        pack_id TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'UPCOMING',
        state_json TEXT NOT NULL DEFAULT '{}',
        source_calendar_event_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_session_pack (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL UNIQUE REFERENCES conversation_session(id) ON DELETE CASCADE,
        space_id TEXT NOT NULL REFERENCES conversation_space(id) ON DELETE CASCADE,
        payload_json TEXT NOT NULL,
        digest TEXT NOT NULL,
        created_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_participant (
        id TEXT PRIMARY KEY,
        space_id TEXT NOT NULL REFERENCES conversation_space(id) ON DELETE CASCADE,
        session_id TEXT,
        display_name TEXT NOT NULL DEFAULT '',
        role TEXT NOT NULL DEFAULT '',
        organization TEXT NOT NULL DEFAULT '',
        identity_confidence REAL NOT NULL DEFAULT 0,
        identity_source TEXT NOT NULL DEFAULT '',
        visibility TEXT NOT NULL DEFAULT 'PRIVATE',
        observations_json TEXT NOT NULL DEFAULT '[]',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_item (
        id TEXT PRIMARY KEY,
        space_id TEXT NOT NULL REFERENCES conversation_space(id) ON DELETE CASCADE,
        session_id TEXT NOT NULL REFERENCES conversation_session(id) ON DELETE CASCADE,
        type TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'PROPOSED',
        title TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT '',
        speaker_id TEXT NOT NULL DEFAULT '',
        owner_id TEXT NOT NULL DEFAULT '',
        due_at TEXT NOT NULL DEFAULT '',
        source_refs_json TEXT NOT NULL DEFAULT '[]',
        source_excerpt TEXT NOT NULL DEFAULT '',
        confidence REAL NOT NULL DEFAULT 0,
        epistemic_status TEXT NOT NULL DEFAULT 'UNKNOWN',
        review_status TEXT NOT NULL DEFAULT 'AI_EXTRACTED',
        supersedes_id TEXT NOT NULL DEFAULT '',
        visibility TEXT NOT NULL DEFAULT 'PRIVATE',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_open_thread (
        id TEXT PRIMARY KEY,
        space_id TEXT NOT NULL REFERENCES conversation_space(id) ON DELETE CASCADE,
        session_id TEXT,
        kind TEXT NOT NULL DEFAULT 'OPEN_QUESTION',
        text TEXT NOT NULL,
        owner_id TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'OPEN',
        source_refs_json TEXT NOT NULL DEFAULT '[]',
        created_at REAL NOT NULL,
        resolved_at REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_guidance_event (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES conversation_session(id) ON DELETE CASCADE,
        candidate_id TEXT NOT NULL DEFAULT '',
        kind TEXT NOT NULL,
        expression_action TEXT NOT NULL,
        text TEXT NOT NULL DEFAULT '',
        source_refs_json TEXT NOT NULL DEFAULT '[]',
        status TEXT NOT NULL DEFAULT 'SHOWN',
        reason TEXT NOT NULL DEFAULT '',
        score_json TEXT NOT NULL DEFAULT '{}',
        user_action TEXT NOT NULL DEFAULT 'NONE',
        rendered_at REAL,
        created_at REAL NOT NULL
    )
    """,
)

_V2_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_conversation_space_status ON conversation_space(status, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_goal_space ON conversation_goal(space_id, status, priority)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_session_space ON conversation_session(space_id, scheduled_at, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_session_status ON conversation_session(status, scheduled_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_participant_space ON conversation_participant(space_id, session_id)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_item_space ON conversation_item(space_id, type, state, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_item_session ON conversation_item(session_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_thread_space ON conversation_open_thread(space_id, status, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_guidance_session ON conversation_guidance_event(session_id, created_at)",
)

# --- v2.0 runtime closure: post-core additive tables ---
# Kept as a separate migration because early v2 development builds may already
# have PRAGMA user_version=2. Never silently assume those databases rerun v2.
_V3_TABLES: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS conversation_draft_action (
        id TEXT PRIMARY KEY,
        space_id TEXT NOT NULL REFERENCES conversation_space(id) ON DELETE CASCADE,
        session_id TEXT REFERENCES conversation_session(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        content TEXT NOT NULL DEFAULT '',
        target TEXT NOT NULL DEFAULT '',
        payload_json TEXT NOT NULL DEFAULT '{}',
        source_refs_json TEXT NOT NULL DEFAULT '[]',
        status TEXT NOT NULL DEFAULT 'DRAFT',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_transcript_segment (
        id TEXT PRIMARY KEY,
        space_id TEXT NOT NULL REFERENCES conversation_space(id) ON DELETE CASCADE,
        session_id TEXT NOT NULL REFERENCES conversation_session(id) ON DELETE CASCADE,
        channel TEXT NOT NULL,
        text TEXT NOT NULL,
        provider TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL DEFAULT '',
        is_final INTEGER NOT NULL DEFAULT 1,
        created_at REAL NOT NULL
    )
    """,
)

_V3_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_conversation_draft_space ON conversation_draft_action(space_id, status, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_transcript_session ON conversation_transcript_segment(session_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_transcript_space ON conversation_transcript_segment(space_id, created_at)",
)

# --- v2.0 lifecycle closure: deletion provenance ---
_V4_TABLES: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS conversation_provenance_tombstone (
        id TEXT PRIMARY KEY,
        original_item_id TEXT NOT NULL,
        space_id TEXT NOT NULL REFERENCES conversation_space(id) ON DELETE CASCADE,
        deleted_session_id TEXT NOT NULL,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        state TEXT NOT NULL,
        review_status TEXT NOT NULL,
        source_refs_json TEXT NOT NULL DEFAULT '[]',
        source_excerpt TEXT NOT NULL DEFAULT '',
        deleted_at REAL NOT NULL
    )
    """,
)

_V4_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_conversation_tombstone_space ON conversation_provenance_tombstone(space_id, deleted_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_tombstone_original ON conversation_provenance_tombstone(original_item_id)",
)

# --- v2.0 design closure: explicit session policy + safe counterparty state ---
# These remain JSON envelopes because the policy/state vocabularies evolve
# faster than the stable Conversation entities. Migration is additive and
# keeps existing v2 databases readable.
def _apply_v5(conn: sqlite3.Connection) -> None:
    session_cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(conversation_session)").fetchall()}
    if "policy_json" not in session_cols:
        conn.execute("ALTER TABLE conversation_session ADD COLUMN policy_json TEXT NOT NULL DEFAULT '{}'")

    participant_cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(conversation_participant)").fetchall()}
    if "counterparty_state_json" not in participant_cols:
        conn.execute("ALTER TABLE conversation_participant ADD COLUMN counterparty_state_json TEXT NOT NULL DEFAULT '{}'")


# --- v2.0 final design audit: explicit temporal provenance ---
def _apply_v6(conn: sqlite3.Connection) -> None:
    item_cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(conversation_item)").fetchall()}
    if "time_semantics_json" not in item_cols:
        conn.execute("ALTER TABLE conversation_item ADD COLUMN time_semantics_json TEXT NOT NULL DEFAULT '{}'")

# --- v2.0 beta productization: Conversation-owned manual screen observations ---
# Raw screenshots are never persisted.  Only extracted text plus one-way
# image/model-route provenance is retained as session-scoped observation state.
_V7_TABLES: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS conversation_screen_context (
        id TEXT PRIMARY KEY,
        space_id TEXT NOT NULL REFERENCES conversation_space(id) ON DELETE CASCADE,
        session_id TEXT NOT NULL REFERENCES conversation_session(id) ON DELETE CASCADE,
        capture_mode TEXT NOT NULL DEFAULT 'MANUAL',
        region TEXT NOT NULL DEFAULT '',
        text TEXT NOT NULL DEFAULT '',
        image_hash TEXT NOT NULL DEFAULT '',
        vision_model TEXT NOT NULL DEFAULT '',
        vision_route TEXT NOT NULL DEFAULT '',
        vision_fingerprint TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL DEFAULT 'LOCAL_SCREEN_CAPTURE',
        created_at REAL NOT NULL
    )
    """,
)

_V7_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_conversation_screen_session ON conversation_screen_context(session_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_screen_space ON conversation_screen_context(space_id, created_at)",
)

# --- v2.0 integration boundary: external snapshots + explicit execution audit ---
# Credentials/tokens are deliberately not stored here. credential_ref is only
# an opaque handle resolved by a provider adapter / OS secure store.
_V8_TABLES: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS conversation_connector_connection (
        id TEXT PRIMARY KEY,
        provider_id TEXT NOT NULL,
        display_name TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'DISCONNECTED',
        auth_mode TEXT NOT NULL DEFAULT 'NONE',
        credential_ref TEXT NOT NULL DEFAULT '',
        granted_capabilities_json TEXT NOT NULL DEFAULT '[]',
        provider_scopes_json TEXT NOT NULL DEFAULT '[]',
        account_hint TEXT NOT NULL DEFAULT '',
        sync_cursor TEXT NOT NULL DEFAULT '',
        last_sync_at REAL,
        last_error TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_connector_snapshot (
        id TEXT PRIMARY KEY,
        connection_id TEXT NOT NULL REFERENCES conversation_connector_connection(id) ON DELETE CASCADE,
        space_id TEXT NOT NULL REFERENCES conversation_space(id) ON DELETE CASCADE,
        capability TEXT NOT NULL,
        external_kind TEXT NOT NULL,
        external_id TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        excerpt TEXT NOT NULL DEFAULT '',
        content_hash TEXT NOT NULL,
        source_url TEXT NOT NULL DEFAULT '',
        occurred_at REAL,
        visibility TEXT NOT NULL DEFAULT 'PRIVATE',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL,
        UNIQUE(connection_id, capability, external_kind, external_id, content_hash)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_connector_execution (
        id TEXT PRIMARY KEY,
        draft_action_id TEXT NOT NULL REFERENCES conversation_draft_action(id) ON DELETE CASCADE,
        connection_id TEXT NOT NULL REFERENCES conversation_connector_connection(id) ON DELETE RESTRICT,
        capability TEXT NOT NULL,
        operation TEXT NOT NULL,
        target TEXT NOT NULL DEFAULT '',
        idempotency_key TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'PENDING',
        request_json TEXT NOT NULL DEFAULT '{}',
        response_json TEXT NOT NULL DEFAULT '{}',
        error TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        executed_at REAL
    )
    """,
)

_V8_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_conversation_connector_provider ON conversation_connector_connection(provider_id, status, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_connector_snapshot_space ON conversation_connector_snapshot(space_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_connector_snapshot_connection ON conversation_connector_snapshot(connection_id, occurred_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_connector_execution_draft ON conversation_connector_execution(draft_action_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_connector_execution_status ON conversation_connector_execution(status, updated_at)",
)


def _apply_v8(conn: sqlite3.Connection) -> None:
    _apply_statements(conn, _V8_TABLES + _V8_INDEXES)
    space_cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(conversation_space)").fetchall()}
    if "selected_connector_snapshot_ids_json" not in space_cols:
        conn.execute(
            "ALTER TABLE conversation_space ADD COLUMN selected_connector_snapshot_ids_json TEXT NOT NULL DEFAULT '[]'"
        )


def _apply_v9(conn: sqlite3.Connection) -> None:
    """Make immutable external snapshots Space-scoped.

    v8 stored space_id on the snapshot row but its UNIQUE constraint omitted
    space_id. The same unchanged provider object synced into two Conversation
    Spaces could therefore alias the first Space's row. Rebuild the beta-only
    table so provenance membership cannot cross Space boundaries.
    """
    conn.execute(
        """
        CREATE TABLE conversation_connector_snapshot_v9 (
            id TEXT PRIMARY KEY,
            connection_id TEXT NOT NULL REFERENCES conversation_connector_connection(id) ON DELETE CASCADE,
            space_id TEXT NOT NULL REFERENCES conversation_space(id) ON DELETE CASCADE,
            capability TEXT NOT NULL,
            external_kind TEXT NOT NULL,
            external_id TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            excerpt TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL,
            source_url TEXT NOT NULL DEFAULT '',
            occurred_at REAL,
            visibility TEXT NOT NULL DEFAULT 'PRIVATE',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL,
            UNIQUE(space_id, connection_id, capability, external_kind, external_id, content_hash)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO conversation_connector_snapshot_v9 (
            id, connection_id, space_id, capability, external_kind, external_id,
            title, excerpt, content_hash, source_url, occurred_at, visibility,
            metadata_json, created_at
        )
        SELECT
            id, connection_id, space_id, capability, external_kind, external_id,
            title, excerpt, content_hash, source_url, occurred_at, visibility,
            metadata_json, created_at
        FROM conversation_connector_snapshot
        """
    )
    conn.execute("DROP TABLE conversation_connector_snapshot")
    conn.execute("ALTER TABLE conversation_connector_snapshot_v9 RENAME TO conversation_connector_snapshot")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversation_connector_snapshot_space "
        "ON conversation_connector_snapshot(space_id, created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversation_connector_snapshot_connection "
        "ON conversation_connector_snapshot(connection_id, occurred_at)"
    )


def _apply_statements(conn: sqlite3.Connection, statements: tuple[str, ...]) -> None:
    for statement in statements:
        conn.execute(statement)


_MIGRATIONS: dict[int, tuple[Callable[[sqlite3.Connection], None], str]] = {
    1: (lambda conn: _apply_statements(conn, _V1_TABLES + _V1_INDEXES), "v1.3 goal-centered product layer"),
    2: (lambda conn: _apply_statements(conn, _V2_TABLES + _V2_INDEXES), "v2.0 personal conversation intelligence"),
    3: (lambda conn: _apply_statements(conn, _V3_TABLES + _V3_INDEXES), "v2.0 conversation runtime closure"),
    4: (lambda conn: _apply_statements(conn, _V4_TABLES + _V4_INDEXES), "v2.0 deletion provenance tombstones"),
    5: (_apply_v5, "v2.0 explicit session policy and counterparty state"),
    6: (_apply_v6, "v2.0 temporal provenance for conversation items"),
    7: (lambda conn: _apply_statements(conn, _V7_TABLES + _V7_INDEXES), "v2.0 manual Conversation screen context observations"),
    8: (_apply_v8, "v2.0 external connector snapshots and reviewed execution audit"),
    9: (_apply_v9, "v2.0 Space-scoped immutable connector snapshot provenance"),
}


def ensure_schema(conn: sqlite3.Connection) -> int:
    """Bring product.db to LATEST_SCHEMA_VERSION; returns the version before."""
    before = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if before >= LATEST_SCHEMA_VERSION:
        return before
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at REAL NOT NULL)"
    )
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
        _log.info("product migration applied: v%s %s", version, name)
    conn.commit()
    return before
