import json
from urllib.parse import parse_qs, urlparse

import pytest

from services.product import conversation_integrations, conversations
from services.product.microsoft_todo_connector import (
    MicrosoftTodoGraphAdapter,
    MicrosoftTodoProviderError,
    register_microsoft_todo_adapter_from_env,
)


class FakeTransport:
    def __init__(self):
        self.responses = []
        self.calls = []

    def queue(self, status, payload, headers=None):
        self.responses.append((status, headers or {}, payload))

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({
            "method": method,
            "url": url,
            "headers": dict(headers),
            "body": body,
            "timeout": timeout,
        })
        if not self.responses:
            raise AssertionError(f"Unexpected Microsoft Graph request: {method} {url}")
        status, response_headers, payload = self.responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return status, response_headers, payload


def _connection(
    *,
    capabilities=None,
    scopes=None,
    ref="provider:microsoft-graph:env:CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN",
):
    capabilities = capabilities or ["project.read", "task.create"]
    scopes = scopes or ["Tasks.ReadWrite", "User.Read"]
    return {
        "id": "ccn_ms_todo",
        "provider_id": "MICROSOFT_GRAPH",
        "credential_ref": ref,
        "granted_capabilities": capabilities,
        "provider_scopes": scopes,
        "status": "CONNECTED",
        "account_hint": "user@example.com",
    }


def _queue_health(transport, *, identity="user@example.com"):
    transport.queue(200, {
        "id": "user-1",
        "displayName": "Test User",
        "mail": identity,
        "userPrincipalName": identity,
    })
    transport.queue(200, {"value": [{"id": "list-default"}]})


def _queue_explicit_list(transport, list_id="list-1", name="Architecture"):
    transport.queue(200, {
        "id": list_id,
        "displayName": name,
        "isOwner": True,
        "isShared": False,
        "wellknownListName": "none",
    })


def test_microsoft_todo_adapter_requires_https():
    with pytest.raises(ValueError, match="HTTPS"):
        MicrosoftTodoGraphAdapter(api_base="http://graph.example", transport=FakeTransport())


def test_microsoft_todo_catalog_is_exact_subset_and_scopes_are_minimal(product_env):
    row = next(x for x in conversation_integrations.catalog() if x["provider_id"] == "MICROSOFT_GRAPH")
    assert row["label"] == "Microsoft To Do (Graph)"
    assert row["capabilities"] == ["project.read", "task.create"]
    assert row["read_capabilities"] == ["project.read"]
    assert row["write_capabilities"] == ["task.create"]
    assert row["external_kinds"] == ["TASK"]
    assert row["identity_scopes"] == ["User.Read"]
    assert row["adapter_available"] is False
    assert row["adapter_capabilities"] == []
    dumped = json.dumps(row)
    assert "Mail.Read" not in dumped
    assert "Mail.Send" not in dumped
    assert "Calendars.Read" not in dumped
    assert "Files.Read" not in dumped

    read_only = conversation_integrations.create_connection(
        "MICROSOFT_GRAPH",
        granted_capabilities=["project.read"],
        credential_ref="provider:microsoft-graph:env:MS_TOKEN",
    )
    assert read_only["provider_scopes"] == ["Tasks.Read", "User.Read"]

    read_write = conversation_integrations.create_connection(
        "MICROSOFT_GRAPH",
        granted_capabilities=["project.read", "task.create"],
        credential_ref="provider:microsoft-graph:env:MS_TOKEN",
    )
    assert read_write["provider_scopes"] == ["Tasks.ReadWrite", "User.Read"]

    write_only = conversation_integrations.create_connection(
        "MICROSOFT_GRAPH",
        granted_capabilities=["task.create"],
        credential_ref="provider:microsoft-graph:env:MS_TOKEN",
    )
    assert write_only["provider_scopes"] == ["Tasks.ReadWrite", "User.Read"]

    with pytest.raises(ValueError, match="provider 不支持 capability"):
        conversation_integrations.create_connection(
            "MICROSOFT_GRAPH",
            granted_capabilities=["mail.read"],
            credential_ref="provider:microsoft-graph:env:MS_TOKEN",
        )


def test_catalog_reports_registered_adapter_capabilities_and_create_rejects_runtime_gap(product_env):
    class ReadOnlyMicrosoftAdapter:
        provider_id = "MICROSOFT_GRAPH"
        capabilities = {"project.read"}

        def health(self, connection=None):
            return {"ok": True, "label": "read only"}

        def read_context(self, **kwargs):
            return {"items": [], "next_cursor": ""}

        def execute(self, **kwargs):
            return {"ok": False, "error": "read only", "retry_safe": False}

    conversation_integrations.register_adapter(ReadOnlyMicrosoftAdapter())
    row = next(x for x in conversation_integrations.catalog() if x["provider_id"] == "MICROSOFT_GRAPH")
    assert row["adapter_available"] is True
    assert row["adapter_capabilities"] == ["project.read"]

    with pytest.raises(ValueError, match="当前 adapter 不支持 capability"):
        conversation_integrations.create_connection(
            "MICROSOFT_GRAPH",
            granted_capabilities=["task.create"],
            credential_ref="provider:microsoft-graph:env:MS_TOKEN",
        )


def test_microsoft_todo_health_verifies_identity_and_task_permission(monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-secret-token")
    transport = FakeTransport()
    _queue_health(transport)
    adapter = MicrosoftTodoGraphAdapter(transport=transport)

    assert adapter.health(None)["runtime"] == "OPT_IN_REAL_PROVIDER"
    health = adapter.health(_connection())
    assert health["ok"] is True
    assert health["account_hint"] == "user@example.com"
    assert health["provider_user_id"] == "user-1"
    assert health["verify"] == "USER_READ_PLUS_TODO_READ_PROBE"

    assert [urlparse(call["url"]).path for call in transport.calls] == [
        "/v1.0/me",
        "/v1.0/me/todo/lists",
    ]
    assert all(call["headers"]["Authorization"] == "Bearer ms-secret-token" for call in transport.calls)


def test_microsoft_todo_rejects_raw_or_missing_credential(monkeypatch):
    adapter = MicrosoftTodoGraphAdapter(transport=FakeTransport())
    with pytest.raises(ValueError, match="credential_ref"):
        adapter.health({**_connection(), "credential_ref": "secret-token"})

    monkeypatch.delenv("MISSING_MS_TOKEN", raising=False)
    with pytest.raises(ValueError, match="未设置"):
        adapter.health({
            **_connection(),
            "credential_ref": "provider:microsoft-graph:env:MISSING_MS_TOKEN",
        })


def test_default_list_resolution_and_full_refresh_snapshot(monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-secret-token")
    transport = FakeTransport()
    transport.queue(200, {"value": [
        {
            "id": "list-other",
            "displayName": "Someday",
            "wellknownListName": "none",
            "isOwner": True,
            "isShared": False,
        },
        {
            "id": "list-default",
            "displayName": "Tasks",
            "wellknownListName": "defaultList",
            "isOwner": True,
            "isShared": False,
        },
    ]})
    transport.queue(200, {"value": [{
        "id": "task-1",
        "title": "Review rollback plan",
        "body": {"content": "Confirm owner before Friday.", "contentType": "text"},
        "status": "notStarted",
        "importance": "high",
        "createdDateTime": "2026-10-09T10:00:00Z",
        "lastModifiedDateTime": "2026-10-10T10:00:00Z",
        "dueDateTime": {"dateTime": "2026-10-12T17:00:00.0000000", "timeZone": "UTC"},
        "categories": ["Architecture"],
        "isReminderOn": False,
    }]})
    adapter = MicrosoftTodoGraphAdapter(transport=transport)

    result = adapter.read_context(
        connection=_connection(capabilities=["project.read"], scopes=["Tasks.Read", "User.Read"]),
        capability="project.read",
        query={"todo_list_id": "defaultList"},
        cursor="ignored",
        limit=500,
    )
    assert result["full_refresh"] is True
    assert result["next_cursor"] == ""
    assert result["todo_list_id"] == "list-default"
    assert result["todo_list_name"] == "Tasks"
    item = result["items"][0]
    assert item["external_kind"] == "TASK"
    assert item["external_id"] == "list-default:task-1"
    assert item["title"] == "Review rollback plan"
    assert item["excerpt"] == "Confirm owner before Friday."
    assert item["metadata"]["status"] == "notStarted"
    assert item["metadata"]["todo_list_id"] == "list-default"
    assert item["occurred_at"] is not None


def test_explicit_list_target_is_url_encoded_and_pagination_is_complete(monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-secret-token")
    transport = FakeTransport()
    _queue_explicit_list(transport, "AQMk list/with+chars", "Shared")
    transport.queue(200, {
        "value": [{"id": "task-1", "title": "One"}],
        "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/todo/lists/AQMk/tasks?$skiptoken=next",
    })
    transport.queue(200, {"value": [{"id": "task-2", "title": "Two"}]})
    adapter = MicrosoftTodoGraphAdapter(transport=transport)

    result = adapter.read_context(
        connection=_connection(capabilities=["project.read"], scopes=["Tasks.Read", "User.Read"]),
        capability="project.read",
        query={"todo_list_id": "AQMk list/with+chars"},
        cursor="",
        limit=500,
    )
    assert [item["title"] for item in result["items"]] == ["One", "Two"]
    assert "%2F" in transport.calls[0]["url"]
    assert transport.calls[-1]["url"].startswith("https://graph.microsoft.com/v1.0/")


def test_untrusted_next_link_is_rejected_before_bearer_forward(monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-secret-token")
    transport = FakeTransport()
    _queue_explicit_list(transport)
    transport.queue(200, {
        "value": [{"id": "task-1", "title": "One"}],
        "@odata.nextLink": "https://evil.example/steal",
    })
    adapter = MicrosoftTodoGraphAdapter(transport=transport)

    with pytest.raises(RuntimeError, match="nextLink"):
        adapter.read_context(
            connection=_connection(capabilities=["project.read"], scopes=["Tasks.Read", "User.Read"]),
            capability="project.read",
            query={"todo_list_id": "list-1"},
            cursor="",
            limit=500,
        )
    assert all(urlparse(call["url"]).netloc != "evil.example" for call in transport.calls)


def test_full_refresh_refuses_partial_snapshot_set(monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-secret-token")
    transport = FakeTransport()
    _queue_explicit_list(transport)
    transport.queue(200, {"value": [
        {"id": f"task-{i}", "title": f"Task {i}"}
        for i in range(3)
    ]})
    adapter = MicrosoftTodoGraphAdapter(transport=transport)
    with pytest.raises(ValueError, match="拒绝半同步"):
        adapter.read_context(
            connection=_connection(capabilities=["project.read"], scopes=["Tasks.Read", "User.Read"]),
            capability="project.read",
            query={"todo_list_id": "list-1"},
            cursor="",
            limit=2,
        )


def test_create_task_uses_reviewed_title_body_without_silent_truncation(monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-secret-token")
    transport = FakeTransport()
    _queue_explicit_list(transport)
    transport.queue(201, {
        "id": "task-created",
        "title": "Ship rollout plan",
        "status": "notStarted",
    })
    adapter = MicrosoftTodoGraphAdapter(transport=transport)
    result = adapter.execute(
        connection=_connection(),
        capability="task.create",
        operation="CREATE_TASK",
        target="list-1",
        payload={
            "title": "Ship rollout plan",
            "content": "Owner=me\nReview rollback before Friday.",
        },
        idempotency_key="audit-only",
    )
    assert result["ok"] is True
    assert result["task_id"] == "task-created"
    assert result["provider_idempotency"] == "NONE"
    body = json.loads(transport.calls[-1]["body"].decode("utf-8"))
    assert body == {
        "title": "Ship rollout plan",
        "body": {"content": "Owner=me\nReview rollback before Friday.", "contentType": "text"},
    }

    too_long = adapter.execute(
        connection=_connection(),
        capability="task.create",
        operation="CREATE_TASK",
        target="list-1",
        payload={"title": "x" * 256, "content": ""},
        idempotency_key="audit-only-2",
    )
    assert too_long["ok"] is False
    assert "静默截断" in too_long["error"]


def test_definitive_4xx_is_failed_but_server_error_is_ambiguous(monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-secret-token")

    transport = FakeTransport()
    _queue_explicit_list(transport)
    transport.queue(403, MicrosoftTodoProviderError(403, "Microsoft Graph HTTP 403"))
    adapter = MicrosoftTodoGraphAdapter(transport=transport)
    failed = adapter.execute(
        connection=_connection(),
        capability="task.create",
        operation="CREATE_TASK",
        target="list-1",
        payload={"title": "Task", "content": "Body"},
        idempotency_key="x",
    )
    assert failed["ok"] is False
    assert failed["http_status"] == 403

    transport2 = FakeTransport()
    _queue_explicit_list(transport2)
    transport2.queue(503, MicrosoftTodoProviderError(503, "Microsoft Graph HTTP 503"))
    adapter2 = MicrosoftTodoGraphAdapter(transport=transport2)
    with pytest.raises(MicrosoftTodoProviderError):
        adapter2.execute(
            connection=_connection(),
            capability="task.create",
            operation="CREATE_TASK",
            target="list-1",
            payload={"title": "Task", "content": "Body"},
            idempotency_key="x",
        )


def test_registration_is_explicit_opt_in(product_env, monkeypatch):
    conversation_integrations.clear_adapters_for_tests()
    monkeypatch.delenv("CHENGZHU_MICROSOFT_TODO_CONNECTOR_ENABLE", raising=False)
    assert register_microsoft_todo_adapter_from_env()["registered"] is False

    monkeypatch.setenv("CHENGZHU_MICROSOFT_TODO_CONNECTOR_ENABLE", "1")
    registered = register_microsoft_todo_adapter_from_env()
    assert registered["registered"] is True
    assert registered["capabilities"] == ["project.read", "task.create"]
    row = next(x for x in conversation_integrations.catalog() if x["provider_id"] == "MICROSOFT_GRAPH")
    assert row["adapter_available"] is True
    assert row["adapter_capabilities"] == ["project.read", "task.create"]


def test_reviewed_two_step_task_execution_uses_exact_connection_and_list(product_env, monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-secret-token")
    transport = FakeTransport()
    adapter = MicrosoftTodoGraphAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    connection = conversation_integrations.create_connection(
        "MICROSOFT_GRAPH",
        display_name="Microsoft To Do",
        granted_capabilities=["project.read", "task.create"],
        credential_ref="provider:microsoft-graph:env:CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN",
    )
    _queue_health(transport)
    connected = conversation_integrations.verify_and_connect(connection["id"])
    assert connected["status"] == "CONNECTED"
    assert connected["account_hint"] == "user@example.com"

    space = conversations.create_space("Project Sync", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    conversations.end_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"],
        kind="CREATE_TASK_DRAFT",
        title="Ship rollout plan",
        content="Owner=me\nReview rollback before Friday.",
        payload={"external_execution": False},
    )
    conversations.review_draft_action(draft["id"], "APPROVE")

    # request_execution health check: /me + To Do list probe
    _queue_health(transport)
    execution = conversation_integrations.request_execution(
        draft["id"], connection["id"], target="list-architecture"
    )
    assert execution["status"] == "PENDING"
    assert execution["capability"] == "task.create"
    assert execution["operation"] == "CREATE_TASK"
    assert execution["target"] == "list-architecture"

    # execute_request health check, explicit list lookup, then POST task.
    _queue_health(transport)
    _queue_explicit_list(transport, "list-architecture", "Architecture")
    transport.queue(201, {"id": "task-real-1", "title": "Ship rollout plan", "status": "notStarted"})
    executed = conversation_integrations.execute_request(execution["id"])
    assert executed["status"] == "SUCCEEDED"
    assert executed["response"]["task_id"] == "task-real-1"
    assert executed["response"]["todo_list_id"] == "list-architecture"
    assert "ms-secret-token" not in json.dumps(executed, ensure_ascii=False)


def test_ambiguous_task_create_becomes_unknown_outcome_and_cannot_retry(product_env, monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-secret-token")
    transport = FakeTransport()
    adapter = MicrosoftTodoGraphAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    connection = conversation_integrations.create_connection(
        "MICROSOFT_GRAPH",
        granted_capabilities=["task.create"],
        credential_ref="provider:microsoft-graph:env:CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN",
    )
    _queue_health(transport)
    conversation_integrations.verify_and_connect(connection["id"])

    space = conversations.create_space("Unknown Task", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    conversations.end_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"], kind="CREATE_TASK_DRAFT", title="Task", content="Body"
    )
    conversations.review_draft_action(draft["id"], "APPROVE")

    _queue_health(transport)
    execution = conversation_integrations.request_execution(
        draft["id"], connection["id"], target="list-1"
    )

    _queue_health(transport)
    _queue_explicit_list(transport)
    transport.queue(503, RuntimeError("timeout after request write"))
    unknown = conversation_integrations.execute_request(execution["id"])
    assert unknown["status"] == "UNKNOWN_OUTCOME"
    with pytest.raises(ValueError, match="必须先在 provider 侧核对"):
        conversation_integrations.execute_request(execution["id"])
