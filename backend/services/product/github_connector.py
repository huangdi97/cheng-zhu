"""Real GitHub provider adapter for Conversation external integrations.

The adapter is intentionally opt-in.  It is registered only when
CHENGZHU_GITHUB_CONNECTOR_ENABLE=1.  product.db stores an opaque credential
reference such as:

    provider:github:env:CHENGZHU_GITHUB_TOKEN

The token itself remains outside product.db and is resolved from the process
environment only when GitHub is actually called.

Supported canonical capabilities:
- project.read  -> GitHub repository issues (read)
- issue.create  -> reviewed CREATE_ISSUE external execution

GitHub pull requests are not imported as issues even though the REST issues
endpoint returns both resources.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


GITHUB_API_VERSION = "2026-03-10"
_DEFAULT_API_BASE = "https://api.github.com"
_ENV_REF_RE = re.compile(r"^provider:github:env:([A-Za-z_][A-Za-z0-9_]{0,127})$")
_REPO_RE = re.compile(r"^([A-Za-z0-9_.-]{1,100})/([A-Za-z0-9_.-]{1,100})$")


class GitHubProviderError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = int(status)


Transport = Callable[
    [str, str, dict[str, str], Optional[bytes], float],
    tuple[int, dict[str, str], Any],
]


def _timeout_seconds() -> float:
    raw = str(os.environ.get("CHENGZHU_GITHUB_TIMEOUT_SECONDS") or "15").strip()
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
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            payload: Any = None
            if raw:
                payload = json.loads(raw.decode("utf-8"))
            return int(response.status), dict(response.headers.items()), payload
    except HTTPError as exc:
        raw = exc.read(16_384)
        message = f"GitHub HTTP {exc.code}"
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            if isinstance(parsed, dict) and parsed.get("message"):
                message = f"{message}: {str(parsed['message'])[:1000]}"
        except Exception:
            pass
        raise GitHubProviderError(int(exc.code), message) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"GitHub transport error: {type(exc).__name__}") from None


def _iso_to_timestamp(value: str) -> Optional[float]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _overlap_cursor(value: str) -> str:
    """Return a slightly overlapping cursor so equal-second updates are re-read.

    Snapshot identity in Chengzhu is content-addressed, so a one-second overlap
    is safer than risking a missed issue when GitHub updates multiple objects
    at the same timestamp.
    """
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return raw[:100]
    return (dt - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")


class GitHubRestAdapter:
    provider_id = "GITHUB"
    capabilities = {"project.read", "issue.create"}

    def __init__(
        self,
        *,
        api_base: str = "",
        transport: Optional[Transport] = None,
    ):
        configured = str(api_base or os.environ.get("CHENGZHU_GITHUB_API_BASE") or _DEFAULT_API_BASE).strip()
        self.api_base = configured.rstrip("/")
        if not self.api_base.startswith(("https://", "http://")):
            raise ValueError("GitHub API base 必须是 http/https URL")
        self._transport = transport or _urllib_transport

    @staticmethod
    def _resolve_token(connection: dict[str, Any]) -> str:
        credential_ref = str(connection.get("credential_ref") or "").strip()
        match = _ENV_REF_RE.fullmatch(credential_ref)
        if not match:
            raise ValueError(
                "GitHub credential_ref 当前只支持 provider:github:env:<ENV_VAR>；token 本身不能写入 product.db"
            )
        env_name = match.group(1)
        token = str(os.environ.get(env_name) or "").strip()
        if not token:
            raise ValueError(f"GitHub credential environment variable 未设置：{env_name}")
        return token

    @staticmethod
    def _repository(value: str) -> tuple[str, str, str]:
        raw = str(value or "").strip()
        match = _REPO_RE.fullmatch(raw)
        if not match:
            raise ValueError("GitHub repository 必须使用 owner/repo")
        owner, repo = match.groups()
        return owner, repo, f"{owner}/{repo}"

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Chengzhu/2.0",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
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
        body = None
        headers = self._headers(token)
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        return self._transport(method, url, headers, body, _timeout_seconds())

    def health(self, connection: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if connection is None:
            return {
                "ok": True,
                "label": "GitHub REST adapter",
                "runtime": "OPT_IN_REAL_PROVIDER",
            }
        token = self._resolve_token(connection)
        status, _headers, payload = self._request("GET", "/user", token=token)
        if status != 200 or not isinstance(payload, dict) or not payload.get("login"):
            return {"ok": False, "error": f"GitHub health check returned HTTP {status}"}
        return {
            "ok": True,
            "label": "GitHub",
            "account_hint": str(payload.get("login") or "")[:200],
            "provider_user_id": str(payload.get("id") or "")[:100],
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
            raise ValueError("GitHub read adapter 只支持 project.read")
        owner, repo, repository = self._repository(
            str(query.get("repository") or query.get("repo") or "")
        )
        token = self._resolve_token(connection)
        requested_limit = max(1, min(int(limit), 500))
        state = str(query.get("state") or "open").lower()
        if state not in {"open", "closed", "all"}:
            raise ValueError("GitHub issue state 只支持 open / closed / all")

        labels = query.get("labels") or []
        if isinstance(labels, str):
            labels = [part.strip() for part in labels.split(",") if part.strip()]
        labels_value = ",".join(str(label)[:100] for label in list(labels)[:20])

        items: list[dict[str, Any]] = []
        page = 1
        latest_updated = ""
        while len(items) < requested_limit and page <= 20:
            per_page = min(100, max(1, requested_limit - len(items)))
            params: dict[str, Any] = {
                "state": state,
                "sort": "updated",
                "direction": "asc",
                "per_page": per_page,
                "page": page,
            }
            if cursor:
                params["since"] = cursor
            if labels_value:
                params["labels"] = labels_value
            status, _headers, payload = self._request(
                "GET",
                f"/repos/{owner}/{repo}/issues",
                token=token,
                params=params,
            )
            if status != 200 or not isinstance(payload, list):
                raise RuntimeError(f"GitHub issue sync returned HTTP {status}")
            if not payload:
                break

            for raw in payload:
                if not isinstance(raw, dict):
                    continue
                updated_at = str(raw.get("updated_at") or "")
                if updated_at and updated_at > latest_updated:
                    latest_updated = updated_at
                # GitHub's issues endpoint also returns pull requests.
                if raw.get("pull_request"):
                    continue
                number = raw.get("number")
                if number is None:
                    continue
                issue_labels = []
                for label in raw.get("labels") or []:
                    if isinstance(label, dict):
                        issue_labels.append(str(label.get("name") or "")[:100])
                    elif label:
                        issue_labels.append(str(label)[:100])
                assignees = [
                    str(user.get("login") or "")[:100]
                    for user in raw.get("assignees") or []
                    if isinstance(user, dict) and user.get("login")
                ]
                items.append({
                    "external_kind": "ISSUE",
                    "external_id": f"{repository}#{number}",
                    "title": str(raw.get("title") or "")[:500],
                    "excerpt": str(raw.get("body") or "")[:20_000],
                    "source_url": str(raw.get("html_url") or ""),
                    "occurred_at": _iso_to_timestamp(updated_at or str(raw.get("created_at") or "")),
                    "visibility": "PRIVATE",
                    "metadata": {
                        "repository": repository,
                        "number": int(number),
                        "state": str(raw.get("state") or ""),
                        "labels": issue_labels,
                        "assignees": assignees,
                        "created_at": str(raw.get("created_at") or ""),
                        "updated_at": updated_at,
                        "provider_node_id": str(raw.get("node_id") or "")[:300],
                    },
                })
                if len(items) >= requested_limit:
                    break

            if len(payload) < per_page:
                break
            page += 1

        return {
            "items": items,
            "next_cursor": _overlap_cursor(latest_updated) if latest_updated else str(cursor or ""),
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
        if capability != "issue.create" or operation != "CREATE_ISSUE":
            return {
                "ok": False,
                "error": "GitHub adapter 只支持 reviewed CREATE_ISSUE / issue.create",
                "retry_safe": False,
            }
        owner, repo, repository = self._repository(target)
        token = self._resolve_token(connection)
        title = str(payload.get("title") or "").strip()
        if not title:
            return {"ok": False, "error": "GitHub issue title 不能为空", "retry_safe": False}
        content = str(payload.get("content") or "").rstrip()
        marker = f"<!-- chengzhu-execution:{idempotency_key} -->"
        body = f"{content}\n\n{marker}".strip()

        try:
            status, _headers, result = self._request(
                "POST",
                f"/repos/{owner}/{repo}/issues",
                token=token,
                payload={"title": title[:256], "body": body[:65_000]},
            )
        except GitHubProviderError as exc:
            # A definitive client rejection means GitHub did not accept the
            # create request.  Server/transport errors remain ambiguous and are
            # re-raised so the integration boundary records UNKNOWN_OUTCOME.
            if 400 <= exc.status < 500 and exc.status not in {408, 425, 429}:
                return {
                    "ok": False,
                    "error": str(exc),
                    "retry_safe": False,
                    "http_status": exc.status,
                }
            raise

        if status != 201 or not isinstance(result, dict) or result.get("number") is None:
            raise RuntimeError(f"GitHub create issue returned ambiguous HTTP {status}")
        number = int(result["number"])
        return {
            "ok": True,
            "provider_id": "GITHUB",
            "repository": repository,
            "external_id": f"{repository}#{number}",
            "issue_number": number,
            "html_url": str(result.get("html_url") or ""),
            "provider_node_id": str(result.get("node_id") or "")[:300],
            "idempotency_marker": marker,
        }


def register_github_adapter_from_env() -> dict[str, Any]:
    """Register the real GitHub adapter only after explicit runtime opt-in."""
    enabled = str(os.environ.get("CHENGZHU_GITHUB_CONNECTOR_ENABLE") or "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return {"registered": False, "provider_id": "GITHUB", "reason": "NOT_ENABLED"}

    # Delayed import avoids a circular import at module load.
    from services.product import conversation_integrations

    adapter = GitHubRestAdapter()
    conversation_integrations.register_adapter(adapter)
    return {
        "registered": True,
        "provider_id": "GITHUB",
        "capabilities": sorted(adapter.capabilities),
        "credential_ref_format": "provider:github:env:<ENV_VAR>",
    }
