"""Local Product DB migration-matrix evidence (offline; no external calls).

Builds real product.db fixtures at each historical schema version by driving the
shipped migrator steps themselves (``_MIGRATIONS``), seeds one marker row per
table that exists at that version, then re-opens the database through
``ensure_schema`` and proves:

  * the migration is additive (every table and every column survives);
  * every seeded row survives, including the v8 -> v9 connector-snapshot table
    rebuild that copies rows into a new table to tighten its UNIQUE key;
  * connector audit / snapshot provenance rows are preserved;
  * no migration is applied twice and the version history has no duplicates;
  * reopening the migrated database is idempotent.

Usage:  python scripts/v2_local_migration_matrix.py [--out PATH]
Exit code 0 only when every case passes.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from services.storage.product_migrations import LATEST_SCHEMA_VERSION, _MIGRATIONS, ensure_schema  # noqa: E402

CASES = ("fresh", "v1", "v2", "v4", "v7", "v8", "v9")


def _build_at(conn: sqlite3.Connection, upto: int) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at REAL NOT NULL)"
    )
    for version in sorted(_MIGRATIONS):
        if version > upto:
            break
        apply_step, name = _MIGRATIONS[version]
        apply_step(conn)
        conn.execute(
            "INSERT OR REPLACE INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (version, name, time.time()),
        )
        conn.execute(f"PRAGMA user_version = {int(version)}")
    conn.commit()


def _tables(conn: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return sorted(str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})"))


def _fingerprint(conn: sqlite3.Connection) -> dict:
    tables = _tables(conn)
    return {
        "user_version": int(conn.execute("PRAGMA user_version").fetchone()[0]),
        "tables": tables,
        "columns": {table: _columns(conn, table) for table in tables},
        "migration_history": [
            int(row[0]) for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")
        ],
    }


def _seed_marker(conn: sqlite3.Connection, table: str, marker: str) -> bool:
    """Insert one row filling only NOT NULL columns that have no default."""
    info = list(conn.execute(f"PRAGMA table_info({table})"))
    names: list[str] = []
    values: list[object] = []
    for _cid, name, ctype, notnull, dflt, pk in info:
        if pk:
            value: object = marker
        elif dflt is not None:
            continue  # let SQLite apply the declared default
        elif notnull:
            kind = str(ctype or "").upper()
            if any(token in kind for token in ("INT", "REAL", "NUM")):
                value = 0
            else:
                value = "{}" if str(name).endswith("json") else ""
        else:
            continue  # nullable: leave NULL
        names.append(str(name))
        values.append(value)
    if not names:
        return False
    sql = f"INSERT INTO {table} ({', '.join(names)}) VALUES ({', '.join('?' for _ in names)})"
    try:
        conn.execute(sql, values)
        conn.commit()
        return True
    except sqlite3.Error:
        return False


def _row_survives(conn: sqlite3.Connection, table: str, marker: str) -> bool:
    info = list(conn.execute(f"PRAGMA table_info({table})"))
    pk_names = [str(row[1]) for row in info if int(row[5]) > 0]
    if not pk_names:
        return False
    where = " AND ".join(f"{name} = ?" for name in pk_names)
    row = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", [marker] * len(pk_names)).fetchone()
    return bool(row and int(row[0]) > 0)


def run_case(name: str, workdir: Path) -> dict:
    upto = {"fresh": 0, "v1": 1, "v2": 2, "v4": 4, "v7": 7, "v8": 8, "v9": 9}[name]
    db_path = workdir / f"{name}.db"
    result: dict = {"case": name, "built_at_version": upto}

    conn = sqlite3.connect(db_path)
    _build_at(conn, upto)

    before = _fingerprint(conn)
    result["version_before"] = before["user_version"]

    seeded: list[str] = []
    if upto > 0:
        for table in before["tables"]:
            if table == "schema_migrations":
                continue
            if _seed_marker(conn, table, f"marker-{name}"):
                seeded.append(table)
    result["seeded_tables"] = seeded
    result["tables_before"] = len(before["tables"])
    conn.close()

    # Re-open exactly like the product layer does and migrate.
    conn = sqlite3.connect(db_path)
    reported_before = ensure_schema(conn)
    conn.commit()
    after = _fingerprint(conn)
    result["version_after"] = after["user_version"]
    result["ensure_schema_reported_before"] = int(reported_before)

    lost_tables = [t for t in before["tables"] if t not in after["tables"]]
    lost_columns = {
        table: [c for c in cols if c not in after["columns"].get(table, [])]
        for table, cols in before["columns"].items()
        if table in after["columns"]
    }
    lost_columns = {table: cols for table, cols in lost_columns.items() if cols}
    lost_rows = [t for t in seeded if not _row_survives(conn, t, f"marker-{name}")]
    history = after["migration_history"]
    duplicates = sorted({v for v in history if history.count(v) > 1})

    # Idempotent reopen: a second ensure_schema must not change anything.
    second_reported = ensure_schema(conn)
    conn.commit()
    second = _fingerprint(conn)
    idempotent = second == after

    result.update(
        {
            "tables_after": len(after["tables"]),
            "lost_tables": lost_tables,
            "lost_columns": lost_columns,
            "lost_seeded_rows": lost_rows,
            "migration_history_len": len(history),
            "duplicate_migrations": duplicates,
            "idempotent_reopen": idempotent,
            "second_ensure_schema_reported": int(second_reported),
        }
    )
    result["connector_tables_present"] = sorted(t for t in after["tables"] if "connector" in t or "external" in t)
    result["passed"] = (
        not lost_tables
        and not lost_columns
        and not lost_rows
        and not duplicates
        and idempotent
        and after["user_version"] == LATEST_SCHEMA_VERSION
        and int(second_reported) == LATEST_SCHEMA_VERSION
    )
    conn.close()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    results = []
    with tempfile.TemporaryDirectory(
        prefix="chengzhu-migration-matrix-", ignore_cleanup_errors=True
    ) as tmp:
        workdir = Path(tmp)
        for case in CASES:
            results.append(run_case(case, workdir))

    payload = {
        "evidence_type": "LOCAL_MIGRATION_MATRIX",
        "latest_schema_version": LATEST_SCHEMA_VERSION,
        "fixture_method": (
            "each historical fixture is built by running the shipped migrator steps themselves "
            "(_MIGRATIONS 1..N), then one marker row is seeded per existing table"
        ),
        "cases": results,
        "passed": all(item["passed"] for item in results),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwritten: {out}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
