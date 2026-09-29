"""G-LICENSE smoke: the repository ships under MIT and nothing still claims CC BY-NC."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_root_license_is_mit():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("MIT License")
    assert "Copyright (c) 2026 huangdi97" in text
    assert "NonCommercial" not in text


def test_readme_and_packages_declare_mit():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "license-MIT" in readme
    assert "CC BY-NC" not in readme and "CC%20BY--NC" not in readme
    for pkg in ("frontend/package.json", "desktop/package.json"):
        assert '"license": "MIT"' in (ROOT / pkg).read_text(encoding="utf-8"), pkg


def test_third_party_notices_present():
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "not** relicensed" in notices
    assert "PyMuPDF" in notices
