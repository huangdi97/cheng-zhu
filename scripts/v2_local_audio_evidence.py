"""Real-device audio/ASR evidence for the v2 closure (local whisper STT only).

Runs on this machine, against real capture devices, with no remote STT provider:

  1. device enumeration through the real backend (``GET /api/devices``);
  2. the Conversation capture lifecycle over real HTTP: start / pause / resume /
     stop, rapid start-stop, and a second-session switch that must prove the
     transport was released and no stale session owner survived;
  3. the repository's own loopback audio validation suite
     (``backend/scripts/run_audio_validation_suite.py``) against the default
     output loopback device, which plays the real latency corpus and checks that
     the last ASR segment is not lost (segment-drop counters).

Usage:
  python scripts/v2_local_audio_evidence.py --out artifacts/runtime-evidence/<dir>/audio.json
Exit code 0 only when the lifecycle checks pass; the suite JSON is always recorded.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
API = "/api/product/conversation"


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
        raise RuntimeError(f"{method} {path} -> {error.code}: {error.read().decode('utf-8', 'ignore')[:400]}") from None
    return json.loads(payload) if payload.strip() else {}


def write_config(home: Path) -> None:
    (home / "config").mkdir(parents=True, exist_ok=True)
    (home / "config" / "config.json").write_text(
        json.dumps(
            {
                "models": [],
                "active_model": 0,
                "stt_provider": "whisper",
                "whisper_model": "base",
                "whisper_language": "zh",
                "ai_policy_mode": "AI_ALLOWED",
                "onboarding_completed": True,
            }
        ),
        encoding="utf-8",
    )


def child_env(home: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith(("CHENGZHU_", "IA_"))}
    env["CHENGZHU_HOME"] = str(home)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def extract_json_objects(text: str) -> list[dict]:
    """Return every JSON object found in ``text`` (the suite logs and prints more than one)."""
    decoder = json.JSONDecoder()
    objects: list[dict] = []
    if not text:
        return objects
    index = text.find("{")
    while index != -1:
        try:
            value, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            index = text.find("{", index + 1)
            continue
        if isinstance(value, dict):
            objects.append(value)
        index = text.find("{", index + max(end, 1))
    return objects


def suite_summary_from(stdout: str) -> dict:
    """The suite's final summary object, preferring the one carrying ``summary``."""
    objects = extract_json_objects(stdout)
    if not objects:
        return {}
    return next((item for item in reversed(objects) if "summary" in item), objects[-1])


def start_backend(port: int, home: Path) -> subprocess.Popen:
    write_config(home)
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(BACKEND),
        env=child_env(home),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    deadline = time.time() + 120
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"backend exited early ({process.returncode}): {(process.stdout.read() if process.stdout else '')[-1500:]}")
        try:
            http(f"http://127.0.0.1:{port}", "GET", "/api/options", timeout=5)
            return process
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("backend did not become ready")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="")
    parser.add_argument("--preflight-repeats", type=int, default=3)
    parser.add_argument("--replay-repeats", type=int, default=1)
    args = parser.parse_args()

    report: dict[str, Any] = {
        "evidence_type": "LOCAL_REAL_DEVICE_AUDIO",
        "stt_provider": "whisper (local, no remote STT)",
        "assertions": [],
        "passed": False,
    }

    def check(name: str, condition: bool, detail: Any = None) -> None:
        report["assertions"].append({"name": name, "ok": bool(condition), "detail": detail})

    with tempfile.TemporaryDirectory(prefix="cz-audio-") as tmp:
        home = Path(tmp)
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        process = start_backend(port, home)
        try:
            # ---- 1. device enumeration -------------------------------------
            devices = http(base, "GET", "/api/devices")
            rows = devices.get("devices", [])
            loopbacks = [row for row in rows if row.get("is_loopback")]
            mics = [row for row in rows if row.get("category") == "microphone"]
            report["devices"] = {
                "count": len(rows),
                "loopback": [{"id": r["id"], "name": r["name"], "is_default_output": r.get("is_default_output")} for r in loopbacks],
                "microphone_count": len(mics),
                "microphone_sample": [{"id": r["id"], "name": r["name"]} for r in mics[:4]],
            }
            check("devices_enumerated", len(rows) > 0, len(rows))
            check("loopback_device_present", bool(loopbacks), report["devices"]["loopback"])
            check("microphone_present", bool(mics), len(mics))
            loopback_id = next((row["id"] for row in loopbacks if row.get("is_default_output")), None)
            if loopback_id is None and loopbacks:
                loopback_id = loopbacks[0]["id"]
            report["loopback_device_id"] = loopback_id

            # ---- 2. Conversation capture lifecycle --------------------------
            space = http(base, "POST", f"{API}/spaces", {"title": "Audio closure space", "profile": "PROJECT_SYNC"})
            space_id = space["id"]

            def new_session(title: str) -> str:
                return http(
                    base,
                    "POST",
                    f"{API}/spaces/{space_id}/sessions",
                    {
                        "title": title,
                        "consent_ack": True,
                        "capture_mode": "TRANSCRIPT",
                        "processing_mode": "LOCAL",
                        "policy": {
                            "transcript_mode": "TEXT_ONLY",
                            "ai_policy": "AI_ALLOWED",
                            "transcript_consent": "NOT_APPLICABLE",
                        },
                    },
                )["id"]

            first = new_session("Audio session A")
            preflight = http(base, "GET", f"{API}/sessions/{first}/preflight")
            check("audio_preflight_has_no_blockers", not preflight.get("blockers"), preflight.get("blockers"))
            http(base, "POST", f"{API}/sessions/{first}/start")

            started = http(base, "POST", f"{API}/sessions/{first}/capture/start", {"device_id": int(loopback_id)})
            report["capture_start"] = started
            time.sleep(4)
            status_active = http(base, "GET", f"{API}/sessions/{first}/capture")
            report["capture_active_status"] = status_active
            paused = http(base, "POST", f"{API}/sessions/{first}/capture/pause")
            report["capture_paused"] = paused
            time.sleep(1)
            resumed = http(base, "POST", f"{API}/sessions/{first}/capture/resume")
            report["capture_resumed"] = resumed
            time.sleep(3)

            # a second session must not be able to steal the live transport
            second = new_session("Audio session B")
            http(base, "POST", f"{API}/sessions/{second}/start")
            steal_error = ""
            try:
                http(base, "POST", f"{API}/sessions/{second}/capture/start", {"device_id": int(loopback_id)})
            except RuntimeError as error:
                steal_error = str(error)
            report["cross_session_steal"] = steal_error[:400]
            check("live_capture_cannot_be_stolen_by_another_session", bool(steal_error), steal_error[:200])

            stopped = http(base, "POST", f"{API}/sessions/{first}/capture/stop")
            report["capture_stop"] = stopped
            stopped_again = http(base, "POST", f"{API}/sessions/{first}/capture/stop")
            report["capture_stop_again"] = stopped_again
            check("stop_is_idempotent", True, "second stop returned without deadlock")

            # after A stopped, B must be able to own the transport (no zombie owner)
            takeover = http(base, "POST", f"{API}/sessions/{second}/capture/start", {"device_id": int(loopback_id)})
            report["transport_released_after_stop"] = takeover
            check("transport_released_after_stop", bool(takeover), takeover)
            http(base, "POST", f"{API}/sessions/{second}/capture/stop")

            # rapid start/stop must not deadlock
            rapid: list[Any] = []
            started_at = time.time()
            for _ in range(3):
                rapid.append(http(base, "POST", f"/api/product/conversation/sessions/{first}/capture/start", {"device_id": int(loopback_id)}))
                rapid.append(http(base, "POST", f"/api/product/conversation/sessions/{first}/capture/stop"))
            elapsed = time.time() - started_at
            report["rapid_start_stop"] = {"rounds": 3, "elapsed_sec": round(elapsed, 2)}
            check("rapid_start_stop_no_deadlock", elapsed < 90, round(elapsed, 2))

            transcript = http(base, "GET", f"{API}/sessions/{first}/transcript")
            report["transcript_after_lifecycle"] = {
                "segments": len(transcript.get("items", [])),
                "sample": [item.get("text", "")[:60] for item in (transcript.get("items") or [])[:3]],
            }
        finally:
            process.terminate()
            try:
                report["backend_log_tail"] = (process.communicate(timeout=30)[0] or "")[-1500:]
            except subprocess.TimeoutExpired:
                process.kill()

        # ---- 3. repository loopback STT validation suite --------------------
        if report.get("loopback_device_id") is not None:
            suite_home = home if home.exists() else Path(tmp)
            write_config(suite_home)
            suite = subprocess.run(
                [
                    sys.executable, "-m", "scripts.run_audio_validation_suite",
                    "--device-id", str(int(report["loopback_device_id"])),
                    "--preflight-repeats", str(args.preflight_repeats),
                    "--replay-repeats", str(args.replay_repeats),
                ],
                cwd=str(BACKEND),
                env=child_env(suite_home),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=1800,
            )
            parsed = suite_summary_from(suite.stdout)
            if not parsed:
                parsed = {"raw_stdout_tail": suite.stdout[-2000:], "stderr_tail": suite.stderr[-2000:]}
            report["audio_validation_suite"] = parsed
            report["audio_validation_suite_exit"] = suite.returncode
            summary = parsed.get("summary", {}) if isinstance(parsed, dict) else {}
            check("audio_suite_ran", suite.returncode in (0, 2), suite.returncode)
            check("audio_suite_no_segment_drop", summary.get("max_segment_dropped", None) == 0, summary.get("max_segment_dropped"))
            check("audio_suite_preflight_all_succeeded", summary.get("preflight_failure_count", None) == 0, summary)

    report["passed"] = all(item["ok"] for item in report["assertions"])
    text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    failed = [item["name"] for item in report["assertions"] if not item["ok"]]
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
