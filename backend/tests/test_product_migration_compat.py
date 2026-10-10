"""v1.2.2 → v1.3 additive migration compatibility (Goal G2 / criterion 4).

A v1.2.2 install has to be adopted by the v1.3 product layer without losing a
single legacy row. The fixture below is built exclusively through the v1.2.2
storage modules, so the schema under test is the one the shipped v1.2.2 build
creates rather than a hand-copied guess.

Invariants protected here:

  * every row of every v1.2 store is unchanged after the upgrade;
  * product.db snapshots itself before migrating an existing file
    (``product.backup_database``);
  * deleting product.db is a complete rollback — the v1.2 data survives and
    the product layer rebuilds the Goal view from it.
"""
import sqlite3
from pathlib import Path
from typing import Any

import pytest

# The v1.2.2 databases, lowest layer first. `product.db` is the only file the
# v1.3 layer is allowed to own; the rest are read-only inputs to it.
V12_STORES = {
    "prep.db": "prep_space",
    "review.db": "review",
    "job_tracker.db": "job_tracker",
    "intelligence.db": "intelligence",
    "knowledge.db": "knowledge",
    "resume_history.db": "resume_history",
}


@pytest.fixture()
def v122_env(tmp_path, monkeypatch):
    """A complete, isolated v1.2.2 store set built by the v1.2.2 modules."""
    import core.config as config_module
    from services.storage import intelligence as intel_storage
    from services.storage import job_tracker, knowledge, prep_space
    from services.storage import product as product_store
    from services.storage import resume_history, review

    modules = {
        "product.db": product_store,
        "intelligence.db": intel_storage,
        "prep.db": prep_space,
        "review.db": review,
        "job_tracker.db": job_tracker,
        "knowledge.db": knowledge,
        "resume_history.db": resume_history,
    }
    for filename, module in modules.items():
        monkeypatch.setattr(module, "DB_PATH", str(tmp_path / filename))
    # Keep config and export writes off the developer's real files.
    monkeypatch.setattr(config_module, "_save_config", lambda cfg: True)
    monkeypatch.setattr(config_module, "_config", config_module._raw_config().model_copy(deep=True))
    monkeypatch.setattr(config_module, "_effective", None)
    monkeypatch.setattr("services.storage.paths.exports_dir", lambda: str(tmp_path))
    monkeypatch.setattr("services.product.data_export.exports_dir", lambda: str(tmp_path))

    # A v1.2.2 install created these schemas on its first launch.
    intel_storage.init_db()
    prep_space.init_db()
    review.init_db()
    job_tracker.init_db()
    knowledge.init_db()
    resume_history.init_db()
    product_store._READY_PATHS.clear()
    product_store._COLUMNS_CACHE.clear()
    yield tmp_path
    config_module.clear_session_overlay()
    product_store._READY_PATHS.clear()
    product_store._COLUMNS_CACHE.clear()


def _seed_v122() -> dict[str, Any]:
    """Create the v1.2.2 data an upgrading user would actually have."""
    from services.storage import intelligence as intel_storage
    from services.storage import job_tracker, knowledge, prep_space
    from services.storage import resume_history, review

    space_id = prep_space.create_space(
        title="MindRank · AIDD Agent Engineer",
        role="AIDD Agent Engineer",
        company="MindRank",
        jd_text="任职要求：熟悉 RAG 与 Agent，有 Redis 高可用经验优先",
    )
    prep_space.add_skill_card(space_id, "WenNian RAG 平台")

    application = job_tracker.create_application(
        {"company": "MindRank", "position": "AIDD Agent Engineer", "stage": "interview"}
    )
    job_tracker.create_or_update_offer(
        {"application_id": application["id"], "status": "negotiating", "comp": "40k*15"}
    )

    session_id = review.create_session(
        started_at=1_700_000_000.0,
        interviewer_enabled=True,
        candidate_enabled=False,
        application_id=application["id"],
    )
    review.add_turn(
        session_id=session_id,
        qa_id="qa-1",
        seq=1,
        question_text="介绍一下你做过最有挑战的项目。",
        candidate_answer_text="我在 WenNian 项目里负责 RAG 架构。",
    )

    knowledge.save_record(
        session_type="practice",
        question="介绍一下你做过最有挑战的项目。",
        answer="参考回答",
        score=4,
        candidate_answer="我在 WenNian 项目里负责 RAG 架构。",
        qa_id="qa-1",
    )

    resume_history.add_upload(b"%PDF-1.4 fake resume", "resume-v1.2.2.pdf")

    candidate_id = intel_storage.active_candidate_id()
    intel_storage.save_candidate_profile(candidate_id)
    intel_storage.save_claims(
        candidate_id,
        [{"id": "claim-1", "text": "我在 WenNian 项目里负责 RAG 架构", "truth_status": "ASSERTED"}],
    )

    return {
        "space_id": space_id,
        "application_id": application["id"],
        "session_id": session_id,
    }


def _snapshot(folder: Path) -> dict[str, dict[str, list[str]]]:
    """Freeze every row of every table in every SQLite file under `folder`."""
    frozen: dict[str, dict[str, list[str]]] = {}
    for path in sorted(folder.glob("*.db")):
        conn = sqlite3.connect(path)
        try:
            tables = sorted(
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            )
            frozen[path.name] = {
                table: sorted(repr(tuple(row)) for row in conn.execute(f"SELECT * FROM {table}"))
                for table in tables
            }
        finally:
            conn.close()
    return frozen


def test_v122_data_survives_the_v13_upgrade_row_for_row(v122_env):
    from services.product import goals, home

    seeded = _seed_v122()
    before = _snapshot(v122_env)
    assert before["prep.db"]["prep_spaces"], "fixture must actually contain v1.2 rows"

    goals.backfill_from_legacy()
    home.summary()  # touch the product layer so every migration path runs

    after = _snapshot(v122_env)
    for filename in V12_STORES:
        assert after[filename] == before[filename], f"v1.2 store {filename} changed during upgrade"

    goal = goals.goal_for_prep_space(seeded["space_id"])
    assert goal is not None, "the v1.2 prep space must become a Goal"
    assert goal["company"] == "MindRank"
    assert goal["application_id"] == seeded["application_id"]
    assert goals.goal_for_review_session(seeded["session_id"]) == goal["id"]

    # Re-running the backfill must not duplicate or rewrite anything.
    assert goals.backfill_from_legacy()["goals_created"] == 0
    assert {name: _snapshot(v122_env)[name] for name in V12_STORES} == before


def test_upgrading_an_existing_product_db_snapshots_it_first(v122_env, monkeypatch):
    from services.product import goals
    from services.storage import product as product_store

    product_store.init_db()
    goal_id = goals.create_goal("MindRank", "AIDD Agent Engineer")["id"]
    assert goal_id
    assert product_store.schema_version() == 9

    # Simulate the next schema release: the shipped file is now one version
    # behind, which is the only situation where a pre-upgrade snapshot is owed.
    monkeypatch.setattr(product_store, "LATEST_SCHEMA_VERSION", 10)
    product_store._READY_PATHS.clear()

    product_store.init_db()

    backups = sorted(v122_env.glob("product.db.backup-*"))
    assert backups, "upgrading an existing product.db must leave a pre-upgrade snapshot"

    conn = sqlite3.connect(backups[0])
    try:
        rows = conn.execute("SELECT id, company FROM goal").fetchall()
    finally:
        conn.close()
    assert (goal_id, "MindRank") in rows, "the snapshot must contain the pre-upgrade rows"




def test_v7_screen_context_migration_preserves_v6_temporal_provenance():
    from services.storage import product_migrations

    conn = sqlite3.connect(":memory:")
    try:
        for version in range(1, 7):
            apply_step, _name = product_migrations._MIGRATIONS[version]
            apply_step(conn)
            conn.execute(f"PRAGMA user_version = {version}")
        conn.commit()

        item_cols_before = {row[1] for row in conn.execute("PRAGMA table_info(conversation_item)")}
        tables_before = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "time_semantics_json" in item_cols_before
        assert "conversation_screen_context" not in tables_before

        apply_v7, _name = product_migrations._MIGRATIONS[7]
        apply_v7(conn)
        conn.execute("PRAGMA user_version = 7")
        conn.commit()

        item_cols_after = {row[1] for row in conn.execute("PRAGMA table_info(conversation_item)")}
        tables_after = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "time_semantics_json" in item_cols_after
        assert "conversation_screen_context" in tables_after
        indexes = {row[1] for row in conn.execute("PRAGMA index_list(conversation_screen_context)")}
        assert "idx_conversation_screen_session" in indexes
        assert "idx_conversation_screen_space" in indexes
    finally:
        conn.close()


def test_v8_integration_migration_is_additive_over_v7_screen_context():
    from services.storage import product_migrations

    conn = sqlite3.connect(":memory:")
    try:
        for version in range(1, 8):
            apply_step, _name = product_migrations._MIGRATIONS[version]
            apply_step(conn)
            conn.execute(f"PRAGMA user_version = {version}")
        conn.commit()

        before_tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        before_item_cols = {row[1] for row in conn.execute("PRAGMA table_info(conversation_item)")}
        before_screen_cols = {row[1] for row in conn.execute("PRAGMA table_info(conversation_screen_context)")}
        assert "conversation_screen_context" in before_tables
        assert "time_semantics_json" in before_item_cols
        assert "text" in before_screen_cols
        assert "conversation_connector_connection" not in before_tables

        before = product_migrations.ensure_schema(conn)
        assert before == 7
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 9

        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {
            "conversation_connector_connection",
            "conversation_connector_snapshot",
            "conversation_connector_execution",
        } <= tables
        space_cols = {row[1] for row in conn.execute("PRAGMA table_info(conversation_space)")}
        assert "selected_connector_snapshot_ids_json" in space_cols
        assert "time_semantics_json" in {row[1] for row in conn.execute("PRAGMA table_info(conversation_item)")}
        assert "text" in {row[1] for row in conn.execute("PRAGMA table_info(conversation_screen_context)")}

        assert product_migrations.ensure_schema(conn) == 9
    finally:
        conn.close()




def test_v9_snapshot_rebuild_preserves_existing_v8_rows_and_adds_space_scoped_unique_key():
    from services.storage import product_migrations

    conn = sqlite3.connect(":memory:")
    try:
        for version in range(1, 9):
            apply_step, _name = product_migrations._MIGRATIONS[version]
            apply_step(conn)
            conn.execute(f"PRAGMA user_version = {version}")
        conn.commit()

        # Seed the minimum referenced parent rows required by the v8 snapshot.
        conn.execute(
            "INSERT INTO conversation_space "
            "(id, title, profile, description, default_goal, default_mode, relationship_key, status, "
            "selected_source_ids_json, selected_quick_note_ids_json, selected_connector_snapshot_ids_json, "
            "retention_policy_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("space-v8", "Space", "PROJECT_SYNC", "", "", "BALANCED", "", "ACTIVE", "[]", "[]", "[]", "{}", 1.0, 1.0),
        )
        conn.execute(
            "INSERT INTO conversation_connector_connection "
            "(id, provider_id, display_name, status, auth_mode, credential_ref, granted_capabilities_json, "
            "provider_scopes_json, account_hint, sync_cursor, last_sync_at, last_error, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("conn-v8", "MCP", "MCP", "CONNECTED", "OPAQUE_REFERENCE", "plugin:mcp/test",
             '["calendar.read"]', '["server-defined"]', "work", "", 1.0, "", 1.0, 1.0),
        )
        conn.execute(
            "INSERT INTO conversation_connector_snapshot "
            "(id, connection_id, space_id, capability, external_kind, external_id, title, excerpt, content_hash, "
            "source_url, occurred_at, visibility, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("snap-v8", "conn-v8", "space-v8", "calendar.read", "CALENDAR_EVENT", "event-1",
             "Review", "10x data scale", "hash-v8", "https://calendar.example/event/1", 1.0, "PRIVATE", '{"safe":"yes"}', 1.0),
        )
        conn.commit()

        before = conn.execute(
            "SELECT id, connection_id, space_id, capability, external_id, content_hash, metadata_json "
            "FROM conversation_connector_snapshot"
        ).fetchone()

        apply_v9, _name = product_migrations._MIGRATIONS[9]
        apply_v9(conn)
        conn.execute("PRAGMA user_version = 9")
        conn.commit()

        after = conn.execute(
            "SELECT id, connection_id, space_id, capability, external_id, content_hash, metadata_json "
            "FROM conversation_connector_snapshot"
        ).fetchone()
        assert after == before

        unique_indexes = [
            row for row in conn.execute("PRAGMA index_list(conversation_connector_snapshot)").fetchall()
            if row[2] == 1
        ]
        assert unique_indexes, "v9 rebuilt snapshot table must retain a UNIQUE provenance key"
        unique_columns = {
            tuple(col[2] for col in conn.execute(f"PRAGMA index_info('{row[1]}')").fetchall())
            for row in unique_indexes
        }
        assert (
            "space_id", "connection_id", "capability", "external_kind", "external_id", "content_hash"
        ) in unique_columns
    finally:
        conn.close()


def test_deleting_product_db_is_a_complete_rollback(v122_env):
    from services.product import goals
    from services.storage import product as product_store

    seeded = _seed_v122()
    goals.backfill_from_legacy()
    assert product_store.schema_version() == 9

    # Rollback: drop the v1.3-owned file only. Nothing else is involved.
    product_store._READY_PATHS.clear()
    product_store._COLUMNS_CACHE.clear()
    Path(product_store.DB_PATH).unlink()

    rebuilt = goals.backfill_from_legacy()
    assert rebuilt["goals_created"] == 1, "the Goal view must rebuild from v1.2 data"
    assert goals.goal_for_prep_space(seeded["space_id"]) is not None
    assert _snapshot(v122_env)["prep.db"]["prep_spaces"]
