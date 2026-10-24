"""At-rest protection for the documents a user would least want copied.

Windows uses DPAPI (`CryptProtectData`): the key is the current Windows user's
credential, so a blob copied to another account, another machine or a backup cannot
be turned back into the document. That is the threat this closes — a resume sitting
readable in a synced folder, a copied profile, an uploaded support bundle.

It is explicitly **not** a replacement for disk encryption and does not stop a
process already running as the same user: that process can call
`CryptUnprotectData` too. Other platforms have no implementation here; `protect()`
returns `None`, callers keep the original bytes, and `status()` says "unsupported"
instead of pretending the feature exists.

Format: `MAGIC` + DPAPI blob. `unprotect()` leaves anything without the magic
untouched, so plaintext written by an older build still reads correctly and a
partially migrated directory stays usable.
"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import hashlib
import sys
from typing import Any, Optional

MAGIC = b"CZHDPAPI1\n"

_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class AtRestError(RuntimeError):
    """Raised when a protected blob cannot be unwrapped."""


def is_protected(data: bytes) -> bool:
    return bool(data) and data.startswith(MAGIC)


def available() -> bool:
    return sys.platform == "win32"


def _entropy(purpose: str) -> bytes:
    return hashlib.sha256(("chengzhu:" + purpose).encode("utf-8")).digest()


if sys.platform == "win32":  # pragma: no cover - exercised on Windows only

    class _BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    def _blob(data: bytes) -> "_BLOB":
        buffer = ctypes.create_string_buffer(data, len(data))
        return _BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))

    def _call(fn, data: bytes, entropy: bytes) -> bytes:
        src = _blob(data)
        ent = _blob(entropy)
        out = _BLOB()
        ok = fn(ctypes.byref(src), None, ctypes.byref(ent), None, None, _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out))
        if not ok:
            raise AtRestError(f"DPAPI call failed: {ctypes.GetLastError()}")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out.pbData)


def protect(data: bytes, purpose: str = "resume") -> Optional[bytes]:
    """Return MAGIC + protected bytes, or None when this platform cannot protect."""
    if not available() or not data:
        return None
    try:
        blob = _call(ctypes.windll.crypt32.CryptProtectData, data, _entropy(purpose))
    except Exception:  # noqa: BLE001 - protection is best effort, never lose the write
        return None
    return MAGIC + blob


def unprotect(data: bytes, purpose: str = "resume") -> bytes:
    """Return the original bytes. Plaintext input is returned unchanged."""
    if not is_protected(data):
        return data
    if not available():
        raise AtRestError("protected payload on a platform without DPAPI")
    blob = data[len(MAGIC):]
    return _call(ctypes.windll.crypt32.CryptUnprotectData, blob, _entropy(purpose))


def status() -> dict[str, Any]:
    return {
        "available": available(),
        "scheme": "windows-dpapi" if available() else "none",
        "magic": base64.b64encode(MAGIC).decode("ascii"),
        "covers": ["resume uploads"],
        "does_not_cover": [
            "sqlite text columns",
            "a process already running as this user",
            "a compromised OS account",
        ],
        "note": "绕过文件拷贝和同步目录，不替代磁盘加密，也不阻止同用户进程解密。",
    }
