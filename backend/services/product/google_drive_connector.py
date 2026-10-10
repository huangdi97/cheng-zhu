"""Opt-in Google Drive / Docs read-only provider for Conversation context.

The provider deliberately implements only `docs.read`.

Credential material is resolved from a process environment variable referenced
by an opaque product.db handle:

    provider:google-drive:env:GOOGLE_DRIVE_ACCESS_TOKEN

The token itself never enters product.db, frontend state, snapshots or exports.

Product semantics are intentionally target-scoped and user-triggered:
- every Sync names one explicit folder id (default: root);
- every Sync performs a complete refresh of that folder's direct children;
- only after complete pagination and content reads succeed does the generic
  integration boundary persist immutable snapshots;
- no background account-wide mirror or Drive write is implemented.

Google Workspace files are exported to a truthful text representation:
- Docs   -> text/plain
- Slides -> text/plain
- Sheets -> text/csv (first sheet only; marked partial)
Common small text blobs use files.get?alt=media.
Unsupported/binary files are stored as metadata-only DOCUMENT snapshots and are
never presented as if their content had been read.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


_DEFAULT_API_BASE = "https://www.googleapis.com/drive/v3"
_ENV_REF_RE = re.compile(r"^provider:google-drive:env:([A-Za-z_][A-Za-z0-9_]{0,127})$")
_FOLDER_RE = re.compile(r"^(?:root|[A-Za-z0-9_-]{1,256})$")
_MAX_FILES_PER_SYNC = 500
_PAGE_SIZE = 100
_MAX_TEXT_BYTES = 2_000_000

_GOOGLE_EXPORTS: dict[str, tuple[str, bool, str]] = {
    "application/vnd.google-apps.document": ("text/plain", False, "FULL_TEXT_EXPORT"),
    "application/vnd.google-apps.presentation": ("text/plain", False, "FULL_TEXT_EXPORT"),
    "application/vnd.google-apps.spreadsheet": ("text/csv", True, "FIRST_SHEET_CSV"),
}
_TEXT_BLOB_MIMES = {
    "application/json",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
    "application/javascript",
    "application/sql",
}


class GoogleDriveProviderError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = int(status)


class GoogleDriveTargetError(GoogleDriveProviderError):
    """A folder/file target rejection; account auth may still be healthy."""

    connection_fatal = False


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


Transport = Callable[
    [str, str, dict[str, str], Optional[bytes], float],
    tuple[int, dict[str, str], Any],
]


def _timeout_seconds() -> float:
    raw = str(os.environ.get("CHENGZHU_GOOGLE_DRIVE_TIMEOUT_SECONDS") or "20").strip()
    try:
        return max(2.0, min(float(raw), 60.0))
    except ValueError:
        return 20.0


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
            return int(response.status), dict(response.headers.items()), raw
    except HTTPError as exc:
        raw = exc.read(16_384)
        message = f"Google Drive HTTP {exc.code}"
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            if isinstance(parsed, dict):
                error = parsed.get("error") or {}
                if isinstance(error, dict) and error.get("message"):
                    message = f"{message}: {str(error['message'])[:1000]}"
        except Exception:
            pass
        raise GoogleDriveProviderError(int(exc.code), message) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Google Drive transport error: {type(exc).__name__}") from None


def _timestamp(value: str) -> Optional[float]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.timestamp()
    except ValueError:
        return None


def _decode_text(raw: bytes) -> str:
    if len(raw) > _MAX_TEXT_BYTES:
        raise ValueError(
            f"Google Drive 文本内容超过 {_MAX_TEXT_BYTES} bytes 安全上限；"
            "拒绝部分截断后冒充完整文档"
        )
    return raw.decode("utf-8", errors="replace")


class GoogleDriveRestAdapter:
    provider_id = "GOOGLE_DRIVE"
    capabilities = {"docs.read"}

    def __init__(self, *, api_base: str = "", transport: Optional[Transport] = None):
        configured = str(
            api_base or os.environ.get("CHENGZHU_GOOGLE_DRIVE_API_BASE") or _DEFAULT_API_BASE
        ).strip()
        self.api_base = configured.rstrip("/")
        if not self.api_base.startswith("https://"):
            raise ValueError("Google Drive API base 必须使用 HTTPS；Bearer token 不允许明文 HTTP 出站")
        self._transport = transport or _urllib_transport

    @staticmethod
    def _resolve_token(connection: dict[str, Any]) -> str:
        credential_ref = str(connection.get("credential_ref") or "").strip()
        match = _ENV_REF_RE.fullmatch(credential_ref)
        if not match:
            raise ValueError(
                "Google Drive credential_ref 当前只支持 "
                "provider:google-drive:env:<ENV_VAR>；access token 本身不能写入 product.db"
            )
        env_name = match.group(1)
        token = str(os.environ.get(env_name) or "").strip()
        if not token:
            raise ValueError(f"Google Drive credential environment variable 未设置：{env_name}")
        return token

    @staticmethod
    def _folder_id(query: dict[str, Any], connection: dict[str, Any]) -> str:
        value = str(
            query.get("folder_id")
            or query.get("folder")
            or connection.get("account_hint")
            or "root"
        ).strip() or "root"
        if not _FOLDER_RE.fullmatch(value):
            raise ValueError("Google Drive folder id 非法；请使用 root 或明确的 Drive folder id")
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
        try:
            return self._transport("GET", url, self._headers(token), None, _timeout_seconds())
        except GoogleDriveProviderError as exc:
            if exc.status != 401 and 400 <= exc.status < 500:
                raise GoogleDriveTargetError(exc.status, str(exc)) from None
            raise

    @staticmethod
    def _json_payload(payload: Any, label: str) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, (bytes, bytearray)):
            try:
                decoded = json.loads(bytes(payload).decode("utf-8"))
            except Exception as exc:
                raise RuntimeError(f"Google Drive {label} returned malformed JSON") from exc
            if isinstance(decoded, dict):
                return decoded
        raise RuntimeError(f"Google Drive {label} returned malformed payload")

    def _validate_folder(self, *, connection: dict[str, Any], folder_id: str) -> dict[str, Any]:
        token = self._resolve_token(connection)
        status, _headers, raw = self._request(
            f"/files/{quote(folder_id, safe='')}",
            token=token,
            params={"fields": "id,name,mimeType,trashed"},
        )
        if status != 200:
            raise RuntimeError(f"Google Drive folder probe returned ambiguous HTTP {status}")
        payload = self._json_payload(raw, "files.get folder")
        if str(payload.get("mimeType") or "") != "application/vnd.google-apps.folder":
            raise ValueError("Google Drive Sync target 不是 folder")
        if bool(payload.get("trashed")):
            raise ValueError("Google Drive Sync target 已在回收站")
        return payload

    def _list_folder(self, *, connection: dict[str, Any], folder_id: str) -> list[dict[str, Any]]:
        token = self._resolve_token(connection)
        page_token = ""
        items: list[dict[str, Any]] = []
        while True:
            params: dict[str, Any] = {
                "q": f"'{folder_id}' in parents and trashed = false",
                "spaces": "drive",
                "pageSize": _PAGE_SIZE,
                "orderBy": "modifiedTime desc",
                "fields": (
                    "nextPageToken,files("
                    "id,name,mimeType,modifiedTime,webViewLink,parents,trashed,"
                    "size,md5Checksum,capabilities(canDownload))"
                ),
            }
            if page_token:
                params["pageToken"] = page_token
            status, _headers, raw = self._request("/files", token=token, params=params)
            if status != 200:
                raise RuntimeError(f"Google Drive files.list returned ambiguous HTTP {status}")
            payload = self._json_payload(raw, "files.list")
            rows = payload.get("files") or []
            if not isinstance(rows, list):
                raise RuntimeError("Google Drive files.list returned malformed files")
            items.extend(row for row in rows if isinstance(row, dict))
            if len(items) > _MAX_FILES_PER_SYNC:
                raise ValueError(
                    f"Google Drive 目标文件夹超过安全上限 {_MAX_FILES_PER_SYNC}；"
                    "请缩小到更具体的 folder，避免把整个 Drive 静默镜像进一个 Space"
                )
            page_token = str(payload.get("nextPageToken") or "")
            if not page_token:
                break
        return items

    def _read_file_content(
        self,
        *,
        connection: dict[str, Any],
        file: dict[str, Any],
    ) -> dict[str, Any]:
        token = self._resolve_token(connection)
        file_id = str(file.get("id") or "").strip()
        mime = str(file.get("mimeType") or "").strip()
        can_download = bool((file.get("capabilities") or {}).get("canDownload", True))

        if mime == "application/vnd.google-apps.folder":
            return {
                "content_available": False,
                "text": "",
                "export_mime": "",
                "content_scope": "FOLDER_METADATA_ONLY",
                "partial_content": False,
                "reason": "FOLDER",
            }

        if mime in _GOOGLE_EXPORTS:
            export_mime, partial, scope = _GOOGLE_EXPORTS[mime]
            status, _headers, raw = self._request(
                f"/files/{quote(file_id, safe='')}/export",
                token=token,
                params={"mimeType": export_mime},
            )
            if status != 200 or not isinstance(raw, (bytes, bytearray)):
                raise RuntimeError(f"Google Drive files.export returned ambiguous HTTP {status}")
            return {
                "content_available": True,
                "text": _decode_text(bytes(raw)),
                "export_mime": export_mime,
                "content_scope": scope,
                "partial_content": partial,
                "reason": "",
            }

        is_text_blob = mime.startswith("text/") or mime in _TEXT_BLOB_MIMES
        if is_text_blob and can_download:
            size_raw = str(file.get("size") or "").strip()
            if size_raw.isdigit() and int(size_raw) > _MAX_TEXT_BYTES:
                return {
                    "content_available": False,
                    "text": "",
                    "export_mime": mime,
                    "content_scope": "METADATA_ONLY",
                    "partial_content": False,
                    "reason": "TEXT_TOO_LARGE",
                }
            status, _headers, raw = self._request(
                f"/files/{quote(file_id, safe='')}",
                token=token,
                params={"alt": "media"},
            )
            if status != 200 or not isinstance(raw, (bytes, bytearray)):
                raise RuntimeError(f"Google Drive files.get media returned ambiguous HTTP {status}")
            return {
                "content_available": True,
                "text": _decode_text(bytes(raw)),
                "export_mime": mime,
                "content_scope": "FULL_TEXT_BLOB",
                "partial_content": False,
                "reason": "",
            }

        return {
            "content_available": False,
            "text": "",
            "export_mime": "",
            "content_scope": "METADATA_ONLY",
            "partial_content": False,
            "reason": "UNSUPPORTED_OR_BINARY",
        }

    def health(self, connection: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if connection is None:
            return {
                "ok": True,
                "label": "Google Drive REST adapter",
                "runtime": "OPT_IN_REAL_PROVIDER",
            }
        token = self._resolve_token(connection)
        status, _headers, raw = self._request(
            "/about",
            token=token,
            params={"fields": "user(displayName,emailAddress)"},
        )
        if status != 200:
            return {"ok": False, "error": f"Google Drive verify returned HTTP {status}"}
        payload = self._json_payload(raw, "about.get")
        user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
        return {
            "ok": True,
            "label": "Google Drive",
            # Preserve the configured folder target in account_hint so a
            # backend restart does not silently lose the user's explicit scope.
            "account_hint": str(connection.get("account_hint") or "root")[:300],
            "account_identity": str(user.get("emailAddress") or user.get("displayName") or "")[:300],
            "verify": "ACCOUNT_READ_PROBE_ONLY",
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
        if capability != "docs.read":
            raise ValueError("Google Drive adapter 只支持 docs.read")
        folder_id = self._folder_id(query, connection)
        self._validate_folder(connection=connection, folder_id=folder_id)
        files = self._list_folder(connection=connection, folder_id=folder_id)
        if len(files) > max(1, min(int(limit), _MAX_FILES_PER_SYNC)):
            raise ValueError(
                f"Google Drive 目标文件夹包含 {len(files)} 个文件，超过 Chengzhu 当前安全写入上限 {limit}；"
                "拒绝部分同步，避免让 snapshot 集合假装完整"
            )

        snapshots: list[dict[str, Any]] = []
        for file in files:
            file_id = str(file.get("id") or "").strip()
            if not file_id:
                continue
            content = self._read_file_content(connection=connection, file=file)
            modified = str(file.get("modifiedTime") or "")
            snapshots.append({
                "external_kind": "DOCUMENT",
                "external_id": file_id,
                "title": str(file.get("name") or "Untitled Drive file")[:500],
                "excerpt": str(content["text"] or "")[:20_000],
                "source_url": str(file.get("webViewLink") or ""),
                "occurred_at": _timestamp(modified),
                "visibility": "PRIVATE",
                "metadata": {
                    "folder_id": folder_id,
                    "file_id": file_id,
                    "mime_type": str(file.get("mimeType") or "")[:300],
                    "modified_time": modified[:100],
                    "parents": [str(x)[:300] for x in (file.get("parents") or [])[:20]],
                    "size": str(file.get("size") or "")[:100],
                    "md5_checksum": str(file.get("md5Checksum") or "")[:200],
                    "content_available": bool(content["content_available"]),
                    "export_mime": str(content["export_mime"] or "")[:200],
                    "content_scope": str(content["content_scope"] or "")[:120],
                    "partial_content": bool(content["partial_content"]),
                    "content_unavailable_reason": str(content["reason"] or "")[:200],
                },
            })

        # This cursor is only an auditable target binding. Sync deliberately
        # remains a user-triggered full folder refresh rather than an
        # account-wide change feed.
        return {
            "items": snapshots,
            "next_cursor": f"gdrive-folder:{folder_id}",
            "folder_id": folder_id,
            "refresh": "FULL_TARGET_REFRESH",
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
            "error": "Google Drive provider 当前只实现 docs.read；不支持外部写入",
            "retry_safe": False,
        }


def register_google_drive_adapter_from_env() -> dict[str, Any]:
    enabled = str(os.environ.get("CHENGZHU_GOOGLE_DRIVE_CONNECTOR_ENABLE") or "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return {"registered": False, "provider_id": "GOOGLE_DRIVE", "reason": "NOT_ENABLED"}

    from services.product import conversation_integrations

    adapter = GoogleDriveRestAdapter()
    conversation_integrations.register_adapter(adapter)
    return {
        "registered": True,
        "provider_id": "GOOGLE_DRIVE",
        "capabilities": sorted(adapter.capabilities),
        "credential_ref_format": "provider:google-drive:env:<ENV_VAR>",
        "write_capabilities": [],
    }
