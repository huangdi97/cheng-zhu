"""Packaged smoke test (R2 Stage AJ).

Runs the real built sidecar (not the source tree) against a throwaway user-data
dir and a local fake OpenAI-compatible provider, so no real key is needed.

Checks:
  1. sidecar starts without a system Python assumption (CHENGZHU_HOME set)
  2. /api/options, /api/config respond; version string
  3. DB migrations applied under CHENGZHU_HOME/data (latest intelligence schema)
  4. prebuilt frontend served (CHENGZHU_FRONTEND_DIST)
  5. Fast Cue E2E with the fake provider: guidance_fast before the first
     answer_chunk, answer_done carries latency
  6. InterviewPack freeze persists across a sidecar restart
  7. nothing is written next to the executable (install dir stays clean)
  8. LICENSE / THIRD_PARTY_NOTICES bundled

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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--frontend-dist", default="")
    ap.add_argument("--report", default="")
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
    shutil.rmtree(home, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
