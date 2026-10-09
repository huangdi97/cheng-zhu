"""Conversation connector runtime: no fake production providers, explicit capability/audit."""
from __future__ import annotations

import pytest

from services.product import conversation_connectors, conversations
from services.storage import product as store


class FakeAdapter:
    provider = "fake-work"

    def __init__(self):
        self.capabilities = {"calendar.read", "docs.read", "mail.send", "task.create"}
        self.ok = True
        self.read_rows = [{
            "external_id": "evt-1",
            "title": "Architecture Review",
            "excerpt": "Agenda: offline migration; rollback owner unresolved.",
            "visibility": "PRIVATE",
        }]
        self.executions: list[tuple[str, dict]] = []
        self.fail_execute = False

    def health(self):
        return {"ok": self.ok, "provider": self.provider}

    def read_context(self, capability, query):
        assert capability in self.capabilities
        return list(self.read_rows)

    def execute(self, capability, payload):
        self.executions.append((capability, dict(payload)))
        if self.fail_execute:
            raise RuntimeError("provider rejected request")
        return {
            "external_ref": f"fake:{capability}:{len(self.executions)}",
            "ok": True,
            "nested": {"access_token": "provider-secret", "safe": "visible"},
        }


@pytest.fixture(autouse=True)
def connector_registry():
    conversation_connectors.reset_adapters_for_tests()
    yield
    conversation_connectors.reset_adapters_for_tests()


def test_schema_v8_adds_connector_and_execution_tables(product_env):
    assert store.schema_version() == 8
    assert store.select("conversation_connector") == []
    assert store.select("conversation_external_execution") == []


def test_connector_cannot_claim_connected_without_real_adapter(product_env):
    with pytest.raises(ValueError, match="没有真实 runtime adapter"):
        conversation_connectors.connect(
            "missing-provider",
            capabilities=["calendar.read"],
        )


def test_connector_metadata_excludes_secrets_and_reports_capability_health(product_env):
    fake = FakeAdapter()
    conversation_connectors.register_adapter(fake)

    connected = conversation_connectors.connect(
        fake.provider,
        label="Work Account",
        capabilities=["calendar.read", "mail.send"],
        scopes=["calendar.readonly", "mail.send"],
        metadata={
            "account_hint": "user@example.invalid",
            "access_token": "must-not-persist",
            "api_key": "must-not-persist",
            "nested": {"authorization": "Bearer hidden", "safe": "ok"},
        },
    )
    assert connected["status"] == "CONNECTED"
    assert connected["metadata"]["account_hint"] == "user@example.invalid"
    assert "access_token" not in connected["metadata"]
    assert "api_key" not in connected["metadata"]
    assert "authorization" not in connected["metadata"]["nested"]
    assert connected["metadata"]["nested"]["safe"] == "ok"

    status = conversation_connectors.capability_status(["calendar.read", "mail.send"])
    assert status["ok"] is True
    assert status["resolved"]["calendar.read"] == connected["id"]
    assert conversation_connectors.capability_status(["issue.create"])["ok"] is False


def test_preflight_and_pack_freeze_real_connector_read_context(product_env):
    fake = FakeAdapter()
    conversation_connectors.register_adapter(fake)
    connector = conversation_connectors.connect(
        fake.provider,
        label="Work",
        capabilities=["calendar.read", "docs.read"],
    )

    space = conversations.create_space("Architecture", "DESIGN_REVIEW")
    session = conversations.create_session(
        space["id"],
        consent_ack=True,
        policy={"connector_permissions": ["calendar.read"]},
    )
    check = conversations.preflight(session["id"])
    assert check["connector_runtime"]["ok"] is True
    assert check["connector_runtime"]["resolved"]["calendar.read"] == connector["id"]
    assert not any(x["key"] == "connector_runtime" for x in check["blockers"])

    started = conversations.start_session(session["id"])
    frozen = started["pack"]["payload"]["connector_context"]
    assert frozen[0]["title"] == "Architecture Review"
    assert frozen[0]["capability"] == "calendar.read"
    assert frozen[0]["connector_id"] == connector["id"]
    assert frozen[0]["content_hash"]
    assert "token" not in repr(frozen).lower()

    asked = conversations.ask(session["id"], "rollback owner")
    assert asked["grounded"] is True
    assert asked["truth_confirmed"] is False
    assert asked["matches"][0]["kind"] == "CONNECTOR_CONTEXT"
    assert asked["matches"][0]["authority"] == "EXTERNAL_REFERENCE"
    assert asked["matches"][0]["source_refs"][0]["connector_id"] == connector["id"]

    live_context = conversations.session_context(session["id"])
    assert live_context["connector_context"][0]["title"] == "Architecture Review"
    assert "excerpt" not in live_context["connector_context"][0]
    assert live_context["connector_runtime"]["resolved"]["calendar.read"] == connector["id"]

    fake.read_rows = [{
        "external_id": "evt-2",
        "title": "Changed after start",
        "excerpt": "must not rewrite old pack",
    }]
    same_pack = conversations.freeze_pack(session["id"])
    assert same_pack["payload"]["connector_context"][0]["title"] == "Architecture Review"


def test_preflight_fails_closed_for_missing_or_unsupported_connector_capability(product_env):
    fake = FakeAdapter()
    conversation_connectors.register_adapter(fake)
    conversation_connectors.connect(fake.provider, capabilities=["calendar.read"])

    space = conversations.create_space("Client", "CLIENT_CALL")
    missing = conversations.create_session(
        space["id"],
        consent_ack=True,
        policy={"connector_permissions": ["mail.read"]},
    )
    check = conversations.preflight(missing["id"])
    assert check["connector_runtime"]["ok"] is False
    assert "mail.read" in check["connector_runtime"]["missing"]
    assert any(x["key"] == "connector_runtime" for x in check["blockers"])
    with pytest.raises(ValueError, match="mail.read"):
        conversations.start_session(missing["id"])

    unsupported = conversations.create_session(
        space["id"],
        consent_ack=True,
        policy={"connector_permissions": ["made.up"]},
    )
    check2 = conversations.preflight(unsupported["id"])
    assert check2["connector_runtime"]["ok"] is False
    assert any(x["key"] == "connector_runtime" for x in check2["blockers"])


def test_external_execution_requires_approved_draft_permission_and_real_connector(product_env):
    fake = FakeAdapter()
    conversation_connectors.register_adapter(fake)
    connector = conversation_connectors.connect(
        fake.provider,
        label="Mail",
        capabilities=["mail.send"],
    )

    space = conversations.create_space("Client", "CLIENT_CALL")
    session = conversations.create_session(
        space["id"],
        consent_ack=True,
        policy={
            "external_writeback": "REVIEW_REQUIRED",
            "connector_permissions": ["mail.send"],
        },
    )
    conversations.start_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"],
        kind="FOLLOWUP_EMAIL_DRAFT",
        title="Follow-up",
        content="Thanks. Next step: confirm rollback owner.",
        target="client@example.invalid",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "reviewed"}],
    )

    with pytest.raises(ValueError, match="APPROVED"):
        conversation_connectors.execute_draft_action(draft["id"], connector["id"])

    approved = conversations.review_draft_action(draft["id"], "APPROVE")
    assert approved["status"] == "APPROVED"
    execution = conversation_connectors.execute_draft_action(draft["id"], connector["id"])
    assert execution["status"] == "SUCCEEDED"
    assert execution["external_ref"].startswith("fake:mail.send:")
    assert "access_token" not in execution["result"]["nested"]
    assert execution["result"]["nested"]["safe"] == "visible"
    assert fake.executions[0][0] == "mail.send"

    replay = conversation_connectors.execute_draft_action(draft["id"], connector["id"])
    assert replay["status"] == "SUCCEEDED"
    assert replay["id"] == execution["id"]
    assert replay["idempotent_replay"] is True
    assert len(fake.executions) == 1


def test_external_execution_failure_is_audited_without_rewriting_draft_truth(product_env):
    fake = FakeAdapter()
    fake.fail_execute = True
    conversation_connectors.register_adapter(fake)
    connector = conversation_connectors.connect(fake.provider, capabilities=["task.create"])

    space = conversations.create_space("Sync", "PROJECT_SYNC")
    session = conversations.create_session(
        space["id"],
        consent_ack=True,
        policy={
            "external_writeback": "REVIEW_REQUIRED",
            "connector_permissions": ["task.create"],
        },
    )
    conversations.start_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"],
        kind="CREATE_TASK_DRAFT",
        title="Task",
        content="Run rollback drill",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "reviewed"}],
    )
    conversations.review_draft_action(draft["id"], "APPROVE")

    execution = conversation_connectors.execute_draft_action(draft["id"], connector["id"])
    assert execution["status"] == "FAILED"
    assert "provider rejected request" in execution["error"]
    assert conversations.list_draft_actions(space["id"])[0]["status"] == "APPROVED"
    assert conversation_connectors.list_executions(draft["id"])[0]["id"] == execution["id"]


def test_writeback_capability_must_be_frozen_in_session_policy(product_env):
    fake = FakeAdapter()
    conversation_connectors.register_adapter(fake)
    connector = conversation_connectors.connect(fake.provider, capabilities=["mail.send"])

    space = conversations.create_space("No Write Permission", "CLIENT_CALL")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"],
        kind="FOLLOWUP_EMAIL_DRAFT",
        title="Follow-up",
        content="Hello",
    )
    conversations.review_draft_action(draft["id"], "APPROVE")

    with pytest.raises(ValueError, match="未授权 connector capability"):
        conversation_connectors.execute_draft_action(draft["id"], connector["id"])
