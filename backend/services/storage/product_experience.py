"""v1.3/v1.4 product-experience storage.

This module deliberately keeps the verified v1.2 intelligence core untouched.
It adds goal-centric product state, quick notes, question banks, pin moments and
local-first product events in a separate SQLite database.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any, Optional

from services.storage.paths import sqlite_path

DB_PATH = sqlite_path("product_experience.db")
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _loads(value: Any, fallback: Any) -> Any:
    try:
        parsed = json.loads(value or "")
        return parsed
    except (TypeError, json.JSONDecodeError):
        return fallback


def init_db() -> None:
    with _lock:
        conn = _conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS goal_meta (
                space_id INTEGER PRIMARY KEY,
                stage TEXT NOT NULL DEFAULT 'active',
                interview_round TEXT NOT NULL DEFAULT '',
                next_interview_at REAL,
                next_focus_json TEXT NOT NULL DEFAULT '[]',
                offer_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS quick_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL DEFAULT 'GOAL',
                goal_id INTEGER,
                title TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                pinned INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_quick_notes_goal ON quick_notes(goal_id, pinned DESC, sort_order, updated_at DESC);

            CREATE TABLE IF NOT EXISTS question_banks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT 'GLOBAL',
                role TEXT NOT NULL DEFAULT '',
                company TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT 'USER_ADDED',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS question_bank_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                difficulty TEXT NOT NULL DEFAULT 'standard',
                origin TEXT NOT NULL DEFAULT 'USER_ADDED',
                source_url TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                FOREIGN KEY(bank_id) REFERENCES question_banks(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_question_items_bank ON question_bank_items(bank_id, id);

            CREATE TABLE IF NOT EXISTS pin_moments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL DEFAULT '',
                goal_id INTEGER,
                turn_id TEXT NOT NULL DEFAULT '',
                label TEXT NOT NULL DEFAULT 'IMPORTANT',
                question TEXT NOT NULL DEFAULT '',
                transcript_excerpt TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_pin_moments_session ON pin_moments(session_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_pin_moments_goal ON pin_moments(goal_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS product_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                goal_id INTEGER,
                session_id TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_product_events_name ON product_events(name, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_product_events_goal ON product_events(goal_id, created_at DESC);
            """
        )
        conn.commit()
        conn.close()


init_db()


def get_goal_meta(space_id: int) -> dict[str, Any]:
    with _lock:
        conn = _conn()
        row = conn.execute("SELECT * FROM goal_meta WHERE space_id = ?", (space_id,)).fetchone()
        conn.close()
    if not row:
        return {
            "space_id": space_id,
            "stage": "active",
            "interview_round": "",
            "next_interview_at": None,
            "next_focus": [],
            "offer": {},
        }
    return {
        "space_id": row["space_id"],
        "stage": row["stage"],
        "interview_round": row["interview_round"],
        "next_interview_at": row["next_interview_at"],
        "next_focus": _loads(row["next_focus_json"], []),
        "offer": _loads(row["offer_json"], {}),
        "updated_at": row["updated_at"],
    }


def upsert_goal_meta(
    space_id: int,
    *,
    stage: Optional[str] = None,
    interview_round: Optional[str] = None,
    next_interview_at: Optional[float] = None,
    next_focus: Optional[list[dict[str, Any]]] = None,
    offer: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    current = get_goal_meta(space_id)
    now = time.time()
    values = {
        "stage": stage if stage is not None else current["stage"],
        "interview_round": interview_round if interview_round is not None else current["interview_round"],
        "next_interview_at": next_interview_at if next_interview_at is not None else current["next_interview_at"],
        "next_focus": next_focus if next_focus is not None else current["next_focus"],
        "offer": offer if offer is not None else current["offer"],
    }
    with _lock:
        conn = _conn()
        conn.execute(
            """
            INSERT INTO goal_meta (
                space_id, stage, interview_round, next_interview_at,
                next_focus_json, offer_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(space_id) DO UPDATE SET
                stage=excluded.stage,
                interview_round=excluded.interview_round,
                next_interview_at=excluded.next_interview_at,
                next_focus_json=excluded.next_focus_json,
                offer_json=excluded.offer_json,
                updated_at=excluded.updated_at
            """,
            (
                space_id,
                values["stage"],
                values["interview_round"],
                values["next_interview_at"],
                json.dumps(values["next_focus"], ensure_ascii=False),
                json.dumps(values["offer"], ensure_ascii=False),
                now,
                now,
            ),
        )
        conn.commit()
        conn.close()
    record_event("goal_meta_updated", goal_id=space_id)
    return get_goal_meta(space_id)


def list_quick_notes(goal_id: Optional[int] = None) -> list[dict[str, Any]]:
    with _lock:
        conn = _conn()
        if goal_id is None:
            rows = conn.execute(
                "SELECT * FROM quick_notes ORDER BY pinned DESC, sort_order ASC, updated_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM quick_notes
                WHERE scope = 'GLOBAL' OR goal_id = ?
                ORDER BY pinned DESC, sort_order ASC, updated_at DESC
                """,
                (goal_id,),
            ).fetchall()
        conn.close()
    return [dict(row) for row in rows]


def create_quick_note(
    *,
    title: str,
    content: str = "",
    scope: str = "GOAL",
    goal_id: Optional[int] = None,
    pinned: bool = False,
) -> dict[str, Any]:
    now = time.time()
    normalized_scope = "GLOBAL" if str(scope).upper() == "GLOBAL" else "GOAL"
    if normalized_scope == "GOAL" and goal_id is None:
        raise ValueError("GOAL Quick Note 需要 goal_id")
    with _lock:
        conn = _conn()
        cur = conn.execute(
            """
            INSERT INTO quick_notes (scope, goal_id, title, content, pinned, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (normalized_scope, goal_id, title.strip() or "未命名笔记", content, 1 if pinned else 0, now, now),
        )
        note_id = int(cur.lastrowid)
        conn.commit()
        row = conn.execute("SELECT * FROM quick_notes WHERE id = ?", (note_id,)).fetchone()
        conn.close()
    record_event("quick_note_created", goal_id=goal_id, payload={"note_id": note_id})
    return dict(row)


def update_quick_note(note_id: int, patch: dict[str, Any]) -> Optional[dict[str, Any]]:
    allowed = {"title", "content", "pinned", "sort_order", "scope", "goal_id"}
    updates: list[str] = []
    values: list[Any] = []
    for key, value in patch.items():
        if key not in allowed:
            continue
        if key == "pinned":
            value = 1 if bool(value) else 0
        if key == "scope":
            value = "GLOBAL" if str(value).upper() == "GLOBAL" else "GOAL"
        updates.append(f"{key} = ?")
        values.append(value)
    if not updates:
        return get_quick_note(note_id)
    updates.append("updated_at = ?")
    values.append(time.time())
    values.append(note_id)
    with _lock:
        conn = _conn()
        conn.execute(f"UPDATE quick_notes SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
        row = conn.execute("SELECT * FROM quick_notes WHERE id = ?", (note_id,)).fetchone()
        conn.close()
    return dict(row) if row else None


def get_quick_note(note_id: int) -> Optional[dict[str, Any]]:
    with _lock:
        conn = _conn()
        row = conn.execute("SELECT * FROM quick_notes WHERE id = ?", (note_id,)).fetchone()
        conn.close()
    return dict(row) if row else None


def delete_quick_note(note_id: int) -> bool:
    with _lock:
        conn = _conn()
        cur = conn.execute("DELETE FROM quick_notes WHERE id = ?", (note_id,))
        conn.commit()
        conn.close()
    return cur.rowcount > 0


def list_question_banks() -> list[dict[str, Any]]:
    with _lock:
        conn = _conn()
        rows = conn.execute(
            """
            SELECT b.*, COUNT(i.id) AS item_count
            FROM question_banks b
            LEFT JOIN question_bank_items i ON i.bank_id = b.id
            GROUP BY b.id
            ORDER BY b.updated_at DESC
            """
        ).fetchall()
        conn.close()
    return [dict(row) for row in rows]


def create_question_bank(
    *, name: str, scope: str = "GLOBAL", role: str = "", company: str = "", source_type: str = "USER_ADDED"
) -> dict[str, Any]:
    now = time.time()
    with _lock:
        conn = _conn()
        cur = conn.execute(
            """
            INSERT INTO question_banks (name, scope, role, company, source_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name.strip() or "未命名题库", scope, role, company, source_type, now, now),
        )
        bank_id = int(cur.lastrowid)
        conn.commit()
        row = conn.execute("SELECT * FROM question_banks WHERE id = ?", (bank_id,)).fetchone()
        conn.close()
    return {**dict(row), "item_count": 0}


def get_question_bank(bank_id: int) -> Optional[dict[str, Any]]:
    with _lock:
        conn = _conn()
        bank = conn.execute("SELECT * FROM question_banks WHERE id = ?", (bank_id,)).fetchone()
        if not bank:
            conn.close()
            return None
        items = conn.execute(
            "SELECT * FROM question_bank_items WHERE bank_id = ? ORDER BY id ASC", (bank_id,)
        ).fetchall()
        conn.close()
    return {**dict(bank), "items": [dict(row) for row in items]}


def add_question_item(
    bank_id: int,
    *,
    question: str,
    category: str = "general",
    difficulty: str = "standard",
    origin: str = "USER_ADDED",
    source_url: str = "",
) -> dict[str, Any]:
    if get_question_bank(bank_id) is None:
        raise ValueError("题库不存在")
    now = time.time()
    with _lock:
        conn = _conn()
        cur = conn.execute(
            """
            INSERT INTO question_bank_items
                (bank_id, question, category, difficulty, origin, source_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (bank_id, question.strip(), category, difficulty, origin, source_url, now),
        )
        item_id = int(cur.lastrowid)
        conn.execute("UPDATE question_banks SET updated_at = ? WHERE id = ?", (now, bank_id))
        conn.commit()
        row = conn.execute("SELECT * FROM question_bank_items WHERE id = ?", (item_id,)).fetchone()
        conn.close()
    return dict(row)


def list_question_items(bank_ids: list[int]) -> list[dict[str, Any]]:
    ids = [int(v) for v in bank_ids if int(v) > 0]
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    with _lock:
        conn = _conn()
        rows = conn.execute(
            f"SELECT * FROM question_bank_items WHERE bank_id IN ({placeholders}) ORDER BY bank_id, id",
            ids,
        ).fetchall()
        conn.close()
    return [dict(row) for row in rows]


def create_pin(
    *,
    session_id: str,
    goal_id: Optional[int],
    turn_id: str = "",
    label: str = "IMPORTANT",
    question: str = "",
    transcript_excerpt: str = "",
    note: str = "",
) -> dict[str, Any]:
    now = time.time()
    with _lock:
        conn = _conn()
        cur = conn.execute(
            """
            INSERT INTO pin_moments
              (session_id, goal_id, turn_id, label, question, transcript_excerpt, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, goal_id, turn_id, label, question, transcript_excerpt, note, now),
        )
        pin_id = int(cur.lastrowid)
        conn.commit()
        row = conn.execute("SELECT * FROM pin_moments WHERE id = ?", (pin_id,)).fetchone()
        conn.close()
    record_event("pin_created", goal_id=goal_id, session_id=session_id, payload={"label": label})
    return dict(row)


def list_pins(*, session_id: str = "", goal_id: Optional[int] = None) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if session_id:
        clauses.append("session_id = ?")
        values.append(session_id)
    if goal_id is not None:
        clauses.append("goal_id = ?")
        values.append(goal_id)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _lock:
        conn = _conn()
        rows = conn.execute(
            f"SELECT * FROM pin_moments{where} ORDER BY created_at DESC LIMIT 200", values
        ).fetchall()
        conn.close()
    return [dict(row) for row in rows]


def record_event(
    name: str,
    *,
    goal_id: Optional[int] = None,
    session_id: str = "",
    payload: Optional[dict[str, Any]] = None,
) -> None:
    now = time.time()
    with _lock:
        conn = _conn()
        conn.execute(
            "INSERT INTO product_events (name, goal_id, session_id, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, goal_id, session_id, json.dumps(payload or {}, ensure_ascii=False), now),
        )
        conn.commit()
        conn.close()


def event_summary(goal_id: Optional[int] = None) -> dict[str, Any]:
    with _lock:
        conn = _conn()
        if goal_id is None:
            rows = conn.execute(
                "SELECT name, COUNT(*) AS count FROM product_events GROUP BY name ORDER BY count DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT name, COUNT(*) AS count FROM product_events WHERE goal_id = ? GROUP BY name ORDER BY count DESC",
                (goal_id,),
            ).fetchall()
        conn.close()
    return {"events": {row["name"]: row["count"] for row in rows}}
