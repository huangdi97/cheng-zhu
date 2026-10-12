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

Examples:
  python scripts/v2_conversation_human_eval.py labels.jsonl --out report.json
  python scripts/v2_conversation_human_eval.py in-product.jsonl independent.jsonl --out report.json
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


REPORT_CONTRACT_VERSION = "v2.0-R1-human-eval-4"


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


def _cognitive_delta(row: dict[str, Any]) -> float | None:
    """Human rubric permits numeric -2..2 only, excluding booleans and NaN."""
    value = row.get("cognitive_load_delta")
    if type(value) not in (int, float) or not -2 <= value <= 2:
        return None
    return float(value) if math.isfinite(value) else None


def _reject_nonfinite_json(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value!r} is not allowed")


def load_rows(
    path: Path,
    *,
    seen: set[tuple[str, str, str, str]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen = seen if seen is not None else set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        try:
            row = json.loads(text, parse_constant=_reject_nonfinite_json)
        except ValueError as exc:
            raise ValueError(f"line {lineno}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {lineno}: row must be an object")
        kind = str(row.get("kind") or "")
        if kind not in ALLOWED_KINDS:
            raise ValueError(f"line {lineno}: unsupported kind {kind!r}")
        if str(row.get("reviewer") or "").strip().upper() in {"", "REPLACE", "TBD", "PLACEHOLDER"}:
            raise ValueError(f"line {lineno}: reviewer is required")
        if str(row.get("session_id") or "").strip().upper() in {"", "REPLACE", "TBD", "PLACEHOLDER"}:
            raise ValueError(f"line {lineno}: session_id is required")
        if kind == "session_outcome" and row.get("cognitive_load_delta") is not None:
            if _cognitive_delta(row) is None:
                raise ValueError(f"line {lineno}: cognitive_load_delta must be a number in [-2, 2]")
        # One reviewer must not inflate a metric by pasting the same event twice.
        # Different reviewers can still independently label the same event.
        event_id = str(row.get("event_id") or "").strip()
        if event_id or kind in {"continue", "session_outcome"}:
            key = (
                str(row["reviewer"]).strip().casefold(),
                str(row["session_id"]).strip(),
                kind,
                event_id,
            )
            if key in seen:
                raise ValueError(f"line {lineno}: duplicate label for reviewer/session/kind/event")
            seen.add(key)
        rows.append(row)
    return rows


def _label_source(row: dict[str, Any]) -> str:
    explicit = str(row.get("label_source") or "").strip().upper()
    if explicit:
        return explicit
    if str(row.get("reviewer") or "").strip().upper() == "IN_PRODUCT_SELF_REPORT":
        return "LOCAL_IN_PRODUCT_EXPLICIT_SELF_REPORT"
    return "UNSPECIFIED"


DECISION_COMMITMENT_PREDICTED_TYPES = {"Decision", "Commitment", "Task"}


def _runtime_origin(row: dict[str, Any]) -> dict[str, Any]:
    system = row.get("system")
    origin = system.get("origin") if isinstance(system, dict) else None
    return origin if isinstance(origin, dict) else {}


def _is_auto_runtime(row: dict[str, Any]) -> bool:
    origin = _runtime_origin(row)
    return bool(
        origin.get("kind") == "TRANSCRIPT_AUTO"
        and str(origin.get("transcript_segment_id") or "").strip()
    )


def _cohort_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe which local Session/Profile/Space each label row belongs to.

    This is consistency provenance, not identity proof. Stable-readiness binds
    these session tuples to an authorized pilot manifest rather than accepting
    an unrelated human-report beside unrelated pilot counts.
    """
    sessions: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    for index, row in enumerate(rows, start=1):
        session_id = str(row.get("session_id") or "").strip()
        profile = str(row.get("profile") or "").strip().upper()
        space_id = str(row.get("space_id") or "").strip()
        if not session_id:
            errors.append(f"row {index}: missing session_id")
            continue
        if not profile:
            errors.append(f"session {session_id}: missing profile")
        if not space_id:
            errors.append(f"session {session_id}: missing space_id")
        if not profile or not space_id:
            continue
        current = {"session_id": session_id, "profile": profile, "space_id": space_id}
        previous = sessions.get(session_id)
        if previous and previous != current:
            errors.append(
                f"session {session_id}: inconsistent profile/space "
                f"({previous['profile']}/{previous['space_id']} vs {profile}/{space_id})"
            )
            continue
        sessions[session_id] = current

    ordered = [sessions[key] for key in sorted(sessions)]
    profiles: dict[str, dict[str, list[str]]] = {}
    for entry in ordered:
        profile = entry["profile"]
        bucket = profiles.setdefault(profile, {"session_ids": [], "space_ids": []})
        bucket["session_ids"].append(entry["session_id"])
        if entry["space_id"] not in bucket["space_ids"]:
            bucket["space_ids"].append(entry["space_id"])
    for bucket in profiles.values():
        bucket["space_ids"].sort()

    return {
        "status": "COMPLETE" if not errors and len(ordered) > 0 else "INCOMPLETE",
        "sessions": ordered,
        "profiles": dict(sorted(profiles.items())),
        "errors": errors,
    }


def aggregate(
    rows: list[dict[str, Any]],
    *,
    include_source_breakdown: bool = True,
) -> dict[str, Any]:
    by_kind = Counter(str(row["kind"]) for row in rows)

    all_guidance_rows = [r for r in rows if r["kind"] == "guidance"]
    guidance_rows = [r for r in all_guidance_rows if _is_auto_runtime(r)]
    proactive = [r for r in guidance_rows if str(r.get("guidance_class") or "") == "PROACTIVE"]
    recall = [r for r in guidance_rows if str(r.get("guidance_class") or "") == "RECALL"]

    useful_labeled = [r for r in proactive if _boolean(r, "useful") is not None]
    interruption_labeled = [r for r in proactive if _boolean(r, "interruption_regret") is not None]
    source_labeled = [r for r in guidance_rows if _boolean(r, "source_correct") is not None]
    recall_labeled = [r for r in recall if _boolean(r, "recall_correct") is not None]

    all_silence_rows = [r for r in rows if r["kind"] == "silence"]
    silence_rows = [
        r for r in all_silence_rows
        if _is_auto_runtime(r)
        and str(_runtime_origin(r).get("decision_class") or "") == "ARBITER"
        and _boolean(r, "silence_correct") is not None
    ]

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
    decision_commitment_rows = [
        r for r in truth_rows
        if str(r.get("predicted_type") or "") in DECISION_COMMITMENT_PREDICTED_TYPES
    ]
    truth_correct = sum(
        1 for r in decision_commitment_rows
        if r["predicted_type"] == r["actual_type"]
        and r["predicted_state"] == r["actual_state"]
    )

    continue_rows = [r for r in rows if r["kind"] == "continue" and _boolean(r, "writeback_accurate") is not None]

    outcome_rows = [r for r in rows if r["kind"] == "session_outcome"]
    cognitive = [
        value
        for r in outcome_rows
        if (value := _cognitive_delta(r)) is not None
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
            "value": _rate(truth_correct, len(decision_commitment_rows)),
            "n": len(decision_commitment_rows),
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
    report = {
        "report_contract_version": REPORT_CONTRACT_VERSION,
        "evidence_type": "HUMAN_LABELED_CONVERSATION_EVAL",
        "rows": len(rows),
        "cohort": _cohort_summary(rows),
        "rows_by_kind": dict(sorted(by_kind.items())),
        "metric_population": {
            "auto_guidance_rows": len(guidance_rows),
            "excluded_non_auto_guidance_rows": len(all_guidance_rows) - len(guidance_rows),
            "arbiter_silence_rows": len(silence_rows),
            "excluded_non_arbiter_or_non_auto_silence_rows": len(all_silence_rows) - len(silence_rows),
            "decision_commitment_task_predicted_rows": len(decision_commitment_rows),
            "excluded_other_truth_item_rows": len(truth_rows) - len(decision_commitment_rows),
        },
        "metrics": metrics,
        "status": "HAS_HUMAN_LABELS" if rows and labeled_metric_count else "INSUFFICIENT_EVIDENCE",
        "claims": {
            "REAL_CONVERSATION_USER_EVIDENCE_AVAILABLE": False,
            "HUMAN_LABELS_AVAILABLE": bool(rows and labeled_metric_count),
            "PMF_PROVEN": False,
        },
        "interpretation": (
            "Stable live-guidance metrics use only v12 capture-time TRANSCRIPT_AUTO provenance; manual Guidance Lab and pre-v12 Guidance rows are excluded. Useful Silence counts only ARBITER decisions, not policy/profile/provenance-forced silence. Decision/Commitment State Precision is scoped to predictions of Decision/Commitment/Task. Human labels still do not verify external-user identity, and no threshold here upgrades PMF or release status."
        ),
    }
    if include_source_breakdown:
        by_source = Counter(_label_source(row) for row in rows)
        report["rows_by_label_source"] = dict(sorted(by_source.items()))
        report["metrics_by_label_source"] = {
            source: aggregate(
                [row for row in rows if _label_source(row) == source],
                include_source_breakdown=False,
            )["metrics"]
            for source in sorted(by_source)
        }

        profiles = sorted({
            str(row.get("profile") or "").strip().upper()
            for row in rows
            if str(row.get("profile") or "").strip()
        })
        report["metrics_by_profile"] = {
            profile: aggregate(
                [
                    row for row in rows
                    if str(row.get("profile") or "").strip().upper() == profile
                ],
                include_source_breakdown=False,
            )["metrics"]
            for profile in profiles
        }
        report["metrics_by_profile_and_label_source"] = {
            profile: {
                source: aggregate(
                    [
                        row for row in rows
                        if str(row.get("profile") or "").strip().upper() == profile
                        and _label_source(row) == source
                    ],
                    include_source_breakdown=False,
                )["metrics"]
                for source in sorted(by_source)
            }
            for profile in profiles
        }
    return report


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
    parser.add_argument(
        "labels",
        nargs="+",
        help="one or more human-labeled JSONL files; duplicate reviewer/session/kind/event labels are rejected across files",
    )
    parser.add_argument("--out", default="")
    parser.add_argument("--markdown-out", default="")
    args = parser.parse_args()

    label_paths = [Path(value) for value in args.labels]
    output_paths = [Path(path) for path in (args.out, args.markdown_out) if path]
    resolved = [*(path.resolve() for path in label_paths), *(path.resolve() for path in output_paths)]
    if len(resolved) != len(set(resolved)):
        parser.error("evaluation outputs must not overwrite labels, labels must be distinct, and outputs must differ")

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for labels_path in label_paths:
        rows.extend(load_rows(labels_path, seen=seen))
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
