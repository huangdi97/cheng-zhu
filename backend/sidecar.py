"""Chengzhu backend sidecar entry (R2 Stage AG).

Built by PyInstaller into ``chengzhu-backend.exe`` and launched by Electron.
The packaged app therefore needs no system Python and no pip.

Usage:
  chengzhu-backend.exe --port 18080 [--host 127.0.0.1]
  chengzhu-backend.exe --screen-capture-worker <region> <max_long_edge>
  chengzhu-backend.exe --version

Environment (set by Electron):
  CHENGZHU_HOME           user-data root (%APPDATA%\\Chengzhu); all writes go here
  CHENGZHU_FRONTEND_DIST  prebuilt frontend dist bundled with the app

 SECURITY:
  - Binds 127.0.0.1 by default. LAN access is an explicit --host choice.
"""
from __future__ import annotations

import argparse
import os
import sys

APP_VERSION = "1.4.1"


def _run_screen_capture_worker(argv: list[str]) -> int:
    # Same contract as services/capture/_screen_capture_worker.py when run
    # as a script: argv = [region, max_long_edge]; prints JSON to stdout.
    import runpy

    here = os.path.dirname(os.path.abspath(__file__))
    worker = os.path.join(here, "services", "capture", "_screen_capture_worker.py")
    sys.argv = [worker, *argv]
    if os.path.isfile(worker):
        runpy.run_path(worker, run_name="__main__")
    else:
        runpy.run_module("services.capture._screen_capture_worker", run_name="__main__")
    return 0


def _force_utf8_stdio() -> None:
    """The frozen sidecar ignores PYTHONIOENCODING, so on a non-Chinese
    Windows locale (cp1252) stdout/stderr pipes could not encode the first
    Chinese print and the backend exited at first launch (v1.2.0)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--screen-capture-worker":
        return _run_screen_capture_worker(argv[1:])

    parser = argparse.ArgumentParser(prog="chengzhu-backend")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "18080")))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args(argv)
    if args.version:
        print(APP_VERSION)
        return 0

    # Make "import main" / "services.*" resolve from the bundle directory.
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    if (os.environ.get("CHENGZHU_HOME") or "").strip():
        cache = os.path.join(os.environ["CHENGZHU_HOME"], "cache")
        os.makedirs(cache, exist_ok=True)
        # Local STT model downloads land in the user cache, not the install dir.
        os.environ.setdefault("HF_HOME", os.path.join(cache, "huggingface"))

    import uvicorn

    from main import app

    uvicorn.run(app, host=args.host, port=args.port, log_level="info", access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
