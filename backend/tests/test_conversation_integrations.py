"""v2.0 external integration boundary: fail-closed accounts, frozen sources and audited execution."""
from __future__ import annotations

import threading
import time

import pytest

from services.product import conversation_integrations, conversations
from services.storage import product as store


class FakeAdapter:
    provider_id = "MCP"

    def __init__(self, capabilities=None):
        self.capabilities = set(capabilities or {
            "calendar.read",
            "docs.read",
            "email.send",
            "task.create",
            "issue.create",
            "decision_log.write",
        })
        self.healthy = True
        self.fail_execute = False
        self.explicit_failure = False
        self.retry_safe_failure = False
        self.missing_ok = False
        self.execute_calls = 0
        self.read_calls = []
        self.items = {
            "calendar.read": [{
                "external_kind": "CALENDAR_EVENT",
                "external_id": "event-1",
                "title": "Architecture review",
                "excerpt": "Q4 migration benchmark validated 10x data scale; rollback owner remains open.",
                "occurred_at": 1_800_000_000.0,
                "source_url": "https://calendar.example/event/1?secret=query",
                "metadata": {"organizer": "Alex", "access_token": "must-not-persist"},
            }],
            "docs.read": [{
                "external_kind": "DOCUMENT",
                "external_id": "doc-1",
                "title": "Migration notes",
                "excerpt": "The reviewed plan prefers offline migration v2.",
                "source_url": "https://docs.example/doc/1#private",
                "metadata": {"safe": "yes"},
            }],
        }

    def health(self, connection=None):
        return {"ok": self.healthy, "label": "Fake MCP"} if self.healthy else {"ok": False, "error": "adapter down"}

    def read_context(self, *, connection, capability, query, cursor, limit):
        self.read_calls.append({"capability": capability, "cursor": cursor, "query": dict(query)})
        return {"items": list(self.items.get(capability, []))[:limit], "next_cursor": f"{capability}:cursor-1"}

    def execute(self, *, connection, capability, operation, target, payload, idempotency_key):
        self.execute_calls += 1
        if self.fail_execute:
            raise RuntimeError("transport timed out after provider may have accepted request")
        if self.missing_ok:
            return {"external_id": "ambiguous-1", "note": "provider omitted explicit outcome"}
        if self.explicit_failure:
            return {
                "ok": False,
                "error": "provider explicitly rejected request",
                "retry_safe": self.retry_safe_failure,
            }
        return {
            "ok": True,
            "external_id": f"{operation.lower()}-1",
            "target": target,
            "idempotency_key": idempotency_key,
            "access_token": "must-not-leak",
            "nested": {"authorization": "must-not-leak", "safe": "kept"},
        }


@pytest.fixture(autouse=True)
def _clean_integration_registry():
    conversation_integrations.clear_adapters_for_tests()
    yield
    conversation_integrations.clear_adapters_for_tests()


def _connected(adapter: FakeAdapter, capabilities: list[str]):
    conversation_integrations.register_adapter(adapter)
    connection = conversation_integrations.create_connection(
        "MCP",
        display_name="Work MCP",
        granted_capabilities=capabilities,
        provider_scopes=["server-defined"],
        credential_ref="plugin:mcp/work",
        account_hint="work@example.test",
    )
    return conversation_integrations.verify_and_connect(connection["id"])


def test_default_boundary_is_fail_closed_and_never_accepts_raw_credentials(product_env):
    catalog = conversation_integrations.catalog()
    assert catalog and all(item["adapter_available"] is False for item in catalog)

    with pytest.raises(ValueError, match="opaque reference"):
        conversation_integrations.create_connection(
            "MCP",
            granted_capabilities=["calendar.read"],
            credential_ref="ya29.this-is-a-token",
        )

    connection = conversation_integrations.create_connection(
        "MCP",
        granted_capabilities=["calendar.read"],
        credential_ref="plugin:mcp/work",
    )
    assert connection["status"] == "DISCONNECTED"
    assert connection["credential_ref_present"] is True
    assert "credential_ref" not in connection

    with pytest.raises(ValueError, match="adapter 未接线"):
        conversation_integrations.verify_and_connect(connection["id"])

    resolved = conversation_integrations.resolve_session_permissions(["calendar.read"])
    assert resolved["ok"] is False
    assert resolved["blocked"] == [{"capability": "calendar.read", "reason": "NO_CONNECTED_ACCOUNT"}]




def test_provider_scopes_are_derived_and_exact_least_privilege(product_env):
    google = conversation_integrations.create_connection(
        "GOOGLE_MAIL",
        granted_capabilities=["mail.read", "email.send"],
        credential_ref="provider:google/work",
    )
    assert google["provider_scopes"] == [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    ]

    with pytest.raises(ValueError, match="最小权限集合"):
        conversation_integrations.create_connection(
            "GOOGLE_MAIL",
            granted_capabilities=["mail.read"],
            provider_scopes=["https://mail.google.com/"],
            credential_ref="provider:google/broad",
        )

    mcp = conversation_integrations.create_connection(
        "MCP",
        granted_capabilities=["calendar.read"],
        credential_ref="plugin:mcp/work",
    )
    assert mcp["provider_scopes"] == ["server-defined"]

    with pytest.raises(ValueError, match="server-defined"):
        conversation_integrations.create_connection(
            "MCP",
            granted_capabilities=["calendar.read"],
            provider_scopes=["calendar.read"],
            credential_ref="plugin:mcp/bad",
        )


def test_connected_account_requires_exact_grants_and_session_permissions_remain_read_only(product_env):
    adapter = FakeAdapter({"calendar.read", "email.send"})
    connection = _connected(adapter, ["calendar.read", "email.send"])
    assert connection["status"] == "CONNECTED"

    read = conversation_integrations.resolve_session_permissions(["calendar.read"])
    assert read["ok"] is True
    assert read["grants"][0]["connection_id"] == connection["id"]
    assert read["grants"][0]["provider_id"] == "MCP"

    write = conversation_integrations.resolve_session_permissions(["email.send"])
    assert write["ok"] is False
    assert write["blocked"] == [{
        "capability": "email.send",
        "reason": "WRITE_REQUIRES_EXPLICIT_EXECUTION_FLOW",
    }]

    missing = conversation_integrations.resolve_session_permissions(["docs.read"])
    assert missing["ok"] is False
    assert missing["blocked"][0]["reason"] == "NO_CONNECTED_ACCOUNT"


def test_sync_creates_immutable_idempotent_snapshots_and_sanitizes_metadata(product_env):
    adapter = FakeAdapter({"calendar.read"})
    connection = _connected(adapter, ["calendar.read"])
    space = conversations.create_space("Connector Space", "PROJECT_SYNC")

    first = conversation_integrations.sync_connection(connection["id"], space["id"], capabilities=["calendar.read"])
    assert len(first["snapshots"]) == 1
    snapshot = first["snapshots"][0]
    assert snapshot["source_url"] == "https://calendar.example/event/1"
    assert "access_token" not in snapshot["metadata"]

    second = conversation_integrations.sync_connection(connection["id"], space["id"], capabilities=["calendar.read"])
    assert second["snapshots"][0]["id"] == snapshot["id"]
    assert len(conversation_integrations.list_snapshots(space["id"])) == 1

    adapter.items["calendar.read"][0] = {
        **adapter.items["calendar.read"][0],
        "excerpt": "Replacement says 50x data scale; this must become a new immutable snapshot.",
    }
    third = conversation_integrations.sync_connection(connection["id"], space["id"], capabilities=["calendar.read"])
    assert third["snapshots"][0]["id"] != snapshot["id"]
    assert len(conversation_integrations.list_snapshots(space["id"])) == 2




def test_same_external_content_is_isolated_per_space_and_selection_cannot_cross_space(product_env):
    adapter = FakeAdapter({"calendar.read"})
    connection = _connected(adapter, ["calendar.read"])
    space_a = conversations.create_space("Space A", "PROJECT_SYNC")
    space_b = conversations.create_space("Space B", "PROJECT_SYNC")

    snap_a = conversation_integrations.sync_connection(
        connection["id"], space_a["id"], capabilities=["calendar.read"]
    )["snapshots"][0]
    snap_b = conversation_integrations.sync_connection(
        connection["id"], space_b["id"], capabilities=["calendar.read"]
    )["snapshots"][0]

    assert snap_a["id"] != snap_b["id"]
    assert snap_a["content_hash"] == snap_b["content_hash"]
    assert [x["id"] for x in conversation_integrations.list_snapshots(space_a["id"])] == [snap_a["id"]]
    assert [x["id"] for x in conversation_integrations.list_snapshots(space_b["id"])] == [snap_b["id"]]

    with pytest.raises(ValueError, match="不属于当前 Space"):
        conversations.update_space(
            space_b["id"],
            {"selected_connector_snapshot_ids": [snap_a["id"]]},
        )
    selected = conversations.update_space(
        space_b["id"],
        {"selected_connector_snapshot_ids": [snap_b["id"], snap_b["id"]]},
    )
    assert selected["selected_connector_snapshot_ids"] == [snap_b["id"]]


def test_provider_content_hash_cannot_override_chengzhu_canonical_snapshot_identity(product_env):
    adapter = FakeAdapter({"calendar.read"})
    adapter.items["calendar.read"][0]["content_hash"] = "provider-fixed-hash"
    connection = _connected(adapter, ["calendar.read"])
    space = conversations.create_space("Canonical Hash", "PROJECT_SYNC")

    first = conversation_integrations.sync_connection(
        connection["id"], space["id"], capabilities=["calendar.read"]
    )["snapshots"][0]
    assert first["metadata"]["provider_content_hash"] == "provider-fixed-hash"
    assert first["content_hash"] != "provider-fixed-hash"

    adapter.items["calendar.read"][0] = {
        **adapter.items["calendar.read"][0],
        "excerpt": "Provider changed the content but incorrectly reused the same provider hash.",
        "content_hash": "provider-fixed-hash",
    }
    second = conversation_integrations.sync_connection(
        connection["id"], space["id"], capabilities=["calendar.read"]
    )["snapshots"][0]
    assert second["id"] != first["id"]
    assert second["content_hash"] != first["content_hash"]
    assert second["metadata"]["provider_content_hash"] == "provider-fixed-hash"


def test_sync_cursors_are_isolated_per_capability(product_env):
    adapter = FakeAdapter({"calendar.read", "docs.read"})
    connection = _connected(adapter, ["calendar.read", "docs.read"])
    space = conversations.create_space("Cursor Isolation", "PROJECT_SYNC")

    conversation_integrations.sync_connection(
        connection["id"],
        space["id"],
        capabilities=["calendar.read", "docs.read"],
    )
    first_calls = adapter.read_calls[-2:]
    assert {call["capability"]: call["cursor"] for call in first_calls} == {
        "calendar.read": "",
        "docs.read": "",
    }
    saved = next(x for x in conversation_integrations.list_connections() if x["id"] == connection["id"])
    assert saved["sync_cursors"] == {
        "calendar.read": "calendar.read:cursor-1",
        "docs.read": "docs.read:cursor-1",
    }
    assert saved["sync_cursor"] == ""

    conversation_integrations.sync_connection(
        connection["id"], space["id"], capabilities=["calendar.read"]
    )
    assert adapter.read_calls[-1]["cursor"] == "calendar.read:cursor-1"

    conversation_integrations.sync_connection(
        connection["id"], space["id"], capabilities=["docs.read"]
    )
    assert adapter.read_calls[-1]["cursor"] == "docs.read:cursor-1"


def test_new_space_cannot_import_existing_connector_snapshot_by_id(product_env):
    adapter = FakeAdapter({"calendar.read"})
    connection = _connected(adapter, ["calendar.read"])
    existing = conversations.create_space("Existing", "PROJECT_SYNC")
    snapshot = conversation_integrations.sync_connection(
        connection["id"], existing["id"], capabilities=["calendar.read"]
    )["snapshots"][0]

    with pytest.raises(ValueError, match="新建 Space 不能直接引用"):
        conversations.create_space(
            "New",
            "PROJECT_SYNC",
            selected_connector_snapshot_ids=[snapshot["id"]],
        )


def test_selected_snapshot_is_frozen_into_pack_and_manual_ask_keeps_reference_authority(product_env):
    adapter = FakeAdapter({"calendar.read"})
    connection = _connected(adapter, ["calendar.read"])
    space = conversations.create_space("Architecture", "DESIGN_REVIEW")
    synced = conversation_integrations.sync_connection(connection["id"], space["id"], capabilities=["calendar.read"])
    snapshot = synced["snapshots"][0]
    conversations.update_space(space["id"], {"selected_connector_snapshot_ids": [snapshot["id"]]})

    session = conversations.create_session(
        space["id"],
        consent_ack=True,
        policy={"connector_permissions": ["calendar.read"]},
    )
    check = conversations.preflight(session["id"])
    assert check["blockers"] == []
    assert check["pack_preview"]["connector_snapshots"][0]["id"] == snapshot["id"]
    assert check["connector_runtime"]["grants"][0]["connection_id"] == connection["id"]

    started = conversations.start_session(session["id"])
    frozen = started["pack"]["payload"]["connector_snapshots"][0]
    assert frozen["id"] == snapshot["id"]
    assert frozen["provider_id"] == "MCP"

    result = conversations.ask(session["id"], "10x data scale")
    assert result["grounded"] is True
    assert result["truth_confirmed"] is False
    assert result["matches"][0]["kind"] == "CONNECTOR_SNAPSHOT"
    assert result["matches"][0]["authority"] == "REFERENCE_SOURCE"
    assert result["matches"][0]["source_refs"][0]["content_hash"] == snapshot["content_hash"]

    adapter.items["calendar.read"][0] = {
        **adapter.items["calendar.read"][0],
        "excerpt": "New sync says 50x data scale.",
    }
    conversation_integrations.sync_connection(connection["id"], space["id"], capabilities=["calendar.read"])
    # Already-started session is pinned to the old immutable snapshot.
    assert conversations.ask(session["id"], "10x data scale")["grounded"] is True
    assert conversations.ask(session["id"], "50x data scale")["grounded"] is False


def test_approved_draft_requires_request_then_second_execute_and_is_idempotent(product_env):
    adapter = FakeAdapter({"email.send"})
    connection = _connected(adapter, ["email.send"])
    space = conversations.create_space("Writeback", "CLIENT_CALL")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"],
        kind="FOLLOWUP_EMAIL_DRAFT",
        title="Follow-up",
        content="Thanks — here are the reviewed next steps.",
        target="alex@example.test",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "reviewed next steps"}],
    )
    approved = conversations.review_draft_action(draft["id"], "APPROVE")
    assert approved["status"] == "APPROVED"
    assert adapter.execute_calls == 0

    request = conversation_integrations.request_execution(
        draft["id"],
        connection["id"],
        target="alex@example.test",
    )
    assert request["status"] == "PENDING"
    assert adapter.execute_calls == 0

    # Request creation is idempotent.
    same = conversation_integrations.request_execution(
        draft["id"],
        connection["id"],
        target="alex@example.test",
    )
    assert same["id"] == request["id"]

    executed = conversation_integrations.execute_request(request["id"])
    assert executed["status"] == "SUCCEEDED"
    assert adapter.execute_calls == 1
    assert executed["response"]["external_id"] == "send_email-1"
    assert "access_token" not in executed["response"]
    assert "authorization" not in executed["response"]["nested"]
    assert executed["response"]["nested"]["safe"] == "kept"

    replay = conversation_integrations.execute_request(request["id"])
    assert replay["status"] == "SUCCEEDED"
    assert adapter.execute_calls == 1


def test_execution_without_write_grant_blocks_and_ambiguous_transport_failure_is_not_retryable(product_env):
    read_adapter = FakeAdapter({"calendar.read"})
    read_connection = _connected(read_adapter, ["calendar.read"])
    space = conversations.create_space("Blocked Write", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"],
        kind="FOLLOWUP_EMAIL_DRAFT",
        title="Follow-up",
        content="body",
    )
    conversations.review_draft_action(draft["id"], "APPROVE")

    blocked = conversation_integrations.request_execution(draft["id"], read_connection["id"])
    assert blocked["status"] == "BLOCKED"
    with pytest.raises(ValueError, match="Connection 没有真实可用 capability"):
        conversation_integrations.execute_request(blocked["id"])

    conversation_integrations.clear_adapters_for_tests()
    ambiguous = FakeAdapter({"email.send"})
    ambiguous.fail_execute = True
    write_connection = _connected(ambiguous, ["email.send"])
    request = conversation_integrations.request_execution(draft["id"], write_connection["id"])
    unknown = conversation_integrations.execute_request(request["id"])
    assert unknown["status"] == "UNKNOWN_OUTCOME"
    assert "transport timed out" in unknown["error"]
    assert ambiguous.execute_calls == 1

    with pytest.raises(ValueError, match="outcome 不确定"):
        conversation_integrations.execute_request(request["id"])
    assert ambiguous.execute_calls == 1




def test_unknown_outcome_requires_explicit_provider_side_reconciliation(product_env):
    adapter = FakeAdapter({"email.send"})
    adapter.fail_execute = True
    connection = _connected(adapter, ["email.send"])
    space = conversations.create_space("Reconcile", "CLIENT_CALL")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])

    def approved(title):
        draft = conversations.create_draft_action(
            session["id"], kind="FOLLOWUP_EMAIL_DRAFT", title=title, content="body",
        )
        conversations.review_draft_action(draft["id"], "APPROVE")
        return draft

    succeeded_draft = approved("Ambiguous but applied")
    succeeded_request = conversation_integrations.request_execution(succeeded_draft["id"], connection["id"])
    unknown = conversation_integrations.execute_request(succeeded_request["id"])
    assert unknown["status"] == "UNKNOWN_OUTCOME"

    with pytest.raises(ValueError, match="核对说明"):
        conversation_integrations.reconcile_unknown_outcome(
            unknown["id"], "CONFIRMED_SUCCEEDED", note="",
        )

    reconciled = conversation_integrations.reconcile_unknown_outcome(
        unknown["id"],
        "CONFIRMED_SUCCEEDED",
        note="Checked provider sent-items; message exists.",
        provider_reference="provider-message-123",
    )
    assert reconciled["status"] == "SUCCEEDED"
    assert reconciled["response"]["ok"] is True
    assert reconciled["response"]["reconciliation"]["source"] == "USER_REPORTED_PROVIDER_CHECK"
    assert reconciled["response"]["reconciliation"]["provider_reference"] == "provider-message-123"
    calls = adapter.execute_calls
    assert conversation_integrations.execute_request(reconciled["id"])["status"] == "SUCCEEDED"
    assert adapter.execute_calls == calls

    retry_draft = approved("Ambiguous but not applied")
    retry_request = conversation_integrations.request_execution(retry_draft["id"], connection["id"])
    unknown_retry = conversation_integrations.execute_request(retry_request["id"])
    assert unknown_retry["status"] == "UNKNOWN_OUTCOME"

    reconciled_retry = conversation_integrations.reconcile_unknown_outcome(
        unknown_retry["id"],
        "CONFIRMED_NOT_APPLIED",
        note="Checked provider activity log; no message/action was created.",
    )
    assert reconciled_retry["status"] == "FAILED"
    assert reconciled_retry["response"]["retry_safe"] is True
    assert reconciled_retry["response"]["reconciliation"]["outcome"] == "CONFIRMED_NOT_APPLIED"

    adapter.fail_execute = False
    retried = conversation_integrations.execute_request(reconciled_retry["id"])
    assert retried["status"] == "SUCCEEDED"

    with pytest.raises(ValueError, match="只有 UNKNOWN_OUTCOME"):
        conversation_integrations.reconcile_unknown_outcome(
            retried["id"], "CONFIRMED_SUCCEEDED", note="duplicate reconciliation",
        )


def test_external_execution_is_serialized_so_double_execute_calls_provider_once(product_env):
    adapter = FakeAdapter({"email.send"})
    entered = threading.Event()
    release = threading.Event()

    def slow_execute(**kwargs):
        adapter.execute_calls += 1
        entered.set()
        assert release.wait(timeout=2), "test must release provider execution"
        return {"ok": True, "external_id": "only-once"}

    adapter.execute = slow_execute
    connection = _connected(adapter, ["email.send"])
    space = conversations.create_space("Concurrent Execute", "CLIENT_CALL")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"], kind="FOLLOWUP_EMAIL_DRAFT", title="Follow-up", content="body",
    )
    conversations.review_draft_action(draft["id"], "APPROVE")
    request = conversation_integrations.request_execution(draft["id"], connection["id"])

    results = []
    errors = []

    def run():
        try:
            results.append(conversation_integrations.execute_request(request["id"]))
        except Exception as exc:
            errors.append(exc)

    first = threading.Thread(target=run)
    second = threading.Thread(target=run)
    first.start()
    assert entered.wait(timeout=1)
    second.start()
    time.sleep(0.05)
    assert second.is_alive(), "second execute should wait behind the side-effect boundary"
    release.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not errors
    assert len(results) == 2
    assert all(row["status"] == "SUCCEEDED" for row in results)
    assert adapter.execute_calls == 1


def test_external_execution_requires_explicit_ok_and_only_retry_safe_failure_can_retry(product_env):
    adapter = FakeAdapter({"email.send"})
    connection = _connected(adapter, ["email.send"])
    space = conversations.create_space("Execution Semantics", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])

    def approved_draft(title):
        draft = conversations.create_draft_action(
            session["id"], kind="FOLLOWUP_EMAIL_DRAFT", title=title, content="body",
        )
        conversations.review_draft_action(draft["id"], "APPROVE")
        return draft

    missing_ok = approved_draft("Ambiguous envelope")
    adapter.missing_ok = True
    request = conversation_integrations.request_execution(missing_ok["id"], connection["id"])
    unknown = conversation_integrations.execute_request(request["id"])
    assert unknown["status"] == "UNKNOWN_OUTCOME"
    assert "显式 boolean ok" in unknown["error"]
    with pytest.raises(ValueError, match="outcome 不确定"):
        conversation_integrations.execute_request(request["id"])

    adapter.missing_ok = False
    adapter.explicit_failure = True
    adapter.retry_safe_failure = False
    failed_draft = approved_draft("Definitive failure")
    failed_request = conversation_integrations.request_execution(failed_draft["id"], connection["id"])
    failed = conversation_integrations.execute_request(failed_request["id"])
    assert failed["status"] == "FAILED"
    assert failed["response"]["ok"] is False
    assert failed["response"]["retry_safe"] is False
    with pytest.raises(ValueError, match="未声明 retry_safe"):
        conversation_integrations.execute_request(failed_request["id"])

    adapter.retry_safe_failure = True
    retry_draft = approved_draft("Retry safe")
    retry_request = conversation_integrations.request_execution(retry_draft["id"], connection["id"])
    first = conversation_integrations.execute_request(retry_request["id"])
    assert first["status"] == "FAILED"
    assert first["response"]["retry_safe"] is True
    calls_before_retry = adapter.execute_calls

    adapter.explicit_failure = False
    retried = conversation_integrations.execute_request(retry_request["id"])
    assert retried["status"] == "SUCCEEDED"
    assert adapter.execute_calls == calls_before_retry + 1


def test_external_execution_unknown_outcome_never_rewrites_conversation_truth(product_env):
    adapter = FakeAdapter({"email.send"})
    adapter.fail_execute = True
    connection = _connected(adapter, ["email.send"])
    space = conversations.create_space("Truth Isolation", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    decision = conversations.add_item(
        session["id"],
        item_type="Decision",
        title="保留原 Decision",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "明确确认"}],
    )
    reviewed = conversations.review_item(decision["id"], "CONFIRM")
    draft = conversations.create_draft_action(
        session["id"], kind="FOLLOWUP_EMAIL_DRAFT", title="Follow-up", content="body",
    )
    approved = conversations.review_draft_action(draft["id"], "APPROVE")

    request = conversation_integrations.request_execution(approved["id"], connection["id"])
    unknown = conversation_integrations.execute_request(request["id"])
    assert unknown["status"] == "UNKNOWN_OUTCOME"
    assert conversations.require_item(decision["id"])["state"] == reviewed["state"]
    assert store.get("conversation_draft_action", draft["id"])["status"] == "APPROVED"




def test_orphaned_executing_audit_recovers_to_unknown_outcome_after_restart(product_env):
    adapter = FakeAdapter({"email.send"})
    connection = _connected(adapter, ["email.send"])
    space = conversations.create_space("Crash Recovery", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"], kind="FOLLOWUP_EMAIL_DRAFT", title="Follow-up", content="body",
    )
    conversations.review_draft_action(draft["id"], "APPROVE")
    request = conversation_integrations.request_execution(draft["id"], connection["id"])

    # Simulate a process that died after persisting EXECUTING but before a
    # definitive provider outcome reached local storage.
    store.update("conversation_connector_execution", request["id"], {
        "status": "EXECUTING",
        "updated_at": store.now() - 30,
    })
    conversation_integrations._ACTIVE_EXECUTIONS.clear()

    rows = conversation_integrations.list_executions(draft_action_id=draft["id"])
    recovered = next(row for row in rows if row["id"] == request["id"])
    assert recovered["status"] == "UNKNOWN_OUTCOME"
    assert "interrupted" in recovered["error"]

    with pytest.raises(ValueError, match="outcome 不确定"):
        conversation_integrations.execute_request(request["id"])
    assert adapter.execute_calls == 0

    diag = conversation_integrations.diagnostics()
    assert diag["unknown_outcome_count"] == 1


def test_retention_keeps_selected_snapshots_and_execution_audit(product_env):
    adapter = FakeAdapter({"calendar.read", "email.send"})
    connection = _connected(adapter, ["calendar.read", "email.send"])
    space = conversations.create_space("Retention", "PROJECT_SYNC")
    first = conversation_integrations.sync_connection(connection["id"], space["id"], capabilities=["calendar.read"])["snapshots"][0]
    adapter.items["calendar.read"][0] = {
        **adapter.items["calendar.read"][0],
        "external_id": "event-2",
        "title": "Unselected old event",
    }
    second = conversation_integrations.sync_connection(connection["id"], space["id"], capabilities=["calendar.read"])["snapshots"][0]
    conversations.update_space(space["id"], {
        "selected_connector_snapshot_ids": [first["id"]],
        "retention_policy": {
            "preset": "CUSTOM",
            "transcript_days": 30,
            "guidance_days": 30,
            "draft_days": 0,
            "connector_snapshot_days": 0,
            "confirmed_items": "KEEP",
            "audio_retention": "OFF",
        },
    })

    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    audited = conversations.create_draft_action(
        session["id"], kind="FOLLOWUP_EMAIL_DRAFT", title="audited", content="body",
    )
    conversations.review_draft_action(audited["id"], "APPROVE")
    execution = conversation_integrations.request_execution(audited["id"], connection["id"])

    unaudited = conversations.create_draft_action(
        session["id"], kind="CREATE_TASK_DRAFT", title="cleanup me", content="body",
    )
    old = store.now() - 100
    store.update("conversation_connector_snapshot", first["id"], {"created_at": old})
    store.update("conversation_connector_snapshot", second["id"], {"created_at": old})
    store.update("conversation_draft_action", audited["id"], {"created_at": old})
    store.update("conversation_draft_action", unaudited["id"], {"created_at": old})

    preview = conversations.retention_preview(space["id"], now=store.now())
    assert preview["would_delete"]["connector_snapshots"] == 1
    assert preview["would_delete"]["draft_actions"] == 1
    assert preview["kept"]["external_execution_audit"] == "KEEP"

    result = conversations.apply_retention(space["id"], confirm=True)
    assert result["deleted"]["connector_snapshots"] == 1
    assert result["deleted"]["draft_actions"] == 1
    assert store.get("conversation_connector_snapshot", first["id"]) is not None
    assert store.get("conversation_connector_snapshot", second["id"]) is None
    assert store.get("conversation_draft_action", audited["id"]) is not None
    assert store.get("conversation_draft_action", unaudited["id"]) is None
    assert store.get("conversation_connector_execution", execution["id"]) is not None


def test_exports_include_connector_provenance_and_audit_but_never_credential_refs(product_env):
    adapter = FakeAdapter({"calendar.read", "email.send"})
    connection = _connected(adapter, ["calendar.read", "email.send"])
    space = conversations.create_space("Export", "PROJECT_SYNC")
    snapshot = conversation_integrations.sync_connection(
        connection["id"], space["id"], capabilities=["calendar.read"]
    )["snapshots"][0]
    conversations.update_space(space["id"], {"selected_connector_snapshot_ids": [snapshot["id"]]})

    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"], kind="FOLLOWUP_EMAIL_DRAFT", title="Follow-up", content="body",
    )
    conversations.review_draft_action(draft["id"], "APPROVE")
    request = conversation_integrations.request_execution(draft["id"], connection["id"])
    conversation_integrations.execute_request(request["id"])

    space_export = conversations.export_space(space["id"])
    session_export = conversations.export_session(session["id"])
    for exported in (space_export, session_export):
        assert exported["export_manifest"]["contains_external_secrets"] is False
        assert exported["export_manifest"]["credential_refs_exported"] is False
        assert exported["connector_snapshots"]
        assert exported["external_execution_audit"]
        assert exported["connector_connections"]
        assert "credential_ref" not in exported["connector_connections"][0]
        assert "plugin:mcp/work" not in str(exported)
        assert "must-not-leak" not in str(exported)


def test_diagnostics_distinguishes_boundary_from_real_provider_availability(product_env):
    diag = conversations.diagnostics()
    assert diag["schema_version"] == 9
    assert diag["health"]["external_connectors"] == "NOT_CONFIGURED"
    assert diag["health"]["external_writeback_execution"] == "REVIEWED_SECOND_EXPLICIT_EXECUTION_BOUNDARY"
    assert diag["integrations"]["connected_count"] == 0
    assert diag["integrations"]["unknown_outcome_count"] == 0
    assert diag["integrations"]["default"] == "NO_PROVIDER_ADAPTERS_CONFIGURED"

    adapter = FakeAdapter({"calendar.read"})
    _connected(adapter, ["calendar.read"])
    connected = conversations.diagnostics()
    assert connected["health"]["external_connectors"] == "CONNECTED"
    assert connected["integrations"]["connected_count"] == 1
