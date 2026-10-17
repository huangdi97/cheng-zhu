"""The local migration matrix must always cover the shipped product schema."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _load_matrix():
    path = ROOT / "scripts" / "v2_local_migration_matrix.py"
    spec = importlib.util.spec_from_file_location("v2_local_migration_matrix_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_case_versions_derive_from_names_and_reject_unknown_versions():
    matrix = _load_matrix()

    assert matrix._case_version("fresh") == 0
    assert matrix._case_version(f"v{matrix.LATEST_SCHEMA_VERSION}") == matrix.LATEST_SCHEMA_VERSION

    with pytest.raises(ValueError, match="newer than the shipped schema"):
        matrix._case_version(f"v{matrix.LATEST_SCHEMA_VERSION + 1}")
    with pytest.raises(ValueError, match="unsupported migration-matrix case"):
        matrix._case_version("not-a-version")


def test_matrix_covers_latest_schema_and_every_case_passes(tmp_path):
    matrix = _load_matrix()
    latest = matrix.LATEST_SCHEMA_VERSION

    assert f"v{latest}" in matrix.CASES, (
        "the migration matrix must add a case for every newly shipped schema "
        f"version; latest is v{latest}"
    )

    results = [matrix.run_case(case, tmp_path) for case in matrix.CASES]
    failed = [row for row in results if not row["passed"]]
    assert failed == [], failed
    assert results[-1]["version_after"] == latest
