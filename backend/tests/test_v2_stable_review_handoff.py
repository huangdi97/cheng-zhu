"""Stable release-review handoff must freeze PASS evidence without granting Stable."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
READY = "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW"


def _load():
    path = ROOT / "scripts" / "v2_conversation_stable_review_handoff.py"
    spec = importlib.util.spec_from_file_location("v2_stable_review_handoff_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _canonical_sha(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _artifact_provenance(distributions: list[str]) -> dict:
    import re

    artifacts = []
    for raw in distributions:
        name, version = raw.split("==", 1)
        normalized = re.sub(r"[-_.]+", "-", name).lower()
        artifacts.append({
            "name": normalized,
            "version": version,
            "filename": f"{normalized}-{version}-py3-none-any.whl",
            "sha256": hashlib.sha256(f"{normalized}-{version}-wheel".encode("utf-8")).hexdigest(),
        })
    artifacts.sort(key=lambda row: row["name"])
    material = {"artifacts": artifacts}
    return {
        "contract_version": "v2.0-R1-python-artifact-provenance-1",
        "artifacts": artifacts,
        "artifacts_count": len(artifacts),
        "sha256": hashlib.sha256(
            json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "install_mode": "WHEEL_SHA256_PINNED",
    }


def _python_env() -> dict:
    distributions = ["fastapi==0.999.0", "pydantic==2.12.5", "pyinstaller==6.16.0"]
    material = {
        "python_version": "3.11.14",
        "implementation": "CPython",
        "architecture": "AMD64",
        "distributions": distributions,
    }
    return {
        "contract_version": "v2.0-R1-python-build-environment-1",
        **material,
        "distributions_count": len(distributions),
        "sha256": _canonical_sha(material),
        "artifact_provenance": _artifact_provenance(distributions),
    }


def _workspace(tmp_path: Path, *, status: str = READY) -> Path:
    ws = tmp_path / "pilot"
    ev = ws / "evaluation"
    ev.mkdir(parents=True)

    toolchain = {
        "contract_version": "v2.0-R1-pilot-toolchain-3",
        "files": [{"path": "scripts/v2_conversation_stable_readiness.py", "sha256": "a" * 64}],
    }
    runtime_baseline = {
        "contract_version": "v2.0-R1-pilot-runtime-baseline-2",
        "runtime_origin": "PACKAGED_EMBEDDED",
        "release_channel": "PRERELEASE",
        "runtime_fingerprint": {
            "contract_version": "v2.0-R1-runtime-fingerprint-1",
            "sha256": "b" * 64,
            "files": 42,
        },
        "python_environment": _python_env(),
        "source_builds": [
            {"app_version": "2.0.0-beta.10", "source_sha": "a" * 40},
        ],
        "sessions": 1,
        "claim_boundary": "SAME_NORMALIZED_RUNTIME_SOURCE_FINGERPRINT_NOT_BEHAVIORAL_EQUIVALENCE_OR_REAL_USER_IDENTITY_PROOF",
    }
    cohort = {
        "contract_version": "v2.0-R1-selected-cohort-snapshot-2",
        "sessions": [{"session_id": "cv_1", "space_id": "cs_1", "user_ref": "pilot-user-01"}],
    }
    policy = {"policy_version": "v2.0-R1-stable-promotion-8"}
    draft_manifest = {
        "contract_version": "v2.0-R1-real-pilot-manifest-3",
        "evidence_type": "DRAFT_NOT_AUTHORIZED_REAL_USE",
    }
    final_manifest = {
        "contract_version": "v2.0-R1-real-pilot-manifest-3",
        "evidence_type": "AUTHORIZED_REAL_CONVERSATION_PILOT",
    }
    coverage = {
        "required_event_metric_pairs": 120,
        "covered_event_metric_pairs": 120,
        "missing_event_metric_pairs": 0,
        "complete": True,
    }
    stable_claims = {
        "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW": status == READY,
        "V2_STABLE_RELEASE": False,
        "PMF_PROVEN": False,
    }

    _write_json(ws / "selected-cohort.snapshot.json", cohort)
    _write_json(ws / "stable-promotion-policy.json", policy)
    _write_json(ws / "pilot-manifest.draft.json", draft_manifest)
    _write_json(ws / "pilot-manifest.final.json", final_manifest)
    (ws / "independent-review.seed.jsonl").write_text(
        '# frozen seed\n{"kind":"guidance","system":{"text":"PRIVATE_TRANSCRIPT_DO_NOT_COPY"}}\n',
        encoding="utf-8",
    )
    (ws / "self-report.jsonl").write_text(
        '# local self report\n{"kind":"session_outcome","notes":"PRIVATE_REVIEW_NOTE_DO_NOT_COPY"}\n',
        encoding="utf-8",
    )

    _write_json(ws / "workspace.json", {
        "contract_version": "v2.0-R1-pilot-workspace-7",
        "policy": {
            "policy_version": policy["policy_version"],
            "sha256": _sha(ws / "stable-promotion-policy.json"),
        },
        "toolchain": toolchain,
        "runtime_baseline": runtime_baseline,
        "outputs": {
            "selected_cohort_snapshot": {
                "sha256": _sha(ws / "selected-cohort.snapshot.json"),
                "logical_sha256": _canonical_sha(cohort),
            },
            "pilot_manifest_draft": {
                "sha256": _sha(ws / "pilot-manifest.draft.json"),
            },
            "independent_review_seed": {
                "sha256": _sha(ws / "independent-review.seed.jsonl"),
            },
            "self_report": {
                "sha256": _sha(ws / "self-report.jsonl"),
            },
        },
    })

    _write_json(ev / "human-report.json", {
        "evidence_type": "HUMAN_LABELED_CONVERSATION_EVAL",
        "claims": {"HUMAN_LABELS_AVAILABLE": True},
        "stable_metric_coverage": coverage,
    })
    _write_json(ev / "stable-readiness.json", {
        "policy_version": policy["policy_version"],
        "status": status,
        "pilot_cohort": {
            "authorized_sessions": 40,
            "human_labeled_sessions": 40,
            "profile_stats": {
                "PROJECT_SYNC": {"distinct_users": 5, "sessions": 20, "cross_session_spaces": 3},
                "DESIGN_REVIEW": {"distinct_users": 5, "sessions": 20, "cross_session_spaces": 3},
            },
        },
        "checks_total": 30,
        "checks_failed": 0 if status == READY else 1,
        "claims": stable_claims,
    })

    _write_json(ws / "finalization.json", {
        "contract_version": "v2.0-R1-pilot-workspace-7",
        "selected_cohort_snapshot_sha256": _sha(ws / "selected-cohort.snapshot.json"),
        "selected_cohort_logical_sha256": _canonical_sha(cohort),
        "draft_manifest_sha256": _sha(ws / "pilot-manifest.draft.json"),
        "final_manifest_sha256": _sha(ws / "pilot-manifest.final.json"),
        "policy_sha256": _sha(ws / "stable-promotion-policy.json"),
        "toolchain": toolchain,
        "runtime_baseline": runtime_baseline,
    })
    _write_json(ev / "evaluation-manifest.json", {
        "contract_version": "v2.0-R1-pilot-workspace-7",
        "status": status,
        "toolchain": toolchain,
        "runtime_baseline": runtime_baseline,
        "inputs": {
            "selected_cohort_snapshot_sha256": _sha(ws / "selected-cohort.snapshot.json"),
            "selected_cohort_logical_sha256": _canonical_sha(cohort),
            "pilot_manifest_final_sha256": _sha(ws / "pilot-manifest.final.json"),
            "policy_sha256": _sha(ws / "stable-promotion-policy.json"),
            "self_report_sha256": _sha(ws / "self-report.jsonl"),
            "independent_review_seed_sha256": _sha(ws / "independent-review.seed.jsonl"),
            "stable_metric_coverage": coverage,
        },
        "outputs": {
            "human_report_sha256": _sha(ev / "human-report.json"),
            "stable_readiness_sha256": _sha(ev / "stable-readiness.json"),
        },
        "claims": stable_claims,
    })
    return ws

def test_handoff_requires_pass_and_keeps_release_decision_pending(tmp_path):
    mod = _load()
    workspace = _workspace(tmp_path)
    out = tmp_path / "handoff"

    result = mod.create_handoff(workspace, out, ROOT)

    assert result["contract_version"] == mod.CONTRACT_VERSION
    assert result["status"] == "READY_FOR_HUMAN_STABLE_RELEASE_REVIEW"
    assert result["claims"]["PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW"] is True
    assert result["claims"]["V2_STABLE_RELEASE"] is False
    assert result["claims"]["PMF_PROVEN"] is False
    assert result["pilot_runtime_baseline"]["runtime_fingerprint"]["sha256"] == "b" * 64
    assert result["pilot_runtime_baseline"]["python_environment"]["sha256"] == _python_env()["sha256"]
    assert result["pilot_runtime_baseline"]["python_environment"]["artifact_provenance"]["sha256"] == _python_env()["artifact_provenance"]["sha256"]
    assert result["claims"]["REAL_USER_IDENTITY_SYSTEM_VERIFIED"] is False
    assert all(
        row["state"] == "PENDING_HUMAN_RELEASE_REVIEW"
        for row in result["release_review_checks"]
    )
    assert len(result["release_review_checks"]) >= 10
    assert result["privacy"] == {
        "raw_transcript_copied": False,
        "guidance_text_copied": False,
        "reviewer_notes_copied": False,
        "direct_identifiers_required": False,
    }
    assert result["provenance_consistency"] == {
        "workspace_contract": "VERIFIED",
        "toolchain": "VERIFIED_ACROSS_WORKSPACE_FINALIZATION_EVALUATION",
        "runtime_baseline": "VERIFIED_ACROSS_WORKSPACE_FINALIZATION_EVALUATION",
        "selected_cohort": "VERIFIED_ACROSS_WORKSPACE_FINALIZATION_EVALUATION",
        "policy": "VERIFIED_ACROSS_WORKSPACE_FINALIZATION_EVALUATION",
        "draft_and_final_manifest": "VERIFIED",
        "review_seed_and_self_report": "VERIFIED",
        "evaluation_claims": "MATCH_STABLE_READINESS",
        "stable_metric_coverage": "MATCH_HUMAN_REPORT",
    }

    serialized = (out / "stable-review-handoff.json").read_text(encoding="utf-8")
    serialized += (out / "stable-review-handoff.md").read_text(encoding="utf-8")
    assert "PRIVATE_TRANSCRIPT_DO_NOT_COPY" not in serialized
    assert "PRIVATE_REVIEW_NOTE_DO_NOT_COPY" not in serialized

    checksums = json.loads((out / "SHA256.json").read_text(encoding="utf-8"))
    assert checksums["handoff_json_sha256"] == _sha(out / "stable-review-handoff.json")
    assert checksums["handoff_markdown_sha256"] == _sha(out / "stable-review-handoff.md")

    with pytest.raises(FileExistsError, match="already exists"):
        mod.create_handoff(workspace, out, ROOT)


def test_handoff_rejects_no_go_evaluation(tmp_path):
    mod = _load()
    workspace = _workspace(tmp_path, status="NO_GO")

    with pytest.raises(ValueError, match="not ready for Stable release review"):
        mod.create_handoff(workspace, tmp_path / "handoff", ROOT)
    assert not (tmp_path / "handoff").exists()


def test_handoff_rejects_frozen_artifact_drift(tmp_path):
    mod = _load()
    workspace = _workspace(tmp_path)
    policy = workspace / "stable-promotion-policy.json"
    policy.write_bytes(policy.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="SHA256 drift"):
        mod.create_handoff(workspace, tmp_path / "handoff", ROOT)
    assert not (tmp_path / "handoff").exists()


def test_handoff_rejects_stable_or_pmf_claim_escalation(tmp_path):
    mod = _load()
    workspace = _workspace(tmp_path)
    stable_path = workspace / "evaluation" / "stable-readiness.json"
    stable = json.loads(stable_path.read_text(encoding="utf-8"))
    stable["claims"]["V2_STABLE_RELEASE"] = True
    _write_json(stable_path, stable)

    evaluation_path = workspace / "evaluation" / "evaluation-manifest.json"
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    evaluation["outputs"]["stable_readiness_sha256"] = _sha(stable_path)
    _write_json(evaluation_path, evaluation)

    with pytest.raises(ValueError, match="must not publish/claim V2_STABLE_RELEASE"):
        mod.create_handoff(workspace, tmp_path / "handoff", ROOT)


def test_handoff_rejects_evaluation_manifest_toolchain_metadata_drift(tmp_path):
    mod = _load()
    workspace = _workspace(tmp_path)
    evaluation_path = workspace / "evaluation" / "evaluation-manifest.json"
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    evaluation["toolchain"]["files"][0]["sha256"] = "b" * 64
    _write_json(evaluation_path, evaluation)

    with pytest.raises(ValueError, match="evaluation/workspace toolchain: provenance mismatch"):
        mod.create_handoff(workspace, tmp_path / "handoff", ROOT)


def test_handoff_rejects_evaluation_coverage_summary_drift(tmp_path):
    mod = _load()
    workspace = _workspace(tmp_path)
    evaluation_path = workspace / "evaluation" / "evaluation-manifest.json"
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    evaluation["inputs"]["stable_metric_coverage"]["covered_event_metric_pairs"] = 119
    evaluation["inputs"]["stable_metric_coverage"]["missing_event_metric_pairs"] = 1
    evaluation["inputs"]["stable_metric_coverage"]["complete"] = False
    _write_json(evaluation_path, evaluation)

    with pytest.raises(ValueError, match="evaluation/human stable metric coverage: provenance mismatch"):
        mod.create_handoff(workspace, tmp_path / "handoff", ROOT)


def test_handoff_rejects_evaluation_claim_summary_drift(tmp_path):
    mod = _load()
    workspace = _workspace(tmp_path)
    evaluation_path = workspace / "evaluation" / "evaluation-manifest.json"
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    evaluation["claims"]["PMF_PROVEN"] = True
    _write_json(evaluation_path, evaluation)

    with pytest.raises(ValueError, match="evaluation/stable claims: provenance mismatch"):
        mod.create_handoff(workspace, tmp_path / "handoff", ROOT)
