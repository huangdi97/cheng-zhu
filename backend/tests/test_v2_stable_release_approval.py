"""Stable v2 release approval must bind one human decision to one exact candidate."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _load():
    path = ROOT / "scripts" / "v2_stable_release_approval.py"
    spec = importlib.util.spec_from_file_location("v2_stable_release_approval_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_handoff():
    path = ROOT / "scripts" / "v2_conversation_stable_review_handoff.py"
    spec = importlib.util.spec_from_file_location("v2_stable_review_handoff_for_approval_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_approval_check_contract_matches_handoff_check_contract():
    approval = _load()
    handoff = _load_handoff()
    assert list(approval.REQUIRED_CHECK_IDS) == [
        check_id for check_id, _reason in handoff.REQUIRED_RELEASE_REVIEW_CHECKS
    ]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _handoff(tmp_path: Path):
    mod = _load()
    root = tmp_path / "handoff"
    root.mkdir()
    handoff = {
        "contract_version": mod.HANDOFF_CONTRACT,
        "status": mod.HANDOFF_READY,
        "evidence_status": mod.EVIDENCE_READY,
        "release_review_checks": [
            {
                "id": check_id,
                "state": "PENDING_HUMAN_RELEASE_REVIEW",
                "required": True,
                "reason": "review",
            }
            for check_id in mod.REQUIRED_CHECK_IDS
        ],
        "claims": {
            "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW": True,
            "V2_STABLE_RELEASE": False,
            "PMF_PROVEN": False,
        },
    }
    _write_json(root / "stable-review-handoff.json", handoff)
    (root / "stable-review-handoff.md").write_text("# handoff\n", encoding="utf-8")
    _write_json(root / "SHA256.json", {
        "contract_version": mod.HANDOFF_CONTRACT,
        "handoff_json_sha256": _sha(root / "stable-review-handoff.json"),
        "handoff_markdown_sha256": _sha(root / "stable-review-handoff.md"),
    })
    return mod, root


def _approved_review(mod, template: dict) -> dict:
    review = json.loads(json.dumps(template))
    review["reviewer_ref"] = "release-owner-01"
    review["reviewed_at"] = "2026-10-14T00:00:00+00:00"
    review["attestations"] = list(mod.REQUIRED_ATTESTATIONS)
    for item in review["release_review_checks"]:
        item["state"] = "APPROVED"
        item["evidence"] = f"evidence:{item['id']}"
    return review


def test_template_is_bound_to_verified_handoff_and_exact_stable_candidate(tmp_path):
    mod, handoff = _handoff(tmp_path)
    template = mod.create_review_template(handoff, "a" * 40, "2.0.0")
    assert template["contract_version"] == mod.REVIEW_INPUT_CONTRACT
    assert template["candidate_source_sha"] == "a" * 40
    assert template["candidate_version"] == "2.0.0"
    assert template["attestations"] == []
    assert template["required_attestations"] == list(mod.REQUIRED_ATTESTATIONS)
    assert [item["id"] for item in template["release_review_checks"]] == list(mod.REQUIRED_CHECK_IDS)
    assert all(item["state"] == "PENDING" for item in template["release_review_checks"])

    with pytest.raises(ValueError, match="stable SemVer"):
        mod.create_review_template(handoff, "a" * 40, "2.0.0-beta.10")


def test_finalize_requires_complete_evidence_and_no_go_is_not_approval(tmp_path):
    mod, handoff = _handoff(tmp_path)
    template = mod.create_review_template(handoff, "b" * 40, "2.0.0")
    review = _approved_review(mod, template)
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    approved = mod.finalize_approval(handoff, review_path, "b" * 40, "2.0.0")
    assert approved["status"] == mod.APPROVED_STATUS
    assert approved["claims"]["STABLE_RELEASE_PUBLICATION_AUTHORIZED"] is True
    assert approved["claims"]["V2_STABLE_RELEASE"] is False
    assert approved["claims"]["PMF_PROVEN"] is False
    assert approved["approval_path"] == ".github/stable-release-approvals/v2.0.0.json"

    review["release_review_checks"][3]["state"] = "REJECTED"
    review["release_review_checks"][3]["evidence"] = "packaged smoke failed"
    _write_json(tmp_path / "rejected.json", review)
    no_go = mod.finalize_approval(handoff, tmp_path / "rejected.json", "b" * 40, "2.0.0")
    assert no_go["status"] == mod.NO_GO_STATUS
    assert no_go["claims"]["STABLE_RELEASE_PUBLICATION_AUTHORIZED"] is False
    assert no_go["rejected_checks"] == ["packaged_runtime_smoke_green"]

    review = _approved_review(mod, template)
    review["release_review_checks"][0]["evidence"] = ""
    _write_json(tmp_path / "missing-evidence.json", review)
    with pytest.raises(ValueError, match="evidence"):
        mod.finalize_approval(handoff, tmp_path / "missing-evidence.json", "b" * 40, "2.0.0")


def test_finalize_requires_timezone_aware_review_timestamp(tmp_path):
    mod, handoff = _handoff(tmp_path)
    template = mod.create_review_template(handoff, "d" * 40, "2.0.0")
    review = _approved_review(mod, template)
    review["reviewed_at"] = "2026-10-14T00:00:00"
    _write_json(tmp_path / "naive-time.json", review)
    with pytest.raises(ValueError, match="timezone-aware"):
        mod.finalize_approval(handoff, tmp_path / "naive-time.json", "d" * 40, "2.0.0")


def test_handoff_drift_or_missing_required_check_fails_closed(tmp_path):
    mod, handoff = _handoff(tmp_path)
    handoff_json = handoff / "stable-review-handoff.json"
    value = json.loads(handoff_json.read_text(encoding="utf-8"))
    value["release_review_checks"].pop()
    _write_json(handoff_json, value)
    # Even if someone updates the local SHA manifest too, the frozen required
    # check set remains an independent contract.
    manifest = json.loads((handoff / "SHA256.json").read_text(encoding="utf-8"))
    manifest["handoff_json_sha256"] = _sha(handoff_json)
    _write_json(handoff / "SHA256.json", manifest)
    with pytest.raises(ValueError, match="check set/order drift"):
        mod.create_review_template(handoff, "c" * 40, "2.0.0")


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def test_committed_approval_must_be_exactly_one_approval_only_child(tmp_path):
    mod, handoff = _handoff(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "ci@example.invalid")
    _git(repo, "config", "user.name", "CI")

    (repo / "desktop").mkdir()
    _write_json(repo / "desktop" / "package.json", {"version": "2.0.0"})
    (repo / "candidate.txt").write_text("candidate\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "stable candidate")
    candidate = _git(repo, "rev-parse", "HEAD")

    template = mod.create_review_template(handoff, candidate, "2.0.0")
    review = _approved_review(mod, template)
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)
    approval = mod.finalize_approval(handoff, review_path, candidate, "2.0.0")

    approval_path = repo / ".github" / "stable-release-approvals" / "v2.0.0.json"
    _write_json(approval_path, approval)
    _git(repo, "add", ".github/stable-release-approvals/v2.0.0.json")
    _git(repo, "commit", "-m", "approve stable")
    release_source = _git(repo, "rev-parse", "HEAD")

    verified = mod.validate_committed_approval(
        repo,
        candidate_version="2.0.0",
        release_source_sha=release_source,
    )
    assert verified["ok"] is True
    assert verified["candidate_source_sha"] == candidate
    assert verified["release_source_sha"] == release_source

    (repo / "README.md").write_text("later source drift\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "drift after approval")
    drifted = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(ValueError, match="exactly one approval-only child"):
        mod.validate_committed_approval(
            repo,
            candidate_version="2.0.0",
            release_source_sha=drifted,
        )


def test_committed_approval_refuses_non_approval_delta(tmp_path):
    mod, handoff = _handoff(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "ci@example.invalid")
    _git(repo, "config", "user.name", "CI")
    (repo / "desktop").mkdir()
    _write_json(repo / "desktop" / "package.json", {"version": "2.0.0"})
    (repo / "app.py").write_text("print('candidate')\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "candidate")
    candidate = _git(repo, "rev-parse", "HEAD")

    template = mod.create_review_template(handoff, candidate, "2.0.0")
    review = _approved_review(mod, template)
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)
    approval = mod.finalize_approval(handoff, review_path, candidate, "2.0.0")
    _write_json(repo / ".github" / "stable-release-approvals" / "v2.0.0.json", approval)
    (repo / "app.py").write_text("print('changed after review')\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "approval plus source change")
    source = _git(repo, "rev-parse", "HEAD")

    with pytest.raises(ValueError, match="approval delta must contain only"):
        mod.validate_committed_approval(
            repo,
            candidate_version="2.0.0",
            release_source_sha=source,
        )
