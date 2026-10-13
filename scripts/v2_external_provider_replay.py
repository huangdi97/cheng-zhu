#!/usr/bin/env python3
"""Privacy-minimized real-account replay for Chengzhu v2 external providers.

This harness exercises the same product API path used by the app:

    opt-in adapter registration
    -> opaque env credential reference
    -> Connection
    -> Verify
    -> explicit Sync (read providers)
       OR reviewed Draft -> APPROVE -> Execution Request -> second Execute
          (write providers)

It deliberately does NOT acquire OAuth tokens. The operator supplies a short-
lived/test-account access token through a named environment variable. Tokens,
account hints, event titles, document excerpts, recipients, task bodies and raw
backend logs are never written to the evidence JSON.

Examples:

  python scripts/v2_external_provider_replay.py google-calendar \
    --token-env CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN \
    --calendar-id primary \
    --out artifacts/runtime-evidence/calendar-replay.json

  python scripts/v2_external_provider_replay.py google-drive \
    --token-env CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN \
    --folder-id root \
    --out artifacts/runtime-evidence/drive-replay.json

  # Verify-only is safe and does not send email:
  python scripts/v2_external_provider_replay.py gmail \
    --token-env CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN \
    --out artifacts/runtime-evidence/gmail-verify.json

  # Full write replay requires an explicit side-effect flag:
  python scripts/v2_external_provider_replay.py gmail \
    --token-env CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN \
    --target replay-recipient@example.test \
    --allow-side-effect \
    --out artifacts/runtime-evidence/gmail-send-replay.json

  python scripts/v2_external_provider_replay.py microsoft-todo \
    --token-env CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN \
    --target default \
    --allow-side-effect \
    --out artifacts/runtime-evidence/todo-create-replay.json

Exit code 0 means the requested mode passed. A VERIFY_ONLY write-provider run
may exit 0 while real_write_execution_proven remains false. That distinction is
intentional.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
API = "/api/product/conversation"

_SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\bya29\.[A-Za-z0-9._-]{8,}"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{8,}"),
    re.compile(r"\b[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b"),
)
_SENSITIVE_KEY = re.compile(
    r"(token|secret|authorization|credential|cookie|password|api[_-]?key|"
    r"access[_-]?token|refresh[_-]?token|client[_-]?secret)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ProviderSpec:
    cli_name: str
    provider_id: str
    flag_env: str
    credential_prefix: str
    default_token_env: str
    capabilities: tuple[str, ...]
    mode: str
    query_arg: str = ""
    query_key: str = ""
    default_query_value: str = ""
    draft_kind: str = ""
    default_target: str = ""
    provider_claim: str = ""


PROVIDERS: dict[str, ProviderSpec] = {
    "google-calendar": ProviderSpec(
        cli_name="google-calendar",
        provider_id="GOOGLE_CALENDAR",
        flag_env="CHENGZHU_GOOGLE_CALENDAR_CONNECTOR_ENABLE",
        credential_prefix="provider:google-calendar:env:",
        default_token_env="CHENGZHU_GOOGLE_CALENDAR_ACCESS_TOKEN",
        capabilities=("calendar.read",),
        mode="READ",
        query_arg="calendar_id",
        query_key="calendar_id",
        default_query_value="primary",
        provider_claim="REAL_GOOGLE_CALENDAR_ACCOUNT_REPLAY",
    ),
    "google-drive": ProviderSpec(
        cli_name="google-drive",
        provider_id="GOOGLE_DRIVE",
        flag_env="CHENGZHU_GOOGLE_DRIVE_CONNECTOR_ENABLE",
        credential_prefix="provider:google-drive:env:",
        default_token_env="CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN",
        capabilities=("docs.read",),
        mode="READ",
        query_arg="folder_id",
        query_key="folder_id",
        default_query_value="root",
        provider_claim="REAL_GOOGLE_DRIVE_ACCOUNT_REPLAY",
    ),
    "gmail": ProviderSpec(
        cli_name="gmail",
        provider_id="GOOGLE_MAIL",
        flag_env="CHENGZHU_GOOGLE_MAIL_CONNECTOR_ENABLE",
        credential_prefix="provider:google-mail:env:",
        default_token_env="CHENGZHU_GOOGLE_MAIL_ACCESS_TOKEN",
        capabilities=("email.send",),
        mode="WRITE",
        draft_kind="FOLLOWUP_EMAIL_DRAFT",
        provider_claim="REAL_GMAIL_ACCOUNT_REPLAY",
    ),
    "microsoft-todo": ProviderSpec(
        cli_name="microsoft-todo",
        provider_id="MICROSOFT_GRAPH",
        flag_env="CHENGZHU_MICROSOFT_TODO_CONNECTOR_ENABLE",
        credential_prefix="provider:microsoft-graph:env:",
        default_token_env="CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN",
        capabilities=("task.create",),
        mode="WRITE",
        draft_kind="CREATE_TASK_DRAFT",
        default_target="default",
        provider_claim="REAL_MICROSOFT_TODO_ACCOUNT_REPLAY",
    ),
}


class _FakeProvider(BaseHTTPRequestHandler):
    answer = "Local replay stub. External-model traffic is disabled."

    def log_message(self, *_args):
        return

    def _json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
                "id": "c1",
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
            "id": "c1",
            "object": "chat.completion.chunk",
            "model": "fake-model",
            "choices": [{"index": 0, "delta": {"content": self.answer}, "finish_reason": None}],
        }
        self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def start_fake_provider() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeProvider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/v1"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http(base: str, method: str, path: str, body: Any = None, timeout: float = 90.0) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(base + path, data=data, method=method)
    if data is not None:
        request.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "ignore")
        raise RuntimeError(f"{method} {path} -> {error.code}: {redact_string(detail)[:800]}") from None
    return json.loads(payload) if payload.strip() else {}


def redact_string(value: str) -> str:
    text = str(value or "")
    for pattern in _SECRET_VALUE_PATTERNS:
        text = pattern.sub("[REDACTED_SECRET]", text)
    return text[:20_000]


def sanitize(value: Any, *, depth: int = 0) -> Any:
    if depth > 8:
        return "[TRUNCATED_DEPTH]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, raw_value in list(value.items())[:300]:
            key = str(raw_key)[:200]
            if _SENSITIVE_KEY.search(key):
                continue
            result[key] = sanitize(raw_value, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [sanitize(item, depth=depth + 1) for item in list(value)[:500]]
    if isinstance(value, str):
        return redact_string(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_string(str(value))


def sha256_text(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            text=True,
            timeout=10,
        ).strip()
    except Exception:
        return ""


def build_child_env(
    spec: ProviderSpec,
    token_env: str,
    token: str,
    home: Path,
    fake_base: str,
    *,
    enabled: bool,
) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("CHENGZHU_", "IA_"))
    }
    env["CHENGZHU_HOME"] = str(home)
    env["PYTHONIOENCODING"] = "utf-8"
    env["IA_AUTH_ENABLE"] = "0"
    env[token_env] = token
    if enabled:
        env[spec.flag_env] = "1"
    return env


def start_backend(
    spec: ProviderSpec,
    token_env: str,
    token: str,
    port: int,
    home: Path,
    fake_base: str,
    *,
    enabled: bool,
) -> subprocess.Popen[str]:
    config_dir = home / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(
        json.dumps({
            "models": [{
                "name": "Local stub",
                "api_base_url": fake_base,
                "api_key": "test-key-not-real",
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
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(BACKEND),
        env=build_child_env(spec, token_env, token, home, fake_base, enabled=enabled),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    deadline = time.time() + 90
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(
                f"backend exited early ({process.returncode}):\n{redact_string(output[-2500:])}"
            )
        try:
            http(f"http://127.0.0.1:{port}", "GET", "/api/options", timeout=5)
            return process
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("backend did not become ready in 90s")


def stop_backend(process: subprocess.Popen[str]) -> str:
    process.terminate()
    try:
        output = process.communicate(timeout=30)[0] or ""
    except subprocess.TimeoutExpired:
        process.kill()
        output = process.communicate()[0] or ""
    return output


def provider_row(base: str, provider_id: str) -> dict[str, Any]:
    catalog = http(base, "GET", f"{API}/integrations/catalog")
    rows = catalog.get("items", catalog if isinstance(catalog, list) else [])
    return next((row for row in rows if row.get("provider_id") == provider_id), {})


def create_connection(base: str, spec: ProviderSpec, token_env: str) -> dict[str, Any]:
    return http(
        base,
        "POST",
        f"{API}/integrations/connections",
        {
            "provider_id": spec.provider_id,
            "display_name": f"Real-account replay · {spec.cli_name}",
            "granted_capabilities": list(spec.capabilities),
            "credential_ref": spec.credential_prefix + token_env,
        },
    )


def create_space_and_session(base: str, label: str) -> tuple[str, str]:
    space = http(base, "POST", f"{API}/spaces", {
        "title": f"External provider replay · {label}",
        "profile": "PROJECT_SYNC",
    })
    space_id = str(space.get("id") or "")
    session = http(base, "POST", f"{API}/spaces/{space_id}/sessions", {
        "title": f"Replay · {label}",
        "consent_ack": True,
        "capture_mode": "NOTES_ONLY",
        "processing_mode": "LOCAL",
        "policy": {
            "external_writeback": "REVIEW_REQUIRED",
            "participant_consent_status": "NOT_APPLICABLE",
            "participant_transparency_plan": "NOT_APPLICABLE",
        },
    })
    return space_id, str(session.get("id") or "")


def assert_safe_connection(connection: dict[str, Any]) -> None:
    if "credential_ref" in connection:
        raise AssertionError("public Connection response leaked credential_ref")
    if connection.get("credential_ref_present") is not True:
        raise AssertionError("Connection did not preserve opaque credential reference")


def run_read_replay(
    base: str,
    spec: ProviderSpec,
    connection: dict[str, Any],
    query_value: str,
) -> dict[str, Any]:
    space_id, session_id = create_space_and_session(base, spec.cli_name)
    sync = http(
        base,
        "POST",
        f"{API}/integrations/connections/{connection['id']}/sync",
        {
            "space_id": space_id,
            "capabilities": list(spec.capabilities),
            "query": {spec.query_key: query_value},
            "limit": 100,
        },
        timeout=180,
    )
    snapshots = http(base, "GET", f"{API}/spaces/{space_id}/connector-snapshots").get("items", [])
    selected_ids = [str(row.get("id") or "") for row in snapshots[:2] if row.get("id")]
    if selected_ids:
        http(base, "PATCH", f"{API}/spaces/{space_id}", {
            "selected_connector_snapshot_ids": selected_ids,
        })

    preflight = http(base, "GET", f"{API}/sessions/{session_id}/preflight")
    # Read permissions are explicitly frozen into the Session Pack.
    # Recreate the session with requested permissions if the default session
    # did not ask for them.
    if spec.capabilities:
        session = http(base, "GET", f"{API}/sessions/{session_id}")
        policy = dict(session.get("policy") or {})
        policy["connector_permissions"] = list(spec.capabilities)
        http(base, "PATCH", f"{API}/sessions/{session_id}", {"policy": policy})
        preflight = http(base, "GET", f"{API}/sessions/{session_id}/preflight")

    started = http(base, "POST", f"{API}/sessions/{session_id}/start")
    context = http(base, "GET", f"{API}/sessions/{session_id}/context")
    grants = list((context.get("connector_runtime") or {}).get("grants") or [])
    frozen_snapshots = list(context.get("connector_snapshots") or [])

    kinds = sorted({str(row.get("external_kind") or "") for row in snapshots if row.get("external_kind")})
    return {
        "sync_completed": True,
        "sync_snapshot_count": len(snapshots),
        "sync_returned_provider_cursor": bool(
            (sync.get("connection") or {}).get("sync_cursor")
            or (sync.get("connection") or {}).get("sync_cursors")
        ),
        "snapshot_external_kinds": kinds,
        "all_snapshots_have_content_hash": bool(snapshots)
        and all(bool(row.get("content_hash")) for row in snapshots),
        "selected_snapshot_count": len(selected_ids),
        "preflight_blocker_count": len(preflight.get("blockers") or []),
        "session_started": bool(started),
        "frozen_snapshot_count": len(frozen_snapshots),
        "frozen_connector_grant_count": len(grants),
        "real_provider_data_snapshot_proven": len(snapshots) > 0,
    }


def run_write_replay(
    base: str,
    spec: ProviderSpec,
    connection: dict[str, Any],
    target: str,
    *,
    allow_side_effect: bool,
) -> dict[str, Any]:
    space_id, session_id = create_space_and_session(base, spec.cli_name)
    marker = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    title = f"Chengzhu connector replay {marker}"
    content = (
        "This is a deliberate Chengzhu real-account connector replay. "
        "It was created through the reviewed Draft -> APPROVE -> Execution Request -> Execute path."
    )
    draft = http(base, "POST", f"{API}/sessions/{session_id}/draft-actions", {
        "kind": spec.draft_kind,
        "title": title,
        "content": content,
        "target": "",
        "source_refs": [],
        "payload": {"replay_marker_sha256": sha256_text(marker)},
    })
    approved = http(base, "POST", f"{API}/draft-actions/{draft['id']}/review", {"action": "APPROVE"})
    execution = http(base, "POST", f"{API}/draft-actions/{draft['id']}/execution", {
        "connection_id": connection["id"],
        "target": target,
    })

    result: dict[str, Any] = {
        "draft_created": bool(draft.get("id")),
        "draft_approved": approved.get("status") == "APPROVED",
        "execution_request_created": bool(execution.get("id")),
        "side_effect_authorized": bool(allow_side_effect),
        "write_execution_attempted": False,
        "write_execution_status": "NOT_EXECUTED",
        "provider_external_id_present": False,
        "provider_accepted_write": False,
        "provider_delivery_or_visibility_proven": False,
    }
    if not allow_side_effect:
        return result

    executed = http(
        base,
        "POST",
        f"{API}/integrations/executions/{execution['id']}/execute",
        timeout=180,
    )
    status = str(executed.get("status") or "")
    response = dict(executed.get("response") or {})
    result.update({
        "write_execution_attempted": True,
        "write_execution_status": status,
        "provider_external_id_present": bool(
            response.get("external_id") or response.get("message_id") or response.get("task_id")
        ),
        "provider_accepted_write": status == "SUCCEEDED",
        "provider_delivery_or_visibility_proven": False,
        "unknown_outcome_requires_manual_provider_check": status == "UNKNOWN_OUTCOME",
    })
    if status != "SUCCEEDED":
        raise RuntimeError(
            "External write did not return SUCCEEDED. Do not retry automatically; "
            f"observed status={status or 'UNKNOWN'}."
        )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider", choices=sorted(PROVIDERS))
    parser.add_argument("--token-env", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--calendar-id", default="primary")
    parser.add_argument("--folder-id", default="root")
    parser.add_argument("--target", default="")
    parser.add_argument(
        "--allow-side-effect",
        action="store_true",
        help="Required to actually send Gmail or create a Microsoft To Do task.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = PROVIDERS[args.provider]
    token_env = str(args.token_env or spec.default_token_env).strip()
    token = str(os.environ.get(token_env) or "").strip()
    if not token:
        raise SystemExit(
            f"{token_env} is not set. Obtain a short-lived/test-account token outside Chengzhu "
            "and expose it only to this shell."
        )

    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"refusing to overwrite existing evidence file: {out}")
    if out.resolve() == (ROOT / "backend" / "data" / "product.db").resolve():
        raise SystemExit("--out must not point at product.db")

    query_value = ""
    if spec.cli_name == "google-calendar":
        query_value = str(args.calendar_id or "primary").strip()
    elif spec.cli_name == "google-drive":
        query_value = str(args.folder_id or "root").strip()

    target = str(args.target or spec.default_target).strip()
    if spec.mode == "WRITE" and args.allow_side_effect and not target:
        raise SystemExit("--target is required when --allow-side-effect is used for this provider")

    report: dict[str, Any] = {
        "contract": "chengzhu-v2-real-account-provider-replay-1",
        "evidence_type": spec.provider_claim,
        "provider": spec.provider_id,
        "requested_mode": "FULL_REPLAY" if (spec.mode == "READ" or args.allow_side_effect) else "VERIFY_ONLY",
        "source_sha": git_sha(),
        "credential_storage": "PROCESS_ENV_ONLY_OPAQUE_REF_IN_DB",
        "raw_provider_content_in_evidence": False,
        "account_identity_value_in_evidence": False,
        "remote_model_traffic": "LOCAL_FAKE_PROVIDER_ONLY",
        "checks": {},
        "result": {},
        "passed": False,
        "claims": {
            "real_account_verified": False,
            "real_read_sync_proven": False,
            "real_provider_data_snapshot_proven": False,
            "real_write_execution_proven": False,
            "provider_delivery_or_visibility_proven": False,
            "oauth_publication_or_app_verification_proven": False,
        },
    }

    def check(name: str, condition: bool, detail: Any = None) -> None:
        report["checks"][name] = {
            "ok": bool(condition),
            "detail": sanitize(detail),
        }
        if not condition:
            raise AssertionError(name)

    fake, fake_base = start_fake_provider()
    disabled_output = ""
    enabled_output = ""
    try:
        with tempfile.TemporaryDirectory(prefix=f"cz-{spec.cli_name}-off-") as home_off:
            port = free_port()
            base = f"http://127.0.0.1:{port}"
            process = start_backend(
                spec, token_env, token, port, Path(home_off), fake_base, enabled=False,
            )
            try:
                row = provider_row(base, spec.provider_id)
                check("disabled_catalog_row_present", bool(row))
                check("disabled_adapter_not_available", row.get("adapter_available") is False)
                connections = http(base, "GET", f"{API}/integrations/connections").get("items", [])
                check("disabled_no_connections", len(connections) == 0)
            finally:
                disabled_output = stop_backend(process)

        with tempfile.TemporaryDirectory(prefix=f"cz-{spec.cli_name}-on-") as home_on:
            port = free_port()
            base = f"http://127.0.0.1:{port}"
            process = start_backend(
                spec, token_env, token, port, Path(home_on), fake_base, enabled=True,
            )
            try:
                row = provider_row(base, spec.provider_id)
                check("enabled_adapter_available", row.get("adapter_available") is True)
                check(
                    "catalog_capabilities_exact",
                    sorted(row.get("capabilities") or []) == sorted(spec.capabilities),
                    row.get("capabilities"),
                )
                setup = dict(row.get("setup") or {})
                check(
                    "catalog_runtime_opt_in_matches",
                    str(setup.get("runtime_opt_in_env") or "").startswith(spec.flag_env + "="),
                )
                check("catalog_secret_storage_process_env", setup.get("secret_storage") == "PROCESS_ENV_ONLY")

                connection = create_connection(base, spec, token_env)
                assert_safe_connection(connection)
                check("connection_created_disconnected", connection.get("status") == "DISCONNECTED")
                verified = http(
                    base,
                    "POST",
                    f"{API}/integrations/connections/{connection['id']}/verify",
                    timeout=120,
                )
                assert_safe_connection(verified)
                check("real_account_verify_connected", verified.get("status") == "CONNECTED")
                check("verify_account_hint_present", bool(verified.get("account_hint")))
                report["claims"]["real_account_verified"] = True

                if spec.mode == "READ":
                    result = run_read_replay(base, spec, verified, query_value)
                    report["claims"]["real_read_sync_proven"] = bool(result["sync_completed"])
                    report["claims"]["real_provider_data_snapshot_proven"] = bool(
                        result["real_provider_data_snapshot_proven"]
                    )
                else:
                    result = run_write_replay(
                        base,
                        spec,
                        verified,
                        target,
                        allow_side_effect=bool(args.allow_side_effect),
                    )
                    report["claims"]["real_write_execution_proven"] = bool(
                        result["provider_accepted_write"]
                    )
                    report["claims"]["provider_delivery_or_visibility_proven"] = False
                report["result"] = result
            finally:
                enabled_output = stop_backend(process)
    except Exception as exc:
        report["error"] = redact_string(str(exc))
        report["passed"] = False
    finally:
        fake.shutdown()
        fake.server_close()

    # Never write backend logs, but prove the token itself was not echoed into
    # either process output. If it was, fail the replay and leave only the
    # boolean finding in the privacy-minimized report.
    token_leaked = bool(token and (token in disabled_output or token in enabled_output))
    report["checks"]["backend_stdout_token_absent"] = {"ok": not token_leaked, "detail": None}
    if token_leaked:
        report["passed"] = False
        report["error"] = "backend stdout contained the credential value; raw logs were not persisted"
    elif "error" not in report:
        if spec.mode == "READ":
            report["passed"] = bool(report["claims"]["real_account_verified"] and report["claims"]["real_read_sync_proven"])
        elif args.allow_side_effect:
            report["passed"] = bool(report["claims"]["real_account_verified"] and report["claims"]["real_write_execution_proven"])
        else:
            report["passed"] = bool(report["claims"]["real_account_verified"])

    # Gmail provider acceptance is not recipient delivery, and neither Gmail
    # nor Drive/Calendar runtime replay proves Google OAuth app publication.
    if spec.provider_id == "GOOGLE_MAIL":
        report["claims"]["provider_delivery_or_visibility_proven"] = False
        report["claims"]["oauth_publication_or_app_verification_proven"] = False
    if spec.provider_id in {"GOOGLE_CALENDAR", "GOOGLE_DRIVE"}:
        report["claims"]["oauth_publication_or_app_verification_proven"] = False

    safe_report = sanitize(report)
    encoded = json.dumps(safe_report, ensure_ascii=False, indent=2)
    if token and token in encoded:
        raise SystemExit("refusing to write evidence because credential value survived sanitization")
    # credential_ref itself is intentionally excluded from evidence, even
    # though it is only an opaque reference.
    if spec.credential_prefix + token_env in encoded:
        raise SystemExit("refusing to write evidence because credential_ref survived sanitization")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(encoded + "\n", encoding="utf-8")
    print(json.dumps({
        "provider": spec.provider_id,
        "requested_mode": safe_report["requested_mode"],
        "passed": safe_report["passed"],
        "out": str(out),
        "claims": safe_report["claims"],
    }, ensure_ascii=False))
    return 0 if safe_report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
