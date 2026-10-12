from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "render_published_release_body.py"


def _load():
    spec = importlib.util.spec_from_file_location("chengzhu_render_release_body", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_published_release_body_prepends_authoritative_status_without_rewriting_notes() -> None:
    mod = _load()
    original = "# Chengzhu beta\n\nThis candidate = beta.6\n原始发布说明。\n"
    source_sha = "1" * 40
    rendered = mod.render(
        original,
        tag="v2.0.0-beta.6",
        source_sha=source_sha,
        channel="PRERELEASE",
        stable_latest="v1.4.2",
    )
    assert rendered.startswith(mod.BEGIN)
    assert "Published: **TRUE** · Channel: **PRERELEASE**" in rendered
    assert source_sha in rendered
    assert "Stable Latest remains: **v1.4.2**" in rendered
    assert "does **not** imply Stable v2, real-user validation, or PMF" in rendered
    assert original.rstrip() in rendered
    assert rendered.count(mod.BEGIN) == 1
    assert rendered.count(mod.END) == 1


def test_published_release_body_is_idempotent_and_preserves_underlying_notes() -> None:
    mod = _load()
    original = "# Notes\n\nCandidate wording remains historical.\n"
    first = mod.render(
        original,
        tag="v2.0.0-beta.6",
        source_sha="a" * 40,
        channel="PRERELEASE",
        stable_latest="v1.4.2",
    )
    second = mod.render(
        first,
        tag="v2.0.0-beta.6",
        source_sha="b" * 40,
        channel="PRERELEASE",
        stable_latest="v1.4.2",
    )
    assert second.count(mod.BEGIN) == 1
    assert second.count(mod.END) == 1
    assert ("b" * 40) in second.split(mod.END, 1)[0]
    assert ("a" * 40) not in second.split(mod.END, 1)[0]
    assert original.rstrip() in second


def test_prerelease_display_requires_stable_latest() -> None:
    mod = _load()
    with pytest.raises(ValueError, match="stable_latest"):
        mod.render(
            "# Notes\n",
            tag="v2.0.0-beta.7",
            source_sha="c" * 40,
            channel="PRERELEASE",
        )


def test_malformed_existing_status_fails_closed() -> None:
    mod = _load()
    with pytest.raises(ValueError, match="without end marker"):
        mod.render(
            mod.BEGIN + "\n# truncated",
            tag="v2.0.0-beta.7",
            source_sha="d" * 40,
            channel="PRERELEASE",
            stable_latest="v1.4.2",
        )
