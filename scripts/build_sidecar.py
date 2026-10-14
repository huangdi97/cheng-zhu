"""Build the backend sidecar in a clean virtualenv (R2 Stage AG).

A clean venv containing only backend/requirements.txt + PyInstaller keeps the
bundle reproducible and small (a developer interpreter may carry torch /
tensorflow that optional imports would drag in).

Usage:  python scripts/build_sidecar.py [--python PATH] [--clean]
Output: build/sidecar/chengzhu-backend/chengzhu-backend.exe
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import runtime_fingerprint

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / "build" / "sidecar-venv"
PYTHON_VERSION_FILE = ROOT / "packaging" / "sidecar-python-version.txt"


def required_python_version() -> str:
    if not PYTHON_VERSION_FILE.is_file():
        raise RuntimeError(f"sidecar Python version file missing: {PYTHON_VERSION_FILE}")
    value = PYTHON_VERSION_FILE.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value):
        raise RuntimeError("sidecar Python version must be exact major.minor.patch")
    return value


def interpreter_version(executable: str | Path) -> str:
    return subprocess.check_output(
        [
            str(executable),
            "-c",
            "import platform; print(platform.python_version())",
        ],
        text=True,
        cwd=ROOT,
    ).strip()


def run(cmd: list[str]) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def _existing_file_from_env(name: str) -> Path | None:
    value = str(os.environ.get(name) or "").strip()
    if not value:
        return None
    path = Path(value).resolve()
    if not path.is_file():
        raise RuntimeError(f"{name} does not exist: {path}")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=sys.executable, help="interpreter used to create the venv")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="remove any existing sidecar venv before building (required by CI/release)",
    )
    args = parser.parse_args()

    required = required_python_version()
    actual = interpreter_version(args.python)
    if actual != required:
        raise RuntimeError(
            f"sidecar build requires Python {required}, got {actual}; "
            f"use --python with the pinned interpreter from {PYTHON_VERSION_FILE}"
        )

    if args.clean and VENV.exists():
        shutil.rmtree(VENV)
    if not VENV.exists():
        run([args.python, "-m", "venv", str(VENV)])
    py = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    venv_version = interpreter_version(py)
    if venv_version != required:
        raise RuntimeError(
            f"existing sidecar venv uses Python {venv_version}, expected {required}; "
            "re-run with --clean"
        )
    provenance_dir = ROOT / "build" / "provenance"
    provenance_dir.mkdir(parents=True, exist_ok=True)
    bootstrap_report = provenance_dir / "pip-bootstrap-install-report.json"
    runtime_report = provenance_dir / "pip-runtime-install-report.json"
    for report in (bootstrap_report, runtime_report):
        if report.exists():
            report.unlink()

    stable_bootstrap = _existing_file_from_env("CHENGZHU_STABLE_PYTHON_BOOTSTRAP_REQUIREMENTS")
    stable_runtime = _existing_file_from_env("CHENGZHU_STABLE_PYTHON_RUNTIME_REQUIREMENTS")
    if bool(stable_bootstrap) != bool(stable_runtime):
        raise RuntimeError("Stable Python hash replay requires both bootstrap and runtime requirement files")

    common_install = [
        "--no-cache-dir",
        "--only-binary",
        ":all:",
    ]
    if stable_bootstrap and stable_runtime:
        run([
            str(py), "-m", "pip", "install",
            "--force-reinstall",
            "--require-hashes",
            *common_install,
            "--report", str(bootstrap_report),
            "-r", str(stable_bootstrap),
            "--quiet",
        ])
        run([
            str(py), "-m", "pip", "install",
            "--require-hashes",
            *common_install,
            "--report", str(runtime_report),
            "-r", str(stable_runtime),
            "--quiet",
        ])
    else:
        # Force a network-resolved pip wheel into the report as well.  The
        # final artifact provenance must cover every distribution in pip freeze,
        # including the build installer itself.
        run([
            str(py), "-m", "pip", "install",
            "--upgrade",
            "--force-reinstall",
            *common_install,
            "--report", str(bootstrap_report),
            "pip",
            "--quiet",
        ])
        run([
            str(py), "-m", "pip", "install",
            *common_install,
            "--report", str(runtime_report),
            "-r", "backend/requirements.txt",
            "pyinstaller>=6.10,<7",
            "--quiet",
        ])

    provenance_path = provenance_dir / "build-provenance.json"
    python_env = runtime_fingerprint.python_environment(
        py,
        install_report_paths=[bootstrap_report, runtime_report],
        require_artifact_provenance=True,
    )
    expected_env_sha = str(
        os.environ.get("CHENGZHU_EXPECTED_PYTHON_ENVIRONMENT_SHA256") or ""
    ).strip().lower()
    if expected_env_sha and python_env["sha256"] != expected_env_sha:
        raise RuntimeError(
            "resolved sidecar Python environment does not match the Stable pilot baseline: "
            f"{python_env['sha256']} != {expected_env_sha}"
        )
    expected_artifact_sha = str(
        os.environ.get("CHENGZHU_EXPECTED_PYTHON_ARTIFACT_PROVENANCE_SHA256") or ""
    ).strip().lower()
    artifact = python_env.get("artifact_provenance") or {}
    artifact_sha = str(artifact.get("sha256") or "").strip().lower()
    if expected_artifact_sha and artifact_sha != expected_artifact_sha:
        raise RuntimeError(
            "resolved sidecar Python artifacts do not match the Stable pilot baseline: "
            f"{artifact_sha or 'MISSING'} != {expected_artifact_sha}"
        )
    provenance = runtime_fingerprint.build_provenance(
        ROOT,
        exact_source_sha=(os.environ.get("CHENGZHU_RELEASE_SOURCE_SHA") or None),
        python_environment_value=python_env,
    )
    runtime_fingerprint.write_json(provenance_path, provenance)
    print(
        "build provenance:",
        provenance["app_version"],
        provenance["source_sha"],
        provenance["runtime_fingerprint"]["sha256"],
        provenance["python_environment"]["sha256"],
        provenance["python_environment"]["artifact_provenance"]["sha256"],
        flush=True,
    )

    run([
        str(py), "-m", "PyInstaller", "packaging/chengzhu-backend.spec", "--noconfirm",
        "--distpath", "build/sidecar", "--workpath", "build/pyinstaller",
    ])
    exe = ROOT / "build" / "sidecar" / "chengzhu-backend" / ("chengzhu-backend.exe" if os.name == "nt" else "chengzhu-backend")
    if not exe.exists():
        print("sidecar executable missing:", exe)
        return 1
    print("sidecar ready:", exe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
