#!/usr/bin/env python3
"""Fail-closed Stable release approval for Chengzhu v2.

This tool sits after the privacy-minimized Stable review handoff and before a
Stable GitHub Release. It does not evaluate product evidence itself and it does
not publish anything.

The approved candidate is the exact main commit *before* the approval artifact
is committed. The release source must then be exactly one child commit whose
only diff is the version-scoped approval JSON. This avoids the impossible
self-reference of an approval file trying to contain the SHA of the commit that
contains that same file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APPROVAL_CONTRACT = "v2.0-R1-stable-release-approval-1"
REVIEW_INPUT_CONTRACT = "v2.0-R1-stable-release-review-input-1"
HANDOFF_CONTRACT = "v2.0-R1-stable-review-handoff-2"
HANDOFF_READY = "READY_FOR_HUMAN_STABLE_RELEASE_REVIEW"
EVIDENCE_READY = "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW"
APPROVED_STATUS = "STABLE_RELEASE_APPROVED_FOR_EXACT_CANDIDATE"
NO_GO_STATUS = "NO_GO"

REQUIRED_CHECK_IDS = (
    "current_main_ci_green",
    "dependency_security_gate_green",
    "release_version_consistency",
    "packaged_runtime_smoke_green",
    "windows_clean_install_green",
    "release_asset_sha256_verified",
    "tag_source_sha_equal",
    "stable_latest_channel_reviewed",
    "privacy_security_incidents_reviewed",
    "known_critical_bugs_reviewed",
    "rollback_plan_reviewed",
    "release_notes_truth_reviewed",
    "code_signing_policy_reviewed",
)

REQUIRED_ATTESTATIONS = (
    "I_REVIEWED_EXACT_CANDIDATE",
    "I_REVIEWED_ALL_REQUIRED_CHECKS",
    "I_ACCEPT_APPROVAL_ONLY_DELTA",
    "NO_STABLE_CLAIM_BEFORE_PUBLICATION",
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_STABLE_V2_RE = re.compile(r"^([2-9][0-9]*)\.[0-9]+\.[0-9]+$")


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


def _stable_version(value: str) -> str:
    version = str(value or "").strip()
    if not _STABLE_V2_RE.fullmatch(version):
        raise ValueError("Stable approval only supports v2+ stable SemVer without prerelease suffix")
    return version


def _candidate_sha(value: str) -> str:
    sha = str(value or "").strip().lower()
    if not _SHA_RE.fullmatch(sha):
        raise ValueError("candidate_source_sha must be a full 40-character lowercase git SHA")
    return sha


def _approval_path(version: str) -> Path:
    return Path(".github") / "stable-release-approvals" / f"v{version}.json"


def _reviewed_at(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("reviewed_at is required")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("reviewed_at must be timezone-aware ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("reviewed_at must be timezone-aware ISO-8601")
    return raw


def _verify_handoff(handoff_dir: Path) -> dict[str, Any]:
    handoff_dir = handoff_dir.resolve()
    handoff_path = handoff_dir / "stable-review-handoff.json"
    markdown_path = handoff_dir / "stable-review-handoff.md"
    sha_path = handoff_dir / "SHA256.json"

    handoff = _load_object(handoff_path)
    manifest = _load_object(sha_path)
    if str(handoff.get("contract_version") or "") != HANDOFF_CONTRACT:
        raise ValueError("unsupported Stable review handoff contract")
    if str(handoff.get("status") or "") != HANDOFF_READY:
        raise ValueError("handoff is not ready for human Stable release review")
    if str(handoff.get("evidence_status") or "") != EVIDENCE_READY:
        raise ValueError("handoff product evidence is not ready for Stable release review")
    claims = dict(handoff.get("claims") or {})
    if claims.get("PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW") is not True:
        raise ValueError("handoff evidence-ready claim is not true")
    if claims.get("V2_STABLE_RELEASE") is not False or claims.get("PMF_PROVEN") is not False:
        raise ValueError("handoff must not already claim Stable or PMF")

    expected_json = str(manifest.get("handoff_json_sha256") or "").lower()
    expected_md = str(manifest.get("handoff_markdown_sha256") or "").lower()
    if _sha256(handoff_path) != expected_json:
        raise ValueError("stable-review-handoff.json SHA256 drift")
    if _sha256(markdown_path) != expected_md:
        raise ValueError("stable-review-handoff.md SHA256 drift")

    checks = handoff.get("release_review_checks")
    if not isinstance(checks, list):
        raise ValueError("handoff release_review_checks missing")
    ids = [str(item.get("id") or "") for item in checks if isinstance(item, dict)]
    if ids != list(REQUIRED_CHECK_IDS):
        raise ValueError("handoff release-review check set/order drift")
    if any(str(item.get("state") or "") != "PENDING_HUMAN_RELEASE_REVIEW" for item in checks):
        raise ValueError("handoff must contain only pending human release-review checks")

    return {
        "handoff": handoff,
        "handoff_manifest_sha256": _sha256(sha_path),
        "handoff_json_sha256": expected_json,
        "handoff_markdown_sha256": expected_md,
    }


def create_review_template(
    handoff_dir: Path,
    candidate_source_sha: str,
    candidate_version: str,
) -> dict[str, Any]:
    verified = _verify_handoff(handoff_dir)
    version = _stable_version(candidate_version)
    sha = _candidate_sha(candidate_source_sha)
    handoff = verified["handoff"]
    return {
        "contract_version": REVIEW_INPUT_CONTRACT,
        "candidate_source_sha": sha,
        "candidate_version": version,
        "reviewer_ref": "",
        "reviewed_at": "",
        "attestations": list(REQUIRED_ATTESTATIONS),
        "release_review_checks": [
            {
                "id": item["id"],
                "state": "PENDING",
                "evidence": "",
                "note": "",
            }
            for item in handoff["release_review_checks"]
        ],
        "note": (
            "Fill reviewer_ref/reviewed_at and set every check to APPROVED or REJECTED. "
            "Evidence is a human-auditable reference/summary, not automatic verification."
        ),
    }


def finalize_approval(
    handoff_dir: Path,
    review_path: Path,
    candidate_source_sha: str,
    candidate_version: str,
) -> dict[str, Any]:
    verified = _verify_handoff(handoff_dir)
    review = _load_object(review_path)
    version = _stable_version(candidate_version)
    sha = _candidate_sha(candidate_source_sha)

    if str(review.get("contract_version") or "") != REVIEW_INPUT_CONTRACT:
        raise ValueError("unsupported Stable release review input contract")
    if str(review.get("candidate_source_sha") or "").lower() != sha:
        raise ValueError("review candidate_source_sha mismatch")
    if str(review.get("candidate_version") or "") != version:
        raise ValueError("review candidate_version mismatch")
    reviewer_ref = str(review.get("reviewer_ref") or "").strip()
    if not reviewer_ref:
        raise ValueError("reviewer_ref is required")
    reviewed_at = _reviewed_at(str(review.get("reviewed_at") or ""))

    attestations = [str(value) for value in (review.get("attestations") or [])]
    if set(attestations) != set(REQUIRED_ATTESTATIONS):
        raise ValueError("required Stable release review attestations are incomplete or changed")

    raw_checks = review.get("release_review_checks")
    if not isinstance(raw_checks, list):
        raise ValueError("release_review_checks must be a list")
    by_id: dict[str, dict[str, Any]] = {}
    for raw in raw_checks:
        if not isinstance(raw, dict):
            raise ValueError("release-review check must be an object")
        check_id = str(raw.get("id") or "")
        if check_id in by_id:
            raise ValueError(f"duplicate release-review check: {check_id}")
        by_id[check_id] = dict(raw)
    if set(by_id) != set(REQUIRED_CHECK_IDS):
        raise ValueError("release-review check set does not match the frozen handoff contract")

    normalized: list[dict[str, Any]] = []
    rejected: list[str] = []
    for check_id in REQUIRED_CHECK_IDS:
        raw = by_id[check_id]
        state = str(raw.get("state") or "").upper()
        if state not in {"APPROVED", "REJECTED"}:
            raise ValueError(f"{check_id}: state must be APPROVED or REJECTED")
        evidence = str(raw.get("evidence") or "").strip()
        note = str(raw.get("note") or "").strip()
        if not evidence:
            raise ValueError(f"{check_id}: evidence reference/summary is required")
        if state == "REJECTED":
            rejected.append(check_id)
        normalized.append({
            "id": check_id,
            "state": state,
            "evidence": evidence[:4000],
            "note": note[:4000],
        })

    approved = not rejected
    return {
        "contract_version": APPROVAL_CONTRACT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": APPROVED_STATUS if approved else NO_GO_STATUS,
        "candidate_source_sha": sha,
        "candidate_version": version,
        "approval_path": str(_approval_path(version)).replace("\\", "/"),
        "approval_delta_policy": "EXACTLY_ONE_CHILD_COMMIT_AND_ONLY_VERSION_SCOPED_APPROVAL_FILE",
        "handoff": {
            "contract_version": HANDOFF_CONTRACT,
            "manifest_sha256": verified["handoff_manifest_sha256"],
            "handoff_json_sha256": verified["handoff_json_sha256"],
            "handoff_markdown_sha256": verified["handoff_markdown_sha256"],
            "evidence_status": EVIDENCE_READY,
        },
        "reviewer_ref": reviewer_ref[:200],
        "reviewed_at": reviewed_at,
        "attestations": list(REQUIRED_ATTESTATIONS),
        "release_review_checks": normalized,
        "rejected_checks": rejected,
        "claims": {
            "STABLE_RELEASE_PUBLICATION_AUTHORIZED": approved,
            "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW": True,
            "V2_STABLE_RELEASE": False,
            "REAL_USER_IDENTITY_SYSTEM_VERIFIED": False,
            "PARTICIPANT_CONSENT_SYSTEM_VERIFIED": False,
            "PMF_PROVEN": False,
        },
        "interpretation": (
            "APPROVED authorizes only a later release commit that is exactly one child of "
            "candidate_source_sha and changes only this version-scoped approval file. "
            "It does not itself publish Stable or prove PMF/identity/consent."
        ),
    }


def _git(repo_root: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and proc.returncode != 0:
        raise ValueError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def validate_committed_approval(
    repo_root: Path,
    *,
    candidate_version: str,
    release_source_sha: str,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    version = _stable_version(candidate_version)
    release_sha = _candidate_sha(release_source_sha)
    rel = _approval_path(version)
    approval_path = repo_root / rel
    approval = _load_object(approval_path)

    if str(approval.get("contract_version") or "") != APPROVAL_CONTRACT:
        raise ValueError("unsupported committed Stable approval contract")
    if str(approval.get("status") or "") != APPROVED_STATUS:
        raise ValueError("committed Stable approval is not APPROVED")
    if str(approval.get("candidate_version") or "") != version:
        raise ValueError("committed approval version mismatch")
    candidate_sha = _candidate_sha(str(approval.get("candidate_source_sha") or ""))
    if str(approval.get("approval_path") or "") != str(rel).replace("\\", "/"):
        raise ValueError("committed approval path contract mismatch")
    if str(approval.get("approval_delta_policy") or "") != (
        "EXACTLY_ONE_CHILD_COMMIT_AND_ONLY_VERSION_SCOPED_APPROVAL_FILE"
    ):
        raise ValueError("committed approval delta policy mismatch")

    claims = dict(approval.get("claims") or {})
    handoff = dict(approval.get("handoff") or {})
    for field in ("manifest_sha256", "handoff_json_sha256", "handoff_markdown_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(handoff.get(field) or "")):
            raise ValueError(f"committed approval handoff {field} missing/invalid")
    if str(handoff.get("contract_version") or "") != HANDOFF_CONTRACT:
        raise ValueError("committed approval handoff contract mismatch")
    if str(handoff.get("evidence_status") or "") != EVIDENCE_READY:
        raise ValueError("committed approval handoff evidence status mismatch")
    if claims.get("STABLE_RELEASE_PUBLICATION_AUTHORIZED") is not True:
        raise ValueError("committed approval does not authorize Stable publication")
    if claims.get("V2_STABLE_RELEASE") is not False or claims.get("PMF_PROVEN") is not False:
        raise ValueError("approval artifact must not pre-claim Stable or PMF")

    reviewer_ref = str(approval.get("reviewer_ref") or "").strip()
    if not reviewer_ref:
        raise ValueError("committed approval reviewer_ref missing")
    _reviewed_at(str(approval.get("reviewed_at") or ""))
    if approval.get("rejected_checks") not in ([], None):
        raise ValueError("committed approval rejected_checks must be empty")

    checks = approval.get("release_review_checks")
    if not isinstance(checks, list):
        raise ValueError("committed approval release_review_checks missing")
    ids = [str(item.get("id") or "") for item in checks if isinstance(item, dict)]
    if ids != list(REQUIRED_CHECK_IDS):
        raise ValueError("committed approval check set/order drift")
    for item in checks:
        if str(item.get("state") or "") != "APPROVED":
            raise ValueError(f"{item.get('id')}: committed approval contains a non-approved check")
        if not str(item.get("evidence") or "").strip():
            raise ValueError(f"{item.get('id')}: committed approval is missing evidence")
    if [str(value) for value in (approval.get("attestations") or [])] != list(REQUIRED_ATTESTATIONS):
        raise ValueError("committed approval attestation set/order drift")

    # The candidate itself must already be the same stable version. Approval
    # happens after the stable candidate has completed CI/review, not before a
    # later version mutation.
    candidate_pkg = _git(repo_root, "show", f"{candidate_sha}:desktop/package.json")
    candidate_version_from_git = str(json.loads(candidate_pkg).get("version") or "")
    if candidate_version_from_git != version:
        raise ValueError(
            f"candidate {candidate_sha} version is {candidate_version_from_git!r}, expected {version!r}"
        )

    # The approval file must not already exist in the candidate commit.
    existed = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"{candidate_sha}:{rel.as_posix()}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0
    if existed:
        raise ValueError("approval artifact already existed in candidate commit")

    parent = _git(repo_root, "rev-parse", f"{release_sha}^")
    if parent != candidate_sha:
        raise ValueError(
            "Stable release source must be exactly one approval-only child commit of candidate_source_sha"
        )
    changed = [
        line.strip()
        for line in _git(repo_root, "diff", "--name-only", f"{candidate_sha}..{release_sha}").splitlines()
        if line.strip()
    ]
    if changed != [rel.as_posix()]:
        raise ValueError(
            "Stable release approval delta must contain only the version-scoped approval JSON; "
            f"changed={changed}"
        )

    return {
        "ok": True,
        "contract_version": APPROVAL_CONTRACT,
        "status": APPROVED_STATUS,
        "candidate_version": version,
        "candidate_source_sha": candidate_sha,
        "release_source_sha": release_sha,
        "approval_path": rel.as_posix(),
        "approval_sha256": _sha256(approval_path),
        "handoff_manifest_sha256": str((approval.get("handoff") or {}).get("manifest_sha256") or ""),
    }


def _write_new_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    template = sub.add_parser("template")
    template.add_argument("--handoff-dir", required=True)
    template.add_argument("--candidate-sha", required=True)
    template.add_argument("--candidate-version", required=True)
    template.add_argument("--out", required=True)

    finalize = sub.add_parser("finalize")
    finalize.add_argument("--handoff-dir", required=True)
    finalize.add_argument("--review", required=True)
    finalize.add_argument("--candidate-sha", required=True)
    finalize.add_argument("--candidate-version", required=True)
    finalize.add_argument("--out", required=True)

    validate = sub.add_parser("validate-committed")
    validate.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    validate.add_argument("--candidate-version", required=True)
    validate.add_argument("--release-source-sha", required=True)

    args = parser.parse_args()
    if args.command == "template":
        result = create_review_template(
            Path(args.handoff_dir),
            args.candidate_sha,
            args.candidate_version,
        )
        _write_new_json(Path(args.out), result)
    elif args.command == "finalize":
        result = finalize_approval(
            Path(args.handoff_dir),
            Path(args.review),
            args.candidate_sha,
            args.candidate_version,
        )
        _write_new_json(Path(args.out), result)
    else:
        result = validate_committed_approval(
            Path(args.repo_root),
            candidate_version=args.candidate_version,
            release_source_sha=args.release_source_sha,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") != NO_GO_STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())
