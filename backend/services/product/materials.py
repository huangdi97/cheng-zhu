"""Material taxonomy and lifecycle (canonical §6 Library, §8 lifecycle).

Project Materials declare a usage on upload: FACTS (项目事实与来源),
REFERENCE (技术参考) or BOTH. Knowledge-base material is never personal
evidence by default — only FACTS/BOTH project material may feed the
candidate's provenance.

Lifecycle per material, derived from its versions:
  PROCESSING  first version still being processed
  READY       an active READY version exists
  FAILED      no READY version and the latest attempt failed
  REPLACING   an active READY version exists and a newer one is processing
The old READY version stays active until the replacement is READY. Pack
freeze reads ``ready_text`` which only ever returns a READY version.
"""
from __future__ import annotations

import hashlib
import tempfile
import threading
from pathlib import Path
from typing import Any, Optional

from core.logger import get_logger
from services.product import events
from services.storage import product as store

_log = get_logger("product.materials")

KINDS = ("PROJECT", "KB")
USAGES = ("FACTS", "REFERENCE", "BOTH")
MIN_TEXT_CHARS = 20
MAX_TEXT_CHARS = 400_000


class MaterialError(ValueError):
    pass


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def extract_text(filename: str, data: bytes) -> str:
    """Text from an uploaded file via the KB loaders; plain decode for text."""
    suffix = Path(filename or "material.txt").suffix.lower() or ".txt"
    if suffix in (".txt", ".md", ".markdown", ".csv", ".json", ".log"):
        for encoding in ("utf-8", "utf-8-sig", "gb18030"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise MaterialError("无法识别文本编码（请另存为 UTF-8）")
    from services.kb.loaders import dispatch_loader

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"upload{suffix}"
        path.write_bytes(data)
        loader = dispatch_loader(path)
        if loader is None:
            raise MaterialError(f"不支持的文件类型：{suffix}")
        doc = loader.load(path, rel_path=path.name)
        return "\n\n".join(s.text for s in doc.sections if (s.text or "").strip())


def _validate_text(text: str) -> str:
    clean = (text or "").replace("\x00", "").strip()
    if len(clean) < MIN_TEXT_CHARS:
        raise MaterialError(f"可读文本过少（{len(clean)} 字），可能是扫描件或空文件")
    return clean[:MAX_TEXT_CHARS]


def create_material(
    title: str,
    *,
    kind: str = "PROJECT",
    usage: str = "FACTS",
    filename: str = "",
    text: str = "",
    data: Optional[bytes] = None,
    background: bool = False,
) -> dict[str, Any]:
    if kind not in KINDS:
        raise MaterialError(f"未知资料类型：{kind}")
    if usage not in USAGES:
        raise MaterialError(f"未知用途：{usage}")
    if kind == "KB" and usage != "REFERENCE":
        # canonical: a knowledge base is never personal evidence by default
        usage = "REFERENCE"
    now = store.now()
    material = {"id": store.new_id("m_"), "kind": kind, "usage": usage,
                "title": (title or filename or "未命名资料").strip()[:120],
                "active_version_id": "", "created_at": now, "updated_at": now}
    store.insert("material", material)
    version = _new_version(material["id"], filename)
    events.record("material_added", kind=kind, usage=usage)
    _schedule(version["id"], text, data, filename, background)
    return get_material(material["id"]) or material


def replace_material(material_id: str, *, filename: str = "", text: str = "",
                     data: Optional[bytes] = None, background: bool = False) -> dict[str, Any]:
    material = require_material(material_id)
    version = _new_version(material_id, filename)
    events.record("material_replaced", kind=material["kind"])
    _schedule(version["id"], text, data, filename, background)
    return get_material(material_id) or material


def retry_material(material_id: str, *, text: str = "", data: Optional[bytes] = None,
                   filename: str = "", background: bool = False) -> dict[str, Any]:
    """Re-run processing for the latest FAILED version with new input."""
    latest = _latest_version(material_id)
    if latest is None or latest["status"] != "FAILED":
        raise MaterialError("只有失败的版本可以重试")
    if not text and data is None:
        raise MaterialError("重试需要重新提供文件或文本")
    store.update("material_version", latest["id"], {"status": "PROCESSING", "error": "",
                                                    "filename": filename or latest["filename"],
                                                    "updated_at": store.now()})
    _schedule(latest["id"], text, data, filename or latest["filename"], background)
    return require_material(material_id)


def _new_version(material_id: str, filename: str) -> dict[str, Any]:
    current = store.scalar("SELECT COALESCE(MAX(version), 0) FROM material_version WHERE material_id = ?",
                           (material_id,)) or 0
    now = store.now()
    row = {"id": store.new_id("mv_"), "material_id": material_id, "version": int(current) + 1,
           "filename": filename or "", "status": "PROCESSING", "error": "",
           "created_at": now, "updated_at": now}
    store.insert("material_version", row)
    return row


def _schedule(version_id: str, text: str, data: Optional[bytes], filename: str, background: bool) -> None:
    if background:
        threading.Thread(target=process_version, args=(version_id, text, data, filename),
                         daemon=True, name=f"material-{version_id}").start()
    else:
        process_version(version_id, text, data, filename)


def process_version(version_id: str, text: str = "", data: Optional[bytes] = None, filename: str = "") -> str:
    """PROCESSING → READY | FAILED. Activates the version only when READY."""
    try:
        raw = text if text else extract_text(filename, data or b"")
        clean = _validate_text(raw)
    except Exception as exc:  # noqa: BLE001 — every failure becomes a visible FAILED reason
        reason = str(exc) if isinstance(exc, MaterialError) else f"解析失败：{type(exc).__name__}"
        store.update("material_version", version_id, {"status": "FAILED", "error": reason[:300],
                                                      "updated_at": store.now()})
        version = store.get("material_version", version_id)
        events.record("material_failed")
        _log.info("material version %s failed: %s", version_id, reason)
        if version:
            store.update("material", version["material_id"], {"updated_at": store.now()})
        return "FAILED"
    version = store.get("material_version", version_id)
    if version is None:
        return "FAILED"
    with store.connect() as conn:
        conn.execute(
            "UPDATE material_version SET status = 'READY', content_text = ?, content_hash = ?, error = '', "
            "updated_at = ? WHERE id = ?",
            (clean, _hash(clean), store.now(), version_id),
        )
        previous = conn.execute("SELECT active_version_id FROM material WHERE id = ?",
                                (version["material_id"],)).fetchone()
        conn.execute("UPDATE material SET active_version_id = ?, updated_at = ? WHERE id = ?",
                     (version_id, store.now(), version["material_id"]))
        if previous and previous[0] and previous[0] != version_id:
            conn.execute("UPDATE material_version SET status = 'SUPERSEDED' WHERE id = ?", (previous[0],))
    return "READY"


def _latest_version(material_id: str) -> Optional[dict[str, Any]]:
    found = store.select("material_version", "material_id = ?", (material_id,), "version DESC", 1)
    return found[0] if found else None


def lifecycle(material: dict[str, Any]) -> dict[str, Any]:
    versions = store.select("material_version", "material_id = ?", (material["id"],), "version DESC")
    active = next((v for v in versions if v["id"] == material.get("active_version_id")), None)
    latest = versions[0] if versions else None
    if active and latest and latest["id"] != active["id"] and latest["status"] == "PROCESSING":
        state = "REPLACING"
    elif active:
        state = "READY"
    elif latest and latest["status"] == "FAILED":
        state = "FAILED"
    else:
        state = "PROCESSING"
    failed = latest if latest and latest["status"] == "FAILED" else None
    return {
        "state": state,
        "active_version": _public_version(active),
        "latest_version": _public_version(latest),
        "error": failed["error"] if failed else "",
        "actions": _actions(state, failed is not None),
    }


def _actions(state: str, has_failure: bool) -> list[str]:
    if state == "FAILED":
        return ["view_reason", "retry", "replace"]
    if state == "READY":
        return ["replace", "view_reason"] if has_failure else ["replace"]
    return []


def _public_version(version: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if version is None:
        return None
    return {k: version[k] for k in ("id", "version", "filename", "status", "error", "content_hash",
                                    "created_at", "updated_at")} | {"chars": len(version.get("content_text") or "")}


def get_material(material_id: str) -> Optional[dict[str, Any]]:
    material = store.get("material", material_id)
    if material is None:
        return None
    return {**material, "lifecycle": lifecycle(material)}


def require_material(material_id: str) -> dict[str, Any]:
    material = get_material(material_id)
    if material is None:
        raise MaterialError("资料不存在")
    return material


def list_materials(kind: str = "") -> list[dict[str, Any]]:
    rows = store.select("material", "kind = ?", (kind,), "updated_at DESC") if kind else \
        store.select("material", "", (), "updated_at DESC")
    return [{**m, "lifecycle": lifecycle(m)} for m in rows]


def set_usage(material_id: str, usage: str) -> dict[str, Any]:
    material = require_material(material_id)
    if usage not in USAGES:
        raise MaterialError(f"未知用途：{usage}")
    if material["kind"] == "KB" and usage != "REFERENCE":
        raise MaterialError("知识库资料不能作为个人事实来源")
    store.update("material", material_id, {"usage": usage, "updated_at": store.now()})
    return require_material(material_id)


def delete_material(material_id: str) -> bool:
    if store.get("material", material_id) is None:
        return False
    store.delete("material", material_id)
    for goal in store.select("goal", "selected_material_ids_json LIKE ?", (f"%{material_id}%",)):
        ids = [i for i in (goal.get("selected_material_ids") or []) if i != material_id]
        store.update("goal", goal["id"], {"selected_material_ids": ids})
    return True


def ready_text(material_id: str) -> Optional[dict[str, Any]]:
    """READY content for pack freeze; None when the material has no READY version."""
    material = store.get("material", material_id)
    if not material or not material.get("active_version_id"):
        return None
    version = store.get("material_version", material["active_version_id"])
    if not version or version["status"] != "READY":
        return None
    return {"material_id": material_id, "version_id": version["id"], "version": version["version"],
            "title": material["title"], "kind": material["kind"], "usage": material["usage"],
            "content_hash": version["content_hash"], "text": version["content_text"],
            "is_personal_evidence": material["kind"] == "PROJECT" and material["usage"] in ("FACTS", "BOTH")}


def materials_for_pack(goal: dict[str, Any]) -> dict[str, Any]:
    included, skipped = [], []
    for material_id in goal.get("selected_material_ids") or []:
        ready = ready_text(material_id)
        if ready is None:
            m = store.get("material", material_id)
            skipped.append({"material_id": material_id, "title": (m or {}).get("title", ""), "reason": "NOT_READY"})
        else:
            included.append(ready)
    return {"included": included, "skipped": skipped}
