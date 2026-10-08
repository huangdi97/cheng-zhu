#!/usr/bin/env python3
"""Aggregate human-labeled Chengzhu v2 Conversation evaluation JSONL.

This tool never invents labels and never turns missing labels into PASS.
It reports a metric only when at least one human-labeled denominator exists.

Supported row kinds:
  guidance       — proactive/direct/recall guidance quality
  silence        — whether staying silent was correct
  direct_question
  truth_item
  continue
  session_outcome

Example:
  python scripts/v2_conversation_human_eval.py labels.jsonl --out report.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


ALLOWED_KINDS = {
    "guidance",
    "silence",
    "direct_question",
    "truth_item",
    "continue",
    "session_outcome",
}


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 6) if den else None


def _boolean(row: dict[str, Any], key: str) -> bool | None:
    value = row.get(key)
    return value if isinstance(value, bool) else None


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {lineno}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {lineno}: row must be an object")
        kind = str(row.get("kind") or "")
        if kind not in ALLOWED_KINDS:
            raise ValueError(f"line {lineno}: unsupported kind {kind!r}")
        if not str(row.get("reviewer") or "").strip():
            raise ValueError(f"line {lineno}: reviewer is required")
        if not str(row.get("session_id") or "").strip():
            raise ValueError(f"line {lineno}: session_id is required")
        rows.append(row)
    return rows


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind = Counter(str(row["kind"]) for row in rows)

    guidance_rows = [r for r in rows if r["kind"] == "guidance"]
    proactive = [r for r in guidance_rows if str(r.get("guidance_class") or "") == "PROACTIVE"]
    recall = [r for r in guidance_rows if str(r.get("guidance_class") or "") == "RECALL"]

    useful_labeled = [r for r in proactive if _boolean(r, "useful") is not None]
    interruption_labeled = [r for r in proactive if _boolean(r, "interruption_regret") is not None]
    source_labeled = [r for r in guidance_rows if _boolean(r, "source_correct") is not None]
    recall_labeled = [r for r in recall if _boolean(r, "recall_correct") is not None]

    silence_rows = [r for r in rows if r["kind"] == "silence" and _boolean(r, "silence_correct") is not None]

    dq_rows = [r for r in rows if r["kind"] == "direct_question"]
    dq_labeled = [
        r for r in dq_rows
        if isinstance(r.get("predicted"), bool) and isinstance(r.get("actual"), bool)
    ]
    tp = sum(1 for r in dq_labeled if r["predicted"] and r["actual"])
    fp = sum(1 for r in dq_labeled if r["predicted"] and not r["actual"])
    fn = sum(1 for r in dq_labeled if not r["predicted"] and r["actual"])

    truth_rows = [
        r for r in rows
        if r["kind"] == "truth_item"
        and str(r.get("predicted_type") or "")
        and str(r.get("actual_type") or "")
        and str(r.get("predicted_state") or "")
        and str(r.get("actual_state") or "")
    ]
    truth_correct = sum(
        1 for r in truth_rows
        if r["predicted_type"] == r["actual_type"]
        and r["predicted_state"] == r["actual_state"]
    )

    continue_rows = [r for r in rows if r["kind"] == "continue" and _boolean(r, "writeback_accurate") is not None]

    outcome_rows = [r for r in rows if r["kind"] == "session_outcome"]
    cognitive = [
        float(r["cognitive_load_delta"])
        for r in outcome_rows
        if isinstance(r.get("cognitive_load_delta"), (int, float))
    ]
    reuse = [r for r in outcome_rows if _boolean(r, "would_reuse_space") is not None]

    metrics = {
        "opportunity_precision": {
            "value": _rate(sum(1 for r in useful_labeled if r["useful"]), len(useful_labeled)),
            "n": len(useful_labeled),
        },
        "interruption_regret": {
            "value": _rate(sum(1 for r in interruption_labeled if r["interruption_regret"]), len(interruption_labeled)),
            "n": len(interruption_labeled),
        },
        "source_attribution_accuracy": {
            "value": _rate(sum(1 for r in source_labeled if r["source_correct"]), len(source_labeled)),
            "n": len(source_labeled),
        },
        "recall_precision": {
            "value": _rate(sum(1 for r in recall_labeled if r["recall_correct"]), len(recall_labeled)),
            "n": len(recall_labeled),
        },
        "useful_silence_rate": {
            "value": _rate(sum(1 for r in silence_rows if r["silence_correct"]), len(silence_rows)),
            "n": len(silence_rows),
        },
        "direct_question_precision": {
            "value": _rate(tp, tp + fp),
            "n": tp + fp,
        },
        "direct_question_recall": {
            "value": _rate(tp, tp + fn),
            "n": tp + fn,
        },
        "decision_commitment_state_precision": {
            "value": _rate(truth_correct, len(truth_rows)),
            "n": len(truth_rows),
        },
        "continue_writeback_accuracy": {
            "value": _rate(sum(1 for r in continue_rows if r["writeback_accurate"]), len(continue_rows)),
            "n": len(continue_rows),
        },
        "mean_cognitive_load_delta": {
            "value": round(sum(cognitive) / len(cognitive), 6) if cognitive else None,
            "n": len(cognitive),
        },
        "space_reuse_intent_rate": {
            "value": _rate(sum(1 for r in reuse if r["would_reuse_space"]), len(reuse)),
            "n": len(reuse),
        },
    }

    labeled_metric_count = sum(1 for value in metrics.values() if value["n"] > 0)
    return {
        "evidence_type": "HUMAN_LABELED_CONVERSATION_EVAL",
        "rows": len(rows),
        "rows_by_kind": dict(sorted(by_kind.items())),
        "metrics": metrics,
        "status": "HAS_HUMAN_LABELS" if rows and labeled_metric_count else "INSUFFICIENT_EVIDENCE",
        "claims": {
            "REAL_CONVERSATION_USER_EVIDENCE_AVAILABLE": bool(rows and labeled_metric_count),
            "PMF_PROVEN": False,
        },
        "interpretation": (
            "Metrics are descriptive human-label aggregates. No threshold in this script upgrades PMF or stable-release status."
        ),
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Chengzhu v2 Conversation Human-label Evaluation",
        "",
        f"- Status: **{report['status']}**",
        f"- Human-labeled rows: **{report['rows']}**",
        "- PMF_PROVEN: **FALSE**",
        "",
        "| Metric | Value | n |",
        "| --- | ---: | ---: |",
    ]
    for name, entry in report["metrics"].items():
        value = "N/A" if entry["value"] is None else str(entry["value"])
        lines.append(f"| {name} | {value} | {entry['n']} |")
    lines += [
        "",
        "> Missing labels stay N/A. This report is descriptive evidence; it does not convert a small pilot into PMF proof.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("labels", help="human-labeled JSONL")
    parser.add_argument("--out", default="")
    parser.add_argument("--markdown-out", default="")
    args = parser.parse_args()

    rows = load_rows(Path(args.labels))
    report = aggregate(rows)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
