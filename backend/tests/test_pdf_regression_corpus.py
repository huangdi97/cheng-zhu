"""PDF regression corpus (v1.2-R2 Stage K).

Covers text extraction (pypdf, KB loader), page numbers, source provenance
and failure modes, plus page rendering (pypdfium2, replaces AGPL PyMuPDF)
for resume image-PDF parsing and KB OCR/Vision.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services import pdf_render  # noqa: E402
from services.kb.loaders import dispatch_loader  # noqa: E402

CORPUS = BACKEND_DIR / "tests" / "fixtures" / "pdf"
MANIFEST = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
READABLE = [name for name, spec in MANIFEST.items() if "pages" in spec]
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture(autouse=True)
def _no_ocr_or_vision(monkeypatch):
    from services.kb.loaders import pdf as pdf_loader

    monkeypatch.setattr(pdf_loader, "_l2_ocr_enabled", lambda: False)
    monkeypatch.setattr(pdf_loader, "_l3_vision_enabled", lambda: False)


def _load(name: str):
    path = CORPUS / name
    loader = dispatch_loader(path)
    assert loader is not None
    return loader.load(path, rel_path=f"kb/{name}")


@pytest.mark.parametrize("name", READABLE)
def test_text_extraction_page_numbers_and_provenance(name):
    spec = MANIFEST[name]
    doc = _load(name)
    assert doc.loader == "pdf"
    assert doc.path == f"kb/{name}"  # source provenance: the KB-relative file
    by_page = {s.page: s for s in doc.sections}
    for page, needles in spec["expect"].items():
        section = by_page[int(page)]
        assert section.origin == "text"
        assert section.section_path.endswith(f"Page {page}")
        for needle in needles:
            assert needle in section.text, (name, page, needle, section.text)
    for page in spec.get("empty_pages", []):
        assert page not in by_page, "an empty / scanned page must not produce a text section"


def test_chinese_text_is_unicode_not_mojibake():
    text = "\n".join(s.text for s in _load("chinese.pdf").sections)
    assert "后端开发工程师" in text
    assert "�" not in text


def test_damaged_pdf_fails_loudly():
    with pytest.raises(Exception):
        _load("damaged.pdf")


def test_encrypted_pdf_is_reported_unsupported():
    with pytest.raises(ValueError, match="加密"):
        _load("encrypted.pdf")


@pytest.mark.parametrize("name", READABLE)
def test_render_every_page_to_png(name):
    spec = MANIFEST[name]
    assert pdf_render.page_count(CORPUS / name) == spec["pages"]
    pages = list(pdf_render.iter_pages_png(CORPUS / name, dpi=72))
    assert len(pages) == spec["pages"]
    assert all(png.startswith(PNG_MAGIC) for png in pages)


def test_render_single_page_for_kb_ocr(tmp_path):
    from services.kb.loaders._vision import render_pdf_page_to_png

    out = tmp_path / "p2.png"
    assert render_pdf_page_to_png(CORPUS / "multipage.pdf", 2, out)
    assert out.read_bytes().startswith(PNG_MAGIC)
    assert not render_pdf_page_to_png(CORPUS / "multipage.pdf", 9, tmp_path / "x.png")
    assert not render_pdf_page_to_png(CORPUS / "damaged.pdf", 1, tmp_path / "y.png")


def test_render_zoom_scales_output(tmp_path):
    from PIL import Image

    small, large = tmp_path / "s.png", tmp_path / "l.png"
    pdf_render.render_page_png(CORPUS / "normal.pdf", 1, small, zoom=1.0)
    pdf_render.render_page_png(CORPUS / "normal.pdf", 1, large, zoom=2.0)
    assert Image.open(large).width == pytest.approx(Image.open(small).width * 2, abs=2)


@pytest.mark.parametrize("name", ["damaged.pdf", "encrypted.pdf"])
def test_render_failure_modes_raise_typed_error(name):
    with pytest.raises(pdf_render.PdfRenderError):
        list(pdf_render.iter_pages_png(CORPUS / name))


def test_resume_pdf_goes_page_by_page_to_vision(monkeypatch):
    import services.llm as llm
    from services import resume

    seen: dict = {}
    monkeypatch.setattr(llm, "has_vision_model", lambda: True)
    monkeypatch.setattr(llm, "vision_extract_text", lambda images: seen.setdefault("images", images) and "ok")
    assert resume.parse_pdf(str(CORPUS / "multipage.pdf")) == "ok"
    assert len(seen["images"]) == 3
    assert base64.b64decode(seen["images"][0]).startswith(PNG_MAGIC)


def test_scanned_resume_pdf_still_renders_for_vision(monkeypatch):
    import services.llm as llm
    from services import resume

    monkeypatch.setattr(llm, "has_vision_model", lambda: True)
    monkeypatch.setattr(llm, "vision_extract_text", lambda images: f"{len(images)} page")
    assert resume.parse_pdf(str(CORPUS / "scanned.pdf")) == "1 page"


def test_encrypted_resume_pdf_gives_user_facing_error(monkeypatch):
    import services.llm as llm
    from services import resume

    monkeypatch.setattr(llm, "has_vision_model", lambda: True)
    with pytest.raises(ValueError, match="加密"):
        resume.parse_pdf(str(CORPUS / "encrypted.pdf"))
