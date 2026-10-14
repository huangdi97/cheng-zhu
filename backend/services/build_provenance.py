"""Read and validate Chengzhu build/runtime provenance.

Packaged builds contain build-provenance.json inside the PyInstaller sidecar.
Source checkouts may synthesize the same shape for development/testing, but the
origin stays SOURCE_CHECKOUT and is not eligible for Stable pilot evidence.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


BUILD_PROVENANCE_CONTRACT = "v2.0-R1-build-provenance-1"
RUNTIME_FINGERPRINT_CONTRACT = "v2.0-R1-runtime-fingerprint-1"


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
    return module.build_provenance(repo)


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
