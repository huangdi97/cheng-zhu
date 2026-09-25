"""准备空间存储：prep_spaces / prep_skill_cards。

每个目标岗位一个准备空间，汇总 简历 + JD + 岗位对齐洞察 + 项目技能卡 + 预测真题，
这是成竹的「面试准备空间」，全部本地 SQLite 存储。
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any, Optional

from services.storage.paths import sqlite_path

DB_PATH = sqlite_path("prep.db")
_db_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _db_lock:
        conn = _conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prep_spaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT '',
                company TEXT NOT NULL DEFAULT '',
                jd_text TEXT NOT NULL DEFAULT '',
                resume_text TEXT NOT NULL DEFAULT '',
                resume_history_id INTEGER,
                insight_markdown TEXT NOT NULL DEFAULT '',
                insight_status TEXT NOT NULL DEFAULT 'pending',
                insight_error TEXT NOT NULL DEFAULT '',
                questions_json TEXT NOT NULL DEFAULT '[]',
                questions_status TEXT NOT NULL DEFAULT 'pending',
                questions_error TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prep_skill_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                space_id INTEGER NOT NULL,
                project_name TEXT NOT NULL,
                card_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                error TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY (space_id) REFERENCES prep_spaces(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_prep_skill_cards_space_id ON prep_skill_cards(space_id)")
        conn.commit()
        conn.close()


init_db()


def _row_to_space(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "role": row["role"],
        "company": row["company"],
        "jd_text": row["jd_text"],
        "resume_text": row["resume_text"],
        "resume_history_id": row["resume_history_id"],
        "insight_markdown": row["insight_markdown"],
        "insight_status": row["insight_status"],
        "insight_error": row["insight_error"],
        "questions_status": row["questions_status"],
        "questions_error": row["questions_error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_card(row: sqlite3.Row) -> dict[str, Any]:
    card = {}
    try:
        card = json.loads(row["card_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        card = {}
    if not isinstance(card, dict):
        card = {}
    return {
        "id": row["id"],
        "space_id": row["space_id"],
        "project_name": row["project_name"],
        "card": card,
        "status": row["status"],
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_space(
    title: str,
    role: str = "",
    company: str = "",
    jd_text: str = "",
    resume_text: str = "",
    resume_history_id: Optional[int] = None,
) -> int:
    now = time.time()
    with _db_lock:
        conn = _conn()
        cur = conn.execute(
            """
            INSERT INTO prep_spaces (
                title, role, company, jd_text, resume_text, resume_history_id,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title or "未命名准备空间", role or "", company or "", jd_text or "",
             resume_text or "", resume_history_id, now, now),
        )
        conn.commit()
        space_id = int(cur.lastrowid)
        conn.close()
    return space_id


def list_spaces() -> list[dict[str, Any]]:
    with _db_lock:
        conn = _conn()
        rows = conn.execute(
            """
            SELECT s.*, (SELECT COUNT(*) FROM prep_skill_cards c WHERE c.space_id = s.id) AS skill_card_count
            FROM prep_spaces s ORDER BY s.updated_at DESC
            """
        ).fetchall()
        conn.close()
    items = []
    for row in rows:
        item = _row_to_space(row)
        item["skill_card_count"] = row["skill_card_count"] or 0
        items.append(item)
    return items


def get_space(space_id: int) -> Optional[dict[str, Any]]:
    with _db_lock:
        conn = _conn()
        row = conn.execute("SELECT * FROM prep_spaces WHERE id = ?", (space_id,)).fetchone()
        if not row:
            conn.close()
            return None
        cards = conn.execute(
            "SELECT * FROM prep_skill_cards WHERE space_id = ? ORDER BY id ASC", (space_id,)
        ).fetchall()
        conn.close()
    space = _row_to_space(row)
    try:
        space["questions"] = json.loads(row["questions_json"] or "[]")
    except (json.JSONDecodeError, TypeError):
        space["questions"] = []
    if not isinstance(space["questions"], list):
        space["questions"] = []
    space["skill_cards"] = [_row_to_card(c) for c in cards]
    return space


def delete_space(space_id: int) -> bool:
    with _db_lock:
        conn = _conn()
        conn.execute("DELETE FROM prep_skill_cards WHERE space_id = ?", (space_id,))
        cur = conn.execute("DELETE FROM prep_spaces WHERE id = ?", (space_id,))
        conn.commit()
        deleted = cur.rowcount > 0
        conn.close()
    return deleted


def update_insight(space_id: int, markdown: str, status: str, error: str = "") -> None:
    now = time.time()
    with _db_lock:
        conn = _conn()
        conn.execute(
            "UPDATE prep_spaces SET insight_markdown = ?, insight_status = ?, insight_error = ?, updated_at = ? WHERE id = ?",
            (markdown or "", status or "done", error or "", now, space_id),
        )
        conn.commit()
        conn.close()


def update_questions(space_id: int, questions: list[dict[str, Any]], status: str, error: str = "") -> None:
    now = time.time()
    with _db_lock:
        conn = _conn()
        conn.execute(
            "UPDATE prep_spaces SET questions_json = ?, questions_status = ?, questions_error = ?, updated_at = ? WHERE id = ?",
            (json.dumps(questions or [], ensure_ascii=False), status or "done", error or "", now, space_id),
        )
        conn.commit()
        conn.close()


def add_skill_card(space_id: int, project_name: str) -> int:
    now = time.time()
    with _db_lock:
        conn = _conn()
        cur = conn.execute(
            "INSERT INTO prep_skill_cards (space_id, project_name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (space_id, project_name or "未命名项目", now, now),
        )
        conn.commit()
        card_id = int(cur.lastrowid)
        conn.close()
    return card_id


def update_skill_card(card_id: int, card: dict[str, Any], status: str, error: str = "") -> None:
    now = time.time()
    with _db_lock:
        conn = _conn()
        conn.execute(
            "UPDATE prep_skill_cards SET card_json = ?, status = ?, error = ?, updated_at = ? WHERE id = ?",
            (json.dumps(card or {}, ensure_ascii=False), status or "done", error or "", now, card_id),
        )
        conn.commit()
        conn.close()
