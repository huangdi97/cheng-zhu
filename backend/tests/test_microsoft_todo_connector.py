import json

import pytest

from services.product import conversation_integrations, conversations
from services.product.microsoft_todo_connector import (
    MicrosoftGraphProviderError,
    MicrosoftTodoTaskAdapter,
    register_microsoft_todo_adapter_from_env,
)


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.responses = []

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


def _connection(ref="provider:microsoft-graph:env:CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN"):
    return {
        "id": "ccn_ms_test",
        "provider_id": "MICROSOFT_GRAPH",
        "credential_ref": ref,
        "granted_capabilities": ["task.create"],
        "provider_scopes": ["Tasks.ReadWrite"],
        "status": "CONNECTED",
        "account_hint": "Microsoft To Do",
    }


@pytest.fixture(autouse=True)
def _clean_adapters():
    conversation_integrations.clear_adapters_for_tests()
    yield
    conversation_integrations.clear_adapters_for_tests()


def _lists_payload():
    return {
        "value": [
            {
                "id": "AQMk-default-list",
                "displayName": "Tasks",
                "isOwner": True,
                "isShared": False,
                "wellknownListName": "defaultList",
            },
            {
                "id": "AQMk-work-list",
                "displayName": "Work",
                "isOwner": True,
                "isShared": False,
                "wellknownListName": "none",
            },
        ]
    }


def test_microsoft_todo_adapter_requires_https_api_base():
    with pytest.raises(ValueError, match="HTTPS"):
        MicrosoftTodoTaskAdapter(
            api_base="http://graph.microsoft.test/v1.0",
            transport=FakeTransport(),
        )


def test_microsoft_todo_scope_model_is_task_create_only_and_least_privilege(product_env):
    connection = conversation_integrations.create_connection(
        "MICROSOFT_GRAPH",
        granted_capabilities=["task.create"],
        credential_ref="provider:microsoft-graph:env:MS_TOKEN",
    )
    assert connection["provider_scopes"] == ["Tasks.ReadWrite"]

    with pytest.raises(ValueError, match="provider 不支持 capability"):
        conversation_integrations.create_connection(
            "MICROSOFT_GRAPH",
            granted_capabilities=["calendar.read"],
            credential_ref="provider:microsoft-graph:env:MS_TOKEN",
        )

    with pytest.raises(ValueError, match="最小权限集合"):
        conversation_integrations.create_connection(
            "MICROSOFT_GRAPH",
            granted_capabilities=["task.create"],
            provider_scopes=["Tasks.ReadWrite", "Mail.Send"],
            credential_ref="provider:microsoft-graph:env:MS_TOKEN",
        )


def test_microsoft_todo_health_uses_external_env_token_and_todo_list_probe(monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-test-token")
    transport = FakeTransport()
    transport.queue(200, _lists_payload())
    adapter = MicrosoftTodoTaskAdapter(transport=transport)

    assert adapter.health(None)["ok"] is True
    health = adapter.health(_connection())
    assert health["ok"] is True
    assert health["verify"] == "TASKS_READWRITE_TODO_LIST_PROBE"
    assert health["default_list_present"] is True
    assert health["default_list_name"] == "Tasks"

    call = transport.calls[0]
    assert call["method"] == "GET"
    assert call["url"].startswith("https://graph.microsoft.com/v1.0/me/todo/lists?")
    assert call["headers"]["Authorization"] == "Bearer ms-test-token"


def test_microsoft_todo_rejects_nonopaque_or_missing_env_reference(monkeypatch):
    adapter = MicrosoftTodoTaskAdapter(transport=FakeTransport())
    with pytest.raises(ValueError, match="credential_ref"):
        adapter.health({**_connection(), "credential_ref": "raw-token"})
    monkeypatch.delenv("MISSING_MS_TOKEN", raising=False)
    with pytest.raises(ValueError, match="未设置"):
        adapter.health({
            **_connection(),
            "credential_ref": "provider:microsoft-graph:env:MISSING_MS_TOKEN",
        })


def test_microsoft_todo_default_target_resolves_builtin_tasks_list_and_creates_reviewed_task(monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-test-token")
    transport = FakeTransport()
    transport.queue(200, _lists_payload())
    transport.queue(201, {"id": "task-123", "title": "Publish rollout plan"})
    adapter = MicrosoftTodoTaskAdapter(transport=transport)

    result = adapter.execute(
        connection=_connection(),
        capability="task.create",
        operation="CREATE_TASK",
        target="default",
        payload={
            "title": "Publish rollout plan",
            "content": "Owner: me\nDue: Friday",
            "outbound_redaction_applied": False,
        },
        idempotency_key="audit-only-not-provider-idempotency",
    )

    assert result["ok"] is True
    assert result["task_id"] == "task-123"
    assert result["task_list_id"] == "AQMk-default-list"
    assert result["task_list_name"] == "Tasks"
    assert result["provider_idempotency"] == "NONE"

    assert transport.calls[0]["method"] == "GET"
    create = transport.calls[1]
    assert create["method"] == "POST"
    assert create["url"].endswith("/me/todo/lists/AQMk-default-list/tasks")
    body = json.loads(create["body"].decode("utf-8"))
    assert body == {
        "title": "Publish rollout plan",
        "body": {"contentType": "text", "content": "Owner: me\nDue: Friday"},
    }


def test_microsoft_todo_explicit_list_target_is_probed_before_create(monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-test-token")
    transport = FakeTransport()
    transport.queue(200, {
        "id": "AQMk-work-list",
        "displayName": "Work",
        "isOwner": True,
        "isShared": False,
        "wellknownListName": "none",
    })
    transport.queue(201, {"id": "task-work-1", "title": "Rollback drill"})
    adapter = MicrosoftTodoTaskAdapter(transport=transport)

    result = adapter.execute(
        connection=_connection(),
        capability="task.create",
        operation="CREATE_TASK",
        target="AQMk-work-list",
        payload={
            "title": "Rollback drill",
            "content": "Schedule rollback drill.",
            "outbound_redaction_applied": False,
        },
        idempotency_key="abc",
    )

    assert result["ok"] is True
    assert result["task_list_name"] == "Work"
    assert transport.calls[0]["method"] == "GET"
    assert "/me/todo/lists/AQMk-work-list?" in transport.calls[0]["url"]
    assert transport.calls[1]["method"] == "POST"


def test_microsoft_todo_never_silently_mutates_reviewed_payload(monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-test-token")
    adapter = MicrosoftTodoTaskAdapter(transport=FakeTransport())

    changed = adapter.execute(
        connection=_connection(),
        capability="task.create",
        operation="CREATE_TASK",
        target="default",
        payload={
            "title": "Reviewed task",
            "content": "redacted body",
            "outbound_redaction_applied": True,
        },
        idempotency_key="redacted",
    )
    assert changed["ok"] is False
    assert "重新审核" in changed["error"]

    too_long_title = adapter.execute(
        connection=_connection(),
        capability="task.create",
        operation="CREATE_TASK",
        target="default",
        payload={
            "title": "x" * 501,
            "content": "body",
            "outbound_redaction_applied": False,
        },
        idempotency_key="long-title",
    )
    assert too_long_title["ok"] is False
    assert "不会静默截断" in too_long_title["error"]

    too_long_body = adapter.execute(
        connection=_connection(),
        capability="task.create",
        operation="CREATE_TASK",
        target="default",
        payload={
            "title": "Task",
            "content": "x" * 20001,
            "outbound_redaction_applied": False,
        },
        idempotency_key="long-body",
    )
    assert too_long_body["ok"] is False
    assert "不会静默截断" in too_long_body["error"]


def test_microsoft_todo_definitive_rejection_differs_from_ambiguous_failure(monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-test-token")
    transport = FakeTransport()
    transport.queue(200, _lists_payload())
    transport.queue(400, MicrosoftGraphProviderError(400, "Microsoft Graph HTTP 400: bad task"))
    adapter = MicrosoftTodoTaskAdapter(transport=transport)

    rejected = adapter.execute(
        connection=_connection(),
        capability="task.create",
        operation="CREATE_TASK",
        target="default",
        payload={
            "title": "Bad task",
            "content": "body",
            "outbound_redaction_applied": False,
        },
        idempotency_key="reject",
    )
    assert rejected["ok"] is False
    assert rejected["http_status"] == 400
    assert rejected["retry_safe"] is False

    transport.queue(200, _lists_payload())
    transport.queue(500, MicrosoftGraphProviderError(500, "Microsoft Graph HTTP 500"))
    with pytest.raises(MicrosoftGraphProviderError):
        adapter.execute(
            connection=_connection(),
            capability="task.create",
            operation="CREATE_TASK",
            target="default",
            payload={
                "title": "Ambiguous task",
                "content": "body",
                "outbound_redaction_applied": False,
            },
            idempotency_key="ambiguous",
        )


def test_microsoft_todo_registration_is_explicit_opt_in(product_env, monkeypatch):
    monkeypatch.delenv("CHENGZHU_MICROSOFT_TODO_CONNECTOR_ENABLE", raising=False)
    assert register_microsoft_todo_adapter_from_env()["registered"] is False
    microsoft = next(
        x for x in conversation_integrations.catalog()
        if x["provider_id"] == "MICROSOFT_GRAPH"
    )
    assert microsoft["adapter_available"] is False
    assert microsoft["capabilities"] == ["task.create"]

    monkeypatch.setenv("CHENGZHU_MICROSOFT_TODO_CONNECTOR_ENABLE", "1")
    registered = register_microsoft_todo_adapter_from_env()
    assert registered["registered"] is True
    assert registered["delegated_permission"] == "Tasks.ReadWrite"
    microsoft = next(
        x for x in conversation_integrations.catalog()
        if x["provider_id"] == "MICROSOFT_GRAPH"
    )
    assert microsoft["adapter_available"] is True


def test_real_microsoft_todo_adapter_runs_through_reviewed_two_step_boundary(product_env, monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-test-token")
    transport = FakeTransport()
    adapter = MicrosoftTodoTaskAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    # Verify connection by probing To Do task lists with Tasks.ReadWrite.
    transport.queue(200, _lists_payload())
    connection = conversation_integrations.create_connection(
        "MICROSOFT_GRAPH",
        display_name="Microsoft To Do · task-create",
        granted_capabilities=["task.create"],
        credential_ref="provider:microsoft-graph:env:CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN",
    )
    connected = conversation_integrations.verify_and_connect(connection["id"])
    assert connected["status"] == "CONNECTED"
    assert connected["account_hint"] == "Microsoft To Do"

    space = conversations.create_space("Project Sync", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    conversations.end_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"],
        kind="CREATE_TASK_DRAFT",
        title="Publish rollout plan",
        content="Owner: me\nDue: Friday",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "explicit follow-up"}],
    )
    conversations.review_draft_action(draft["id"], "APPROVE")

    # Execution request creation re-checks capability/account health.
    transport.queue(200, _lists_payload())
    request = conversation_integrations.request_execution(
        draft["id"],
        connection["id"],
        target="default",
    )
    assert request["status"] == "PENDING"
    assert request["capability"] == "task.create"
    assert request["operation"] == "CREATE_TASK"

    # Second explicit Execute re-checks connection health, resolves target list,
    # then creates the task.
    transport.queue(200, _lists_payload())
    transport.queue(200, _lists_payload())
    transport.queue(201, {"id": "task-real-1", "title": "Publish rollout plan"})
    executed = conversation_integrations.execute_request(request["id"])
    assert executed["status"] == "SUCCEEDED"
    assert executed["response"]["provider_id"] == "MICROSOFT_GRAPH"
    assert executed["response"]["task_id"] == "task-real-1"
    assert executed["response"]["task_list_id"] == "AQMk-default-list"
    assert "ms-test-token" not in json.dumps(executed, ensure_ascii=False)


def test_microsoft_todo_ambiguous_transport_becomes_unknown_and_cannot_auto_retry(product_env, monkeypatch):
    monkeypatch.setenv("CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN", "ms-test-token")
    transport = FakeTransport()
    adapter = MicrosoftTodoTaskAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    transport.queue(200, _lists_payload())
    connection = conversation_integrations.create_connection(
        "MICROSOFT_GRAPH",
        granted_capabilities=["task.create"],
        credential_ref="provider:microsoft-graph:env:CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN",
    )
    conversation_integrations.verify_and_connect(connection["id"])

    space = conversations.create_space("Unknown Outcome", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    conversations.end_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"], kind="CREATE_TASK_DRAFT", title="Task", content="Body"
    )
    conversations.review_draft_action(draft["id"], "APPROVE")

    transport.queue(200, _lists_payload())
    execution = conversation_integrations.request_execution(
        draft["id"], connection["id"], target="default"
    )
    transport.queue(200, _lists_payload())
    transport.queue(200, _lists_payload())
    transport.queue(503, RuntimeError("transport timeout after request write"))
    unknown = conversation_integrations.execute_request(execution["id"])
    assert unknown["status"] == "UNKNOWN_OUTCOME"
    with pytest.raises(ValueError, match="必须先在 provider 侧核对"):
        conversation_integrations.execute_request(execution["id"])
