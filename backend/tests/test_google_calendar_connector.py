from urllib.parse import parse_qs, urlparse

import pytest

from services.product import conversation_integrations, conversations
from services.product.google_calendar_connector import (
    GoogleCalendarFullSyncRequired,
    GoogleCalendarProviderError,
    GoogleCalendarRestAdapter,
    GoogleCalendarTargetError,
    register_google_calendar_adapter_from_env,
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
            raise AssertionError(f"Unexpected Google Calendar request: {method} {url}")
        status, response_headers, payload = self.responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return status, response_headers, payload


def _connection(ref="provider:google-calendar:env:CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN"):
    return {
        "id": "ccn_gcal_test",
        "provider_id": "GOOGLE_CALENDAR",
        "credential_ref": ref,
        "granted_capabilities": ["calendar.read"],
        "provider_scopes": ["https://www.googleapis.com/auth/calendar.events.readonly"],
        "status": "CONNECTED",
        "account_hint": "primary",
    }


def _event(event_id="evt-1", summary="Architecture Review", status="confirmed"):
    return {
        "id": event_id,
        "summary": summary,
        "description": "Discuss rollout and rollback owner.",
        "status": status,
        "htmlLink": f"https://calendar.google.com/calendar/event?eid={event_id}&auth=secret",
        "created": "2026-10-10T01:00:00Z",
        "updated": "2026-10-10T02:00:00Z",
        "start": {"dateTime": "2026-10-11T09:00:00+08:00", "timeZone": "Asia/Shanghai"},
        "end": {"dateTime": "2026-10-11T10:00:00+08:00", "timeZone": "Asia/Shanghai"},
        "location": "Meet",
        "organizer": {"email": "owner@example.test", "self": True},
        "attendees": [
            {"email": "alex@example.test", "responseStatus": "accepted"},
        ],
        "hangoutLink": "https://meet.google.com/abc-defg-hij",
    }


def test_google_calendar_adapter_requires_https_api_base():
    with pytest.raises(ValueError, match="HTTPS"):
        GoogleCalendarRestAdapter(api_base="http://calendar.test", transport=FakeTransport())


def test_google_calendar_scope_is_events_readonly(product_env):
    connection = conversation_integrations.create_connection(
        "GOOGLE_CALENDAR",
        granted_capabilities=["calendar.read"],
        credential_ref="provider:google-calendar:env:CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN",
        account_hint="primary",
    )
    assert connection["provider_scopes"] == [
        "https://www.googleapis.com/auth/calendar.events.readonly"
    ]
    with pytest.raises(ValueError, match="最小权限集合"):
        conversation_integrations.create_connection(
            "GOOGLE_CALENDAR",
            granted_capabilities=["calendar.read"],
            provider_scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            credential_ref="provider:google-calendar:env:CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN",
        )


def test_google_calendar_health_is_one_page_read_probe(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN", "ya29.test_calendar_token")
    transport = FakeTransport()
    transport.queue(200, {"items": []})
    adapter = GoogleCalendarRestAdapter(transport=transport)

    assert adapter.health(None)["ok"] is True
    health = adapter.health(_connection())
    assert health["ok"] is True
    assert health["account_hint"] == "primary"
    assert health["verify"] == "READ_PROBE_ONLY"

    call = transport.calls[0]
    assert call["method"] == "GET"
    assert call["headers"]["Authorization"] == "Bearer ya29.test_calendar_token"
    parsed = urlparse(call["url"])
    params = parse_qs(parsed.query)
    assert parsed.path == "/calendar/v3/calendars/primary/events"
    assert params["maxResults"] == ["1"]
    assert params["singleEvents"] == ["true"]
    assert params["showDeleted"] == ["true"]
    assert "timeMin" not in params
    assert "syncToken" not in params


def test_google_calendar_rejects_non_opaque_or_missing_env_reference(monkeypatch):
    adapter = GoogleCalendarRestAdapter(transport=FakeTransport())
    with pytest.raises(ValueError, match="credential_ref"):
        adapter.health({**_connection(), "credential_ref": "ya29.raw-secret"})
    monkeypatch.delenv("MISSING_GOOGLE_TOKEN", raising=False)
    with pytest.raises(ValueError, match="未设置"):
        adapter.health({
            **_connection(),
            "credential_ref": "provider:google-calendar:env:MISSING_GOOGLE_TOKEN",
        })


def test_google_calendar_full_sync_pages_to_final_sync_token(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN", "ya29.test_calendar_token")
    transport = FakeTransport()
    transport.queue(200, {
        "items": [_event("evt-1")],
        "nextPageToken": "page-2",
    })
    transport.queue(200, {
        "items": [_event("evt-2", "Design Review")],
        "nextSyncToken": "sync-token-1",
    })
    adapter = GoogleCalendarRestAdapter(transport=transport)

    result = adapter.read_context(
        connection=_connection(),
        capability="calendar.read",
        query={"calendar_id": "primary"},
        cursor="",
        limit=500,
    )
    assert [x["external_id"] for x in result["items"]] == ["primary:evt-1", "primary:evt-2"]
    assert result["next_cursor"] == "sync-token-1"

    first = parse_qs(urlparse(transport.calls[0]["url"]).query)
    second = parse_qs(urlparse(transport.calls[1]["url"]).query)
    assert "timeMin" in first
    assert "syncToken" not in first
    assert second["pageToken"] == ["page-2"]
    assert second["timeMin"] == first["timeMin"]
    assert first["maxResults"] == ["250"]
    assert second["maxResults"] == ["250"]


def test_google_calendar_incremental_sync_uses_token_without_time_filter(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN", "ya29.test_calendar_token")
    transport = FakeTransport()
    transport.queue(200, {
        "items": [_event("evt-cancelled", "[Cancelled]", status="cancelled")],
        "nextSyncToken": "sync-token-2",
    })
    adapter = GoogleCalendarRestAdapter(transport=transport)

    result = adapter.read_context(
        connection=_connection(),
        capability="calendar.read",
        query={"calendar_id": "primary"},
        cursor="sync-token-1",
        limit=500,
    )
    assert result["next_cursor"] == "sync-token-2"
    assert result["items"][0]["metadata"]["cancelled"] is True
    params = parse_qs(urlparse(transport.calls[0]["url"]).query)
    assert params["syncToken"] == ["sync-token-1"]
    assert "timeMin" not in params


def test_google_calendar_410_requests_full_sync_reset(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN", "ya29.test_calendar_token")
    transport = FakeTransport()
    transport.queue(
        410,
        GoogleCalendarFullSyncRequired(410, "Google Calendar HTTP 410: fullSyncRequired"),
    )
    adapter = GoogleCalendarRestAdapter(transport=transport)

    result = adapter.read_context(
        connection=_connection(),
        capability="calendar.read",
        query={"calendar_id": "primary"},
        cursor="expired-token",
        limit=500,
    )
    assert result["items"] == []
    assert result["next_cursor"] == ""
    assert result["full_sync_required"] is True


def test_google_calendar_refuses_partial_change_set_before_advancing_token(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN", "ya29.test_calendar_token")
    transport = FakeTransport()
    transport.queue(200, {
        "items": [_event(f"evt-{i}") for i in range(3)],
        "nextSyncToken": "must-not-be-used",
    })
    adapter = GoogleCalendarRestAdapter(transport=transport)

    with pytest.raises(ValueError, match="超过 Chengzhu 当前安全写入上限"):
        adapter.read_context(
            connection=_connection(),
            capability="calendar.read",
            query={"calendar_id": "primary"},
            cursor="",
            limit=2,
        )


def test_google_calendar_target_error_is_not_account_fatal(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN", "ya29.test_calendar_token")
    transport = FakeTransport()
    transport.queue(404, GoogleCalendarProviderError(404, "Google Calendar HTTP 404: Not Found"))
    adapter = GoogleCalendarRestAdapter(transport=transport)

    with pytest.raises(GoogleCalendarTargetError):
        adapter.read_context(
            connection=_connection(),
            capability="calendar.read",
            query={"calendar_id": "missing@example.test"},
            cursor="",
            limit=500,
        )


def test_google_calendar_registration_is_explicit_opt_in(product_env, monkeypatch):
    conversation_integrations.clear_adapters_for_tests()
    monkeypatch.delenv("CHENGZHU_GOOGLE_CALENDAR_CONNECTOR_ENABLE", raising=False)
    assert register_google_calendar_adapter_from_env()["registered"] is False
    row = next(x for x in conversation_integrations.catalog() if x["provider_id"] == "GOOGLE_CALENDAR")
    assert row["adapter_available"] is False

    monkeypatch.setenv("CHENGZHU_GOOGLE_CALENDAR_CONNECTOR_ENABLE", "1")
    registered = register_google_calendar_adapter_from_env()
    assert registered["registered"] is True
    row = next(x for x in conversation_integrations.catalog() if x["provider_id"] == "GOOGLE_CALENDAR")
    assert row["adapter_available"] is True
    assert row["write_capabilities"] == []


def test_calendar_integration_boundary_resets_expired_token_and_keeps_provenance(product_env, monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN", "ya29.test_calendar_token")
    transport = FakeTransport()
    adapter = GoogleCalendarRestAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    # Verify connection by read-only one-page probe.
    transport.queue(200, {"items": []})
    connection = conversation_integrations.create_connection(
        "GOOGLE_CALENDAR",
        granted_capabilities=["calendar.read"],
        credential_ref="provider:google-calendar:env:CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN",
        account_hint="primary",
    )
    connected = conversation_integrations.verify_and_connect(connection["id"])
    assert connected["status"] == "CONNECTED"

    space = conversations.create_space("Calendar Project", "PROJECT_SYNC")

    # First Sync: health probe + full sync -> token-1.
    transport.queue(200, {"items": []})
    transport.queue(200, {"items": [_event("evt-1")], "nextSyncToken": "token-1"})
    first = conversation_integrations.sync_connection(
        connection["id"],
        space["id"],
        capabilities=["calendar.read"],
        query={"calendar_id": "primary"},
    )
    assert first["snapshots"][0]["external_id"] == "primary:evt-1"
    assert first["connection"]["sync_cursors"]["calendar.read"] == "token-1"

    # Second Sync: health probe + expired incremental token + one full reset.
    transport.queue(200, {"items": []})
    transport.queue(410, GoogleCalendarFullSyncRequired(410, "fullSyncRequired"))
    transport.queue(200, {"items": [_event("evt-2", "Next Review")], "nextSyncToken": "token-2"})
    second = conversation_integrations.sync_connection(
        connection["id"],
        space["id"],
        capabilities=["calendar.read"],
        query={"calendar_id": "primary"},
    )
    assert second["connection"]["sync_cursors"]["calendar.read"] == "token-2"
    assert second["snapshots"][0]["external_id"] == "primary:evt-2"

    historical = conversation_integrations.list_snapshots(space["id"], connection_id=connection["id"])
    assert {row["external_id"] for row in historical} == {"primary:evt-1", "primary:evt-2"}


def test_calendar_target_failure_keeps_verified_connection_connected(product_env, monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN", "ya29.test_calendar_token")
    transport = FakeTransport()
    adapter = GoogleCalendarRestAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    transport.queue(200, {"items": []})
    connection = conversation_integrations.create_connection(
        "GOOGLE_CALENDAR",
        granted_capabilities=["calendar.read"],
        credential_ref="provider:google-calendar:env:CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN",
        account_hint="primary",
    )
    conversation_integrations.verify_and_connect(connection["id"])
    space = conversations.create_space("Target Error", "PROJECT_SYNC")

    # sync_connection health probe succeeds; explicit shared calendar target fails.
    transport.queue(200, {"items": []})
    transport.queue(404, GoogleCalendarProviderError(404, "Google Calendar HTTP 404: Not Found"))
    with pytest.raises(ValueError, match="404"):
        conversation_integrations.sync_connection(
            connection["id"],
            space["id"],
            capabilities=["calendar.read"],
            query={"calendar_id": "missing@example.test"},
        )
    after = next(x for x in conversation_integrations.list_connections() if x["id"] == connection["id"])
    assert after["status"] == "CONNECTED"
    assert "404" in after["last_error"]


def test_calendar_auth_failure_during_sync_marks_connection_error(product_env, monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN", "ya29.test_calendar_token")
    transport = FakeTransport()
    adapter = GoogleCalendarRestAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    transport.queue(200, {"items": []})
    connection = conversation_integrations.create_connection(
        "GOOGLE_CALENDAR",
        granted_capabilities=["calendar.read"],
        credential_ref="provider:google-calendar:env:CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN",
        account_hint="primary",
    )
    conversation_integrations.verify_and_connect(connection["id"])
    space = conversations.create_space("Auth Error", "PROJECT_SYNC")

    transport.queue(401, GoogleCalendarProviderError(401, "Google Calendar HTTP 401: invalid credentials"))
    with pytest.raises(ValueError, match="401"):
        conversation_integrations.sync_connection(
            connection["id"],
            space["id"],
            capabilities=["calendar.read"],
            query={"calendar_id": "primary"},
        )
    after = next(x for x in conversation_integrations.list_connections() if x["id"] == connection["id"])
    assert after["status"] == "ERROR"
