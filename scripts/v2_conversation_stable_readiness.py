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
from datetime import datetime
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


_PLACEHOLDERS = {"", "REPLACE", "TBD", "PLACEHOLDER"}


def _clean_token(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.upper() in _PLACEHOLDERS else text


def _parse_iso8601(value: Any) -> datetime | None:
    text = _clean_token(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _manifest_cohort(
    pilot_manifest: dict[str, Any],
    required_profiles: list[str],
    *,
    cross_session_space_min_sessions: int,
) -> dict[str, Any]:
    profiles = pilot_manifest.get("profiles")
    errors: list[str] = []
    if not isinstance(profiles, dict):
        profiles = {}
        errors.append("profiles must be an object")

    unexpected = sorted(set(str(key) for key in profiles) - set(required_profiles))
    if unexpected:
        errors.append(f"unexpected profiles: {', '.join(unexpected)}")

    session_index: dict[str, dict[str, str]] = {}
    stats: dict[str, dict[str, int]] = {}

    for profile in required_profiles:
        block = profiles.get(profile)
        entries = block.get("sessions") if isinstance(block, dict) else None
        if not isinstance(entries, list):
            errors.append(f"{profile}: sessions must be a list")
            entries = []

        users: set[str] = set()
        session_ids: set[str] = set()
        space_sessions: dict[str, set[str]] = {}

        for index, raw in enumerate(entries, start=1):
            if not isinstance(raw, dict):
                errors.append(f"{profile} session #{index}: entry must be an object")
                continue
            session_id = _clean_token(raw.get("session_id"))
            space_id = _clean_token(raw.get("space_id"))
            user_ref = _clean_token(raw.get("user_ref"))
            if not session_id or not space_id or not user_ref:
                errors.append(
                    f"{profile} session #{index}: session_id, space_id and user_ref are required"
                )
                continue

            current = {
                "profile": profile,
                "space_id": space_id,
                "user_ref": user_ref,
            }
            previous = session_index.get(session_id)
            if previous:
                errors.append(
                    f"duplicate session_id {session_id}: "
                    f"{previous['profile']}/{previous['space_id']} and {profile}/{space_id}"
                )
                continue

            session_index[session_id] = current
            session_ids.add(session_id)
            users.add(user_ref.casefold())
            space_sessions.setdefault(space_id, set()).add(session_id)

        stats[profile] = {
            "distinct_users": len(users),
            "sessions": len(session_ids),
            "cross_session_spaces": sum(
                1
                for ids in space_sessions.values()
                if len(ids) >= cross_session_space_min_sessions
            ),
        }

    return {
        "errors": errors,
        "session_index": session_index,
        "stats": stats,
    }


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

    required_report_contract = str(policy.get("human_report_contract_version") or "")
    add(
        "human_report_contract_version",
        str(human_report.get("report_contract_version") or "") == required_report_contract,
        actual=human_report.get("report_contract_version"),
        required=required_report_contract,
    )
    required_sample_unit = str(policy.get("metric_sample_unit") or "")
    human_sample_unit = str(
        ((human_report.get("metric_population") or {}).get("sample_unit") or "")
    )
    add(
        "metric_sample_unit_contract",
        required_sample_unit == "UNIQUE_EVENT_PER_METRIC"
        and str(policy.get("duplicate_event_metric_policy") or "") == "FAIL_CLOSED",
        actual={
            "metric_sample_unit": required_sample_unit,
            "duplicate_event_metric_policy": policy.get("duplicate_event_metric_policy"),
        },
        required={
            "metric_sample_unit": "UNIQUE_EVENT_PER_METRIC",
            "duplicate_event_metric_policy": "FAIL_CLOSED",
        },
        reason=(
            "Stable min_n is a unique product event × metric floor. Reviewer/source annotation "
            "multiplicity must never increase sample size."
        ),
    )
    add(
        "human_report_sample_unit",
        human_sample_unit == required_sample_unit == "UNIQUE_EVENT_PER_METRIC",
        actual=human_sample_unit,
        required=required_sample_unit or "UNIQUE_EVENT_PER_METRIC",
    )

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

    required_manifest_contract = str(policy.get("pilot_manifest_contract_version") or "")
    add(
        "pilot_manifest_contract_version",
        str(pilot_manifest.get("contract_version") or "") == required_manifest_contract,
        actual=pilot_manifest.get("contract_version"),
        required=required_manifest_contract,
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

    period = pilot_manifest.get("period") or {}
    period_start = _parse_iso8601(period.get("started_at") if isinstance(period, dict) else None)
    period_end = _parse_iso8601(period.get("ended_at") if isinstance(period, dict) else None)
    period_valid = bool(period_start and period_end and period_start <= period_end)
    add(
        "pilot_period_valid",
        period_valid,
        actual=period if isinstance(period, dict) else None,
        required="timezone-aware ISO-8601 started_at <= ended_at",
    )

    required_profiles = [str(value) for value in (policy.get("profiles_required") or {})]
    raw_cross_session_min = policy.get("cross_session_space_min_sessions")
    cross_session_min_valid = (
        isinstance(raw_cross_session_min, int)
        and not isinstance(raw_cross_session_min, bool)
        and raw_cross_session_min >= 3
    )
    add(
        "cross_session_space_min_sessions_contract",
        cross_session_min_valid,
        actual=raw_cross_session_min,
        required="integer >= 3",
        reason=(
            "Canonical Stable Gate defines a cross-session Space as at least 3 authorized Sessions "
            "in that same Space. Policy may become stricter, but must not silently lower this floor."
        ),
    )
    # Invalid policy must fail closed. Use a sentinel larger than any practical
    # pilot rather than falling back to the historical buggy >=2 behavior.
    cross_session_space_min_sessions = (
        int(raw_cross_session_min) if cross_session_min_valid else 10**9
    )
    manifest_cohort = _manifest_cohort(
        pilot_manifest,
        required_profiles,
        cross_session_space_min_sessions=cross_session_space_min_sessions,
    )
    add(
        "pilot_manifest_cohort_integrity",
        not manifest_cohort["errors"],
        actual=manifest_cohort["errors"],
        required="enumerated unique session_id/space_id/user_ref entries",
    )

    for profile, requirements in (policy.get("profiles_required") or {}).items():
        actual_stats = manifest_cohort["stats"].get(profile) or {}
        for field, minimum in requirements.items():
            value = actual_stats.get(field, 0)
            add(
                f"profile:{profile}:{field}",
                value >= int(minimum),
                actual=value,
                required=f">={minimum}",
            )

    human_cohort = human_report.get("cohort") or {}
    cohort_status = str(human_cohort.get("status") or "") if isinstance(human_cohort, dict) else ""
    cohort_errors = human_cohort.get("errors") if isinstance(human_cohort, dict) else []
    add(
        "human_report_cohort_complete",
        cohort_status == "COMPLETE" and not cohort_errors,
        actual={"status": cohort_status, "errors": cohort_errors},
        required={"status": "COMPLETE", "errors": []},
    )

    metric_profiles = [str(value) for value in (policy.get("metric_profiles") or required_profiles)]
    manifest_index = manifest_cohort["session_index"]
    human_sessions = human_cohort.get("sessions") if isinstance(human_cohort, dict) else None
    if not isinstance(human_sessions, list):
        human_sessions = []

    unauthorized: list[str] = []
    out_of_scope: list[str] = []
    for raw in human_sessions:
        if not isinstance(raw, dict):
            unauthorized.append("<invalid human cohort row>")
            continue
        session_id = _clean_token(raw.get("session_id"))
        profile = _clean_token(raw.get("profile")).upper()
        space_id = _clean_token(raw.get("space_id"))
        authorized = manifest_index.get(session_id)
        if not authorized or authorized["profile"] != profile or authorized["space_id"] != space_id:
            unauthorized.append(f"{session_id}:{profile}:{space_id}")
        if profile not in metric_profiles:
            out_of_scope.append(f"{session_id}:{profile}")

    add(
        "human_report_sessions_authorized",
        bool(human_sessions) and not unauthorized,
        actual={"sessions": len(human_sessions), "unauthorized": unauthorized},
        required="every labeled session must match manifest session_id/profile/space_id",
    )
    add(
        "human_report_profiles_in_stable_scope",
        not out_of_scope,
        actual=out_of_scope,
        required=metric_profiles,
    )

    metrics_by_profile_source = human_report.get("metrics_by_profile_and_label_source") or {}
    for name, rule in (policy.get("metrics") or {}).items():
        allowed_sources = [str(value) for value in (rule.get("allowed_label_sources") or [])]
        source_entries: list[tuple[str, str, float, int]] = []
        population_counts: dict[str, dict[str, int]] = {}
        for profile in metric_profiles:
            profile_map = metrics_by_profile_source.get(profile) or {}
            population_counts[profile] = {}
            for source in allowed_sources:
                entry = (profile_map.get(source) or {}).get(name) or {}
                source_value = _finite_number(entry.get("value"))
                source_n = entry.get("n")
                valid_n = (
                    int(source_n)
                    if isinstance(source_n, int) and not isinstance(source_n, bool) and source_n > 0
                    else 0
                )
                population_counts[profile][source] = valid_n
                if source_value is not None and valid_n > 0:
                    source_entries.append((profile, source, source_value, valid_n))

        n = sum(item[3] for item in source_entries)
        value = (
            sum(item[2] * item[3] for item in source_entries) / n
            if n
            else None
        )
        if value is not None:
            value = round(value, 6)
        add(
            f"metric:{name}:population",
            bool(source_entries),
            actual=population_counts,
            required={
                "profiles": metric_profiles,
                "label_sources": allowed_sources,
            },
            reason=(
                "Stable metrics count only explicitly allowed label sources from the policy's target profiles; "
                "other Conversation profiles cannot inflate the denominator or score."
            ),
        )
        profile_coverage = {
            profile: sum(population_counts.get(profile, {}).values())
            for profile in metric_profiles
        }
        add(
            f"metric:{name}:profile_coverage",
            all(value > 0 for value in profile_coverage.values()),
            actual=profile_coverage,
            required={profile: ">=1 allowed-source sample" for profile in metric_profiles},
            reason=(
                "Each launch-wedge profile must contribute real metric evidence; a strong score from one profile "
                "cannot stand in for an entirely unmeasured Project Sync or Design Review experience."
            ),
        )
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
        "pilot_cohort": {
            "manifest_contract_version": pilot_manifest.get("contract_version"),
            "human_report_contract_version": human_report.get("report_contract_version"),
            "profile_stats": manifest_cohort["stats"],
            "authorized_sessions": len(manifest_cohort["session_index"]),
            "human_labeled_sessions": len(human_sessions),
            "metric_profiles": metric_profiles,
            "cross_session_space_min_sessions": cross_session_space_min_sessions,
        },
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
            "PASS only permits a stable-release review. Stable min_n counts unique product event × metric observations, not reviewer annotations. Human-label sessions must match the authorized pilot "
            "manifest by session/profile/space; profile floors are derived from enumerated pseudonymous cohort entries, "
            f"a cross-session Space requires at least {cross_session_space_min_sessions} authorized Sessions in that same Space, "
            "and Stable metrics count only target profiles plus label sources explicitly allowed by policy. "
            "user_ref is a local pseudonym and not identity proof. Packaging/signing/release gates remain independent, "
            "and this tool does not establish PMF or universal user value."
        ),
    }


def markdown(report: dict[str, Any]) -> str:
    cohort = report.get("pilot_cohort") or {}
    lines = [
        "# Chengzhu v2 Stable Promotion Evidence Gate",
        "",
        f"- Status: **{report['status']}**",
        f"- Policy: **{report.get('policy_version') or 'unknown'}**",
        f"- Authorized manifest Sessions: **{cohort.get('authorized_sessions', 0)}**",
        f"- Human-labeled Sessions: **{cohort.get('human_labeled_sessions', 0)}**",
        f"- Metric Profiles: **{', '.join(cohort.get('metric_profiles') or []) or 'none'}**",
        f"- Cross-session Space minimum Sessions: **{cohort.get('cross_session_space_min_sessions', 'unknown')}**",
        f"- Failed checks: **{report['checks_failed']} / {report['checks_total']}**",
        "- V2_STABLE_RELEASE: **FALSE**",
        "- PMF_PROVEN: **FALSE**",
        "",
        "## Derived pilot profile counts",
        "",
        "| Profile | Distinct pseudonymous users | Sessions | Cross-session Spaces |",
        "| --- | ---: | ---: | ---: |",
    ]
    for profile, stats in (cohort.get("profile_stats") or {}).items():
        lines.append(
            f"| {profile} | {stats.get('distinct_users', 0)} | "
            f"{stats.get('sessions', 0)} | {stats.get('cross_session_spaces', 0)} |"
        )
    lines += [
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
