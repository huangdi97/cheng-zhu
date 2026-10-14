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
from urllib.parse import unquote, urlparse


CONTRACT_VERSION = "v2.0-R1-runtime-fingerprint-1"
PYTHON_ENVIRONMENT_CONTRACT = "v2.0-R1-python-build-environment-1"
PYTHON_ARTIFACT_PROVENANCE_CONTRACT = "v2.0-R1-python-artifact-provenance-1"

# Runtime-bearing tracked paths. Keep evaluator/release/tests/docs out; include
# packaging/build inputs that can change the shipped product.
ROOT_FILES = (
    "backend/main.py",
    "backend/sidecar.py",
    "backend/requirements.txt",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/index.html",
    "frontend/vite.config.ts",
    "frontend/tsconfig.json",
    "frontend/tailwind.config.js",
    "frontend/postcss.config.js",
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
DESKTOP_RUNTIME_EXTENSIONS = {".js", ".json", ".html", ".css", ".png", ".ico", ".svg"}


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
        if relative.startswith((
            "frontend/e2e/",
            "frontend/scripts/",
            "frontend/src/test/",
        )):
            return False
        name = Path(relative).name
        if ".test." in name or ".spec." in name:
            return False
        return relative.startswith(("frontend/src/", "frontend/public/"))
    if relative.startswith("desktop/"):
        name = Path(relative).name
        if ".test." in name or ".spec." in name:
            return False
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


def _normalize_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", str(value or "").strip()).lower()


def _distribution_pairs(distributions: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in distributions:
        value = str(raw or "").strip()
        match = re.fullmatch(
            r"(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<version>[^\s;]+)",
            value,
        )
        if not match:
            raise ValueError(
                "packaged Python environment requires exact name==version distributions; "
                f"unsupported freeze entry: {value!r}"
            )
        name = _normalize_distribution_name(match.group("name"))
        version = match.group("version")
        previous = out.get(name)
        if previous is not None and previous != version:
            raise ValueError(f"conflicting packaged Python distribution versions: {name}")
        out[name] = version
    return out


def python_artifact_provenance(
    install_report_paths: Iterable[Path | str],
    *,
    distributions: list[str],
) -> dict[str, object]:
    expected = _distribution_pairs(distributions)
    artifacts_by_name: dict[str, dict[str, str]] = {}

    for raw_path in install_report_paths:
        path = Path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(f"pip installation report missing: {path}")
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict) or str(report.get("version") or "") != "1":
            raise ValueError(f"unsupported pip installation report: {path}")
        install = report.get("install")
        if not isinstance(install, list):
            raise ValueError(f"pip installation report has no install list: {path}")

        for row in install:
            if not isinstance(row, dict):
                raise ValueError(f"pip installation report row is invalid: {path}")
            metadata = row.get("metadata")
            download = row.get("download_info")
            if not isinstance(metadata, dict) or not isinstance(download, dict):
                raise ValueError("pip report entry is missing metadata/download_info")
            if bool(row.get("is_direct")):
                raise ValueError("direct/VCS/local Python distributions are not replay-safe")
            if bool(row.get("is_yanked")):
                raise ValueError("yanked Python distributions are not accepted for pilot baseline")

            name = _normalize_distribution_name(str(metadata.get("name") or ""))
            version = str(metadata.get("version") or "").strip()
            if not name or not version:
                raise ValueError("pip report entry is missing package name/version")

            archive = download.get("archive_info")
            hashes = archive.get("hashes") if isinstance(archive, dict) else None
            sha256 = str((hashes or {}).get("sha256") or "").strip().lower()
            if not re.fullmatch(r"[0-9a-f]{64}", sha256):
                raise ValueError(
                    f"{name}=={version}: pip report is missing archive sha256"
                )

            url = str(download.get("url") or "").strip()
            filename = unquote(Path(urlparse(url).path).name)
            if not filename.lower().endswith(".whl"):
                raise ValueError(
                    f"{name}=={version}: only wheel artifacts are accepted for replay"
                )

            artifact = {
                "name": name,
                "version": version,
                "filename": filename,
                "sha256": sha256,
            }
            previous = artifacts_by_name.get(name)
            if previous is not None and previous != artifact:
                raise ValueError(f"conflicting artifact provenance for distribution: {name}")
            artifacts_by_name[name] = artifact

    missing = sorted(set(expected) - set(artifacts_by_name))
    unexpected = sorted(set(artifacts_by_name) - set(expected))
    if missing:
        raise ValueError(
            "pip artifact provenance does not cover final environment distributions: "
            + ", ".join(missing)
        )
    if unexpected:
        raise ValueError(
            "pip artifact provenance contains packages absent from final environment: "
            + ", ".join(unexpected)
        )
    for name, version in expected.items():
        if artifacts_by_name[name]["version"] != version:
            raise ValueError(
                f"artifact version differs from final environment: {name} "
                f"{artifacts_by_name[name]['version']} != {version}"
            )

    artifacts = [artifacts_by_name[name] for name in sorted(artifacts_by_name)]
    material = {"artifacts": artifacts}
    raw = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "contract_version": PYTHON_ARTIFACT_PROVENANCE_CONTRACT,
        "artifacts": artifacts,
        "artifacts_count": len(artifacts),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "install_mode": "WHEEL_SHA256_PINNED",
    }


def python_environment(
    python_executable: Path | str,
    *,
    install_report_paths: Iterable[Path | str] | None = None,
    require_artifact_provenance: bool = False,
) -> dict[str, object]:
    python_executable = str(python_executable)
    meta_raw = subprocess.check_output(
        [
            python_executable,
            "-c",
            (
                "import json,platform,sys;"
                "print(json.dumps({"
                "'python_version':platform.python_version(),"
                "'implementation':platform.python_implementation(),"
                "'architecture':platform.machine() or 'UNKNOWN'"
                "},sort_keys=True))"
            ),
        ],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()
    meta = json.loads(meta_raw)
    freeze_raw = subprocess.check_output(
        [python_executable, "-m", "pip", "freeze", "--all"],
        text=True,
        stderr=subprocess.DEVNULL,
    )
    distributions = sorted(
        line.strip()
        for line in freeze_raw.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    material = {
        "python_version": str(meta.get("python_version") or ""),
        "implementation": str(meta.get("implementation") or ""),
        "architecture": str(meta.get("architecture") or ""),
        "distributions": distributions,
    }
    if not material["python_version"] or not material["implementation"]:
        raise ValueError("could not determine Python build environment")
    raw = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    result: dict[str, object] = {
        "contract_version": PYTHON_ENVIRONMENT_CONTRACT,
        **material,
        "distributions_count": len(distributions),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    report_paths = list(install_report_paths or [])
    if report_paths:
        result["artifact_provenance"] = python_artifact_provenance(
            report_paths,
            distributions=distributions,
        )
    elif require_artifact_provenance:
        raise ValueError("packaged build requires pip artifact provenance reports")
    return result


def build_provenance(
    repo: Path,
    *,
    exact_source_sha: str | None = None,
    exact_version: str | None = None,
    python_environment_value: dict[str, object] | None = None,
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
        "python_environment": python_environment_value,
        "provenance_level": "PACKAGED_BUILD" if python_environment_value else "SOURCE_CANDIDATE",
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
