import json

import pytest

from services.product import conversation_integrations, conversations
from services.product.mcp_decision_log_connector import (
    McpDecisionLogAdapter,
    McpProviderError,
    register_mcp_decision_log_adapter_from_env,
)


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.responses = []

    def queue(self, status, payload, headers=None):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.responses.append((status, headers or {"Content-Type": "application/json"}, body))

    def queue_error(self, exc):
        self.responses.append(exc)

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({
            "method": method,
            "url": url,
            "headers": dict(headers),
            "body": json.loads(body.decode("utf-8")),
            "timeout": timeout,
        })
        if not self.responses:
            raise AssertionError(f"Unexpected MCP request: {method} {url}")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _discover():
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "resultType": "complete",
            "supportedVersions": ["2026-07-28"],
            "capabilities": {"tools": {}},
            "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "work-mcp", "version": "1"}},
        },
    }


def _tool_schema(name="chengzhu_update_decision_log"):
    return {
        "name": name,
        "description": "Write a reviewed Chengzhu decision log entry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "target": {"type": "string"},
                "idempotency_key": {"type": "string"},
            },
            "required": ["title", "content", "target", "idempotency_key"],
            "additionalProperties": False,
        },
    }


def _tools(tool=None):
    return {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "resultType": "complete",
            "tools": [tool or _tool_schema()],
        },
    }


def _tool_success():
    return {
        "jsonrpc": "2.0",
        "id": 3,
        "result": {
            "resultType": "complete",
            "content": [{"type": "text", "text": "updated"}],
            "isError": False,
        },
    }


def _connection(ref="provider:mcp:env:CHENGZHU_MCP_DECISION_LOG_CONFIG"):
    return {
        "id": "ccn_mcp_test",
        "provider_id": "MCP",
        "credential_ref": ref,
        "granted_capabilities": ["decision_log.write"],
        "provider_scopes": ["server-defined"],
        "status": "CONNECTED",
        "account_hint": "work-mcp",
    }


@pytest.fixture(autouse=True)
def _clean_adapters():
    conversation_integrations.clear_adapters_for_tests()
    yield
    conversation_integrations.clear_adapters_for_tests()


@pytest.fixture
def mcp_env(monkeypatch):
    monkeypatch.setenv(
        "CHENGZHU_MCP_DECISION_LOG_CONFIG",
        json.dumps({
            "endpoint": "https://mcp.example.test/mcp",
            "tool_name": "chengzhu_update_decision_log",
            "bearer_token_env": "CHENGZHU_MCP_BEARER_TOKEN",
            "account_hint": "work-mcp",
        }),
    )
    monkeypatch.setenv("CHENGZHU_MCP_BEARER_TOKEN", "mcp-secret-token")


def test_mcp_endpoint_requires_https_except_loopback(monkeypatch):
    adapter = McpDecisionLogAdapter(transport=FakeTransport())
    monkeypatch.setenv(
        "MCP_BAD",
        json.dumps({
            "endpoint": "http://mcp.example.test/mcp",
            "tool_name": "chengzhu_update_decision_log",
        }),
    )
    bad = adapter.health({**_connection(), "credential_ref": "provider:mcp:env:MCP_BAD"})
    assert bad["ok"] is False
    assert "HTTPS" in bad["error"]

    monkeypatch.setenv(
        "MCP_LOCAL",
        json.dumps({
            "endpoint": "http://127.0.0.1:8765/mcp",
            "tool_name": "chengzhu_update_decision_log",
        }),
    )
    transport = FakeTransport()
    transport.queue(200, _discover())
    transport.queue(200, _tools())
    local = McpDecisionLogAdapter(transport=transport)
    assert local.health({**_connection(), "credential_ref": "provider:mcp:env:MCP_LOCAL"})["ok"] is True


def test_mcp_config_rejects_inline_secret(monkeypatch):
    adapter = McpDecisionLogAdapter(transport=FakeTransport())
    monkeypatch.setenv(
        "MCP_INLINE_SECRET",
        json.dumps({
            "endpoint": "https://mcp.example.test/mcp",
            "tool_name": "chengzhu_update_decision_log",
            "bearer_token": "do-not-store-here",
        }),
    )
    health = adapter.health({
        **_connection(),
        "credential_ref": "provider:mcp:env:MCP_INLINE_SECRET",
    })
    assert health["ok"] is False
    assert "不允许内嵌" in health["error"]


def test_mcp_health_discovers_exact_tool_schema_with_modern_headers(mcp_env):
    transport = FakeTransport()
    transport.queue(200, _discover())
    transport.queue(200, _tools())
    adapter = McpDecisionLogAdapter(transport=transport)

    health = adapter.health(_connection())
    assert health["ok"] is True
    assert health["verify"] == "SERVER_DISCOVER_PLUS_EXACT_TOOL_SCHEMA"
    assert health["protocol"] == "2026-07-28"
    assert health["tool_name"] == "chengzhu_update_decision_log"
    assert health["account_hint"] == "work-mcp"

    discover_call, list_call = transport.calls
    assert discover_call["headers"]["MCP-Protocol-Version"] == "2026-07-28"
    assert discover_call["headers"]["Mcp-Method"] == "server/discover"
    assert "Mcp-Name" not in discover_call["headers"]
    assert discover_call["headers"]["Authorization"] == "Bearer mcp-secret-token"
    assert discover_call["body"]["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"] == "2026-07-28"
    assert list_call["headers"]["Mcp-Method"] == "tools/list"


def test_mcp_health_fails_closed_when_exact_tool_or_schema_is_missing(mcp_env):
    missing = FakeTransport()
    missing.queue(200, _discover())
    missing.queue(200, {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {"resultType": "complete", "tools": [_tool_schema("some_other_tool")]},
    })
    health = McpDecisionLogAdapter(transport=missing).health(_connection())
    assert health["ok"] is False
    assert "未暴露配置" in health["error"]

    bad_schema = _tool_schema()
    del bad_schema["inputSchema"]["properties"]["idempotency_key"]
    invalid = FakeTransport()
    invalid.queue(200, _discover())
    invalid.queue(200, _tools(bad_schema))
    health = McpDecisionLogAdapter(transport=invalid).health(_connection())
    assert health["ok"] is False
    assert "canonical string field" in health["error"]


def test_mcp_execute_uses_only_configured_tool_and_reviewed_canonical_arguments(mcp_env):
    transport = FakeTransport()
    # Execute performs a fresh discover + tools/list pre-write check.
    transport.queue(200, _discover())
    transport.queue(200, _tools())
    transport.queue(200, _tool_success())
    adapter = McpDecisionLogAdapter(transport=transport)

    result = adapter.execute(
        connection=_connection(),
        capability="decision_log.write",
        operation="UPDATE_DECISION_LOG",
        target="architecture-decisions",
        payload={
            "title": "Architecture Review · Decision Log Draft",
            "content": "- offline migration 采用 v2 · state=AGREED",
            "outbound_redaction_applied": False,
        },
        idempotency_key="decision-log-idempotency-123",
    )

    assert result["ok"] is True
    assert result["provider_id"] == "MCP"
    assert result["tool_name"] == "chengzhu_update_decision_log"
    assert result["target"] == "architecture-decisions"
    assert result["provider_idempotency"] == "UNVERIFIED_APPLICATION_ARGUMENT"

    call = transport.calls[-1]
    assert call["headers"]["Mcp-Method"] == "tools/call"
    assert call["headers"]["Mcp-Name"] == "chengzhu_update_decision_log"
    assert call["body"]["params"]["name"] == "chengzhu_update_decision_log"
    assert call["body"]["params"]["arguments"] == {
        "title": "Architecture Review · Decision Log Draft",
        "content": "- offline migration 采用 v2 · state=AGREED",
        "target": "architecture-decisions",
        "idempotency_key": "decision-log-idempotency-123",
    }


def test_mcp_rejects_redacted_payload_empty_target_and_silent_truncation(mcp_env):
    adapter = McpDecisionLogAdapter(transport=FakeTransport())

    redacted = adapter.execute(
        connection=_connection(),
        capability="decision_log.write",
        operation="UPDATE_DECISION_LOG",
        target="log",
        payload={
            "title": "Decision",
            "content": "redacted",
            "outbound_redaction_applied": True,
        },
        idempotency_key="a",
    )
    assert redacted["ok"] is False
    assert "重新审核" in redacted["error"]

    no_target = adapter.execute(
        connection=_connection(),
        capability="decision_log.write",
        operation="UPDATE_DECISION_LOG",
        target="",
        payload={
            "title": "Decision",
            "content": "body",
            "outbound_redaction_applied": False,
        },
        idempotency_key="b",
    )
    assert no_target["ok"] is False
    assert no_target["retry_safe"] is False
    assert no_target["phase"] == "MCP_PREFLIGHT_PRE_WRITE"

    long_title = adapter.execute(
        connection=_connection(),
        capability="decision_log.write",
        operation="UPDATE_DECISION_LOG",
        target="log",
        payload={
            "title": "x" * 501,
            "content": "body",
            "outbound_redaction_applied": False,
        },
        idempotency_key="c",
    )
    assert long_title["ok"] is False
    assert "不会静默截断" in long_title["error"]


def test_mcp_prewrite_failure_is_retry_safe_but_tool_call_transport_is_ambiguous(mcp_env):
    prewrite = FakeTransport()
    prewrite.queue_error(McpProviderError(503, "MCP HTTP 503"))
    result = McpDecisionLogAdapter(transport=prewrite).execute(
        connection=_connection(),
        capability="decision_log.write",
        operation="UPDATE_DECISION_LOG",
        target="decision-log",
        payload={
            "title": "Decision",
            "content": "body",
            "outbound_redaction_applied": False,
        },
        idempotency_key="prewrite",
    )
    assert result["ok"] is False
    assert result["retry_safe"] is True
    assert result["phase"] == "MCP_PREFLIGHT_PRE_WRITE"
    assert len(prewrite.calls) == 1

    postwrite = FakeTransport()
    postwrite.queue(200, _discover())
    postwrite.queue(200, _tools())
    postwrite.queue_error(RuntimeError("connection closed after tools/call write"))
    adapter = McpDecisionLogAdapter(transport=postwrite)
    with pytest.raises(RuntimeError, match="connection closed"):
        adapter.execute(
            connection=_connection(),
            capability="decision_log.write",
            operation="UPDATE_DECISION_LOG",
            target="decision-log",
            payload={
                "title": "Decision",
                "content": "body",
                "outbound_redaction_applied": False,
            },
            idempotency_key="ambiguous",
        )
    assert transport_call_method(postwrite.calls[-1]) == "tools/call"


def transport_call_method(call):
    return call["body"]["method"]


def test_mcp_iserror_is_definitive_failure_and_nonfinal_result_is_ambiguous(mcp_env):
    failed = FakeTransport()
    failed.queue(200, _discover())
    failed.queue(200, _tools())
    failed.queue(200, {
        "jsonrpc": "2.0",
        "id": 3,
        "result": {
            "resultType": "complete",
            "isError": True,
            "content": [{"type": "text", "text": "rejected"}],
        },
    })
    result = McpDecisionLogAdapter(transport=failed).execute(
        connection=_connection(),
        capability="decision_log.write",
        operation="UPDATE_DECISION_LOG",
        target="log",
        payload={
            "title": "Decision",
            "content": "body",
            "outbound_redaction_applied": False,
        },
        idempotency_key="iserror",
    )
    assert result["ok"] is False
    assert result["retry_safe"] is False

    nonfinal = FakeTransport()
    nonfinal.queue(200, _discover())
    nonfinal.queue(200, _tools())
    nonfinal.queue(200, {
        "jsonrpc": "2.0",
        "id": 3,
        "result": {
            "resultType": "input_required",
            "inputRequests": {},
        },
    })
    with pytest.raises(RuntimeError, match="non-final"):
        McpDecisionLogAdapter(transport=nonfinal).execute(
            connection=_connection(),
            capability="decision_log.write",
            operation="UPDATE_DECISION_LOG",
            target="log",
            payload={
                "title": "Decision",
                "content": "body",
                "outbound_redaction_applied": False,
            },
            idempotency_key="mrtr",
        )


def test_mcp_registration_is_explicit_opt_in(product_env, monkeypatch):
    monkeypatch.delenv("CHENGZHU_MCP_DECISION_LOG_CONNECTOR_ENABLE", raising=False)
    assert register_mcp_decision_log_adapter_from_env()["registered"] is False
    mcp = next(item for item in conversation_integrations.catalog() if item["provider_id"] == "MCP")
    assert mcp["adapter_available"] is False

    monkeypatch.setenv("CHENGZHU_MCP_DECISION_LOG_CONNECTOR_ENABLE", "1")
    registered = register_mcp_decision_log_adapter_from_env()
    assert registered["registered"] is True
    assert registered["capabilities"] == ["decision_log.write"]
    assert registered["protocol"] == "2026-07-28"


def test_real_mcp_adapter_runs_through_reviewed_two_step_boundary(product_env, monkeypatch, mcp_env):
    transport = FakeTransport()
    adapter = McpDecisionLogAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    # Verify the exact server + tool schema before marking CONNECTED.
    transport.queue(200, _discover())
    transport.queue(200, _tools())
    connection = conversation_integrations.create_connection(
        "MCP",
        display_name="Work MCP · Decision Log",
        granted_capabilities=["decision_log.write"],
        provider_scopes=["server-defined"],
        credential_ref="provider:mcp:env:CHENGZHU_MCP_DECISION_LOG_CONFIG",
    )
    connected = conversation_integrations.verify_and_connect(connection["id"])
    assert connected["status"] == "CONNECTED"
    assert connected["account_hint"] == "work-mcp"

    space = conversations.create_space("Architecture", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    conversations.end_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"],
        kind="UPDATE_DECISION_LOG_DRAFT",
        title="Architecture Review · Decision Log Draft",
        content="- offline migration 采用 v2 · state=AGREED",
    )
    conversations.review_draft_action(draft["id"], "APPROVE")

    # Request creation health check.
    transport.queue(200, _discover())
    transport.queue(200, _tools())
    request = conversation_integrations.request_execution(
        draft["id"],
        connection["id"],
        target="architecture-decisions",
    )
    assert request["status"] == "PENDING"
    assert request["capability"] == "decision_log.write"

    # Execute boundary health check, then adapter's final pre-write recheck,
    # then one and only one tools/call side effect.
    transport.queue(200, _discover())
    transport.queue(200, _tools())
    transport.queue(200, _discover())
    transport.queue(200, _tools())
    transport.queue(200, _tool_success())
    executed = conversation_integrations.execute_request(request["id"])

    assert executed["status"] == "SUCCEEDED"
    assert executed["response"]["provider_id"] == "MCP"
    assert executed["response"]["tool_name"] == "chengzhu_update_decision_log"
    tool_calls = [
        call for call in transport.calls
        if call["body"]["method"] == "tools/call"
    ]
    assert len(tool_calls) == 1
    assert "mcp-secret-token" not in json.dumps(executed, ensure_ascii=False)


def test_mcp_post_tools_call_transport_failure_becomes_unknown_and_cannot_auto_retry(product_env, mcp_env):
    transport = FakeTransport()
    adapter = McpDecisionLogAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    transport.queue(200, _discover())
    transport.queue(200, _tools())
    connection = conversation_integrations.create_connection(
        "MCP",
        granted_capabilities=["decision_log.write"],
        provider_scopes=["server-defined"],
        credential_ref="provider:mcp:env:CHENGZHU_MCP_DECISION_LOG_CONFIG",
    )
    conversation_integrations.verify_and_connect(connection["id"])

    space = conversations.create_space("Unknown MCP", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    conversations.end_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"],
        kind="UPDATE_DECISION_LOG_DRAFT",
        title="Decision log",
        content="- reviewed decision",
    )
    conversations.review_draft_action(draft["id"], "APPROVE")

    transport.queue(200, _discover())
    transport.queue(200, _tools())
    execution = conversation_integrations.request_execution(
        draft["id"], connection["id"], target="decision-log"
    )

    transport.queue(200, _discover())
    transport.queue(200, _tools())
    transport.queue(200, _discover())
    transport.queue(200, _tools())
    transport.queue_error(RuntimeError("transport closed after tools/call"))
    unknown = conversation_integrations.execute_request(execution["id"])
    assert unknown["status"] == "UNKNOWN_OUTCOME"

    with pytest.raises(ValueError, match="必须先在 provider 侧核对"):
        conversation_integrations.execute_request(execution["id"])
