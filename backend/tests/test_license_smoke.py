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
    assert "`pypdfium2`" in notices


def test_no_agpl_pdf_renderer_shipped():
    """PyMuPDF (AGPL-3.0) was replaced by pypdfium2 before the MIT release."""
    requirements = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "pymupdf" not in requirements.replace("替代 agpl 的 pymupdf", "")
    spec = (ROOT / "packaging" / "chengzhu-backend.spec").read_text(encoding="utf-8")
    assert '"fitz"' not in spec and '"pymupdf"' not in spec
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    backend_table = notices.split("## Backend")[1].split("## Copyleft")[0]
    assert "AGPL" not in backend_table and "pymupdf" not in backend_table.lower()


def _notices_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("third_party_notices", ROOT / "scripts" / "generate_third_party_notices.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_license_gate_unverified_vs_known_copyleft(monkeypatch, tmp_path):
    """Uninstalled wheels (Linux CI) are unverified, not failures; a known
    copyleft package fails the gate even when it is not installed."""
    notices = _notices_module()
    req = tmp_path / "backend" / "requirements.txt"
    req.parent.mkdir(parents=True)
    req.write_text("fastapi>=0.1\nsome-windows-only-wheel>=1\n", encoding="utf-8")
    monkeypatch.setattr(notices, "ROOT", tmp_path)
    _text, flagged, unverified = notices.render()
    assert flagged == [] and unverified == ["some-windows-only-wheel"]
    req.write_text("fastapi>=0.1\npymupdf>=1.24\n", encoding="utf-8")
    _text, flagged, _unverified = notices.render()
    assert flagged and "pymupdf" in flagged[0] and "AGPL" in flagged[0]
