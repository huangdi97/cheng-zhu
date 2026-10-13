#!/usr/bin/env python3
"""Export explicit in-product Conversation feedback to human-eval JSONL.

Only rows the user explicitly entered through the local pilot feedback surface
are exported. Pin/Use/Dismiss actions, click-throughs, suppressed events and
other runtime proxies are never converted into quality labels.

The fixed reviewer label IN_PRODUCT_SELF_REPORT is a provenance category, not
verified identity. This exporter does not create an authorized real-use pilot
manifest and cannot make REAL_USER_VALIDATED true.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


REVIEWER = "IN_PRODUCT_SELF_REPORT"


def _json(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
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
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "conversation_human_feedback" not in tables:
            return []

        where = "WHERE f.space_id = ?" if space_id else ""
        params: tuple[Any, ...] = (space_id,) if space_id else ()
        feedback = conn.execute(
            "SELECT f.*, s.template AS profile "
            "FROM conversation_human_feedback f "
            "JOIN conversation_session s ON s.id = f.session_id "
            f"{where} ORDER BY f.created_at ASC",
            params,
        ).fetchall()

        rows: list[dict[str, Any]] = []
        for raw in feedback:
            item = dict(raw)
            kind = str(item.get("kind") or "").upper()
            labels = _json(item.get("labels_json"), {})
            base = {
                "session_id": item["session_id"],
                "space_id": item["space_id"],
                "profile": item.get("profile") or "",
                "event_id": item.get("target_id") or "",
                "timestamp": item.get("created_at"),
                "reviewer": REVIEWER,
                "notes": item.get("note") or "",
                "label_source": "LOCAL_IN_PRODUCT_EXPLICIT_SELF_REPORT",
            }

            if kind in {"GUIDANCE", "SILENCE"}:
                event = conn.execute(
                    "SELECT * FROM conversation_guidance_event WHERE id = ? AND session_id = ?",
                    (item.get("target_id") or "", item["session_id"]),
                ).fetchone()
                if event is None:
                    # A deleted/retained-mismatch target must not silently
                    # become evaluation evidence without its source event.
                    continue
                event = dict(event)
                origin = _json(event.get("origin_json"), {})
                if (
                    not isinstance(origin, dict)
                    or origin.get("kind") != "TRANSCRIPT_AUTO"
                    or not str(origin.get("transcript_segment_id") or "").strip()
                ):
                    # Pre-v12/manual-lab feedback stays local history but cannot
                    # enter Stable live-guidance metric populations.
                    continue
                if kind == "SILENCE" and str(origin.get("decision_class") or "") != "ARBITER":
                    continue
                if kind == "GUIDANCE":
                    row = {
                        **base,
                        "kind": "guidance",
                        "guidance_class": _guidance_class(str(event.get("kind") or "")),
                        "useful": labels.get("useful"),
                        "interruption_regret": labels.get("interruption_regret"),
                        "source_correct": labels.get("source_correct"),
                        "recall_correct": labels.get("recall_correct"),
                        "system": {
                            "kind": event.get("kind"),
                            "expression_action": event.get("expression_action"),
                            "reason": event.get("reason"),
                            "status": event.get("status"),
                            "source_refs": _json(event.get("source_refs_json"), []),
                            "origin": origin,
                        },
                    }
                else:
                    row = {
                        **base,
                        "kind": "silence",
                        "silence_correct": labels.get("silence_correct"),
                        "system": {
                            "kind": event.get("kind"),
                            "expression_action": event.get("expression_action"),
                            "reason": event.get("reason"),
                            "status": event.get("status"),
                            "origin": origin,
                        },
                    }
                rows.append(row)
                continue

            if kind == "CONTINUE":
                rows.append({
                    **base,
                    "kind": "continue",
                    "writeback_accurate": labels.get("writeback_accurate"),
                })
            elif kind == "SESSION_OUTCOME":
                rows.append({
                    **base,
                    "kind": "session_outcome",
                    "cognitive_load_delta": labels.get("cognitive_load_delta"),
                    "would_reuse_space": labels.get("would_reuse_space"),
                })
        return rows
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="path to local product.db")
    parser.add_argument("--space-id", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    db = Path(args.db)
    out = Path(args.out)
    if db.resolve() == out.resolve():
        parser.error("--out must not overwrite product.db")
    if out.exists():
        parser.error("--out already exists; choose a new path to preserve prior evidence")

    rows = export_rows(db, space_id=args.space_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as fh:
        fh.write("# LOCAL EXPLICIT SELF-REPORT LABELS — not verified real-user identity.\n")
        fh.write("# Pair with independent labels + authorized pilot manifest before stable review.\n")
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(json.dumps({
        "rows": len(rows),
        "out": str(out),
        "reviewer": REVIEWER,
        "evidence_status": "LOCAL_EXPLICIT_SELF_REPORT",
        "real_user_validated": False,
        "pmf_proven": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
