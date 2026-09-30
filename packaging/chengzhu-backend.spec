# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Chengzhu backend sidecar (R2 Stage AG).
#
# Build (from repo root):
#   python -m PyInstaller packaging/chengzhu-backend.spec --noconfirm --distpath build/sidecar --workpath build/pyinstaller
#
# Output: build/sidecar/chengzhu-backend/chengzhu-backend.exe (onedir: fast
# start, no temp extraction). Electron ships that folder as resources/backend.
#
# SECURITY / PRIVACY: only code, the example config and static assets are
# bundled. backend/config.json (a developer's real keys), data/, log/ and
# tmp/ are never included.
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

REPO = os.path.abspath(os.path.join(SPECPATH, ".."))
BACKEND = os.path.join(REPO, "backend")

hiddenimports = []
for pkg in ("api", "services", "core", "evals"):
    hiddenimports += collect_submodules(pkg, filter=lambda name: ".tests" not in name)
hiddenimports += collect_submodules("uvicorn")
hiddenimports += [
    "websockets.legacy",
    "websockets.legacy.server",
    "multipart",
    "python_multipart",
    "sounddevice",
    "soundcard",
    "mss",
    "opencc",
    "docx",
    "pypdf",
    "pypdfium2",
    "pypdfium2_raw",
    "qrcode",
    "faster_whisper",
    "ctranslate2",
]

datas = [
    (os.path.join(BACKEND, "config.example.json"), "."),
    (os.path.join(BACKEND, "assets"), "assets"),
    (os.path.join(BACKEND, "services", "capture", "_screen_capture_worker.py"), os.path.join("services", "capture")),
    (os.path.join(REPO, "LICENSE"), "."),
    (os.path.join(REPO, "THIRD_PARTY_NOTICES.md"), "."),
]
for pkg in ("faster_whisper", "opencc", "certifi"):
    try:
        datas += collect_data_files(pkg)
    except Exception:  # noqa: BLE001 - optional runtime data
        pass

a = Analysis(
    [os.path.join(BACKEND, "sidecar.py")],
    pathex=[BACKEND],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Heavy ML stacks are never Chengzhu runtime deps; excluding them keeps a
    # polluted build interpreter from ballooning the installer.
    excludes=[
        "tkinter", "pytest", "matplotlib", "IPython", "notebook", "PyInstaller",
        "torch", "torchvision", "torchaudio", "triton", "tensorflow", "keras", "jax",
        "transformers", "sklearn", "scipy", "pandas", "cv2",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="chengzhu-backend",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="chengzhu-backend",
)
