"""Opt-in Google Calendar read-only provider for Conversation external context.

This adapter deliberately supports only `calendar.read`.

Credential material is resolved from a process environment variable referenced
by an opaque product.db handle:

    provider:google-calendar:env:GOOGLE_CALENDAR_ACCESS_TOKEN

The token itself never enters product.db, frontend state, snapshots or exports.

The adapter uses Google Calendar's native Events incremental synchronization:
- initial full pagination until the final page yields nextSyncToken;
- subsequent syncToken pagination with identical supported parameters;
- HTTP 410 becomes an explicit "full sync required" signal;
- no partial cursor is returned when the complete collection cannot be read.

No event write/create capability is implemented here.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


_DEFAULT_API_BASE = "https://www.googleapis.com/calendar/v3"
_ENV_REF_RE = re.compile(r"^provider:google-calendar:env:([A-Za-z_][A-Za-z0-9_]{0,127})$")
_MAX_EVENTS_PER_SYNC = 5_000
_PAGE_SIZE = 250


class GoogleCalendarProviderError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = int(status)


class GoogleCalendarTargetError(GoogleCalendarProviderError):
    """A calendar-target rejection; the verified account may still be healthy."""

    connection_fatal = False


class GoogleCalendarFullSyncRequired(GoogleCalendarProviderError):
    """The provider invalidated the stored sync token (HTTP 410)."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


Transport = Callable[
    [str, str, dict[str, str], Optional[bytes], float],
    tuple[int, dict[str, str], Any],
]


def _timeout_seconds() -> float:
    raw = str(os.environ.get("CHENGZHU_GOOGLE_CALENDAR_TIMEOUT_SECONDS") or "15").strip()
    try:
        return max(2.0, min(float(raw), 60.0))
    except ValueError:
        return 15.0


def _urllib_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    body: Optional[bytes],
    timeout: float,
) -> tuple[int, dict[str, str], Any]:
    request = Request(url=url, data=body, method=method, headers=headers)
    opener = build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read()
            payload: Any = json.loads(raw.decode("utf-8")) if raw else None
            return int(response.status), dict(response.headers.items()), payload
    except HTTPError as exc:
        raw = exc.read(16_384)
        message = f"Google Calendar HTTP {exc.code}"
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            if isinstance(parsed, dict):
                error = parsed.get("error") or {}
                if isinstance(error, dict) and error.get("message"):
                    message = f"{message}: {str(error['message'])[:1000]}"
        except Exception:
            pass
        if int(exc.code) == 410:
            raise GoogleCalendarFullSyncRequired(410, message) from None
        raise GoogleCalendarProviderError(int(exc.code), message) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Google Calendar transport error: {type(exc).__name__}") from None


def _timestamp(value: str) -> Optional[float]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _event_when(raw: dict[str, Any]) -> tuple[str, Optional[float]]:
    start = raw.get("start") if isinstance(raw.get("start"), dict) else {}
    if start.get("dateTime"):
        text = str(start["dateTime"])
        return text, _timestamp(text)
    if start.get("date"):
        text = str(start["date"])
        return text, _timestamp(f"{text}T00:00:00+00:00")
    updated = str(raw.get("updated") or raw.get("created") or "")
    return updated, _timestamp(updated)


class GoogleCalendarRestAdapter:
    provider_id = "GOOGLE_CALENDAR"
    capabilities = {"calendar.read"}

    def __init__(self, *, api_base: str = "", transport: Optional[Transport] = None):
        configured = str(
            api_base or os.environ.get("CHENGZHU_GOOGLE_CALENDAR_API_BASE") or _DEFAULT_API_BASE
        ).strip()
        self.api_base = configured.rstrip("/")
        if not self.api_base.startswith("https://"):
            raise ValueError("Google Calendar API base 必须使用 HTTPS；Bearer token 不允许明文 HTTP 出站")
        self._transport = transport or _urllib_transport

    @staticmethod
    def _resolve_token(connection: dict[str, Any]) -> str:
        credential_ref = str(connection.get("credential_ref") or "").strip()
        match = _ENV_REF_RE.fullmatch(credential_ref)
        if not match:
            raise ValueError(
                "Google Calendar credential_ref 当前只支持 "
                "provider:google-calendar:env:<ENV_VAR>；access token 本身不能写入 product.db"
            )
        env_name = match.group(1)
        token = str(os.environ.get(env_name) or "").strip()
        if not token:
            raise ValueError(f"Google Calendar credential environment variable 未设置：{env_name}")
        return token

    @staticmethod
    def _calendar_id(query: dict[str, Any], connection: dict[str, Any]) -> str:
        value = str(
            query.get("calendar_id")
            or query.get("calendar")
            or connection.get("account_hint")
            or "primary"
        ).strip()
        if not value:
            value = "primary"
        if len(value) > 500 or any(ch in value for ch in "\r\n\x00"):
            raise ValueError("Google Calendar calendar_id 非法")
        return value

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Chengzhu/2.0",
        }

    def _request(
        self,
        path: str,
        *,
        token: str,
        params: Optional[dict[str, Any]] = None,
    ) -> tuple[int, dict[str, str], Any]:
        query = urlencode(
            [(str(k), str(v)) for k, v in (params or {}).items() if v not in (None, "", [])],
            doseq=True,
        )
        url = f"{self.api_base}{path}"
        if query:
            url = f"{url}?{query}"
        return self._transport("GET", url, self._headers(token), None, _timeout_seconds())

    def _list_events(
        self,
        *,
        connection: dict[str, Any],
        calendar_id: str,
        cursor: str,
        collect: bool,
    ) -> dict[str, Any]:
        token = self._resolve_token(connection)
        path = f"/calendars/{quote(calendar_id, safe='')}/events"
        base_params: dict[str, Any] = {
            "maxResults": _PAGE_SIZE,
            "singleEvents": "true",
            "showDeleted": "true",
        }
        if cursor:
            base_params["syncToken"] = cursor
        else:
            # Bound the initial collection while still using Google's native
            # sync-token model. The official sync guide explicitly demonstrates
            # an initial timeMin filter followed by token-only incremental sync.
            # This keeps personal calendars tractable without pretending an
            # arbitrarily truncated result is complete.
            one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
            base_params["timeMin"] = one_year_ago.isoformat().replace("+00:00", "Z")

        page_token = ""
        next_sync_token = ""
        items: list[dict[str, Any]] = []
        seen = 0
        while True:
            params = dict(base_params)
            if page_token:
                params["pageToken"] = page_token
            status, _headers, payload = self._request(path, token=token, params=params)
            if status != 200 or not isinstance(payload, dict):
                raise RuntimeError(f"Google Calendar events sync returned ambiguous HTTP {status}")
            rows = payload.get("items") or []
            if not isinstance(rows, list):
                raise RuntimeError("Google Calendar events sync returned malformed items")
            seen += len(rows)
            if seen > _MAX_EVENTS_PER_SYNC:
                raise ValueError(
                    f"Google Calendar 单次完整同步超过安全上限 {_MAX_EVENTS_PER_SYNC}；"
                    "为避免半同步，不写入 snapshots/cursor。"
                )
            if collect:
                items.extend(row for row in rows if isinstance(row, dict))
            page_token = str(payload.get("nextPageToken") or "")
            if page_token:
                continue
            next_sync_token = str(payload.get("nextSyncToken") or "")
            break

        if not next_sync_token:
            raise RuntimeError("Google Calendar 完整分页结束但缺少 nextSyncToken；拒绝保存不完整 cursor")
        return {"items": items, "next_cursor": next_sync_token, "seen": seen}

    def health(self, connection: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if connection is None:
            return {
                "ok": True,
                "label": "Google Calendar REST adapter",
                "runtime": "OPT_IN_REAL_PROVIDER",
            }
        calendar_id = str(connection.get("account_hint") or "primary").strip() or "primary"
        token = self._resolve_token(connection)
        path = f"/calendars/{quote(calendar_id, safe='')}/events"
        status, _headers, payload = self._request(
            path,
            token=token,
            params={"maxResults": 1, "singleEvents": "true", "showDeleted": "true"},
        )
        if status != 200 or not isinstance(payload, dict) or not isinstance(payload.get("items", []), list):
            return {"ok": False, "error": f"Google Calendar verify returned HTTP {status}"}
        return {
            "ok": True,
            "label": "Google Calendar",
            "account_hint": calendar_id[:300],
            "calendar_id": calendar_id[:500],
            "verify": "READ_PROBE_ONLY",
        }

    def read_context(
        self,
        *,
        connection: dict[str, Any],
        capability: str,
        query: dict[str, Any],
        cursor: str,
        limit: int,
    ) -> dict[str, Any]:
        if capability != "calendar.read":
            raise ValueError("Google Calendar adapter 只支持 calendar.read")
        calendar_id = self._calendar_id(query, connection)
        try:
            synced = self._list_events(
                connection=connection,
                calendar_id=calendar_id,
                cursor=str(cursor or ""),
                collect=True,
            )
        except GoogleCalendarFullSyncRequired:
            if not cursor:
                raise
            # Caller receives a semantic reset request rather than a fake empty
            # incremental result. The integration boundary can clear only this
            # capability cursor and invoke one full resync.
            return {
                "items": [],
                "next_cursor": "",
                "full_sync_required": True,
                "calendar_id": calendar_id,
            }
        except GoogleCalendarProviderError as exc:
            if exc.status != 401 and 400 <= exc.status < 500:
                raise GoogleCalendarTargetError(exc.status, str(exc)) from None
            raise

        snapshots: list[dict[str, Any]] = []
        for raw in synced["items"]:
            event_id = str(raw.get("id") or "").strip()
            if not event_id:
                continue
            status = str(raw.get("status") or "")
            when_text, occurred_at = _event_when(raw)
            cancelled = status == "cancelled"
            attendees = []
            for attendee in raw.get("attendees") or []:
                if not isinstance(attendee, dict):
                    continue
                attendees.append({
                    "display_name": str(attendee.get("displayName") or "")[:200],
                    "email": str(attendee.get("email") or "")[:320],
                    "response_status": str(attendee.get("responseStatus") or "")[:80],
                    "self": bool(attendee.get("self")),
                    "organizer": bool(attendee.get("organizer")),
                })
            snapshots.append({
                "external_kind": "CALENDAR_EVENT",
                "external_id": f"{calendar_id}:{event_id}",
                "title": str(raw.get("summary") or ("[Cancelled event]" if cancelled else "Untitled event"))[:500],
                "excerpt": str(raw.get("description") or "")[:20_000],
                "source_url": str(raw.get("htmlLink") or ""),
                "occurred_at": occurred_at,
                "visibility": "PRIVATE",
                "metadata": {
                    "calendar_id": calendar_id,
                    "event_id": event_id,
                    "status": status,
                    "cancelled": cancelled,
                    "when": when_text,
                    "start": raw.get("start") or {},
                    "end": raw.get("end") or {},
                    "location": str(raw.get("location") or "")[:1000],
                    "organizer": raw.get("organizer") or {},
                    "attendees": attendees[:100],
                    "hangout_link": str(raw.get("hangoutLink") or "")[:2000],
                    "updated": str(raw.get("updated") or "")[:100],
                    "recurring_event_id": str(raw.get("recurringEventId") or "")[:500],
                },
            })

        # The provider cursor represents the complete collection state. Limit
        # only affects what the generic boundary may return to the UI; the
        # adapter refuses unsafe partial full syncs above the hard cap.
        requested = max(1, min(int(limit), _MAX_EVENTS_PER_SYNC))
        if len(snapshots) > requested:
            raise ValueError(
                f"Google Calendar 本次完整变更集包含 {len(snapshots)} 条，超过 Chengzhu 当前安全写入上限 {requested}；"
                "拒绝推进 sync token，避免半同步。"
            )
        return {
            "items": snapshots,
            "next_cursor": str(synced["next_cursor"]),
            "calendar_id": calendar_id,
            "full_sync_required": False,
        }

    def execute(
        self,
        *,
        connection: dict[str, Any],
        capability: str,
        operation: str,
        target: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "error": "Google Calendar provider 当前只实现 calendar.read；不支持外部写入",
            "retry_safe": False,
        }


def register_google_calendar_adapter_from_env() -> dict[str, Any]:
    enabled = str(os.environ.get("CHENGZHU_GOOGLE_CALENDAR_CONNECTOR_ENABLE") or "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return {"registered": False, "provider_id": "GOOGLE_CALENDAR", "reason": "NOT_ENABLED"}

    from services.product import conversation_integrations

    adapter = GoogleCalendarRestAdapter()
    conversation_integrations.register_adapter(adapter)
    return {
        "registered": True,
        "provider_id": "GOOGLE_CALENDAR",
        "capabilities": sorted(adapter.capabilities),
        "credential_ref_format": "provider:google-calendar:env:<ENV_VAR>",
        "write_capabilities": [],
    }
