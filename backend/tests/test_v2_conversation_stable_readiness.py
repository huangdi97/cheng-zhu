import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "v2_conversation_stable_readiness.py"
POLICY = ROOT / "docs" / "evals" / "V2_CONVERSATION_STABLE_PROMOTION_POLICY.json"


def _module():
    spec = importlib.util.spec_from_file_location("v2_stable_readiness", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _policy():
    return json.loads(POLICY.read_text(encoding="utf-8"))


def _session_id(profile: str, index: int) -> str:
    prefix = "project" if profile == "PROJECT_SYNC" else "design"
    return f"cv-{prefix}-{index:02d}"


def _space_id(profile: str, index: int) -> str:
    prefix = "project" if profile == "PROJECT_SYNC" else "design"
    return f"cs-{prefix}-{index}"


def _human_report():
    policy = _policy()
    metrics = {}
    nested = {"PROJECT_SYNC": {}, "DESIGN_REVIEW": {}}

    for name, rule in policy["metrics"].items():
        threshold = rule["threshold"]
        total_n = int(rule["min_n"])
        project_n = max(1, total_n // 2)
        design_n = max(0, total_n - project_n)
        source = rule["allowed_label_sources"][0]

        metrics[name] = {"value": threshold, "n": total_n}
        nested["PROJECT_SYNC"].setdefault(source, {})[name] = {
            "value": threshold,
            "n": project_n,
        }
        nested["DESIGN_REVIEW"].setdefault(source, {})[name] = {
            "value": threshold,
            "n": design_n,
        }

    sessions = [
        {
            "session_id": _session_id("PROJECT_SYNC", 0),
            "profile": "PROJECT_SYNC",
            "space_id": _space_id("PROJECT_SYNC", 0),
        },
        {
            "session_id": _session_id("DESIGN_REVIEW", 0),
            "profile": "DESIGN_REVIEW",
            "space_id": _space_id("DESIGN_REVIEW", 0),
        },
    ]
    return {
        "report_contract_version": policy["human_report_contract_version"],
        "evidence_type": "HUMAN_LABELED_CONVERSATION_EVAL",
        "claims": {"HUMAN_LABELS_AVAILABLE": True, "PMF_PROVEN": False},
        "cohort": {
            "status": "COMPLETE",
            "sessions": sessions,
            "profiles": {
                "PROJECT_SYNC": {
                    "session_ids": [_session_id("PROJECT_SYNC", 0)],
                    "space_ids": [_space_id("PROJECT_SYNC", 0)],
                },
                "DESIGN_REVIEW": {
                    "session_ids": [_session_id("DESIGN_REVIEW", 0)],
                    "space_ids": [_space_id("DESIGN_REVIEW", 0)],
                },
            },
            "errors": [],
        },
        "metrics": metrics,
        "metrics_by_profile_and_label_source": nested,
    }


def _source_for(policy, metric: str) -> str:
    return policy["metrics"][metric]["allowed_label_sources"][0]


def _profile_sessions(profile: str, policy: dict):
    requirements = policy["profiles_required"][profile]
    count = int(requirements["sessions"])
    distinct_users = int(requirements["distinct_users"])
    cross_spaces = int(requirements["cross_session_spaces"])
    return [
        {
            "session_id": _session_id(profile, index),
            "space_id": _space_id(profile, index % cross_spaces),
            "user_ref": f"{profile.lower()}-user-{index % distinct_users}",
        }
        for index in range(count)
    ]


def _pilot():
    policy = _policy()
    return {
        "contract_version": policy["pilot_manifest_contract_version"],
        "evidence_type": "AUTHORIZED_REAL_CONVERSATION_PILOT",
        "period": {
            "started_at": "2026-10-01T09:00:00+08:00",
            "ended_at": "2026-10-11T18:00:00+08:00",
        },
        "attestations": [
            "AUTHORIZED_REAL_USE",
            "NO_SYNTHETIC_ROWS_IN_HUMAN_EVAL",
            "RAW_LABELS_KEPT_LOCAL",
            "NO_CRITICAL_PRIVACY_INCIDENT",
            "NO_KNOWN_DATA_LOSS",
        ],
        "profiles": {
            profile: {"sessions": _profile_sessions(profile, policy)}
            for profile in policy["profiles_required"]
        },
        "critical_incidents": 0,
    }


def _metric_entries(human: dict, policy: dict, metric: str):
    source = _source_for(policy, metric)
    return [
        human["metrics_by_profile_and_label_source"][profile][source][metric]
        for profile in policy["metric_profiles"]
    ]


def test_stable_readiness_pass_only_grants_release_review():
    module = _module()
    policy = _policy()
    report = module.evaluate(_human_report(), _pilot(), policy)
    assert report["status"] == "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW"
    assert report["claims"]["PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW"] is True
    assert report["claims"]["V2_STABLE_RELEASE"] is False
    assert report["claims"]["PMF_PROVEN"] is False
    assert report["pilot_cohort"]["profile_stats"]["PROJECT_SYNC"] == {
        "distinct_users": 5,
        "sessions": 20,
        "cross_session_spaces": 3,
    }
    assert report["pilot_cohort"]["cross_session_space_min_sessions"] == 3


def test_stable_readiness_fails_when_sample_size_is_insufficient():
    module = _module()
    policy = _policy()
    human = _human_report()
    entries = _metric_entries(human, policy, "opportunity_precision")
    entries[0]["n"] = 1
    entries[1]["n"] = 0
    report = module.evaluate(human, _pilot(), policy)
    assert report["status"] == "NO_GO"
    assert any(
        item["name"] == "metric:opportunity_precision:sample_size"
        for item in report["failed_checks"]
    )


def test_stable_readiness_fails_on_bad_quality_even_with_large_n():
    module = _module()
    policy = _policy()
    human = _human_report()
    for entry in _metric_entries(human, policy, "interruption_regret"):
        entry.update({"value": 0.5, "n": 100})
    report = module.evaluate(human, _pilot(), policy)
    assert report["status"] == "NO_GO"
    assert any(
        item["name"] == "metric:interruption_regret:threshold"
        for item in report["failed_checks"]
    )


def test_stable_readiness_fails_without_real_use_attestation():
    module = _module()
    policy = _policy()
    pilot = _pilot()
    pilot["attestations"].remove("AUTHORIZED_REAL_USE")
    report = module.evaluate(_human_report(), pilot, policy)
    assert report["status"] == "NO_GO"
    assert any(
        item["name"] == "attestation:AUTHORIZED_REAL_USE"
        for item in report["failed_checks"]
    )


def test_stable_readiness_derives_profile_floor_from_enumerated_sessions():
    module = _module()
    policy = _policy()
    pilot = _pilot()
    pilot["profiles"]["PROJECT_SYNC"]["sessions"] = pilot["profiles"]["PROJECT_SYNC"]["sessions"][:2]
    report = module.evaluate(_human_report(), pilot, policy)
    assert report["status"] == "NO_GO"
    assert any(
        item["name"] == "profile:PROJECT_SYNC:sessions"
        for item in report["failed_checks"]
    )


def test_two_session_spaces_do_not_satisfy_canonical_cross_session_floor():
    module = _module()
    policy = _policy()
    pilot = _pilot()
    sessions = pilot["profiles"]["PROJECT_SYNC"]["sessions"]

    # Preserve 20 Sessions, 5 pseudonymous users and exactly three repeated
    # Spaces, but give each repeated Space only 2 Sessions. The historical v4
    # bug counted these as cross-session and could therefore pass this floor.
    for index, entry in enumerate(sessions):
        if index < 6:
            entry["space_id"] = _space_id("PROJECT_SYNC", index // 2)
        else:
            entry["space_id"] = f"cs-project-single-{index}"

    report = module.evaluate(_human_report(), pilot, policy)
    assert report["status"] == "NO_GO"
    cross = next(
        item for item in report["failed_checks"]
        if item["name"] == "profile:PROJECT_SYNC:cross_session_spaces"
    )
    assert cross["actual"] == 0
    assert cross["required"] == ">=3"


def test_policy_cannot_lower_cross_session_space_qualification_below_three():
    module = _module()
    policy = _policy()
    policy["cross_session_space_min_sessions"] = 2
    report = module.evaluate(_human_report(), _pilot(), policy)
    assert report["status"] == "NO_GO"
    check = next(
        item for item in report["failed_checks"]
        if item["name"] == "cross_session_space_min_sessions_contract"
    )
    assert check["actual"] == 2
    assert check["required"] == "integer >= 3"


def test_stable_readiness_derives_distinct_users_instead_of_trusting_a_count():
    module = _module()
    policy = _policy()
    pilot = _pilot()
    for entry in pilot["profiles"]["PROJECT_SYNC"]["sessions"]:
        entry["user_ref"] = "same-local-pseudonym"
    report = module.evaluate(_human_report(), pilot, policy)
    assert report["status"] == "NO_GO"
    assert any(
        item["name"] == "profile:PROJECT_SYNC:distinct_users"
        for item in report["failed_checks"]
    )


def test_stable_readiness_fails_on_critical_incident():
    module = _module()
    policy = _policy()
    pilot = _pilot()
    pilot["critical_incidents"] = 1
    report = module.evaluate(_human_report(), pilot, policy)
    assert report["status"] == "NO_GO"
    assert any(item["name"] == "critical_incidents_zero" for item in report["failed_checks"])


def test_stable_readiness_self_report_cannot_satisfy_independent_review_metric():
    module = _module()
    policy = _policy()
    human = _human_report()
    metric = "recall_precision"
    independent = "INDEPENDENT_HUMAN_REVIEW"
    self_report = "LOCAL_IN_PRODUCT_EXPLICIT_SELF_REPORT"

    for profile in policy["metric_profiles"]:
        entry = human["metrics_by_profile_and_label_source"][profile][independent].pop(metric)
        human["metrics_by_profile_and_label_source"][profile].setdefault(self_report, {})[metric] = entry

    report = module.evaluate(human, _pilot(), policy)
    assert report["status"] == "NO_GO"
    failed = {item["name"] for item in report["failed_checks"]}
    assert f"metric:{metric}:population" in failed
    assert f"metric:{metric}:sample_size" in failed


def test_stable_readiness_ignores_unspecified_labels_even_when_aggregate_looks_good():
    module = _module()
    policy = _policy()
    human = _human_report()
    metric = "source_attribution_accuracy"
    independent = "INDEPENDENT_HUMAN_REVIEW"

    for profile in policy["metric_profiles"]:
        entry = human["metrics_by_profile_and_label_source"][profile][independent].pop(metric)
        human["metrics_by_profile_and_label_source"][profile].setdefault("UNSPECIFIED", {})[metric] = entry

    report = module.evaluate(human, _pilot(), policy)
    assert report["status"] == "NO_GO"
    failed = {item["name"] for item in report["failed_checks"]}
    assert f"metric:{metric}:population" in failed
    assert f"metric:{metric}:sample_size" in failed


def test_old_count_only_manifest_cannot_pass_current_policy():
    module = _module()
    policy = _policy()
    pilot = _pilot()
    pilot["contract_version"] = "v2.0-R1-pilot-counts-legacy"
    pilot["profiles"] = {
        "PROJECT_SYNC": {
            "distinct_users": 999,
            "sessions": 999,
            "cross_session_spaces": 999,
        },
        "DESIGN_REVIEW": {
            "distinct_users": 999,
            "sessions": 999,
            "cross_session_spaces": 999,
        },
    }
    report = module.evaluate(_human_report(), pilot, policy)
    assert report["status"] == "NO_GO"
    failed = {item["name"] for item in report["failed_checks"]}
    assert "pilot_manifest_contract_version" in failed
    assert "pilot_manifest_cohort_integrity" in failed
    assert "profile:PROJECT_SYNC:sessions" in failed


def test_human_report_session_must_belong_to_authorized_manifest_cohort():
    module = _module()
    policy = _policy()
    human = _human_report()
    human["cohort"]["sessions"][0]["session_id"] = "cv-not-authorized"
    report = module.evaluate(human, _pilot(), policy)
    assert report["status"] == "NO_GO"
    assert any(
        item["name"] == "human_report_sessions_authorized"
        for item in report["failed_checks"]
    )


def test_human_report_space_must_match_authorized_session_space():
    module = _module()
    policy = _policy()
    human = _human_report()
    human["cohort"]["sessions"][0]["space_id"] = "cs-wrong-space"
    report = module.evaluate(human, _pilot(), policy)
    assert report["status"] == "NO_GO"
    assert any(
        item["name"] == "human_report_sessions_authorized"
        for item in report["failed_checks"]
    )


def test_one_launch_profile_cannot_supply_all_metric_evidence():
    module = _module()
    policy = _policy()
    human = _human_report()
    metric = "opportunity_precision"
    source = _source_for(policy, metric)

    project = human["metrics_by_profile_and_label_source"]["PROJECT_SYNC"][source][metric]
    design = human["metrics_by_profile_and_label_source"]["DESIGN_REVIEW"][source][metric]
    project["n"] += design["n"]
    design["n"] = 0

    report = module.evaluate(human, _pilot(), policy)
    assert report["status"] == "NO_GO"
    failed = {item["name"] for item in report["failed_checks"]}
    assert f"metric:{metric}:profile_coverage" in failed


def test_out_of_scope_profile_metrics_cannot_inflate_stable_gate():
    module = _module()
    policy = _policy()
    human = _human_report()
    metric = "opportunity_precision"
    source = _source_for(policy, metric)

    for profile in policy["metric_profiles"]:
        human["metrics_by_profile_and_label_source"][profile][source].pop(metric)

    human["metrics_by_profile_and_label_source"]["CLIENT_CALL"] = {
        source: {metric: {"value": 1.0, "n": 1000}}
    }

    report = module.evaluate(human, _pilot(), policy)
    assert report["status"] == "NO_GO"
    failed = {item["name"] for item in report["failed_checks"]}
    assert f"metric:{metric}:population" in failed
    assert f"metric:{metric}:sample_size" in failed


def test_duplicate_manifest_session_id_fails_cohort_integrity():
    module = _module()
    policy = _policy()
    pilot = _pilot()
    duplicate = dict(pilot["profiles"]["PROJECT_SYNC"]["sessions"][0])
    pilot["profiles"]["PROJECT_SYNC"]["sessions"].append(duplicate)
    report = module.evaluate(_human_report(), pilot, policy)
    assert report["status"] == "NO_GO"
    assert any(
        item["name"] == "pilot_manifest_cohort_integrity"
        for item in report["failed_checks"]
    )


def test_pilot_period_requires_timezone_aware_iso8601():
    module = _module()
    policy = _policy()
    pilot = _pilot()
    pilot["period"] = {
        "started_at": "2026-10-01T09:00:00",
        "ended_at": "2026-10-11T18:00:00",
    }
    report = module.evaluate(_human_report(), pilot, policy)
    assert report["status"] == "NO_GO"
    assert any(item["name"] == "pilot_period_valid" for item in report["failed_checks"])
