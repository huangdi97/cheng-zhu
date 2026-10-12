#!/usr/bin/env python3
"""Real-account replay harness for Chengzhu v2 external Conversation providers.

This is source-side operator tooling. It launches Chengzhu against an isolated
temporary CHENGZHU_HOME and a local fake model provider, so the only intended
external traffic is the selected connector provider.

Supported providers:
- google-calendar: read-only Calendar sync + frozen Session Pack replay
- google-drive: read-only Drive folder sync + frozen Session Pack replay
- google-mail: real account verify; optional explicit Gmail send replay
- microsoft-todo: real account verify; optional explicit To Do create replay

Write providers are SAFE BY DEFAULT: without --execute-write they stop after
connection verification and local Draft approval. A real side effect requires
both --execute-write and the exact --confirm-write marker.

The report deliberately omits raw tokens, account identities, recipients,
provider object ids, titles/excerpts and backend logs. It is provider-account
engineering evidence only; it does not prove real-user value, PMF, Google OAuth
publication approval or Stable release readiness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
API = "/api/product/conversation"
REPORT_CONTRACT = "v2.0-R1-real-provider-account-replay-1"


@dataclass(frozen=True)
class ProviderSpec:
    key: str
    provider_id: str
    enable_env: str
    credential_prefix: str
    capability: str
    mode: str
    default_target: str
    query_key: str = ""
    draft_kind: str = ""
    confirm_marker: str = ""


PROVIDERS: dict[str, ProviderSpec] = {
    "google-calendar": ProviderSpec(
        key="google-calendar",
        provider_id="GOOGLE_CALENDAR",
        enable_env="CHENGZHU_GOOGLE_CALENDAR_CONNECTOR_ENABLE",
        credential_prefix="provider:google-calendar:env:",
        capability="calendar.read",
        mode="READ",
        default_target="primary",
        query_key="calendar_id",
    ),
    "google-drive": ProviderSpec(
        key="google-drive",
        provider_id="GOOGLE_DRIVE",
        enable_env="CHENGZHU_GOOGLE_DRIVE_CONNECTOR_ENABLE",
        credential_prefix="provider:google-drive:env:",
        capability="docs.read",
        mode="READ",
        default_target="root",
        query_key="folder_id",
    ),
    "google-mail": ProviderSpec(
        key="google-mail",
        provider_id="GOOGLE_MAIL",
        enable_env="CHENGZHU_GOOGLE_MAIL_CONNECTOR_ENABLE",
        credential_prefix="provider:google-mail:env:",
        capability="email.send",
        mode="WRITE",
        default_target="",
        draft_kind="FOLLOWUP_EMAIL_DRAFT",
        confirm_marker="SEND_EMAIL",
    ),
    "microsoft-todo": ProviderSpec(
        key="microsoft-todo",
        provider_id="MICROSOFT_GRAPH",
        enable_env="CHENGZHU_MICROSOFT_TODO_CONNECTOR_ENABLE",
        credential_prefix="provider:microsoft-graph:env:",
        capability="task.create",
        mode="WRITE",
        default_target="default",
        draft_kind="CREATE_TASK_DRAFT",
        confirm_marker="CREATE_TASK",
    ),
}


class ReplayFailure(RuntimeError):
    pass


class _FakeProvider(BaseHTTPRequestHandler):
    """Local OpenAI-compatible stub: connector replay never needs a remote model."""

    answer = "Chengzhu connector replay local model stub."

    def log_message(self, *_args):
        return

    def _json(self, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):  # noqa: N802
        self._json({"object": "list", "data": [{"id": "fake-model", "object": "model"}]})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            request = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            request = {}
        if not request.get("stream"):
            self._json({
                "id": "stub",
                "object": "chat.completion",
                "model": "fake-model",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": self.answer},
                    "finish_reason": "stop",
                }],
            })
            return
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        chunk = {
            "id": "stub",
            "object": "chat.completion.chunk",
            "model": "fake-model",
            "choices": [{"index": 0, "delta": {"content": self.answer}, "finish_reason": None}],
        }
        self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_text(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest() if value else ""


def _source_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).strip()
    except Exception as exc:
        raise ReplayFailure(f"cannot resolve exact source SHA: {type(exc).__name__}") from None


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_fake_provider() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeProvider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/v1"


def _http(base: str, method: str, path: str, body: Any = None, timeout: float = 90.0) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(base + path, data=data, method=method)
    if data is not None:
        request.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        raise ReplayFailure(f"{method} {path} -> HTTP {exc.code}: {detail[:600]}") from None
    return json.loads(payload) if payload.strip() else {}


def _stop_backend(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()


def _start_backend(
    *,
    port: int,
    home: Path,
    fake_base: str,
    spec: ProviderSpec,
    enable_connector: bool,
    token_env: str,
    token: str,
) -> subprocess.Popen[str]:
    config_dir = home / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(
        json.dumps({
            "models": [{
                "name": "Connector replay local stub",
                "api_base_url": fake_base,
                "api_key": "local-stub-key",
                "model": "fake-model",
                "enabled": True,
                "supports_think": False,
                "supports_vision": False,
            }],
            "active_model": 0,
            "stt_provider": "whisper",
            "ai_policy_mode": "AI_ALLOWED",
            "onboarding_completed": True,
        }),
        encoding="utf-8",
    )
    # Strip Chengzhu-specific parent settings so registration is controlled
    # solely by this replay. Other provider flags/tokens cannot accidentally
    # become active in the isolated backend.
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("CHENGZHU_", "IA_"))
    }
    env["CHENGZHU_HOME"] = str(home)
    env["PYTHONIOENCODING"] = "utf-8"
    if enable_connector:
        env[spec.enable_env] = "1"
        env[token_env] = token
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(BACKEND),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    deadline = time.time() + 90
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise ReplayFailure(
                f"backend exited early ({process.returncode}); log tail omitted from evidence; "
                f"last line={output.splitlines()[-1][:240] if output.splitlines() else ''}"
            )
        try:
            _http(f"http://127.0.0.1:{port}", "GET", "/api/options", timeout=5)
            return process
        except Exception:
            time.sleep(0.5)
    raise ReplayFailure("backend did not become ready in 90s")


def _catalog_item(base: str, provider_id: str) -> dict[str, Any]:
    rows = (_http(base, "GET", f"{API}/integrations/catalog") or {}).get("items") or []
    row = next((item for item in rows if item.get("provider_id") == provider_id), None)
    if not row:
        raise ReplayFailure(f"connector catalog missing provider {provider_id}")
    return row


def _public_connection(connection: dict[str, Any]) -> dict[str, Any]:
    identity = str(connection.get("account_hint") or "")
    return {
        "id_present": bool(connection.get("id")),
        "status": str(connection.get("status") or ""),
        "provider_id": str(connection.get("provider_id") or ""),
        "credential_ref_present": bool(connection.get("credential_ref_present")),
        "credential_ref_returned": "credential_ref" in connection,
        "account_hint_sha256": _hash_text(identity),
        "granted_capabilities": list(connection.get("granted_capabilities") or []),
        "provider_scopes": list(connection.get("provider_scopes") or []),
    }


def _validate_cli(spec: ProviderSpec, args: argparse.Namespace) -> str:
    if not args.token_env or not args.token_env.replace("_", "A").isalnum() or args.token_env[0].isdigit():
        raise ValueError("--token-env must be an environment-variable name")
    target = str(args.target or spec.default_target).strip()
    if spec.mode == "READ" and args.execute_write:
        raise ValueError(f"{spec.key} is read-only; --execute-write is invalid")
    if spec.mode == "WRITE" and args.execute_write:
        if args.confirm_write != spec.confirm_marker:
            raise ValueError(
                f"real external write requires --confirm-write {spec.confirm_marker}"
            )
        if spec.key == "google-mail" and not target:
            raise ValueError("Gmail write replay requires explicit --target recipient")
    elif args.confirm_write:
        raise ValueError("--confirm-write is only valid together with --execute-write")
    return target


def _must(report: dict[str, Any], name: str, condition: bool, detail: Any = "") -> None:
    item = {"name": name, "ok": bool(condition)}
    if detail not in ("", None):
        item["detail"] = detail
    report["assertions"].append(item)
    if not condition:
        raise ReplayFailure(f"assertion failed: {name}")


def _blocked_report(spec: ProviderSpec, source_sha: str, token_env: str) -> dict[str, Any]:
    return {
        "contract_version": REPORT_CONTRACT,
        "created_at": _now_iso(),
        "source_sha": source_sha,
        "provider": spec.key,
        "provider_id": spec.provider_id,
        "capability": spec.capability,
        "status": "BLOCKED_ACCOUNT",
        "reason": "TOKEN_ENV_NOT_SET",
        "token_env_name": token_env,
        "external_write_attempted": False,
        "claims": {
            "REAL_ACCOUNT_VALIDATED": False,
            "V2_STABLE_RELEASE": False,
            "REAL_USER_VALIDATED": False,
            "PMF_PROVEN": False,
        },
    }


def _read_replay(
    base: str,
    home: Path,
    spec: ProviderSpec,
    connection_id: str,
    target: str,
    token: str,
    report: dict[str, Any],
    limit: int,
) -> None:
    space = _http(base, "POST", f"{API}/spaces", {
        "title": f"{spec.key} real-account replay",
        "profile": "PROJECT_SYNC",
    })
    space_id = str(space.get("id") or "")
    _must(report, "space_created", bool(space_id))

    sync = _http(
        base,
        "POST",
        f"{API}/integrations/connections/{connection_id}/sync",
        {
            "space_id": space_id,
            "capabilities": [spec.capability],
            "query": {spec.query_key: target},
            "limit": limit,
        },
        timeout=180,
    )
    snapshot_rows = (_http(base, "GET", f"{API}/spaces/{space_id}/connector-snapshots") or {}).get("items") or []
    _must(report, "real_read_sync_completed", isinstance(sync, dict))
    _must(
        report,
        "real_read_target_returned_snapshot",
        len(snapshot_rows) > 0,
        {"snapshot_count": len(snapshot_rows)},
    )

    selected_ids = [str(row.get("id") or "") for row in snapshot_rows[:2] if row.get("id")]
    _http(base, "PATCH", f"{API}/spaces/{space_id}", {
        "selected_connector_snapshot_ids": selected_ids,
    })
    session = _http(base, "POST", f"{API}/spaces/{space_id}/sessions", {
        "title": "Real provider frozen-pack replay",
        "consent_ack": True,
        "capture_mode": "NOTES_ONLY",
        "processing_mode": "LOCAL",
        "policy": {
            "connector_permissions": [spec.capability],
            "external_writeback": "REVIEW_REQUIRED",
        },
    })
    session_id = str(session.get("id") or "")
    _must(report, "read_replay_session_created", bool(session_id))
    preflight = _http(base, "GET", f"{API}/sessions/{session_id}/preflight")
    _must(report, "read_replay_preflight_no_blockers", not (preflight.get("blockers") or []))
    _http(base, "POST", f"{API}/sessions/{session_id}/start")
    context = _http(base, "GET", f"{API}/sessions/{session_id}/context")
    frozen = context.get("connector_snapshots") or []
    grants = (context.get("connector_runtime") or {}).get("grants") or []
    _must(report, "frozen_pack_contains_real_snapshot", len(frozen) > 0, len(frozen))
    _must(
        report,
        "frozen_pack_contains_real_provider_grant",
        any(
            grant.get("provider_id") == spec.provider_id
            and grant.get("capability") == spec.capability
            for grant in grants
        ),
        len(grants),
    )

    export = _http(base, "GET", f"{API}/spaces/{space_id}/export")
    _must(report, "token_absent_from_space_export", token not in json.dumps(export, ensure_ascii=False))
    db_path = home / "data" / "product.db"
    _must(
        report,
        "token_absent_from_product_db",
        db_path.is_file() and token.encode() not in db_path.read_bytes(),
    )
    report["real_account_replay"] = {
        "mode": "READ",
        "target_sha256": _hash_text(target),
        "snapshot_count": len(snapshot_rows),
        "frozen_snapshot_count": len(frozen),
        "frozen_grant_count": len(grants),
        "external_write_attempted": False,
        "result": "PASS_REAL_ACCOUNT_READ_PRODUCT_REPLAY",
    }


def _write_replay(
    base: str,
    home: Path,
    spec: ProviderSpec,
    connection_id: str,
    target: str,
    token: str,
    report: dict[str, Any],
    *,
    execute_write: bool,
    title: str,
    content: str,
) -> None:
    space = _http(base, "POST", f"{API}/spaces", {
        "title": f"{spec.key} real-account replay",
        "profile": "PROJECT_SYNC",
    })
    space_id = str(space.get("id") or "")
    _must(report, "write_replay_space_created", bool(space_id))
    session = _http(base, "POST", f"{API}/spaces/{space_id}/sessions", {
        "title": "Real provider reviewed-write replay",
        "consent_ack": True,
        "capture_mode": "NOTES_ONLY",
        "processing_mode": "LOCAL",
        "policy": {
            "connector_permissions": [],
            "external_writeback": "REVIEW_REQUIRED",
        },
    })
    session_id = str(session.get("id") or "")
    _http(base, "POST", f"{API}/sessions/{session_id}/start")
    draft = _http(base, "POST", f"{API}/sessions/{session_id}/draft-actions", {
        "kind": spec.draft_kind,
        "title": title,
        "content": content,
        "target": "",
        "source_refs": [{
            "kind": "USER_NOTE",
            "excerpt": "Explicit real-provider replay operator fixture",
            "visibility": "PRIVATE",
        }],
    })
    draft_id = str(draft.get("id") or "")
    _must(report, "local_draft_created", bool(draft_id) and draft.get("status") == "DRAFT")
    approved = _http(base, "POST", f"{API}/draft-actions/{draft_id}/review", {"action": "APPROVE"})
    _must(report, "local_draft_explicitly_approved", approved.get("status") == "APPROVED")

    if not execute_write:
        db_path = home / "data" / "product.db"
        _must(
            report,
            "token_absent_from_product_db",
            db_path.is_file() and token.encode() not in db_path.read_bytes(),
        )
        report["real_account_replay"] = {
            "mode": "WRITE_PROVIDER_AUTH_ONLY",
            "target_sha256": _hash_text(target),
            "external_write_attempted": False,
            "result": "PASS_REAL_ACCOUNT_AUTH_PRODUCT_REPLAY_WRITE_NOT_EXECUTED",
        }
        return

    request_row = _http(base, "POST", f"{API}/draft-actions/{draft_id}/execution", {
        "connection_id": connection_id,
        "target": target,
    })
    execution_id = str(request_row.get("id") or "")
    _must(
        report,
        "explicit_execution_request_created",
        bool(execution_id) and request_row.get("status") == "PENDING",
    )
    executed = _http(base, "POST", f"{API}/integrations/executions/{execution_id}/execute", timeout=120)
    _must(
        report,
        "real_provider_write_succeeded",
        executed.get("status") == "SUCCEEDED",
        {"status": executed.get("status")},
    )

    audit_rows = (_http(base, "GET", f"{API}/integrations/executions") or {}).get("items") or []
    audit = next((row for row in audit_rows if row.get("id") == execution_id), {})
    _must(report, "execution_audit_row_present", bool(audit))
    _must(report, "execution_audit_target_recorded", str(audit.get("target") or "") == target)

    export = _http(base, "GET", f"{API}/spaces/{space_id}/export")
    _must(report, "token_absent_from_space_export", token not in json.dumps(export, ensure_ascii=False))
    db_path = home / "data" / "product.db"
    _must(
        report,
        "token_absent_from_product_db",
        db_path.is_file() and token.encode() not in db_path.read_bytes(),
    )

    response = executed.get("response") if isinstance(executed.get("response"), dict) else {}
    external_id = str(
        response.get("external_id")
        or response.get("message_id")
        or response.get("task_id")
        or ""
    )
    report["real_account_replay"] = {
        "mode": "WRITE",
        "target_sha256": _hash_text(target),
        "external_object_id_sha256": _hash_text(external_id),
        "external_write_attempted": True,
        "provider_idempotency": str(response.get("provider_idempotency") or "UNKNOWN"),
        "result": "PASS_REAL_ACCOUNT_WRITE_PRODUCT_REPLAY",
    }


def run_replay(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    spec = PROVIDERS[args.provider]
    target = _validate_cli(spec, args)
    source_sha = _source_sha()
    token = str(os.environ.get(args.token_env) or "").strip()
    if not token:
        return _blocked_report(spec, source_sha, args.token_env), 2

    report: dict[str, Any] = {
        "contract_version": REPORT_CONTRACT,
        "created_at": _now_iso(),
        "source_sha": source_sha,
        "provider": spec.key,
        "provider_id": spec.provider_id,
        "capability": spec.capability,
        "token_env_name": args.token_env,
        "credential_ref_format": spec.credential_prefix + "<ENV_VAR>",
        "assertions": [],
        "claims": {
            "REAL_ACCOUNT_VALIDATED": False,
            "GOOGLE_OAUTH_PUBLICATION_VERIFIED": False,
            "V2_STABLE_RELEASE": False,
            "REAL_USER_VALIDATED": False,
            "PMF_PROVEN": False,
        },
    }

    fake, fake_base = _start_fake_provider()
    try:
        with tempfile.TemporaryDirectory(prefix=f"chengzhu-{spec.key}-replay-") as temp:
            root = Path(temp)

            # Negative opt-in gate: no connector flag means no adapter wiring.
            disabled_port = _free_port()
            disabled = _start_backend(
                port=disabled_port,
                home=root / "disabled",
                fake_base=fake_base,
                spec=spec,
                enable_connector=False,
                token_env=args.token_env,
                token="",
            )
            try:
                base = f"http://127.0.0.1:{disabled_port}"
                catalog = _catalog_item(base, spec.provider_id)
                _must(
                    report,
                    "connector_not_registered_without_explicit_enable",
                    catalog.get("adapter_available") is False,
                )
            finally:
                _stop_backend(disabled)

            enabled_home = root / "enabled"
            enabled_port = _free_port()
            enabled = _start_backend(
                port=enabled_port,
                home=enabled_home,
                fake_base=fake_base,
                spec=spec,
                enable_connector=True,
                token_env=args.token_env,
                token=token,
            )
            try:
                base = f"http://127.0.0.1:{enabled_port}"
                catalog = _catalog_item(base, spec.provider_id)
                _must(
                    report,
                    "connector_registered_only_after_explicit_enable",
                    catalog.get("adapter_available") is True,
                )
                connection = _http(base, "POST", f"{API}/integrations/connections", {
                    "provider_id": spec.provider_id,
                    "display_name": f"{spec.key} real-account replay",
                    "granted_capabilities": [spec.capability],
                    "credential_ref": spec.credential_prefix + args.token_env,
                    "account_hint": target if spec.mode == "READ" else "",
                })
                public_connection = _public_connection(connection)
                _must(report, "connection_created_disconnected", public_connection["status"] == "DISCONNECTED")
                _must(report, "connection_reports_credential_ref_present", public_connection["credential_ref_present"])
                _must(report, "connection_never_returns_credential_ref", not public_connection["credential_ref_returned"])
                _must(
                    report,
                    "connection_capability_exact",
                    public_connection["granted_capabilities"] == [spec.capability],
                    public_connection["granted_capabilities"],
                )

                verified = _http(
                    base,
                    "POST",
                    f"{API}/integrations/connections/{connection.get('id')}/verify",
                    timeout=120,
                )
                _must(report, "real_account_verify_connected", verified.get("status") == "CONNECTED")
                identity = str(
                    verified.get("account_identity")
                    or verified.get("account_hint")
                    or ""
                )
                report["verified_account"] = {
                    "identity_present": bool(identity),
                    "identity_sha256": _hash_text(identity),
                    "provider_scopes": list(verified.get("provider_scopes") or []),
                    "raw_identity_exported": False,
                }

                if spec.mode == "READ":
                    _read_replay(
                        base,
                        enabled_home,
                        spec,
                        str(connection.get("id") or ""),
                        target,
                        token,
                        report,
                        args.limit,
                    )
                else:
                    _write_replay(
                        base,
                        enabled_home,
                        spec,
                        str(connection.get("id") or ""),
                        target,
                        token,
                        report,
                        execute_write=bool(args.execute_write),
                        title=args.write_title,
                        content=args.write_body,
                    )
            finally:
                _stop_backend(enabled)
    except Exception as exc:
        message = str(exc).replace(token, "[REDACTED_TOKEN]")[:1200]
        report["status"] = "FAILED"
        report["error_class"] = type(exc).__name__
        report["error"] = message
        report["claims"]["REAL_ACCOUNT_VALIDATED"] = False
        return report, 1
    finally:
        fake.shutdown()

    passed = all(item.get("ok") for item in report["assertions"])
    report["passed"] = passed
    if passed:
        report["status"] = str((report.get("real_account_replay") or {}).get("result") or "PASS")
        report["claims"]["REAL_ACCOUNT_VALIDATED"] = True
    serialized = json.dumps(report, ensure_ascii=False)
    if token and token in serialized:
        raise ReplayFailure("credential token leaked into replay report serialization")
    return report, 0 if passed else 1


def _write_report(path: str, report: dict[str, Any]) -> None:
    if not path:
        return
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    parser.add_argument("--token-env", required=True)
    parser.add_argument(
        "--target",
        default="",
        help="Calendar id / Drive folder id / Gmail recipient / To Do list id or default",
    )
    parser.add_argument("--limit", type=int, default=500, choices=range(1, 501))
    parser.add_argument("--execute-write", action="store_true")
    parser.add_argument("--confirm-write", default="")
    parser.add_argument(
        "--write-title",
        default="Chengzhu real-account replay",
        help="reviewed Gmail subject or To Do task title used only when write execution is enabled",
    )
    parser.add_argument(
        "--write-body",
        default="Explicit Chengzhu real-provider replay. This is a test artifact.",
        help="reviewed Gmail body or To Do task content used only when write execution is enabled",
    )
    parser.add_argument("--out", default="")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        spec = PROVIDERS[args.provider]
        _validate_cli(spec, args)
        report, code = run_replay(args)
        _write_report(args.out, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return code
    except (FileExistsError, ReplayFailure, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
