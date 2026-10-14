#!/usr/bin/env python3
"""Compute Chengzhu product-runtime source fingerprint.

This fingerprint is intentionally different from a git commit SHA:
- it includes only runtime-affecting source/dependency/package inputs;
- pure application version bumps are normalized away;
- release/docs/tests/evaluator-only changes do not change the fingerprint.

That allows a Stable candidate to prove it is behaviorally sourced from the
same product runtime that produced the real-pilot evidence, even though the
Stable candidate necessarily has a different SemVer/source commit.

This is a source/build provenance control, not a behavioral equivalence proof.
If the fingerprint differs, Stable promotion fails closed and requires a new
pilot baseline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Iterable


CONTRACT_VERSION = "v2.0-R1-runtime-fingerprint-1"

# Runtime-bearing tracked paths. Keep evaluator/release/tests/docs out; include
# packaging/build inputs that can change the shipped product.
ROOT_FILES = (
    "backend/main.py",
    "backend/sidecar.py",
    "backend/requirements.txt",
    "frontend/package.json",
    "frontend/package-lock.json",
    "desktop/package.json",
    "desktop/package-lock.json",
    "packaging/chengzhu-backend.spec",
    "scripts/build_sidecar.py",
    "scripts/runtime_fingerprint.py",
)
ROOT_PREFIXES = (
    "backend/api/",
    "backend/core/",
    "backend/services/",
    "backend/assets/",
    "frontend/src/",
    "frontend/public/",
    "desktop/",
    "packaging/",
)
DESKTOP_RUNTIME_EXTENSIONS = {".js", ".json", ".png", ".ico"}


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def _tracked_files(repo: Path) -> list[str]:
    try:
        values = _git(repo, "ls-files").splitlines()
    except (OSError, subprocess.CalledProcessError):
        values = [
            str(path.relative_to(repo)).replace("\\", "/")
            for path in repo.rglob("*")
            if path.is_file()
        ]
    return sorted({value.replace("\\", "/") for value in values if value})


def _include(relative: str) -> bool:
    if relative in ROOT_FILES:
        return True
    if relative.startswith(("backend/tests/", "backend/evals/")):
        return False
    if relative.startswith("backend/"):
        return any(relative.startswith(prefix) for prefix in ROOT_PREFIXES)
    if relative.startswith("frontend/"):
        return any(relative.startswith(prefix) for prefix in ROOT_PREFIXES)
    if relative.startswith("desktop/"):
        if relative in {"desktop/package.json", "desktop/package-lock.json"}:
            return True
        return Path(relative).suffix.lower() in DESKTOP_RUNTIME_EXTENSIONS
    if relative.startswith("packaging/"):
        return True
    return False


def _normalize_package_json(relative: str, raw: bytes) -> bytes:
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{relative}: expected JSON object")
    # Only normalize the app/root version. Dependency versions remain part of
    # the runtime fingerprint.
    if relative.endswith("package-lock.json"):
        if "version" in value:
            value["version"] = "__APP_VERSION__"
        packages = value.get("packages")
        if isinstance(packages, dict):
            root = packages.get("")
            if isinstance(root, dict) and "version" in root:
                root["version"] = "__APP_VERSION__"
    elif "version" in value:
        value["version"] = "__APP_VERSION__"
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _normalized_bytes(relative: str, raw: bytes) -> bytes:
    if relative in {
        "frontend/package.json",
        "frontend/package-lock.json",
        "desktop/package.json",
        "desktop/package-lock.json",
    }:
        return _normalize_package_json(relative, raw)
    if relative == "backend/sidecar.py":
        text = raw.decode("utf-8")
        text = re.sub(
            r'(?m)^APP_VERSION\s*=\s*["\'][^"\']+["\']\s*$',
            'APP_VERSION = "__APP_VERSION__"',
            text,
        )
        return text.encode("utf-8")
    return raw


def fingerprint(repo: Path) -> dict[str, object]:
    repo = repo.resolve()
    files: list[dict[str, object]] = []
    digest = hashlib.sha256()
    for relative in _tracked_files(repo):
        if not _include(relative):
            continue
        path = repo / relative
        if not path.is_file():
            continue
        normalized = _normalized_bytes(relative, path.read_bytes())
        file_sha = hashlib.sha256(normalized).hexdigest()
        files.append({
            "path": relative,
            "sha256": file_sha,
            "bytes": len(normalized),
        })
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_sha.encode("ascii"))
        digest.update(b"\n")
    if not files:
        raise RuntimeError("runtime fingerprint input set is empty")
    return {
        "contract_version": CONTRACT_VERSION,
        "sha256": digest.hexdigest(),
        "files": len(files),
        "inputs": files,
    }


def source_sha(repo: Path) -> str:
    value = _git(repo.resolve(), "rev-parse", "HEAD").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("git HEAD is not a full 40-character SHA")
    return value


def app_version(repo: Path) -> str:
    value = json.loads((repo / "frontend" / "package.json").read_text(encoding="utf-8"))
    version = str(value.get("version") or "").strip()
    if not version:
        raise ValueError("frontend/package.json has no version")
    return version


def build_provenance(
    repo: Path,
    *,
    exact_source_sha: str | None = None,
    exact_version: str | None = None,
) -> dict[str, object]:
    repo = repo.resolve()
    sha = str(exact_source_sha or source_sha(repo)).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("source_sha must be a full 40-character git SHA")
    version = str(exact_version or app_version(repo)).strip()
    if not version:
        raise ValueError("version is required")
    runtime = fingerprint(repo)
    return {
        "contract_version": "v2.0-R1-build-provenance-1",
        "app_version": version,
        "source_sha": sha,
        "release_channel": "PRERELEASE" if "-" in version else "STABLE",
        "runtime_fingerprint": {
            "contract_version": runtime["contract_version"],
            "sha256": runtime["sha256"],
            "files": runtime["files"],
        },
        "claim_boundary": "SOURCE_BUILD_PROVENANCE_NOT_REAL_USER_OR_BEHAVIORAL_EQUIVALENCE_PROOF",
    }


def write_json(path: Path, value: object) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--source-sha", default="")
    parser.add_argument("--version", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--full", action="store_true", help="include per-file inputs")
    args = parser.parse_args()

    repo = Path(args.repo_root)
    provenance = build_provenance(
        repo,
        exact_source_sha=args.source_sha or None,
        exact_version=args.version or None,
    )
    if args.full:
        provenance["runtime_fingerprint_full"] = fingerprint(repo)
    if args.out:
        write_json(Path(args.out), provenance)
    print(json.dumps(provenance, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
