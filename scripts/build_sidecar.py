"""Build the backend sidecar in a clean virtualenv (R2 Stage AG).

A clean venv containing only backend/requirements.txt + PyInstaller keeps the
bundle reproducible and small (a developer interpreter may carry torch /
tensorflow that optional imports would drag in).

Usage:  python scripts/build_sidecar.py [--python PATH]
Output: build/sidecar/chengzhu-backend/chengzhu-backend.exe
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / "build" / "sidecar-venv"


def run(cmd: list[str]) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=sys.executable, help="interpreter used to create the venv (3.11 recommended)")
    args = parser.parse_args()
    if not VENV.exists():
        run([args.python, "-m", "venv", str(VENV)])
    py = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run([str(py), "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
    run([str(py), "-m", "pip", "install", "-r", "backend/requirements.txt", "pyinstaller>=6.10,<7", "--quiet"])
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
