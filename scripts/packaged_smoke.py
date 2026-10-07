"""Packaged smoke test (R2 Stage AJ).

Runs the real built sidecar (not the source tree) against a throwaway user-data
dir and a local fake OpenAI-compatible provider, so no real key is needed.

Checks:
  1. sidecar starts without a system Python assumption (CHENGZHU_HOME set)
  2. /api/options, /api/config respond; version string
  3. DB migrations applied under CHENGZHU_HOME/data (latest intelligence + product schema)
  4. prebuilt frontend served (CHENGZHU_FRONTEND_DIST)
  5. Fast Cue E2E with the fake provider: guidance_fast before the first
     answer_chunk, answer_done carries latency
  6. InterviewPack freeze persists across a sidecar restart
  7. Conversation Beta packaged loop:
     Space -> Preflight -> frozen Session Pack -> reviewed truth/Open Thread
     -> deterministic Guidance -> Continue -> History -> Export
  8. Conversation product.db and continuity persist across sidecar restart
  9. nothing is written next to the executable (install dir stays clean)
 10. LICENSE / THIRD_PARTY_NOTICES bundled

Usage:
  python scripts/packaged_smoke.py --exe build/sidecar/chengzhu-backend/chengzhu-backend.exe \
      [--frontend-dist frontend/dist] [--report reports/packaged_smoke.json]
Exit code 0 only when every check passes.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SMOKE_NONCE = "smoke-nonce-0123456789abcdef"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeOpenAI(BaseHTTPRequestHandler):
    """Minimal /v1/chat/completions (stream + non-stream) and /v1/models."""

    def log_message(self, *_args):  # quiet
        pass

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        self._json({"object": "list", "data": [{"id": "fake-model", "object": "model"}]})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        req = json.loads(self.rfile.read(length) or b"{}")
        text = "RAG 更适合频繁更新的知识，来源可追溯。微调适合固定风格。"
        if not req.get("stream"):
            self._json({
                "id": "c1", "object": "chat.completion", "model": "fake-model",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            })
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for piece in [text[i:i + 6] for i in range(0, len(text), 6)]:
            chunk = {"id": "c1", "object": "chat.completion.chunk", "model": "fake-model",
                     "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}]}
            self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()
            time.sleep(0.03)
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def http_json(url: str, method: str = "GET", body: dict | None = None, timeout: float = 10) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip().startswith(("{", "[")) else {"_text": raw}


def wait_ready(base: str, timeout: float) -> float:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            http_json(f"{base}/api/options", timeout=2)
            return time.time() - t0
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise TimeoutError("sidecar did not become ready")


def start(exe: Path, port: int, home: Path, frontend_dist: str) -> subprocess.Popen:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("PYTHON", "VIRTUAL_ENV", "CONDA"))}
    # No Python assumption: strip interpreter dirs from PATH for the sidecar.
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep) if "python" not in p.lower())
    env["CHENGZHU_HOME"] = str(home)
    env["CHENGZHU_INSTANCE_NONCE"] = SMOKE_NONCE
    if frontend_dist:
        env["CHENGZHU_FRONTEND_DIST"] = str(Path(frontend_dist).resolve())
    log = open(home / "sidecar-stdout.log", "ab")
    return subprocess.Popen([str(exe), "--port", str(port)], cwd=str(exe.parent), env=env, stdout=log, stderr=subprocess.STDOUT)


def stop(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


def ws_collect(port: int, ask_text: str, timeout: float = 40) -> list[dict]:
    import websocket  # websocket-client

    ws = websocket.create_connection(f"ws://127.0.0.1:{port}/ws", timeout=timeout)
    events: list[dict] = []
    http_json(f"http://127.0.0.1:{port}/api/ask", "POST", {"text": ask_text})
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            msg = json.loads(ws.recv())
        except Exception:  # noqa: BLE001
            break
        if msg.get("type") == "ping":
            ws.send(json.dumps({"type": "pong"}))
            continue
        events.append(msg)
        if msg.get("type") in {"answer_done", "answer_error"}:
            break
    ws.close()
    return events


def run_conversation_packaged_loop(base: str) -> dict[str, object]:
    """Exercise the real Conversation API through the packaged sidecar.

    This deliberately avoids microphone/OS-device assumptions. Audio transport
    has its own tests; this gate proves the packaged product/runtime contract
    and the persistence/truth boundaries that make Conversation Beta usable.
    """
    out: dict[str, object] = {}

    space = http_json(
        f"{base}/api/product/conversation/spaces",
        "POST",
        {
            "title": "Packaged Project Sync",
            "profile": "PROJECT_SYNC",
            "description": "Windows packaged Conversation Beta smoke",
            "default_goal": "确认 packaged Conversation continuity",
        },
    )
    space_id = str(space["id"])
    out["space_id"] = space_id
    out["space_profile"] = space.get("profile")

    goal = http_json(
        f"{base}/api/product/conversation/spaces/{space_id}/goals",
        "POST",
        {
            "title": "形成 packaged runtime 结论",
            "outcome_definition": "Decision 有 provenance；Open Thread 可延续；重启后仍存在",
            "priority": 90,
        },
    )
    out["goal_id"] = goal.get("id")

    session = http_json(
        f"{base}/api/product/conversation/spaces/{space_id}/sessions",
        "POST",
        {
            "title": "Packaged Project Sync #1",
            "goal_ids": [goal["id"]],
            "capture_mode": "NOTES_ONLY",
            "processing_mode": "LOCAL",
            "assistance_mode": "BALANCED",
            "consent_ack": True,
            "policy": {
                "screen_context": "OFF",
                "ai_assistance": "AI_ALLOWED",
                "human_assistance": "HUMAN_PRACTICE_ONLY",
                "share_privacy": "OFF",
                "external_writeback": "REVIEW_REQUIRED",
                "participant_consent_status": "NOT_APPLICABLE",
                "participant_transparency_plan": "NOT_APPLICABLE",
            },
        },
    )
    session_id = str(session["id"])
    out["session_id"] = session_id

    preflight = http_json(f"{base}/api/product/conversation/sessions/{session_id}/preflight")
    blockers = list(preflight.get("blockers") or [])
    out["preflight_blockers"] = blockers
    out["preflight_policy"] = preflight.get("policy")
    out["preflight_processing_runtime"] = preflight.get("processing_runtime")
    if blockers:
        raise AssertionError(f"Conversation packaged preflight blockers: {blockers}")

    started = http_json(f"{base}/api/product/conversation/sessions/{session_id}/start", "POST", {})
    pack = started.get("pack") or {}
    digest = str(pack.get("digest") or "")
    if not digest:
        raise AssertionError("Conversation Session Pack has no digest")
    out["pack_id"] = pack.get("id")
    out["pack_digest"] = digest
    payload = pack.get("payload") or {}
    out["pack_policy"] = payload.get("policy")
    out["pack_processing_runtime"] = payload.get("processing_runtime")
    if (payload.get("policy") or {}).get("share_privacy") != "OFF":
        raise AssertionError("Conversation packaged pack did not freeze Share Privacy OFF")

    decision = http_json(
        f"{base}/api/product/conversation/sessions/{session_id}/items",
        "POST",
        {
            "item_type": "Decision",
            "title": "packaged Conversation 使用 frozen Session Pack",
            "state": "PROPOSED",
            "source_refs": [
                {
                    "kind": "USER_NOTE",
                    "excerpt": "packaged smoke explicitly confirms the frozen Session Pack rule",
                    "visibility": "PRIVATE",
                }
            ],
            "source_excerpt": "packaged smoke explicitly confirms the frozen Session Pack rule",
            "confidence": 1.0,
            "epistemic_status": "OBSERVED",
        },
    )
    decision = http_json(
        f"{base}/api/product/conversation/items/{decision['id']}/review",
        "POST",
        {"action": "CONFIRM", "patch": {}},
    )
    out["decision"] = {
        "id": decision.get("id"),
        "state": decision.get("state"),
        "review_status": decision.get("review_status"),
        "source_refs": decision.get("source_refs"),
    }
    if decision.get("state") != "AGREED" or not decision.get("source_refs"):
        raise AssertionError("Conversation Decision did not become sourced AGREED truth")

    question = http_json(
        f"{base}/api/product/conversation/sessions/{session_id}/items",
        "POST",
        {
            "item_type": "OpenQuestion",
            "title": "packaged restart 后 continuity 是否仍存在？",
            "state": "PROPOSED",
            "source_refs": [
                {
                    "kind": "USER_NOTE",
                    "excerpt": "packaged continuity must survive restart",
                    "visibility": "PRIVATE",
                }
            ],
            "confidence": 1.0,
            "epistemic_status": "OBSERVED",
        },
    )
    question = http_json(
        f"{base}/api/product/conversation/items/{question['id']}/review",
        "POST",
        {"action": "CONFIRM", "patch": {}},
    )
    out["open_question"] = {
        "id": question.get("id"),
        "review_status": question.get("review_status"),
    }

    detail = http_json(f"{base}/api/product/conversation/spaces/{space_id}")
    threads = list(detail.get("threads") or [])
    out["open_threads"] = [
        {"id": t.get("id"), "status": t.get("status"), "text": t.get("text")}
        for t in threads
    ]
    if not any(t.get("status") == "OPEN" and question["id"] in json.dumps(t.get("source_refs") or []) for t in threads):
        raise AssertionError("reviewed OpenQuestion did not project to a sourced Open Thread")

    guidance = http_json(
        f"{base}/api/product/conversation/sessions/{session_id}/guidance/evaluate",
        "POST",
        {
            "candidate_text": "提醒这场使用 frozen Session Pack，并确认 restart continuity",
            "source_refs": [
                {
                    "kind": "USER_NOTE",
                    "excerpt": "packaged smoke verified source",
                    "visibility": "PRIVATE",
                }
            ],
            "relevance": 1.0,
            "novelty": 1.0,
            "provenance_strength": 1.0,
            "goal_relevance": 1.0,
            "decision_impact": 1.0,
        },
    )
    event = guidance.get("guidance")
    if not event:
        raise AssertionError(f"Conversation deterministic Guidance suppressed unexpectedly: {guidance}")
    out["guidance"] = {
        "kind": event.get("kind"),
        "expression_action": event.get("expression_action"),
        "reason": event.get("reason"),
        "source_refs": event.get("source_refs"),
    }

    ended = http_json(f"{base}/api/product/conversation/sessions/{session_id}/end", "POST", {})
    out["continue_review_required"] = ended.get("review_required")
    out["continue_next_focus"] = ended.get("next_focus")
    if not any(x.get("id") == decision["id"] for x in ended.get("decisions") or []):
        raise AssertionError("confirmed Decision missing from Continue")
    if not any(x.get("id") == question["id"] for x in ended.get("open_questions") or []):
        raise AssertionError("reviewed OpenQuestion missing from Continue")

    history = http_json(f"{base}/api/product/conversation/history?limit=20")
    history_items = list(history.get("items") or [])
    out["history_count"] = len(history_items)
    if not any(x.get("id") == session_id and x.get("space_id") == space_id for x in history_items):
        raise AssertionError("ended Conversation session missing from Conversation History")

    exported = http_json(f"{base}/api/product/conversation/spaces/{space_id}/export")
    out["export_keys"] = sorted(exported.keys())
    serialized_export = json.dumps(exported, ensure_ascii=False)
    if str(decision["id"]) not in serialized_export or str(question["id"]) not in serialized_export:
        raise AssertionError("Conversation export lost reviewed truth/provenance")

    retention = http_json(f"{base}/api/product/conversation/spaces/{space_id}/retention")
    out["retention_policy"] = retention.get("policy")
    out["retention_would_delete"] = retention.get("would_delete")

    return out


def markdown_report(results: dict[str, object]) -> str:
    checks = results.get("checks") if isinstance(results.get("checks"), dict) else {}
    checks = checks if isinstance(checks, dict) else {}
    conversation = checks.get("conversation_packaged_loop")
    conversation = conversation if isinstance(conversation, dict) else {}

    def mark(value: object) -> str:
        return "PASS" if bool(value) else "FAIL"

    decision = conversation.get("decision")
    decision = decision if isinstance(decision, dict) else {}
    guidance = conversation.get("guidance")
    guidance = guidance if isinstance(guidance, dict) else {}
    lines = [
        "# Chengzhu Packaged Runtime Evidence",
        "",
        "> Generated by `scripts/packaged_smoke.py` against the built sidecar executable.",
        "",
        f"**Overall**: {mark(results.get('passed'))}",
        "",
        "## Interview packaged contract",
        "",
        f"- Fresh first run: {mark(checks.get('fresh_first_run_ok'))}",
        f"- Share Privacy default OFF: {mark(checks.get('config_share_privacy_default') == 'OFF')}",
        f"- Fast Cue before Deep: {mark(checks.get('fast_cue_before_deep'))}",
        f"- InterviewPack persists after restart: {mark(checks.get('pack_persisted_after_restart'))}",
        "",
        "## Conversation Beta packaged contract",
        "",
        f"- product.db schema: {checks.get('product_schema_version')} / expected {checks.get('product_schema_expected')}",
        f"- Space: `{conversation.get('space_id') or '—'}` ({conversation.get('space_profile') or '—'})",
        f"- Session: `{conversation.get('session_id') or '—'}`",
        f"- Session Pack digest: `{conversation.get('pack_digest') or '—'}`",
        f"- Preflight blockers: {len(conversation.get('preflight_blockers') or [])}",
        f"- Reviewed Decision: {decision.get('state') or '—'} / {decision.get('review_status') or '—'}",
        f"- Open Threads: {len(conversation.get('open_threads') or [])}",
        f"- Guidance: {guidance.get('kind') or '—'} / {guidance.get('reason') or '—'}",
        f"- Conversation History after end: {conversation.get('history_count') or 0}",
        f"- Conversation persists after restart: {mark(checks.get('conversation_persisted_after_restart'))}",
        "",
        "## Packaging / isolation",
        "",
        f"- Frontend served from packaged runtime: {mark(checks.get('frontend_served'))}",
        f"- Install directory unchanged: {mark(checks.get('install_dir_unchanged'))}",
        f"- LICENSE bundled: {mark(checks.get('license_bundled'))}",
        "",
        "## Evidence boundary",
        "",
        "This artifact proves packaged sidecar/runtime integration under an isolated CHENGZHU_HOME.",
        "It does **not** prove:",
        "",
        "- stable/public v2 release;",
        "- real microphone or loopback capture on end-user hardware;",
        "- installer/portable clean-install + download-back provenance;",
        "- real-user usefulness, precision, cognitive-load reduction, or PMF.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--frontend-dist", default="")
    ap.add_argument("--report", default="")
    ap.add_argument("--markdown-report", default="")
    ap.add_argument("--resources", default="", help="packaged resources dir to check bundled license files")
    args = ap.parse_args()

    exe = Path(args.exe).resolve()
    results: dict[str, object] = {"exe": str(exe), "checks": {}}
    checks: dict[str, object] = results["checks"]  # type: ignore[assignment]
    install_before = {p.name for p in exe.parent.iterdir()}
    home = Path(tempfile.mkdtemp(prefix="chengzhu-smoke-"))
    fake_port = free_port()
    fake = ThreadingHTTPServer(("127.0.0.1", fake_port), FakeOpenAI)
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    (home / "config").mkdir(parents=True, exist_ok=True)
    (home / "config" / "config.json").write_text(json.dumps({
        "models": [{"name": "Fake", "api_base_url": f"http://127.0.0.1:{fake_port}/v1", "api_key": "test-key-not-real",
                    "model": "fake-model", "enabled": True, "supports_think": False, "supports_vision": False}],
        "active_model": 0,
        "resume_text": "",
    }, ensure_ascii=False), encoding="utf-8")

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    ok = True

    # Fresh first run: no config at all, the exact state of a new user. The
    # sidecar prints Chinese while creating the config; v1.2.0 crashed here
    # on a cp1252 (non-Chinese) Windows locale.
    fresh_home = Path(tempfile.mkdtemp(prefix="chengzhu-smoke-fresh-"))
    fresh = start(exe, port, fresh_home, args.frontend_dist)
    try:
        checks["fresh_first_run_seconds"] = round(wait_ready(base, 120), 2)
        checks["fresh_first_run_ok"] = http_json(f"{base}/api/instance").get("app") == "chengzhu"
    except Exception as exc:  # noqa: BLE001
        checks["fresh_first_run_ok"] = False
        log_tail = (fresh_home / "sidecar-stdout.log").read_text(encoding="utf-8", errors="replace")[-800:] if (fresh_home / "sidecar-stdout.log").exists() else ""
        checks["fresh_first_run_error"] = f"{type(exc).__name__}: {exc} | {log_tail}"
    finally:
        stop(fresh)
    ok &= bool(checks.get("fresh_first_run_ok"))
    shutil.rmtree(fresh_home, ignore_errors=True)

    proc = start(exe, port, home, args.frontend_dist)
    try:
        checks["cold_start_seconds"] = round(wait_ready(base, 120), 2)
        checks["options"] = bool(http_json(f"{base}/api/options"))
        inst = http_json(f"{base}/api/instance")
        checks["instance_nonce_echo"] = inst.get("app") == "chengzhu" and inst.get("nonce") == SMOKE_NONCE
        ok &= bool(checks["instance_nonce_echo"])
        cfg = http_json(f"{base}/api/config")
        checks["config_share_privacy_default"] = cfg.get("share_privacy_mode")
        ok &= cfg.get("share_privacy_mode") == "OFF"
        ver = subprocess.run([str(exe), "--version"], capture_output=True, text=True, timeout=60)
        checks["version"] = ver.stdout.strip()
        expected_version = json.loads((Path(__file__).resolve().parents[1] / "desktop" / "package.json").read_text(encoding="utf-8"))["version"]
        checks["version_expected"] = expected_version
        ok &= ver.stdout.strip() == expected_version

        db = home / "data" / "intelligence.db"
        user_version = sqlite3.connect(db).execute("PRAGMA user_version").fetchone()[0] if db.exists() else None
        checks["intelligence_schema_version"] = user_version
        migrations_source = (Path(__file__).resolve().parents[1] / "backend" / "services" / "storage" / "intelligence_migrations.py").read_text(encoding="utf-8")
        import re
        version_match = re.search(r"^LATEST_SCHEMA_VERSION\s*=\s*(\d+)", migrations_source, re.MULTILINE)
        expected_schema = int(version_match.group(1)) if version_match else None
        checks["intelligence_schema_expected"] = expected_schema
        ok &= expected_schema is not None and user_version == expected_schema

        conversation = run_conversation_packaged_loop(base)
        checks["conversation_packaged_loop"] = conversation

        product_db = home / "data" / "product.db"
        product_version = sqlite3.connect(product_db).execute("PRAGMA user_version").fetchone()[0] if product_db.exists() else None
        checks["product_schema_version"] = product_version
        product_migrations = (Path(__file__).resolve().parents[1] / "backend" / "services" / "storage" / "product_migrations.py").read_text(encoding="utf-8")
        product_version_match = re.search(r"^LATEST_SCHEMA_VERSION\s*=\s*(\d+)", product_migrations, re.MULTILINE)
        expected_product_schema = int(product_version_match.group(1)) if product_version_match else None
        checks["product_schema_expected"] = expected_product_schema
        ok &= expected_product_schema is not None and product_version == expected_product_schema

        if args.frontend_dist:
            with urllib.request.urlopen(f"{base}/", timeout=10) as resp:
                html = resp.read().decode("utf-8", "replace")
            checks["frontend_served"] = "<div id=\"root\"" in html or "<!doctype html" in html.lower()
            ok &= bool(checks["frontend_served"])

        events = ws_collect(port, "RAG 和微调怎么选")
        types = [e.get("type") for e in events]
        checks["ws_event_types"] = types
        cue_ok = "guidance_fast" in types and "answer_chunk" in types and types.index("guidance_fast") < types.index("answer_chunk")
        checks["fast_cue_before_deep"] = cue_ok
        done = next((e for e in events if e.get("type") == "answer_done"), {})
        checks["answer_done_latency"] = done.get("latency")
        ok &= cue_ok and bool(done)

        pack = http_json(f"{base}/api/intelligence/pack/freeze", "POST", {"share_privacy_policy": "OFF"})
        checks["pack_frozen_id"] = pack.get("id")
        stop(proc)

        proc = start(exe, port, home, args.frontend_dist)
        checks["restart_seconds"] = round(wait_ready(base, 120), 2)
        after = http_json(f"{base}/api/intelligence/pack")
        checks["pack_persisted_after_restart"] = bool(after.get("frozen")) and after["pack"]["id"] == pack.get("id")
        ok &= bool(checks["pack_persisted_after_restart"])

        conv_after = http_json(f"{base}/api/product/conversation/history?limit=20")
        conv_ids = [x.get("id") for x in conv_after.get("items") or []]
        conversation_session_id = str((checks.get("conversation_packaged_loop") or {}).get("session_id") or "")
        checks["conversation_persisted_after_restart"] = conversation_session_id in conv_ids
        ok &= bool(checks["conversation_persisted_after_restart"])
    except Exception as exc:  # noqa: BLE001
        checks["error"] = f"{type(exc).__name__}: {exc}"
        ok = False
    finally:
        stop(proc)
        fake.shutdown()

    install_after = {p.name for p in exe.parent.iterdir()}
    checks["install_dir_unchanged"] = install_before == install_after
    ok &= bool(checks["install_dir_unchanged"])
    checks["user_data_layout"] = sorted(p.name for p in home.iterdir())
    if args.resources:
        res = Path(args.resources)
        checks["license_bundled"] = (res / "LICENSE").is_file() and (res / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")
        checks["third_party_notices_bundled"] = (res / "THIRD_PARTY_NOTICES.md").is_file()
        ok &= bool(checks["license_bundled"]) and bool(checks["third_party_notices_bundled"])
    else:
        internal = exe.parent / "_internal"
        checks["license_bundled"] = (internal / "LICENSE").is_file()
        ok &= bool(checks["license_bundled"])

    results["passed"] = bool(ok)
    text = json.dumps(results, ensure_ascii=False, indent=2)
    print(text)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(text, encoding="utf-8")
    if args.markdown_report:
        Path(args.markdown_report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown_report).write_text(markdown_report(results), encoding="utf-8")
    shutil.rmtree(home, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
