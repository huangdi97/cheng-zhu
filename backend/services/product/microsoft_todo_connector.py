"""Opt-in Microsoft To Do provider for reviewed Conversation task execution.

This adapter deliberately supports only canonical `task.create`.

Delegated permission:
- Tasks.ReadWrite

Credential material is resolved from a process environment variable referenced
by an opaque product.db handle:

    provider:microsoft-graph:env:CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN

The token itself never enters product.db, frontend state, snapshots or exports.
The provider does not claim Calendar/Mail/Files support and performs no
background sync.

Microsoft Graph To Do task creation does not expose a Chengzhu-usable
idempotency primitive. Ambiguous transport/server outcomes therefore bubble up
so the shared execution boundary records UNKNOWN_OUTCOME and forbids automatic
retry.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


_DEFAULT_GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
_ENV_REF_RE = re.compile(
    r"^provider:microsoft-graph:env:([A-Za-z_][A-Za-z0-9_]{0,127})$"
)


class MicrosoftGraphProviderError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = int(status)


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


Transport = Callable[
    [str, str, dict[str, str], Optional[bytes], float],
    tuple[int, dict[str, str], Any],
]


def _timeout_seconds() -> float:
    raw = str(os.environ.get("CHENGZHU_MICROSOFT_GRAPH_TIMEOUT_SECONDS") or "15").strip()
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
            if isinstance(parsed, dict):
                error = parsed.get("error") or {}
                if isinstance(error, dict) and error.get("message"):
                    message = f"{message}: {str(error['message'])[:1000]}"
        except Exception:
            pass
        raise MicrosoftGraphProviderError(int(exc.code), message) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Microsoft Graph transport error: {type(exc).__name__}") from None


class MicrosoftTodoTaskAdapter:
    provider_id = "MICROSOFT_GRAPH"
    capabilities = {"task.create"}

    def __init__(
        self,
        *,
        api_base: str = "",
        transport: Optional[Transport] = None,
    ):
        self.api_base = str(
            api_base
            or os.environ.get("CHENGZHU_MICROSOFT_GRAPH_API_BASE")
            or _DEFAULT_GRAPH_API_BASE
        ).strip().rstrip("/")
        if not self.api_base.startswith("https://"):
            raise ValueError("Microsoft Graph API base 必须使用 HTTPS；Bearer token 不允许明文 HTTP 出站")
        self._transport = transport or _urllib_transport

    @staticmethod
    def _resolve_token(connection: dict[str, Any]) -> str:
        credential_ref = str(connection.get("credential_ref") or "").strip()
        match = _ENV_REF_RE.fullmatch(credential_ref)
        if not match:
            raise ValueError(
                "Microsoft Graph credential_ref 当前只支持 "
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
            [(str(k), str(v)) for k, v in (params or {}).items() if v not in (None, "", [])]
        )
        url = f"{self.api_base}{path}"
        if query:
            url = f"{url}?{query}"
        headers = self._headers(token)
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        return self._transport(method, url, headers, body, _timeout_seconds())

    def _list_task_lists(self, token: str) -> list[dict[str, Any]]:
        status, _headers, payload = self._request(
            "GET",
            "/me/todo/lists",
            token=token,
            params={
                "$top": 100,
                "$select": "id,displayName,isOwner,isShared,wellknownListName",
            },
        )
        if status != 200 or not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
            raise RuntimeError(f"Microsoft To Do list probe returned ambiguous HTTP {status}")
        return [row for row in payload["value"] if isinstance(row, dict)]

    def health(self, connection: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if connection is None:
            return {
                "ok": True,
                "label": "Microsoft To Do task.create adapter",
                "runtime": "OPT_IN_REAL_PROVIDER",
            }
        token = self._resolve_token(connection)
        try:
            lists = self._list_task_lists(token)
        except MicrosoftGraphProviderError as exc:
            return {"ok": False, "error": str(exc), "http_status": exc.status}

        default_list = next(
            (row for row in lists if str(row.get("wellknownListName") or "") == "defaultList"),
            None,
        )
        return {
            "ok": True,
            "label": "Microsoft To Do",
            "account_hint": "Microsoft To Do",
            "verify": "TASKS_READWRITE_TODO_LIST_PROBE",
            "default_list_present": default_list is not None,
            "default_list_name": str((default_list or {}).get("displayName") or "")[:160],
            "task_create_capability_proof": "PENDING_FIRST_EXPLICIT_EXECUTION",
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
        raise ValueError("Microsoft To Do v1 provider 是 task.create only；不实现 project.read / task sync")

    @staticmethod
    def _target(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return "default"
        if len(raw) > 500 or any(ch in raw for ch in "\r\n\x00/?#"):
            raise ValueError("Microsoft To Do target 必须是 default 或明确 task-list id")
        return raw

    def _resolve_list(
        self,
        *,
        token: str,
        target: str,
    ) -> tuple[str, str]:
        if target.lower() == "default":
            lists = self._list_task_lists(token)
            row = next(
                (item for item in lists if str(item.get("wellknownListName") or "") == "defaultList"),
                None,
            )
            if not row or not row.get("id"):
                raise ValueError("Microsoft To Do 没有返回 built-in default Tasks list")
            return str(row["id"]), str(row.get("displayName") or "Tasks")[:160]

        encoded = quote(target, safe="")
        status, _headers, payload = self._request(
            "GET",
            f"/me/todo/lists/{encoded}",
            token=token,
            params={"$select": "id,displayName,isOwner,isShared,wellknownListName"},
        )
        if status != 200 or not isinstance(payload, dict) or not payload.get("id"):
            raise RuntimeError(f"Microsoft To Do target probe returned ambiguous HTTP {status}")
        return str(payload["id"]), str(payload.get("displayName") or "")[:160]

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
        if bool(payload.get("outbound_redaction_applied")):
            return {
                "ok": False,
                "error": "执行前安全层检测到并替换了疑似 secret；请回到 Draft 重新审核后再创建新的 Execution Request",
                "retry_safe": False,
            }

        title = str(payload.get("title") or "").strip()
        content = str(payload.get("content") or "")
        if not title or any(ch in title for ch in "\r\n\x00"):
            return {"ok": False, "error": "Task 标题不能为空或包含换行", "retry_safe": False}
        if len(title) > 500:
            return {
                "ok": False,
                "error": "Task 标题超过 500 字符；不会静默截断已审核标题，请修改 Draft 后重新审核",
                "retry_safe": False,
            }
        if len(content) > 20_000:
            return {
                "ok": False,
                "error": "Task 正文超过 20000 字符；不会静默截断已审核内容，请修改 Draft 后重新审核",
                "retry_safe": False,
            }

        token = self._resolve_token(connection)
        try:
            list_target = self._target(target)
            list_id, list_name = self._resolve_list(token=token, target=list_target)
        except (ValueError, MicrosoftGraphProviderError) as exc:
            if isinstance(exc, MicrosoftGraphProviderError):
                if 400 <= exc.status < 500 and exc.status not in {408, 425, 429}:
                    return {
                        "ok": False,
                        "error": str(exc),
                        "retry_safe": False,
                        "http_status": exc.status,
                    }
            if isinstance(exc, ValueError):
                return {"ok": False, "error": str(exc), "retry_safe": False}
            raise

        task_payload: dict[str, Any] = {
            "title": title,
            "body": {
                "contentType": "text",
                "content": content,
            },
        }
        encoded_list_id = quote(list_id, safe="")
        try:
            status, _response_headers, result = self._request(
                "POST",
                f"/me/todo/lists/{encoded_list_id}/tasks",
                token=token,
                payload=task_payload,
            )
        except MicrosoftGraphProviderError as exc:
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
            "external_id": str(result.get("id") or "")[:500],
            "task_id": str(result.get("id") or "")[:500],
            "task_list_id": list_id[:500],
            "task_list_name": list_name,
            "target": list_target,
            "provider_idempotency": "NONE",
            "reviewed_payload_unchanged": True,
        }


def register_microsoft_todo_adapter_from_env() -> dict[str, Any]:
    enabled = str(os.environ.get("CHENGZHU_MICROSOFT_TODO_CONNECTOR_ENABLE") or "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return {"registered": False, "provider_id": "MICROSOFT_GRAPH", "reason": "NOT_ENABLED"}

    from services.product import conversation_integrations

    adapter = MicrosoftTodoTaskAdapter()
    conversation_integrations.register_adapter(adapter)
    return {
        "registered": True,
        "provider_id": "MICROSOFT_GRAPH",
        "capabilities": sorted(adapter.capabilities),
        "credential_ref_format": "provider:microsoft-graph:env:<ENV_VAR>",
        "delegated_permission": "Tasks.ReadWrite",
        "read_capabilities": [],
        "write_capabilities": ["task.create"],
        "default_target": "default",
    }
