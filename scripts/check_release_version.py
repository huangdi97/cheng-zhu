#!/usr/bin/env python3
"""Release version consistency gate for Chengzhu.

The distributable Windows product spans four versioned surfaces:
frontend metadata, desktop metadata, package locks, and the packaged Python
sidecar. A release is not version-consistent unless all of them agree.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sidecar_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']\s*$', text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def main() -> int:
    frontend = str(read_json(ROOT / "frontend" / "package.json").get("version") or "")
    desktop = str(read_json(ROOT / "desktop" / "package.json").get("version") or "")
    frontend_lock = str(read_json(ROOT / "frontend" / "package-lock.json").get("version") or "")
    desktop_lock = str(read_json(ROOT / "desktop" / "package-lock.json").get("version") or "")
    backend = sidecar_version(ROOT / "backend" / "sidecar.py")
    errors: list[str] = []

    versions = {
        "frontend": frontend,
        "desktop": desktop,
        "frontend_lock": frontend_lock,
        "desktop_lock": desktop_lock,
        "backend_sidecar": backend,
    }

    for name, version in versions.items():
        if not version:
            errors.append(f"{name} version is empty")

    expected = desktop
    semver = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")
    if expected and not semver.fullmatch(expected):
        errors.append(f"desktop version {expected!r} is not a supported SemVer release version")
    is_prerelease = bool(expected and "-" in expected)

    for name, version in versions.items():
        if expected and version and version != expected:
            errors.append(f"{name} version {version!r} != desktop version {expected!r}")

    notes = ROOT / "docs" / f"RELEASE_NOTES_v{expected}.md"
    if expected and not notes.is_file():
        errors.append(f"missing release notes: {notes.relative_to(ROOT)}")

    # A valid release must be reproducible from one exact commit: the SHA that
    # passed main CI is the SHA checked out for packaging and the SHA targeted
    # by the public tag. This gate prevents a moving-main race from creating a
    # tag for newer source than the installer/portable binaries actually used.
    release_workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    publisher_workflow = (
        ROOT / ".github" / "workflows" / "publish-current-version-on-green-main.yml"
    ).read_text(encoding="utf-8")
    for token in (
        "source_sha:",
        "CHENGZHU_RELEASE_SOURCE_SHA",
        "--target $sourceSha",
        "tag $tag points to $tagSha but binaries were built from $sourceSha",
        "$version.Contains('-')",
        "--prerelease",
        "--latest=false",
        "release channel mismatch",
        "prerelease $tag incorrectly replaced the stable Latest release",
    ):
        if token not in release_workflow:
            errors.append(f"release workflow missing provenance invariant: {token}")
    for token in (
        "github.event.workflow_run.head_sha",
        'gh workflow run release.yml --ref main -f publish=true -f source_sha="$SOURCE_SHA"',
        "RELEASE_NOTES_v$version.md",
    ):
        if token not in publisher_workflow:
            errors.append(f"current-version publisher missing exact-SHA invariant: {token}")

    if errors:
        print(json.dumps({"ok": False, "versions": versions, "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({
        "ok": True,
        "version": expected,
        "release_channel": "PRERELEASE" if is_prerelease else "STABLE",
        "versions": versions,
        "release_notes": str(notes.relative_to(ROOT)),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
