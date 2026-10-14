#!/usr/bin/env python3
"""Create a privacy-minimized Stable release-review handoff from a PASS pilot workspace.

This tool runs *after* the frozen evaluator has completed. It does not change
Pilot Workspace v5 evaluator semantics, publish a release, verify human identity
or participant consent, or prove PMF.

A handoff may be created only when the immutable workspace evaluation says
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW. The output freezes hashes and
release-review obligations so the later human decision cannot silently confuse
"evidence gate passed" with "Stable was released".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "v2.0-R1-stable-review-handoff-3"
REQUIRED_WORKSPACE_CONTRACT = "v2.0-R1-pilot-workspace-6"
REQUIRED_TOOLCHAIN_CONTRACT = "v2.0-R1-pilot-toolchain-2"
REQUIRED_COHORT_SNAPSHOT_CONTRACT = "v2.0-R1-selected-cohort-snapshot-2"
READY_STATUS = "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW"

REQUIRED_RELEASE_REVIEW_CHECKS: tuple[tuple[str, str], ...] = (
    ("current_main_ci_green", "Current candidate main SHA must pass the complete CI gate."),
    ("dependency_security_gate_green", "Current candidate dependency-security gate must pass."),
    ("release_version_consistency", "All release version surfaces and release notes must agree."),
    ("packaged_runtime_smoke_green", "Current candidate packaged runtime smoke must pass."),
    ("windows_clean_install_green", "Current candidate Windows installer must pass clean-install replay."),
    ("release_asset_sha256_verified", "Final installer/portable SHA256 must be verified after download-back."),
    ("tag_source_sha_equal", "Public tag SHA must equal the exact source SHA used to build binaries."),
    ("stable_latest_channel_reviewed", "Stable publication must intentionally update the stable channel only after review."),
    ("privacy_security_incidents_reviewed", "Known privacy/security incidents since pilot evaluation must be reviewed."),
    ("known_critical_bugs_reviewed", "Known critical product/data-loss bugs must be reviewed."),
    ("rollback_plan_reviewed", "Rollback and previous-stable recovery path must be reviewed."),
    ("release_notes_truth_reviewed", "Release notes and public maturity claims must match evidence truth."),
    ("code_signing_policy_reviewed", "Windows signing/SmartScreen decision must be explicitly reviewed."),
)


def _load_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_hash(path: Path, expected: str, label: str) -> None:
    expected = str(expected or "").strip().lower()
    if not expected:
        raise ValueError(f"{label}: missing frozen SHA256")
    actual = _sha256(path)
    if actual != expected:
        raise ValueError(f"{label}: SHA256 drift; expected {expected}, got {actual}")


def _canonical_json_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: provenance mismatch")


def _require_runtime_baseline(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label}: missing packaged runtime baseline")
    if str(value.get("contract_version") or "") != "v2.0-R1-pilot-runtime-baseline-1":
        raise ValueError(f"{label}: runtime baseline contract mismatch")
    runtime = value.get("runtime_fingerprint")
    if not isinstance(runtime, dict):
        raise ValueError(f"{label}: runtime fingerprint missing")
    if str(runtime.get("contract_version") or "") != "v2.0-R1-runtime-fingerprint-1":
        raise ValueError(f"{label}: runtime fingerprint contract mismatch")
    runtime_sha = str(runtime.get("sha256") or "").strip().lower()
    if len(runtime_sha) != 64 or any(ch not in "0123456789abcdef" for ch in runtime_sha):
        raise ValueError(f"{label}: runtime fingerprint SHA256 invalid")
    if str(value.get("runtime_origin") or "") != "PACKAGED_EMBEDDED":
        raise ValueError(f"{label}: runtime baseline is not packaged")
    if str(value.get("release_channel") or "") != "PRERELEASE":
        raise ValueError(f"{label}: runtime baseline is not prerelease")
    return value


def _git(repo_root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _source_checkout(repo_root: Path) -> dict[str, Any]:
    head = _git(repo_root, "rev-parse", "HEAD")
    status = _git(repo_root, "status", "--porcelain")
    version_path = repo_root / "frontend" / "package.json"
    version = ""
    if version_path.is_file():
        raw = _load_object(version_path)
        version = str(raw.get("version") or "")
    return {
        "git_head": head,
        "working_tree_clean": status == "",
        "version": version,
        "note": (
            "Checkout identity is context for the human Stable review. "
            "It is not release provenance and does not replace exact-SHA package/download-back verification."
        ),
    }


def create_handoff(workspace: Path, out_dir: Path, repo_root: Path) -> dict[str, Any]:
    workspace = workspace.resolve()
    out_dir = out_dir.resolve()
    repo_root = repo_root.resolve()
    if not workspace.is_dir():
        raise FileNotFoundError(workspace)
    if out_dir.exists():
        raise FileExistsError(f"handoff output already exists: {out_dir}")

    evaluation_dir = workspace / "evaluation"
    evaluation_manifest_path = evaluation_dir / "evaluation-manifest.json"
    stable_path = evaluation_dir / "stable-readiness.json"
    human_path = evaluation_dir / "human-report.json"
    draft_manifest_path = workspace / "pilot-manifest.draft.json"
    final_manifest_path = workspace / "pilot-manifest.final.json"
    finalization_path = workspace / "finalization.json"
    policy_path = workspace / "stable-promotion-policy.json"
    workspace_meta_path = workspace / "workspace.json"
    cohort_path = workspace / "selected-cohort.snapshot.json"
    seed_path = workspace / "independent-review.seed.jsonl"
    self_report_path = workspace / "self-report.jsonl"

    evaluation_manifest = _load_object(evaluation_manifest_path)
    stable = _load_object(stable_path)
    human = _load_object(human_path)
    final_manifest = _load_object(final_manifest_path)
    finalization = _load_object(finalization_path)
    workspace_meta = _load_object(workspace_meta_path)
    policy = _load_object(policy_path)
    cohort_snapshot = _load_object(cohort_path)

    outputs = evaluation_manifest.get("outputs") or {}
    inputs = evaluation_manifest.get("inputs") or {}
    workspace_outputs = workspace_meta.get("outputs") or {}
    workspace_policy = workspace_meta.get("policy") or {}

    workspace_contract = str(workspace_meta.get("contract_version") or "")
    if not workspace_contract:
        raise ValueError("workspace.json: missing contract_version")
    if workspace_contract != REQUIRED_WORKSPACE_CONTRACT:
        raise ValueError(
            "Stable handoff requires Pilot Workspace v6 with packaged runtime baseline provenance"
        )
    _require_equal(
        str(finalization.get("contract_version") or ""),
        workspace_contract,
        "finalization/workspace contract",
    )
    _require_equal(
        str(evaluation_manifest.get("contract_version") or ""),
        workspace_contract,
        "evaluation/workspace contract",
    )

    workspace_toolchain = workspace_meta.get("toolchain")
    if not isinstance(workspace_toolchain, dict):
        raise ValueError("workspace.json: missing frozen evaluator toolchain")
    if str(workspace_toolchain.get("contract_version") or "") != REQUIRED_TOOLCHAIN_CONTRACT:
        raise ValueError("Stable handoff requires Pilot Toolchain v2")
    workspace_runtime_baseline = _require_runtime_baseline(
        workspace_meta.get("runtime_baseline"),
        "workspace.json",
    )
    _require_equal(
        finalization.get("toolchain"),
        workspace_toolchain,
        "finalization/workspace toolchain",
    )
    _require_equal(
        evaluation_manifest.get("toolchain"),
        workspace_toolchain,
        "evaluation/workspace toolchain",
    )
    _require_equal(
        _require_runtime_baseline(finalization.get("runtime_baseline"), "finalization.json"),
        workspace_runtime_baseline,
        "finalization/workspace runtime baseline",
    )
    _require_equal(
        _require_runtime_baseline(evaluation_manifest.get("runtime_baseline"), "evaluation-manifest.json"),
        workspace_runtime_baseline,
        "evaluation/workspace runtime baseline",
    )

    _require_hash(stable_path, str(outputs.get("stable_readiness_sha256") or ""), "stable-readiness.json")
    _require_hash(human_path, str(outputs.get("human_report_sha256") or ""), "human-report.json")

    if str(cohort_snapshot.get("contract_version") or "") != REQUIRED_COHORT_SNAPSHOT_CONTRACT:
        raise ValueError("Stable handoff requires selected cohort snapshot v2")
    workspace_cohort_meta = workspace_outputs.get("selected_cohort_snapshot") or {}
    _require_hash(
        cohort_path,
        str(workspace_cohort_meta.get("sha256") or ""),
        "selected-cohort.snapshot.json workspace provenance",
    )
    _require_hash(
        cohort_path,
        str(finalization.get("selected_cohort_snapshot_sha256") or ""),
        "selected-cohort.snapshot.json finalization provenance",
    )
    _require_hash(
        cohort_path,
        str(inputs.get("selected_cohort_snapshot_sha256") or ""),
        "selected-cohort.snapshot.json evaluation provenance",
    )
    cohort_logical_sha = _canonical_json_sha256(cohort_snapshot)
    _require_equal(
        str(workspace_cohort_meta.get("logical_sha256") or ""),
        cohort_logical_sha,
        "selected-cohort logical workspace provenance",
    )
    _require_equal(
        str(finalization.get("selected_cohort_logical_sha256") or ""),
        cohort_logical_sha,
        "selected-cohort logical finalization provenance",
    )
    _require_equal(
        str(inputs.get("selected_cohort_logical_sha256") or ""),
        cohort_logical_sha,
        "selected-cohort logical evaluation provenance",
    )

    _require_hash(
        policy_path,
        str(workspace_policy.get("sha256") or ""),
        "stable-promotion-policy.json workspace provenance",
    )
    _require_hash(
        policy_path,
        str(finalization.get("policy_sha256") or ""),
        "stable-promotion-policy.json finalization provenance",
    )
    _require_hash(
        policy_path,
        str(inputs.get("policy_sha256") or ""),
        "stable-promotion-policy.json evaluation provenance",
    )

    workspace_draft_meta = workspace_outputs.get("pilot_manifest_draft") or {}
    _require_hash(
        draft_manifest_path,
        str(workspace_draft_meta.get("sha256") or ""),
        "pilot-manifest.draft.json workspace provenance",
    )
    _require_hash(
        draft_manifest_path,
        str(finalization.get("draft_manifest_sha256") or ""),
        "pilot-manifest.draft.json finalization provenance",
    )

    _require_hash(
        final_manifest_path,
        str(finalization.get("final_manifest_sha256") or ""),
        "pilot-manifest.final.json finalization provenance",
    )
    _require_hash(
        final_manifest_path,
        str(inputs.get("pilot_manifest_final_sha256") or ""),
        "pilot-manifest.final.json evaluation provenance",
    )

    workspace_seed_meta = workspace_outputs.get("independent_review_seed") or {}
    _require_hash(
        seed_path,
        str(workspace_seed_meta.get("sha256") or ""),
        "independent-review.seed.jsonl workspace provenance",
    )
    _require_hash(
        seed_path,
        str(inputs.get("independent_review_seed_sha256") or ""),
        "independent-review.seed.jsonl evaluation provenance",
    )

    workspace_self_report_meta = workspace_outputs.get("self_report") or {}
    self_report_expected = str(workspace_self_report_meta.get("sha256") or "")
    evaluation_self_report_expected = str(inputs.get("self_report_sha256") or "")
    if self_report_path.is_file() or self_report_expected or evaluation_self_report_expected:
        _require_hash(
            self_report_path,
            self_report_expected,
            "self-report.jsonl workspace provenance",
        )
        _require_hash(
            self_report_path,
            evaluation_self_report_expected,
            "self-report.jsonl evaluation provenance",
        )

    policy_version = str(policy.get("policy_version") or "")
    _require_equal(
        str(workspace_policy.get("policy_version") or ""),
        policy_version,
        "workspace/policy version",
    )
    _require_equal(
        str(stable.get("policy_version") or ""),
        policy_version,
        "stable-readiness/policy version",
    )

    if str(evaluation_manifest.get("status") or "") != READY_STATUS:
        raise ValueError("evaluation-manifest is not ready for Stable release review")
    if str(stable.get("status") or "") != READY_STATUS:
        raise ValueError("stable-readiness report is not ready for Stable release review")
    claims = dict(stable.get("claims") or {})
    if claims.get("PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW") is not True:
        raise ValueError("Stable evidence-ready claim is not true")
    if claims.get("V2_STABLE_RELEASE") is not False:
        raise ValueError("Stable evaluator must not publish/claim V2_STABLE_RELEASE")
    if claims.get("PMF_PROVEN") is not False:
        raise ValueError("Stable evaluator must not claim PMF")

    _require_equal(
        evaluation_manifest.get("claims"),
        stable.get("claims"),
        "evaluation/stable claims",
    )
    _require_equal(
        str(evaluation_manifest.get("status") or ""),
        str(stable.get("status") or ""),
        "evaluation/stable status",
    )
    _require_equal(
        inputs.get("stable_metric_coverage"),
        human.get("stable_metric_coverage"),
        "evaluation/human stable metric coverage",
    )

    review_checks = [
        {
            "id": check_id,
            "state": "PENDING_HUMAN_RELEASE_REVIEW",
            "required": True,
            "reason": reason,
        }
        for check_id, reason in REQUIRED_RELEASE_REVIEW_CHECKS
    ]

    artifact_hashes = {
        "workspace_json": _sha256(workspace_meta_path),
        "selected_cohort_snapshot": _sha256(cohort_path),
        "stable_promotion_policy": _sha256(policy_path),
        "pilot_manifest_draft": _sha256(draft_manifest_path),
        "pilot_manifest_final": _sha256(final_manifest_path),
        "finalization": _sha256(finalization_path),
        "independent_review_seed": _sha256(seed_path),
        "self_report": _sha256(self_report_path) if self_report_path.is_file() else None,
        "evaluation_manifest": _sha256(evaluation_manifest_path),
        "human_report": _sha256(human_path),
        "stable_readiness": _sha256(stable_path),
    }

    handoff = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "READY_FOR_HUMAN_STABLE_RELEASE_REVIEW",
        "evidence_status": READY_STATUS,
        "workspace_contract_version": workspace_meta.get("contract_version"),
        "stable_policy_version": stable.get("policy_version"),
        "pilot_manifest_contract_version": final_manifest.get("contract_version"),
        "evaluator_toolchain": workspace_toolchain,
        "pilot_runtime_baseline": workspace_runtime_baseline,
        "pilot_cohort": stable.get("pilot_cohort"),
        "stable_gate": {
            "checks_total": stable.get("checks_total"),
            "checks_failed": stable.get("checks_failed"),
            "stable_metric_coverage": human.get("stable_metric_coverage"),
        },
        "artifact_sha256": artifact_hashes,
        "provenance_consistency": {
            "workspace_contract": "VERIFIED",
            "toolchain": "VERIFIED_ACROSS_WORKSPACE_FINALIZATION_EVALUATION",
            "runtime_baseline": "VERIFIED_ACROSS_WORKSPACE_FINALIZATION_EVALUATION",
            "selected_cohort": "VERIFIED_ACROSS_WORKSPACE_FINALIZATION_EVALUATION",
            "policy": "VERIFIED_ACROSS_WORKSPACE_FINALIZATION_EVALUATION",
            "draft_and_final_manifest": "VERIFIED",
            "review_seed_and_self_report": "VERIFIED",
            "evaluation_claims": "MATCH_STABLE_READINESS",
            "stable_metric_coverage": "MATCH_HUMAN_REPORT",
        },
        "source_checkout": _source_checkout(repo_root),
        "release_review_checks": review_checks,
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
        "interpretation": (
            "This artifact proves only that the frozen pilot evaluation passed the evidence gate and "
            "that its packaged pilot runtime baseline plus frozen workspace/finalization/evaluation facts cross-match "
            "and its handoff inputs still "
            "match their SHA256 provenance. Every release-review check remains "
            "PENDING_HUMAN_RELEASE_REVIEW. Creating this artifact does not publish Stable, verify identities/"
            "consent/reviewer independence, or prove PMF."
        ),
    }

    out_dir.mkdir(parents=True, exist_ok=False)
    json_path = out_dir / "stable-review-handoff.json"
    md_path = out_dir / "stable-review-handoff.md"
    json_path.write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    cohort = handoff.get("pilot_cohort") or {}
    lines = [
        "# Chengzhu v2 Stable Release Review Handoff",
        "",
        f"- Handoff contract: **{CONTRACT_VERSION}**",
        f"- Evidence status: **{READY_STATUS}**",
        f"- Stable policy: **{handoff.get('stable_policy_version') or 'unknown'}**",
        f"- Authorized manifest Sessions: **{cohort.get('authorized_sessions', 0)}**",
        f"- Human-labeled Sessions: **{cohort.get('human_labeled_sessions', 0)}**",
        "- V2_STABLE_RELEASE: **FALSE**",
        "- PMF_PROVEN: **FALSE**",
        "",
        "## Human release-review checks",
        "",
        "| Check | State |",
        "| --- | --- |",
    ]
    for item in review_checks:
        lines.append(f"| {item['id']} | {item['state']} |")
    lines += [
        "",
        "## Privacy / claim boundary",
        "",
        "This handoff contains hashes and summaries only. It does not copy raw transcript, Guidance text or reviewer notes.",
        "",
        "> A handoff is not a Stable release decision. Every release-review item above still requires explicit human review.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # Self-hash is written last and covers both handoff files as created.
    manifest = {
        "contract_version": CONTRACT_VERSION,
        "handoff_json_sha256": _sha256(json_path),
        "handoff_markdown_sha256": _sha256(md_path),
    }
    (out_dir / "SHA256.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return handoff


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()

    result = create_handoff(
        Path(args.workspace),
        Path(args.out_dir),
        Path(args.repo_root),
    )
    print(json.dumps({
        "status": result["status"],
        "contract_version": result["contract_version"],
        "claims": result["claims"],
        "out_dir": str(Path(args.out_dir)),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
