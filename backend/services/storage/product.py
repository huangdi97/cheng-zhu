"""product.db — persistence for the v1.3 Goal-centered product layer.

House style follows storage.intelligence: module-level DB_PATH (tests
monkeypatch it), WAL, Row factory, one lock, JSON payloads in ``*_json``
TEXT columns. Rows are returned as plain dicts with ``*_json`` columns decoded
under the key without the suffix (``tags_json`` -> ``tags``) and 0/1 flag
columns as booleans.

The schema is created lazily on first use of each DB_PATH so a monkeypatched
path in tests gets a fresh, migrated file.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from core.logger import get_logger
from services.storage.paths import sqlite_path
from services.storage.product_migrations import LATEST_SCHEMA_VERSION, ensure_schema

_log = get_logger("storage.product")

DB_PATH = sqlite_path("product.db")
_LOCK = threading.RLock()
_READY_PATHS: set[str] = set()

_BOOL_COLUMNS = frozenset({"pinned", "builtin", "used_in_reflection", "guided", "consent_ack"})
_COLUMNS_CACHE: dict[tuple[str, str], list[str]] = {}


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"


def now() -> float:
    return time.time()


def _raw_conn(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def backup_database(path: Optional[str] = None) -> Optional[str]:
    """Copy product.db (+wal/shm) aside before a schema upgrade."""
    src_path = path or DB_PATH
    if not Path(src_path).exists():
        return None
    target = f"{src_path}.backup-{time.strftime('%Y%m%d-%H%M%S')}"
    try:
        for suffix in ("", "-wal", "-shm"):
            src = Path(src_path + suffix)
            if src.exists():
                shutil.copy2(src, target + suffix)
        return target
    except OSError as exc:
        _log.warning("product db backup failed: %s", exc)
        return None


def _ensure_ready(path: str) -> None:
    if path in _READY_PATHS:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    existed = Path(path).exists()
    conn = _raw_conn(path)
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if existed and 0 < version < LATEST_SCHEMA_VERSION:
            conn.close()
            backup_database(path)
            conn = _raw_conn(path)
        ensure_schema(conn)
    finally:
        conn.close()
    _READY_PATHS.add(path)


def init_db() -> None:
    with _LOCK:
        _ensure_ready(DB_PATH)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Locked connection that commits on success and rolls back on error."""
    path = DB_PATH
    with _LOCK:
        _ensure_ready(path)
        conn = _raw_conn(path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def schema_version() -> int:
    with connect() as conn:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])


# ---------------------------------------------------------------------------
# Row codec
# ---------------------------------------------------------------------------


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    key = (DB_PATH, table)
    cols = _COLUMNS_CACHE.get(key)
    if cols is None:
        cols = [str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        _COLUMNS_CACHE[key] = cols
    return cols


def decode_row(row: Optional[sqlite3.Row]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    out: dict[str, Any] = {}
    for key in row.keys():
        value = row[key]
        if key.endswith("_json"):
            try:
                out[key[:-5]] = json.loads(value) if value else None
            except (TypeError, json.JSONDecodeError):
                out[key[:-5]] = None
        elif key in _BOOL_COLUMNS:
            out[key] = bool(value)
        else:
            out[key] = value
    return out


def _encode(conn: sqlite3.Connection, table: str, data: dict[str, Any]) -> dict[str, Any]:
    cols = set(_columns(conn, table))
    encoded: dict[str, Any] = {}
    for key, value in data.items():
        if f"{key}_json" in cols:
            encoded[f"{key}_json"] = json.dumps(value if value is not None else None, ensure_ascii=False)
        elif key in cols:
            encoded[key] = int(bool(value)) if key in _BOOL_COLUMNS else value
    return encoded


# ---------------------------------------------------------------------------
# Generic table helpers (domain services own validation)
# ---------------------------------------------------------------------------


def insert(table: str, data: dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> dict[str, Any]:
    def _do(c: sqlite3.Connection) -> dict[str, Any]:
        # SQLite permits NULL in a TEXT PRIMARY KEY unless the column is also
        # declared NOT NULL. Every product entity table uses an explicit text
        # id, so silently accepting a missing id would create a row that none
        # of the domain services can address again. INTEGER AUTOINCREMENT and
        # composite-key tables are intentionally excluded from this guard.
        info = c.execute(f"PRAGMA table_info({table})").fetchall()
        pk = [r for r in info if int(r[5] or 0) > 0]
        if len(pk) == 1 and str(pk[0][1]) == "id" and str(pk[0][2]).upper() != "INTEGER" and not data.get("id"):
            raise ValueError(f"{table}.id is required")
        enc = _encode(c, table, data)
        if not enc:
            raise ValueError(f"{table}: no writable columns supplied")
        cols = ", ".join(enc)
        marks = ", ".join("?" for _ in enc)
        c.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(enc.values()))
        return data

    if conn is not None:
        return _do(conn)
    with connect() as c:
        return _do(c)


def update(
    table: str,
    key_value: Any,
    data: dict[str, Any],
    key: str = "id",
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    def _do(c: sqlite3.Connection) -> int:
        enc = _encode(c, table, data)
        if not enc:
            return 0
        sets = ", ".join(f"{k} = ?" for k in enc)
        cur = c.execute(f"UPDATE {table} SET {sets} WHERE {key} = ?", (*enc.values(), key_value))
        return int(cur.rowcount)

    if conn is not None:
        return _do(conn)
    with connect() as c:
        return _do(c)


def get(table: str, key_value: Any, key: str = "id") -> Optional[dict[str, Any]]:
    with connect() as c:
        return decode_row(c.execute(f"SELECT * FROM {table} WHERE {key} = ?", (key_value,)).fetchone())


def select(
    table: str,
    where: str = "",
    params: tuple[Any, ...] = (),
    order: str = "",
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    if order:
        sql += f" ORDER BY {order}"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    with connect() as c:
        return [decode_row(r) for r in c.execute(sql, params).fetchall()]  # type: ignore[misc]


def delete(table: str, key_value: Any, key: str = "id") -> bool:
    with connect() as c:
        return c.execute(f"DELETE FROM {table} WHERE {key} = ?", (key_value,)).rowcount > 0


def scalar(sql: str, params: tuple[Any, ...] = ()) -> Any:
    with connect() as c:
        row = c.execute(sql, params).fetchone()
        return row[0] if row else None


def rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connect() as c:
        return [decode_row(r) for r in c.execute(sql, params).fetchall()]  # type: ignore[misc]


def meta_get(key: str) -> Optional[str]:
    with connect() as c:
        row = c.execute("SELECT value FROM product_meta WHERE key = ?", (key,)).fetchone()
        return str(row[0]) if row else None


def meta_set(key: str, value: str) -> None:
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO product_meta (key, value) VALUES (?, ?)", (key, value))
