#!/usr/bin/env python3
"""Evaluate whether Conversation v2 has enough product evidence for stable review.

This script does not publish a release and does not prove PMF. It combines:
1) the human-label aggregate report,
2) a local pilot manifest with explicit attestations,
3) a versioned acceptance policy.

A PASS means only PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def _finite_number(value: Any) -> float | None:
    if type(value) not in (int, float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def evaluate(
    human_report: dict[str, Any],
    pilot_manifest: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, *, actual: Any = None, required: Any = None, reason: str = "") -> None:
        checks.append({
            "name": name,
            "passed": bool(passed),
            "actual": actual,
            "required": required,
            "reason": reason,
        })

    add(
        "human_report_evidence_type",
        human_report.get("evidence_type") == "HUMAN_LABELED_CONVERSATION_EVAL",
        actual=human_report.get("evidence_type"),
        required="HUMAN_LABELED_CONVERSATION_EVAL",
    )
    add(
        "human_labels_available",
        bool((human_report.get("claims") or {}).get("HUMAN_LABELS_AVAILABLE")),
        actual=(human_report.get("claims") or {}).get("HUMAN_LABELS_AVAILABLE"),
        required=True,
    )

    manifest_type = str(pilot_manifest.get("evidence_type") or "")
    add(
        "pilot_manifest_type",
        manifest_type == "AUTHORIZED_REAL_CONVERSATION_PILOT",
        actual=manifest_type,
        required="AUTHORIZED_REAL_CONVERSATION_PILOT",
    )

    attestations = set(str(x) for x in pilot_manifest.get("attestations") or [])
    for required in policy.get("required_attestations") or []:
        add(
            f"attestation:{required}",
            required in attestations,
            actual=required in attestations,
            required=True,
        )

    profiles = pilot_manifest.get("profiles") or {}
    for profile, requirements in (policy.get("profiles_required") or {}).items():
        actual = profiles.get(profile) or {}
        for field, minimum in requirements.items():
            value = actual.get(field)
            passed = isinstance(value, int) and not isinstance(value, bool) and value >= int(minimum)
            add(
                f"profile:{profile}:{field}",
                passed,
                actual=value,
                required=f">={minimum}",
            )

    metrics = human_report.get("metrics") or {}
    for name, rule in (policy.get("metrics") or {}).items():
        entry = metrics.get(name) or {}
        value = _finite_number(entry.get("value"))
        n = entry.get("n")
        min_n = int(rule.get("min_n") or 0)
        add(
            f"metric:{name}:sample_size",
            isinstance(n, int) and not isinstance(n, bool) and n >= min_n,
            actual=n,
            required=f">={min_n}",
        )
        direction = str(rule.get("direction") or "")
        threshold = _finite_number(rule.get("threshold"))
        metric_pass = False
        if value is not None and threshold is not None:
            if direction == "gte":
                metric_pass = value >= threshold
            elif direction == "lte":
                metric_pass = value <= threshold
        add(
            f"metric:{name}:threshold",
            metric_pass,
            actual=value,
            required=f"{direction} {threshold}",
        )

    critical_incidents = pilot_manifest.get("critical_incidents")
    add(
        "critical_incidents_zero",
        critical_incidents == 0,
        actual=critical_incidents,
        required=0,
    )

    all_passed = all(item["passed"] for item in checks)
    status = "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW" if all_passed else "NO_GO"
    failed = [item for item in checks if not item["passed"]]
    return {
        "policy_version": policy.get("policy_version"),
        "status": status,
        "checks_total": len(checks),
        "checks_failed": len(failed),
        "failed_checks": failed,
        "checks": checks,
        "claims": {
            "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW": all_passed,
            "V2_STABLE_RELEASE": False,
            "PMF_PROVEN": False,
        },
        "interpretation": (
            "PASS only permits a stable-release review. Packaging/signing/release gates remain independent, "
            "and this tool does not establish PMF or universal user value."
        ),
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Chengzhu v2 Stable Promotion Evidence Gate",
        "",
        f"- Status: **{report['status']}**",
        f"- Policy: **{report.get('policy_version') or 'unknown'}**",
        f"- Failed checks: **{report['checks_failed']} / {report['checks_total']}**",
        "- V2_STABLE_RELEASE: **FALSE**",
        "- PMF_PROVEN: **FALSE**",
        "",
        "| Check | Pass | Actual | Required |",
        "| --- | :---: | --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(
            f"| {item['name']} | {'YES' if item['passed'] else 'NO'} | "
            f"{item.get('actual')} | {item.get('required')} |"
        )
    lines += [
        "",
        "> Passing this gate means only that product evidence is strong enough to enter a separate stable release review.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("human_report", help="JSON output from v2_conversation_human_eval.py")
    parser.add_argument("pilot_manifest", help="authorized local pilot manifest JSON")
    parser.add_argument(
        "--policy",
        default="docs/evals/V2_CONVERSATION_STABLE_PROMOTION_POLICY.json",
    )
    parser.add_argument("--out", default="")
    parser.add_argument("--markdown-out", default="")
    args = parser.parse_args()

    human_path = Path(args.human_report)
    pilot_path = Path(args.pilot_manifest)
    policy_path = Path(args.policy)
    outputs = [Path(x) for x in (args.out, args.markdown_out) if x]
    inputs = [human_path.resolve(), pilot_path.resolve(), policy_path.resolve()]
    if any(out.resolve() in inputs for out in outputs):
        parser.error("outputs must not overwrite evidence inputs or policy")
    if len({out.resolve() for out in outputs}) != len(outputs):
        parser.error("outputs must be distinct")

    report = evaluate(
        _load_object(human_path),
        _load_object(pilot_path),
        _load_object(policy_path),
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(markdown(report), encoding="utf-8")
    return 0 if report["status"] != "NO_GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
