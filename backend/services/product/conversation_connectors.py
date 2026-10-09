"""Fail-closed Conversation connector capability registry.

This module defines *capability truth*, not provider integrations.

A provider is considered usable only after runtime code explicitly registers
that provider with the exact capabilities it can satisfy.  The default
registry is empty, so Conversation Preflight remains fail-closed until a real
connector is present.

No credentials, OAuth tokens, refresh tokens, message bodies or external
identifiers are stored here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


READ_CAPABILITIES = frozenset({
    "calendar.read",
    "docs.read",
    "mail.read",
    "project.read",
})

WRITE_CAPABILITIES = frozenset({
    "email.send",
    "task.create",
    "issue.create",
    "decision_log.write",
})

KNOWN_CAPABILITIES = READ_CAPABILITIES | WRITE_CAPABILITIES


@dataclass(frozen=True)
class ConnectorProvider:
    provider_id: str
    capabilities: frozenset[str]
    health: str = "AVAILABLE"
    account_label: str = ""


_registry: dict[str, ConnectorProvider] = {}


def clear_registry() -> None:
    """Clear process-local provider registrations.

    Production startup begins empty unless a real connector integration
    registers itself.  Tests may use this helper to prove fail-closed behavior.
    """
    _registry.clear()


def register_provider(
    provider_id: str,
    capabilities: Iterable[str],
    *,
    health: str = "AVAILABLE",
    account_label: str = "",
) -> ConnectorProvider:
    pid = str(provider_id or "").strip()
    if not pid:
        raise ValueError("connector provider_id 不能为空")
    caps = frozenset(str(x or "").strip() for x in capabilities if str(x or "").strip())
    unknown = sorted(caps - KNOWN_CAPABILITIES)
    if unknown:
        raise ValueError(f"connector capability 不支持: {', '.join(unknown)}")
    provider = ConnectorProvider(
        provider_id=pid,
        capabilities=caps,
        health=str(health or "UNKNOWN").upper(),
        account_label=str(account_label or "")[:160],
    )
    _registry[pid] = provider
    return provider


def unregister_provider(provider_id: str) -> None:
    _registry.pop(str(provider_id or "").strip(), None)


def providers() -> list[dict]:
    return [
        {
            "provider_id": provider.provider_id,
            "capabilities": sorted(provider.capabilities),
            "health": provider.health,
            "account_label": provider.account_label,
        }
        for provider in sorted(_registry.values(), key=lambda p: p.provider_id)
    ]


def resolve_permissions(
    requested: Iterable[str],
    *,
    allow_write: bool = False,
) -> dict:
    requested_caps = list(dict.fromkeys(
        str(x or "").strip() for x in requested if str(x or "").strip()
    ))
    unknown = sorted({cap for cap in requested_caps if cap not in KNOWN_CAPABILITIES})
    write_requested = sorted({cap for cap in requested_caps if cap in WRITE_CAPABILITIES})
    blocked_write = write_requested if not allow_write else []

    grants: list[dict] = []
    blocked: list[dict] = []
    for cap in requested_caps:
        if cap in unknown:
            blocked.append({"capability": cap, "reason": "UNKNOWN_CAPABILITY"})
            continue
        if cap in blocked_write:
            blocked.append({"capability": cap, "reason": "WRITE_REQUIRES_EXPLICIT_EXECUTION_FLOW"})
            continue
        candidates = [
            p for p in _registry.values()
            if cap in p.capabilities and p.health == "AVAILABLE"
        ]
        if not candidates:
            blocked.append({"capability": cap, "reason": "NO_AVAILABLE_PROVIDER"})
            continue
        provider = sorted(candidates, key=lambda p: p.provider_id)[0]
        grants.append({
            "capability": cap,
            "provider_id": provider.provider_id,
            "account_label": provider.account_label,
        })

    relevant_provider_ids = {
        provider.provider_id
        for provider in _registry.values()
        if any(cap in provider.capabilities for cap in requested_caps)
    }
    provider_rows = [
        row for row in providers()
        if row["provider_id"] in relevant_provider_ids
    ]
    return {
        "requested": requested_caps,
        "grants": grants,
        "blocked": blocked,
        "ok": not blocked,
        "providers": provider_rows,
        "write_execution_allowed": bool(allow_write),
    }


def resolve_read_permissions(requested: Iterable[str]) -> dict:
    """Resolve Session connector permissions.

    Session Policy connector_permissions is read-only in v2.  Any write
    capability must use the separate reviewed DraftAction execution path.
    """
    return resolve_permissions(requested, allow_write=False)


def diagnostics() -> dict:
    provider_rows = providers()
    available_caps = sorted({
        cap
        for provider in _registry.values()
        if provider.health == "AVAILABLE"
        for cap in provider.capabilities
    })
    return {
        "provider_count": len(provider_rows),
        "providers": provider_rows,
        "available_capabilities": available_caps,
        "read_capabilities": sorted(READ_CAPABILITIES),
        "write_capabilities": sorted(WRITE_CAPABILITIES),
        "default": "FAIL_CLOSED_EMPTY_REGISTRY",
    }
