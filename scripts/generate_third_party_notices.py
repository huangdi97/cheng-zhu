"""Generate THIRD_PARTY_NOTICES.md from the real dependency manifests.

Sources:
  - frontend/package-lock.json, desktop/package-lock.json (npm, prod + dev flagged)
  - backend/requirements.txt resolved against the installed environment
    (importlib.metadata) for Python licenses

Run:  python scripts/generate_third_party_notices.py [--check]

--check exits non-zero if the committed file is out of date or if a
dependency declares a license outside the allow-list below (the release
gate uses this so a copyleft/non-commercial dependency never ships silently).
"""
from __future__ import annotations

import json
import re
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "THIRD_PARTY_NOTICES.md"

# Licenses compatible with shipping inside an MIT-licensed desktop binary.
# LGPL is allowed only for dynamically linked Python/native libs (recorded,
# not blocked); anything else unknown is flagged for manual review.
PERMISSIVE = re.compile(
    r"^(MIT|MIT-0|ISC|BSD|BSD-2-Clause|BSD-3-Clause|0BSD|Apache-2\.0|Apache|Apache Software License|"
    r"Python-2\.0|PSF|PSF-2\.0|Python Software Foundation License|Unlicense|CC0-1\.0|BlueOak-1\.0\.0|"
    r"Zlib|CMU|MIT-CMU|MPL-2\.0|CC-BY-4\.0|WTFPL|Artistic-2\.0|HPND|LGPL.*)$",
    re.IGNORECASE,
)


# Copyleft / non-commercial Python packages that must never ship in the MIT
# desktop build, checked by name so the gate holds even where the package is
# not installed (the Linux CI runner lacks some Windows-only wheels).
KNOWN_COPYLEFT_PYTHON = {
    "pymupdf": "AGPL-3.0",
    "fitz": "AGPL-3.0",
    "pyqt5": "GPL-3.0",
    "pyqt6": "GPL-3.0",
    "ghostscript": "AGPL-3.0",
    "mysql-connector-python": "GPL-2.0",
}


# Packages whose lockfile entry has no license field (legacy `licenses: [...]`
# in their package.json). Pinned here so the output does not depend on
# node_modules being installed (CI's backend job has none).
KNOWN_LEGACY_LICENSES = {
    "format": "MIT",
}


def _installed_npm_license(pkg_root: Path, name: str) -> str:
    """Old packages declare `licenses: [{type}]`, which the lockfile drops."""
    if name in KNOWN_LEGACY_LICENSES:
        return KNOWN_LEGACY_LICENSES[name]
    manifest = pkg_root / "node_modules" / name / "package.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "UNKNOWN"
    legacy = data.get("licenses") or []
    types = [str(item.get("type", "")) for item in legacy if isinstance(item, dict)]
    return " OR ".join(t for t in types if t) or str(data.get("license") or "UNKNOWN")


def _npm_rows(lock_path: Path) -> list[tuple[str, str, str, bool]]:
    if not lock_path.is_file():
        return []
    data = json.loads(lock_path.read_text(encoding="utf-8"))
    rows = []
    for key, info in (data.get("packages") or {}).items():
        if not key.startswith("node_modules/"):
            continue
        name = key.split("node_modules/")[-1]
        license_value = info.get("license") or _installed_npm_license(lock_path.parent, name)
        if isinstance(license_value, dict):
            license_value = license_value.get("type", "UNKNOWN")
        rows.append((name, str(info.get("version", "")), str(license_value), bool(info.get("dev"))))
    return sorted(set(rows))


def _python_rows(req_path: Path) -> list[tuple[str, str, str]]:
    rows = []
    for raw in req_path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name = re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0]
        try:
            meta = metadata.metadata(name)
            version = metadata.version(name)
            lic = (meta.get("License-Expression") or "").strip()
            if not lic or len(lic) > 60:
                classifiers = [c for c in (meta.get_all("Classifier") or []) if c.startswith("License ::")]
                lic = classifiers[-1].split("::")[-1].strip() if classifiers else (meta.get("License") or "UNKNOWN").strip()
            if len(lic) > 60:
                lic = lic.splitlines()[0][:60]
        except metadata.PackageNotFoundError:
            version, lic = "(not installed)", "UNKNOWN"
        rows.append((name, version, lic or "UNKNOWN"))
    return rows


def _normalize(lic: str) -> str:
    lic = lic.strip().strip("()")
    lic = lic.replace("Apache Software License", "Apache-2.0").replace("MIT-CMU", "MIT")
    lic = lic.replace(" License", "").replace("The ", "")
    return lic


def _is_permissive(lic: str) -> bool:
    parts = re.split(r"\s+(?:OR|AND)\s+|/|\(|,", _normalize(lic))
    return any(PERMISSIVE.match(part.strip().strip("()")) for part in parts)


def render() -> tuple[str, list[str], list[str]]:
    flagged: list[str] = []
    unverified: list[str] = []
    out = [
        "# Third-Party Notices",
        "",
        "成竹 Chengzhu itself is licensed under the [MIT License](LICENSE).",
        "The components below are **not** relicensed by Chengzhu; each keeps its own license.",
        "This file is generated by `scripts/generate_third_party_notices.py` — do not edit by hand.",
        "",
        "## Provenance note",
        "",
        "Earlier releases (up to v1.1, Git history before the v1.2 MIT change) were published under CC BY-NC 4.0.",
        "Early base code descends from the maintainer's own earlier `interview-assistant` code line; the maintainer",
        "confirmed on 2026-09-30 that it was also written by `huangdi97` and that no third-party-owned code remains",
        "(`reports/LEGACY_CODE_PROVENANCE_AUDIT.md`). All commits are authored by `huangdi97`, who relicensed the tree to MIT in v1.2.",
        "If you are the author of upstream code and believe it is included here under different terms, please open an issue.",
        "",
        "## Bundled assets",
        "",
        "| Asset | Origin | License |",
        "|---|---|---|",
        "| `frontend/public/icon.png`, `desktop/icon.png` | Chengzhu project artwork | MIT (project) |",
        "| `frontend/public/avatars/generated/*` | Generated for this project | MIT (project) |",
        "| `docs/screenshots/*` | Screenshots of Chengzhu itself | MIT (project) |",
        "| `backend/assets/preflight_phrase.wav` | Synthesized test phrase for preflight | MIT (project) |",
        "",
        "## Models (downloaded at runtime, not bundled)",
        "",
        "| Model | License | Note |",
        "|---|---|---|",
        "| faster-whisper / CTranslate2 Whisper weights (optional local STT) | MIT (OpenAI Whisper weights) | Downloaded on first use from Hugging Face; not shipped in the installer. |",
        "| Remote LLM / STT providers (BYOK) | Provider terms | User supplies their own key; no provider SDK weights ship with Chengzhu. |",
        "",
    ]
    for title, lock in (("Frontend (npm)", ROOT / "frontend" / "package-lock.json"), ("Desktop (npm)", ROOT / "desktop" / "package-lock.json")):
        rows = _npm_rows(lock)
        out += [f"## {title}", "", f"{len(rows)} packages. `dev` = build/test only, not shipped in the app bundle.", "", "| Package | Version | License | Scope |", "|---|---|---|---|"]
        for name, version, lic, dev in rows:
            out.append(f"| `{name}` | {version} | {lic} | {'dev' if dev else 'runtime'} |")
            if not dev and not _is_permissive(lic):
                flagged.append(f"npm {name}@{version}: {lic}")
        out.append("")
    py_rows = _python_rows(ROOT / "backend" / "requirements.txt")
    out += ["## Backend (Python, bundled into the sidecar)", "", "| Package | Version | License |", "|---|---|---|"]
    for name, version, lic in py_rows:
        out.append(f"| `{name}` | {version} | {lic} |")
        if name.lower() in KNOWN_COPYLEFT_PYTHON:
            flagged.append(f"python {name}: known copyleft ({KNOWN_COPYLEFT_PYTHON[name.lower()]})")
        elif version == "(not installed)":
            # Cannot be read on this machine (e.g. Windows-only wheels on the
            # Linux CI runner); the Windows release job installs every
            # requirement and verifies it there.
            unverified.append(name)
        elif not _is_permissive(lic):
            flagged.append(f"python {name}=={version}: {lic}")
    out.append("")
    out += [
        "## Copyleft components shipped in the Windows build",
        "",
        "- none. PDF page rendering uses **pypdfium2** (PDFium; BSD-3-Clause / Apache-2.0) since v1.2.0;",
        "  PyMuPDF (AGPL-3.0) was removed before the first MIT release (`reports/PYMUPDF_LICENSE_DECISION.md`).",
        "  The pypdfium2 wheel carries PDFium's bundled third-party licenses (FreeType, ICU, libjpeg-turbo,",
        "  libpng, OpenJPEG, lcms, zlib, abseil …) in its `dist-info/licenses` directory, which the installer keeps.",
        "",
    ]
    out += ["## Needs manual review", ""]
    out += [f"- {item}" for item in flagged] or ["- none"]
    out.append("")
    return "\n".join(out), flagged, unverified


def main() -> int:
    text, flagged, unverified = render()
    if unverified:
        print("Not installed here; license verified by the Windows release job:", ", ".join(unverified))
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        # Versions differ between machines for Python; compare only the npm
        # section + header to keep the check deterministic in CI.
        if current.split("## Backend")[0] != text.split("## Backend")[0]:
            print("THIRD_PARTY_NOTICES.md is out of date; run scripts/generate_third_party_notices.py")
            return 1
        # Release gate: a shipped dependency outside the allow-list (AGPL,
        # GPL, non-commercial, unknown) fails the check instead of only
        # being listed.
        if flagged:
            print("Shipped dependencies need license review:")
            for item in flagged:
                print("  FLAG", item)
            return 1
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} ({len(flagged)} flagged)")
    for item in flagged:
        print("  FLAG", item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
