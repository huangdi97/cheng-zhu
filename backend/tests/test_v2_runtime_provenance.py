"""Product runtime provenance must bind pilot evidence to the shipped runtime."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from services import build_provenance
from services.product import conversations


ROOT = Path(__file__).resolve().parents[2]


def _load_runtime_fingerprint():
    path = ROOT / "scripts" / "runtime_fingerprint.py"
    spec = importlib.util.spec_from_file_location("runtime_fingerprint_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fixture_repo(tmp_path: Path) -> Path:
    files = {
        "backend/main.py": "print('runtime')\n",
        "backend/sidecar.py": 'APP_VERSION = "2.0.0-beta.10"\nprint("sidecar")\n',
        "backend/requirements.txt": "fastapi==1.0\n",
        "backend/services/x.py": "VALUE = 1\n",
        "backend/tests/ignored.py": "SHOULD_NOT_COUNT = 1\n",
        "frontend/src/main.ts": "export const value = 1\n",
        "frontend/package.json": json.dumps({"name": "x", "version": "2.0.0-beta.10", "dependencies": {"a": "1.0.0"}}),
        "frontend/package-lock.json": json.dumps({
            "name": "x",
            "version": "2.0.0-beta.10",
            "lockfileVersion": 3,
            "packages": {"": {"name": "x", "version": "2.0.0-beta.10", "dependencies": {"a": "1.0.0"}}},
        }),
        "desktop/main.js": "console.log('desktop')\n",
        "desktop/package.json": json.dumps({"name": "desktop", "version": "2.0.0-beta.10", "dependencies": {"e": "2"}}),
        "desktop/package-lock.json": json.dumps({
            "name": "desktop",
            "version": "2.0.0-beta.10",
            "lockfileVersion": 3,
            "packages": {"": {"name": "desktop", "version": "2.0.0-beta.10"}},
        }),
        "packaging/chengzhu-backend.spec": "SPEC = 1\n",
        "scripts/build_sidecar.py": "print('build')\n",
        "scripts/runtime_fingerprint.py": "# algorithm v1\n",
        "docs/ignored.md": "docs do not affect product runtime\n",
    }
    for relative, value in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
    return tmp_path


def _packaged(version: str = "2.0.0-beta.10", *, runtime_sha: str = "b" * 64) -> dict:
    return {
        "contract_version": "v2.0-R1-build-provenance-1",
        "app_version": version,
        "source_sha": "a" * 40,
        "release_channel": "PRERELEASE" if "-" in version else "STABLE",
        "runtime_fingerprint": {
            "contract_version": "v2.0-R1-runtime-fingerprint-1",
            "sha256": runtime_sha,
            "files": 42,
        },
        "runtime_origin": "PACKAGED_EMBEDDED",
        "claim_boundary": "SOURCE_BUILD_PROVENANCE_NOT_REAL_USER_OR_BEHAVIORAL_EQUIVALENCE_PROOF",
    }


def test_runtime_fingerprint_ignores_only_release_version_and_non_runtime_files(tmp_path):
    mod = _load_runtime_fingerprint()
    repo = _fixture_repo(tmp_path)
    first = mod.fingerprint(repo)

    for relative in ("frontend/package.json", "desktop/package.json"):
        path = repo / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        value["version"] = "2.0.0"
        path.write_text(json.dumps(value), encoding="utf-8")
    for relative in ("frontend/package-lock.json", "desktop/package-lock.json"):
        path = repo / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        value["version"] = "2.0.0"
        value["packages"][""]["version"] = "2.0.0"
        path.write_text(json.dumps(value), encoding="utf-8")
    (repo / "backend/sidecar.py").write_text(
        'APP_VERSION = "2.0.0"\nprint("sidecar")\n',
        encoding="utf-8",
    )
    (repo / "docs/ignored.md").write_text("completely different release docs\n", encoding="utf-8")
    (repo / "backend/tests/ignored.py").write_text("SHOULD_NOT_COUNT = 999\n", encoding="utf-8")

    second = mod.fingerprint(repo)
    assert second["sha256"] == first["sha256"]
    assert second["files"] == first["files"]

    (repo / "frontend/src/main.ts").write_text("export const value = 2\n", encoding="utf-8")
    changed = mod.fingerprint(repo)
    assert changed["sha256"] != first["sha256"]


def test_runtime_fingerprint_changes_when_algorithm_or_dependency_changes(tmp_path):
    mod = _load_runtime_fingerprint()
    repo = _fixture_repo(tmp_path)
    first = mod.fingerprint(repo)

    (repo / "scripts/runtime_fingerprint.py").write_text("# algorithm v2\n", encoding="utf-8")
    assert mod.fingerprint(repo)["sha256"] != first["sha256"]

    repo = _fixture_repo(tmp_path / "dependency")
    baseline = mod.fingerprint(repo)
    (repo / "backend/requirements.txt").write_text("fastapi==2.0\n", encoding="utf-8")
    assert mod.fingerprint(repo)["sha256"] != baseline["sha256"]


def test_packaged_build_provenance_reader_is_fail_closed(tmp_path, monkeypatch):
    path = tmp_path / "build-provenance.json"
    value = _packaged()
    path.write_text(json.dumps({
        key: val for key, val in value.items() if key not in {"runtime_origin"}
    }), encoding="utf-8")
    monkeypatch.setenv("CHENGZHU_BUILD_PROVENANCE_FILE", str(path))
    build_provenance.current_build_provenance.cache_clear()

    loaded = build_provenance.current_build_provenance()
    assert loaded["runtime_origin"] == "PACKAGED_EMBEDDED"
    assert loaded["source_sha"] == "a" * 40
    assert loaded["runtime_fingerprint"]["sha256"] == "b" * 64
    assert build_provenance.packaged_build_provenance() == loaded

    broken = json.loads(path.read_text(encoding="utf-8"))
    broken["runtime_fingerprint"]["sha256"] = "not-a-sha"
    path.write_text(json.dumps(broken), encoding="utf-8")
    build_provenance.current_build_provenance.cache_clear()
    with pytest.raises(ValueError, match="fingerprint sha256"):
        build_provenance.current_build_provenance()
    build_provenance.current_build_provenance.cache_clear()


def test_session_start_freezes_runtime_provenance_in_row_and_pack(product_env, monkeypatch):
    frozen = _packaged()
    monkeypatch.setattr(
        build_provenance,
        "current_build_provenance",
        lambda: json.loads(json.dumps(frozen)),
    )

    space = conversations.create_space("Runtime Baseline", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    started = conversations.start_session(session["id"])
    row = conversations.require_session(session["id"])

    assert row["runtime_provenance"] == frozen
    assert started["pack"]["payload"]["runtime_provenance"] == frozen
    assert conversations.session_context(session["id"])["runtime_provenance"] == frozen

    different = _packaged(runtime_sha="c" * 64)
    monkeypatch.setattr(
        build_provenance,
        "current_build_provenance",
        lambda: json.loads(json.dumps(different)),
    )
    restarted = conversations.start_session(session["id"])
    assert restarted["session"]["runtime_provenance"] == frozen
    assert restarted["pack"]["payload"]["runtime_provenance"] == frozen


def test_source_checkout_provenance_is_not_packaged_pilot_proof(monkeypatch):
    source_value = _packaged()
    source_value["runtime_origin"] = "SOURCE_CHECKOUT"
    monkeypatch.setattr(build_provenance, "current_build_provenance", lambda: source_value)
    with pytest.raises(ValueError, match="packaged embedded build"):
        build_provenance.packaged_build_provenance()
