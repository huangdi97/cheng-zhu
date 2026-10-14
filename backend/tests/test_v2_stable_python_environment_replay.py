"""Stable release must replay the packaged pilot Python environment safely."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"


def _load():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    path = SCRIPTS / "stable_python_environment_replay.py"
    spec = importlib.util.spec_from_file_location("stable_python_environment_replay_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _norm(name: str) -> str:
    import re
    return re.sub(r"[-_.]+", "-", name).lower()


def _artifact_provenance(distributions: list[str]) -> dict:
    artifacts = []
    for raw in distributions:
        if "==" not in raw:
            continue
        name, version = raw.split("==", 1)
        if not name or not version or any(token in version for token in (";", " ", ">", "<")):
            continue
        normalized = _norm(name)
        wheel_bytes = f"{normalized}-{version}-wheel".encode("utf-8")
        artifacts.append({
            "name": normalized,
            "version": version,
            "filename": f"{normalized}-{version}-py3-none-any.whl",
            "sha256": hashlib.sha256(wheel_bytes).hexdigest(),
        })
    artifacts.sort(key=lambda row: row["name"])
    material = {"artifacts": artifacts}
    raw = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "contract_version": "v2.0-R1-python-artifact-provenance-1",
        "artifacts": artifacts,
        "artifacts_count": len(artifacts),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "install_mode": "WHEEL_SHA256_PINNED",
    }


def _python_env(distributions: list[str] | None = None) -> dict:
    values = list(distributions or [
        "fastapi==0.999.0",
        "pip==25.2",
        "PyInstaller==6.22.3",
        "setuptools==65.5.0",
    ])
    material = {
        "python_version": "3.13.16",
        "implementation": "CPython",
        "architecture": "AMD64",
        "distributions": values,
    }
    raw = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "contract_version": "v2.0-R1-python-build-environment-1",
        **material,
        "distributions_count": len(values),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "artifact_provenance": _artifact_provenance(values),
    }


def _token(*, env: dict | None = None, source: str = "a" * 40, runtime: str = "b" * 64) -> str:
    resolved_env = env if env is not None else _python_env()
    artifact_sha = str((resolved_env.get("artifact_provenance") or {}).get("sha256") or "")
    value = {
        "contract_version": "v2.0-R1-stable-release-authorization-3",
        "decision": "GO",
        "eligible_for_stable_release_workflow": True,
        "candidate_source_sha": source,
        "candidate_version": "2.0.0",
        "pilot_runtime_fingerprint": {
            "contract_version": "v2.0-R1-runtime-fingerprint-1",
            "sha256": runtime,
            "files": 42,
        },
        "pilot_python_environment": resolved_env,
        "pilot_python_artifact_provenance_sha256": artifact_sha,
        "candidate_runtime_fingerprint": {
            "contract_version": "v2.0-R1-runtime-fingerprint-1",
            "sha256": runtime,
            "files": 42,
        },
        "runtime_baseline_match": True,
        "review_check_digest": "c" * 64,
        "checks": [],
        "claims": {},
        "boundary": "AUTHORIZATION_IS_NOT_PUBLICATION",
    }
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _current() -> dict[str, str]:
    return {
        "python_version": "3.13.16",
        "implementation": "CPython",
        "architecture": "AMD64",
    }


def test_prepare_replay_generates_hash_checked_wheel_requirements():
    mod = _load()
    env = _python_env()
    result = mod.prepare_replay(
        _token(env=env),
        source_sha="a" * 40,
        version="2.0.0",
        runtime_fingerprint_sha256="b" * 64,
        required_python_version="3.13.16",
        current_python=_current(),
    )
    assert result["contract_version"] == "v2.0-R1-stable-python-environment-replay-1"
    assert result["python_version"] == "3.13.16"
    hashes = {
        row["name"]: row["sha256"]
        for row in env["artifact_provenance"]["artifacts"]
    }
    assert result["bootstrap_requirements"] == [
        f"pip==25.2 --hash=sha256:{hashes['pip']}",
    ]
    assert result["runtime_requirements"] == [
        f"fastapi==0.999.0 --hash=sha256:{hashes['fastapi']}",
        f"pyinstaller==6.22.3 --hash=sha256:{hashes['pyinstaller']}",
        f"setuptools==65.5.0 --hash=sha256:{hashes['setuptools']}",
    ]
    assert result["pilot_python_artifact_provenance_sha256"] == env["artifact_provenance"]["sha256"]
    raw = (
        "\n".join(result["bootstrap_requirements"])
        + "\n--RUNTIME--\n"
        + "\n".join(result["runtime_requirements"])
        + "\n"
    ).encode("utf-8")
    assert result["hashed_requirements_sha256"] == hashlib.sha256(raw).hexdigest()


def test_prepare_replay_requires_artifact_provenance():
    mod = _load()
    env = _python_env()
    env.pop("artifact_provenance")
    with pytest.raises(ValueError, match="artifact provenance"):
        mod.prepare_replay(
            _token(env=env),
            source_sha="a" * 40,
            version="2.0.0",
            runtime_fingerprint_sha256="b" * 64,
            required_python_version="3.13.16",
            current_python=_current(),
        )


def test_prepare_replay_rejects_non_wheel_artifact():
    mod = _load()
    env = _python_env()
    env["artifact_provenance"]["artifacts"][0]["filename"] = "fastapi-0.999.0.tar.gz"
    with pytest.raises(ValueError, match="wheel artifact"):
        mod.prepare_replay(
            _token(env=env),
            source_sha="a" * 40,
            version="2.0.0",
            runtime_fingerprint_sha256="b" * 64,
            required_python_version="3.13.16",
            current_python=_current(),
        )


def test_prepare_replay_rejects_artifact_provenance_sha_drift():
    mod = _load()
    env = _python_env()
    env["artifact_provenance"]["sha256"] = "9" * 64
    with pytest.raises(ValueError, match="artifact provenance SHA256 mismatch"):
        mod.prepare_replay(
            _token(env=env),
            source_sha="a" * 40,
            version="2.0.0",
            runtime_fingerprint_sha256="b" * 64,
            required_python_version="3.13.16",
            current_python=_current(),
        )


@pytest.mark.parametrize("unsafe", [
    "evil @ https://example.invalid/evil.whl",
    "evil==1.0; python_version>'3.10'",
    "-e git+https://example.invalid/repo.git",
    "evil>=1.0",
    "evil",
])
def test_prepare_replay_rejects_non_exact_or_remote_distribution_specs(unsafe):
    mod = _load()
    with pytest.raises(ValueError, match="exact name==version"):
        mod.prepare_replay(
            _token(env=_python_env(["pip==25.2", unsafe])),
            source_sha="a" * 40,
            version="2.0.0",
            runtime_fingerprint_sha256="b" * 64,
            required_python_version="3.13.16",
            current_python=_current(),
        )


def test_prepare_replay_rejects_conflicting_normalized_distribution_names():
    mod = _load()
    with pytest.raises(ValueError, match="conflicting duplicate"):
        mod.prepare_replay(
            _token(env=_python_env(["Example_Pkg==1.0", "example-pkg==2.0"])),
            source_sha="a" * 40,
            version="2.0.0",
            runtime_fingerprint_sha256="b" * 64,
            required_python_version="3.13.16",
            current_python=_current(),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source", "c" * 40, "source SHA"),
        ("runtime", "d" * 64, "runtime"),
        ("required_python_version", "3.13.15", "repository-pinned"),
    ],
)
def test_prepare_replay_is_bound_to_candidate_and_pinned_python(field, value, message):
    mod = _load()
    kwargs = {
        "authorization_b64": _token(),
        "source_sha": "a" * 40,
        "version": "2.0.0",
        "runtime_fingerprint_sha256": "b" * 64,
        "required_python_version": "3.13.16",
        "current_python": _current(),
    }
    if field == "source":
        kwargs["source_sha"] = value
    elif field == "runtime":
        kwargs["runtime_fingerprint_sha256"] = value
    else:
        kwargs["required_python_version"] = value
    with pytest.raises(ValueError, match=message):
        mod.prepare_replay(**kwargs)


def test_prepare_replay_rejects_current_interpreter_drift():
    mod = _load()
    with pytest.raises(ValueError, match="python_version differs"):
        mod.prepare_replay(
            _token(),
            source_sha="a" * 40,
            version="2.0.0",
            runtime_fingerprint_sha256="b" * 64,
            required_python_version="3.13.16",
            current_python={**_current(), "python_version": "3.13.17"},
        )


def test_sidecar_python_patch_pin_is_a_runtime_fingerprint_input(tmp_path):
    runtime = _load_runtime_fingerprint_for_pin_test()
    repo = _minimal_runtime_repo(tmp_path)
    first = runtime.fingerprint(repo)
    version_file = repo / "packaging" / "sidecar-python-version.txt"
    version_file.write_text("3.13.17\n", encoding="utf-8")
    second = runtime.fingerprint(repo)
    assert second["sha256"] != first["sha256"]


def _load_runtime_fingerprint_for_pin_test():
    path = SCRIPTS / "runtime_fingerprint.py"
    spec = importlib.util.spec_from_file_location("runtime_fingerprint_pin_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _minimal_runtime_repo(root: Path) -> Path:
    files = {
        "backend/main.py": "print('runtime')\n",
        "backend/sidecar.py": 'APP_VERSION = "2.0.0-beta.10"\n',
        "backend/requirements.txt": "fastapi==1.0\n",
        "backend/services/x.py": "VALUE = 1\n",
        "frontend/src/main.ts": "export const x = 1\n",
        "frontend/index.html": "<div></div>\n",
        "frontend/vite.config.ts": "export default {}\n",
        "frontend/tsconfig.json": "{}\n",
        "frontend/tailwind.config.js": "export default {}\n",
        "frontend/postcss.config.js": "export default {}\n",
        "frontend/package.json": '{"name":"x","version":"2.0.0-beta.10"}\n',
        "frontend/package-lock.json": '{"name":"x","version":"2.0.0-beta.10","lockfileVersion":3,"packages":{"":{"version":"2.0.0-beta.10"}}}\n',
        "desktop/main.js": "console.log('x')\n",
        "desktop/package.json": '{"name":"d","version":"2.0.0-beta.10"}\n',
        "desktop/package-lock.json": '{"name":"d","version":"2.0.0-beta.10","lockfileVersion":3,"packages":{"":{"version":"2.0.0-beta.10"}}}\n',
        "packaging/chengzhu-backend.spec": "SPEC=1\n",
        "packaging/sidecar-python-version.txt": "3.13.16\n",
        "scripts/build_sidecar.py": "print('build')\n",
        "scripts/runtime_fingerprint.py": "# fingerprint\n",
    }
    for relative, body in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def _load_build_sidecar():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    path = SCRIPTS / "build_sidecar.py"
    spec = importlib.util.spec_from_file_location("build_sidecar_replay_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_sidecar_reads_exact_python_pin_and_stable_requirement_paths(tmp_path, monkeypatch):
    mod = _load_build_sidecar()
    version_file = tmp_path / "sidecar-python-version.txt"
    version_file.write_text("3.13.16\n", encoding="utf-8")
    monkeypatch.setattr(mod, "PYTHON_VERSION_FILE", version_file)
    assert mod.required_python_version() == "3.13.16"

    requirements = tmp_path / "stable-hashes.txt"
    requirements.write_text(
        "fastapi==0.999.0 --hash=sha256:" + ("a" * 64) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CHENGZHU_STABLE_PYTHON_RUNTIME_REQUIREMENTS", str(requirements))
    assert mod._existing_file_from_env("CHENGZHU_STABLE_PYTHON_RUNTIME_REQUIREMENTS") == requirements.resolve()
    monkeypatch.delenv("CHENGZHU_STABLE_PYTHON_RUNTIME_REQUIREMENTS")
    assert mod._existing_file_from_env("CHENGZHU_STABLE_PYTHON_RUNTIME_REQUIREMENTS") is None

    monkeypatch.setenv("CHENGZHU_STABLE_PYTHON_RUNTIME_REQUIREMENTS", str(tmp_path / "missing.txt"))
    with pytest.raises(RuntimeError, match="does not exist"):
        mod._existing_file_from_env("CHENGZHU_STABLE_PYTHON_RUNTIME_REQUIREMENTS")


def test_build_sidecar_rejects_non_exact_python_pin(tmp_path, monkeypatch):
    mod = _load_build_sidecar()
    version_file = tmp_path / "sidecar-python-version.txt"
    version_file.write_text("3.13\n", encoding="utf-8")
    monkeypatch.setattr(mod, "PYTHON_VERSION_FILE", version_file)
    with pytest.raises(RuntimeError, match="major.minor.patch"):
        mod.required_python_version()
