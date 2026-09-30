# PyMuPDF license decision

**Status: REPLACED**

Date: 2026-09-30

## Decision

PyMuPDF (AGPL-3.0 / Artifex commercial) is removed from Chengzhu. PDF page rendering now uses
**pypdfium2** (Python binding: BSD-3-Clause / Apache-2.0; PDFium: BSD-3-Clause; bundled build
dependencies FreeType, ICU, libjpeg-turbo, libpng, libtiff, OpenJPEG, lcms, zlib, abseil,
fast_float, simdutf, llvm-libc, agg — all permissive; their texts ship inside the wheel's
`dist-info/licenses`, which PyInstaller keeps in the sidecar).

The shipped Windows build therefore contains **no copyleft component**. No commercial license is required.

## Change

| Before | After |
|---|---|
| `fitz.open(...).get_pixmap(dpi=150)` in `services/resume.py` | `services/pdf_render.iter_pages_png(path, dpi=150)` |
| `fitz` page render in `services/kb/loaders/_vision.py` | `services/pdf_render.render_page_png(path, page, out, zoom)` |
| `_dep_ok("fitz")` | `_dep_ok("pypdfium2")` |
| `pymupdf>=1.24,<2` | `pypdfium2>=4.30,<6` |
| spec hidden imports `fitz`, `pymupdf` | `pypdfium2`, `pypdfium2_raw` |

Text extraction (pypdf), page numbers and KB source provenance are unchanged.
New behaviour: encrypted PDFs (user password) now fail with a clear "PDF 已加密，暂不支持"
message in both the resume and KB paths instead of an opaque error.

## Verification

- `backend/tests/test_pdf_regression_corpus.py` — corpus in `backend/tests/fixtures/pdf/`
  (normal, multi-page, Chinese, English, mixed, table, empty page, scanned, damaged, encrypted):
  text extraction per page, page numbers, source path, Unicode, render every page to PNG,
  zoom scaling, typed failure for damaged/encrypted, resume → vision page-by-page.
- Existing KB loader / API tests pass unchanged.
- `python scripts/generate_third_party_notices.py --check` now **fails** on any shipped dependency
  outside the permissive allow-list (it previously only listed them), so an AGPL dependency cannot
  return silently.
- `test_license_smoke.test_no_agpl_pdf_renderer_shipped` asserts no `pymupdf` in requirements,
  spec or the shipped Python table.

## Distribution obligations after the change

MIT for Chengzhu; keep `LICENSE` and `THIRD_PARTY_NOTICES.md` with the binary (both are bundled
in the installer and attached to the GitHub Release). No source-offer obligation remains.
