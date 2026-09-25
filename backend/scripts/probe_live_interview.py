"""Probe the real system-audio -> streaming STT -> auto-answer chain.

This script talks to a running backend.  It starts an interview on the chosen
loopback device, plays the built-in spoken fixture through the normal API, and
records milestone latency from WebSocket events.  It always stops the session.

Usage:
    python -m scripts.probe_live_interview --device-id 20001
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

import aiohttp

from api.assist.sound_test import play_audio_fixture


MILESTONE_EVENTS = {
    "interviewer_transcription_partial": "first_partial_ms",
    "transcription": "final_transcript_ms",
    "question_parse_status": "question_parse_ms",
    "answer_start": "answer_start_ms",
    "answer_chunk": "answer_first_chunk_ms",
    "answer_done": "answer_done_ms",
    "answer_error": "answer_error_ms",
}


async def probe(
    base_url: str,
    device_id: int,
    timeout_sec: float,
    *,
    audio_path: str | None = None,
) -> dict[str, Any]:
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
    result: dict[str, Any] = {
        "ok": False,
        "stt_parse_ok": False,
        "answer_ok": False,
        "device_id": int(device_id),
        "milestones": {},
        "events": [],
        "transcript": "",
        "answer_preview": "",
        "terminal": "timeout",
        "expected_answers": 0,
        "answer_done_count": 0,
        "answer_error_count": 0,
        "audio_path": audio_path or "built-in preflight phrase",
    }
    started = 0.0

    async with aiohttp.ClientSession() as session:
        ws = await session.ws_connect(ws_url, heartbeat=20)
        try:
            await ws.receive_json(timeout=5)
            start_response = await session.post(
                f"{base_url}/api/start",
                json={"device_id": int(device_id)},
            )
            if start_response.status != 200:
                result["terminal"] = f"start_http_{start_response.status}"
                result["detail"] = (await start_response.text())[:300]
                return result

            await asyncio.sleep(0.8)
            started = time.monotonic()
            # The public output-test endpoint intentionally rejects playback
            # during an active interview.  The probe owns both sides of this
            # controlled test, so play the same built-in fixture locally while
            # the backend captures the selected loopback device.
            playback_task = asyncio.create_task(asyncio.to_thread(play_audio_fixture, audio_path))

            deadline = time.monotonic() + max(5.0, float(timeout_sec))
            while time.monotonic() < deadline:
                remaining = max(0.1, deadline - time.monotonic())
                try:
                    message = await ws.receive(timeout=remaining)
                except asyncio.TimeoutError:
                    break
                if message.type != aiohttp.WSMsgType.TEXT:
                    if message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
                        result["terminal"] = "websocket_closed"
                        break
                    continue
                event = json.loads(message.data)
                event_type = str(event.get("type") or "")
                elapsed_ms = int((time.monotonic() - started) * 1000)
                milestone = MILESTONE_EVENTS.get(event_type)
                if milestone and milestone not in result["milestones"]:
                    # Assembling statuses are useful but are not the semantic
                    # parse completion milestone.
                    if event_type != "question_parse_status" or event.get("stage") == "parsed":
                        result["milestones"][milestone] = elapsed_ms
                if event_type in MILESTONE_EVENTS or event_type in {"recording", "stt_fallback", "error"}:
                    result["events"].append({
                        "type": event_type,
                        "at_ms": elapsed_ms,
                        "stage": event.get("stage"),
                        "message": event.get("message"),
                    })
                if event_type == "transcription":
                    result["transcript"] = str(event.get("text") or "")
                elif event_type == "interviewer_transcription_partial" and not result.get("first_partial"):
                    result["first_partial"] = str(event.get("text") or "")
                elif event_type == "question_parse_status" and event.get("stage") == "parsed":
                    clusters = event.get("clusters") or []
                    result["expected_answers"] = max(result["expected_answers"], len(clusters))
                    result["question_parse"] = {
                        "clusters": clusters,
                        "needs_confirmation": bool(event.get("needs_confirmation")),
                        "ignored": event.get("ignored") or [],
                    }
                elif event_type == "answer_chunk" and not result["answer_preview"]:
                    result["answer_preview"] = str(event.get("chunk") or "")[:160]
                elif event_type == "answer_done":
                    result["answer_done_count"] += 1
                    expected = max(1, result["expected_answers"])
                    if result["answer_done_count"] + result["answer_error_count"] >= expected:
                        result["terminal"] = "answer_done"
                        break
                elif event_type == "answer_error":
                    result["answer_error_count"] += 1
                    result["detail"] = str(event.get("message") or "")
                    expected = max(1, result["expected_answers"])
                    if result["answer_done_count"] + result["answer_error_count"] >= expected:
                        result["terminal"] = "answer_error"
                        break
                elif event_type == "error":
                    result["terminal"] = "error"
                    result["detail"] = str(event.get("message") or "")
                    break
            result["playback_elapsed_sec"] = await playback_task
        finally:
            try:
                try:
                    await session.post(f"{base_url}/api/stop", json={})
                except Exception as exc:  # preserve the primary probe result
                    result["stop_error"] = str(exc)
            finally:
                await ws.close()

    result["stt_parse_ok"] = bool(
        result["transcript"] and result["milestones"].get("question_parse_ms")
    )
    result["answer_ok"] = bool(
        result["expected_answers"]
        and result["answer_done_count"] == result["expected_answers"]
        and not result["answer_error_count"]
    )
    # `ok` describes the locally testable audio/STT/parse chain.  Keep the
    # external answer-provider outcome separate so an account or quota error
    # can never be mistaken for a full end-to-end pass.
    result["ok"] = result["stt_parse_ok"]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe the real live interview chain.")
    parser.add_argument("--device-id", type=int, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--timeout-sec", type=float, default=45.0)
    parser.add_argument("--audio-path", default="", help="Optional WAV file to play through the selected loopback device.")
    args = parser.parse_args(argv)
    result = asyncio.run(probe(
        args.base_url.rstrip("/"),
        args.device_id,
        args.timeout_sec,
        audio_path=args.audio_path or None,
    ))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
