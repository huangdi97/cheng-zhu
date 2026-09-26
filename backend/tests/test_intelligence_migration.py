"""Migration tests for the Intelligence storage (canonical Stage O).

 INVARIANT:
  - Fresh installs bootstrap to the latest schema version in one pass.
  - Re-running migrations is idempotent; existing data is never lost.
  - Backups are taken before upgrade and can be restored for rollback.
"""
import sqlite3

import pytest

from services.storage import intelligence as intel
from services.storage.intelligence_migrations import LATEST_SCHEMA_VERSION


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "intelligence.db")
    monkeypatch.setattr(intel, "DB_PATH", db_path)
    intel.init_db()
    return db_path


def test_fresh_install_bootstraps_to_latest_version(fresh_db):
    conn = sqlite3.connect(fresh_db)
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        assert version == LATEST_SCHEMA_VERSION
    finally:
        conn.close()


def test_migration_is_idempotent(fresh_db):
    intel.init_db()
    intel.init_db()
    conn = sqlite3.connect(fresh_db)
    try:
        rows = list(conn.execute("SELECT version FROM schema_migrations ORDER BY version"))
        assert [row[0] for row in rows] == list(range(1, LATEST_SCHEMA_VERSION + 1))
    finally:
        conn.close()


def test_core_tables_exist(fresh_db):
    expected = {
        "candidate_profile", "experience", "project", "claim", "evidence",
        "claim_evidence", "skill", "story", "job_profile",
        "candidate_job_alignment", "interview_session", "interview_turn",
        "interview_state_snapshot", "guidance_event", "memory_item", "voice_profile",
    }
    conn = sqlite3.connect(fresh_db)
    try:
        rows = list(conn.execute("SELECT name FROM sqlite_master WHERE type='table'"))
        names = {row[0] for row in rows}
    finally:
        conn.close()
    missing = expected - names
    assert not missing, f"missing tables: {missing}"


def test_existing_data_survives_reinit(fresh_db):
    intel.save_candidate_profile("cand-x", profile_text="hello")
    intel.save_claims("cand-x", [{"id": "cl-1", "text": "我使用过 Redis", "truth_status": "SUPPORTED"}])
    intel.init_db()
    assert intel.get_candidate_profile("cand-x")["profile_text"] == "hello"
    claims = intel.list_claims("cand-x")
    assert len(claims) == 1 and claims[0]["id"] == "cl-1"


def test_rebuild_never_duplicates_claim_rows(fresh_db):
    claims = [{"id": "cl-1", "text": "我使用过 Redis", "truth_status": "SUPPORTED"}]
    intel.save_claims("cand-x", claims)
    intel.save_claims("cand-x", claims)
    assert len(intel.list_claims("cand-x")) == 1


def test_claim_status_update_roundtrip(fresh_db):
    intel.save_claims("cand-x", [{"id": "cl-9", "text": "x", "truth_status": "UNKNOWN"}])
    assert intel.update_claim_status("cl-9", "VERIFIED", 0.9) is True
    claim = intel.list_claims("cand-x")[0]
    assert claim["truth_status"] == "VERIFIED" and claim["confidence"] == 0.9
    assert intel.update_claim_status("missing", "VERIFIED") is False


def test_backup_database_creates_snapshot(fresh_db):
    backup = intel.backup_database()
    assert backup is not None
    import os

    try:
        assert os.path.exists(backup)
    finally:
        if os.path.exists(backup):
            os.unlink(backup)


def test_wal_mode_enabled(fresh_db):
    conn = sqlite3.connect(fresh_db)
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert str(mode).lower() == "wal"
    finally:
        conn.close()
