from __future__ import annotations

import gzip
import json
import struct
import threading
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.stt import engines  # noqa: E402
from services.stt.engines import DoubaoSTT  # noqa: E402


def test_doubao_stt_reports_missing_websocket_dependency(monkeypatch):
    monkeypatch.setattr(engines, "websocket", None)

    with pytest.raises(RuntimeError, match="websocket-client"):
        DoubaoSTT(api_key="sk-test").transcribe(
            np.zeros(1600, dtype=np.float32),
            sample_rate=16000,
        )


def _server_text_frame(text: str) -> bytes:
    payload = gzip.compress(
        json.dumps({"result": {"text": text}}, ensure_ascii=False).encode("utf-8")
    )
    return (
        bytes([0x00, engines.MSG_FULL_SERVER_RESPONSE << 4, engines.COMPRESSION_GZIP, 0x00])
        + b"\x00\x00\x00\x00"
        + struct.pack(">I", len(payload))
        + payload
    )


def test_doubao_stt_does_not_retry_timeout_before_factory_fallback(monkeypatch):
    calls = {"connect": 0, "sleep": []}

    def fake_create_connection(*_args, **_kwargs):
        calls["connect"] += 1
        raise TimeoutError("timed out")

    monkeypatch.setattr(
        engines,
        "websocket",
        SimpleNamespace(create_connection=fake_create_connection),
    )
    monkeypatch.setattr(engines.time, "sleep", lambda seconds: calls["sleep"].append(seconds))

    engine = DoubaoSTT(api_key="sk-test")

    with pytest.raises(TimeoutError):
        engine.transcribe(np.zeros(1600, dtype=np.float32), sample_rate=16000)

    assert calls["connect"] == 1
    assert calls["sleep"] == []


def test_doubao_stt_leaves_transient_retry_to_factory_fallback(monkeypatch):
    calls = {"connect": 0, "sleep": []}

    class FakeWebSocket:
        def __init__(self):
            self.recv_count = 0

        def send_binary(self, _frame):
            pass

        def settimeout(self, _timeout):
            pass

        def recv(self):
            self.recv_count += 1
            if self.recv_count == 1:
                return _server_text_frame("你好")
            raise TimeoutError("done")

        def close(self):
            pass

    def fake_create_connection(*_args, **_kwargs):
        calls["connect"] += 1
        if calls["connect"] == 1:
            raise ConnectionError("connection reset")
        return FakeWebSocket()

    monkeypatch.setattr(
        engines,
        "websocket",
        SimpleNamespace(create_connection=fake_create_connection),
    )
    monkeypatch.setattr(engines.time, "sleep", lambda seconds: calls["sleep"].append(seconds))

    engine = DoubaoSTT(api_key="sk-test")

    with pytest.raises(ConnectionError):
        engine.transcribe(np.zeros(1600, dtype=np.float32), sample_rate=16000)

    assert calls["connect"] == 1
    assert calls["sleep"] == []


# ---------------------------------------------------------------------------
# Real-time (bigmodel_async + enable_nonstream) request/response handling
# ---------------------------------------------------------------------------


def _gzip_json_payload(obj: dict) -> bytes:
    return gzip.compress(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def _server_frame(text: str = "", utterances=None) -> bytes:
    res = {"text": text}
    if utterances is not None:
        res["utterances"] = utterances
    payload = _gzip_json_payload({"result": res})
    return (
        bytes([0x00, engines.MSG_FULL_SERVER_RESPONSE << 4, engines.COMPRESSION_GZIP, 0x00])
        + b"\x00\x00\x00\x00"
        + struct.pack(">I", len(payload))
        + payload
    )


def test_build_ws_frame_full_request_async_omits_language_and_sets_realtime_params():
    frame = engines._build_ws_frame_full_request(
        "app-key",
        "boost-table",
        language="",
        result_type="single",
        end_window_size=400,
    )
    payload = json.loads(gzip.decompress(frame[8:]).decode("utf-8"))
    # bigmodel_async 不支持 audio.language；不传才支持中英文自动识别
    assert "language" not in payload["audio"]
    # 显式传入 language（bigmodel_nostream 场景）时仍写入 audio
    frame2 = engines._build_ws_frame_full_request("k", "", language="zh-CN")
    payload2 = json.loads(gzip.decompress(frame2[8:]).decode("utf-8"))
    assert payload2["audio"]["language"] == "zh-CN"
    req = payload["request"]
    assert req["model_name"] == "bigmodel"
    assert req["enable_nonstream"] is True
    assert req["result_type"] == "single"
    assert req["end_window_size"] == 400
    assert req["force_to_speech_time"] == 1000
    assert req["enable_accelerate_text"] is True
    assert req["accelerate_score"] == 5
    assert req["show_utterances"] is True
    assert req["enable_ddc"] is True
    assert req["corpus"]["boosting_table_id"] == "boost-table"


def test_build_ws_frame_full_request_full_result_no_force():
    frame = engines._build_ws_frame_full_request(
        "k", "", language="", result_type="full", force_to_speech_time=0, accelerate_score=0
    )
    payload = json.loads(gzip.decompress(frame[8:]).decode("utf-8"))
    assert payload["request"]["result_type"] == "full"
    assert "force_to_speech_time" not in payload["request"]
    assert "enable_accelerate_text" not in payload["request"]


def test_parse_doubao_result_payload_definite_and_partial():
    info = engines._parse_doubao_result_payload(
        {
            "result": {
                "text": "请问你有项目经验吗",
                "utterances": [
                    {"text": "请问你有项目", "definite": False},
                    {"text": "经验吗", "definite": True},
                ],
            }
        }
    )
    assert info["text"] == "请问你有项目经验吗"
    assert info["definite"] == ["经验吗"]
    assert info["partial"] == "请问你有项目"
    info2 = engines._parse_doubao_result_payload({"result": {"text": "你好"}})
    assert info2["definite"] == []
    assert info2["partial"] == ""


def test_doubao_stream_session_accumulates_definite_and_partial():
    from services.stt.doubao_stream import DoubaoStreamSession

    partials = []
    finals = []
    sess = DoubaoStreamSession.__new__(DoubaoStreamSession)
    sess._committed = []
    sess._partial = ""
    sess._last_shown = ""
    sess._final_text = ""
    sess._on_partial = partials.append
    sess._on_final = finals.append

    sess._handle_result({"result": {"text": "请介绍一下", "utterances": [{"text": "请介绍一下", "definite": False}]}})
    assert partials[-1] == "请介绍一下"
    sess._handle_result({"result": {"text": "请介绍一下你自己", "utterances": [{"text": "请介绍一下你自己", "definite": True}]}})
    assert partials[-1] == "请介绍一下你自己"
    assert sess._final_text == "请介绍一下你自己"
    assert finals[-1] == "请介绍一下你自己"
    sess._handle_result({"result": {"text": "然后", "utterances": [{"text": "然后", "definite": False}]}})
    assert partials[-1] == "请介绍一下你自己然后"


def test_doubao_stream_finish_drains_sender_before_reader_and_keeps_partial():
    from services.stt.doubao_stream import DoubaoStreamSession

    order = []

    class FakeThread:
        def __init__(self, name):
            self.name = name
            self.alive = True

        def is_alive(self):
            return self.alive

        def join(self, timeout=None):
            order.append((self.name, timeout))
            self.alive = False

    class FakeWebSocket:
        def __init__(self):
            self.timeouts = []
            self.closed = False

        def settimeout(self, value):
            self.timeouts.append(value)

        def close(self):
            self.closed = True

    sess = DoubaoStreamSession.__new__(DoubaoStreamSession)
    sess._started = True
    sess._stop = threading.Event()
    sess._sender_thread = FakeThread("sender")
    sess._reader_thread = FakeThread("reader")
    sess._ws = FakeWebSocket()
    sess._final_text = ""
    sess._last_shown = "请介绍一下你最近做过的项目"

    assert sess.finish() == "请介绍一下你最近做过的项目"
    assert [name for name, _timeout in order] == ["sender", "reader"]
    assert sess._ws.closed is True
