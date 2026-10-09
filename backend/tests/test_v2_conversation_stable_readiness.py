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


def _human_report():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    metrics = {}
    for name, rule in policy["metrics"].items():
        threshold = rule["threshold"]
        value = threshold
        metrics[name] = {"value": value, "n": rule["min_n"]}
    return {
        "evidence_type": "HUMAN_LABELED_CONVERSATION_EVAL",
        "claims": {"HUMAN_LABELS_AVAILABLE": True, "PMF_PROVEN": False},
        "metrics": metrics,
    }


def _pilot():
    return {
        "evidence_type": "AUTHORIZED_REAL_CONVERSATION_PILOT",
        "attestations": [
            "AUTHORIZED_REAL_USE",
            "NO_SYNTHETIC_ROWS_IN_HUMAN_EVAL",
            "RAW_LABELS_KEPT_LOCAL",
            "NO_CRITICAL_PRIVACY_INCIDENT",
            "NO_KNOWN_DATA_LOSS",
        ],
        "profiles": {
            "PROJECT_SYNC": {
                "distinct_users": 5,
                "sessions": 20,
                "cross_session_spaces": 3,
            },
            "DESIGN_REVIEW": {
                "distinct_users": 5,
                "sessions": 20,
                "cross_session_spaces": 3,
            },
        },
        "critical_incidents": 0,
    }


def test_stable_readiness_pass_only_grants_release_review():
    module = _module()
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    report = module.evaluate(_human_report(), _pilot(), policy)
    assert report["status"] == "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW"
    assert report["claims"]["PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW"] is True
    assert report["claims"]["V2_STABLE_RELEASE"] is False
    assert report["claims"]["PMF_PROVEN"] is False


def test_stable_readiness_fails_when_sample_size_is_insufficient():
    module = _module()
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    human = _human_report()
    human["metrics"]["opportunity_precision"]["n"] = 1
    report = module.evaluate(human, _pilot(), policy)
    assert report["status"] == "NO_GO"
    assert any(
        item["name"] == "metric:opportunity_precision:sample_size"
        for item in report["failed_checks"]
    )


def test_stable_readiness_fails_on_bad_quality_even_with_large_n():
    module = _module()
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    human = _human_report()
    human["metrics"]["interruption_regret"] = {"value": 0.5, "n": 100}
    report = module.evaluate(human, _pilot(), policy)
    assert report["status"] == "NO_GO"
    assert any(
        item["name"] == "metric:interruption_regret:threshold"
        for item in report["failed_checks"]
    )


def test_stable_readiness_fails_without_real_use_attestation():
    module = _module()
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    pilot = _pilot()
    pilot["attestations"].remove("AUTHORIZED_REAL_USE")
    report = module.evaluate(_human_report(), pilot, policy)
    assert report["status"] == "NO_GO"
    assert any(
        item["name"] == "attestation:AUTHORIZED_REAL_USE"
        for item in report["failed_checks"]
    )


def test_stable_readiness_fails_when_profile_floor_is_missing():
    module = _module()
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    pilot = _pilot()
    pilot["profiles"]["PROJECT_SYNC"]["sessions"] = 2
    report = module.evaluate(_human_report(), pilot, policy)
    assert report["status"] == "NO_GO"
    assert any(
        item["name"] == "profile:PROJECT_SYNC:sessions"
        for item in report["failed_checks"]
    )


def test_stable_readiness_fails_on_critical_incident():
    module = _module()
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    pilot = _pilot()
    pilot["critical_incidents"] = 1
    report = module.evaluate(_human_report(), pilot, policy)
    assert report["status"] == "NO_GO"
    assert any(item["name"] == "critical_incidents_zero" for item in report["failed_checks"])
