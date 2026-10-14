#!/usr/bin/env python3
"""Verify Chengzhu Stable v2+ release authorization passed to GitHub Actions.

Prereleases never require a Stable authorization. Legacy v1 stable releases are
left unchanged. Stable major versions >= 2 fail closed unless the caller
supplies a valid GO authorization produced from a human Stable release review.

This validates structure/provenance binding, not human identity or truthfulness.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import v2_conversation_stable_review_handoff as handoff_tool
import v2_stable_release_review_decision as decision_tool


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _version_kind(version: str) -> tuple[bool, int]:
    value = str(version or "").strip()
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)(?:-([0-9A-Za-z.-]+))?", value)
    if not match:
        raise ValueError("version is not supported SemVer")
    return bool(match.group(4)), int(match.group(1))


def verify_authorization(
    authorization_b64: str,
    *,
    source_sha: str,
    version: str,
    runtime_fingerprint_sha256: str = "",
) -> dict[str, Any]:
    is_prerelease, major = _version_kind(version)
    source_sha = str(source_sha or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("source_sha must be a full 40-character git SHA")

    if is_prerelease:
        return {
            "required": False,
            "status": "NOT_REQUIRED_PRERELEASE",
            "version": version,
            "source_sha": source_sha,
            "claims": {"V2_STABLE_RELEASE": False, "PMF_PROVEN": False},
        }
    if major < 2:
        return {
            "required": False,
            "status": "NOT_REQUIRED_LEGACY_STABLE",
            "version": version,
            "source_sha": source_sha,
        }

    runtime_fingerprint_sha256 = str(runtime_fingerprint_sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", runtime_fingerprint_sha256):
        raise ValueError("Stable v2+ publication requires a valid candidate runtime fingerprint SHA256")

    token = str(authorization_b64 or "").strip()
    if not token:
        raise ValueError("Stable v2+ publication requires stable_review_authorization_b64")
    try:
        raw = base64.b64decode(token.encode("ascii"), validate=True)
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Stable release authorization is not valid base64 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("Stable release authorization must decode to a JSON object")

    if str(value.get("contract_version") or "") != decision_tool.AUTHORIZATION_CONTRACT:
        raise ValueError("unsupported Stable release authorization contract")
    if str(value.get("decision") or "") != "GO":
        raise ValueError("Stable release authorization decision is not GO")
    if value.get("eligible_for_stable_release_workflow") is not True:
        raise ValueError("Stable release authorization is not workflow-eligible")
    if str(value.get("candidate_source_sha") or "").lower() != source_sha:
        raise ValueError("Stable release authorization source SHA does not match release source")
    if str(value.get("candidate_version") or "") != version:
        raise ValueError("Stable release authorization version does not match release version")
    if str(value.get("handoff_contract_version") or "") != handoff_tool.CONTRACT_VERSION:
        raise ValueError("Stable release authorization handoff contract mismatch")
    if not re.fullmatch(r"[0-9a-f]{64}", str(value.get("handoff_json_sha256") or "")):
        raise ValueError("Stable release authorization is missing a valid handoff SHA256")

    pilot_runtime = value.get("pilot_runtime_fingerprint")
    candidate_runtime = value.get("candidate_runtime_fingerprint")
    if not isinstance(pilot_runtime, dict) or not isinstance(candidate_runtime, dict):
        raise ValueError("Stable release authorization is missing runtime baseline provenance")
    for label, runtime in (
        ("pilot", pilot_runtime),
        ("candidate", candidate_runtime),
    ):
        if str(runtime.get("contract_version") or "") != "v2.0-R1-runtime-fingerprint-1":
            raise ValueError(f"Stable release authorization {label} runtime contract mismatch")
        if not re.fullmatch(r"[0-9a-f]{64}", str(runtime.get("sha256") or "")):
            raise ValueError(f"Stable release authorization {label} runtime SHA256 invalid")
    if value.get("runtime_baseline_match") is not True:
        raise ValueError("Stable release authorization does not prove runtime-baseline match")
    pilot_runtime_sha = str(pilot_runtime.get("sha256") or "").lower()
    candidate_runtime_sha = str(candidate_runtime.get("sha256") or "").lower()
    if pilot_runtime_sha != candidate_runtime_sha:
        raise ValueError("Stable release authorization pilot/candidate runtime fingerprints differ")
    if candidate_runtime_sha != runtime_fingerprint_sha256:
        raise ValueError("Stable release authorization runtime fingerprint does not match release candidate")

    expected_ids = [check_id for check_id, _reason in handoff_tool.REQUIRED_RELEASE_REVIEW_CHECKS]
    checks = list(value.get("checks") or [])
    if [str(row.get("id") or "") for row in checks] != expected_ids:
        raise ValueError("Stable release authorization check set/order drift")
    if any(str(row.get("state") or "") != "PASS" for row in checks):
        raise ValueError("Stable release authorization contains a non-PASS review check")

    claims = dict(value.get("claims") or {})
    required_claims = {
        "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW": True,
        "V2_STABLE_RELEASE": False,
        "REAL_USER_IDENTITY_SYSTEM_VERIFIED": False,
        "REVIEWER_INDEPENDENCE_SYSTEM_VERIFIED": False,
        "PARTICIPANT_CONSENT_SYSTEM_VERIFIED": False,
        "PMF_PROVEN": False,
    }
    if claims != required_claims:
        raise ValueError("Stable release authorization claim boundary drift")

    if str(value.get("boundary") or "") != "AUTHORIZATION_IS_NOT_PUBLICATION":
        raise ValueError("Stable release authorization boundary drift")

    digest = _canonical_sha256(checks)
    if str(value.get("review_check_digest") or "") != digest:
        raise ValueError("Stable release authorization review-check digest mismatch")

    return {
        "required": True,
        "status": "VERIFIED_HUMAN_STABLE_RELEASE_REVIEW_GO",
        "version": version,
        "source_sha": source_sha,
        "runtime_fingerprint_sha256": runtime_fingerprint_sha256,
        "pilot_runtime_fingerprint_sha256": pilot_runtime_sha,
        "authorization": value,
        "authorization_token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
        "claims": required_claims,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization-b64", default="")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--runtime-fingerprint-sha256", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        result = verify_authorization(
            args.authorization_b64,
            source_sha=args.source_sha,
            version=args.version,
            runtime_fingerprint_sha256=args.runtime_fingerprint_sha256,
        )
        _write_json(Path(args.out), result)
        print(json.dumps({
            "required": result["required"],
            "status": result["status"],
            "version": result["version"],
            "source_sha": result["source_sha"],
            "runtime_fingerprint_sha256": result.get("runtime_fingerprint_sha256"),
        }, ensure_ascii=False))
        return 0
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
