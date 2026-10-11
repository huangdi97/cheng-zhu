#!/usr/bin/env python3
"""Export an unlabeled human-review seed from a local Chengzhu product.db.

The output deliberately contains null label fields. It is a review queue, not
evaluation evidence. Humans must fill labels before running
v2_conversation_human_eval.py.

Prediction provenance is never reconstructed from newer logic:
- Conversation Item predictions come from immutable v10 prediction snapshots
  (or a still-unreviewed legacy candidate);
- Direct Question predictions come only from v11 capture-time transcript
  analysis snapshots;
- historical reviewed/unversioned rows are marked prediction_unavailable.
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
        transcript = conn.execute(
            f"SELECT * FROM conversation_transcript_segment WHERE session_id IN ({placeholders}) "
            "AND is_final = 1 ORDER BY created_at ASC",
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
                "label_source": "",
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

        for raw in transcript:
            segment = dict(raw)
            channel = str(segment.get("channel") or "").upper()
            if channel == "SELF_MIC":
                continue
            session = session_map[segment["session_id"]]
            analysis = _json(segment.get("analysis_json"), {})
            direct = analysis.get("direct_question") if isinstance(analysis, dict) else None
            if not isinstance(direct, dict):
                direct = {}
            eligible = direct.get("eligible")
            predicted = direct.get("predicted")
            detector_version = str(direct.get("detector_version") or "").strip()
            versioned_snapshot = (
                isinstance(eligible, bool)
                and isinstance(predicted, bool)
                and bool(detector_version)
            )
            # A versioned eligible=false snapshot means the detector was
            # explicitly not active for this row (for example AI_FORBIDDEN).
            # It is outside the metric population, not missing evidence.
            if versioned_snapshot and eligible is False:
                continue
            has_prediction = versioned_snapshot and eligible is True
            rows.append({
                "kind": "direct_question",
                "session_id": segment["session_id"],
                "space_id": segment["space_id"],
                "profile": session["space_profile"],
                "event_id": segment["id"],
                "timestamp": segment["created_at"],
                "reviewer": "",
                "label_source": "",
                "predicted": predicted if has_prediction else None,
                "actual": None,
                "prediction_unavailable": not has_prediction,
                "system": {
                    "channel": segment.get("channel") or "",
                    "provider": segment.get("provider") or "",
                    "source": segment.get("source") or "",
                    "text": segment.get("text") or "",
                    "direct_question_prediction": direct,
                },
                "notes": "",
            })

        for raw in items:
            item = dict(raw)
            session = session_map[item["session_id"]]
            prediction = _json(item.get("prediction_json"), {})
            # v10 freezes AI_EXTRACTED candidates before review. For historical
            # pre-v10 rows, the current row is usable as a prediction only if it
            # is still unreviewed. Once a legacy row has been confirmed/edited/
            # rejected, its current type/state are post-review truth and must
            # never be backfilled into predicted_*.
            legacy_unreviewed = item.get("review_status") == "AI_EXTRACTED" and not prediction
            predicted_type = (
                str(prediction.get("type") or "")
                if prediction
                else str(item.get("type") or "") if legacy_unreviewed else ""
            )
            predicted_state = (
                str(prediction.get("state") or "")
                if prediction
                else str(item.get("state") or "") if legacy_unreviewed else ""
            )
            rows.append({
                "kind": "truth_item",
                "session_id": item["session_id"],
                "space_id": item["space_id"],
                "profile": session["space_profile"],
                "event_id": item["id"],
                "timestamp": item["created_at"],
                "reviewer": "",
                "label_source": "",
                "predicted_type": predicted_type or None,
                "actual_type": None,
                "predicted_state": predicted_state or None,
                "actual_state": None,
                "prediction_unavailable": not bool(predicted_type and predicted_state),
                "system": {
                    "review_status": item["review_status"],
                    "epistemic_status": item["epistemic_status"],
                    "owner_id": item["owner_id"],
                    "due_at": item["due_at"],
                    "source_refs": _json(item["source_refs_json"], []),
                    "title": item["title"],
                    "prediction": prediction,
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
                "label_source": "",
                "writeback_accurate": None,
                "notes": "",
            })
            rows.append({
                "kind": "session_outcome",
                "session_id": session["id"],
                "space_id": session["space_id"],
                "profile": session["space_profile"],
                "reviewer": "",
                "label_source": "",
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

    db = Path(args.db)
    out = Path(args.out)
    # A human-label seed contains potentially private transcript excerpts. Never
    # destroy the source DB or overwrite an existing, possibly reviewed, seed.
    if db.resolve() == out.resolve():
        parser.error("--out must not overwrite the source product.db")
    if out.exists():
        parser.error("--out already exists; choose a new path to preserve labels")

    rows = export_rows(db, space_id=args.space_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also protects against a race between the check and open.
    with out.open("x", encoding="utf-8") as fh:
        fh.write("# UNLABELED REVIEW SEED — fill reviewer + label_source + label fields before evaluation.\n")
        fh.write("# For stable review use label_source=INDEPENDENT_HUMAN_REVIEW for independent reviewers.\n")
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
