"""Conversation external integration boundary.

This module deliberately separates:
1) provider capability/scope metadata,
2) read-only external snapshots used as provenance-bearing sources,
3) reviewed external execution requests.

No provider token or secret is stored in product.db. Actual adapters are
registered at runtime by provider-specific code; absent adapters fail closed.
"""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlsplit, urlunsplit
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from services.storage import product as store


CONNECTION_STATUSES = {"DISCONNECTED", "CONNECTED", "ERROR", "REVOKED"}
EXECUTION_STATUSES = {"PENDING", "EXECUTING", "SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED"}

PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "GOOGLE_CALENDAR": {
        "label": "Google Calendar",
        "read_scopes": ["calendar.read"],
        "write_scopes": [],
        "external_kinds": ["CALENDAR_EVENT"],
        "provider_scopes": {
            "calendar.read": "https://www.googleapis.com/auth/calendar.readonly",
        },
        "sync": "INCREMENTAL_CURSOR",
    },
    "GOOGLE_MAIL": {
        "label": "Gmail",
        "read_scopes": ["mail.read"],
        "write_scopes": ["mail.send"],
        "external_kinds": ["MAIL_THREAD"],
        "provider_scopes": {
            "mail.read": "https://www.googleapis.com/auth/gmail.readonly",
            "mail.send": "https://www.googleapis.com/auth/gmail.send",
        },
        "sync": "PROVIDER_CURSOR",
    },
    "GOOGLE_DRIVE": {
        "label": "Google Drive / Docs",
        "read_scopes": ["docs.read"],
        "write_scopes": [],
        "external_kinds": ["DOCUMENT"],
        "provider_scopes": {
            "docs.read": "https://www.googleapis.com/auth/drive.readonly",
        },
        "sync": "PROVIDER_CURSOR",
    },
    "MICROSOFT_GRAPH": {
        "label": "Microsoft Graph",
        "read_scopes": ["calendar.read", "mail.read", "docs.read", "tasks.read"],
        "write_scopes": ["mail.send", "tasks.write"],
        "external_kinds": ["CALENDAR_EVENT", "MAIL_THREAD", "DOCUMENT", "TASK"],
        "provider_scopes": {
            "calendar.read": "Calendars.Read",
            "mail.read": "Mail.Read",
            "docs.read": "Files.Read",
            "tasks.read": "Tasks.Read",
            "mail.send": "Mail.Send",
            "tasks.write": "Tasks.ReadWrite",
        },
        "sync": "PROVIDER_CURSOR",
    },
    "GITHUB": {
        "label": "GitHub",
        "read_scopes": ["issues.read"],
        "write_scopes": ["issues.write"],
        "external_kinds": ["ISSUE"],
        "provider_scopes": {
            "issues.read": "Issues: read",
            "issues.write": "Issues: write",
        },
        "sync": "ETAG_OR_CURSOR",
    },
    "MCP": {
        "label": "Model Context Protocol",
        "read_scopes": ["context.read"],
        "write_scopes": ["action.execute"],
        "external_kinds": ["DOCUMENT", "TASK", "ISSUE", "CALENDAR_EVENT", "MAIL_THREAD"],
        "provider_scopes": {
            "context.read": "server-defined read scope",
            "action.execute": "server-defined action scope",
        },
        "sync": "SERVER_DEFINED",
    },
}

DRAFT_OPERATION: dict[str, tuple[str, str]] = {
    "FOLLOWUP_EMAIL_DRAFT": ("SEND_EMAIL", "mail.send"),
    "CREATE_TASK_DRAFT": ("CREATE_TASK", "tasks.write"),
    "CREATE_ISSUE_DRAFT": ("CREATE_ISSUE", "issues.write"),
    "UPDATE_DECISION_LOG_DRAFT": ("UPDATE_DECISION_LOG", "action.execute"),
}


class ConnectorAdapter(Protocol):
    provider: str

    def read_snapshots(
        self,
        *,
        connection: dict[str, Any],
        space_id: str,
        cursor: str,
        limit: int,
    ) -> dict[str, Any]:
        """Return {"items": [...], "next_cursor": "..."}."""

    def execute(
        self,
        *,
        connection: dict[str, Any],
        operation: str,
        target: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Execute one reviewed action and return provider result metadata."""


_ADAPTERS: dict[str, ConnectorAdapter] = {}
_CREDENTIAL_REF_RE = re.compile(r"^(?:keyring|oskeychain|provider|plugin):[A-Za-z0-9._:/-]{1,240}$")


def register_adapter(adapter: ConnectorAdapter) -> None:
    provider = str(getattr(adapter, "provider", "") or "").upper()
    if provider not in PROVIDER_CATALOG:
        raise ValueError("Connector provider 不受支持")
    _ADAPTERS[provider] = adapter


def unregister_adapter(provider: str) -> None:
    _ADAPTERS.pop(str(provider or "").upper(), None)


def catalog() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for provider, spec in PROVIDER_CATALOG.items():
        out.append({
            "provider": provider,
            **spec,
            "adapter_available": provider in _ADAPTERS,
        })
    return out


def _require_connection(connection_id: str) -> dict[str, Any]:
    row = store.get("conversation_connector_connection", connection_id)
    if not row:
        raise ValueError("Connector connection 不存在")
    return row


def _validate_scopes(provider: str, scopes: list[str]) -> list[str]:
    spec = PROVIDER_CATALOG[provider]
    allowed = set(spec["read_scopes"]) | set(spec["write_scopes"])
    clean = sorted({str(scope).strip() for scope in scopes if str(scope).strip()})
    unknown = [scope for scope in clean if scope not in allowed]
    if unknown:
        raise ValueError(f"Connector scope 不受支持：{', '.join(unknown)}")
    return clean


def _validate_credential_ref(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if not _CREDENTIAL_REF_RE.fullmatch(value):
        raise ValueError("credential_ref 只能是 keyring/oskeychain/provider/plugin 的 opaque reference；不能直接存 token")
    return value


def create_connection(
    provider: str,
    *,
    display_name: str = "",
    granted_scopes: Optional[list[str]] = None,
    credential_ref: str = "",
    account_hint: str = "",
) -> dict[str, Any]:
    provider = str(provider or "").upper()
    if provider not in PROVIDER_CATALOG:
        raise ValueError("Connector provider 不受支持")
    scopes = _validate_scopes(provider, list(granted_scopes or []))
    credential_ref = _validate_credential_ref(credential_ref)
    ts = store.now()
    row = {
        "id": store.new_id("ccn_"),
        "provider": provider,
        "display_name": str(display_name or PROVIDER_CATALOG[provider]["label"])[:200],
        "status": "DISCONNECTED",
        "auth_mode": "OPAQUE_REFERENCE" if credential_ref else "NONE",
        "credential_ref": credential_ref,
        "granted_scopes": scopes,
        "capabilities": {
            "read": list(PROVIDER_CATALOG[provider]["read_scopes"]),
            "write": list(PROVIDER_CATALOG[provider]["write_scopes"]),
            "external_kinds": list(PROVIDER_CATALOG[provider]["external_kinds"]),
        },
        "account_hint": str(account_hint or "")[:300],
        "sync_cursor": "",
        "last_sync_at": None,
        "last_error": "",
        "created_at": ts,
        "updated_at": ts,
    }
    store.insert("conversation_connector_connection", row)
    return _require_connection(row["id"])


def list_connections() -> list[dict[str, Any]]:
    rows = store.select("conversation_connector_connection", order="created_at ASC")
    public: list[dict[str, Any]] = []
    for row in rows:
        item = {k: v for k, v in row.items() if k != "credential_ref"}
        item["credential_ref_present"] = bool(row.get("credential_ref"))
        item["adapter_available"] = row["provider"] in _ADAPTERS
        public.append(item)
    return public


def set_connection_status(connection_id: str, status: str, *, error: str = "") -> dict[str, Any]:
    row = _require_connection(connection_id)
    status = str(status or "").upper()
    if status not in CONNECTION_STATUSES:
        raise ValueError("Connector connection 状态不支持")
    if status == "CONNECTED":
        if row["provider"] not in _ADAPTERS:
            raise ValueError("当前 provider adapter 未接线，不能标记 CONNECTED")
        if not row.get("credential_ref"):
            raise ValueError("缺少 opaque credential_ref，不能标记 CONNECTED")
    store.update("conversation_connector_connection", connection_id, {
        "status": status,
        "last_error": str(error or "")[:2000],
        "updated_at": store.now(),
    })
    return _require_connection(connection_id)


def revoke_connection(connection_id: str) -> dict[str, Any]:
    _require_connection(connection_id)
    store.update("conversation_connector_connection", connection_id, {
        "status": "REVOKED",
        "auth_mode": "NONE",
        "credential_ref": "",
        "sync_cursor": "",
        "last_error": "",
        "updated_at": store.now(),
    })
    public = next((row for row in list_connections() if row["id"] == connection_id), None)
    return public or {"id": connection_id, "status": "REVOKED", "credential_ref_present": False}


_SENSITIVE_METADATA_KEY = re.compile(
    r"(?:^|[_-])(token|secret|authorization|credential|cookie|api[_-]?key|refresh[_-]?token|access[_-]?token)(?:$|[_-])",
    re.IGNORECASE,
)


def _sanitize_metadata(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in list(value.items())[:100]:
            key_text = str(key)[:200]
            if _SENSITIVE_METADATA_KEY.search(key_text):
                continue
            out[key_text] = _sanitize_metadata(item, depth=depth + 1)
        return out
    if isinstance(value, list):
        return [_sanitize_metadata(item, depth=depth + 1) for item in value[:100]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value if not isinstance(value, str) else value[:4000]
    return str(value)[:4000]


def _safe_source_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        if parts.scheme not in {"http", "https"}:
            return ""
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))[:2000]
    except ValueError:
        return ""


def _snapshot_hash(item: dict[str, Any]) -> str:
    basis = {
        "external_kind": item.get("external_kind") or "",
        "external_id": item.get("external_id") or "",
        "title": item.get("title") or "",
        "excerpt": item.get("excerpt") or "",
        "occurred_at": item.get("occurred_at"),
        "metadata": item.get("metadata") or {},
    }
    raw = json.dumps(basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _store_snapshot(connection: dict[str, Any], space_id: str, item: dict[str, Any]) -> dict[str, Any]:
    provider = connection["provider"]
    kind = str(item.get("external_kind") or "").upper()
    if kind not in PROVIDER_CATALOG[provider]["external_kinds"]:
        raise ValueError(f"{provider} 不能提供 {kind or '空'} snapshot")
    external_id = str(item.get("external_id") or "").strip()
    if not external_id:
        raise ValueError("Connector snapshot 缺少 external_id")
    normalized = {
        "external_kind": kind,
        "external_id": external_id[:500],
        "title": str(item.get("title") or "")[:500],
        "excerpt": str(item.get("excerpt") or "")[:20_000],
        "occurred_at": item.get("occurred_at"),
        "metadata": _sanitize_metadata(dict(item.get("metadata") or {})),
    }
    content_hash = str(item.get("content_hash") or _snapshot_hash(normalized))
    existing = store.rows(
        "SELECT * FROM conversation_connector_snapshot "
        "WHERE connection_id = ? AND external_kind = ? AND external_id = ? AND content_hash = ? LIMIT 1",
        (connection["id"], kind, external_id, content_hash),
    )
    if existing:
        return existing[0]
    row = {
        "id": store.new_id("ccs_"),
        "connection_id": connection["id"],
        "space_id": space_id,
        **normalized,
        "content_hash": content_hash,
        "source_url": _safe_source_url(str(item.get("source_url") or "")),
        "visibility": str(item.get("visibility") or "PRIVATE").upper()[:80],
        "created_at": store.now(),
    }
    store.insert("conversation_connector_snapshot", row)
    return store.get("conversation_connector_snapshot", row["id"]) or row


def sync_connection(connection_id: str, space_id: str, *, limit: int = 100) -> dict[str, Any]:
    from services.product import conversations

    conversations.require_space(space_id)
    connection = _require_connection(connection_id)
    provider = connection["provider"]
    if connection["status"] != "CONNECTED":
        raise ValueError("Connector 未连接")
    adapter = _ADAPTERS.get(provider)
    if adapter is None:
        raise ValueError("Connector adapter 未接线")
    granted = set(connection.get("granted_scopes") or [])
    required_read = set(PROVIDER_CATALOG[provider]["read_scopes"])
    if not granted.intersection(required_read):
        raise ValueError("Connector 没有任何 read scope，不能同步")

    try:
        result = adapter.read_snapshots(
            connection=connection,
            space_id=space_id,
            cursor=str(connection.get("sync_cursor") or ""),
            limit=max(1, min(int(limit), 500)),
        )
        items = list(result.get("items") or [])
        snapshots = [_store_snapshot(connection, space_id, item) for item in items]
        store.update("conversation_connector_connection", connection_id, {
            "sync_cursor": str(result.get("next_cursor") or connection.get("sync_cursor") or "")[:4000],
            "last_sync_at": store.now(),
            "last_error": "",
            "updated_at": store.now(),
        })
        return {"connection": _require_connection(connection_id), "snapshots": snapshots}
    except Exception as exc:
        store.update("conversation_connector_connection", connection_id, {
            "status": "ERROR",
            "last_error": str(exc)[:2000],
            "updated_at": store.now(),
        })
        raise


def list_snapshots(space_id: str, *, connection_id: str = "", limit: int = 200) -> list[dict[str, Any]]:
    from services.product import conversations

    conversations.require_space(space_id)
    if connection_id:
        return store.select(
            "conversation_connector_snapshot",
            where="space_id = ? AND connection_id = ?",
            params=(space_id, connection_id),
            order="COALESCE(occurred_at, created_at) DESC",
            limit=max(1, min(int(limit), 1000)),
        )
    return store.select(
        "conversation_connector_snapshot",
        where="space_id = ?",
        params=(space_id,),
        order="COALESCE(occurred_at, created_at) DESC",
        limit=max(1, min(int(limit), 1000)),
    )


def snapshot_source_ref(snapshot: dict[str, Any]) -> dict[str, Any]:
    connection = _require_connection(snapshot["connection_id"])
    return {
        "kind": "CONNECTOR_SNAPSHOT",
        "id": snapshot["id"],
        "provider": connection["provider"],
        "external_kind": snapshot["external_kind"],
        "external_id": snapshot["external_id"],
        "content_hash": snapshot["content_hash"],
        "occurred_at": snapshot.get("occurred_at"),
        "visibility": snapshot.get("visibility") or "PRIVATE",
    }


def _idempotency_key(draft: dict[str, Any], connection_id: str, operation: str, target: str) -> str:
    raw = "|".join([
        draft["id"],
        str(draft.get("updated_at") or ""),
        connection_id,
        operation,
        target,
    ]).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def request_execution(
    draft_action_id: str,
    connection_id: str,
    *,
    target: str = "",
) -> dict[str, Any]:
    draft = store.get("conversation_draft_action", draft_action_id)
    if not draft:
        raise ValueError("DraftAction 不存在")
    if draft["status"] != "APPROVED":
        raise ValueError("只有 APPROVED DraftAction 才能请求外部执行")
    mapping = DRAFT_OPERATION.get(str(draft.get("kind") or "").upper())
    if not mapping:
        raise ValueError("DraftAction 没有 external execution mapping")
    operation, required_scope = mapping
    connection = _require_connection(connection_id)
    provider = connection["provider"]
    scopes = set(connection.get("granted_scopes") or [])
    provider_write = set(PROVIDER_CATALOG[provider]["write_scopes"])

    target_value = str(target or draft.get("target") or "")[:1000]
    key = _idempotency_key(draft, connection_id, operation, target_value)
    existing = store.rows(
        "SELECT * FROM conversation_connector_execution WHERE idempotency_key = ? LIMIT 1",
        (key,),
    )
    if existing:
        return existing[0]

    status = "PENDING"
    error = ""
    if connection["status"] != "CONNECTED":
        status, error = "BLOCKED", "Connector 未连接"
    elif required_scope not in scopes or required_scope not in provider_write:
        status, error = "BLOCKED", f"缺少 write scope：{required_scope}"
    elif provider not in _ADAPTERS:
        status, error = "BLOCKED", "Connector adapter 未接线"

    ts = store.now()
    row = {
        "id": store.new_id("cce_"),
        "draft_action_id": draft_action_id,
        "connection_id": connection_id,
        "operation": operation,
        "target": target_value,
        "idempotency_key": key,
        "status": status,
        "request": {
            "draft_kind": draft["kind"],
            "title": draft.get("title") or "",
            "content": draft.get("content") or "",
            "payload": draft.get("payload") or {},
            "source_refs": draft.get("source_refs") or [],
        },
        "response": {},
        "error": error,
        "created_at": ts,
        "updated_at": ts,
        "executed_at": None,
    }
    store.insert("conversation_connector_execution", row)
    return store.get("conversation_connector_execution", row["id"]) or row


def execute_request(execution_id: str) -> dict[str, Any]:
    row = store.get("conversation_connector_execution", execution_id)
    if not row:
        raise ValueError("External execution request 不存在")
    if row["status"] == "SUCCEEDED":
        return row
    if row["status"] == "BLOCKED":
        raise ValueError(row.get("error") or "External execution request 已阻断")
    if row["status"] not in {"PENDING", "FAILED"}:
        raise ValueError("External execution request 当前状态不能执行")

    draft = store.get("conversation_draft_action", row["draft_action_id"])
    if not draft or draft["status"] != "APPROVED":
        store.update("conversation_connector_execution", execution_id, {
            "status": "BLOCKED",
            "error": "DraftAction 不再是 APPROVED",
            "updated_at": store.now(),
        })
        raise ValueError("DraftAction 不再是 APPROVED")

    connection = _require_connection(row["connection_id"])
    if connection["status"] != "CONNECTED":
        store.update("conversation_connector_execution", execution_id, {
            "status": "BLOCKED", "error": "Connector 未连接", "updated_at": store.now(),
        })
        raise ValueError("Connector 未连接")
    adapter = _ADAPTERS.get(connection["provider"])
    if adapter is None:
        store.update("conversation_connector_execution", execution_id, {
            "status": "BLOCKED", "error": "Connector adapter 未接线", "updated_at": store.now(),
        })
        raise ValueError("Connector adapter 未接线")

    store.update("conversation_connector_execution", execution_id, {
        "status": "EXECUTING", "error": "", "updated_at": store.now(),
    })
    try:
        result = adapter.execute(
            connection=connection,
            operation=row["operation"],
            target=row.get("target") or "",
            payload=dict(row.get("request") or {}),
            idempotency_key=row["idempotency_key"],
        )
    except Exception as exc:
        store.update("conversation_connector_execution", execution_id, {
            "status": "FAILED",
            "error": str(exc)[:4000],
            "updated_at": store.now(),
        })
        return store.get("conversation_connector_execution", execution_id) or row

    store.update("conversation_connector_execution", execution_id, {
        "status": "SUCCEEDED",
        "response": dict(result or {}),
        "error": "",
        "updated_at": store.now(),
        "executed_at": store.now(),
    })
    return store.get("conversation_connector_execution", execution_id) or row


def list_executions(*, draft_action_id: str = "", limit: int = 200) -> list[dict[str, Any]]:
    if draft_action_id:
        return store.select(
            "conversation_connector_execution",
            where="draft_action_id = ?",
            params=(draft_action_id,),
            order="created_at DESC",
            limit=max(1, min(int(limit), 1000)),
        )
    return store.select(
        "conversation_connector_execution",
        order="created_at DESC",
        limit=max(1, min(int(limit), 1000),
    )


def runtime_status(*, requested_permissions: Optional[list[str]] = None) -> dict[str, Any]:
    requested = sorted({str(x).strip() for x in (requested_permissions or []) if str(x).strip()})
    connections = list_connections()
    usable = [
        row for row in connections
        if row["status"] == "CONNECTED" and row["provider"] in _ADAPTERS
    ]
    available_scopes: set[str] = set()
    for row in usable:
        available_scopes.update(row.get("granted_scopes") or [])
    missing = [scope for scope in requested if scope not in available_scopes]
    blockers = [
        f"Connector permission {scope} 没有对应的已连接 adapter/scope；不会静默扩大权限。"
        for scope in missing
    ]
    return {
        "requested_permissions": requested,
        "available_scopes": sorted(available_scopes),
        "connected_provider_ids": [row["id"] for row in usable],
        "missing_permissions": missing,
        "blockers": blockers,
        "live_access": "AVAILABLE" if requested and not missing else "NOT_REQUESTED" if not requested else "BLOCKED",
        "snapshot_access": "EXPLICIT_SELECTION_ONLY",
    }


def diagnostics() -> dict[str, Any]:
    connections = list_connections()
    return {
        "catalog": catalog(),
        "connections": connections,
        "connected": sum(1 for row in connections if row["status"] == "CONNECTED"),
        "available_adapters": sorted(_ADAPTERS),
        "external_execution": "REVIEW_REQUIRED_AND_EXPLICIT",
        "secret_storage": "OPAQUE_REFERENCE_ONLY",
    }
