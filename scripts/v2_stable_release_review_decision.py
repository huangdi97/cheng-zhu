#!/usr/bin/env python3
"""Create a fail-closed human Stable release-review decision for Chengzhu v2+.

This tool consumes a privacy-minimized Stable review handoff. It never publishes
GitHub Releases, never verifies human identity/consent/reviewer independence,
and never turns a GO review decision into V2_STABLE_RELEASE=true.

A GO decision is only an authorization input for the separate exact-SHA release
pipeline. The actual Stable release exists only after that pipeline publishes
and verifies the public tag/assets.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import runtime_fingerprint
import v2_conversation_stable_review_handoff as handoff_tool


DRAFT_CONTRACT = "v2.0-R1-stable-release-review-draft-3"
DECISION_CONTRACT = "v2.0-R1-stable-release-review-decision-3"
AUTHORIZATION_CONTRACT = "v2.0-R1-stable-release-authorization-3"
READY_STATUS = "READY_FOR_HUMAN_STABLE_RELEASE_REVIEW"
EVIDENCE_READY = "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW"


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


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _git(repo_root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _repo_state(repo_root: Path) -> dict[str, Any]:
    head = _git(repo_root, "rev-parse", "HEAD")
    status = _git(repo_root, "status", "--porcelain")
    version_path = repo_root / "desktop" / "package.json"
    version = str(_load_object(version_path).get("version") or "") if version_path.is_file() else ""
    return {"git_head": head, "working_tree_clean": status == "", "version": version}


def _validate_candidate(source_sha: str, version: str) -> tuple[str, str]:
    source_sha = str(source_sha or "").strip().lower()
    version = str(version or "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("candidate_source_sha must be a full 40-character git SHA")
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", version)
    if not match:
        raise ValueError("candidate_version must be a stable SemVer without prerelease suffix")
    if int(match.group(1)) < 2:
        raise ValueError("this v2 Stable review contract applies only to major version >= 2")
    return source_sha, version


def _require_repo_candidate(repo_root: Path, source_sha: str, version: str) -> dict[str, Any]:
    state = _repo_state(repo_root)
    if state["git_head"] != source_sha:
        raise ValueError(
            f"candidate checkout mismatch: expected {source_sha}, got {state['git_head'] or 'UNKNOWN'}"
        )
    if not state["working_tree_clean"]:
        raise ValueError("candidate checkout must be clean before Stable release review")
    if state["version"] != version:
        raise ValueError(
            f"candidate version mismatch: expected {version}, checkout reports {state['version'] or 'UNKNOWN'}"
        )
    return state


def _runtime_equivalence(repo_root: Path, handoff: dict[str, Any]) -> dict[str, Any]:
    pilot = handoff.get("pilot_runtime_baseline")
    if not isinstance(pilot, dict):
        raise ValueError("handoff is missing packaged pilot runtime baseline")
    pilot = handoff_tool._require_runtime_baseline(
        pilot,
        "handoff pilot_runtime_baseline",
    )
    pilot_runtime = pilot.get("runtime_fingerprint")
    if not isinstance(pilot_runtime, dict):
        raise ValueError("handoff pilot runtime fingerprint missing")
    if str(pilot_runtime.get("contract_version") or "") != runtime_fingerprint.CONTRACT_VERSION:
        raise ValueError("handoff pilot runtime fingerprint contract mismatch")
    pilot_sha = str(pilot_runtime.get("sha256") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", pilot_sha):
        raise ValueError("handoff pilot runtime fingerprint SHA256 invalid")

    current = runtime_fingerprint.fingerprint(repo_root.resolve())
    candidate = {
        "contract_version": str(current.get("contract_version") or ""),
        "sha256": str(current.get("sha256") or "").strip().lower(),
        "files": int(current.get("files") or 0),
    }
    if candidate["contract_version"] != runtime_fingerprint.CONTRACT_VERSION:
        raise ValueError("candidate runtime fingerprint contract mismatch")
    if candidate["sha256"] != pilot_sha:
        raise ValueError(
            "Stable candidate runtime differs from the packaged runtime that produced the pilot evidence; "
            "run a new prerelease pilot before Stable promotion"
        )
    pilot_python_environment = pilot.get("python_environment")
    if not isinstance(pilot_python_environment, dict):
        raise ValueError("handoff pilot Python environment baseline missing")
    pilot_env_sha = str(pilot_python_environment.get("sha256") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", pilot_env_sha):
        raise ValueError("handoff pilot Python environment SHA256 invalid")
    artifact = pilot_python_environment.get("artifact_provenance")
    if not isinstance(artifact, dict):
        raise ValueError("handoff pilot Python artifact provenance missing")
    if (
        str(artifact.get("contract_version") or "")
        != runtime_fingerprint.PYTHON_ARTIFACT_PROVENANCE_CONTRACT
    ):
        raise ValueError("handoff pilot Python artifact provenance contract mismatch")
    pilot_artifact_sha = str(artifact.get("sha256") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", pilot_artifact_sha):
        raise ValueError("handoff pilot Python artifact provenance SHA256 invalid")

    return {
        "contract_version": "v2.0-R1-stable-runtime-equivalence-3",
        "pilot_runtime_fingerprint": {
            "contract_version": runtime_fingerprint.CONTRACT_VERSION,
            "sha256": pilot_sha,
            "files": int(pilot_runtime.get("files") or 0),
        },
        "pilot_python_environment": pilot_python_environment,
        "pilot_python_artifact_provenance_sha256": pilot_artifact_sha,
        "candidate_runtime_fingerprint": candidate,
        "runtime_baseline_match": True,
        "interpretation": (
            "Normalized source/runtime fingerprint equality is a release-provenance gate, "
            "not a proof of behavioral equivalence, real-user identity, or PMF."
        ),
    }


def _verify_handoff(handoff_dir: Path) -> tuple[dict[str, Any], dict[str, str]]:
    handoff_dir = handoff_dir.resolve()
    handoff_path = handoff_dir / "stable-review-handoff.json"
    markdown_path = handoff_dir / "stable-review-handoff.md"
    sha_path = handoff_dir / "SHA256.json"
    manifest = _load_object(sha_path)
    handoff = _load_object(handoff_path)

    if str(manifest.get("contract_version") or "") != handoff_tool.CONTRACT_VERSION:
        raise ValueError("handoff checksum manifest contract mismatch")
    if str(handoff.get("contract_version") or "") != handoff_tool.CONTRACT_VERSION:
        raise ValueError("unsupported Stable review handoff contract")
    if str(manifest.get("handoff_json_sha256") or "") != _sha256(handoff_path):
        raise ValueError("stable-review-handoff.json SHA256 mismatch")
    if str(manifest.get("handoff_markdown_sha256") or "") != _sha256(markdown_path):
        raise ValueError("stable-review-handoff.md SHA256 mismatch")
    if str(handoff.get("status") or "") != READY_STATUS:
        raise ValueError("handoff is not ready for human Stable release review")
    if str(handoff.get("evidence_status") or "") != EVIDENCE_READY:
        raise ValueError("handoff does not carry a Stable-evidence PASS")

    claims = dict(handoff.get("claims") or {})
    if claims.get("PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW") is not True:
        raise ValueError("handoff evidence-ready claim is not true")
    if claims.get("V2_STABLE_RELEASE") is not False:
        raise ValueError("handoff must not already claim V2_STABLE_RELEASE")
    if claims.get("PMF_PROVEN") is not False:
        raise ValueError("handoff must not claim PMF")

    expected_ids = [check_id for check_id, _reason in handoff_tool.REQUIRED_RELEASE_REVIEW_CHECKS]
    rows = list(handoff.get("release_review_checks") or [])
    if [str(row.get("id") or "") for row in rows] != expected_ids:
        raise ValueError("handoff release-review check set/order drift")
    for row in rows:
        if row.get("required") is not True:
            raise ValueError(f"handoff check {row.get('id')}: required flag drift")
        if str(row.get("state") or "") != "PENDING_HUMAN_RELEASE_REVIEW":
            raise ValueError(f"handoff check {row.get('id')}: must still be pending")

    privacy = dict(handoff.get("privacy") or {})
    for field in ("raw_transcript_copied", "guidance_text_copied", "reviewer_notes_copied", "direct_identifiers_required"):
        if privacy.get(field) is not False:
            raise ValueError(f"handoff privacy boundary drift: {field}")

    return handoff, {
        "handoff_json_sha256": _sha256(handoff_path),
        "handoff_markdown_sha256": _sha256(markdown_path),
        "handoff_sha_manifest_sha256": _sha256(sha_path),
    }


def init_review(
    handoff_dir: Path,
    out_path: Path,
    repo_root: Path,
    *,
    candidate_source_sha: str,
    candidate_version: str,
) -> dict[str, Any]:
    if out_path.exists():
        raise FileExistsError(f"review draft already exists: {out_path}")
    source_sha, version = _validate_candidate(candidate_source_sha, candidate_version)
    handoff, hashes = _verify_handoff(handoff_dir)
    source = _require_repo_candidate(repo_root.resolve(), source_sha, version)
    runtime_equivalence = _runtime_equivalence(repo_root.resolve(), handoff)

    draft = {
        "contract_version": DRAFT_CONTRACT,
        "status": "DRAFT_HUMAN_STABLE_RELEASE_REVIEW",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate": {
            "source_sha": source_sha,
            "version": version,
        },
        "handoff": {
            "contract_version": handoff["contract_version"],
            "evidence_status": handoff["evidence_status"],
            "stable_policy_version": handoff.get("stable_policy_version"),
            **hashes,
        },
        "reviewer": {
            "reviewer_ref": "",
            "identity_system_verified": False,
        },
        "checks": [
            {
                "id": check_id,
                "state": "PENDING_HUMAN_RELEASE_REVIEW",
                "evidence_ref": "",
                "reason": reason,
            }
            for check_id, reason in handoff_tool.REQUIRED_RELEASE_REVIEW_CHECKS
        ],
        "source_checkout": source,
        "runtime_equivalence": runtime_equivalence,
        "claims": {
            "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW": True,
            "V2_STABLE_RELEASE": False,
            "REAL_USER_IDENTITY_SYSTEM_VERIFIED": False,
            "REVIEWER_INDEPENDENCE_SYSTEM_VERIFIED": False,
            "PARTICIPANT_CONSENT_SYSTEM_VERIFIED": False,
            "PMF_PROVEN": False,
        },
        "instructions": (
            "A human reviewer must replace every PENDING state with PASS or FAIL, provide a concise non-sensitive "
            "evidence_ref for every check, and set reviewer.reviewer_ref. The reviewer_ref is an audit label, not "
            "system-verified identity. Finalization derives GO only when every required check is PASS."
        ),
    }
    _write_json(out_path, draft)
    return draft


def finalize_review(
    handoff_dir: Path,
    draft_path: Path,
    out_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    if out_dir.exists():
        raise FileExistsError(f"review decision output already exists: {out_dir}")
    handoff, hashes = _verify_handoff(handoff_dir)
    draft = _load_object(draft_path)
    if str(draft.get("contract_version") or "") != DRAFT_CONTRACT:
        raise ValueError("unsupported Stable release-review draft contract")

    candidate = dict(draft.get("candidate") or {})
    source_sha, version = _validate_candidate(candidate.get("source_sha"), candidate.get("version"))
    source = _require_repo_candidate(repo_root.resolve(), source_sha, version)
    runtime_equivalence = _runtime_equivalence(repo_root.resolve(), handoff)
    if draft.get("runtime_equivalence") != runtime_equivalence:
        raise ValueError(
            "Stable review draft runtime fingerprint drift; candidate or pilot baseline changed after review init"
        )

    draft_handoff = dict(draft.get("handoff") or {})
    expected_handoff = {
        "contract_version": handoff["contract_version"],
        "evidence_status": handoff["evidence_status"],
        "stable_policy_version": handoff.get("stable_policy_version"),
        **hashes,
    }
    if draft_handoff != expected_handoff:
        raise ValueError("review draft handoff provenance drift")

    reviewer = dict(draft.get("reviewer") or {})
    reviewer_ref = str(reviewer.get("reviewer_ref") or "").strip()
    if not reviewer_ref or len(reviewer_ref) > 200:
        raise ValueError("reviewer.reviewer_ref is required and must be <= 200 characters")
    if reviewer.get("identity_system_verified") is not False:
        raise ValueError("reviewer identity must remain explicitly not system-verified")

    expected = list(handoff_tool.REQUIRED_RELEASE_REVIEW_CHECKS)
    expected_ids = [check_id for check_id, _reason in expected]
    rows = list(draft.get("checks") or [])
    if [str(row.get("id") or "") for row in rows] != expected_ids:
        raise ValueError("Stable release-review check set/order drift")

    normalized_checks: list[dict[str, Any]] = []
    for row, (check_id, reason) in zip(rows, expected):
        state = str(row.get("state") or "").strip().upper()
        if state not in {"PASS", "FAIL"}:
            raise ValueError(f"{check_id}: every check must be explicitly PASS or FAIL before finalization")
        evidence_ref = str(row.get("evidence_ref") or "").strip()
        if not evidence_ref or len(evidence_ref) > 1000:
            raise ValueError(f"{check_id}: non-sensitive evidence_ref is required and must be <= 1000 characters")
        normalized_checks.append({
            "id": check_id,
            "state": state,
            "evidence_ref": evidence_ref,
            "reason": reason,
        })

    decision = "GO" if all(row["state"] == "PASS" for row in normalized_checks) else "NO_GO"
    decision_check_digest = _canonical_sha256(normalized_checks)
    authorization_checks = [
        {"id": row["id"], "state": row["state"]}
        for row in normalized_checks
    ]
    authorization_check_digest = _canonical_sha256(authorization_checks)
    claims = {
        "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW": True,
        "V2_STABLE_RELEASE": False,
        "REAL_USER_IDENTITY_SYSTEM_VERIFIED": False,
        "REVIEWER_INDEPENDENCE_SYSTEM_VERIFIED": False,
        "PARTICIPANT_CONSENT_SYSTEM_VERIFIED": False,
        "PMF_PROVEN": False,
    }
    decision_artifact = {
        "contract_version": DECISION_CONTRACT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "candidate": {"source_sha": source_sha, "version": version},
        "handoff": expected_handoff,
        "reviewer": {
            "reviewer_ref": reviewer_ref,
            "identity_system_verified": False,
        },
        "checks": normalized_checks,
        "review_check_digest": decision_check_digest,
        "source_checkout": source,
        "runtime_equivalence": runtime_equivalence,
        "claims": claims,
        "interpretation": (
            "GO authorizes only the separate exact-SHA Stable release workflow after machine-verifying "
            "that the candidate normalized runtime fingerprint matches the packaged pilot baseline. It is not "
            "publication itself. NO_GO blocks publication. Neither result verifies identity/consent/reviewer "
            "independence, proves behavioral equivalence, or proves PMF."
        ),
    }

    authorization = {
        "contract_version": AUTHORIZATION_CONTRACT,
        "decision": decision,
        "eligible_for_stable_release_workflow": decision == "GO",
        "candidate_source_sha": source_sha,
        "candidate_version": version,
        "handoff_contract_version": handoff["contract_version"],
        "handoff_json_sha256": hashes["handoff_json_sha256"],
        "pilot_runtime_fingerprint": runtime_equivalence["pilot_runtime_fingerprint"],
        "pilot_python_environment": runtime_equivalence["pilot_python_environment"],
        "pilot_python_artifact_provenance_sha256": runtime_equivalence["pilot_python_artifact_provenance_sha256"],
        "candidate_runtime_fingerprint": runtime_equivalence["candidate_runtime_fingerprint"],
        "runtime_baseline_match": True,
        "review_check_digest": authorization_check_digest,
        "checks": authorization_checks,
        "claims": claims,
        "boundary": "AUTHORIZATION_IS_NOT_PUBLICATION",
    }

    stage = out_dir.with_name(out_dir.name + ".tmp")
    if stage.exists():
        raise FileExistsError(f"temporary review decision output already exists: {stage}")
    stage.mkdir(parents=True)
    try:
        decision_path = stage / "stable-release-review-decision.json"
        auth_path = stage / "stable-release-authorization.json"
        _write_json(decision_path, decision_artifact)
        _write_json(auth_path, authorization)
        if decision == "GO":
            compact = json.dumps(authorization, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            token = base64.b64encode(compact).decode("ascii")
            (stage / "stable-release-authorization.b64").write_text(token + "\n", encoding="ascii")
        checksums = {
            "contract_version": DECISION_CONTRACT,
            "decision_sha256": _sha256(decision_path),
            "authorization_sha256": _sha256(auth_path),
            "authorization_b64_sha256": (
                _sha256(stage / "stable-release-authorization.b64")
                if (stage / "stable-release-authorization.b64").is_file()
                else None
            ),
        }
        _write_json(stage / "SHA256.json", checksums)
        stage.replace(out_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return decision_artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--handoff-dir", required=True)
    init.add_argument("--out", required=True)
    init.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    init.add_argument("--candidate-source-sha", required=True)
    init.add_argument("--candidate-version", required=True)

    finalize = sub.add_parser("finalize")
    finalize.add_argument("--handoff-dir", required=True)
    finalize.add_argument("--draft", required=True)
    finalize.add_argument("--out-dir", required=True)
    finalize.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))

    args = parser.parse_args()
    try:
        if args.command == "init":
            result = init_review(
                Path(args.handoff_dir),
                Path(args.out),
                Path(args.repo_root),
                candidate_source_sha=args.candidate_source_sha,
                candidate_version=args.candidate_version,
            )
            print(json.dumps({"status": result["status"], "out": args.out}, ensure_ascii=False))
            return 0
        result = finalize_review(
            Path(args.handoff_dir),
            Path(args.draft),
            Path(args.out_dir),
            Path(args.repo_root),
        )
        print(json.dumps({
            "decision": result["decision"],
            "candidate": result["candidate"],
            "out_dir": args.out_dir,
            "V2_STABLE_RELEASE": False,
            "PMF_PROVEN": False,
        }, ensure_ascii=False))
        return 0 if result["decision"] == "GO" else 2
    except (FileNotFoundError, FileExistsError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
