#!/usr/bin/env python3
"""Prepare hash-checked Python replay inputs for Chengzhu Stable v2+.

A Stable authorization carries the exact resolved Python environment and the
wheel SHA256 set from the packaged prerelease that produced real-pilot
evidence. This tool turns that frozen baseline into complete hash-checking
requirements for the later Stable build without allowing arbitrary URLs, VCS,
editable installs, environment markers or source distributions.

This is a build reproducibility control, not a signature or human-identity
system. The authoritative post-build gate remains
verify_stable_release_authorization.py, which compares the actually built
environment SHA256 to the pilot baseline.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import platform
import re
from pathlib import Path
from typing import Any

import runtime_fingerprint
import v2_stable_release_review_decision as decision_tool


CONTRACT_VERSION = "v2.0-R1-stable-python-environment-replay-1"
_PIN_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)=="
    r"(?P<version>[A-Za-z0-9][A-Za-z0-9.!+_-]*)$"
)
_PYTHON_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _decode_authorization(token: str) -> dict[str, Any]:
    token = str(token or "").strip()
    if not token:
        raise ValueError("Stable Python environment replay requires stable_review_authorization_b64")
    try:
        raw = base64.b64decode(token.encode("ascii"), validate=True)
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Stable release authorization is not valid base64 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("Stable release authorization must decode to a JSON object")
    return value


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _safe_distributions(distributions: Any) -> dict[str, str]:
    if not isinstance(distributions, list) or not distributions:
        raise ValueError("pilot Python environment distributions are missing")
    by_name: dict[str, str] = {}
    for raw in distributions:
        if not isinstance(raw, str):
            raise ValueError("pilot Python environment distribution must be a string")
        value = raw.strip()
        match = _PIN_RE.fullmatch(value)
        if not match:
            raise ValueError(
                "Stable replay accepts only exact name==version distributions; "
                f"unsafe or non-exact entry: {value!r}"
            )
        normalized = _normalize_name(match.group("name"))
        version = match.group("version")
        if normalized in by_name and by_name[normalized] != version:
            raise ValueError(f"conflicting duplicate distribution: {normalized}")
        by_name[normalized] = version
    return by_name


def _hashed_requirements(
    env: dict[str, Any],
    distributions: dict[str, str],
) -> tuple[list[str], list[str], str]:
    provenance = env.get("artifact_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("pilot Python environment is missing artifact provenance")
    if (
        str(provenance.get("contract_version") or "")
        != runtime_fingerprint.PYTHON_ARTIFACT_PROVENANCE_CONTRACT
    ):
        raise ValueError("pilot Python artifact provenance contract mismatch")
    artifacts = provenance.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("pilot Python artifact provenance is empty")
    if int(provenance.get("artifacts_count") or -1) != len(artifacts):
        raise ValueError("pilot Python artifact count mismatch")
    if str(provenance.get("install_mode") or "") != "WHEEL_SHA256_PINNED":
        raise ValueError("pilot Python artifact install mode mismatch")

    by_name: dict[str, dict[str, str]] = {}
    for raw in artifacts:
        if not isinstance(raw, dict):
            raise ValueError("pilot Python artifact row is invalid")
        name = _normalize_name(str(raw.get("name") or ""))
        version = str(raw.get("version") or "").strip()
        filename = str(raw.get("filename") or "").strip()
        sha256 = str(raw.get("sha256") or "").strip().lower()
        if not name or not version:
            raise ValueError("pilot Python artifact name/version missing")
        if not filename.lower().endswith(".whl"):
            raise ValueError(f"{name}=={version}: Stable replay requires wheel artifact")
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError(f"{name}=={version}: Stable replay artifact sha256 invalid")
        row = {
            "name": name,
            "version": version,
            "filename": filename,
            "sha256": sha256,
        }
        previous = by_name.get(name)
        if previous is not None and previous != row:
            raise ValueError(f"conflicting pilot Python artifact: {name}")
        by_name[name] = row

    material = {"artifacts": [by_name[name] for name in sorted(by_name)]}
    expected_artifact_sha = _canonical_sha256(material)
    artifact_sha = str(provenance.get("sha256") or "").strip().lower()
    if artifact_sha != expected_artifact_sha:
        raise ValueError("pilot Python artifact provenance SHA256 mismatch")

    if set(by_name) != set(distributions):
        missing = sorted(set(distributions) - set(by_name))
        unexpected = sorted(set(by_name) - set(distributions))
        raise ValueError(
            "pilot Python artifact set differs from resolved distribution set; "
            f"missing={missing}, unexpected={unexpected}"
        )
    for name, version in distributions.items():
        if by_name[name]["version"] != version:
            raise ValueError(
                f"pilot artifact version differs from resolved distribution: {name}"
            )

    lines = {
        name: f"{name}=={row['version']} --hash=sha256:{row['sha256']}"
        for name, row in by_name.items()
    }
    if "pip" not in lines:
        raise ValueError("pilot artifact provenance must include pip bootstrap wheel")
    bootstrap = [lines["pip"]]
    runtime = [lines[name] for name in sorted(lines) if name != "pip"]
    if not runtime:
        raise ValueError("pilot artifact provenance has no runtime distributions")
    return bootstrap, runtime, artifact_sha


def prepare_replay(
    authorization_b64: str,
    *,
    source_sha: str,
    version: str,
    runtime_fingerprint_sha256: str,
    required_python_version: str,
    current_python: dict[str, str] | None = None,
) -> dict[str, Any]:
    value = _decode_authorization(authorization_b64)
    source_sha = str(source_sha or "").strip().lower()
    version = str(version or "").strip()
    runtime_sha = str(runtime_fingerprint_sha256 or "").strip().lower()
    required_python_version = str(required_python_version or "").strip()

    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("source_sha must be a full 40-character git SHA")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Stable Python replay applies only to stable SemVer")
    if int(version.split(".", 1)[0]) < 2:
        raise ValueError("Stable Python replay applies only to Stable major version >= 2")
    if not re.fullmatch(r"[0-9a-f]{64}", runtime_sha):
        raise ValueError("runtime_fingerprint_sha256 must be a 64-character SHA256")
    if not _PYTHON_VERSION_RE.fullmatch(required_python_version):
        raise ValueError("required Python version must be an exact major.minor.patch value")

    if str(value.get("contract_version") or "") != decision_tool.AUTHORIZATION_CONTRACT:
        raise ValueError("unsupported Stable release authorization contract")
    if str(value.get("decision") or "") != "GO":
        raise ValueError("Stable release authorization decision is not GO")
    if value.get("eligible_for_stable_release_workflow") is not True:
        raise ValueError("Stable release authorization is not eligible for the Stable workflow")
    if str(value.get("candidate_source_sha") or "").strip().lower() != source_sha:
        raise ValueError("Stable release authorization source SHA does not match candidate")
    if str(value.get("candidate_version") or "").strip() != version:
        raise ValueError("Stable release authorization version does not match candidate")
    if value.get("runtime_baseline_match") is not True:
        raise ValueError("Stable release authorization does not carry a runtime-baseline match")

    for label in ("pilot_runtime_fingerprint", "candidate_runtime_fingerprint"):
        runtime = value.get(label)
        if not isinstance(runtime, dict):
            raise ValueError(f"Stable release authorization {label} missing")
        if str(runtime.get("contract_version") or "") != runtime_fingerprint.CONTRACT_VERSION:
            raise ValueError(f"Stable release authorization {label} contract mismatch")
        if str(runtime.get("sha256") or "").strip().lower() != runtime_sha:
            raise ValueError(f"Stable release authorization {label} differs from candidate runtime")

    env = value.get("pilot_python_environment")
    if not isinstance(env, dict):
        raise ValueError("Stable release authorization is missing pilot Python environment")
    if str(env.get("contract_version") or "") != runtime_fingerprint.PYTHON_ENVIRONMENT_CONTRACT:
        raise ValueError("pilot Python environment contract mismatch")
    distributions = env.get("distributions")
    distribution_map = _safe_distributions(distributions)
    if int(env.get("distributions_count") or -1) != len(distributions):
        raise ValueError("pilot Python environment distribution count mismatch")

    material = {
        "python_version": str(env.get("python_version") or "").strip(),
        "implementation": str(env.get("implementation") or "").strip(),
        "architecture": str(env.get("architecture") or "").strip(),
        "distributions": list(distributions),
    }
    if material["python_version"] != required_python_version:
        raise ValueError(
            "pilot Python version differs from repository-pinned sidecar Python version"
        )
    if material["implementation"] != "CPython":
        raise ValueError("Stable sidecar replay requires CPython")
    if not material["architecture"]:
        raise ValueError("pilot Python architecture is missing")

    expected_env_sha = _canonical_sha256(material)
    env_sha = str(env.get("sha256") or "").strip().lower()
    if env_sha != expected_env_sha:
        raise ValueError("pilot Python environment SHA256 mismatch")

    current = current_python or {
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "architecture": platform.machine() or "UNKNOWN",
    }
    current = {key: str(value or "").strip() for key, value in current.items()}
    for field in ("python_version", "implementation", "architecture"):
        if current.get(field) != material[field]:
            raise ValueError(
                f"Stable build interpreter {field} differs from pilot baseline: "
                f"{current.get(field) or 'UNKNOWN'} != {material[field]}"
            )

    bootstrap_requirements, runtime_requirements, artifact_sha = _hashed_requirements(
        env,
        distribution_map,
    )

    return {
        "contract_version": CONTRACT_VERSION,
        "candidate_source_sha": source_sha,
        "candidate_version": version,
        "runtime_fingerprint_sha256": runtime_sha,
        "pilot_python_environment_sha256": env_sha,
        "pilot_python_artifact_provenance_sha256": artifact_sha,
        "python_version": material["python_version"],
        "implementation": material["implementation"],
        "architecture": material["architecture"],
        "bootstrap_requirements": bootstrap_requirements,
        "runtime_requirements": runtime_requirements,
        "requirements_count": len(bootstrap_requirements) + len(runtime_requirements),
        "hashed_requirements_sha256": hashlib.sha256(
            (
                "\n".join(bootstrap_requirements)
                + "\n--RUNTIME--\n"
                + "\n".join(runtime_requirements)
                + "\n"
            ).encode("utf-8")
        ).hexdigest(),
        "claim_boundary": (
            "WHEEL_SHA256_HASH_CHECKING_REPLAY_INPUT_NOT_RELEASE_AUTHORIZATION_"
            "OR_POST_BUILD_ENVIRONMENT_PROOF"
        ),
    }


def _write_new(path: Path, data: str) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as fh:
        fh.write(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization-b64", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--runtime-fingerprint-sha256", required=True)
    parser.add_argument(
        "--python-version-file",
        default=str(Path(__file__).resolve().parents[1] / "packaging" / "sidecar-python-version.txt"),
    )
    parser.add_argument("--bootstrap-requirements-out", required=True)
    parser.add_argument("--runtime-requirements-out", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    version_path = Path(args.python_version_file)
    if not version_path.is_file():
        parser.error(f"sidecar Python version file missing: {version_path}")
    required = version_path.read_text(encoding="utf-8").strip()
    try:
        replay = prepare_replay(
            args.authorization_b64,
            source_sha=args.source_sha,
            version=args.version,
            runtime_fingerprint_sha256=args.runtime_fingerprint_sha256,
            required_python_version=required,
        )
        bootstrap_path = Path(args.bootstrap_requirements_out)
        runtime_path = Path(args.runtime_requirements_out)
        out_path = Path(args.out)
        resolved = {
            bootstrap_path.resolve(),
            runtime_path.resolve(),
            out_path.resolve(),
        }
        if len(resolved) != 3:
            raise ValueError("Stable replay outputs must use distinct paths")
        _write_new(
            bootstrap_path,
            "\n".join(replay["bootstrap_requirements"]) + "\n",
        )
        _write_new(
            runtime_path,
            "\n".join(replay["runtime_requirements"]) + "\n",
        )
        public = {
            key: value
            for key, value in replay.items()
            if key not in {"bootstrap_requirements", "runtime_requirements"}
        }
        _write_new(
            out_path,
            json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
    except (FileExistsError, ValueError) as exc:
        parser.error(str(exc))

    print(json.dumps({
        "status": "STABLE_PYTHON_ENVIRONMENT_REPLAY_READY",
        "python_version": replay["python_version"],
        "requirements_count": replay["requirements_count"],
        "pilot_python_environment_sha256": replay["pilot_python_environment_sha256"],
        "pilot_python_artifact_provenance_sha256": replay["pilot_python_artifact_provenance_sha256"],
        "out": args.out,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
