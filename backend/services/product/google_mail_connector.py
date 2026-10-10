"""Opt-in Gmail send-only provider for reviewed Conversation follow-up execution.

This adapter deliberately supports only `email.send`.

OAuth/access requirements:
- openid
- email
- https://www.googleapis.com/auth/gmail.send

The identity scopes exist only so Chengzhu can verify which Google account the
token represents through Google's OIDC UserInfo endpoint.  No Gmail mailbox
read scope is requested or supported.

Credential material is resolved from a process environment variable referenced
by an opaque product.db handle:

    provider:google-mail:env:CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN

The access token itself never enters product.db, frontend state, snapshots or
exports.  Gmail has no provider-side idempotency primitive for messages.send;
ambiguous transport/server outcomes therefore bubble up so the shared external
execution boundary records UNKNOWN_OUTCOME and forbids automatic retry.
"""
from __future__ import annotations

import base64
import json
import os
import re
from email.headerregistry import Address
from email.message import EmailMessage
from email.policy import SMTP
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


_DEFAULT_GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
_DEFAULT_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_ENV_REF_RE = re.compile(r"^provider:google-mail:env:([A-Za-z_][A-Za-z0-9_]{0,127})$")


class GoogleMailProviderError(RuntimeError):
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
    raw = str(os.environ.get("CHENGZHU_GOOGLE_MAIL_TIMEOUT_SECONDS") or "15").strip()
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
        message = f"Gmail HTTP {exc.code}"
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            if isinstance(parsed, dict):
                error = parsed.get("error") or {}
                if isinstance(error, dict) and error.get("message"):
                    message = f"{message}: {str(error['message'])[:1000]}"
        except Exception:
            pass
        raise GoogleMailProviderError(int(exc.code), message) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Gmail transport error: {type(exc).__name__}") from None


def _bare_email(value: str, *, label: str) -> str:
    raw = str(value or "").strip()
    if not raw or len(raw) > 320 or any(ch in raw for ch in "\r\n\x00,;"):
        raise ValueError(f"{label} 必须是一个明确的单一邮箱地址")
    try:
        address = Address(addr_spec=raw)
    except Exception:
        raise ValueError(f"{label} 邮箱地址非法") from None
    normalized = address.addr_spec
    if not normalized or "@" not in normalized or normalized != raw:
        raise ValueError(f"{label} 必须使用裸邮箱地址，例如 name@example.com")
    return normalized


class GoogleMailSendAdapter:
    provider_id = "GOOGLE_MAIL"
    capabilities = {"email.send"}

    def __init__(
        self,
        *,
        api_base: str = "",
        userinfo_url: str = "",
        transport: Optional[Transport] = None,
    ):
        self.api_base = str(
            api_base or os.environ.get("CHENGZHU_GOOGLE_MAIL_API_BASE") or _DEFAULT_GMAIL_API_BASE
        ).strip().rstrip("/")
        self.userinfo_url = str(
            userinfo_url or os.environ.get("CHENGZHU_GOOGLE_USERINFO_URL") or _DEFAULT_USERINFO_URL
        ).strip()
        if not self.api_base.startswith("https://") or not self.userinfo_url.startswith("https://"):
            raise ValueError("Gmail/UserInfo endpoint 必须使用 HTTPS；Bearer token 不允许明文 HTTP 出站")
        self._transport = transport or _urllib_transport

    @staticmethod
    def _resolve_token(connection: dict[str, Any]) -> str:
        credential_ref = str(connection.get("credential_ref") or "").strip()
        match = _ENV_REF_RE.fullmatch(credential_ref)
        if not match:
            raise ValueError(
                "Gmail credential_ref 当前只支持 provider:google-mail:env:<ENV_VAR>；access token 本身不能写入 product.db"
            )
        env_name = match.group(1)
        token = str(os.environ.get(env_name) or "").strip()
        if not token:
            raise ValueError(f"Gmail credential environment variable 未设置：{env_name}")
        return token

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Chengzhu/2.0",
        }

    def health(self, connection: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if connection is None:
            return {
                "ok": True,
                "label": "Gmail send-only adapter",
                "runtime": "OPT_IN_REAL_PROVIDER",
            }
        token = self._resolve_token(connection)
        status, _headers, payload = self._transport(
            "GET",
            self.userinfo_url,
            self._headers(token),
            None,
            _timeout_seconds(),
        )
        if status != 200 or not isinstance(payload, dict):
            return {"ok": False, "error": f"Google UserInfo verify returned HTTP {status}"}
        email = str(payload.get("email") or "").strip()
        if not email or payload.get("email_verified") is not True:
            return {
                "ok": False,
                "error": "Google UserInfo 未返回 verified email；需要 openid + email identity scopes",
            }
        try:
            email = _bare_email(email, label="Google account")
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "label": "Gmail",
            "account_hint": email,
            "provider_user_id": str(payload.get("sub") or "")[:255],
            "verify": "OIDC_USERINFO_IDENTITY_ONLY",
            "send_capability_proof": "PENDING_FIRST_EXPLICIT_EXECUTION",
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
        raise ValueError("Gmail v1 provider 是 send-only；不实现 mail.read / inbox sync")

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
        if capability != "email.send" or operation != "SEND_EMAIL":
            return {
                "ok": False,
                "error": "Gmail adapter 只支持 reviewed SEND_EMAIL / email.send",
                "retry_safe": False,
            }
        if bool(payload.get("outbound_redaction_applied")):
            return {
                "ok": False,
                "error": "发送前安全层检测到并替换了疑似 secret；请回到 Draft 重新审核后再创建新的 Execution Request",
                "retry_safe": False,
            }

        try:
            recipient = _bare_email(target, label="收件人")
            sender = _bare_email(str(connection.get("account_hint") or ""), label="已验证 Gmail 账号")
        except ValueError as exc:
            return {"ok": False, "error": str(exc), "retry_safe": False}

        subject = str(payload.get("title") or "").strip()
        if not subject or any(ch in subject for ch in "\r\n\x00"):
            return {"ok": False, "error": "邮件主题不能为空或包含换行", "retry_safe": False}
        if len(subject) > 998:
            return {
                "ok": False,
                "error": "邮件主题过长；不会静默截断已审核 Subject，请修改 Draft 后重新审核",
                "retry_safe": False,
            }
        content = str(payload.get("content") or "")
        if not content.strip():
            return {"ok": False, "error": "邮件正文不能为空", "retry_safe": False}
        if len(content) > 20_000:
            return {
                "ok": False,
                "error": "邮件正文超过 20000 字符；不会静默截断已审核内容，请缩短 Draft 后重新审核",
                "retry_safe": False,
            }

        message = EmailMessage(policy=SMTP)
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = subject
        # Audit marker is intentionally not an idempotency claim. Gmail's
        # messages.send endpoint does not expose a provider-side idempotency
        # key, so ambiguous outcomes remain UNKNOWN_OUTCOME in the shared layer.
        message["X-Chengzhu-Execution-ID"] = str(idempotency_key or "")[:128]
        message.set_content(content, subtype="plain", charset="utf-8")
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        body = json.dumps({"raw": raw}, separators=(",", ":")).encode("utf-8")
        headers = self._headers(self._resolve_token(connection))
        headers["Content-Type"] = "application/json"

        try:
            status, _response_headers, result = self._transport(
                "POST",
                f"{self.api_base}/users/me/messages/send",
                headers,
                body,
                _timeout_seconds(),
            )
        except GoogleMailProviderError as exc:
            # Definitive 4xx rejections mean Gmail did not accept this request.
            # 408/425/429 and server/transport failures stay ambiguous so the
            # shared integration boundary records UNKNOWN_OUTCOME.
            if 400 <= exc.status < 500 and exc.status not in {408, 425, 429}:
                return {
                    "ok": False,
                    "error": str(exc),
                    "retry_safe": False,
                    "http_status": exc.status,
                }
            raise

        if status != 200 or not isinstance(result, dict) or not result.get("id"):
            raise RuntimeError(f"Gmail messages.send returned ambiguous HTTP {status}")
        return {
            "ok": True,
            "provider_id": "GOOGLE_MAIL",
            "external_id": str(result.get("id") or "")[:500],
            "message_id": str(result.get("id") or "")[:500],
            "thread_id": str(result.get("threadId") or "")[:500],
            "recipient": recipient,
            "sender": sender,
            "idempotency_header": "X-Chengzhu-Execution-ID",
            "provider_idempotency": "NONE",
        }


def register_google_mail_adapter_from_env() -> dict[str, Any]:
    enabled = str(os.environ.get("CHENGZHU_GOOGLE_MAIL_CONNECTOR_ENABLE") or "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return {"registered": False, "provider_id": "GOOGLE_MAIL", "reason": "NOT_ENABLED"}

    from services.product import conversation_integrations

    adapter = GoogleMailSendAdapter()
    conversation_integrations.register_adapter(adapter)
    return {
        "registered": True,
        "provider_id": "GOOGLE_MAIL",
        "capabilities": sorted(adapter.capabilities),
        "credential_ref_format": "provider:google-mail:env:<ENV_VAR>",
        "oauth_required_scopes": [
            "openid",
            "email",
            "https://www.googleapis.com/auth/gmail.send",
        ],
        "read_capabilities": [],
        "write_capabilities": ["email.send"],
    }
