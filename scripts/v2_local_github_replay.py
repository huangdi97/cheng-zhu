"""Real GitHub account connector replay for the v2 closure (offline LLM stub).

Runs two real backend processes against a real GitHub account credential that the
backend resolves from the process environment:

  run A (flag unset)  -> the GitHub adapter must NOT be registered: catalog shows
                         ``adapter_available = false`` and no external call happens;
  run B (flag = 1)    -> real read snapshot + real reviewed ``CREATE_ISSUE_DRAFT``
                         executing exactly one GitHub issue.

Nothing here calls an external model provider: the backend is pointed at a local
fake OpenAI-compatible server so only GitHub traffic leaves the machine.

Usage:
  python scripts/v2_local_github_replay.py --repo owner/name --token-env CHENGZHU_GITHUB_TOKEN \
      --out artifacts/runtime-evidence/<dir>/github-replay.json

Exit code 0 only when every assertion passes.
"""
from __future__ import annotations

import argparse
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
API = "/api/product/conversation"
CONNECTOR_FLAG = "CHENGZHU_GITHUB_CONNECTOR_ENABLE"


# --------------------------------------------------------------------------- #
# local fake OpenAI-compatible provider (keeps model traffic off the network)
# --------------------------------------------------------------------------- #
class _FakeProvider(BaseHTTPRequestHandler):
    answer = "先给结论：这里是与外部连接器无关的本地桩回答。"

    def log_message(self, *_args):  # silence
        return

    def _json(self, payload: dict) -> None:
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
            self._json(
                {
                    "id": "c1",
                    "object": "chat.completion",
                    "model": "fake-model",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": self.answer},
                            "finish_reason": "stop",
                        }
                    ],
                }
            )
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
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/v1"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http(base: str, method: str, path: str, body: Any = None, timeout: float = 60.0) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(base + path, data=data, method=method)
    if data is not None:
        request.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "ignore")
        raise RuntimeError(f"{method} {path} -> {error.code}: {detail[:600]}") from None
    return json.loads(payload) if payload.strip() else {}


def start_backend(port: int, home: Path, fake_base: str, enable_connector: bool, token: str) -> subprocess.Popen:
    config_dir = home / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(
        json.dumps(
            {
                "models": [
                    {
                        "name": "Local stub",
                        "api_base_url": fake_base,
                        "api_key": "test-key-not-real",
                        "model": "fake-model",
                        "enabled": True,
                        "supports_think": False,
                        "supports_vision": False,
                    }
                ],
                "active_model": 0,
                "stt_provider": "whisper",
                "ai_policy_mode": "AI_ALLOWED",
                "onboarding_completed": True,
            }
        ),
        encoding="utf-8",
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("CHENGZHU_", "IA_"))
    }
    env["CHENGZHU_HOME"] = str(home)
    env["PYTHONIOENCODING"] = "utf-8"
    if enable_connector:
        env[CONNECTOR_FLAG] = "1"
    # A real credential is only ever handed to the child process environment.
    if token:
        env["CHENGZHU_GITHUB_TOKEN"] = token
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
            raise RuntimeError(f"backend exited early ({process.returncode}):\n{output[-2000:]}")
        try:
            http(f"http://127.0.0.1:{port}", "GET", "/api/options", timeout=5)
            return process
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("backend did not become ready in 90s")


def stop_backend(process: subprocess.Popen) -> str:
    process.terminate()
    try:
        output = process.communicate(timeout=30)[0] or ""
    except subprocess.TimeoutExpired:
        process.kill()
        output = process.communicate()[0] or ""
    return output


def github_api(token: str, method: str, path: str, body: Any = None) -> Any:
    request = urllib.request.Request(f"https://api.github.com{path}", method=method)
    request.add_header("accept", "application/vnd.github+json")
    request.add_header("authorization", f"Bearer {token}")
    request.add_header("user-agent", "chengzhu-closure-replay")
    data = None if body is None else json.dumps(body).encode("utf-8")
    if data is not None:
        request.add_header("content-type", "application/json")
    request.data = data
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "ignore")
        raise RuntimeError(f"GitHub {method} {path} -> {error.code}: {detail[:400]}") from None
    return json.loads(payload) if payload.strip() else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="owner/name of the throwaway test repository")
    parser.add_argument("--token-env", default="CHENGZHU_GITHUB_TOKEN")
    parser.add_argument("--out", default="")
    parser.add_argument(
        "--issue-title",
        default="Chengzhu v2 closure replay: reviewed issue draft " + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
    )
    parser.add_argument("--issue-body", default="Created by the reviewed CREATE_ISSUE_DRAFT flow during the v2 local closure replay.")
    args = parser.parse_args()

    token = os.environ.get(args.token_env, "").strip()
    if not token:
        raise SystemExit(f"{args.token_env} is not set in this shell; run with the real account credential present")

    report: dict[str, Any] = {
        "evidence_type": "GITHUB_REAL_ACCOUNT_REPLAY",
        "repository": args.repo,
        "disabled_run": {},
        "enabled_run": {},
        "checks": {},
        "assertions": [],
        "passed": False,
    }

    def check(name: str, condition: bool, detail: Any = None) -> None:
        report["checks"][name] = {"ok": bool(condition), "detail": detail}
        report["assertions"].append({"name": name, "ok": bool(condition)})

    provider, fake_base = start_fake_provider()
    try:
        # ---------------- run A: connector flag unset ------------------------ #
        with tempfile.TemporaryDirectory(prefix="cz-replay-off-") as home_off:
            port = free_port()
            base = f"http://127.0.0.1:{port}"
            process = start_backend(port, Path(home_off), fake_base, enable_connector=False, token=token)
            try:
                catalog = http(base, "GET", f"{API}/integrations/catalog")
                rows = catalog.get("items", catalog if isinstance(catalog, list) else [])
                github_row = next((row for row in rows if row.get("provider_id") == "GITHUB"), None)
                report["disabled_run"] = {
                    "catalog_row": github_row,
                    "connection_count": len(http(base, "GET", f"{API}/integrations/connections").get("items", [])),
                }
                check("disabled_adapter_not_available", bool(github_row) and github_row.get("adapter_available") is False, github_row)
                check("disabled_no_connections", report["disabled_run"]["connection_count"] == 0)
            finally:
                stop_backend(process)

        # ---------------- run B: connector enabled --------------------------- #
        with tempfile.TemporaryDirectory(prefix="cz-replay-on-") as home_on:
            home = Path(home_on)
            port = free_port()
            base = f"http://127.0.0.1:{port}"
            process = start_backend(port, home, fake_base, enable_connector=True, token=token)
            step: dict[str, Any] = {}
            try:
                # 1. catalog (enabled)
                catalog = http(base, "GET", f"{API}/integrations/catalog")
                rows = catalog.get("items", catalog if isinstance(catalog, list) else [])
                github_row = next((row for row in rows if row.get("provider_id") == "GITHUB"), {})
                setup = github_row.get("setup", {})
                step["catalog_github"] = github_row
                check("enabled_adapter_available", github_row.get("adapter_available") is True, github_row.get("adapter_available"))
                check(
                    "catalog_capabilities",
                    sorted(github_row.get("capabilities", [])) == ["issue.create", "project.read"],
                    github_row.get("capabilities"),
                )
                check(
                    "catalog_provider_scopes",
                    github_row.get("provider_scopes", {}).get("project.read") == "Issues: read"
                    and github_row.get("provider_scopes", {}).get("issue.create") == "Issues: write",
                    github_row.get("provider_scopes"),
                )
                check("catalog_credential_ref_format", setup.get("credential_ref_format") == "provider:github:env:<ENV_VAR>", setup)
                check("catalog_runtime_opt_in_env", setup.get("runtime_opt_in_env") == "CHENGZHU_GITHUB_CONNECTOR_ENABLE=1", setup)
                check("catalog_secret_storage", setup.get("secret_storage") == "PROCESS_ENV_ONLY", setup)

                # 2. create connection
                connection = http(
                    base,
                    "POST",
                    f"{API}/integrations/connections",
                    {
                        "provider_id": "GITHUB",
                        "display_name": "Closure replay GitHub",
                        "granted_capabilities": ["project.read", "issue.create"],
                        "credential_ref": f"provider:github:env:{args.token_env}",
                    },
                )
                connection_id = connection.get("id")
                step["connection"] = connection
                check("connection_disconnected_initially", connection.get("status") == "DISCONNECTED", connection.get("status"))
                check("connection_credential_ref_present", connection.get("credential_ref_present") is True, connection)
                check("connection_does_not_return_credential_ref", "credential_ref" not in connection, list(connection.keys()))
                check(
                    "connection_scope_collapsed_to_write",
                    connection.get("provider_scopes") in (["Issues: write"],),
                    connection.get("provider_scopes"),
                )

                # 3. verify
                verified = http(base, "POST", f"{API}/integrations/connections/{connection_id}/verify")
                step["verify"] = verified
                check("verify_connected", verified.get("status") == "CONNECTED", verified.get("status"))
                check("verify_account_hint_login", bool(verified.get("account_hint")), verified.get("account_hint"))

                # 4. space + session
                space = http(base, "POST", f"{API}/spaces", {"title": "GitHub connector replay space", "profile": "PROJECT_SYNC"})
                space_id = space.get("id")
                step["space_id"] = space_id

                # 5. sync a read snapshot of the real repository
                sync = http(
                    base,
                    "POST",
                    f"{API}/integrations/connections/{connection_id}/sync",
                    {
                        "space_id": space_id,
                        "capabilities": ["project.read"],
                        "query": {"repository": args.repo, "state": "all"},
                        "limit": 100,
                    },
                )
                step["sync"] = sync
                snapshots = http(base, "GET", f"{API}/spaces/{space_id}/connector-snapshots")
                snapshot_rows = snapshots.get("items", [])
                step["snapshot_count"] = len(snapshot_rows)
                check("sync_returned_snapshots", len(snapshot_rows) > 0, len(snapshot_rows))
                if snapshot_rows:
                    first = snapshot_rows[0]
                    step["snapshot_sample"] = {
                        key: first.get(key)
                        for key in (
                            "id", "connection_id", "capability", "external_kind", "external_id",
                            "content_hash", "provider_id", "is_latest_revision", "occurred_at",
                        )
                    }
                    check("snapshot_has_content_hash", bool(first.get("content_hash")), first.get("content_hash"))
                    check("snapshot_revision_view_present", "is_latest_revision" in first, list(first.keys()))
                    check("snapshot_is_immutable_projection", first.get("capability") == "project.read", first.get("capability"))

                # 6. select the snapshot into the Space
                selected_ids = [row["id"] for row in snapshot_rows[:2]] or []
                patched = http(base, "PATCH", f"{API}/spaces/{space_id}", {"selected_connector_snapshot_ids": selected_ids})
                step["space_selection"] = patched.get("selected_connector_snapshot_ids")
                check("space_selected_snapshots", bool(selected_ids), selected_ids)

                # 7. session + preflight + start (freeze)
                session = http(
                    base,
                    "POST",
                    f"{API}/spaces/{space_id}/sessions",
                    {
                        "title": "Connector replay session",
                        "consent_ack": True,
                        "capture_mode": "NOTES_ONLY",
                        "processing_mode": "LOCAL",
                        "policy": {
                            "transcript_mode": "TEXT_ONLY",
                            "ai_policy": "AI_ALLOWED",
                            # Session Pack permissions are read-only by design: a write
                            # capability is never inherited from a read grant.
                            "connector_permissions": ["project.read"],
                            "external_writeback": "REVIEW_REQUIRED",
                            "transcript_consent": "NOT_APPLICABLE",
                        },
                    },
                )
                session_id = session.get("id")
                step["session_id"] = session_id
                preflight = http(base, "GET", f"{API}/sessions/{session_id}/preflight")
                preview = preflight.get("pack_preview") or {}
                step["preflight"] = {
                    "blockers": preflight.get("blockers"),
                    "warnings": preflight.get("warnings"),
                    "pack_preview_snapshot_ids": preview.get("selected_connector_snapshot_ids"),
                    "pack_preview_snapshots": len(preview.get("connector_snapshots") or []),
                    "connector_runtime": preflight.get("connector_runtime"),
                }
                check("preflight_has_no_blockers", not preflight.get("blockers"), preflight.get("blockers"))
                check(
                    "preflight_pack_preview_has_snapshot",
                    len(preview.get("connector_snapshots") or []) > 0,
                    preview.get("selected_connector_snapshot_ids"),
                )
                started = http(base, "POST", f"{API}/sessions/{session_id}/start")
                session_after = http(base, "GET", f"{API}/sessions/{session_id}")
                step["start"] = {
                    "start_response_keys": sorted(started.keys())[:10],
                    "session_status": session_after.get("status"),
                }
                check("session_started_active", session_after.get("status") == "ACTIVE", session_after.get("status"))
                context = http(base, "GET", f"{API}/sessions/{session_id}/context")
                frozen_snapshots = context.get("connector_snapshots") or []
                grants = (context.get("connector_runtime") or {}).get("grants", [])
                step["frozen"] = {
                    "pack_digest": context.get("pack_digest"),
                    "connector_snapshots": len(frozen_snapshots),
                    "connector_grants": grants,
                    "conversation_state": context.get("conversation_state"),
                }
                check("frozen_pack_has_snapshot", len(frozen_snapshots) > 0, len(frozen_snapshots))
                check("frozen_pack_has_connector_grant", len(grants) > 0, grants)
                check(
                    "frozen_pack_grant_has_account_hint",
                    all(grant.get("account_hint") for grant in grants),
                    grants,
                )

                # 7b. a write capability must never be grantable inside a Session Pack
                write_probe_session = http(
                    base,
                    "POST",
                    f"{API}/spaces/{space_id}/sessions",
                    {
                        "title": "Connector write-permission probe",
                        "consent_ack": True,
                        "capture_mode": "NOTES_ONLY",
                        "processing_mode": "LOCAL",
                        "policy": {
                            "transcript_mode": "TEXT_ONLY",
                            "ai_policy": "AI_ALLOWED",
                            "connector_permissions": ["project.read", "issue.create"],
                            "external_writeback": "REVIEW_REQUIRED",
                            "transcript_consent": "NOT_APPLICABLE",
                        },
                    },
                ).get("id")
                write_probe_error = ""
                try:
                    http(base, "POST", f"{API}/sessions/{write_probe_session}/start")
                except RuntimeError as error:
                    write_probe_error = str(error)
                step["write_grant_gate"] = write_probe_error[:400]
                check(
                    "session_pack_write_grant_blocked",
                    "WRITE_REQUIRES_EXPLICIT_EXECUTION_FLOW" in write_probe_error,
                    write_probe_error[:300],
                )

                # 8. manual ask grounded on the frozen connector snapshot
                # Ask about ONE frozen snapshot, using only words taken from that same
                # title, so the question is a coherent query about one frozen source
                # (mixing tokens from two different snapshots is legitimately not grounded).
                first_title = str((frozen_snapshots[0] if frozen_snapshots else {}).get("title") or "")
                ask_tokens = [word for word in first_title.replace(":", " ").split() if len(word) > 4][:3]
                question = " ".join(ask_tokens) if ask_tokens else "cache invalidation"
                answered = http(base, "POST", f"{API}/sessions/{session_id}/ask", {"question": question})
                matches = answered.get("matches") or []
                top = matches[0] if matches else {}
                provenance_blob = json.dumps(top.get("source_refs") or [], ensure_ascii=False)
                step["ask"] = {
                    "question": question,
                    "grounded": answered.get("grounded"),
                    "truth_confirmed": answered.get("truth_confirmed"),
                    "top_kind": top.get("kind"),
                    "top_authority": top.get("authority"),
                    "top_title": top.get("title"),
                    "top_source_refs": top.get("source_refs"),
                }
                check("ask_grounded_on_snapshot", answered.get("grounded") is True, answered.get("grounded"))
                check("ask_authority_reference_source", top.get("authority") == "REFERENCE_SOURCE", top.get("authority"))
                check("ask_source_kind_connector_snapshot", top.get("kind") == "CONNECTOR_SNAPSHOT", top.get("kind"))
                check("ask_not_promoted_to_confirmed_truth", answered.get("truth_confirmed") is False, answered.get("truth_confirmed"))
                check(
                    "ask_source_ref_carries_connector_provenance",
                    any(token in provenance_blob for token in ("content_hash", "provider_id", "connection_id")),
                    top.get("source_refs"),
                )

                narrow = http(base, "POST", f"{API}/sessions/{session_id}/ask", {"question": "50x data scale unrelated token"})
                step["ask_negative"] = {"grounded": narrow.get("grounded")}
                check("ask_negative_not_grounded", narrow.get("grounded") is False, narrow.get("grounded"))

                # 9. reviewed external write: draft -> approve -> explicit target -> second execute
                draft = http(
                    base,
                    "POST",
                    f"{API}/sessions/{session_id}/draft-actions",
                    {
                        "kind": "CREATE_ISSUE_DRAFT",
                        "title": args.issue_title,
                        "content": args.issue_body,
                        "source_refs": [{"kind": "USER_NOTE", "excerpt": question}],
                    },
                )
                draft_id = draft.get("id")
                step["draft"] = {"id": draft_id, "status": draft.get("status"), "kind": draft.get("kind")}
                check("draft_created_not_executed", draft.get("status") in ("DRAFT", "PENDING_REVIEW"), draft.get("status"))

                approved = http(base, "POST", f"{API}/draft-actions/{draft_id}/review", {"action": "APPROVE"})
                step["review"] = approved.get("status")
                check("draft_approved", approved.get("status") == "APPROVED", approved.get("status"))

                # gating: with no explicit target anywhere (neither on the approved
                # draft nor on the execution request) nothing may reach the provider.
                probe_draft = http(
                    base,
                    "POST",
                    f"{API}/sessions/{session_id}/draft-actions",
                    {
                        "kind": "CREATE_ISSUE_DRAFT",
                        "title": f"{args.issue_title} (no-target probe)",
                        "content": args.issue_body,
                        "source_refs": [{"kind": "USER_NOTE", "excerpt": question}],
                    },
                )
                probe_draft_id = probe_draft["id"]
                http(base, "POST", f"{API}/draft-actions/{probe_draft_id}/review", {"action": "APPROVE"})
                empty_request = http(
                    base,
                    "POST",
                    f"{API}/draft-actions/{probe_draft_id}/execution",
                    {"connection_id": connection_id, "target": ""},
                )
                empty_result = http(
                    base, "POST", f"{API}/integrations/executions/{empty_request['id']}/execute"
                )
                step["no_target_gate"] = {
                    "request_status": empty_request.get("status"),
                    "request_target": empty_request.get("target"),
                    "result_status": empty_result.get("status"),
                    "result_error": str(empty_result.get("error") or "")[:200],
                }
                check(
                    "explicit_target_required",
                    empty_result.get("status") in ("FAILED", "UNKNOWN_OUTCOME", "BLOCKED"),
                    step["no_target_gate"],
                )

                request_row = http(
                    base,
                    "POST",
                    f"{API}/draft-actions/{draft_id}/execution",
                    {"connection_id": connection_id, "target": args.repo},
                )
                execution_id = request_row.get("id")
                step["execution_request"] = {"id": execution_id, "status": request_row.get("status"), "target": request_row.get("target")}
                check("execution_request_pending", request_row.get("status") == "PENDING", request_row.get("status"))
                check("execution_request_target_recorded", request_row.get("target") == args.repo, request_row.get("target"))

                executed = http(base, "POST", f"{API}/integrations/executions/{execution_id}/execute")
                step["execution_result"] = {
                    "status": executed.get("status"),
                    "target": executed.get("target"),
                    "has_response": bool(executed.get("response")),
                }
                check("execution_succeeded", executed.get("status") == "SUCCEEDED", executed.get("status"))

                # idempotency: a second execute must not create a second issue
                replayed = http(base, "POST", f"{API}/integrations/executions/{execution_id}/execute")
                step["execution_replay_status"] = replayed.get("status")
                check("second_execute_is_idempotent", replayed.get("status") == "SUCCEEDED", replayed.get("status"))

                # 10. audit read path
                audit = http(base, "GET", f"{API}/integrations/executions", timeout=60)
                audit_rows = audit if isinstance(audit, list) else audit.get("items", [])
                row = next((item for item in audit_rows if item.get("id") == execution_id), {})
                step["audit_row"] = {
                    key: row.get(key)
                    for key in ("id", "draft_action_id", "connection_id", "capability", "operation", "target", "status", "idempotency_key")
                }
                serialized_audit = json.dumps(row, ensure_ascii=False)
                check("audit_row_present", bool(row), list(row.keys())[:12])
                check("audit_records_target", row.get("target") == args.repo, row.get("target"))
                check("audit_response_sanitized", "[REDACTED_SECRET]" in serialized_audit or "authorization" not in serialized_audit.lower(), True)
                check("audit_never_contains_token", token not in serialized_audit, "token value absent from audit row")

                # 11. provider truth: exactly one issue with the exact reviewed content
                matching = []
                issues: list[dict[str, Any]] = []
                for _attempt in range(10):
                    issues = github_api(token, "GET", f"/repos/{args.repo}/issues?state=all&per_page=100")
                    matching = [item for item in issues if item.get("title") == args.issue_title]
                    if matching:
                        break
                    time.sleep(3)
                numbers = sorted(item["number"] for item in matching)
                created_body = matching[0].get("body", "") if matching else ""
                audit_idempotency_key = str(row.get("idempotency_key") or "")
                body_matches_reviewed = created_body.strip().startswith(args.issue_body.strip())
                marker_present = bool(audit_idempotency_key) and f"chengzhu-execution:{audit_idempotency_key}" in created_body
                step["github_issues"] = {
                    "total": len(issues),
                    "matching_title": len(matching),
                    "matching_numbers": numbers,
                    "body_starts_with_reviewed_content": body_matches_reviewed,
                    "audit_idempotency_marker_present": marker_present,
                    "created_body": created_body,
                    "created_url": matching[0].get("html_url") if matching else None,
                }
                check("github_exactly_one_issue", len(matching) == 1, numbers)
                check("github_issue_body_matches_reviewed_content", body_matches_reviewed, created_body[:200])
                check("github_issue_carries_audit_idempotency_marker", marker_present, audit_idempotency_key)

                # 12. the credential must never reach the persisted store
                db_bytes = (home / "data" / "product.db").read_bytes() if (home / "data" / "product.db").exists() else b""
                check("token_absent_from_product_db", token.encode() not in db_bytes, "scanned product.db bytes")
                export = http(base, "GET", f"{API}/spaces/{space_id}/export")
                check("token_absent_from_space_export", token not in json.dumps(export, ensure_ascii=False), "scanned space export")

                report["enabled_run"] = step
            finally:
                report["backend_log_tail"] = stop_backend(process)[-4000:] if process.stdout else ""
    finally:
        provider.shutdown()

    report["passed"] = all(item["ok"] for item in report["assertions"])
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"\nwritten: {out}")
    failed = [item["name"] for item in report["assertions"] if not item["ok"]]
    if failed:
        print("\nFAILED ASSERTIONS: " + ", ".join(failed))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
