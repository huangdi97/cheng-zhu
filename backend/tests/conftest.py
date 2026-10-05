"""Shared fixtures.

``product_env`` isolates every SQLite store the v1.3 product layer touches
(product / intelligence / prep / review / job_tracker) in a tmp dir and
keeps config writes off disk, so product tests never see or change the
developer's real data.
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture()
def product_env(tmp_path, monkeypatch):
    import core.config as config_module
    from services.storage import intelligence as intel_storage
    from services.storage import job_tracker, prep_space, product, review

    monkeypatch.setattr(product, "DB_PATH", str(tmp_path / "product.db"))
    monkeypatch.setattr(intel_storage, "DB_PATH", str(tmp_path / "intelligence.db"))
    monkeypatch.setattr(prep_space, "DB_PATH", str(tmp_path / "prep.db"))
    monkeypatch.setattr(review, "DB_PATH", str(tmp_path / "review.db"))
    monkeypatch.setattr(job_tracker, "DB_PATH", str(tmp_path / "job_tracker.db"))
    monkeypatch.setattr(config_module, "_save_config", lambda cfg: True)
    # in-memory config edits made by a test are rolled back at teardown
    monkeypatch.setattr(config_module, "_config", config_module._raw_config().model_copy(deep=True))
    monkeypatch.setattr(config_module, "_effective", None)
    monkeypatch.setattr("services.storage.paths.exports_dir", lambda: str(tmp_path))
    monkeypatch.setattr("services.product.data_export.exports_dir", lambda: str(tmp_path))
    intel_storage.init_db()
    prep_space.init_db()
    review.init_db()
    job_tracker.init_db()
    product.init_db()
    config_module.clear_session_overlay()
    yield tmp_path
    config_module.clear_session_overlay()
