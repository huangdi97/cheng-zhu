"""Stable v2 release source must remain the exact current green main."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


verify = _load("verify_stable_release_source_test", "scripts/verify_stable_release_source.py")


def test_stable_v2_requires_exact_current_green_main():
    sha = "a" * 40
    result = verify.verify_source(
        version="2.0.0",
        source_sha=sha,
        current_main_sha=sha,
        successful_main_ci_count=1,
    )
    assert result["required"] is True
    assert result["status"] == "VERIFIED_CURRENT_GREEN_MAIN"

    with pytest.raises(ValueError, match="stale/non-main"):
        verify.verify_source(
            version="2.0.0",
            source_sha=sha,
            current_main_sha="b" * 40,
            successful_main_ci_count=1,
        )

    with pytest.raises(ValueError, match="no successful main push CI"):
        verify.verify_source(
            version="2.0.0",
            source_sha=sha,
            current_main_sha=sha,
            successful_main_ci_count=0,
        )


def test_prerelease_and_legacy_stable_do_not_require_green_main_gate():
    source = "c" * 40
    prerelease = verify.verify_source(
        version="2.0.0-beta.10",
        source_sha=source,
        current_main_sha="",
        successful_main_ci_count=0,
    )
    assert prerelease["required"] is False
    assert prerelease["status"] == "NOT_REQUIRED_PRERELEASE"

    legacy = verify.verify_source(
        version="1.4.2",
        source_sha=source,
        current_main_sha="",
        successful_main_ci_count=0,
    )
    assert legacy["required"] is False
    assert legacy["status"] == "NOT_REQUIRED_LEGACY_STABLE"


def test_stable_source_verifier_rejects_malformed_sha():
    with pytest.raises(ValueError, match="full 40-character"):
        verify.verify_source(
            version="2.0.0",
            source_sha="abc",
            current_main_sha="abc",
            successful_main_ci_count=1,
        )


def test_release_workflow_checks_green_main_before_build_and_before_publish():
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    wrapper = (ROOT / "scripts" / "verify_stable_release_source.ps1").read_text(encoding="utf-8")

    assert release.count("scripts/verify_stable_release_source.ps1") >= 3
    assert "Stable green-main source wrapper regression" in release
    assert "Stable v2+ exact green-main source gate" in release
    assert "actions: read" in release
    assert "git/ref/heads/main" in wrapper
    assert "actions/workflows/ci.yml/runs" in wrapper
    assert "head_branch -eq \"main\"" in wrapper
    assert "event -eq \"push\"" in wrapper
    assert "conclusion -eq \"success\"" in wrapper
