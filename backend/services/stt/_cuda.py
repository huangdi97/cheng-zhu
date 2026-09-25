"""Locate CUDA runtime DLLs (cuBLAS/cuDNN) and prepend them to the DLL search path.

ctranslate2 (faster-whisper) on CUDA needs ``cublas64_*.dll`` / ``cudnn64_*.dll``
to be findable. On this kind of Windows setup they usually live inside:
- a CUDA-enabled torch:  site-packages/torch/lib
- the nvidia pip wheels: site-packages/nvidia/{cublas,cudnn,cuda_runtime}/bin
- a CUDA toolkit:        C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v*/bin

We prepend the first directory that actually contains a cuBLAS DLL to PATH
before ctranslate2 is imported/used. Safe to call multiple times.
"""

from __future__ import annotations

import os
import site
import sys

_ENSURED = False


def _site_packages_dirs() -> list[str]:
    dirs: list[str] = []
    seen: set[str] = set()
    for p in list(sys.path) + list(site.getsitepackages()):
        try:
            rp = os.path.realpath(p)
        except Exception:
            continue
        if rp and rp not in seen:
            seen.add(rp)
            dirs.append(rp)
    return dirs


def _candidate_dirs() -> list[str]:
    out: list[str] = []
    for sp in _site_packages_dirs():
        out.append(os.path.join(sp, "torch", "lib"))
        for n in ("cublas", "cudnn", "cuda_runtime", "cuda_nvrtc"):
            out.append(os.path.join(sp, "nvidia", n, "bin"))
    # CUDA toolkit
    tk_root = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"
    try:
        if os.path.isdir(tk_root):
            for name in sorted(os.listdir(tk_root), reverse=True):
                out.append(os.path.join(tk_root, name, "bin"))
    except Exception:
        pass
    return out


def ensure_cuda_dll_path() -> None:
    global _ENSURED
    if _ENSURED:
        return
    _ENSURED = True
    if os.environ.get("IA_SKIP_CUDA_PATH"):
        return
    found: list[str] = []
    for d in _candidate_dirs():
        try:
            if not os.path.isdir(d):
                continue
            names = os.listdir(d)
        except Exception:
            continue
        has_cublas = any(n.lower().startswith("cublas64_") and n.lower().endswith(".dll") for n in names)
        has_cudnn = any(n.lower().startswith("cudnn64_") and n.lower().endswith(".dll") for n in names)
        if has_cublas or has_cudnn:
            found.append(d)
    if not found:
        return
    current = os.environ.get("PATH", "")
    parts = [d for d in found if d not in current.split(";")]
    if parts:
        os.environ["PATH"] = ";".join(parts) + (";" + current if current else "")