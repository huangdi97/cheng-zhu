"""实时听写（真流式）：边采边把 200ms 音频块发给豆包流式 ASR，实时显示部分结果。

关键点：检测到说话（VAD）才连接豆包，避免点击后停顿导致会话空转失效。
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Any

import numpy as np

from core.config import get_config
from core.logger import get_logger
from services.stt import get_stt_engine
from services.stt.engines import (
    DOUBAO_ASR_WS_URL,
    MSG_ERROR,
    MSG_FULL_SERVER_RESPONSE,
    _build_ws_frame_audio,
    _build_ws_frame_full_request,
    _parse_ws_response,
)
from services.stt.engines import DoubaoSTT

logger = get_logger("live_listen")

_LOCK = threading.Lock()
_STREAM_LOCK = threading.Lock()
_STATE: dict[str, Any] = {
    "active": False,
    "device_id": None,
    "capture_rate": 16000,
    "started_at": 0.0,
    "silence_sec": 1.2,
    "max_seconds": 60.0,
    "vad_threshold": 0.001,
    "partial_text": "",
    "final_text": "",
    "heard_speech": False,
    "last_level": 0.0,
    "done": False,
    "stop_event": None,
    "send_queue": None,
    "ws": None,
    "threads": [],
}


def _reset_state() -> None:
    _STATE.update({
        "active": True,
        "device_id": None,
        "capture_rate": 16000,
        "started_at": time.time(),
        "silence_sec": 1.2,
        "max_seconds": 60.0,
        "vad_threshold": 0.005,
        "partial_text": "",
        "final_text": "",
        "heard_speech": False,
        "done": False,
        "stop_event": threading.Event(),
        "send_queue": queue.Queue(maxsize=1000),
        "ws": None,
        "threads": [],
    })


def _resample_chunk(a: np.ndarray, rate: int) -> np.ndarray:
    if rate == 16000 or len(a) == 0:
        return a.astype(np.int16)
    n_out = max(1, int(len(a) * 16000 / rate))
    xs = np.linspace(0, max(0, len(a) - 1), n_out)
    return np.interp(xs, np.arange(len(a)), a.astype(np.float64)).astype(np.int16)


def _open_doubao_ws():
    engine = get_stt_engine()
    if not isinstance(engine, DoubaoSTT):
        raise RuntimeError("实时听写需要豆包 ASR 引擎，请在 config.json 中设置 stt_provider=doubao")
    app_key = engine.app_id or engine.access_token or engine.api_key
    boosting = engine.boosting_table_id or ""
    headers = [f"{k}: {v}" for k, v in engine._build_headers().items()]
    import websocket as _ws

    conn = _ws.create_connection(DOUBAO_ASR_WS_URL, header=headers, timeout=10)
    conn.send_binary(_build_ws_frame_full_request(app_key, boosting, language="zh-CN"))
    time.sleep(0.02)
    return conn


def _reader_loop(ws) -> None:
    ws.settimeout(15)
    while not _STATE["stop_event"].is_set():
        try:
            raw = ws.recv()
        except Exception:
            break
        if raw is None:
            break
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        msg_type, payload = _parse_ws_response(raw)
        if msg_type == MSG_ERROR:
            break
        if msg_type == MSG_FULL_SERVER_RESPONSE and payload:
            res = payload.get("result") or {}
            text = (res.get("text") or "").strip()
            if text:
                _STATE["partial_text"] = text
    _STATE["done"] = True


def _sender_loop(ws) -> None:
    q = _STATE["send_queue"]
    while not _STATE["stop_event"].is_set():
        try:
            chunk = q.get(timeout=0.2)
        except queue.Empty:
            continue
        if chunk is None:
            break
        try:
            ws.send_binary(_build_ws_frame_audio(chunk, is_last=False))
        except Exception:
            break
    while True:
        try:
            chunk = q.get_nowait()
        except queue.Empty:
            break
        if chunk is None:
            continue
        try:
            ws.send_binary(_build_ws_frame_audio(chunk, is_last=False))
        except Exception:
            break
    try:
        ws.send_binary(_build_ws_frame_audio(b"", is_last=True))
    except Exception:
        pass


def _ensure_stream_locked() -> bool:
    """打开豆包 WS 并启动 sender/reader（仅一次）。"""
    with _STREAM_LOCK:
        if _STATE["ws"] is not None:
            return True
        try:
            ws = _open_doubao_ws()
        except Exception as e:
            logger.warning("open doubao ws failed: %s", e)
            return False
        _STATE["ws"] = ws
        sender = threading.Thread(target=_sender_loop, args=(ws,), daemon=True)
        reader = threading.Thread(target=_reader_loop, args=(ws,), daemon=True)
        _STATE["threads"].extend([sender, reader])
        sender.start()
        reader.start()
        return True


def _capture_loop(device_id: int) -> None:
    import sounddevice as sd

    info = sd.query_devices(device_id, "input")
    rate = int(info.get("default_samplerate") or 48000)
    _STATE["capture_rate"] = rate
    _STATE["started_at"] = time.time()
    block = max(1, int(rate * 0.2))
    noise_floor = 20.0
    silence_blocks = 0
    silence_limit = max(1, int(_STATE["silence_sec"] * rate / block))
    started = time.time()

    def _cb(indata, _frames, _time_info, _status):
        nonlocal silence_blocks, noise_floor
        a = np.asarray(indata[:, 0], dtype=np.int16)
        rms = float(np.sqrt(np.mean(a.astype(np.float64) ** 2))) if len(a) else 0.0
        _STATE["last_level"] = rms
        if not _STATE["heard_speech"] and rms < 300:
            noise_floor = 0.9 * noise_floor + 0.1 * rms
        threshold_now = max(noise_floor * 2.5, 10.0)
        if rms > threshold_now:
            _STATE["heard_speech"] = True
            silence_blocks = 0
        elif _STATE["heard_speech"]:
            silence_blocks += 1
        if _STATE["heard_speech"]:
            chunk16 = _resample_chunk(a, rate)
            if len(chunk16) > 0:
                try:
                    _STATE["send_queue"].put_nowait(chunk16.tobytes())
                except queue.Full:
                    pass
        if _STATE["heard_speech"] and silence_blocks >= silence_limit:
            _STATE["stop_event"].set()

    with sd.InputStream(
        samplerate=rate, channels=1, dtype="int16",
        device=device_id, blocksize=block, callback=_cb,
    ):
        while not _STATE["stop_event"].is_set() and time.time() - started < _STATE["max_seconds"]:
            if _STATE["heard_speech"]:
                _ensure_stream_locked()
            time.sleep(0.1)


def start(device_id: int, max_seconds: float = 60.0, silence_sec: float = 1.2) -> dict[str, Any]:
    with _LOCK:
        if _STATE["active"]:
            return {"ok": False, "error": "已有听写会话在进行中，请先停止"}
        _reset_state()
        _STATE["device_id"] = device_id
        _STATE["max_seconds"] = max(5.0, min(float(max_seconds or 60.0), 120.0))
        _STATE["silence_sec"] = max(0.5, min(float(silence_sec or 1.2), 5.0))
        capture = threading.Thread(target=_capture_loop, args=(device_id,), daemon=True)
        _STATE["threads"] = [capture]
        capture.start()
        return {"ok": True, "listening": True}


def status() -> dict[str, Any]:
    with _LOCK:
        return {
            "active": _STATE["active"],
            "done": _STATE["done"],
            "partial_text": _STATE["partial_text"],
            "final_text": _STATE["final_text"],
            "heard_speech": _STATE["heard_speech"],
            "level": round(float(_STATE.get("last_level") or 0.0), 1),
            "elapsed_sec": round(time.time() - (_STATE.get("started_at") or time.time()), 1),
        }


def stop() -> dict[str, Any]:
    with _LOCK:
        if not _STATE["active"] and _STATE["done"]:
            return {"ok": True, "text": _STATE["final_text"] or _STATE["partial_text"],
                    "heard_speech": _STATE["heard_speech"], "duration_sec": 0.0}
        _STATE["stop_event"].set()
        ws = _STATE.get("ws")
        for t in list(_STATE.get("threads", [])):
            if t.is_alive():
                t.join(timeout=12)
        final = _STATE["final_text"] or _STATE["partial_text"]
        try:
            if ws is not None:
                ws.close()
        except Exception:
            pass
        _STATE["active"] = False
        _STATE["done"] = True
        _STATE["final_text"] = final
        return {"ok": True, "text": final, "heard_speech": _STATE["heard_speech"], "duration_sec": 0.0}