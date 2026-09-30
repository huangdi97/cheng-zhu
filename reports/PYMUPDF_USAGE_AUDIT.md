# PyMuPDF usage audit (v1.2-R2 Stage I)

Date: 2026-09-30 · Base: `f04f217` · Commands: `git grep -n "fitz"`, `git grep -n -i "pymupdf"`

## Where PyMuPDF (`fitz`) was used

| File | Function | API used | Purpose |
|---|---|---|---|
| `backend/services/resume.py` | `_pdf_to_images_base64` | `fitz.open`, `page.get_pixmap(dpi=150)`, `pix.tobytes("png")` | Rasterize every page of a resume PDF → PNG base64 → vision model (`parse_pdf`) |
| `backend/services/kb/loaders/_vision.py` | `render_pdf_page_to_png` | `fitz.open`, `load_page`, `Matrix(zoom)`, `get_pixmap`, `pix.save` | Rasterize one KB PDF page for L2 OCR (RapidOCR, optional) and L3 Vision caption (optional, off by default) |
| `backend/api/kb/routes.py` | `kb_status` | `_dep_ok("fitz")` | Report whether Vision captioning is available |
| `packaging/chengzhu-backend.spec` | hidden imports | `fitz`, `pymupdf` | Bundle into the sidecar |
| `start.py` | dependency probe | `pymupdf → fitz` | Dev launcher check |
| `backend/requirements.txt` | — | `pymupdf>=1.24,<2` | Runtime dependency |

## What it was *not* used for

| Concern | Finding |
|---|---|
| PDF text extraction | Not PyMuPDF — the KB loader uses **pypdf** (`PdfReader.extract_text`) with page numbers. Resume PDFs are parsed by a vision model from rendered pages. |
| Page count / metadata | pypdf (`reader.pages`, `reader.metadata.title`) |
| OCR | RapidOCR (optional) on a rendered PNG; PyMuPDF only produced the PNG |
| Annotations / editing / search | none |
| Tests | only `test_start_dependencies` (import map) and `test_license_smoke` (notice text); no functional PDF rendering test existed |
| Performance dependency | none on the live path; rendering only runs at resume upload / KB indexing |

## Conclusion

PyMuPDF was used **only for page rasterization** (PDF page → PNG). That is replaceable with a permissive renderer without touching text extraction or provenance. See `PYMUPDF_LICENSE_DECISION.md`.
