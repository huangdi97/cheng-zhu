from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from services.product import conversation_integrations, conversations
from services.product.local_markdown_connector import (
    LocalMarkdownDecisionLogAdapter,
    register_local_markdown_adapter_from_env,
)


@pytest.fixture(autouse=True)
def _clean_adapters():
    conversation_integrations.clear_adapters_for_tests()
    yield
    conversation_integrations.clear_adapters_for_tests()


def _connection(ref="provider:local-markdown:env:CHENGZHU_DECISION_LOG_ROOT"):
    return {
        "id": "ccn_local_markdown",
        "provider_id": "LOCAL_MARKDOWN",
        "credential_ref": ref,
        "granted_capabilities": ["decision_log.write"],
        "provider_scopes": ["local.filesystem.markdown.write"],
        "status": "CONNECTED",
        "account_hint": "Decision Log",
    }


def test_local_markdown_scope_is_decision_log_only_and_least_privilege(product_env):
    connection = conversation_integrations.create_connection(
        "LOCAL_MARKDOWN",
        granted_capabilities=["decision_log.write"],
        credential_ref="provider:local-markdown:env:DECISION_ROOT",
    )
    assert connection["provider_scopes"] == ["local.filesystem.markdown.write"]
    assert connection["credential_ref_present"] is True
    assert "credential_ref" not in connection

    with pytest.raises(ValueError, match="provider 不支持 capability"):
        conversation_integrations.create_connection(
            "LOCAL_MARKDOWN",
            granted_capabilities=["docs.read"],
            credential_ref="provider:local-markdown:env:DECISION_ROOT",
        )

    with pytest.raises(ValueError, match="最小权限集合"):
        conversation_integrations.create_connection(
            "LOCAL_MARKDOWN",
            granted_capabilities=["decision_log.write"],
            provider_scopes=["filesystem:*"],
            credential_ref="provider:local-markdown:env:DECISION_ROOT",
        )


def test_local_markdown_health_resolves_root_from_env_without_persisting_path(monkeypatch, tmp_path):
    root = tmp_path / "My Vault"
    root.mkdir()
    monkeypatch.setenv("CHENGZHU_DECISION_LOG_ROOT", str(root))
    adapter = LocalMarkdownDecisionLogAdapter()

    assert adapter.health(None)["ok"] is True
    health = adapter.health(_connection())
    assert health["ok"] is True
    assert health["verify"] == "LOCAL_ROOT_READ_WRITE_PROBE"
    assert health["account_hint"] == "My Vault"
    assert str(root) not in json.dumps(health, ensure_ascii=False)

    with pytest.raises(ValueError, match="credential_ref"):
        adapter.health({**_connection(), "credential_ref": str(root)})


def test_local_markdown_rejects_target_escape_and_non_markdown_before_write(monkeypatch, tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("CHENGZHU_DECISION_LOG_ROOT", str(root))
    adapter = LocalMarkdownDecisionLogAdapter()

    base = {
        "connection": _connection(),
        "capability": "decision_log.write",
        "operation": "UPDATE_DECISION_LOG",
        "payload": {"title": "Decision", "content": "Use v2.", "outbound_redaction_applied": False},
        "idempotency_key": "exec-safe",
    }
    traversal = adapter.execute(target="../escape.md", **base)
    assert traversal["ok"] is False
    assert traversal["retry_safe"] is True
    assert traversal["phase"] == "TARGET_VALIDATION_PRE_WRITE"
    assert not (tmp_path / "escape.md").exists()

    absolute = adapter.execute(target=str(tmp_path / "outside.md"), **base)
    assert absolute["ok"] is False
    assert not (tmp_path / "outside.md").exists()

    wrong_suffix = adapter.execute(target="Decisions.txt", **base)
    assert wrong_suffix["ok"] is False
    assert not (root / "Decisions.txt").exists()


def test_local_markdown_writes_reviewed_entry_and_marker_deduplicates(monkeypatch, tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("CHENGZHU_DECISION_LOG_ROOT", str(root))
    adapter = LocalMarkdownDecisionLogAdapter()

    kwargs = {
        "connection": _connection(),
        "capability": "decision_log.write",
        "operation": "UPDATE_DECISION_LOG",
        "target": "Projects/Alpha/Decisions.md",
        "payload": {
            "title": "Architecture Review · Decision Log Draft",
            "content": "- offline migration 采用 v2 · state=AGREED",
            "outbound_redaction_applied": False,
        },
        "idempotency_key": "audit-123",
    }
    first = adapter.execute(**kwargs)
    assert first["ok"] is True
    assert first["deduplicated"] is False
    assert first["target"] == "Projects/Alpha/Decisions.md"
    assert first["provider_idempotency"] == "MARKER_IN_FILE"

    target = root / "Projects" / "Alpha" / "Decisions.md"
    body = target.read_text(encoding="utf-8")
    assert "<!-- chengzhu-execution:audit-123 -->" in body
    assert "Architecture Review · Decision Log Draft" in body
    assert "offline migration 采用 v2" in body
    assert str(root) not in json.dumps(first, ensure_ascii=False)

    second = adapter.execute(**kwargs)
    assert second["ok"] is True
    assert second["deduplicated"] is True
    assert target.read_text(encoding="utf-8") == body


def test_local_markdown_never_writes_silently_mutated_reviewed_payload(monkeypatch, tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("CHENGZHU_DECISION_LOG_ROOT", str(root))
    adapter = LocalMarkdownDecisionLogAdapter()

    result = adapter.execute(
        connection=_connection(),
        capability="decision_log.write",
        operation="UPDATE_DECISION_LOG",
        target="decisions.md",
        payload={
            "title": "Reviewed decision",
            "content": "[REDACTED_SECRET]",
            "outbound_redaction_applied": True,
        },
        idempotency_key="redacted",
    )
    assert result["ok"] is False
    assert result["retry_safe"] is False
    assert "重新审核" in result["error"]
    assert not (root / "decisions.md").exists()


def test_local_markdown_registration_is_explicit_opt_in(product_env, monkeypatch):
    monkeypatch.delenv("CHENGZHU_LOCAL_MARKDOWN_CONNECTOR_ENABLE", raising=False)
    assert register_local_markdown_adapter_from_env()["registered"] is False
    local = next(
        row for row in conversation_integrations.catalog()
        if row["provider_id"] == "LOCAL_MARKDOWN"
    )
    assert local["adapter_available"] is False
    assert local["capabilities"] == ["decision_log.write"]

    monkeypatch.setenv("CHENGZHU_LOCAL_MARKDOWN_CONNECTOR_ENABLE", "1")
    registered = register_local_markdown_adapter_from_env()
    assert registered["registered"] is True
    assert registered["provider_scope"] == "local.filesystem.markdown.write"
    local = next(
        row for row in conversation_integrations.catalog()
        if row["provider_id"] == "LOCAL_MARKDOWN"
    )
    assert local["adapter_available"] is True


def test_local_markdown_runs_through_reviewed_two_step_execution_boundary(product_env, monkeypatch, tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("CHENGZHU_DECISION_LOG_ROOT", str(root))
    adapter = LocalMarkdownDecisionLogAdapter()
    conversation_integrations.register_adapter(adapter)

    connection = conversation_integrations.create_connection(
        "LOCAL_MARKDOWN",
        display_name="Obsidian Decision Log",
        granted_capabilities=["decision_log.write"],
        credential_ref="provider:local-markdown:env:CHENGZHU_DECISION_LOG_ROOT",
    )
    connected = conversation_integrations.verify_and_connect(connection["id"])
    assert connected["status"] == "CONNECTED"
    assert connected["account_hint"] == "vault"

    space = conversations.create_space("Design Review", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    decision = conversations.add_item(
        session["id"],
        item_type="Decision",
        title="采用方案 B",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "explicit reviewed decision"}],
    )
    conversations.review_item(decision["id"], "CONFIRM")
    conversations.end_session(session["id"])
    draft = conversations.derived_writeback_draft(
        session["id"], "UPDATE_DECISION_LOG_DRAFT"
    )
    conversations.review_draft_action(draft["id"], "APPROVE")

    request = conversation_integrations.request_execution(
        draft["id"], connection["id"], target="Architecture/Decisions.md"
    )
    assert request["status"] == "PENDING"
    assert request["capability"] == "decision_log.write"
    assert request["operation"] == "UPDATE_DECISION_LOG"

    executed = conversation_integrations.execute_request(request["id"])
    assert executed["status"] == "SUCCEEDED"
    assert executed["response"]["provider_id"] == "LOCAL_MARKDOWN"
    assert executed["response"]["target"] == "Architecture/Decisions.md"
    assert executed["response"]["reviewed_payload_unchanged"] is True
    assert (root / "Architecture" / "Decisions.md").exists()

    replay = conversation_integrations.execute_request(request["id"])
    assert replay["status"] == "SUCCEEDED"
    text = (root / "Architecture" / "Decisions.md").read_text(encoding="utf-8")
    assert text.count(f"<!-- chengzhu-execution:{request['idempotency_key']} -->") == 1


def test_local_markdown_post_replace_exception_becomes_unknown_outcome(product_env, monkeypatch, tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("CHENGZHU_DECISION_LOG_ROOT", str(root))
    adapter = LocalMarkdownDecisionLogAdapter()
    conversation_integrations.register_adapter(adapter)

    connection = conversation_integrations.create_connection(
        "LOCAL_MARKDOWN",
        granted_capabilities=["decision_log.write"],
        credential_ref="provider:local-markdown:env:CHENGZHU_DECISION_LOG_ROOT",
    )
    conversation_integrations.verify_and_connect(connection["id"])

    space = conversations.create_space("Unknown Local Outcome", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    conversations.end_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"],
        kind="UPDATE_DECISION_LOG_DRAFT",
        title="Decision",
        content="- reviewed",
    )
    conversations.review_draft_action(draft["id"], "APPROVE")
    request = conversation_integrations.request_execution(
        draft["id"], connection["id"], target="decisions.md"
    )

    real_replace = os.replace

    def replace_then_raise(src, dst):
        real_replace(src, dst)
        raise RuntimeError("simulated crash after atomic replace")

    monkeypatch.setattr("services.product.local_markdown_connector.os.replace", replace_then_raise)
    unknown = conversation_integrations.execute_request(request["id"])
    assert unknown["status"] == "UNKNOWN_OUTCOME"
    assert (root / "decisions.md").exists()
    with pytest.raises(ValueError, match="必须先在 provider 侧核对"):
        conversation_integrations.execute_request(request["id"])
