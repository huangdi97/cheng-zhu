"""Opt-in MCP provider for reviewed Conversation decision-log write-back.

This adapter intentionally exposes exactly one Chengzhu capability:

    decision_log.write

The concrete MCP endpoint/tool mapping lives in a process environment variable
referenced by an opaque product.db handle:

    provider:mcp:env:CHENGZHU_MCP_DECISION_LOG_CONFIG

Example config env value (configuration only; no raw token):

    {
      "endpoint": "https://mcp.example.com/mcp",
      "tool_name": "chengzhu_update_decision_log",
      "bearer_token_env": "CHENGZHU_MCP_BEARER_TOKEN",
      "account_hint": "work-mcp"
    }

The bearer token, when needed, is resolved from bearer_token_env and never
enters product.db, frontend state, exports or execution audit.

Protocol scope:
- MCP Streamable HTTP
- modern protocol revision 2026-07-28
- server/discover + tools/list verification
- tools/call execution

Legacy initialize/session negotiation is deliberately not hand-rolled here.
A server that does not speak the modern revision remains fail-closed instead of
being guessed compatible.

The configured tool must advertise object input properties:
- title: string
- content: string
- target: string
- idempotency_key: string

Chengzhu never lets the frontend choose an arbitrary MCP tool.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


_PROTOCOL_VERSION = "2026-07-28"
_CONFIG_REF_RE = re.compile(r"^provider:mcp:env:([A-Za-z_][A-Za-z0-9_]{0,127})$")
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_.:/-]{1,200}$")
_REQUIRED_TOOL_FIELDS = ("title", "content", "target", "idempotency_key")


class McpProviderError(RuntimeError):
    def __init__(self, status: int, message: str, *, pre_write: bool = False):
        super().__init__(message)
        self.status = int(status)
        self.pre_write = bool(pre_write)


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


Transport = Callable[
    [str, str, dict[str, str], bytes, float],
    tuple[int, dict[str, str], bytes],
]


def _timeout_seconds() -> float:
    raw = str(os.environ.get("CHENGZHU_MCP_TIMEOUT_SECONDS") or "15").strip()
    try:
        return max(2.0, min(float(raw), 60.0))
    except ValueError:
        return 15.0


def _urllib_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes,
    timeout: float,
) -> tuple[int, dict[str, str], bytes]:
    request = Request(url=url, data=body, method=method, headers=headers)
    opener = build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            return int(response.status), dict(response.headers.items()), response.read()
    except HTTPError as exc:
        raw = exc.read(32_768)
        message = f"MCP HTTP {exc.code}"
        try:
            parsed = _decode_response(raw, str(exc.headers.get("Content-Type") or ""))
            error = parsed.get("error") if isinstance(parsed, dict) else None
            if isinstance(error, dict) and error.get("message"):
                message = f"{message}: {str(error['message'])[:1000]}"
        except Exception:
            pass
        raise McpProviderError(int(exc.code), message) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"MCP transport error: {type(exc).__name__}") from None


def _decode_response(raw: bytes, content_type: str) -> dict[str, Any]:
    if not raw:
        raise RuntimeError("MCP returned an empty response")
    text = raw.decode("utf-8", errors="strict").strip()
    if "text/event-stream" in str(content_type or "").lower() or text.startswith("event:") or text.startswith("data:"):
        for line in text.splitlines():
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload:
                    decoded = json.loads(payload)
                    if isinstance(decoded, dict):
                        return decoded
        raise RuntimeError("MCP SSE response did not contain a JSON data event")
    decoded = json.loads(text)
    if not isinstance(decoded, dict):
        raise RuntimeError("MCP response must be a JSON object")
    return decoded


def _is_loopback_host(host: str) -> bool:
    normalized = str(host or "").strip().lower()
    if normalized in {"localhost", "localhost."}:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _validate_endpoint(value: str) -> str:
    endpoint = str(value or "").strip()
    if len(endpoint) > 2000:
        raise ValueError("MCP endpoint 过长")
    parts = urlsplit(endpoint)
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("MCP endpoint 不允许 userinfo/query/fragment；secret 必须走独立 bearer token env")
    if not parts.hostname:
        raise ValueError("MCP endpoint 缺少 host")
    if parts.scheme == "https":
        return endpoint.rstrip("/")
    if parts.scheme == "http" and _is_loopback_host(parts.hostname):
        return endpoint.rstrip("/")
    raise ValueError("MCP endpoint 必须使用 HTTPS；仅 localhost/loopback 开发服务允许 HTTP")


class McpDecisionLogAdapter:
    provider_id = "MCP"
    capabilities = {"decision_log.write"}

    def __init__(self, *, transport: Optional[Transport] = None):
        self._transport = transport or _urllib_transport

    @staticmethod
    def _config(connection: dict[str, Any]) -> dict[str, str]:
        credential_ref = str(connection.get("credential_ref") or "").strip()
        match = _CONFIG_REF_RE.fullmatch(credential_ref)
        if not match:
            raise ValueError(
                "MCP credential_ref 当前只支持 provider:mcp:env:<CONFIG_ENV>；"
                "endpoint/tool/token 不得直接写入 product.db"
            )
        config_env = match.group(1)
        raw = str(os.environ.get(config_env) or "").strip()
        if not raw:
            raise ValueError(f"MCP config environment variable 未设置：{config_env}")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"MCP config env 不是合法 JSON：{exc.msg}") from None
        if not isinstance(parsed, dict):
            raise ValueError("MCP config env 必须是 JSON object")

        endpoint = _validate_endpoint(str(parsed.get("endpoint") or ""))
        tool_name = str(parsed.get("tool_name") or "").strip()
        if not _TOOL_NAME_RE.fullmatch(tool_name):
            raise ValueError("MCP tool_name 只能使用明确的安全字符，且不能为空")

        token_env = str(parsed.get("bearer_token_env") or "").strip()
        if token_env and not _ENV_NAME_RE.fullmatch(token_env):
            raise ValueError("MCP bearer_token_env 必须是环境变量名，不能内嵌 token")
        if any(key in parsed for key in ("token", "access_token", "authorization", "bearer_token", "secret")):
            raise ValueError("MCP config env 不允许内嵌 token/secret；请使用 bearer_token_env")

        account_hint = str(parsed.get("account_hint") or urlsplit(endpoint).hostname or "MCP")[:300]
        return {
            "endpoint": endpoint,
            "tool_name": tool_name,
            "bearer_token_env": token_env,
            "account_hint": account_hint,
        }

    @staticmethod
    def _authorization(config: dict[str, str]) -> str:
        token_env = str(config.get("bearer_token_env") or "")
        if not token_env:
            return ""
        token = str(os.environ.get(token_env) or "").strip()
        if not token:
            raise ValueError(f"MCP bearer token environment variable 未设置：{token_env}")
        return f"Bearer {token}"

    @staticmethod
    def _meta() -> dict[str, Any]:
        return {
            "io.modelcontextprotocol/protocolVersion": _PROTOCOL_VERSION,
            "io.modelcontextprotocol/clientInfo": {
                "name": "Chengzhu",
                "version": "2.0",
            },
            "io.modelcontextprotocol/clientCapabilities": {},
        }

    def _rpc(
        self,
        config: dict[str, str],
        *,
        method: str,
        params: Optional[dict[str, Any]] = None,
        name: str = "",
        request_id: int = 1,
        pre_write: bool,
    ) -> dict[str, Any]:
        rpc_params = dict(params or {})
        rpc_params["_meta"] = self._meta()
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": rpc_params,
        }
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": _PROTOCOL_VERSION,
            "Mcp-Method": method,
            "User-Agent": "Chengzhu/2.0",
        }
        if name:
            headers["Mcp-Name"] = name
        authorization = self._authorization(config)
        if authorization:
            headers["Authorization"] = authorization

        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            status, response_headers, raw = self._transport(
                "POST",
                config["endpoint"],
                headers,
                body,
                _timeout_seconds(),
            )
        except McpProviderError as exc:
            exc.pre_write = pre_write
            raise
        except RuntimeError:
            raise

        if status < 200 or status >= 300:
            raise McpProviderError(status, f"MCP HTTP {status}", pre_write=pre_write)
        content_type = ""
        for key, value in response_headers.items():
            if str(key).lower() == "content-type":
                content_type = str(value)
                break
        decoded = _decode_response(raw, content_type)
        if decoded.get("id") not in {request_id, str(request_id)}:
            raise RuntimeError("MCP JSON-RPC response id mismatch")
        error = decoded.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or "MCP JSON-RPC error")[:1000]
            code = error.get("code")
            raise McpProviderError(400, f"MCP RPC {code}: {message}", pre_write=pre_write)
        result = decoded.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("MCP JSON-RPC response missing object result")
        return result

    @staticmethod
    def _validate_tool(tool: dict[str, Any], expected_name: str) -> None:
        if str(tool.get("name") or "") != expected_name:
            raise ValueError("MCP configured decision-log tool name mismatch")
        schema = tool.get("inputSchema")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ValueError("MCP decision-log tool inputSchema 必须是 object")
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            raise ValueError("MCP decision-log tool inputSchema 缺少 properties")
        for field in _REQUIRED_TOOL_FIELDS:
            spec = properties.get(field)
            if not isinstance(spec, dict) or spec.get("type") != "string":
                raise ValueError(
                    "MCP decision-log tool 必须接受 canonical string field："
                    + ", ".join(_REQUIRED_TOOL_FIELDS)
                )

    def _discover_and_tool(self, config: dict[str, str]) -> dict[str, Any]:
        discover = self._rpc(
            config,
            method="server/discover",
            params={},
            request_id=1,
            pre_write=True,
        )
        supported = discover.get("supportedVersions")
        if isinstance(supported, list) and _PROTOCOL_VERSION not in [str(v) for v in supported]:
            raise ValueError(f"MCP server 不声明支持 {_PROTOCOL_VERSION}")

        listed = self._rpc(
            config,
            method="tools/list",
            params={},
            request_id=2,
            pre_write=True,
        )
        tools = listed.get("tools")
        if not isinstance(tools, list):
            raise ValueError("MCP tools/list 未返回 tools array")
        tool = next(
            (item for item in tools if isinstance(item, dict) and str(item.get("name") or "") == config["tool_name"]),
            None,
        )
        if tool is None:
            raise ValueError(f"MCP server 未暴露配置的 decision-log tool：{config['tool_name']}")
        self._validate_tool(tool, config["tool_name"])
        return {
            "discover": discover,
            "tool": tool,
        }

    def health(self, connection: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if connection is None:
            return {
                "ok": True,
                "label": "MCP decision_log.write adapter",
                "runtime": "OPT_IN_REAL_PROVIDER",
                "protocol": _PROTOCOL_VERSION,
            }
        config = self._config(connection)
        try:
            proof = self._discover_and_tool(config)
        except (ValueError, McpProviderError, RuntimeError) as exc:
            return {"ok": False, "error": str(exc)}
        tool = proof["tool"]
        return {
            "ok": True,
            "label": "MCP decision log",
            "account_hint": config["account_hint"],
            "verify": "SERVER_DISCOVER_PLUS_EXACT_TOOL_SCHEMA",
            "protocol": _PROTOCOL_VERSION,
            "tool_name": str(tool.get("name") or ""),
            "decision_log_write_capability_proof": "PENDING_FIRST_EXPLICIT_EXECUTION",
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
        raise ValueError("MCP v1 concrete provider 是 decision_log.write only；不实现 read sync")

    @staticmethod
    def _target(value: str) -> str:
        target = str(value or "").strip()
        if not target:
            raise ValueError("MCP Decision Log 外部执行必须明确 target")
        if len(target) > 500 or any(ch in target for ch in "\r\n\x00"):
            raise ValueError("MCP Decision Log target 非法")
        return target

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
        if capability != "decision_log.write" or operation != "UPDATE_DECISION_LOG":
            return {
                "ok": False,
                "error": "MCP concrete adapter 只支持 reviewed UPDATE_DECISION_LOG / decision_log.write",
                "retry_safe": False,
            }
        if bool(payload.get("outbound_redaction_applied")):
            return {
                "ok": False,
                "error": "执行前安全层改写了 reviewed Draft；请移除 secret 后重新审核并创建新的 Execution Request",
                "retry_safe": False,
            }

        title = str(payload.get("title") or "").strip()
        content = str(payload.get("content") or "")
        if not title or any(ch in title for ch in "\r\n\x00"):
            return {"ok": False, "error": "Decision Log 标题不能为空或包含换行", "retry_safe": False}
        if len(title) > 500:
            return {
                "ok": False,
                "error": "Decision Log 标题超过 500 字符；不会静默截断已审核标题",
                "retry_safe": False,
            }
        if len(content) > 20_000:
            return {
                "ok": False,
                "error": "Decision Log 正文超过 20000 字符；不会静默截断已审核内容",
                "retry_safe": False,
            }

        try:
            exact_target = self._target(target)
            config = self._config(connection)
            # Re-verify exact tool schema immediately before a side effect.
            self._discover_and_tool(config)
        except ValueError as exc:
            # Deterministic local/config/schema failure. No side effect happened,
            # but replaying the same immutable Execution Request cannot fix it.
            return {
                "ok": False,
                "error": str(exc),
                "retry_safe": False,
                "phase": "MCP_PREFLIGHT_PRE_WRITE",
            }
        except McpProviderError as exc:
            # server/discover/tools/list are pre-write. Throttle/server failures
            # can be retried safely because tools/call was never issued.
            return {
                "ok": False,
                "error": str(exc),
                "retry_safe": exc.status in {408, 425, 429} or exc.status >= 500,
                "http_status": exc.status,
                "phase": "MCP_PREFLIGHT_PRE_WRITE",
            }
        except RuntimeError as exc:
            # Transport/decoding failure during read-only preflight happened
            # before tools/call, so an identical request is safe to retry.
            return {
                "ok": False,
                "error": str(exc),
                "retry_safe": True,
                "phase": "MCP_PREFLIGHT_PRE_WRITE",
            }

        arguments = {
            "title": title,
            "content": content,
            "target": exact_target,
            "idempotency_key": str(idempotency_key or ""),
        }
        try:
            result = self._rpc(
                config,
                method="tools/call",
                name=config["tool_name"],
                params={
                    "name": config["tool_name"],
                    "arguments": arguments,
                },
                request_id=3,
                pre_write=False,
            )
        except McpProviderError as exc:
            if 400 <= exc.status < 500 and exc.status not in {408, 425, 429}:
                return {
                    "ok": False,
                    "error": str(exc),
                    "retry_safe": False,
                    "http_status": exc.status,
                }
            raise

        if bool(result.get("isError")):
            return {
                "ok": False,
                "error": "MCP tool returned isError=true",
                "retry_safe": False,
                "provider_result_type": str(result.get("resultType") or ""),
            }

        result_type = str(result.get("resultType") or "complete")
        if result_type != "complete":
            raise RuntimeError(
                f"MCP decision-log tool returned non-final resultType={result_type}; "
                "Chengzhu v1 does not drive MRTR/tasks for external write-back"
            )

        return {
            "ok": True,
            "provider_id": "MCP",
            "tool_name": config["tool_name"],
            "target": exact_target,
            "provider_result_type": result_type,
            "provider_idempotency": "UNVERIFIED_APPLICATION_ARGUMENT",
            "reviewed_payload_unchanged": True,
        }


def register_mcp_decision_log_adapter_from_env() -> dict[str, Any]:
    enabled = str(os.environ.get("CHENGZHU_MCP_DECISION_LOG_CONNECTOR_ENABLE") or "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return {"registered": False, "provider_id": "MCP", "reason": "NOT_ENABLED"}

    from services.product import conversation_integrations

    adapter = McpDecisionLogAdapter()
    conversation_integrations.register_adapter(adapter)
    return {
        "registered": True,
        "provider_id": "MCP",
        "capabilities": sorted(adapter.capabilities),
        "credential_ref_format": "provider:mcp:env:<CONFIG_ENV>",
        "protocol": _PROTOCOL_VERSION,
        "read_capabilities": [],
        "write_capabilities": ["decision_log.write"],
    }
