#!/usr/bin/env python3
"""Release version consistency gate for Chengzhu.

The desktop package is the distributable product, but the frontend and release
notes must describe the exact same semantic version.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    frontend = str(read_json(ROOT / "frontend" / "package.json").get("version") or "")
    desktop = str(read_json(ROOT / "desktop" / "package.json").get("version") or "")
    errors: list[str] = []

    if not frontend:
        errors.append("frontend/package.json version is empty")
    if not desktop:
        errors.append("desktop/package.json version is empty")
    if frontend != desktop:
        errors.append(f"frontend version {frontend!r} != desktop version {desktop!r}")

    notes = ROOT / "docs" / f"RELEASE_NOTES_v{desktop}.md"
    if desktop and not notes.is_file():
        errors.append(f"missing release notes: {notes.relative_to(ROOT)}")

    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({
        "ok": True,
        "version": desktop,
        "frontend": frontend,
        "desktop": desktop,
        "release_notes": str(notes.relative_to(ROOT)),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
