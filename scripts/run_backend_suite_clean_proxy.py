#!/usr/bin/env python
"""Run the backend suite on a machine whose NO_PROXY contains a bracketed IPv6.

Why this wrapper exists
-----------------------
httpx 0.28.x builds its default client mounts from the process proxy
environment. It treats every comma-separated ``no_proxy`` entry as a
``URLPattern``, and a bracketed IPv6 literal such as ``[::1]`` makes it raise
``httpx.InvalidURL: Invalid port: ':1]'``.

``no_proxy`` is read case-insensitively by httpx, and on Windows an environment
variable set in one case is also visible in the other. Stripping only
``NO_PROXY`` is therefore not enough: ``no_proxy`` still carries the entry.

The value must also be re-created rather than assigned: on Windows, assigning to
an existing ``os.environ`` key does not reliably propagate the new value to child
processes, which is why an assignment-only fix looks like it works (the parent's
own ``httpx.Client()`` then succeeds) while the pytest child still fails.

This wrapper removes the offending entry from every case variant, then runs
pytest in the sanitised environment.

This is an environment workaround for this machine only. It changes no product
code and no test contract; the suite it runs is the unmodified repository suite.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

BRACKETED_IPV6 = re.compile(r"^\[[0-9A-Fa-f:.]+\]$")


def sanitize_proxy_environment() -> list[str]:
    """Drop bracketed IPv6 literals from every ``no_proxy`` case variant.

    Only ``no_proxy`` is touched: it is a comma separated host allowlist whose
    entries httpx parses as URL patterns. Other proxy variables are left alone.

    The value must be re-created rather than assigned. On Windows an assignment
    to an existing ``os.environ`` key does not reliably propagate the new value
    to child processes, so the key is removed and re-added.
    """
    removed: list[str] = []
    for key in [k for k in list(os.environ) if k.lower() == "no_proxy"]:
        parts = [p.strip() for p in os.environ.get(key, "").split(",")]
        dropped = [p for p in parts if p and BRACKETED_IPV6.match(p)]
        if not dropped:
            continue
        kept = ",".join(p for p in parts if p and not BRACKETED_IPV6.match(p))
        os.environ.pop(key, None)
        os.environ[key] = kept
        removed.append(f"{key}: dropped {dropped!r} -> {kept!r}")
    return removed


def main() -> int:
    removed = sanitize_proxy_environment()
    if removed:
        print("[reverify] sanitized proxy environment for httpx compatibility:")
        for line in removed:
            print(f"[reverify]   {line}")
    else:
        print("[reverify] no bracketed IPv6 no_proxy entry found; running as-is")

    # Fail fast with a clear message rather than letting 1300 tests run first.
    try:
        import httpx

        httpx.Client()
        print("[reverify] httpx.Client() constructs cleanly")
    except Exception as exc:  # noqa: BLE001 - diagnostic only
        print(f"[reverify] FATAL: httpx.Client() still fails: {type(exc).__name__}: {exc}")
        return 2

    # Scope the run to the backend suite. The repository root also contains a
    # stray test_review_api.py, and collecting both produces a duplicate-basename
    # collection error that has nothing to do with the suite under test.
    cmd = [sys.executable, "-m", "pytest", "-q", "tests", *sys.argv[1:]]
    print(f"[reverify] running: {' '.join(cmd)} (cwd={Path(__file__).resolve().parents[1] / 'backend'})")
    return subprocess.call(cmd, cwd=str(Path(__file__).resolve().parents[1] / "backend"))


if __name__ == "__main__":
    raise SystemExit(main())
