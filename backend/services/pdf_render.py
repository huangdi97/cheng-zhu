"""PDF page -> PNG rendering (resume image-PDF parsing, KB L2 OCR / L3 Vision).

Backed by pypdfium2 (PDFium; BSD-3-Clause / Apache-2.0). Replaces PyMuPDF
(AGPL-3.0) so the MIT desktop build ships no copyleft PDF renderer. Text
extraction stays with pypdf; this module only rasterizes pages.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Iterator


class PdfRenderError(ValueError):
    """The PDF could not be opened or rendered (damaged, encrypted, empty)."""


def _open(path: str | Path):
    try:
        import pypdfium2 as pdfium
    except ImportError:
        raise PdfRenderError("解析图片版 PDF 需要 pypdfium2：pip install pypdfium2") from None
    try:
        return pdfium.PdfDocument(str(path))
    except pdfium.PdfiumError as exc:
        message = str(exc).lower()
        if "password" in message:
            raise PdfRenderError("PDF 已加密，暂不支持；请导出未加密的 PDF 后再上传") from exc
        raise PdfRenderError(f"PDF 无法打开：{exc}") from exc


def _png_bytes(page, scale: float) -> bytes:
    image = page.render(scale=scale).to_pil()
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def page_count(path: str | Path) -> int:
    doc = _open(path)
    try:
        return len(doc)
    finally:
        doc.close()


def iter_pages_png(path: str | Path, dpi: int = 150) -> Iterator[bytes]:
    """Yield every page as PNG bytes, in page order."""
    doc = _open(path)
    try:
        scale = max(0.25, float(dpi) / 72.0)
        for index in range(len(doc)):
            page = doc[index]
            try:
                yield _png_bytes(page, scale)
            finally:
                page.close()
    finally:
        doc.close()


def render_page_png(path: str | Path, page_idx: int, out_path: Path, zoom: float = 2.0) -> None:
    """Render one page (1-based) to ``out_path``. Raises PdfRenderError."""
    doc = _open(path)
    try:
        if page_idx < 1 or page_idx > len(doc):
            raise PdfRenderError(f"页码越界：{page_idx}/{len(doc)}")
        page = doc[page_idx - 1]
        try:
            data = _png_bytes(page, max(0.25, float(zoom)))
        finally:
            page.close()
    finally:
        doc.close()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
