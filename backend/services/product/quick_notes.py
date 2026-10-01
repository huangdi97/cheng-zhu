"""Quick Notes — first-class short notes, global or goal-scoped.

 TRUTH BOUNDARY (canonical §9):
  Quick Note != Evidence != Knowledge Base != User-Confirmed Claim != Memory.
  Nothing in this module touches claims, evidence, KB or memory. A note that
  says "我做过 Redis Cluster" stays a note; the pack exposes notes in their own
  section labelled ``USER_NOTE`` and the compiler never cites them as evidence.

 Concurrent edits: every note carries ``revision``. An update must send the
 revision it was based on; a stale revision is rejected (QuickNoteConflict)
 instead of silently overwriting the newer text.
"""
from __future__ import annotations

from typing import Any, Optional

from services.product import events
from services.storage import product as store

SCOPES = ("GLOBAL", "GOAL")
ASK_TAG = "想问"
MAX_TITLE = 120
MAX_CONTENT = 4000


class QuickNoteError(ValueError):
    pass


class QuickNoteConflict(QuickNoteError):
    def __init__(self, current: dict[str, Any]):
        super().__init__("这条速记已在别处修改，请刷新后再保存")
        self.current = current


def _clean_tags(tags: Any) -> list[str]:
    if not isinstance(tags, list):
        return []
    out: list[str] = []
    for tag in tags:
        text = str(tag or "").strip()[:20]
        if text and text not in out:
            out.append(text)
    return out[:8]


def create_note(
    content: str,
    title: str = "",
    scope: str = "GLOBAL",
    goal_id: Optional[str] = None,
    pinned: bool = False,
    tags: Optional[list[str]] = None,
    origin: str = "USER",
) -> dict[str, Any]:
    content = (content or "").strip()
    title = (title or "").strip()
    if not content and not title:
        raise QuickNoteError("速记内容不能为空")
    if scope not in SCOPES:
        raise QuickNoteError(f"未知范围：{scope}")
    if scope == "GOAL" and not goal_id:
        raise QuickNoteError("目标速记需要指定求职目标")
    if scope == "GOAL":
        from services.product.goals import require_goal

        require_goal(str(goal_id))
    now = store.now()
    max_order = store.scalar("SELECT COALESCE(MAX(sort_order), 0) FROM quick_note") or 0
    note = {
        "id": store.new_id("qn_"),
        "scope": scope,
        "goal_id": goal_id if scope == "GOAL" else None,
        "title": title[:MAX_TITLE],
        "content": content[:MAX_CONTENT],
        "pinned": bool(pinned),
        "sort_order": int(max_order) + 10,
        "tags": _clean_tags(tags),
        "revision": 1,
        "created_at": now,
        "updated_at": now,
    }
    store.insert("quick_note", note)
    events.record("quick_note_created", goal_id=goal_id or "", scope=scope, origin=origin)
    if origin == "REFLECTION":
        events.record("quick_note_from_reflection", goal_id=goal_id or "")
    return note


def get_note(note_id: str) -> Optional[dict[str, Any]]:
    return store.get("quick_note", note_id)


def list_notes(goal_id: Optional[str] = None, include_global: bool = True, scope: str = "") -> list[dict[str, Any]]:
    """Notes visible for a goal (goal-scoped + global), pinned first, then sort_order."""
    order = "pinned DESC, sort_order ASC, created_at ASC"
    if scope == "GLOBAL":
        return store.select("quick_note", "scope = 'GLOBAL'", (), order)
    if goal_id:
        if include_global:
            return store.select("quick_note", "scope = 'GLOBAL' OR goal_id = ?", (goal_id,), order)
        return store.select("quick_note", "goal_id = ?", (goal_id,), order)
    return store.select("quick_note", "", (), order)


def update_note(note_id: str, patch: dict[str, Any], base_revision: Optional[int] = None) -> dict[str, Any]:
    current = get_note(note_id)
    if current is None:
        raise QuickNoteError("速记不存在")
    if base_revision is not None and int(base_revision) != int(current["revision"]):
        raise QuickNoteConflict(current)
    clean: dict[str, Any] = {}
    if "title" in patch:
        clean["title"] = str(patch["title"] or "").strip()[:MAX_TITLE]
    if "content" in patch:
        clean["content"] = str(patch["content"] or "").strip()[:MAX_CONTENT]
    if "pinned" in patch:
        clean["pinned"] = bool(patch["pinned"])
    if "tags" in patch:
        clean["tags"] = _clean_tags(patch["tags"])
    if "scope" in patch or "goal_id" in patch:
        scope = patch.get("scope", current["scope"])
        goal_id = patch.get("goal_id", current["goal_id"])
        if scope not in SCOPES or (scope == "GOAL" and not goal_id):
            raise QuickNoteError("范围无效")
        clean["scope"] = scope
        clean["goal_id"] = goal_id if scope == "GOAL" else None
    if not clean:
        return current
    if not (clean.get("content", current["content"]) or clean.get("title", current["title"])):
        raise QuickNoteError("速记内容不能为空")
    clean["revision"] = int(current["revision"]) + 1
    clean["updated_at"] = store.now()
    with store.connect() as conn:
        # compare-and-swap on revision so two writers cannot both win
        sets = ", ".join(f"{k} = ?" for k in _encode_keys(clean))
        values = list(_encode_values(clean))
        cur = conn.execute(
            f"UPDATE quick_note SET {sets} WHERE id = ? AND revision = ?",
            (*values, note_id, int(current["revision"])),
        )
        if cur.rowcount == 0:
            latest = store.decode_row(conn.execute("SELECT * FROM quick_note WHERE id = ?", (note_id,)).fetchone())
            raise QuickNoteConflict(latest or current)
    return get_note(note_id) or current


def _encode_keys(data: dict[str, Any]) -> list[str]:
    return [f"{k}_json" if k == "tags" else k for k in data]


def _encode_values(data: dict[str, Any]) -> list[Any]:
    import json

    out: list[Any] = []
    for key, value in data.items():
        if key == "tags":
            out.append(json.dumps(value, ensure_ascii=False))
        elif key == "pinned":
            out.append(int(bool(value)))
        else:
            out.append(value)
    return out


def delete_note(note_id: str) -> bool:
    note = get_note(note_id)
    if note is None:
        return False
    store.delete("quick_note", note_id)
    _detach_from_goals(note_id)
    return True


def _detach_from_goals(note_id: str) -> None:
    for goal in store.select("goal", "selected_quick_note_ids_json LIKE ?", (f"%{note_id}%",)):
        ids = [i for i in (goal.get("selected_quick_note_ids") or []) if i != note_id]
        store.update("goal", goal["id"], {"selected_quick_note_ids": ids})


def reorder(ordered_ids: list[str]) -> int:
    with store.connect() as conn:
        changed = 0
        for index, note_id in enumerate(ordered_ids):
            changed += conn.execute(
                "UPDATE quick_note SET sort_order = ? WHERE id = ?", ((index + 1) * 10, note_id)
            ).rowcount
    return changed


def notes_for_pack(goal: dict[str, Any], record_usage: bool = False) -> list[dict[str, Any]]:
    """Notes selected into a Goal's InterviewPack, labelled as user notes.

    Selection is explicit (goal.selected_quick_note_ids). Pinned notes of the
    goal are included by default only when the user has not curated a
    selection yet.
    """
    selected = [i for i in (goal.get("selected_quick_note_ids") or []) if i]
    if selected:
        notes = [n for n in (get_note(i) for i in selected) if n]
    else:
        notes = [n for n in list_notes(goal["id"]) if n["pinned"]]
    if record_usage:
        for _note in notes:
            events.record("quick_note_used_in_pack", goal_id=goal["id"])
    return [
        {"id": n["id"], "title": n["title"], "content": n["content"], "tags": n["tags"],
         "kind": "USER_NOTE", "is_evidence": False}
        for n in notes
    ]


def ask_notes(goal_id: Optional[str]) -> list[dict[str, Any]]:
    """Notes tagged 想问 — inputs for Closing Mode."""
    return [n for n in list_notes(goal_id) if ASK_TAG in (n.get("tags") or []) or n["title"].startswith(ASK_TAG)]
