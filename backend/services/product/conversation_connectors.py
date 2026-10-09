"""Provider-agnostic Conversation connector runtime.

The runtime deliberately owns *contracts and audit*, not OAuth/token storage.
Provider-specific adapters are registered by integration packages at runtime.
Without a registered adapter, capabilities remain unavailable and Conversation
Preflight/execution fail closed.
"""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from services.storage import product as store


READ_CAPABILITIES = {
    "calendar.read",
    "docs.read",
    "mail.read",
    "project.read",
}

WRITE_CAPABILITIES = {
    "mail.send",
    "task.create",
    "issue.create",
    "decision_log.write",
}

ALL_CAPABILITIES = READ_CAPABILITIES | WRITE_CAPABILITIES

DRAFT_CAPABILITY = {
    "FOLLOWUP_EMAIL_DRAFT": "mail.send",
    "CREATE_TASK_DRAFT": "task.create",
    "CREATE_ISSUE_DRAFT": "issue.create",
    "UPDATE_DECISION_LOG_DRAFT": "decision_log.write",
}

CONNECTED = "CONNECTED"
DISCONNECTED = "DISCONNECTED"
ERROR = "ERROR"

_SECRET_KEYS = {
    "token", "access_token", "refresh_token", "id_token",
    "api_key", "apikey", "secret", "client_secret", "password",
    "authorization", "cookie", "set-cookie", "private_key",
}


def _sanitize_for_storage(value: Any, *, depth: int = 0) -> Any:
    """Recursively remove credential-like fields from connector-owned payloads."""
    if depth > 8:
        return "[TRUNCATED_DEPTH]"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            normalized = key.lower().replace("-", "_")
            if normalized in {k.replace("-", "_") for k in _SECRET_KEYS}:
                continue
            out[key[:200]] = _sanitize_for_storage(raw_value, depth=depth + 1)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_for_storage(item, depth=depth + 1) for item in list(value)[:500]]
    if isinstance(value, str):
        return value[:20_000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:20_000]


class ConnectorAdapter(Protocol):
    provider: str
    capabilities: set[str]

    def health(self) -> dict[str, Any]:
        ...

    def read_context(self, capability: str, query: dict[str, Any]) -> list[dict[str, Any]]:
        ...

    def execute(self, capability: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class RuntimeConnector:
    connector_id: str
    provider: str
    label: str
    capabilities: tuple[str, ...]
    scopes: tuple[str, ...]


_lock = threading.RLock()
_adapters: dict[str, ConnectorAdapter] = {}


def _provider(value: str) -> str:
    provider = str(value or "").strip().lower()
    if not provider:
        raise ValueError("connector provider 不能为空")
    return provider


def _capabilities(values: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    result = sorted({str(v or "").strip() for v in values if str(v or "").strip()})
    unsupported = [v for v in result if v not in ALL_CAPABILITIES]
    if unsupported:
        raise ValueError(f"不支持的 connector capability: {', '.join(unsupported)}")
    return result


def register_adapter(adapter: ConnectorAdapter) -> None:
    provider = _provider(getattr(adapter, "provider", ""))
    capabilities = _capabilities(set(getattr(adapter, "capabilities", set()) or set()))
    if not capabilities:
        raise ValueError("connector adapter 至少声明一个 capability")
    with _lock:
        _adapters[provider] = adapter


def unregister_adapter(provider: str) -> None:
    with _lock:
        _adapters.pop(_provider(provider), None)


def reset_adapters_for_tests() -> None:
    with _lock:
        _adapters.clear()


def adapter(provider: str) -> Optional[ConnectorAdapter]:
    with _lock:
        return _adapters.get(_provider(provider))


def registered_providers() -> list[dict[str, Any]]:
    with _lock:
        items = list(_adapters.items())
    out: list[dict[str, Any]] = []
    for provider, runtime in items:
        try:
            health = _sanitize_for_storage(dict(runtime.health() or {}))
        except Exception as exc:
            health = {"ok": False, "error": str(exc)}
        out.append({
            "provider": provider,
            "capabilities": _capabilities(set(getattr(runtime, "capabilities", set()) or set())),
            "health": health,
        })
    return sorted(out, key=lambda item: item["provider"])


def connect(
    provider: str,
    *,
    label: str = "",
    capabilities: Optional[list[str]] = None,
    scopes: Optional[list[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
    connector_id: str = "",
) -> dict[str, Any]:
    """Persist non-secret account metadata after a provider adapter is real."""
    normalized = _provider(provider)
    runtime = adapter(normalized)
    if runtime is None:
        raise ValueError(f"connector provider {normalized} 没有真实 runtime adapter")
    supported = set(_capabilities(set(getattr(runtime, "capabilities", set()) or set())))
    requested = set(_capabilities(capabilities or list(supported)))
    if not requested:
        raise ValueError("connector 至少需要一个 capability")
    if not requested <= supported:
        missing = ", ".join(sorted(requested - supported))
        raise ValueError(f"adapter 不支持 capability: {missing}")
    health = _sanitize_for_storage(dict(runtime.health() or {}))
    if not bool(health.get("ok", False)):
        raise ValueError(str(health.get("error") or "connector runtime health check failed"))

    now = store.now()
    cid = connector_id or store.new_id("ccn_")
    existing = store.get("conversation_connector", cid)
    row = {
        "id": cid,
        "provider": normalized,
        "label": str(label or normalized)[:200],
        "status": CONNECTED,
        "capabilities": sorted(requested),
        "scopes": sorted({str(x) for x in (scopes or []) if str(x)}),
        # Never accept obvious secret-like metadata keys into product.db.
        "metadata": _sanitize_for_storage(dict(metadata or {})),
        "last_error": "",
        "created_at": (existing or {}).get("created_at") or now,
        "updated_at": now,
    }
    if existing:
        store.update("conversation_connector", cid, row)
    else:
        store.insert("conversation_connector", row)
    return store.get("conversation_connector", cid) or row


def disconnect(connector_id: str) -> dict[str, Any]:
    row = require_connector(connector_id)
    store.update("conversation_connector", connector_id, {
        "status": DISCONNECTED,
        "updated_at": store.now(),
    })
    return store.get("conversation_connector", connector_id) or row


def require_connector(connector_id: str) -> dict[str, Any]:
    row = store.get("conversation_connector", connector_id)
    if not row:
        raise ValueError("Conversation connector 不存在")
    return row


def list_connectors() -> list[dict[str, Any]]:
    rows = store.select("conversation_connector", order="updated_at DESC")
    registered = {item["provider"]: item for item in registered_providers()}
    out: list[dict[str, Any]] = []
    for row in rows:
        runtime = registered.get(str(row.get("provider") or "").lower())
        status = str(row.get("status") or DISCONNECTED)
        available = bool(
            status == CONNECTED
            and runtime
            and bool((runtime.get("health") or {}).get("ok", False))
        )
        out.append({
            **row,
            "runtime_registered": runtime is not None,
            "runtime_health": (runtime or {}).get("health") or {"ok": False, "error": "adapter_not_registered"},
            "available": available,
        })
    return out


def capability_status(capabilities: list[str]) -> dict[str, Any]:
    requested = _capabilities(capabilities)
    connectors = list_connectors()
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for capability in requested:
        match = next(
            (
                row for row in connectors
                if row["available"] and capability in set(row.get("capabilities") or [])
            ),
            None,
        )
        if match:
            resolved[capability] = match["id"]
        else:
            missing.append(capability)
    return {
        "requested": requested,
        "resolved": resolved,
        "missing": missing,
        "ok": not missing,
    }


def collect_read_context(
    capabilities: list[str],
    *,
    query: dict[str, Any],
    max_items_per_capability: int = 8,
) -> list[dict[str, Any]]:
    """Read external context only through connected, capability-matched adapters."""
    status = capability_status([cap for cap in capabilities if cap in READ_CAPABILITIES])
    if status["missing"]:
        raise ValueError(
            "connector read capability unavailable: " + ", ".join(status["missing"])
        )

    snapshots: list[dict[str, Any]] = []
    for capability, connector_id in status["resolved"].items():
        connector = require_connector(connector_id)
        runtime = adapter(str(connector["provider"]))
        if runtime is None:
            raise ValueError(f"connector provider {connector['provider']} runtime unavailable")
        rows = runtime.read_context(capability, dict(query or {})) or []
        for raw in list(rows)[:max_items_per_capability]:
            raw = dict(raw or {})
            external_id = str(raw.get("external_id") or raw.get("id") or "")
            title = str(raw.get("title") or "")[:300]
            excerpt = str(raw.get("excerpt") or raw.get("text") or "")[:4000]
            stable = json.dumps(
                {
                    "provider": connector["provider"],
                    "capability": capability,
                    "external_id": external_id,
                    "title": title,
                    "excerpt": excerpt,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            snapshots.append({
                "connector_id": connector_id,
                "provider": connector["provider"],
                "capability": capability,
                "external_id": external_id,
                "title": title,
                "excerpt": excerpt,
                "content_hash": hashlib.sha256(stable.encode("utf-8")).hexdigest(),
                "visibility": str(raw.get("visibility") or "PRIVATE"),
                "metadata": _sanitize_for_storage({
                    str(k): v for k, v in raw.items()
                    if k not in {"text", "excerpt"}
                }),
            })
    return snapshots


def _execution_payload(draft: dict[str, Any], capability: str) -> dict[str, Any]:
    return {
        "draft_action_id": draft["id"],
        "kind": draft["kind"],
        "title": draft.get("title") or "",
        "content": draft.get("content") or "",
        "target": draft.get("target") or "",
        "source_refs": list(draft.get("source_refs") or []),
        "capability": capability,
    }


def list_executions(draft_action_id: str = "") -> list[dict[str, Any]]:
    if draft_action_id:
        return store.select(
            "conversation_external_execution",
            where="draft_action_id = ?",
            params=(draft_action_id,),
            order="created_at DESC",
        )
    return store.select("conversation_external_execution", order="created_at DESC", limit=200)


def execute_draft_action(
    draft_action_id: str,
    connector_id: str,
) -> dict[str, Any]:
    """Execute an explicitly APPROVED local draft through a real connector.

    Idempotency rule: one successful execution per draft+connector+operation.
    A failed attempt remains audit-visible and may be retried explicitly.
    """
    draft = store.get("conversation_draft_action", draft_action_id)
    if not draft:
        raise ValueError("DraftAction 不存在")
    if draft.get("status") != "APPROVED":
        raise ValueError("只有 APPROVED DraftAction 才能执行外部写回")

    capability = DRAFT_CAPABILITY.get(str(draft.get("kind") or ""))
    if not capability:
        raise ValueError("该 DraftAction 没有对应的外部执行 capability")

    session = store.get("conversation_session", str(draft.get("session_id") or ""))
    if not session:
        raise ValueError("DraftAction 对应 Session 不存在")
    policy = dict(session.get("policy") or {})
    if str(policy.get("external_writeback") or "REVIEW_REQUIRED") == "OFF":
        raise ValueError("本场 External Write-back 已关闭")
    allowed = set(policy.get("connector_permissions") or [])
    if capability not in allowed:
        raise ValueError(f"本场未授权 connector capability: {capability}")

    connector = require_connector(connector_id)
    if connector.get("status") != CONNECTED:
        raise ValueError("目标 connector 未连接")
    if capability not in set(connector.get("capabilities") or []):
        raise ValueError(f"目标 connector 不支持 {capability}")
    runtime = adapter(str(connector.get("provider") or ""))
    if runtime is None:
        raise ValueError("目标 connector runtime adapter 不可用")
    health = dict(runtime.health() or {})
    if not bool(health.get("ok", False)):
        raise ValueError(str(health.get("error") or "connector health check failed"))

    succeeded = store.select(
        "conversation_external_execution",
        where="draft_action_id = ? AND connector_id = ? AND operation = ? AND status = 'SUCCEEDED'",
        params=(draft_action_id, connector_id, capability),
        order="created_at DESC",
        limit=1,
    )
    if succeeded:
        return {**succeeded[0], "idempotent_replay": True}

    now = store.now()
    execution_id = store.new_id("cex_")
    payload = _execution_payload(draft, capability)
    store.insert("conversation_external_execution", {
        "id": execution_id,
        "connector_id": connector_id,
        "draft_action_id": draft_action_id,
        "operation": capability,
        "target": str(draft.get("target") or "")[:500],
        "request": payload,
        "result": {},
        "status": "PENDING",
        "external_ref": "",
        "error": "",
        "created_at": now,
        "completed_at": None,
    })

    try:
        raw_result = dict(runtime.execute(capability, payload) or {})
        result = _sanitize_for_storage(raw_result)
        external_ref = str(result.get("external_ref") or result.get("id") or "")[:1000]
        store.update("conversation_external_execution", execution_id, {
            "result": result,
            "status": "SUCCEEDED",
            "external_ref": external_ref,
            "error": "",
            "completed_at": store.now(),
        })
    except Exception as exc:
        store.update("conversation_external_execution", execution_id, {
            "status": "FAILED",
            "error": str(exc)[:3000],
            "completed_at": store.now(),
        })
    return store.get("conversation_external_execution", execution_id) or {
        "id": execution_id,
        "status": "FAILED",
    }
