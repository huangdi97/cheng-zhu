#!/usr/bin/env python3
"""Verify that a Stable v2+ release source is the exact current green main.

Human Stable review authorization is necessary but not sufficient. Stable
publication must also come from the current main tip and from a successful
main push CI run for that exact SHA. This helper is intentionally pure: the
workflow obtains GitHub facts, then passes them here for deterministic checks.
"""
from __future__ import annotations

import argparse
import json
import re


SEMVER = re.compile(r"^(?P<major>[0-9]+)\.(?P<minor>[0-9]+)\.(?P<patch>[0-9]+)(?P<suffix>-[0-9A-Za-z.-]+)?$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def verify_source(
    *,
    version: str,
    source_sha: str,
    current_main_sha: str,
    successful_main_ci_count: int,
) -> dict[str, object]:
    version = str(version or "").strip()
    source_sha = str(source_sha or "").strip().lower()
    current_main_sha = str(current_main_sha or "").strip().lower()
    match = SEMVER.fullmatch(version)
    if not match:
        raise ValueError("unsupported release version")

    major = int(match.group("major"))
    is_prerelease = bool(match.group("suffix"))
    if is_prerelease:
        return {
            "required": False,
            "status": "NOT_REQUIRED_PRERELEASE",
            "version": version,
            "source_sha": source_sha,
        }
    if major < 2:
        return {
            "required": False,
            "status": "NOT_REQUIRED_LEGACY_STABLE",
            "version": version,
            "source_sha": source_sha,
        }

    if not SHA40.fullmatch(source_sha):
        raise ValueError("Stable v2+ source SHA must be a full 40-character lowercase git SHA")
    if not SHA40.fullmatch(current_main_sha):
        raise ValueError("current main SHA must be a full 40-character lowercase git SHA")
    if source_sha != current_main_sha:
        raise ValueError(
            f"Stable v2+ source is stale/non-main: source={source_sha} current_main={current_main_sha}"
        )
    if int(successful_main_ci_count) < 1:
        raise ValueError("Stable v2+ source has no successful main push CI run")

    return {
        "required": True,
        "status": "VERIFIED_CURRENT_GREEN_MAIN",
        "version": version,
        "source_sha": source_sha,
        "current_main_sha": current_main_sha,
        "successful_main_ci_count": int(successful_main_ci_count),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--current-main-sha", required=True)
    parser.add_argument("--successful-main-ci-count", type=int, required=True)
    args = parser.parse_args()
    try:
        result = verify_source(
            version=args.version,
            source_sha=args.source_sha,
            current_main_sha=args.current_main_sha,
            successful_main_ci_count=args.successful_main_ci_count,
        )
    except ValueError as exc:
        parser.error(str(exc))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
