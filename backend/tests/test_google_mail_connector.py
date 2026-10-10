import base64
import json
from email import policy
from email.parser import BytesParser
from urllib.parse import urlparse

import pytest

from services.product import conversation_integrations, conversations
from services.product.google_mail_connector import (
    GoogleMailProviderError,
    GoogleMailSendAdapter,
    register_google_mail_adapter_from_env,
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
            raise AssertionError(f"Unexpected Gmail request: {method} {url}")
        status, response_headers, payload = self.responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return status, response_headers, payload


def _connection(ref="provider:google-mail:env:CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN"):
    return {
        "id": "ccn_gmail_test",
        "provider_id": "GOOGLE_MAIL",
        "credential_ref": ref,
        "granted_capabilities": ["email.send"],
        "provider_scopes": [
            "email",
            "https://www.googleapis.com/auth/gmail.send",
            "openid",
        ],
        "status": "CONNECTED",
        "account_hint": "sender@example.com",
    }


def test_google_mail_adapter_requires_https_endpoints():
    with pytest.raises(ValueError, match="HTTPS"):
        GoogleMailSendAdapter(api_base="http://gmail.test", transport=FakeTransport())
    with pytest.raises(ValueError, match="HTTPS"):
        GoogleMailSendAdapter(userinfo_url="http://userinfo.test", transport=FakeTransport())


def test_google_mail_catalog_is_send_only_with_identity_scopes(product_env):
    row = next(x for x in conversation_integrations.catalog() if x["provider_id"] == "GOOGLE_MAIL")
    assert row["capabilities"] == ["email.send"]
    assert row["read_capabilities"] == []
    assert row["write_capabilities"] == ["email.send"]
    assert row["identity_scopes"] == ["openid", "email"]
    assert "mail.read" not in row["capabilities"]
    assert "gmail.readonly" not in json.dumps(row)

    connection = conversation_integrations.create_connection(
        "GOOGLE_MAIL",
        granted_capabilities=["email.send"],
        credential_ref="provider:google-mail:env:CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN",
    )
    assert connection["provider_scopes"] == [
        "email",
        "https://www.googleapis.com/auth/gmail.send",
        "openid",
    ]

    with pytest.raises(ValueError, match="最小权限集合"):
        conversation_integrations.create_connection(
            "GOOGLE_MAIL",
            granted_capabilities=["email.send"],
            provider_scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            credential_ref="provider:google-mail:env:CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN",
        )


def test_google_mail_health_uses_oidc_userinfo_without_mailbox_read(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN", "ya29.gmail_test_secret")
    transport = FakeTransport()
    transport.queue(200, {
        "sub": "google-user-1",
        "email": "sender@example.com",
        "email_verified": True,
    })
    adapter = GoogleMailSendAdapter(transport=transport)

    assert adapter.health(None)["runtime"] == "OPT_IN_REAL_PROVIDER"
    health = adapter.health(_connection())
    assert health["ok"] is True
    assert health["account_hint"] == "sender@example.com"
    assert health["provider_user_id"] == "google-user-1"
    assert health["verify"] == "OIDC_USERINFO_IDENTITY_ONLY"
    assert health["send_capability_proof"] == "PENDING_FIRST_EXPLICIT_EXECUTION"

    call = transport.calls[0]
    assert call["method"] == "GET"
    assert urlparse(call["url"]).netloc == "openidconnect.googleapis.com"
    assert call["headers"]["Authorization"] == "Bearer ya29.gmail_test_secret"
    assert "gmail" not in urlparse(call["url"]).path.lower()


def test_google_mail_health_rejects_missing_verified_identity(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN", "ya29.gmail_test_secret")
    transport = FakeTransport()
    transport.queue(200, {"sub": "google-user-1", "email": "sender@example.com", "email_verified": False})
    adapter = GoogleMailSendAdapter(transport=transport)
    health = adapter.health(_connection())
    assert health["ok"] is False
    assert "verified email" in health["error"]


def test_google_mail_rejects_raw_or_missing_credential(monkeypatch):
    adapter = GoogleMailSendAdapter(transport=FakeTransport())
    with pytest.raises(ValueError, match="credential_ref"):
        adapter.health({**_connection(), "credential_ref": "ya29.secret"})
    monkeypatch.delenv("MISSING_GMAIL_TOKEN", raising=False)
    with pytest.raises(ValueError, match="未设置"):
        adapter.health({
            **_connection(),
            "credential_ref": "provider:google-mail:env:MISSING_GMAIL_TOKEN",
        })


def test_google_mail_read_context_is_not_implemented():
    adapter = GoogleMailSendAdapter(transport=FakeTransport())
    with pytest.raises(ValueError, match="send-only"):
        adapter.read_context(
            connection=_connection(),
            capability="mail.read",
            query={},
            cursor="",
            limit=100,
        )


def test_google_mail_send_builds_single_recipient_rfc_message(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN", "ya29.gmail_test_secret")
    transport = FakeTransport()
    transport.queue(200, {"id": "msg-123", "threadId": "thread-456"})
    adapter = GoogleMailSendAdapter(transport=transport)

    result = adapter.execute(
        connection=_connection(),
        capability="email.send",
        operation="SEND_EMAIL",
        target="recipient@example.com",
        payload={
            "title": "Architecture Review · Follow-up",
            "content": "这场之后：\nDecision：采用方案 B",
            "payload": {"external_execution": False},
            "outbound_redaction_applied": False,
        },
        idempotency_key="a" * 64,
    )
    assert result["ok"] is True
    assert result["message_id"] == "msg-123"
    assert result["thread_id"] == "thread-456"
    assert result["provider_idempotency"] == "NONE"
    assert result["recipient"] == "recipient@example.com"
    assert result["sender"] == "sender@example.com"

    call = transport.calls[0]
    assert call["method"] == "POST"
    assert urlparse(call["url"]).path.endswith("/users/me/messages/send")
    request_json = json.loads(call["body"].decode("utf-8"))
    mime_bytes = base64.urlsafe_b64decode(request_json["raw"].encode("ascii"))
    message = BytesParser(policy=policy.default).parsebytes(mime_bytes)
    assert message["From"] == "sender@example.com"
    assert message["To"] == "recipient@example.com"
    assert message["Subject"] == "Architecture Review · Follow-up"
    assert message["X-Chengzhu-Execution-ID"] == "a" * 64
    assert "Decision：采用方案 B" in message.get_content()
    assert "ya29.gmail_test_secret" not in call["body"].decode("utf-8")


@pytest.mark.parametrize("target", [
    "",
    "a@example.com,b@example.com",
    "Name <a@example.com>",
    "a@example.com\r\nBcc: hidden@example.com",
])
def test_google_mail_rejects_ambiguous_or_header_injection_recipient(monkeypatch, target):
    monkeypatch.setenv("CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN", "ya29.gmail_test_secret")
    transport = FakeTransport()
    adapter = GoogleMailSendAdapter(transport=transport)
    result = adapter.execute(
        connection=_connection(),
        capability="email.send",
        operation="SEND_EMAIL",
        target=target,
        payload={"title": "Follow-up", "content": "Body", "outbound_redaction_applied": False},
        idempotency_key="x",
    )
    assert result["ok"] is False
    assert transport.calls == []




@pytest.mark.parametrize(
    ("title", "content", "message"),
    [
        ("x" * 999, "Body", "主题过长"),
        ("Follow-up", "x" * 20_001, "正文超过 20000"),
    ],
)
def test_google_mail_rejects_oversized_reviewed_content_instead_of_truncating(monkeypatch, title, content, message):
    monkeypatch.setenv("CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN", "ya29.gmail_test_secret")
    transport = FakeTransport()
    adapter = GoogleMailSendAdapter(transport=transport)
    result = adapter.execute(
        connection=_connection(),
        capability="email.send",
        operation="SEND_EMAIL",
        target="recipient@example.com",
        payload={
            "title": title,
            "content": content,
            "outbound_redaction_applied": False,
        },
        idempotency_key="x",
    )
    assert result["ok"] is False
    assert message in result["error"]
    assert transport.calls == []


def test_google_mail_blocks_send_if_outbound_redaction_changed_reviewed_draft(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN", "ya29.gmail_test_secret")
    transport = FakeTransport()
    adapter = GoogleMailSendAdapter(transport=transport)
    result = adapter.execute(
        connection=_connection(),
        capability="email.send",
        operation="SEND_EMAIL",
        target="recipient@example.com",
        payload={
            "title": "Follow-up",
            "content": "[REDACTED_SECRET]",
            "outbound_redaction_applied": True,
        },
        idempotency_key="x",
    )
    assert result["ok"] is False
    assert "重新审核" in result["error"]
    assert transport.calls == []


def test_google_mail_definitive_4xx_is_failed_but_server_error_is_ambiguous(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN", "ya29.gmail_test_secret")

    transport = FakeTransport()
    transport.queue(403, GoogleMailProviderError(403, "Gmail HTTP 403: insufficientPermissions"))
    adapter = GoogleMailSendAdapter(transport=transport)
    result = adapter.execute(
        connection=_connection(),
        capability="email.send",
        operation="SEND_EMAIL",
        target="recipient@example.com",
        payload={"title": "Follow-up", "content": "Body", "outbound_redaction_applied": False},
        idempotency_key="x",
    )
    assert result["ok"] is False
    assert result["http_status"] == 403

    transport2 = FakeTransport()
    transport2.queue(503, GoogleMailProviderError(503, "Gmail HTTP 503"))
    adapter2 = GoogleMailSendAdapter(transport=transport2)
    with pytest.raises(GoogleMailProviderError):
        adapter2.execute(
            connection=_connection(),
            capability="email.send",
            operation="SEND_EMAIL",
            target="recipient@example.com",
            payload={"title": "Follow-up", "content": "Body", "outbound_redaction_applied": False},
            idempotency_key="x",
        )


def test_google_mail_registration_is_explicit_opt_in(product_env, monkeypatch):
    conversation_integrations.clear_adapters_for_tests()
    monkeypatch.delenv("CHENGZHU_GOOGLE_MAIL_CONNECTOR_ENABLE", raising=False)
    assert register_google_mail_adapter_from_env()["registered"] is False
    row = next(x for x in conversation_integrations.catalog() if x["provider_id"] == "GOOGLE_MAIL")
    assert row["adapter_available"] is False

    monkeypatch.setenv("CHENGZHU_GOOGLE_MAIL_CONNECTOR_ENABLE", "1")
    registered = register_google_mail_adapter_from_env()
    assert registered["registered"] is True
    assert registered["capabilities"] == ["email.send"]
    assert registered["read_capabilities"] == []
    row = next(x for x in conversation_integrations.catalog() if x["provider_id"] == "GOOGLE_MAIL")
    assert row["adapter_available"] is True


def test_google_mail_reviewed_two_step_execution_succeeds_without_mail_read(product_env, monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN", "ya29.gmail_test_secret")
    transport = FakeTransport()
    adapter = GoogleMailSendAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    connection = conversation_integrations.create_connection(
        "GOOGLE_MAIL",
        display_name="Follow-up Gmail",
        granted_capabilities=["email.send"],
        credential_ref="provider:google-mail:env:CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN",
    )
    transport.queue(200, {"sub": "u1", "email": "sender@example.com", "email_verified": True})
    connected = conversation_integrations.verify_and_connect(connection["id"])
    assert connected["status"] == "CONNECTED"
    assert connected["account_hint"] == "sender@example.com"

    space = conversations.create_space("Client Follow-up", "CLIENT_CALL")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    conversations.end_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"],
        kind="FOLLOWUP_EMAIL_DRAFT",
        title="Client Call · Follow-up",
        content="Thanks — next step is rollout review.",
        payload={"external_execution": False},
    )
    draft = conversations.review_draft_action(draft["id"], "APPROVE")
    assert draft["status"] == "APPROVED"

    # Request creation re-checks current provider health.
    transport.queue(200, {"sub": "u1", "email": "sender@example.com", "email_verified": True})
    execution = conversation_integrations.create_execution_request(
        draft["id"],
        connection["id"],
        target="recipient@example.com",
    )
    assert execution["status"] == "PENDING"
    assert execution["capability"] == "email.send"
    assert execution["operation"] == "SEND_EMAIL"

    # Execute performs another capability/identity health check, then sends.
    transport.queue(200, {"sub": "u1", "email": "sender@example.com", "email_verified": True})
    transport.queue(200, {"id": "msg-real-1", "threadId": "thread-real-1"})
    executed = conversation_integrations.execute_request(execution["id"])
    assert executed["status"] == "SUCCEEDED"
    assert executed["response"]["message_id"] == "msg-real-1"
    assert executed["response"]["recipient"] == "recipient@example.com"
    assert "ya29.gmail_test_secret" not in json.dumps(executed, ensure_ascii=False)
    assert all("/messages/" not in call["url"] or call["method"] == "POST" for call in transport.calls)


def test_google_mail_ambiguous_transport_becomes_unknown_outcome_and_cannot_retry(product_env, monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN", "ya29.gmail_test_secret")
    transport = FakeTransport()
    adapter = GoogleMailSendAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    connection = conversation_integrations.create_connection(
        "GOOGLE_MAIL",
        granted_capabilities=["email.send"],
        credential_ref="provider:google-mail:env:CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN",
    )
    transport.queue(200, {"sub": "u1", "email": "sender@example.com", "email_verified": True})
    conversation_integrations.verify_and_connect(connection["id"])

    space = conversations.create_space("Unknown Outcome", "CLIENT_CALL")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    conversations.end_session(session["id"])
    draft = conversations.create_draft_action(
        session["id"],
        kind="FOLLOWUP_EMAIL_DRAFT",
        title="Follow-up",
        content="Body",
    )
    conversations.review_draft_action(draft["id"], "APPROVE")

    transport.queue(200, {"sub": "u1", "email": "sender@example.com", "email_verified": True})
    execution = conversation_integrations.create_execution_request(
        draft["id"], connection["id"], target="recipient@example.com"
    )
    transport.queue(200, {"sub": "u1", "email": "sender@example.com", "email_verified": True})
    transport.queue(503, RuntimeError("transport timeout after request write"))
    unknown = conversation_integrations.execute_request(execution["id"])
    assert unknown["status"] == "UNKNOWN_OUTCOME"
    with pytest.raises(ValueError, match="必须先在 provider 侧核对"):
        conversation_integrations.execute_request(execution["id"])
