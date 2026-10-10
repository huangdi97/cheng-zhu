"""Conversation external integration boundary.

This module sits *above* conversation_connectors capability truth.

conversation_connectors answers:
    "Is there a real runtime provider for capability X?"

This module answers:
    "Which user-approved connection is allowed to use it, what immutable
     external snapshot entered a Space/Session, and what explicit reviewed
     external action was attempted?"

No OAuth token, refresh token, provider secret or raw API key is stored in
product.db.  credential_ref is an opaque handle resolved by provider-specific
code (OS keychain, provider plugin, etc.).  With no registered adapter this
runtime is intentionally fail-closed.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from typing import Any, Optional, Protocol
from urllib.parse import urlsplit, urlunsplit

from services.product import conversation_connectors
from services.storage import product as store


CONNECTION_STATUSES = {"DISCONNECTED", "CONNECTED", "ERROR", "REVOKED"}
EXECUTION_STATUSES = {"PENDING", "EXECUTING", "SUCCEEDED", "FAILED", "UNKNOWN_OUTCOME", "BLOCKED", "CANCELLED"}

# Product capabilities are the canonical names from conversation_connectors.
PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "GOOGLE_CALENDAR": {
        "label": "Google Calendar",
        "capabilities": ["calendar.read"],
        "external_kinds": ["CALENDAR_EVENT"],
        "provider_scopes": {
            "calendar.read": "https://www.googleapis.com/auth/calendar.events.readonly",
        },
        "sync": "NATIVE_SYNC_TOKEN",
        "setup": {
            "runtime_opt_in_env": "CHENGZHU_GOOGLE_CALENDAR_CONNECTOR_ENABLE=1",
            "credential_ref_format": "provider:google-calendar:env:<ENV_VAR>",
            "read_target": "calendar_id (default primary)",
            "secret_storage": "PROCESS_ENV_ONLY",
            "write_support": "NONE",
        },
    },
    "GOOGLE_MAIL": {
        "label": "Gmail",
        "capabilities": ["email.send"],
        "external_kinds": [],
        "provider_scopes": {
            "email.send": "https://www.googleapis.com/auth/gmail.send",
        },
        "identity_scopes": ["openid", "email"],
        "sync": "WRITE_ONLY_NO_SYNC",
        "setup": {
            "runtime_opt_in_env": "CHENGZHU_GOOGLE_MAIL_CONNECTOR_ENABLE=1",
            "credential_ref_format": "provider:google-mail:env:<ENV_VAR>",
            "write_target": "single recipient email address",
            "secret_storage": "PROCESS_ENV_ONLY",
            "mailbox_read_support": "NONE",
            "oauth_required_scopes": "openid email gmail.send",
            "oauth_scope_classification": "GMAIL_SEND_SENSITIVE",
            "public_release_gate": "GOOGLE_OAUTH_APP_VERIFICATION_REQUIRED",
        },
    },
    "GOOGLE_DRIVE": {
        "label": "Google Drive / Docs",
        "capabilities": ["docs.read"],
        "external_kinds": ["DOCUMENT"],
        "provider_scopes": {
            "docs.read": "https://www.googleapis.com/auth/drive.readonly",
        },
        "sync": "FULL_TARGET_REFRESH",
        "setup": {
            "runtime_opt_in_env": "CHENGZHU_GOOGLE_DRIVE_CONNECTOR_ENABLE=1",
            "credential_ref_format": "provider:google-drive:env:<ENV_VAR>",
            "read_target": "folder_id (default root)",
            "secret_storage": "PROCESS_ENV_ONLY",
            "write_support": "NONE",
            "workspace_export": "Docs/Slides=text/plain; Sheets=first-sheet CSV",
        },
    },
    "MICROSOFT_GRAPH": {
        "label": "Microsoft To Do",
        "capabilities": ["task.create"],
        "external_kinds": [],
        "provider_scopes": {
            "task.create": "Tasks.ReadWrite",
        },
        "sync": "WRITE_ONLY_NO_SYNC",
        "setup": {
            "runtime_opt_in_env": "CHENGZHU_MICROSOFT_TODO_CONNECTOR_ENABLE=1",
            "credential_ref_format": "provider:microsoft-graph:env:<ENV_VAR>",
            "write_target": "default or explicit Microsoft To Do task-list id",
            "secret_storage": "PROCESS_ENV_ONLY",
            "read_support": "NONE",
            "delegated_permission": "Tasks.ReadWrite",
        },
    },
    "GITHUB": {
        "label": "GitHub",
        "capabilities": ["project.read", "issue.create"],
        "external_kinds": ["ISSUE"],
        "provider_scopes": {
            "project.read": "Issues: read",
            "issue.create": "Issues: write",
        },
        "sync": "UPDATED_AT_CURSOR_WITH_OVERLAP",
        "setup": {
            "runtime_opt_in_env": "CHENGZHU_GITHUB_CONNECTOR_ENABLE=1",
            "credential_ref_format": "provider:github:env:<ENV_VAR>",
            "read_target": "owner/repo",
            "write_target": "owner/repo",
            "secret_storage": "PROCESS_ENV_ONLY",
        },
    },
    "MCP": {
        "label": "Model Context Protocol",
        # MCP remains a generic contract surface, but the concrete adapter
        # shipped in v2 exposes only decision_log.write. verify_and_connect()
        # additionally requires the connection grant to be a subset of the
        # registered adapter capabilities, so catalog metadata can never
        # manufacture a real read/write runtime.
        "capabilities": sorted(conversation_connectors.KNOWN_CAPABILITIES),
        "external_kinds": ["DOCUMENT", "TASK", "ISSUE", "CALENDAR_EVENT", "MAIL_THREAD"],
        "provider_scopes": {
            capability: "server-defined"
            for capability in sorted(conversation_connectors.KNOWN_CAPABILITIES)
        },
        "sync": "SERVER_DEFINED",
        "setup": {
            "runtime_opt_in_env": "CHENGZHU_MCP_DECISION_LOG_CONNECTOR_ENABLE=1",
            "credential_ref_format": "provider:mcp:env:<CONFIG_ENV>",
            "concrete_adapter_capabilities": "decision_log.write",
            "protocol": "2026-07-28 Streamable HTTP",
            "write_target": "explicit decision-log target",
            "tool_mapping": "fixed in config env; frontend cannot choose arbitrary tool",
            "secret_storage": "PROCESS_ENV_ONLY",
            "read_support": "NONE_IN_CONCRETE_ADAPTER",
        },
    },
}

DRAFT_CAPABILITY: dict[str, tuple[str, str]] = {
    "FOLLOWUP_EMAIL_DRAFT": ("SEND_EMAIL", "email.send"),
    "CREATE_TASK_DRAFT": ("CREATE_TASK", "task.create"),
    "CREATE_ISSUE_DRAFT": ("CREATE_ISSUE", "issue.create"),
    "UPDATE_DECISION_LOG_DRAFT": ("UPDATE_DECISION_LOG", "decision_log.write"),
}


class ConnectorAdapter(Protocol):
    provider_id: str
    capabilities: set[str]

    def health(self, connection: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Return at minimum {"ok": bool}; may resolve credential_ref securely."""

    def read_context(
        self,
        *,
        connection: dict[str, Any],
        capability: str,
        query: dict[str, Any],
        cursor: str,
        limit: int,
    ) -> dict[str, Any]:
        """Return {"items": [...], "next_cursor": "..."}."""

    def execute(
        self,
        *,
        connection: dict[str, Any],
        capability: str,
        operation: str,
        target: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Execute one already-reviewed action.

        The adapter MUST return an explicit outcome envelope:
          {"ok": True, ...provider metadata...}
        or:
          {"ok": False, "error": "...", "retry_safe": bool, ...}

        Raising, timing out, or returning no explicit boolean `ok` is an
        ambiguous external outcome. Chengzhu records UNKNOWN_OUTCOME and MUST
        NOT retry it automatically because the provider may already have
        applied the side effect. The supplied idempotency_key is only a safety
        primitive when the concrete provider actually enforces it.
        """


_ADAPTERS: dict[str, ConnectorAdapter] = {}
_ACTIVE_EXECUTIONS: set[str] = set()
# External side effects are deliberately serialized in the personal Desktop
# runtime. This makes request claim + connection revoke/disconnect ordering
# deterministic and prevents two UI/API execute requests from calling the
# provider for one audit row at the same time.
_EXECUTION_LOCK = threading.RLock()
_CREDENTIAL_REF_RE = re.compile(r"^(?:keyring|oskeychain|provider|plugin):[A-Za-z0-9._:/-]{1,240}$")
_SENSITIVE_KEY_RE = re.compile(
    r"(?:^|[_-])(token|secret|authorization|credential|cookie|api[_-]?key|"
    r"refresh[_-]?token|access[_-]?token|password|client[_-]?secret|private[_-]?key)(?:$|[_-])",
    re.IGNORECASE,
)

_SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\bya29\.[A-Za-z0-9._-]{8,}"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\b[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b"),
)


def _redact_secret_values(value: str) -> str:
    text = str(value or "")
    for pattern in _SECRET_VALUE_PATTERNS:
        text = pattern.sub("[REDACTED_SECRET]", text)
    return text[:20_000]


def _contains_secret_value(value: str) -> bool:
    text = str(value or "")
    return any(pattern.search(text) for pattern in _SECRET_VALUE_PATTERNS)


def _provider_id(value: str) -> str:
    provider = str(value or "").strip().upper()
    if provider not in PROVIDER_CATALOG:
        raise ValueError("Connector provider 不受支持")
    return provider


def _capabilities(values: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    result = sorted({str(v or "").strip() for v in values if str(v or "").strip()})
    unknown = [v for v in result if v not in conversation_connectors.KNOWN_CAPABILITIES]
    if unknown:
        raise ValueError(f"Connector capability 不受支持：{', '.join(unknown)}")
    return result


def _expected_provider_scopes(provider: str, granted: set[str]) -> list[str]:
    # Gmail send-only needs no mailbox read scope. The two identity scopes are
    # standard OIDC scopes used solely to verify which Google account the
    # access token represents; they do not grant inbox/message read access.
    if provider == "GOOGLE_MAIL" and "email.send" in granted:
        return sorted([
            "openid",
            "email",
            "https://www.googleapis.com/auth/gmail.send",
        ])
    # GitHub fine-grained repository permissions are one level per permission,
    # not independent read+write scopes. Issues: write subsumes read.
    if provider == "GITHUB":
        if "issue.create" in granted:
            return ["Issues: write"]
        if "project.read" in granted:
            return ["Issues: read"]
        return []
    scope_map = dict(PROVIDER_CATALOG[provider].get("provider_scopes") or {})
    expected = {
        str(scope_map.get(capability) or "").strip()
        for capability in granted
        if str(scope_map.get(capability) or "").strip()
    }
    return sorted(expected)


def _validated_provider_scopes(
    provider: str,
    granted: set[str],
    supplied: Optional[list[str]],
) -> list[str]:
    expected = _expected_provider_scopes(provider, granted)
    actual = sorted({str(value or "").strip() for value in (supplied or []) if str(value or "").strip()})
    if not actual:
        return expected
    if provider == "MCP" and expected == ["server-defined"]:
        if actual != ["server-defined"]:
            raise ValueError("MCP provider scope 由 server 定义；Chengzhu 只记录 server-defined，不接受伪造 scope")
        return actual
    if actual != expected:
        raise ValueError(
            "provider_scopes 必须与 granted capabilities 的最小权限集合完全一致；"
            f" expected={expected}, got={actual}"
        )
    return actual


def _validate_credential_ref(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if not _CREDENTIAL_REF_RE.fullmatch(value) or _contains_secret_value(value):
        raise ValueError(
            "credential_ref 只能保存 keyring/oskeychain/provider/plugin 的 opaque reference；不能直接或伪装保存 token"
        )
    return value


def _sanitize(value: Any, *, depth: int = 0) -> Any:
    if depth > 6:
        return "[TRUNCATED_DEPTH]"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for raw_key, raw_value in list(value.items())[:200]:
            key = str(raw_key)[:200]
            if _SENSITIVE_KEY_RE.search(key):
                continue
            out[key] = _sanitize(raw_value, depth=depth + 1)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_sanitize(v, depth=depth + 1) for v in list(value)[:500]]
    if isinstance(value, str):
        return _redact_secret_values(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:20_000]


def _safe_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        if parts.scheme not in {"http", "https"}:
            return ""
        # Strip userinfo/query/fragment because provider URLs often carry
        # credentials or sensitive IDs. Preserve host, optional port and path.
        host = parts.hostname or ""
        if not host:
            return ""
        display_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
        port = f":{parts.port}" if parts.port is not None else ""
        return urlunsplit((parts.scheme, display_host + port, parts.path, "", ""))[:2000]
    except ValueError:
        return ""


def register_adapter(adapter: ConnectorAdapter) -> None:
    provider = _provider_id(getattr(adapter, "provider_id", ""))
    supported = set(PROVIDER_CATALOG[provider]["capabilities"])
    capabilities = set(_capabilities(set(getattr(adapter, "capabilities", set()) or set())))
    if not capabilities:
        raise ValueError("Connector adapter 至少声明一个 capability")
    if not capabilities <= supported:
        raise ValueError(
            "Adapter 声明了 provider catalog 不允许的 capability: "
            + ", ".join(sorted(capabilities - supported))
        )
    try:
        health = _sanitize(dict(adapter.health(None) or {}))
    except Exception as exc:
        raise ValueError(_redact_secret_values(str(exc)) or "Connector adapter health check failed") from None
    if not bool(health.get("ok", False)):
        raise ValueError(_redact_secret_values(str(health.get("error") or "Connector adapter health check failed")))
    _ADAPTERS[provider] = adapter
    conversation_connectors.register_provider(
        provider,
        capabilities,
        health="AVAILABLE",
        account_label=str(health.get("label") or PROVIDER_CATALOG[provider]["label"])[:160],
    )


def unregister_adapter(provider_id: str) -> None:
    provider = _provider_id(provider_id)
    _ADAPTERS.pop(provider, None)
    conversation_connectors.unregister_provider(provider)


def clear_adapters_for_tests() -> None:
    for provider in list(_ADAPTERS):
        conversation_connectors.unregister_provider(provider)
    _ADAPTERS.clear()
    _ACTIVE_EXECUTIONS.clear()


def catalog() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for provider, spec in PROVIDER_CATALOG.items():
        rows.append({
            "provider_id": provider,
            "label": spec["label"],
            "capabilities": list(spec["capabilities"]),
            "read_capabilities": [
                cap for cap in spec["capabilities"]
                if cap in conversation_connectors.READ_CAPABILITIES
            ],
            "write_capabilities": [
                cap for cap in spec["capabilities"]
                if cap in conversation_connectors.WRITE_CAPABILITIES
            ],
            "external_kinds": list(spec["external_kinds"]),
            "provider_scopes": dict(spec["provider_scopes"]),
            "identity_scopes": list(spec.get("identity_scopes") or []),
            "sync": spec["sync"],
            "setup": dict(spec.get("setup") or {}),
            "adapter_available": provider in _ADAPTERS,
        })
    return rows


def _require_connection(connection_id: str) -> dict[str, Any]:
    row = store.get("conversation_connector_connection", connection_id)
    if not row:
        raise ValueError("Connector connection 不存在")
    return row


def create_connection(
    provider_id: str,
    *,
    display_name: str = "",
    granted_capabilities: Optional[list[str]] = None,
    provider_scopes: Optional[list[str]] = None,
    credential_ref: str = "",
    account_hint: str = "",
) -> dict[str, Any]:
    provider = _provider_id(provider_id)
    supported = set(PROVIDER_CATALOG[provider]["capabilities"])
    granted = set(_capabilities(granted_capabilities or []))
    if not granted:
        raise ValueError("Connector connection 至少需要一个 capability")
    if not granted <= supported:
        raise ValueError(
            "provider 不支持 capability: " + ", ".join(sorted(granted - supported))
        )
    credential_ref = _validate_credential_ref(credential_ref)
    validated_scopes = _validated_provider_scopes(provider, granted, provider_scopes)
    ts = store.now()
    row = {
        "id": store.new_id("ccn_"),
        "provider_id": provider,
        "display_name": _redact_secret_values(str(display_name or PROVIDER_CATALOG[provider]["label"]))[:200],
        "status": "DISCONNECTED",
        "auth_mode": "OPAQUE_REFERENCE" if credential_ref else "NONE",
        "credential_ref": credential_ref,
        "granted_capabilities": sorted(granted),
        "provider_scopes": validated_scopes,
        "account_hint": _redact_secret_values(str(account_hint or ""))[:300],
        "sync_cursor": "",
        "sync_cursors": {},
        "last_sync_at": None,
        "last_error": "",
        "created_at": ts,
        "updated_at": ts,
    }
    store.insert("conversation_connector_connection", row)
    return public_connection(_require_connection(row["id"]))


def public_connection(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if key != "credential_ref"
    } | {
        "credential_ref_present": bool(row.get("credential_ref")),
        "adapter_available": str(row.get("provider_id") or "") in _ADAPTERS,
    }


def list_connections() -> list[dict[str, Any]]:
    return [
        public_connection(row)
        for row in store.select("conversation_connector_connection", order="created_at ASC")
    ]


def verify_and_connect(connection_id: str) -> dict[str, Any]:
    row = _require_connection(connection_id)
    provider = str(row["provider_id"])
    adapter = _ADAPTERS.get(provider)
    if adapter is None:
        raise ValueError("Connector adapter 未接线，不能标记 CONNECTED")
    if not row.get("credential_ref"):
        raise ValueError("缺少 opaque credential_ref，不能标记 CONNECTED")
    granted = set(row.get("granted_capabilities") or [])
    if not granted <= set(getattr(adapter, "capabilities", set()) or set()):
        raise ValueError("Adapter 不满足 connection 已授权 capability")
    expected_scopes = _expected_provider_scopes(provider, granted)
    if sorted(row.get("provider_scopes") or []) != expected_scopes:
        raise ValueError("Connection provider scope 与最小 capability grant 不一致，拒绝 CONNECTED")
    try:
        health = _sanitize(dict(adapter.health(row) or {}))
    except Exception as exc:
        safe_error = _redact_secret_values(str(exc))[:2000] or "Connector health check failed"
        store.update("conversation_connector_connection", connection_id, {
            "status": "ERROR",
            "last_error": safe_error,
            "updated_at": store.now(),
        })
        raise ValueError(safe_error) from None
    if not bool(health.get("ok", False)):
        safe_error = _redact_secret_values(str(health.get("error") or "health check failed"))[:2000]
        store.update("conversation_connector_connection", connection_id, {
            "status": "ERROR",
            "last_error": safe_error,
            "updated_at": store.now(),
        })
        raise ValueError(safe_error)
    safe_account_hint = _redact_secret_values(str(health.get("account_hint") or row.get("account_hint") or ""))[:300]
    store.update("conversation_connector_connection", connection_id, {
        "status": "CONNECTED",
        "account_hint": safe_account_hint,
        "last_error": "",
        "updated_at": store.now(),
    })
    return public_connection(_require_connection(connection_id))


def disconnect(connection_id: str) -> dict[str, Any]:
    with _EXECUTION_LOCK:
        _require_connection(connection_id)
        store.update("conversation_connector_connection", connection_id, {
            "status": "DISCONNECTED",
            "updated_at": store.now(),
        })
        return public_connection(_require_connection(connection_id))


def revoke(connection_id: str) -> dict[str, Any]:
    with _EXECUTION_LOCK:
        _require_connection(connection_id)
        store.update("conversation_connector_connection", connection_id, {
            "status": "REVOKED",
            "auth_mode": "NONE",
            "credential_ref": "",
            "sync_cursor": "",
            "sync_cursors": {},
            "last_error": "",
            "updated_at": store.now(),
        })
        return public_connection(_require_connection(connection_id))


def _connection_usable(row: dict[str, Any], capability: str = "") -> bool:
    provider = str(row.get("provider_id") or "")
    adapter = _ADAPTERS.get(provider)
    if row.get("status") != "CONNECTED" or adapter is None:
        return False
    if capability and capability not in set(row.get("granted_capabilities") or []):
        return False
    if capability and capability not in set(getattr(adapter, "capabilities", set()) or set()):
        return False
    try:
        health = dict(adapter.health(row) or {})
    except Exception:
        return False
    return bool(health.get("ok", False))


def resolve_session_permissions(requested: list[str]) -> dict[str, Any]:
    requested_caps = _capabilities(requested)
    # Session Pack permissions are read-only. Writes have their own reviewed
    # execution path and are never silently inherited from a read permission.
    write_requested = [cap for cap in requested_caps if cap in conversation_connectors.WRITE_CAPABILITIES]
    grants: list[dict[str, Any]] = []
    blocked: list[dict[str, str]] = []
    connections = store.select("conversation_connector_connection", order="created_at ASC")

    for capability in requested_caps:
        if capability in write_requested:
            blocked.append({
                "capability": capability,
                "reason": "WRITE_REQUIRES_EXPLICIT_EXECUTION_FLOW",
            })
            continue
        match = next(
            (row for row in connections if _connection_usable(row, capability)),
            None,
        )
        if match is None:
            blocked.append({"capability": capability, "reason": "NO_CONNECTED_ACCOUNT"})
            continue
        grants.append({
            "capability": capability,
            "provider_id": match["provider_id"],
            "connection_id": match["id"],
            "account_hint": match.get("account_hint") or "",
        })
    return {
        "requested": requested_caps,
        "grants": grants,
        "blocked": blocked,
        "ok": not blocked,
        "providers": conversation_connectors.providers(),
        "write_execution_allowed": False,
    }


def _snapshot_hash(item: dict[str, Any]) -> str:
    """Canonical Chengzhu hash for one normalized external snapshot.

    Provider-supplied hashes are metadata only. Provenance identity is derived
    from the exact normalized fields Chengzhu freezes, including visibility and
    the query-stripped source URL.
    """
    raw = json.dumps({
        "capability": item.get("capability") or "",
        "external_kind": item.get("external_kind") or "",
        "external_id": item.get("external_id") or "",
        "title": item.get("title") or "",
        "excerpt": item.get("excerpt") or "",
        "source_url": item.get("source_url") or "",
        "occurred_at": item.get("occurred_at"),
        "visibility": item.get("visibility") or "PRIVATE",
        "metadata": item.get("metadata") or {},
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _store_snapshot(
    connection: dict[str, Any],
    space_id: str,
    capability: str,
    raw: dict[str, Any],
) -> dict[str, Any]:
    kind = str(raw.get("external_kind") or "").upper()
    if kind not in set(PROVIDER_CATALOG[connection["provider_id"]]["external_kinds"]):
        raise ValueError(f"{connection['provider_id']} 不能提供 {kind or '空'} snapshot")
    external_id = _redact_secret_values(str(raw.get("external_id") or raw.get("id") or "").strip())[:500]
    if not external_id:
        raise ValueError("Connector snapshot 缺少 external_id")
    canonical_metadata = _sanitize(dict(raw.get("metadata") or {}))
    normalized = {
        "capability": capability,
        "external_kind": kind,
        "external_id": external_id,
        "title": _redact_secret_values(str(raw.get("title") or ""))[:500],
        "excerpt": _redact_secret_values(str(raw.get("excerpt") or raw.get("text") or ""))[:20_000],
        "source_url": _safe_url(str(raw.get("source_url") or "")),
        "occurred_at": raw.get("occurred_at"),
        "visibility": str(raw.get("visibility") or "PRIVATE").upper()[:80],
        "metadata": canonical_metadata,
    }
    # Provider hashes are retained only as provenance metadata. They do not
    # control Chengzhu's immutable identity and therefore are not hash inputs.
    content_hash = _snapshot_hash(normalized)
    stored_metadata = dict(canonical_metadata)
    provider_content_hash = _redact_secret_values(str(raw.get("content_hash") or "").strip())
    if provider_content_hash:
        stored_metadata["provider_content_hash"] = provider_content_hash[:500]
    existing = store.rows(
        "SELECT * FROM conversation_connector_snapshot "
        "WHERE space_id = ? AND connection_id = ? AND capability = ? AND external_kind = ? "
        "AND external_id = ? AND content_hash = ? LIMIT 1",
        (space_id, connection["id"], capability, kind, external_id, content_hash),
    )
    if existing:
        return existing[0]
    row = {
        "id": store.new_id("ccs_"),
        "connection_id": connection["id"],
        "space_id": space_id,
        **normalized,
        "metadata": stored_metadata,
        "content_hash": content_hash,
        "source_url": normalized["source_url"],
        "visibility": normalized["visibility"],
        "created_at": store.now(),
    }
    store.insert("conversation_connector_snapshot", row)
    return store.get("conversation_connector_snapshot", row["id"]) or row


def sync_connection(
    connection_id: str,
    space_id: str,
    *,
    capabilities: Optional[list[str]] = None,
    query: Optional[dict[str, Any]] = None,
    limit: int = 100,
) -> dict[str, Any]:
    # Delayed import avoids service import cycles.
    from services.product import conversations

    conversations.require_space(space_id)
    connection = _require_connection(connection_id)
    provider = str(connection["provider_id"])
    adapter = _ADAPTERS.get(provider)
    if adapter is None or connection.get("status") != "CONNECTED":
        raise ValueError("Connector 未连接或 adapter 不可用")
    try:
        health = _sanitize(dict(adapter.health(connection) or {}))
    except Exception as exc:
        safe_error = _redact_secret_values(str(exc))[:2000] or "Connector health check failed"
        store.update("conversation_connector_connection", connection_id, {
            "status": "ERROR",
            "last_error": safe_error,
            "updated_at": store.now(),
        })
        raise ValueError(safe_error) from None
    if not bool(health.get("ok", False)):
        safe_error = _redact_secret_values(str(health.get("error") or "health check failed"))[:2000]
        store.update("conversation_connector_connection", connection_id, {
            "status": "ERROR",
            "last_error": safe_error,
            "updated_at": store.now(),
        })
        raise ValueError(safe_error)

    requested = _capabilities(capabilities or list(connection.get("granted_capabilities") or []))
    requested = [cap for cap in requested if cap in conversation_connectors.READ_CAPABILITIES]
    allowed = set(connection.get("granted_capabilities") or [])
    requested = [cap for cap in requested if cap in allowed]
    if not requested:
        raise ValueError("Connector 没有可同步的 read capability")

    cursors = dict(connection.get("sync_cursors") or {})
    # v8 compatibility: if exactly one capability is requested and no
    # capability cursor exists yet, seed it from the legacy scalar cursor.
    legacy_cursor = str(connection.get("sync_cursor") or "")
    snapshots: list[dict[str, Any]] = []
    try:
        for capability in requested:
            cursor = str(cursors.get(capability) or (legacy_cursor if len(requested) == 1 else ""))
            effective_limit = 500 if (
                (provider == "GOOGLE_CALENDAR" and capability == "calendar.read")
                or (provider == "GOOGLE_DRIVE" and capability == "docs.read")
            ) else max(1, min(int(limit), 500))
            result = adapter.read_context(
                connection=connection,
                capability=capability,
                query=dict(query or {}),
                cursor=cursor,
                limit=effective_limit,
            ) or {}
            if bool(result.get("full_sync_required")):
                # Native provider sync tokens (e.g. Google Calendar) can be
                # invalidated. Reset only this capability cursor, then perform
                # one explicit full resync. Immutable historical snapshots are
                # provenance/audit records rather than a mutable provider
                # mirror, so they are not erased here.
                cursors[capability] = ""
                result = adapter.read_context(
                    connection=connection,
                    capability=capability,
                    query=dict(query or {}),
                    cursor="",
                    limit=effective_limit,
                ) or {}
                if bool(result.get("full_sync_required")):
                    raise RuntimeError("Provider full sync reset did not converge")
            for raw in list(result.get("items") or [])[:effective_limit]:
                snapshots.append(_store_snapshot(connection, space_id, capability, dict(raw or {})))
            if result.get("next_cursor") is not None:
                cursors[capability] = str(result.get("next_cursor") or "")[:4000]
        store.update("conversation_connector_connection", connection_id, {
            "sync_cursors": cursors,
            # Keep the scalar field readable for old beta tooling only when
            # the sync is unambiguously a single capability.
            "sync_cursor": str(cursors.get(requested[0]) or "") if len(requested) == 1 else "",
            "last_sync_at": store.now(),
            "last_error": "",
            "updated_at": store.now(),
        })
        return {"connection": public_connection(_require_connection(connection_id)), "snapshots": snapshots}
    except Exception as exc:
        safe_error = _redact_secret_values(str(exc))[:2000] or "Connector sync failed"
        # A concrete provider may know that the failure belongs to one target
        # repository/resource rather than to account authentication itself.
        # Keep that account CONNECTED while recording the target failure.
        connection_fatal = bool(getattr(exc, "connection_fatal", True))
        store.update("conversation_connector_connection", connection_id, {
            "status": "ERROR" if connection_fatal else str(connection.get("status") or "CONNECTED"),
            "last_error": safe_error,
            "updated_at": store.now(),
        })
        raise ValueError(safe_error) from None


def _snapshot_revision_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Annotate immutable provenance with current-provider revision truth.

    Historical snapshots remain readable/exportable. is_latest_revision
    answers whether this is the newest observed version of the same external
    object inside this Space/connection/capability.
    """
    rows = store.rows(
        "SELECT id FROM conversation_connector_snapshot "
        "WHERE space_id = ? AND connection_id = ? AND capability = ? "
        "AND external_kind = ? AND external_id = ? "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (
            snapshot.get("space_id"),
            snapshot.get("connection_id"),
            snapshot.get("capability"),
            snapshot.get("external_kind"),
            snapshot.get("external_id"),
        ),
    )
    latest_id = str(rows[0]["id"]) if rows else str(snapshot.get("id") or "")
    return {
        **snapshot,
        "is_latest_revision": str(snapshot.get("id") or "") == latest_id,
        "latest_snapshot_id": latest_id,
    }


def list_snapshots(space_id: str, *, connection_id: str = "", limit: int = 200) -> list[dict[str, Any]]:
    if connection_id:
        rows = store.select(
            "conversation_connector_snapshot",
            where="space_id = ? AND connection_id = ?",
            params=(space_id, connection_id),
            order="COALESCE(occurred_at, created_at) DESC",
            limit=max(1, min(int(limit), 1000)),
        )
    else:
        rows = store.select(
            "conversation_connector_snapshot",
            where="space_id = ?",
            params=(space_id,),
            order="COALESCE(occurred_at, created_at) DESC",
            limit=max(1, min(int(limit), 1000)),
        )
    return [_snapshot_revision_view(row) for row in rows]


def validate_snapshot_selection(space_id: str, snapshot_ids: list[str]) -> list[str]:
    """Return a stable deduplicated selection or fail on cross-Space provenance."""
    if not store.get("conversation_space", space_id):
        raise ValueError("对话空间不存在")
    selected: list[str] = []
    seen: set[str] = set()
    for raw_id in snapshot_ids:
        snapshot_id = str(raw_id or "").strip()
        if not snapshot_id or snapshot_id in seen:
            continue
        snapshot = store.get("conversation_connector_snapshot", snapshot_id)
        if not snapshot:
            raise ValueError(f"Connector Snapshot 不存在：{snapshot_id}")
        if str(snapshot.get("space_id") or "") != space_id:
            raise ValueError(f"Connector Snapshot 不属于当前 Space：{snapshot_id}")
        seen.add(snapshot_id)
        selected.append(snapshot_id)
    return selected


def snapshot_source_ref(snapshot: dict[str, Any]) -> dict[str, Any]:
    connection = _require_connection(snapshot["connection_id"])
    return {
        "kind": "CONNECTOR_SNAPSHOT",
        "id": snapshot["id"],
        "provider_id": connection["provider_id"],
        "capability": snapshot["capability"],
        "external_kind": snapshot["external_kind"],
        "external_id": snapshot["external_id"],
        "content_hash": snapshot["content_hash"],
        "occurred_at": snapshot.get("occurred_at"),
        "visibility": snapshot.get("visibility") or "PRIVATE",
    }


def request_execution(
    draft_action_id: str,
    connection_id: str,
    *,
    target: str = "",
) -> dict[str, Any]:
    draft = store.get("conversation_draft_action", draft_action_id)
    if not draft:
        raise ValueError("DraftAction 不存在")
    if draft.get("status") != "APPROVED":
        raise ValueError("只有 APPROVED DraftAction 才能请求外部执行")
    mapping = DRAFT_CAPABILITY.get(str(draft.get("kind") or "").upper())
    if not mapping:
        raise ValueError("DraftAction 没有 external execution mapping")
    operation, capability = mapping

    session = store.get("conversation_session", str(draft.get("session_id") or ""))
    if not session:
        raise ValueError("DraftAction 对应 Session 不存在")
    if str((session.get("policy") or {}).get("external_writeback") or "REVIEW_REQUIRED") == "OFF":
        raise ValueError("本场 External Write-back 已关闭")

    connection = _require_connection(connection_id)
    status = "PENDING"
    error = ""
    if not _connection_usable(connection, capability):
        status = "BLOCKED"
        error = f"Connection 没有真实可用 capability: {capability}"

    target_value = str(target or draft.get("target") or "")[:1000]
    key_raw = "|".join([
        draft["id"],
        str(draft.get("updated_at") or ""),
        connection_id,
        capability,
        operation,
        target_value,
    ])
    idempotency_key = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()
    existing = store.rows(
        "SELECT * FROM conversation_connector_execution WHERE idempotency_key = ? LIMIT 1",
        (idempotency_key,),
    )
    if existing:
        return existing[0]

    raw_request = {
        "draft_kind": draft["kind"],
        "title": draft.get("title") or "",
        "content": draft.get("content") or "",
        "payload": draft.get("payload") or {},
        "source_refs": draft.get("source_refs") or [],
    }
    outbound_redaction_applied = _contains_secret_value(
        json.dumps(raw_request, ensure_ascii=False, sort_keys=True, default=str)
    )
    safe_request = _sanitize(raw_request)
    if isinstance(safe_request, dict):
        # This key intentionally avoids secret/token naming so the sanitizer
        # does not remove the audit marker itself.
        safe_request["outbound_redaction_applied"] = outbound_redaction_applied

    ts = store.now()
    row = {
        "id": store.new_id("cce_"),
        "draft_action_id": draft_action_id,
        "connection_id": connection_id,
        "capability": capability,
        "operation": operation,
        "target": target_value,
        "idempotency_key": idempotency_key,
        "status": status,
        "request": safe_request,
        "response": {},
        "error": error,
        "created_at": ts,
        "updated_at": ts,
        "executed_at": None,
    }
    store.insert("conversation_connector_execution", row)
    return store.get("conversation_connector_execution", row["id"]) or row


def _recover_orphaned_executions() -> int:
    """Convert persisted EXECUTING rows with no live in-process call to UNKNOWN."""
    with _EXECUTION_LOCK:
        recovered = 0
        for row in store.select(
            "conversation_connector_execution",
            where="status = 'EXECUTING'",
            order="updated_at ASC",
            limit=1000,
        ):
            execution_id = str(row.get("id") or "")
            if not execution_id or execution_id in _ACTIVE_EXECUTIONS:
                continue
            store.update("conversation_connector_execution", execution_id, {
                "status": "UNKNOWN_OUTCOME",
                "error": "Backend execution was interrupted; provider outcome must be reconciled before retry",
                "updated_at": store.now(),
            })
            recovered += 1
        return recovered


def _retry_history_for(row: dict[str, Any]) -> list[dict[str, Any]]:
    if row.get("status") != "FAILED":
        return []
    previous = dict(row.get("response") or {})
    history = list(previous.pop("retry_history", []) or [])
    history.append({
        "status": "FAILED",
        "response": previous,
        "error": str(row.get("error") or "")[:4000],
        "recorded_at": row.get("updated_at"),
    })
    return history[-20:]


def _with_retry_history(response: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return response
    return {**response, "retry_history": history}


def execute_request(execution_id: str) -> dict[str, Any]:
    # Keep the state claim, final capability check, provider side effect and
    # persisted outcome in one ordering boundary. Revoke/disconnect uses the
    # same lock, so no new provider call can begin after revocation wins.
    with _EXECUTION_LOCK:
        row = store.get("conversation_connector_execution", execution_id)
        if not row:
            raise ValueError("External execution request 不存在")
        if row["status"] == "EXECUTING":
            if execution_id in _ACTIVE_EXECUTIONS:
                raise ValueError("External execution request 正在当前进程执行")
            store.update("conversation_connector_execution", execution_id, {
                "status": "UNKNOWN_OUTCOME",
                "error": "Backend execution was interrupted; provider outcome must be reconciled before retry",
                "updated_at": store.now(),
            })
            row = store.get("conversation_connector_execution", execution_id) or row
        if row["status"] == "SUCCEEDED":
            return row
        if row["status"] == "BLOCKED":
            raise ValueError(row.get("error") or "External execution request 已阻断")
        if row["status"] == "UNKNOWN_OUTCOME":
            raise ValueError("External execution outcome 不确定；必须先在 provider 侧核对并记录 reconciliation，禁止直接重试")
        if row["status"] == "FAILED":
            prior_response = dict(row.get("response") or {})
            if prior_response.get("retry_safe") is not True:
                raise ValueError("上次 provider 明确失败但未声明 retry_safe；禁止直接重试")
        elif row["status"] != "PENDING":
            raise ValueError("External execution request 当前状态不能执行")
        retry_history = _retry_history_for(row)

        draft = store.get("conversation_draft_action", row["draft_action_id"])
        if not draft or draft.get("status") != "APPROVED":
            store.update("conversation_connector_execution", execution_id, {
                "status": "BLOCKED",
                "error": "DraftAction 不再是 APPROVED",
                "updated_at": store.now(),
            })
            raise ValueError("DraftAction 不再是 APPROVED")

        connection = _require_connection(row["connection_id"])
        capability = str(row.get("capability") or "")
        if not _connection_usable(connection, capability):
            store.update("conversation_connector_execution", execution_id, {
                "status": "BLOCKED",
                "error": f"Connection 不再具备 {capability}",
                "updated_at": store.now(),
            })
            raise ValueError(f"Connection 不再具备 {capability}")

        adapter = _ADAPTERS[str(connection["provider_id"])]
        _ACTIVE_EXECUTIONS.add(execution_id)
        store.update("conversation_connector_execution", execution_id, {
            "status": "EXECUTING",
            "error": "",
            "updated_at": store.now(),
        })
        try:
            try:
                raw_result = adapter.execute(
                    connection=connection,
                    capability=capability,
                    operation=str(row.get("operation") or ""),
                    target=str(row.get("target") or ""),
                    payload=dict(row.get("request") or {}),
                    idempotency_key=str(row.get("idempotency_key") or ""),
                )
                result = _sanitize(dict(raw_result or {}))
            except Exception as exc:
                store.update("conversation_connector_execution", execution_id, {
                    "status": "UNKNOWN_OUTCOME",
                    "response": _with_retry_history({}, retry_history),
                    "error": _redact_secret_values(str(exc))[:4000],
                    "updated_at": store.now(),
                })
                return store.get("conversation_connector_execution", execution_id) or row

            if not isinstance(result.get("ok"), bool):
                store.update("conversation_connector_execution", execution_id, {
                    "status": "UNKNOWN_OUTCOME",
                    "response": _with_retry_history(result, retry_history),
                    "error": "Provider 未返回显式 boolean ok；无法确认外部副作用是否发生",
                    "updated_at": store.now(),
                })
                return store.get("conversation_connector_execution", execution_id) or row

            if result["ok"] is False:
                store.update("conversation_connector_execution", execution_id, {
                    "status": "FAILED",
                    "response": _with_retry_history(result, retry_history),
                    "error": str(result.get("error") or "Provider 明确返回失败")[:4000],
                    "updated_at": store.now(),
                })
                return store.get("conversation_connector_execution", execution_id) or row

            store.update("conversation_connector_execution", execution_id, {
                "status": "SUCCEEDED",
                "response": _with_retry_history(result, retry_history),
                "error": "",
                "updated_at": store.now(),
                "executed_at": store.now(),
            })
            return store.get("conversation_connector_execution", execution_id) or row
        finally:
            _ACTIVE_EXECUTIONS.discard(execution_id)


def reconcile_unknown_outcome(
    execution_id: str,
    outcome: str,
    *,
    note: str,
    provider_reference: str = "",
) -> dict[str, Any]:
    """Record a human/provider-side reconciliation for UNKNOWN_OUTCOME.

    This never guesses the provider state. The user must first verify the
    outcome in the provider and leave an audit note.
    """
    outcome = str(outcome or "").upper()
    if outcome not in {"CONFIRMED_SUCCEEDED", "CONFIRMED_NOT_APPLIED"}:
        raise ValueError("reconciliation 只支持 CONFIRMED_SUCCEEDED / CONFIRMED_NOT_APPLIED")
    note = str(note or "").strip()
    if not note:
        raise ValueError("reconciliation 必须记录 provider-side 核对说明")
    note = _redact_secret_values(note)[:4000]
    provider_reference = _redact_secret_values(str(provider_reference or ""))[:1000]

    with _EXECUTION_LOCK:
        row = store.get("conversation_connector_execution", execution_id)
        if not row:
            raise ValueError("External execution request 不存在")
        if row.get("status") != "UNKNOWN_OUTCOME":
            raise ValueError("只有 UNKNOWN_OUTCOME 才能记录 reconciliation")

        previous = dict(row.get("response") or {})
        audit = {
            "outcome": outcome,
            "provider_reference": provider_reference,
            "note": note,
            "recorded_at": store.now(),
            "source": "USER_REPORTED_PROVIDER_CHECK",
        }
        if outcome == "CONFIRMED_SUCCEEDED":
            status = "SUCCEEDED"
            # Do not synthesize provider `ok=true`: this success was established
            # by an explicit user-reported provider-side check, not by the
            # original adapter response. The real execution timestamp is
            # unknown, so executed_at deliberately remains unset.
            response = {**previous, "reconciliation": audit}
            error = ""
            executed_at = None
        else:
            status = "FAILED"
            # A provider-side check explicitly confirmed no side effect. This
            # is the only reconciliation path that can make a retry safe.
            response = {**previous, "retry_safe": True, "reconciliation": audit}
            error = "Provider-side reconciliation confirmed the side effect was not applied"
            executed_at = None

        store.update("conversation_connector_execution", execution_id, {
            "status": status,
            "response": response,
            "error": error,
            "updated_at": store.now(),
            "executed_at": executed_at,
        })
        return store.get("conversation_connector_execution", execution_id) or row

def list_executions(*, draft_action_id: str = "", limit: int = 200) -> list[dict[str, Any]]:
    _recover_orphaned_executions()
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
        limit=max(1, min(int(limit), 1000)),
    )


def diagnostics() -> dict[str, Any]:
    recovered_orphans = _recover_orphaned_executions()
    connections = list_connections()
    connected = [row for row in connections if row["status"] == "CONNECTED" and row["adapter_available"]]
    return {
        "catalog": catalog(),
        "connections": connections,
        "connected_count": len(connected),
        "registered_adapters": sorted(_ADAPTERS),
        "snapshot_count": int(store.scalar("SELECT COUNT(*) FROM conversation_connector_snapshot") or 0),
        "execution_count": int(store.scalar("SELECT COUNT(*) FROM conversation_connector_execution") or 0),
        "external_execution": "REVIEW_SECOND_EXECUTE_WITH_AMBIGUOUS_OUTCOME_GUARD",
        "unknown_outcome_count": int(store.scalar(
            "SELECT COUNT(*) FROM conversation_connector_execution WHERE status = 'UNKNOWN_OUTCOME'"
        ) or 0),
        "orphaned_executions_recovered": recovered_orphans,
        "secret_storage": "OPAQUE_REFERENCE_ONLY",
        "default": "PROVIDERS_REQUIRE_EXPLICIT_CONNECTION" if _ADAPTERS else "NO_PROVIDER_ADAPTERS_CONFIGURED",
    }
