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
