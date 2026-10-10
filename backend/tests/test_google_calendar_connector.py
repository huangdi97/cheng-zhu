from urllib.parse import parse_qs, urlparse

import pytest

from services.product import conversation_integrations, conversations
from services.storage import product as store
from services.product.google_calendar_connector import (
    GoogleCalendarFullSyncRequired,
    GoogleCalendarProviderError,
    GoogleCalendarRestAdapter,
    GoogleCalendarTargetError,
    _decode_cursor,
    _encode_cursor,
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
    assert _decode_cursor(result["next_cursor"]) == {
        "calendar_id": "primary",
        "sync_token": "sync-token-1",
    }

    first = parse_qs(urlparse(transport.calls[0]["url"]).query)
    second = parse_qs(urlparse(transport.calls[1]["url"]).query)
    assert "timeMin" in first
    assert "syncToken" not in first
    assert second["pageToken"] == ["page-2"]
    assert second["timeMin"] == first["timeMin"]
    assert first["maxResults"] == ["250"]
    assert second["maxResults"] == ["250"]




def test_google_calendar_preserves_timezone_and_does_not_invent_all_day_time(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN", "ya29.test_calendar_token")
    transport = FakeTransport()
    timed = _event("evt-tz")
    timed["start"] = {"dateTime": "2026-10-11T09:00:00", "timeZone": "Asia/Shanghai"}
    all_day = _event("evt-all-day", "Conference day")
    all_day["start"] = {"date": "2026-10-12"}
    all_day["end"] = {"date": "2026-10-13"}
    transport.queue(200, {
        "items": [timed, all_day],
        "nextSyncToken": "sync-token-time",
    })
    adapter = GoogleCalendarRestAdapter(transport=transport)

    result = adapter.read_context(
        connection=_connection(),
        capability="calendar.read",
        query={"calendar_id": "primary"},
        cursor="",
        limit=500,
    )
    by_id = {row["external_id"]: row for row in result["items"]}
    timed_snapshot = by_id["primary:evt-tz"]
    assert timed_snapshot["metadata"]["timezone"] == "Asia/Shanghai"
    assert timed_snapshot["metadata"]["all_day"] is False
    assert timed_snapshot["occurred_at"] is not None

    all_day_snapshot = by_id["primary:evt-all-day"]
    assert all_day_snapshot["metadata"]["all_day"] is True
    assert all_day_snapshot["metadata"]["when"] == "2026-10-12"
    assert all_day_snapshot["occurred_at"] is None


def test_calendar_import_rejects_all_day_and_status_events(product_env):
    space = conversations.create_space("Calendar Non Meetings", "PROJECT_SYNC")
    connection = conversation_integrations.create_connection(
        "GOOGLE_CALENDAR",
        granted_capabilities=["calendar.read"],
        credential_ref="provider:google-calendar:env:CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN",
        account_hint="primary",
    )
    all_day = conversation_integrations._store_snapshot(
        connection,
        space["id"],
        "calendar.read",
        {
            "external_kind": "CALENDAR_EVENT",
            "external_id": "primary:all-day",
            "title": "Conference Day",
            "occurred_at": None,
            "metadata": {
                "calendar_id": "primary",
                "event_id": "all-day",
                "status": "confirmed",
                "cancelled": False,
                "all_day": True,
                "event_type": "default",
            },
        },
    )
    with pytest.raises(ValueError, match="All-day"):
        conversations.schedule_from_calendar_snapshot(space["id"], all_day["id"])

    for event_type in ("focusTime", "outOfOffice", "workingLocation"):
        status_event = conversation_integrations._store_snapshot(
            connection,
            space["id"],
            "calendar.read",
            {
                "external_kind": "CALENDAR_EVENT",
                "external_id": f"primary:{event_type}",
                "title": event_type,
                "occurred_at": store.now() + 3600,
                "metadata": {
                    "calendar_id": "primary",
                    "event_id": event_type,
                    "status": "confirmed",
                    "cancelled": False,
                    "all_day": False,
                    "event_type": event_type,
                },
            },
        )
        with pytest.raises(ValueError, match="不是 Conversation Session"):
            conversations.schedule_from_calendar_snapshot(space["id"], status_event["id"])


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
        cursor=_encode_cursor("primary", "sync-token-1"),
        limit=500,
    )
    assert _decode_cursor(result["next_cursor"]) == {
        "calendar_id": "primary",
        "sync_token": "sync-token-2",
    }
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
        cursor=_encode_cursor("primary", "expired-token"),
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
    first_cursor = _decode_cursor(first["connection"]["sync_cursors"]["calendar.read"])
    assert first_cursor == {"calendar_id": "primary", "sync_token": "token-1"}

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
    second_cursor = _decode_cursor(second["connection"]["sync_cursors"]["calendar.read"])
    assert second_cursor == {"calendar_id": "primary", "sync_token": "token-2"}
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


def test_calendar_snapshot_import_creates_one_provenance_linked_upcoming_session(product_env):
    space = conversations.create_space("Calendar Continuity", "PROJECT_SYNC")
    connection = conversation_integrations.create_connection(
        "GOOGLE_CALENDAR",
        granted_capabilities=["calendar.read"],
        credential_ref="provider:google-calendar:env:CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN",
        account_hint="primary",
    )
    future = store.now() + 3600
    snapshot = conversation_integrations._store_snapshot(
        connection,
        space["id"],
        "calendar.read",
        {
            "external_kind": "CALENDAR_EVENT",
            "external_id": "primary:evt-next",
            "title": "Architecture Review",
            "excerpt": "Review rollout and rollback owner.",
            "occurred_at": future,
            "visibility": "PRIVATE",
            "metadata": {
                "calendar_id": "primary",
                "event_id": "evt-next",
                "status": "confirmed",
                "cancelled": False,
            },
        },
    )

    imported = conversations.schedule_from_calendar_snapshot(space["id"], snapshot["id"])
    assert imported["created"] is True
    assert imported["snapshot_selected"] is True
    session = imported["session"]
    assert session["status"] == "UPCOMING"
    assert session["title"] == "Architecture Review"
    assert session["scheduled_at"] == future
    assert session["source_calendar_event"]["snapshot_id"] == snapshot["id"]
    assert session["source_calendar_event"]["content_hash"] == snapshot["content_hash"]
    assert session["state"]["calendar_imported"] is True

    detail = conversations.space_detail(space["id"])
    assert snapshot["id"] in detail["selected_connector_snapshot_ids"]
    assert detail["next_session"]["id"] == session["id"]

    repeated = conversations.schedule_from_calendar_snapshot(space["id"], snapshot["id"])
    assert repeated["created"] is False
    assert repeated["session"]["id"] == session["id"]
    assert len([x for x in conversations.list_sessions(space["id"]) if x["source_calendar_event"].get("snapshot_id") == snapshot["id"]]) == 1


def test_calendar_snapshot_import_rejects_cancelled_past_cross_space_and_non_google(product_env):
    space = conversations.create_space("Calendar Guard", "PROJECT_SYNC")
    other = conversations.create_space("Other Space", "PROJECT_SYNC")
    gcal = conversation_integrations.create_connection(
        "GOOGLE_CALENDAR",
        granted_capabilities=["calendar.read"],
        credential_ref="provider:google-calendar:env:CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN",
        account_hint="primary",
    )
    github = conversation_integrations.create_connection(
        "GITHUB",
        granted_capabilities=["project.read"],
        credential_ref="provider:github:env:CHENGZHU_GITHUB_TOKEN",
    )

    cancelled = conversation_integrations._store_snapshot(
        gcal, space["id"], "calendar.read",
        {
            "external_kind": "CALENDAR_EVENT", "external_id": "primary:cancelled",
            "title": "Cancelled", "occurred_at": store.now() + 3600,
            "metadata": {"cancelled": True, "status": "cancelled"},
        },
    )
    with pytest.raises(ValueError, match="已取消"):
        conversations.schedule_from_calendar_snapshot(space["id"], cancelled["id"])

    past = conversation_integrations._store_snapshot(
        gcal, space["id"], "calendar.read",
        {
            "external_kind": "CALENDAR_EVENT", "external_id": "primary:past",
            "title": "Past", "occurred_at": store.now() - 3600,
            "metadata": {"cancelled": False, "status": "confirmed"},
        },
    )
    with pytest.raises(ValueError, match="未来"):
        conversations.schedule_from_calendar_snapshot(space["id"], past["id"])

    cross = conversation_integrations._store_snapshot(
        gcal, other["id"], "calendar.read",
        {
            "external_kind": "CALENDAR_EVENT", "external_id": "primary:cross",
            "title": "Cross", "occurred_at": store.now() + 3600,
            "metadata": {"cancelled": False, "status": "confirmed"},
        },
    )
    with pytest.raises(ValueError, match="不属于当前 Space"):
        conversations.schedule_from_calendar_snapshot(space["id"], cross["id"])

    fake_calendar_from_github = conversation_integrations._store_snapshot(
        # _store_snapshot validates GitHub external_kind, so create the row
        # directly to prove the import guard cannot be bypassed by DB-shaped data.
        gcal, space["id"], "calendar.read",
        {
            "external_kind": "CALENDAR_EVENT", "external_id": "primary:not-google",
            "title": "Wrong Provider", "occurred_at": store.now() + 7200,
            "metadata": {"cancelled": False, "status": "confirmed"},
        },
    )
    # Re-point only the connection id to a non-Google connection; import must
    # reject provider provenance even though the snapshot shape is Calendar-like.
    store.update("conversation_connector_snapshot", fake_calendar_from_github["id"], {"connection_id": github["id"]})
    with pytest.raises(ValueError, match="不是 Google Calendar"):
        conversations.schedule_from_calendar_snapshot(space["id"], fake_calendar_from_github["id"])




def test_calendar_only_latest_revision_can_be_imported_and_old_revision_stays_audit_only(product_env):
    space = conversations.create_space("Calendar Revision", "PROJECT_SYNC")
    connection = conversation_integrations.create_connection(
        "GOOGLE_CALENDAR",
        granted_capabilities=["calendar.read"],
        credential_ref="provider:google-calendar:env:CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN",
        account_hint="primary",
    )
    now = store.now()
    old = conversation_integrations._store_snapshot(
        connection, space["id"], "calendar.read",
        {
            "external_kind": "CALENDAR_EVENT",
            "external_id": "primary:evt-revision",
            "title": "Architecture Review",
            "excerpt": "Old time",
            "occurred_at": now + 3600,
            "metadata": {"calendar_id": "primary", "event_id": "evt-revision", "status": "confirmed", "cancelled": False},
        },
    )
    latest = conversation_integrations._store_snapshot(
        connection, space["id"], "calendar.read",
        {
            "external_kind": "CALENDAR_EVENT",
            "external_id": "primary:evt-revision",
            "title": "Architecture Review · Rescheduled",
            "excerpt": "New time",
            "occurred_at": now + 7200,
            "metadata": {"calendar_id": "primary", "event_id": "evt-revision", "status": "confirmed", "cancelled": False},
        },
    )

    listed = {row["id"]: row for row in conversation_integrations.list_snapshots(space["id"])}
    assert listed[old["id"]]["is_latest_revision"] is False
    assert listed[old["id"]]["latest_snapshot_id"] == latest["id"]
    assert listed[latest["id"]]["is_latest_revision"] is True

    with pytest.raises(ValueError, match="不是最新 revision"):
        conversations.schedule_from_calendar_snapshot(space["id"], old["id"])
    imported = conversations.schedule_from_calendar_snapshot(space["id"], latest["id"])
    assert imported["session"]["scheduled_at"] == latest["occurred_at"]


def test_calendar_cancelled_latest_revision_blocks_old_import_and_marks_existing_session_drift(product_env):
    space = conversations.create_space("Calendar Cancellation", "PROJECT_SYNC")
    connection = conversation_integrations.create_connection(
        "GOOGLE_CALENDAR",
        granted_capabilities=["calendar.read"],
        credential_ref="provider:google-calendar:env:CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN",
        account_hint="primary",
    )
    now = store.now()
    confirmed = conversation_integrations._store_snapshot(
        connection, space["id"], "calendar.read",
        {
            "external_kind": "CALENDAR_EVENT",
            "external_id": "primary:evt-cancel",
            "title": "Client Review",
            "occurred_at": now + 3600,
            "metadata": {"calendar_id": "primary", "event_id": "evt-cancel", "status": "confirmed", "cancelled": False},
        },
    )
    imported = conversations.schedule_from_calendar_snapshot(space["id"], confirmed["id"])
    original_time = imported["session"]["scheduled_at"]

    cancelled = conversation_integrations._store_snapshot(
        connection, space["id"], "calendar.read",
        {
            "external_kind": "CALENDAR_EVENT",
            "external_id": "primary:evt-cancel",
            "title": "[Cancelled event]",
            "occurred_at": now + 3600,
            "metadata": {"calendar_id": "primary", "event_id": "evt-cancel", "status": "cancelled", "cancelled": True},
        },
    )

    with pytest.raises(ValueError, match="更新版本中取消"):
        conversations.schedule_from_calendar_snapshot(space["id"], confirmed["id"])
    with pytest.raises(ValueError, match="已取消"):
        conversations.schedule_from_calendar_snapshot(space["id"], cancelled["id"])

    detail = conversations.space_detail(space["id"])
    session = next(x for x in detail["sessions"] if x["id"] == imported["session"]["id"])
    assert session["scheduled_at"] == original_time
    assert session["source_calendar_event"]["revision_status"] == "CANCELLED_UPSTREAM"
    assert session["source_calendar_event"]["latest_snapshot_id"] == cancelled["id"]
    assert session["source_calendar_event"]["latest_cancelled"] is True


def test_calendar_rescheduled_latest_revision_marks_existing_session_source_drift_without_rewriting(product_env):
    space = conversations.create_space("Calendar Drift", "PROJECT_SYNC")
    connection = conversation_integrations.create_connection(
        "GOOGLE_CALENDAR",
        granted_capabilities=["calendar.read"],
        credential_ref="provider:google-calendar:env:CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN",
        account_hint="primary",
    )
    now = store.now()
    first = conversation_integrations._store_snapshot(
        connection, space["id"], "calendar.read",
        {
            "external_kind": "CALENDAR_EVENT",
            "external_id": "primary:evt-drift",
            "title": "Design Review",
            "occurred_at": now + 3600,
            "metadata": {"calendar_id": "primary", "event_id": "evt-drift", "status": "confirmed", "cancelled": False},
        },
    )
    imported = conversations.schedule_from_calendar_snapshot(space["id"], first["id"])
    moved = conversation_integrations._store_snapshot(
        connection, space["id"], "calendar.read",
        {
            "external_kind": "CALENDAR_EVENT",
            "external_id": "primary:evt-drift",
            "title": "Design Review · Moved",
            "occurred_at": now + 10800,
            "metadata": {"calendar_id": "primary", "event_id": "evt-drift", "status": "confirmed", "cancelled": False},
        },
    )

    detail = conversations.space_detail(space["id"])
    session = next(x for x in detail["sessions"] if x["id"] == imported["session"]["id"])
    assert session["scheduled_at"] == first["occurred_at"]
    assert session["title"] == "Design Review"
    assert session["source_calendar_event"]["revision_status"] == "SOURCE_DRIFT"
    assert session["source_calendar_event"]["latest_snapshot_id"] == moved["id"]
    assert session["source_calendar_event"]["latest_scheduled_at"] == moved["occurred_at"]


def test_calendar_cursor_never_crosses_explicit_calendar_targets(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN", "ya29.test_calendar_token")
    transport = FakeTransport()
    transport.queue(200, {
        "items": [_event("shared-1", "Shared Calendar Review")],
        "nextSyncToken": "shared-token",
    })
    adapter = GoogleCalendarRestAdapter(transport=transport)

    result = adapter.read_context(
        connection=_connection(),
        capability="calendar.read",
        query={"calendar_id": "shared@example.test"},
        cursor=_encode_cursor("primary", "primary-token"),
        limit=500,
    )
    decoded = _decode_cursor(result["next_cursor"])
    assert decoded == {"calendar_id": "shared@example.test", "sync_token": "shared-token"}

    params = parse_qs(urlparse(transport.calls[0]["url"]).query)
    assert "syncToken" not in params
    assert "timeMin" in params
    assert urlparse(transport.calls[0]["url"]).path.endswith("/calendars/shared%40example.test/events")
