"""What is actually readable on this machine, right now.

The privacy copy tells users what to expect; this endpoint answers the question
directly from the filesystem instead of from intent: which stores hold data, which
of them are protected, and whether the disk itself is encrypted.

It is deliberately a *report*, not a promise. Every field says where its answer came
from, and `None` means "could not determine here" rather than "fine".
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from typing import Any, Optional

from services.privacy import at_rest
from services.storage.paths import data_dir

_UPLOAD_DIR = "resume_uploads"


def _disk_encryption() -> dict[str, Any]:
    """Best effort per platform; `protected: null` means undetermined."""
    if sys.platform == "win32":
        return _bitlocker()
    if sys.platform == "darwin":
        return _filevault()
    return {"checked": False, "protected": None, "source": None, "note": "此平台未实现检测"}


def _run(cmd: list[str], timeout: float = 8.0) -> Optional[str]:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception:  # noqa: BLE001 - detection must never fail the request
        return None
    text = (out.stdout or "") + (out.stderr or "")
    return text or None


def _bitlocker() -> dict[str, Any]:
    text = _run(["manage-bde", "-status", os.environ.get("SystemDrive", "C:") + os.sep])
    if not text:
        return {"checked": True, "protected": None, "source": "bitlocker", "note": "无法读取 BitLocker 状态"}
    lowered = text.lower()
    if "protection on" in lowered or "保护已打开" in text or "保护状态: 已打开" in text:
        return {"checked": True, "protected": True, "source": "bitlocker"}
    if "protection off" in lowered or "保护已关闭" in text:
        return {"checked": True, "protected": False, "source": "bitlocker"}
    return {"checked": True, "protected": None, "source": "bitlocker", "note": "输出无法解析"}


def _filevault() -> dict[str, Any]:
    text = _run(["fdesetup", "status"])
    if not text:
        return {"checked": True, "protected": None, "source": "filevault", "note": "无法读取 FileVault 状态"}
    if "FileVault is On" in text:
        return {"checked": True, "protected": True, "source": "filevault"}
    if "FileVault is Off" in text:
        return {"checked": True, "protected": False, "source": "filevault"}
    return {"checked": True, "protected": None, "source": "filevault", "note": "输出无法解析"}


def _uploads() -> dict[str, Any]:
    directory = os.path.join(data_dir(), _UPLOAD_DIR)
    total = protected = 0
    try:
        for name in os.listdir(directory):
            path = os.path.join(directory, name)
            if not os.path.isfile(path):
                continue
            total += 1
            try:
                with open(path, "rb") as handle:
                    if at_rest.is_protected(handle.read(len(at_rest.MAGIC))):
                        protected += 1
            except OSError:
                continue
    except OSError:
        return {"total": 0, "protected": 0, "plaintext": 0}
    return {"total": total, "protected": protected, "plaintext": total - protected}


def _resume_rows() -> dict[str, Any]:
    """Count resume rows whose summary column carries our marker."""
    from services.storage import resume_history as rh

    result = {"total": 0, "protected": 0}
    try:
        conn = sqlite3.connect(rh.DB_PATH)
        try:
            rows = conn.execute("SELECT resume_summary, preview FROM resume_entries").fetchall()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 - no database yet is a normal state
        return result
    for summary, preview in rows:
        result["total"] += 1
        combined = f"{summary or ''}{preview or ''}"
        if _looks_protected(combined):
            result["protected"] += 1
    return result


def _looks_protected(value: str) -> bool:
    import base64

    for candidate in (value or "",):
        try:
            raw = base64.b64decode(candidate, validate=True)
        except Exception:  # noqa: BLE001
            continue
        if at_rest.is_protected(raw):
            return True
    return False


def _databases() -> list[dict[str, Any]]:
    directory = data_dir()
    files: list[dict[str, Any]] = []
    try:
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".db"):
                continue
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                files.append({"name": name, "bytes": os.path.getsize(path)})
    except OSError:
        return []
    return files


def scan() -> dict[str, Any]:
    uploads = _uploads()
    rows = _resume_rows()
    encryption = _disk_encryption()
    at_rest_status = at_rest.status()

    gaps: list[str] = []
    if uploads["plaintext"]:
        gaps.append(f"{uploads['plaintext']} 个简历原件未加密")
    if rows["total"] and rows["protected"] < rows["total"]:
        gaps.append(f"{rows['total'] - rows['protected']} 条简历文本仍为明文")
    if encryption["protected"] is False:
        gaps.append("磁盘未开启加密")
    if not at_rest_status["available"]:
        gaps.append(f"当前平台没有静态加密实现（{sys.platform}）")

    return {
        "data_dir": data_dir(),
        "platform": sys.platform,
        "at_rest": at_rest_status,
        "databases": _databases(),
        "resume_uploads": uploads,
        "resume_rows": rows,
        "disk_encryption": encryption,
        "gaps": gaps,
        "verdict": "clean" if not gaps else "exposed",
    }
