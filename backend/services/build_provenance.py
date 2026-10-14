"""Read and validate Chengzhu build/runtime provenance.

Packaged builds contain build-provenance.json inside the PyInstaller sidecar.
Source checkouts may synthesize the same shape for development/testing, but the
origin stays SOURCE_CHECKOUT and is not eligible for Stable pilot evidence.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


BUILD_PROVENANCE_CONTRACT = "v2.0-R1-build-provenance-1"
RUNTIME_FINGERPRINT_CONTRACT = "v2.0-R1-runtime-fingerprint-1"
PYTHON_ENVIRONMENT_CONTRACT = "v2.0-R1-python-build-environment-1"
PYTHON_ARTIFACT_PROVENANCE_CONTRACT = "v2.0-R1-python-artifact-provenance-1"


def _validate(value: dict[str, Any], *, origin: str) -> dict[str, Any]:
    if str(value.get("contract_version") or "") != BUILD_PROVENANCE_CONTRACT:
        raise ValueError("build provenance contract mismatch")
    version = str(value.get("app_version") or "").strip()
    source_sha = str(value.get("source_sha") or "").strip().lower()
    runtime = value.get("runtime_fingerprint")
    if not version:
        raise ValueError("build provenance app_version missing")
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("build provenance source_sha invalid")
    if not isinstance(runtime, dict):
        raise ValueError("build provenance runtime_fingerprint missing")
    if str(runtime.get("contract_version") or "") != RUNTIME_FINGERPRINT_CONTRACT:
        raise ValueError("runtime fingerprint contract mismatch")
    runtime_sha = str(runtime.get("sha256") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", runtime_sha):
        raise ValueError("runtime fingerprint sha256 invalid")
    files = runtime.get("files")
    if isinstance(files, bool) or not isinstance(files, int) or files <= 0:
        raise ValueError("runtime fingerprint files invalid")
    python_env = value.get("python_environment")
    if not isinstance(python_env, dict):
        raise ValueError("build provenance python_environment missing")
    if str(python_env.get("contract_version") or "") != PYTHON_ENVIRONMENT_CONTRACT:
        raise ValueError("Python build environment contract mismatch")
    distributions = python_env.get("distributions")
    if not isinstance(distributions, list) or any(not isinstance(item, str) for item in distributions):
        raise ValueError("Python build environment distributions invalid")
    if int(python_env.get("distributions_count") or -1) != len(distributions):
        raise ValueError("Python build environment distribution count mismatch")
    material = {
        "python_version": str(python_env.get("python_version") or ""),
        "implementation": str(python_env.get("implementation") or ""),
        "architecture": str(python_env.get("architecture") or ""),
        "distributions": list(distributions),
    }
    env_sha = str(python_env.get("sha256") or "").strip().lower()
    expected_env_sha = hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if not material["python_version"] or not material["implementation"]:
        raise ValueError("Python build environment metadata missing")
    if env_sha != expected_env_sha:
        raise ValueError("Python build environment SHA256 mismatch")

    artifact = python_env.get("artifact_provenance")
    validated_artifact: dict[str, Any] | None = None
    if artifact is not None:
        if not isinstance(artifact, dict):
            raise ValueError("Python artifact provenance invalid")
        if str(artifact.get("contract_version") or "") != PYTHON_ARTIFACT_PROVENANCE_CONTRACT:
            raise ValueError("Python artifact provenance contract mismatch")
        artifacts = artifact.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise ValueError("Python artifact provenance artifacts missing")
        if int(artifact.get("artifacts_count") or -1) != len(artifacts):
            raise ValueError("Python artifact provenance count mismatch")
        normalized: list[dict[str, str]] = []
        seen: set[str] = set()
        for row in artifacts:
            if not isinstance(row, dict):
                raise ValueError("Python artifact provenance row invalid")
            name = re.sub(r"[-_.]+", "-", str(row.get("name") or "").strip()).lower()
            version_value = str(row.get("version") or "").strip()
            filename = str(row.get("filename") or "").strip()
            sha256 = str(row.get("sha256") or "").strip().lower()
            if not name or not version_value or not filename.lower().endswith(".whl"):
                raise ValueError("Python artifact provenance row metadata invalid")
            if not re.fullmatch(r"[0-9a-f]{64}", sha256):
                raise ValueError("Python artifact provenance row SHA256 invalid")
            if name in seen:
                raise ValueError("Python artifact provenance duplicate distribution")
            seen.add(name)
            normalized.append({
                "name": name,
                "version": version_value,
                "filename": filename,
                "sha256": sha256,
            })
        normalized.sort(key=lambda row: row["name"])
        expected_artifact_sha = hashlib.sha256(
            json.dumps(
                {"artifacts": normalized},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        artifact_sha = str(artifact.get("sha256") or "").strip().lower()
        if artifact_sha != expected_artifact_sha:
            raise ValueError("Python artifact provenance SHA256 mismatch")
        distribution_map: dict[str, str] = {}
        for raw_distribution in distributions:
            match = re.fullmatch(
                r"(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<version>[^\s;]+)",
                str(raw_distribution or "").strip(),
            )
            if not match:
                raise ValueError("Python build environment distribution is not exact name==version")
            name = re.sub(r"[-_.]+", "-", match.group("name")).lower()
            version_value = match.group("version")
            if name in distribution_map and distribution_map[name] != version_value:
                raise ValueError("Python build environment duplicate distribution version conflict")
            distribution_map[name] = version_value
        artifact_map = {row["name"]: row["version"] for row in normalized}
        if artifact_map != distribution_map:
            raise ValueError(
                "Python artifact provenance set/version does not match resolved distributions"
            )
        validated_artifact = {
            "contract_version": PYTHON_ARTIFACT_PROVENANCE_CONTRACT,
            "artifacts": normalized,
            "artifacts_count": len(normalized),
            "sha256": artifact_sha,
            "install_mode": "WHEEL_SHA256_PINNED",
        }

    channel = str(value.get("release_channel") or "").upper()
    expected_channel = "PRERELEASE" if "-" in version else "STABLE"
    if channel != expected_channel:
        raise ValueError("build provenance release_channel/version mismatch")
    return {
        "contract_version": BUILD_PROVENANCE_CONTRACT,
        "app_version": version,
        "source_sha": source_sha,
        "release_channel": channel,
        "runtime_fingerprint": {
            "contract_version": RUNTIME_FINGERPRINT_CONTRACT,
            "sha256": runtime_sha,
            "files": files,
        },
        "python_environment": {
            "contract_version": PYTHON_ENVIRONMENT_CONTRACT,
            **material,
            "distributions_count": len(distributions),
            "sha256": env_sha,
            **({"artifact_provenance": validated_artifact} if validated_artifact else {}),
        },
        "runtime_origin": origin,
        "claim_boundary": "SOURCE_BUILD_PROVENANCE_NOT_REAL_USER_OR_BEHAVIORAL_EQUIVALENCE_PROOF",
    }


def _embedded_candidates() -> list[Path]:
    values: list[Path] = []
    explicit = str(os.environ.get("CHENGZHU_BUILD_PROVENANCE_FILE") or "").strip()
    if explicit:
        values.append(Path(explicit))
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        values.append(Path(str(meipass)) / "build-provenance.json")
    executable_dir = Path(sys.executable).resolve().parent
    values.append(executable_dir / "build-provenance.json")
    # Keep ordering stable while removing duplicates.
    seen: set[str] = set()
    out: list[Path] = []
    for path in values:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("build provenance JSON must be an object")
    return value


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _source_checkout_provenance() -> dict[str, Any]:
    repo = _repo_root()
    script = repo / "scripts" / "runtime_fingerprint.py"
    if not script.is_file():
        raise RuntimeError("source checkout runtime fingerprint tool unavailable")
    spec = importlib.util.spec_from_file_location("chengzhu_runtime_fingerprint", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load runtime fingerprint tool")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_provenance(
        repo,
        python_environment_value=module.python_environment(Path(sys.executable)),
    )


@lru_cache(maxsize=1)
def current_build_provenance() -> dict[str, Any]:
    for path in _embedded_candidates():
        if path.is_file():
            return _validate(_load_json(path), origin="PACKAGED_EMBEDDED")
    return _validate(_source_checkout_provenance(), origin="SOURCE_CHECKOUT")


def packaged_build_provenance() -> dict[str, Any]:
    value = current_build_provenance()
    if value["runtime_origin"] != "PACKAGED_EMBEDDED":
        raise ValueError("Stable pilot runtime provenance requires a packaged embedded build")
    return value
