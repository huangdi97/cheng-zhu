"""Opt-in Microsoft To Do provider over Microsoft Graph for Conversation.

This adapter intentionally supports only:
- project.read -> read one explicit Microsoft To Do task list
- task.create  -> reviewed CREATE_TASK external execution into one explicit list

It does NOT implement Microsoft Mail, Calendar, OneDrive/SharePoint, Planner,
Teams, or directory traversal. Identity verification uses User.Read; task
permissions stay limited to Tasks.Read or Tasks.ReadWrite.

Credential material stays outside product.db behind an opaque environment
reference:

    provider:microsoft-graph:env:MICROSOFT_GRAPH_ACCESS_TOKEN
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


_DEFAULT_API_BASE = "https://graph.microsoft.com/v1.0"
_ENV_REF_RE = re.compile(r"^provider:microsoft-graph:env:([A-Za-z_][A-Za-z0-9_]{0,127})$")
_DEFAULT_LIST_ALIASES = {"", "default", "defaultlist", "tasks"}
_PAGE_SIZE = 100
_MAX_TASKS_PER_SYNC = 5_000


class MicrosoftTodoProviderError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = int(status)


class MicrosoftTodoTargetError(MicrosoftTodoProviderError):
    """A list/target rejection that does not necessarily invalidate account auth."""

    connection_fatal = False


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


Transport = Callable[
    [str, str, dict[str, str], Optional[bytes], float],
    tuple[int, dict[str, str], Any],
]


def _timeout_seconds() -> float:
    raw = str(os.environ.get("CHENGZHU_MICROSOFT_TODO_TIMEOUT_SECONDS") or "15").strip()
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
        message = f"Microsoft Graph HTTP {exc.code}"
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            error = parsed.get("error") if isinstance(parsed, dict) else {}
            if isinstance(error, dict):
                detail = error.get("message") or error.get("code")
                if detail:
                    message = f"{message}: {str(detail)[:1000]}"
        except Exception:
            pass
        raise MicrosoftTodoProviderError(int(exc.code), message) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Microsoft Graph transport error: {type(exc).__name__}") from None


def _timestamp(value: Any) -> Optional[float]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _safe_target(value: Any) -> str:
    raw = str(value or "").strip()
    if len(raw) > 512 or any(ch in raw for ch in "\r\n\x00"):
        raise ValueError("Microsoft To Do list id 非法")
    return raw


def _task_body_text(raw: dict[str, Any]) -> tuple[str, str]:
    body = raw.get("body") if isinstance(raw.get("body"), dict) else {}
    return str(body.get("content") or "")[:20_000], str(body.get("contentType") or "")[:40]


class MicrosoftTodoGraphAdapter:
    provider_id = "MICROSOFT_GRAPH"
    capabilities = {"project.read", "task.create"}

    def __init__(
        self,
        *,
        api_base: str = "",
        transport: Optional[Transport] = None,
    ):
        configured = str(
            api_base or os.environ.get("CHENGZHU_MICROSOFT_GRAPH_API_BASE") or _DEFAULT_API_BASE
        ).strip()
        self.api_base = configured.rstrip("/")
        parts = urlsplit(self.api_base)
        if parts.scheme != "https" or not parts.hostname:
            raise ValueError("Microsoft Graph API base 必须使用 HTTPS；Bearer token 不允许明文 HTTP 出站")
        self._api_host = parts.hostname.lower()
        self._transport = transport or _urllib_transport

    @staticmethod
    def _resolve_token(connection: dict[str, Any]) -> str:
        credential_ref = str(connection.get("credential_ref") or "").strip()
        match = _ENV_REF_RE.fullmatch(credential_ref)
        if not match:
            raise ValueError(
                "Microsoft To Do credential_ref 当前只支持 "
                "provider:microsoft-graph:env:<ENV_VAR>；access token 本身不能写入 product.db"
            )
        env_name = match.group(1)
        token = str(os.environ.get(env_name) or "").strip()
        if not token:
            raise ValueError(f"Microsoft Graph credential environment variable 未设置：{env_name}")
        return token

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Chengzhu/2.0",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> tuple[int, dict[str, str], Any]:
        query = urlencode(
            [(str(k), str(v)) for k, v in (params or {}).items() if v not in (None, "", [])],
            doseq=True,
        )
        url = f"{self.api_base}{path}"
        if query:
            url = f"{url}?{query}"
        headers = self._headers(token)
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return self._transport(method, url, headers, body, _timeout_seconds())

    def _request_next(self, next_url: str, *, token: str) -> tuple[int, dict[str, str], Any]:
        parts = urlsplit(str(next_url or ""))
        if (
            parts.scheme != "https"
            or (parts.hostname or "").lower() != self._api_host
            or not parts.path.startswith("/v1.0/")
        ):
            raise RuntimeError("Microsoft Graph nextLink 越出受信任 API 边界；拒绝转发 Bearer token")
        return self._transport("GET", next_url, self._headers(token), None, _timeout_seconds())

    def _list_task_lists(self, token: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        status, _headers, payload = self._request(
            "GET",
            "/me/todo/lists",
            token=token,
            params={"$top": 100, "$select": "id,displayName,isOwner,isShared,wellknownListName"},
        )
        while True:
            if status != 200 or not isinstance(payload, dict) or not isinstance(payload.get("value", []), list):
                raise RuntimeError(f"Microsoft To Do list discovery returned ambiguous HTTP {status}")
            rows.extend(row for row in payload.get("value", []) if isinstance(row, dict))
            next_url = str(payload.get("@odata.nextLink") or "")
            if not next_url:
                break
            if len(rows) > 1000:
                raise ValueError("Microsoft To Do task-list discovery 超过安全上限 1000")
            status, _headers, payload = self._request_next(next_url, token=token)
        return rows

    def _resolve_list(
        self,
        *,
        connection: dict[str, Any],
        target: str,
        token: str,
    ) -> dict[str, Any]:
        raw = _safe_target(target)
        if raw.lower() in _DEFAULT_LIST_ALIASES:
            lists = self._list_task_lists(token)
            match = next(
                (item for item in lists if str(item.get("wellknownListName") or "") == "defaultList"),
                None,
            )
            if not match:
                raise MicrosoftTodoTargetError(404, "Microsoft To Do 没有找到 built-in defaultList")
            return {
                "id": str(match.get("id") or ""),
                "displayName": str(match.get("displayName") or "Tasks")[:300],
                "wellknownListName": "defaultList",
                "isOwner": bool(match.get("isOwner")),
                "isShared": bool(match.get("isShared")),
            }

        if not raw:
            raise ValueError("Microsoft To Do list id 不能为空")
        try:
            status, _headers, payload = self._request(
                "GET",
                f"/me/todo/lists/{quote(raw, safe='')}",
                token=token,
                params={"$select": "id,displayName,isOwner,isShared,wellknownListName"},
            )
        except MicrosoftTodoProviderError as exc:
            if exc.status != 401 and 400 <= exc.status < 500:
                raise MicrosoftTodoTargetError(exc.status, str(exc)) from None
            raise
        if status != 200 or not isinstance(payload, dict) or not payload.get("id"):
            raise RuntimeError(f"Microsoft To Do list lookup returned ambiguous HTTP {status}")
        return {
            "id": str(payload.get("id") or ""),
            "displayName": str(payload.get("displayName") or "")[:300],
            "wellknownListName": str(payload.get("wellknownListName") or "")[:80],
            "isOwner": bool(payload.get("isOwner")),
            "isShared": bool(payload.get("isShared")),
        }

    def health(self, connection: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if connection is None:
            return {
                "ok": True,
                "label": "Microsoft To Do (Graph)",
                "runtime": "OPT_IN_REAL_PROVIDER",
            }

        token = self._resolve_token(connection)
        status, _headers, profile = self._request(
            "GET",
            "/me",
            token=token,
            params={"$select": "id,displayName,mail,userPrincipalName"},
        )
        if status != 200 or not isinstance(profile, dict) or not profile.get("id"):
            return {"ok": False, "error": f"Microsoft Graph /me verify returned HTTP {status}"}

        # Verify the task permission without importing or persisting any task.
        # Tasks.ReadWrite includes read; both supported connection shapes can
        # therefore safely perform this one-row probe.
        status, _headers, lists = self._request(
            "GET",
            "/me/todo/lists",
            token=token,
            params={"$top": 1, "$select": "id"},
        )
        if status != 200 or not isinstance(lists, dict) or not isinstance(lists.get("value", []), list):
            return {"ok": False, "error": f"Microsoft To Do permission probe returned HTTP {status}"}

        hint = str(
            profile.get("mail")
            or profile.get("userPrincipalName")
            or profile.get("displayName")
            or ""
        )[:300]
        return {
            "ok": True,
            "label": "Microsoft To Do",
            "account_hint": hint,
            "provider_user_id": str(profile.get("id") or "")[:200],
            "display_name": str(profile.get("displayName") or "")[:300],
            "verify": "USER_READ_PLUS_TODO_READ_PROBE",
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
        if capability != "project.read":
            raise ValueError("Microsoft To Do read adapter 只支持 project.read")

        token = self._resolve_token(connection)
        requested_target = str(
            query.get("todo_list_id")
            or query.get("task_list_id")
            or query.get("list_id")
            or "defaultList"
        )
        task_list = self._resolve_list(connection=connection, target=requested_target, token=token)
        list_id = task_list["id"]
        if not list_id:
            raise RuntimeError("Microsoft To Do resolved task list 缺少 id")

        status, _headers, payload = self._request(
            "GET",
            f"/me/todo/lists/{quote(list_id, safe='')}/tasks",
            token=token,
            params={"$top": _PAGE_SIZE},
        )
        rows: list[dict[str, Any]] = []
        while True:
            if status != 200 or not isinstance(payload, dict) or not isinstance(payload.get("value", []), list):
                raise RuntimeError(f"Microsoft To Do tasks sync returned ambiguous HTTP {status}")
            rows.extend(row for row in payload.get("value", []) if isinstance(row, dict))
            if len(rows) > _MAX_TASKS_PER_SYNC:
                raise ValueError(
                    f"Microsoft To Do 单次完整同步超过安全上限 {_MAX_TASKS_PER_SYNC}；"
                    "为避免半同步，不写入 snapshots。"
                )
            next_url = str(payload.get("@odata.nextLink") or "")
            if not next_url:
                break
            status, _headers, payload = self._request_next(next_url, token=token)

        requested_limit = max(1, min(int(limit), 500))
        if len(rows) > requested_limit:
            raise ValueError(
                f"Microsoft To Do 当前 task list 有 {len(rows)} 条任务，超过 Chengzhu 当前安全写入上限 "
                f"{requested_limit}；拒绝半同步。"
            )

        snapshots: list[dict[str, Any]] = []
        for raw in rows:
            task_id = str(raw.get("id") or "").strip()
            if not task_id:
                continue
            body_text, body_type = _task_body_text(raw)
            status_text = str(raw.get("status") or "")[:80]
            completed = raw.get("completedDateTime") if isinstance(raw.get("completedDateTime"), dict) else {}
            due = raw.get("dueDateTime") if isinstance(raw.get("dueDateTime"), dict) else {}
            snapshots.append({
                "external_kind": "TASK",
                "external_id": f"{list_id}:{task_id}",
                "title": str(raw.get("title") or "Untitled task")[:500],
                "excerpt": body_text,
                "source_url": "",
                "occurred_at": _timestamp(raw.get("lastModifiedDateTime") or raw.get("createdDateTime")),
                "visibility": "PRIVATE",
                "metadata": {
                    "todo_list_id": list_id,
                    "todo_list_name": task_list.get("displayName") or "",
                    "wellknown_list_name": task_list.get("wellknownListName") or "",
                    "task_id": task_id,
                    "status": status_text,
                    "importance": str(raw.get("importance") or "")[:80],
                    "body_content_type": body_type,
                    "created_at": str(raw.get("createdDateTime") or "")[:100],
                    "last_modified_at": str(raw.get("lastModifiedDateTime") or "")[:100],
                    "due": due,
                    "completed": completed,
                    "categories": [str(x)[:100] for x in (raw.get("categories") or [])[:50]],
                    "is_reminder_on": bool(raw.get("isReminderOn")),
                    "list_is_owner": bool(task_list.get("isOwner")),
                    "list_is_shared": bool(task_list.get("isShared")),
                },
            })

        return {
            "items": snapshots,
            "next_cursor": "",
            "todo_list_id": list_id,
            "todo_list_name": task_list.get("displayName") or "",
            "full_refresh": True,
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
        if capability != "task.create" or operation != "CREATE_TASK":
            return {
                "ok": False,
                "error": "Microsoft To Do adapter 只支持 reviewed CREATE_TASK / task.create",
                "retry_safe": False,
            }

        title = str(payload.get("title") or "").strip()
        content = str(payload.get("content") or "").rstrip()
        if not title:
            return {"ok": False, "error": "Microsoft To Do task title 不能为空", "retry_safe": False}
        if len(title) > 255:
            return {
                "ok": False,
                "error": "Microsoft To Do task title 超过 Chengzhu 安全上限 255；拒绝静默截断已审核标题",
                "retry_safe": False,
            }
        if len(content) > 20_000:
            return {
                "ok": False,
                "error": "Microsoft To Do task body 超过 Chengzhu 安全上限 20000；拒绝静默截断已审核正文",
                "retry_safe": False,
            }
        if bool(payload.get("outbound_redaction_applied")):
            return {
                "ok": False,
                "error": "安全层改写了已审核 Task 内容；请移除敏感值并重新审核 Draft 后再执行",
                "retry_safe": False,
            }

        # Do not touch Microsoft Graph for invalid/review-changed content.
        token = self._resolve_token(connection)
        try:
            task_list = self._resolve_list(connection=connection, target=target or "defaultList", token=token)
        except Exception as exc:
            # Target resolution is GET-only. No task-create side effect has
            # been attempted yet, so even an ambiguous lookup transport error
            # is safe to retry after the user fixes/rechecks the target/account.
            status = getattr(exc, "status", None)
            return {
                "ok": False,
                "error": str(exc)[:2000] or "Microsoft To Do list target resolution failed",
                "retry_safe": True,
                "stage": "TARGET_RESOLUTION",
                **({"http_status": int(status)} if isinstance(status, int) else {}),
            }
        list_id = task_list["id"]

        request_payload: dict[str, Any] = {"title": title}
        if content:
            request_payload["body"] = {"content": content, "contentType": "text"}

        try:
            status, _headers, result = self._request(
                "POST",
                f"/me/todo/lists/{quote(list_id, safe='')}/tasks",
                token=token,
                payload=request_payload,
            )
        except MicrosoftTodoProviderError as exc:
            if 400 <= exc.status < 500 and exc.status not in {408, 425, 429}:
                return {
                    "ok": False,
                    "error": str(exc),
                    "retry_safe": False,
                    "http_status": exc.status,
                }
            raise

        if status != 201 or not isinstance(result, dict) or not result.get("id"):
            raise RuntimeError(f"Microsoft To Do create task returned ambiguous HTTP {status}")

        return {
            "ok": True,
            "provider_id": "MICROSOFT_GRAPH",
            "provider_surface": "MICROSOFT_TODO",
            "todo_list_id": list_id,
            "todo_list_name": task_list.get("displayName") or "",
            "task_id": str(result.get("id") or "")[:500],
            "task_title": str(result.get("title") or title)[:500],
            "task_status": str(result.get("status") or "")[:80],
            "provider_idempotency": "NONE",
            "idempotency_key_audit_only": str(idempotency_key or "")[:128],
        }


def register_microsoft_todo_adapter_from_env() -> dict[str, Any]:
    """Register the To Do subset only after explicit runtime opt-in."""
    enabled = str(os.environ.get("CHENGZHU_MICROSOFT_TODO_CONNECTOR_ENABLE") or "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return {"registered": False, "provider_id": "MICROSOFT_GRAPH", "reason": "NOT_ENABLED"}

    from services.product import conversation_integrations

    adapter = MicrosoftTodoGraphAdapter()
    conversation_integrations.register_adapter(adapter)
    return {
        "registered": True,
        "provider_id": "MICROSOFT_GRAPH",
        "surface": "MICROSOFT_TODO",
        "capabilities": sorted(adapter.capabilities),
        "credential_ref_format": "provider:microsoft-graph:env:<ENV_VAR>",
        "identity_scope": "User.Read",
        "task_read_scope": "Tasks.Read",
        "task_write_scope": "Tasks.ReadWrite",
        "mail_calendar_files_support": "NONE_IN_THIS_ADAPTER",
    }
