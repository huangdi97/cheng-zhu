#!/usr/bin/env python3
"""Export an unlabeled human-review seed from a local Chengzhu product.db.

The output deliberately contains null label fields. It is a review queue, not
evaluation evidence. Humans must fill labels before running
v2_conversation_human_eval.py.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def _json(value: str | None, fallback: Any) -> Any:
    try:
        parsed = json.loads(value or "")
        return parsed
    except Exception:  # noqa: BLE001
        return fallback


def _guidance_class(kind: str) -> str:
    return {
        "RECALL": "RECALL",
        "ANSWER_CUE": "DIRECT_QUESTION",
        "RISK": "CRITICAL_RISK",
        "DELIVERY": "DELIVERY",
    }.get(kind, "PROACTIVE")


def export_rows(db: Path, *, space_id: str = "") -> list[dict[str, Any]]:
    if not db.is_file():
        raise FileNotFoundError(db)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        where = "WHERE sp.id = ?" if space_id else ""
        params: tuple[Any, ...] = (space_id,) if space_id else ()
        sessions = conn.execute(
            "SELECT s.*, sp.profile AS space_profile, sp.title AS space_title "
            "FROM conversation_session s "
            "JOIN conversation_space sp ON sp.id = s.space_id "
            f"{where} ORDER BY s.created_at ASC",
            params,
        ).fetchall()
        session_map = {row["id"]: dict(row) for row in sessions}
        if not session_map:
            return []

        placeholders = ",".join("?" for _ in session_map)
        ids = tuple(session_map)
        guidance = conn.execute(
            f"SELECT * FROM conversation_guidance_event WHERE session_id IN ({placeholders}) ORDER BY created_at ASC",
            ids,
        ).fetchall()
        items = conn.execute(
            f"SELECT * FROM conversation_item WHERE session_id IN ({placeholders}) ORDER BY created_at ASC",
            ids,
        ).fetchall()

        rows: list[dict[str, Any]] = []
        for raw in guidance:
            event = dict(raw)
            session = session_map[event["session_id"]]
            base = {
                "session_id": event["session_id"],
                "space_id": session["space_id"],
                "profile": session["space_profile"],
                "event_id": event["id"],
                "timestamp": event["created_at"],
                "reviewer": "",
                "system": {
                    "kind": event["kind"],
                    "expression_action": event["expression_action"],
                    "reason": event["reason"],
                    "user_action": event["user_action"],
                    "text": event["text"],
                    "source_refs": _json(event["source_refs_json"], []),
                    "score": _json(event["score_json"], {}),
                },
                "notes": "",
            }
            if event["status"] == "SHOWN":
                rows.append({
                    **base,
                    "kind": "guidance",
                    "guidance_class": _guidance_class(event["kind"]),
                    "useful": None,
                    "interruption_regret": None,
                    "source_correct": None,
                    "recall_correct": None if event["kind"] == "RECALL" else None,
                })
            else:
                rows.append({
                    **base,
                    "kind": "silence",
                    "silence_correct": None,
                })

        for raw in items:
            item = dict(raw)
            session = session_map[item["session_id"]]
            rows.append({
                "kind": "truth_item",
                "session_id": item["session_id"],
                "space_id": item["space_id"],
                "profile": session["space_profile"],
                "event_id": item["id"],
                "timestamp": item["created_at"],
                "reviewer": "",
                "predicted_type": item["type"],
                "actual_type": None,
                "predicted_state": item["state"],
                "actual_state": None,
                "system": {
                    "review_status": item["review_status"],
                    "epistemic_status": item["epistemic_status"],
                    "owner_id": item["owner_id"],
                    "due_at": item["due_at"],
                    "source_refs": _json(item["source_refs_json"], []),
                    "title": item["title"],
                },
                "notes": "",
            })

        for session in sessions:
            if session["status"] != "ENDED":
                continue
            rows.append({
                "kind": "continue",
                "session_id": session["id"],
                "space_id": session["space_id"],
                "profile": session["space_profile"],
                "reviewer": "",
                "writeback_accurate": None,
                "notes": "",
            })
            rows.append({
                "kind": "session_outcome",
                "session_id": session["id"],
                "space_id": session["space_id"],
                "profile": session["space_profile"],
                "reviewer": "",
                "cognitive_load_delta": None,
                "would_reuse_space": None,
                "notes": "",
            })
        return rows
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="path to product.db")
    parser.add_argument("--space-id", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    rows = export_rows(Path(args.db), space_id=args.space_id)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        fh.write("# UNLABELED REVIEW SEED — fill reviewer + label fields before evaluation.\n")
        fh.write("# This file is not real-user evidence until a human reviews the rows.\n")
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({
        "rows": len(rows),
        "out": str(out),
        "evidence_status": "UNLABELED_REVIEW_QUEUE",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
