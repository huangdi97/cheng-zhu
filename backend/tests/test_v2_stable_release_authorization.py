"""Stable v2 release authorization must be explicit, exact-SHA bound and fail closed."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


decision = _load("v2_stable_release_review_decision_test", "scripts/v2_stable_release_review_decision.py")
verify = _load("verify_stable_release_authorization_test", "scripts/verify_stable_release_authorization.py")
handoff_tool = _load("v2_stable_handoff_contract_test", "scripts/v2_conversation_stable_review_handoff.py")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _runtime_sha() -> str:
    return str(decision.runtime_fingerprint.fingerprint(ROOT)["sha256"])


def _python_env() -> dict:
    distributions = ["fastapi==0.999.0", "pydantic==2.12.5", "pyinstaller==6.16.0"]
    material = {
        "python_version": "3.11.14",
        "implementation": "CPython",
        "architecture": "AMD64",
        "distributions": distributions,
    }
    raw = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "contract_version": "v2.0-R1-python-build-environment-1",
        **material,
        "distributions_count": len(distributions),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _handoff(tmp_path: Path) -> Path:
    out = tmp_path / "handoff"
    out.mkdir()
    checks = [
        {
            "id": check_id,
            "state": "PENDING_HUMAN_RELEASE_REVIEW",
            "required": True,
            "reason": reason,
        }
        for check_id, reason in handoff_tool.REQUIRED_RELEASE_REVIEW_CHECKS
    ]
    payload = {
        "contract_version": handoff_tool.CONTRACT_VERSION,
        "status": "READY_FOR_HUMAN_STABLE_RELEASE_REVIEW",
        "evidence_status": "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW",
        "stable_policy_version": "v2.0-R1-stable-promotion-8",
        "pilot_runtime_baseline": {
            "contract_version": "v2.0-R1-pilot-runtime-baseline-1",
            "runtime_origin": "PACKAGED_EMBEDDED",
            "release_channel": "PRERELEASE",
            "runtime_fingerprint": {
                "contract_version": decision.runtime_fingerprint.CONTRACT_VERSION,
                "sha256": _runtime_sha(),
                "files": int(decision.runtime_fingerprint.fingerprint(ROOT)["files"]),
            },
            "python_environment": _python_env(),
            "source_builds": [
                {"app_version": "2.0.0-beta.10", "source_sha": "f" * 40},
            ],
            "sessions": 40,
        },
        "release_review_checks": checks,
        "claims": {
            "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW": True,
            "V2_STABLE_RELEASE": False,
            "REAL_USER_IDENTITY_SYSTEM_VERIFIED": False,
            "REVIEWER_INDEPENDENCE_SYSTEM_VERIFIED": False,
            "PARTICIPANT_CONSENT_SYSTEM_VERIFIED": False,
            "PMF_PROVEN": False,
        },
        "privacy": {
            "raw_transcript_copied": False,
            "guidance_text_copied": False,
            "reviewer_notes_copied": False,
            "direct_identifiers_required": False,
        },
    }
    _write_json(out / "stable-review-handoff.json", payload)
    (out / "stable-review-handoff.md").write_text("# Stable handoff\n", encoding="utf-8")
    _write_json(out / "SHA256.json", {
        "contract_version": handoff_tool.CONTRACT_VERSION,
        "handoff_json_sha256": _sha(out / "stable-review-handoff.json"),
        "handoff_markdown_sha256": _sha(out / "stable-review-handoff.md"),
    })
    return out


def _candidate(monkeypatch, sha: str = "a" * 40, version: str = "2.0.0") -> None:
    monkeypatch.setattr(
        decision,
        "_repo_state",
        lambda _root: {"git_head": sha, "working_tree_clean": True, "version": version},
    )


def _review_all(draft_path: Path, *, failed: str = "") -> None:
    value = json.loads(draft_path.read_text(encoding="utf-8"))
    value["reviewer"]["reviewer_ref"] = "release-reviewer-01"
    for row in value["checks"]:
        row["state"] = "FAIL" if row["id"] == failed else "PASS"
        row["evidence_ref"] = f"evidence:{row['id']}"
    _write_json(draft_path, value)


def test_go_decision_produces_exact_sha_bound_authorization_accepted_by_release_gate(tmp_path, monkeypatch):
    handoff = _handoff(tmp_path)
    source_sha = "a" * 40
    _candidate(monkeypatch, source_sha, "2.0.0")
    draft = tmp_path / "review.draft.json"

    decision.init_review(
        handoff,
        draft,
        ROOT,
        candidate_source_sha=source_sha,
        candidate_version="2.0.0",
    )
    _review_all(draft)
    out = tmp_path / "decision"
    result = decision.finalize_review(handoff, draft, out, ROOT)

    assert result["decision"] == "GO"
    assert result["claims"]["V2_STABLE_RELEASE"] is False
    assert result["claims"]["PMF_PROVEN"] is False
    token = (out / "stable-release-authorization.b64").read_text(encoding="ascii").strip()
    verified = verify.verify_authorization(token, source_sha=source_sha, version="2.0.0", runtime_fingerprint_sha256=_runtime_sha(), python_environment_sha256=_python_env()["sha256"])
    assert verified["required"] is True
    assert verified["status"] == "VERIFIED_HUMAN_STABLE_RELEASE_REVIEW_GO"
    assert verified["runtime_fingerprint_sha256"] == _runtime_sha()
    assert verified["pilot_runtime_fingerprint_sha256"] == _runtime_sha()
    assert verified["python_environment_sha256"] == _python_env()["sha256"]
    assert verified["pilot_python_environment_sha256"] == _python_env()["sha256"]
    assert verified["claims"]["V2_STABLE_RELEASE"] is False


def test_no_go_decision_never_emits_release_token(tmp_path, monkeypatch):
    handoff = _handoff(tmp_path)
    source_sha = "b" * 40
    _candidate(monkeypatch, source_sha, "2.0.0")
    draft = tmp_path / "review.draft.json"
    decision.init_review(
        handoff,
        draft,
        ROOT,
        candidate_source_sha=source_sha,
        candidate_version="2.0.0",
    )
    _review_all(draft, failed=handoff_tool.REQUIRED_RELEASE_REVIEW_CHECKS[0][0])
    out = tmp_path / "decision"
    result = decision.finalize_review(handoff, draft, out, ROOT)

    assert result["decision"] == "NO_GO"
    assert not (out / "stable-release-authorization.b64").exists()
    auth = json.loads((out / "stable-release-authorization.json").read_text(encoding="utf-8"))
    assert auth["eligible_for_stable_release_workflow"] is False


def test_finalize_rejects_pending_or_missing_evidence(tmp_path, monkeypatch):
    handoff = _handoff(tmp_path)
    source_sha = "c" * 40
    _candidate(monkeypatch, source_sha, "2.0.0")
    draft = tmp_path / "review.draft.json"
    decision.init_review(
        handoff,
        draft,
        ROOT,
        candidate_source_sha=source_sha,
        candidate_version="2.0.0",
    )
    pending = json.loads(draft.read_text(encoding="utf-8"))
    pending["reviewer"]["reviewer_ref"] = "release-reviewer-01"
    _write_json(draft, pending)
    with pytest.raises(ValueError, match="PASS or FAIL"):
        decision.finalize_review(handoff, draft, tmp_path / "decision-pending", ROOT)

    _review_all(draft)
    value = json.loads(draft.read_text(encoding="utf-8"))
    value["checks"][0]["evidence_ref"] = ""
    _write_json(draft, value)
    with pytest.raises(ValueError, match="evidence_ref"):
        decision.finalize_review(handoff, draft, tmp_path / "decision-missing-evidence", ROOT)


def test_finalize_rechecks_clean_exact_candidate_checkout(tmp_path, monkeypatch):
    handoff = _handoff(tmp_path)
    source_sha = "d" * 40
    _candidate(monkeypatch, source_sha, "2.0.0")
    draft = tmp_path / "review.draft.json"
    decision.init_review(
        handoff,
        draft,
        ROOT,
        candidate_source_sha=source_sha,
        candidate_version="2.0.0",
    )
    _review_all(draft)

    monkeypatch.setattr(
        decision,
        "_repo_state",
        lambda _root: {"git_head": "e" * 40, "working_tree_clean": True, "version": "2.0.0"},
    )
    with pytest.raises(ValueError, match="checkout mismatch"):
        decision.finalize_review(handoff, draft, tmp_path / "decision", ROOT)


def test_handoff_checksum_drift_is_rejected_before_review(tmp_path, monkeypatch):
    handoff = _handoff(tmp_path)
    source_sha = "f" * 40
    _candidate(monkeypatch, source_sha, "2.0.0")
    (handoff / "stable-review-handoff.md").write_text("# drift\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        decision.init_review(
            handoff,
            tmp_path / "draft.json",
            ROOT,
            candidate_source_sha=source_sha,
            candidate_version="2.0.0",
        )


def test_release_verifier_requires_token_only_for_stable_v2_plus():
    source_sha = "1" * 40
    prerelease = verify.verify_authorization("", source_sha=source_sha, version="2.0.0-beta.10")
    assert prerelease["required"] is False
    assert prerelease["status"] == "NOT_REQUIRED_PRERELEASE"

    legacy = verify.verify_authorization("", source_sha=source_sha, version="1.4.2")
    assert legacy["required"] is False
    assert legacy["status"] == "NOT_REQUIRED_LEGACY_STABLE"

    with pytest.raises(ValueError, match="requires stable_review_authorization_b64"):
        verify.verify_authorization("", source_sha=source_sha, version="2.0.0", runtime_fingerprint_sha256=_runtime_sha(), python_environment_sha256=_python_env()["sha256"])


def test_release_verifier_rejects_source_version_and_check_drift(tmp_path, monkeypatch):
    handoff = _handoff(tmp_path)
    source_sha = "2" * 40
    _candidate(monkeypatch, source_sha, "2.0.0")
    draft = tmp_path / "draft.json"
    decision.init_review(
        handoff,
        draft,
        ROOT,
        candidate_source_sha=source_sha,
        candidate_version="2.0.0",
    )
    _review_all(draft)
    out = tmp_path / "decision"
    decision.finalize_review(handoff, draft, out, ROOT)
    token = (out / "stable-release-authorization.b64").read_text(encoding="ascii").strip()

    with pytest.raises(ValueError, match="source SHA"):
        verify.verify_authorization(token, source_sha="3" * 40, version="2.0.0", runtime_fingerprint_sha256=_runtime_sha(), python_environment_sha256=_python_env()["sha256"])
    with pytest.raises(ValueError, match="version"):
        verify.verify_authorization(token, source_sha=source_sha, version="2.1.0", runtime_fingerprint_sha256=_runtime_sha(), python_environment_sha256=_python_env()["sha256"])

    raw = json.loads(base64.b64decode(token).decode("utf-8"))
    raw["checks"][0]["state"] = "FAIL"
    tampered = base64.b64encode(
        json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    with pytest.raises(ValueError, match="non-PASS"):
        verify.verify_authorization(tampered, source_sha=source_sha, version="2.0.0", runtime_fingerprint_sha256=_runtime_sha(), python_environment_sha256=_python_env()["sha256"])


def test_human_go_cannot_be_reused_after_candidate_runtime_drift(tmp_path, monkeypatch):
    handoff = _handoff(tmp_path)
    source_sha = "e" * 40
    _candidate(monkeypatch, source_sha, "2.0.0")
    draft = tmp_path / "review.draft.json"
    decision.init_review(
        handoff,
        draft,
        ROOT,
        candidate_source_sha=source_sha,
        candidate_version="2.0.0",
    )
    _review_all(draft)

    original_fingerprint = decision.runtime_fingerprint.fingerprint
    monkeypatch.setattr(
        decision.runtime_fingerprint,
        "fingerprint",
        lambda _root: {
            "contract_version": decision.runtime_fingerprint.CONTRACT_VERSION,
            "sha256": "9" * 64,
            "files": 42,
            "inputs": [],
        },
    )
    with pytest.raises(ValueError, match="runtime differs|runtime fingerprint drift"):
        decision.finalize_review(handoff, draft, tmp_path / "decision-runtime-drift", ROOT)
    monkeypatch.setattr(decision.runtime_fingerprint, "fingerprint", original_fingerprint)


def test_release_gate_rejects_go_token_for_different_runtime_fingerprint(tmp_path, monkeypatch):
    handoff = _handoff(tmp_path)
    source_sha = "6" * 40
    _candidate(monkeypatch, source_sha, "2.0.0")
    draft = tmp_path / "review.draft.json"
    decision.init_review(
        handoff,
        draft,
        ROOT,
        candidate_source_sha=source_sha,
        candidate_version="2.0.0",
    )
    _review_all(draft)
    out = tmp_path / "decision"
    decision.finalize_review(handoff, draft, out, ROOT)
    token = (out / "stable-release-authorization.b64").read_text(encoding="ascii").strip()

    with pytest.raises(ValueError, match="runtime fingerprint"):
        verify.verify_authorization(
            token,
            source_sha=source_sha,
            version="2.0.0",
            runtime_fingerprint_sha256="7" * 64,
            python_environment_sha256=_python_env()["sha256"],
        )


def test_release_gate_rejects_go_token_for_different_python_environment(tmp_path, monkeypatch):
    handoff = _handoff(tmp_path)
    source_sha = "8" * 40
    _candidate(monkeypatch, source_sha, "2.0.0")
    draft = tmp_path / "review-python-env.draft.json"
    decision.init_review(
        handoff,
        draft,
        ROOT,
        candidate_source_sha=source_sha,
        candidate_version="2.0.0",
    )
    _review_all(draft)
    out = tmp_path / "decision-python-env"
    decision.finalize_review(handoff, draft, out, ROOT)
    token = (out / "stable-release-authorization.b64").read_text(encoding="ascii").strip()

    with pytest.raises(ValueError, match="Python environment"):
        verify.verify_authorization(
            token,
            source_sha=source_sha,
            version="2.0.0",
            runtime_fingerprint_sha256=_runtime_sha(),
            python_environment_sha256="9" * 64,
        )


def test_release_workflows_enforce_stable_v2_human_authorization_contract():
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    publisher = (ROOT / ".github" / "workflows" / "publish-current-version-on-green-main.yml").read_text(encoding="utf-8")

    for token in (
        "stable_review_authorization_b64:",
        "scripts/verify_stable_release_authorization.py",
        "VERIFIED_HUMAN_STABLE_RELEASE_REVIEW_GO",
        "RELEASE_AUTHORIZATION.json",
        "--runtime-fingerprint-sha256",
        "--python-environment-sha256",
        "CHENGZHU_RUNTIME_FINGERPRINT_SHA256",
        "CHENGZHU_PYTHON_ENVIRONMENT_SHA256",
        "BUILD_PROVENANCE.json",
        "--pattern \"BUILD_PROVENANCE.json\"",
        "--pattern \"RELEASE_AUTHORIZATION.json\"",
    ):
        assert token in release

    assert "Stable v2+" in publisher
    assert "requires manual human release authorization" in publisher
    assert "generic publisher will not dispatch" in publisher
