import json
from urllib.parse import parse_qs, urlparse

import pytest

from services.product import conversation_integrations, conversations
from services.product.github_connector import (
    GITHUB_API_VERSION,
    GitHubProviderError,
    GitHubRestAdapter,
    register_github_adapter_from_env,
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
            raise AssertionError(f"Unexpected GitHub request: {method} {url}")
        status, response_headers, payload = self.responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return status, response_headers, payload


def _connection(ref="provider:github:env:CHENGZHU_GITHUB_TOKEN"):
    return {
        "id": "ccn_test",
        "provider_id": "GITHUB",
        "credential_ref": ref,
        "granted_capabilities": ["project.read", "issue.create"],
        "provider_scopes": ["Issues: write"],
        "status": "CONNECTED",
    }




def test_github_adapter_requires_https_api_base():
    with pytest.raises(ValueError, match="HTTPS"):
        GitHubRestAdapter(api_base="http://api.github.test", transport=FakeTransport())


def test_github_scope_model_collapses_read_plus_write_to_issues_write(product_env):
    read_only = conversation_integrations.create_connection(
        "GITHUB",
        granted_capabilities=["project.read"],
        credential_ref="provider:github:env:CHENGZHU_GITHUB_TOKEN",
    )
    assert read_only["provider_scopes"] == ["Issues: read"]

    read_write = conversation_integrations.create_connection(
        "GITHUB",
        granted_capabilities=["project.read", "issue.create"],
        credential_ref="provider:github:env:CHENGZHU_GITHUB_TOKEN",
    )
    assert read_write["provider_scopes"] == ["Issues: write"]

    with pytest.raises(ValueError, match="最小权限集合"):
        conversation_integrations.create_connection(
            "GITHUB",
            granted_capabilities=["project.read", "issue.create"],
            provider_scopes=["Issues: read", "Issues: write"],
            credential_ref="provider:github:env:CHENGZHU_GITHUB_TOKEN",
        )


def test_github_adapter_health_uses_external_env_credential(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GITHUB_TOKEN", "github_pat_test_only_secret")
    transport = FakeTransport()
    transport.queue(200, {"login": "octocat", "id": 42})
    adapter = GitHubRestAdapter(transport=transport)

    assert adapter.health(None)["ok"] is True
    health = adapter.health(_connection())
    assert health["ok"] is True
    assert health["account_hint"] == "octocat"

    call = transport.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "https://api.github.com/user"
    assert call["headers"]["Authorization"] == "Bearer github_pat_test_only_secret"
    assert call["headers"]["X-GitHub-Api-Version"] == GITHUB_API_VERSION
    assert call["headers"]["User-Agent"].startswith("Chengzhu/")


def test_github_adapter_rejects_non_opaque_or_missing_env_reference(monkeypatch):
    adapter = GitHubRestAdapter(transport=FakeTransport())
    with pytest.raises(ValueError, match="credential_ref"):
        adapter.health({**_connection(), "credential_ref": "github_pat_secret"})
    monkeypatch.delenv("MISSING_GITHUB_TOKEN", raising=False)
    with pytest.raises(ValueError, match="未设置"):
        adapter.health({**_connection(), "credential_ref": "provider:github:env:MISSING_GITHUB_TOKEN"})


def test_github_project_read_filters_pull_requests_and_returns_overlap_cursor(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GITHUB_TOKEN", "github_pat_test_only_secret")
    transport = FakeTransport()
    transport.queue(200, [
        {
            "number": 7,
            "node_id": "I_7",
            "title": "Rollback owner unresolved",
            "body": "Need to confirm the rollback owner.",
            "state": "open",
            "labels": [{"name": "risk"}],
            "assignees": [{"login": "alex"}],
            "created_at": "2026-10-10T01:00:00Z",
            "updated_at": "2026-10-10T02:00:00Z",
            "html_url": "https://github.com/acme/project/issues/7?secret=no",
        },
        {
            "number": 8,
            "node_id": "PR_8",
            "title": "A pull request",
            "body": "must not be imported as an issue snapshot",
            "state": "open",
            "pull_request": {"url": "https://api.github.com/repos/acme/project/pulls/8"},
            "created_at": "2026-10-10T02:00:00Z",
            "updated_at": "2026-10-10T03:00:00Z",
            "html_url": "https://github.com/acme/project/pull/8",
        },
    ])
    adapter = GitHubRestAdapter(transport=transport)

    result = adapter.read_context(
        connection=_connection(),
        capability="project.read",
        query={"repository": "acme/project", "state": "open", "labels": ["risk"]},
        cursor="2026-10-09T00:00:00Z",
        limit=50,
    )

    assert len(result["items"]) == 1
    issue = result["items"][0]
    assert issue["external_kind"] == "ISSUE"
    assert issue["external_id"] == "acme/project#7"
    assert issue["metadata"]["repository"] == "acme/project"
    assert issue["metadata"]["labels"] == ["risk"]
    assert issue["metadata"]["assignees"] == ["alex"]
    assert result["next_cursor"] == "2026-10-10T02:59:59Z"

    parsed = urlparse(transport.calls[0]["url"])
    params = parse_qs(parsed.query)
    assert parsed.path == "/repos/acme/project/issues"
    assert params["since"] == ["2026-10-09T00:00:00Z"]
    assert params["labels"] == ["risk"]




def test_github_target_sync_failure_does_not_invalidate_authenticated_account(product_env, monkeypatch):
    monkeypatch.setenv("CHENGZHU_GITHUB_TOKEN", "github_pat_test_only_secret")
    transport = FakeTransport()
    adapter = GitHubRestAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    transport.queue(200, {"login": "octocat", "id": 42})
    connection = conversation_integrations.create_connection(
        "GITHUB",
        granted_capabilities=["project.read"],
        credential_ref="provider:github:env:CHENGZHU_GITHUB_TOKEN",
    )
    connected = conversation_integrations.verify_and_connect(connection["id"])
    assert connected["status"] == "CONNECTED"

    space = conversations.create_space("Target Error", "PROJECT_SYNC")
    transport.queue(200, {"login": "octocat", "id": 42})
    transport.queue(404, GitHubProviderError(404, "GitHub HTTP 404: Not Found"))
    with pytest.raises(ValueError, match="404"):
        conversation_integrations.sync_connection(
            connection["id"],
            space["id"],
            capabilities=["project.read"],
            query={"repository": "missing/repo"},
        )

    after = next(row for row in conversation_integrations.list_connections() if row["id"] == connection["id"])
    assert after["status"] == "CONNECTED"
    assert "404" in after["last_error"]


def test_github_auth_failure_during_sync_marks_connection_error(product_env, monkeypatch):
    monkeypatch.setenv("CHENGZHU_GITHUB_TOKEN", "github_pat_test_only_secret")
    transport = FakeTransport()
    adapter = GitHubRestAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    transport.queue(200, {"login": "octocat", "id": 42})
    connection = conversation_integrations.create_connection(
        "GITHUB",
        granted_capabilities=["project.read"],
        credential_ref="provider:github:env:CHENGZHU_GITHUB_TOKEN",
    )
    conversation_integrations.verify_and_connect(connection["id"])

    space = conversations.create_space("Auth Error", "PROJECT_SYNC")
    transport.queue(401, GitHubProviderError(401, "GitHub HTTP 401: Bad credentials"))
    with pytest.raises(ValueError, match="401"):
        conversation_integrations.sync_connection(
            connection["id"],
            space["id"],
            capabilities=["project.read"],
            query={"repository": "acme/project"},
        )

    after = next(row for row in conversation_integrations.list_connections() if row["id"] == connection["id"])
    assert after["status"] == "ERROR"




def test_github_issue_pagination_keeps_constant_page_size_when_pull_requests_are_filtered(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GITHUB_TOKEN", "github_pat_test_only_secret")
    transport = FakeTransport()
    first_page = [
        {
            "number": i,
            "node_id": f"PR_{i}",
            "title": f"PR {i}",
            "body": "",
            "state": "open",
            "pull_request": {"url": f"https://api.github.com/repos/acme/project/pulls/{i}"},
            "created_at": "2026-10-10T01:00:00Z",
            "updated_at": "2026-10-10T02:00:00Z",
            "html_url": f"https://github.com/acme/project/pull/{i}",
        }
        for i in range(1, 101)
    ]
    transport.queue(200, first_page)
    transport.queue(200, [{
        "number": 101,
        "node_id": "I_101",
        "title": "Real issue after many PRs",
        "body": "must not be skipped",
        "state": "open",
        "labels": [],
        "assignees": [],
        "created_at": "2026-10-10T03:00:00Z",
        "updated_at": "2026-10-10T03:00:00Z",
        "html_url": "https://github.com/acme/project/issues/101",
    }])
    adapter = GitHubRestAdapter(transport=transport)

    result = adapter.read_context(
        connection=_connection(),
        capability="project.read",
        query={"repository": "acme/project"},
        cursor="",
        limit=1,
    )
    assert [item["external_id"] for item in result["items"]] == ["acme/project#101"]
    first = parse_qs(urlparse(transport.calls[0]["url"]).query)
    second = parse_qs(urlparse(transport.calls[1]["url"]).query)
    assert first["per_page"] == ["100"]
    assert second["per_page"] == ["100"]
    assert first["page"] == ["1"]
    assert second["page"] == ["2"]


def test_github_issue_create_returns_explicit_provider_success(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GITHUB_TOKEN", "github_pat_test_only_secret")
    transport = FakeTransport()
    transport.queue(201, {
        "number": 23,
        "node_id": "I_23",
        "html_url": "https://github.com/acme/project/issues/23",
    })
    adapter = GitHubRestAdapter(transport=transport)

    result = adapter.execute(
        connection=_connection(),
        capability="issue.create",
        operation="CREATE_ISSUE",
        target="acme/project",
        payload={"title": "Rollback drill", "content": "Schedule a rollback drill."},
        idempotency_key="abc123",
    )

    assert result["ok"] is True
    assert result["external_id"] == "acme/project#23"
    call = transport.calls[0]
    assert call["method"] == "POST"
    body = json.loads(call["body"].decode("utf-8"))
    assert body["title"] == "Rollback drill"
    assert "Schedule a rollback drill." in body["body"]
    assert "<!-- chengzhu-execution:abc123 -->" in body["body"]


def test_github_issue_create_distinguishes_definitive_rejection_from_ambiguous_failure(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GITHUB_TOKEN", "github_pat_test_only_secret")
    transport = FakeTransport()
    transport.queue(422, GitHubProviderError(422, "GitHub HTTP 422: validation failed"))
    adapter = GitHubRestAdapter(transport=transport)

    rejected = adapter.execute(
        connection=_connection(),
        capability="issue.create",
        operation="CREATE_ISSUE",
        target="acme/project",
        payload={"title": "Bad issue", "content": "body"},
        idempotency_key="reject",
    )
    assert rejected["ok"] is False
    assert rejected["http_status"] == 422
    assert rejected["retry_safe"] is False

    transport.queue(500, GitHubProviderError(500, "GitHub HTTP 500"))
    with pytest.raises(GitHubProviderError):
        adapter.execute(
            connection=_connection(),
            capability="issue.create",
            operation="CREATE_ISSUE",
            target="acme/project",
            payload={"title": "Ambiguous issue", "content": "body"},
            idempotency_key="ambiguous",
        )


def test_github_registration_is_explicit_opt_in(product_env, monkeypatch):
    conversation_integrations.clear_adapters_for_tests()
    monkeypatch.delenv("CHENGZHU_GITHUB_CONNECTOR_ENABLE", raising=False)
    assert register_github_adapter_from_env()["registered"] is False
    github = next(x for x in conversation_integrations.catalog() if x["provider_id"] == "GITHUB")
    assert github["adapter_available"] is False

    monkeypatch.setenv("CHENGZHU_GITHUB_CONNECTOR_ENABLE", "1")
    registered = register_github_adapter_from_env()
    assert registered["registered"] is True
    github = next(x for x in conversation_integrations.catalog() if x["provider_id"] == "GITHUB")
    assert github["adapter_available"] is True
    assert set(github["capabilities"]) == {"project.read", "issue.create"}


def test_real_github_adapter_runs_through_audited_boundary_with_fake_http(product_env, monkeypatch):
    monkeypatch.setenv("CHENGZHU_GITHUB_TOKEN", "github_pat_test_only_secret")
    transport = FakeTransport()
    adapter = GitHubRestAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    # verify_and_connect -> GET /user
    transport.queue(200, {"login": "octocat", "id": 42})
    connection = conversation_integrations.create_connection(
        "GITHUB",
        display_name="Work GitHub",
        granted_capabilities=["project.read", "issue.create"],
        credential_ref="provider:github:env:CHENGZHU_GITHUB_TOKEN",
    )
    connected = conversation_integrations.verify_and_connect(connection["id"])
    assert connected["status"] == "CONNECTED"
    assert connected["account_hint"] == "octocat"
    assert connected["credential_ref_present"] is True
    assert "credential_ref" not in connected

    # sync re-checks account health, then reads immutable ISSUE snapshots
    transport.queue(200, {"login": "octocat", "id": 42})
    transport.queue(200, [{
        "number": 7,
        "node_id": "I_7",
        "title": "Rollback owner unresolved",
        "body": "Need to confirm owner.",
        "state": "open",
        "labels": [],
        "assignees": [],
        "created_at": "2026-10-10T01:00:00Z",
        "updated_at": "2026-10-10T02:00:00Z",
        "html_url": "https://github.com/acme/project/issues/7",
    }])
    space = conversations.create_space("GitHub Project", "PROJECT_SYNC")
    synced = conversation_integrations.sync_connection(
        connection["id"],
        space["id"],
        capabilities=["project.read"],
        query={"repository": "acme/project"},
    )
    assert synced["snapshots"][0]["external_id"] == "acme/project#7"
    assert synced["snapshots"][0]["capability"] == "project.read"

    # reviewed local issue draft -> exact account -> second execute -> provider
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"],
        kind="CREATE_ISSUE_DRAFT",
        title="Rollback drill",
        content="Schedule a rollback drill.",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "explicit follow-up"}],
    )
    conversations.review_draft_action(draft["id"], "APPROVE")
    request = conversation_integrations.request_execution(
        draft["id"],
        connection["id"],
        target="acme/project",
    )
    assert request["status"] == "PENDING"

    # execute re-checks connection health first, then POST issue
    transport.queue(200, {"login": "octocat", "id": 42})
    transport.queue(201, {
        "number": 24,
        "node_id": "I_24",
        "html_url": "https://github.com/acme/project/issues/24",
    })
    executed = conversation_integrations.execute_request(request["id"])
    assert executed["status"] == "SUCCEEDED"
    assert executed["response"]["external_id"] == "acme/project#24"
    assert executed["response"]["provider_id"] == "GITHUB"
