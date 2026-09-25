"""Tests for Cheng Zhu's local Whisper preview and Doubao feed format."""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
import sys

import numpy as np
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.config import AppConfig  # noqa: E402
from services.stt.doubao_stream import DoubaoStreamSession  # noqa: E402
from services.stt.engines import _audio_to_pcm_int16  # noqa: E402
from services.stt import whisper_stream as ws_mod  # noqa: E402
from services.stt.whisper_stream import WhisperStreamSession  # noqa: E402


class _FakeEngine:
    def __init__(self, model_size="base", language="zh", text="测试文本"):
        self.model_size = model_size
        self.language = language
        self.is_loaded = True
        self.text = text
        self.calls = []

    def load_model(self):
        self.is_loaded = True

    def transcribe_fast(self, audio, sample_rate=16000, position="", language="zh"):
        self.calls.append(len(audio))
        return self.text


@pytest.fixture
def fake_engine(monkeypatch):
    engine = _FakeEngine()
    monkeypatch.setattr(ws_mod, "_get_stream_engine", lambda *a, **k: engine)
    return engine


def test_stream_engine_shared_by_key(monkeypatch):
    created = []

    class _Rec(_FakeEngine):
        def __init__(self, model_size="base", language="zh"):
            super().__init__(model_size, language)
            created.append((model_size, language))

    monkeypatch.setattr(ws_mod, "STTEngine", _Rec)
    ws_mod._reset_stream_engines_for_tests()
    a = ws_mod._get_stream_engine("small", "zh")
    b = ws_mod._get_stream_engine("small", "zh")
    c = ws_mod._get_stream_engine("medium", "zh")
    assert a is b
    assert a is not c
    assert created == [("small", "zh"), ("medium", "zh")]
    ws_mod._reset_stream_engines_for_tests()


def _audio(secs: float) -> np.ndarray:
    return np.zeros(int(secs * 16000), dtype=np.float32)


def test_whisper_stream_decode_emits_partial_and_dedupes(fake_engine):
    sess = WhisperStreamSession(
        model_size="small",
        language="zh",
        interval_sec=0.01,
        min_window_sec=0.3,
        max_window_sec=8.0,
    )
    partials = []
    sess._on_partial = partials.append
    sess._started = True
    sess.feed(_audio(0.6))

    first = sess._decode_now(final=False)
    assert first == "测试文本"
    assert partials == ["测试文本"]

    # duplicate decode does not re-emit
    second = sess._decode_now(final=False)
    assert second == "测试文本"
    assert partials == ["测试文本"]


def test_whisper_stream_respects_min_window(fake_engine):
    sess = WhisperStreamSession(
        model_size="small",
        language="zh",
        min_window_sec=1.0,
        max_window_sec=8.0,
    )
    sess._started = True
    sess.feed(_audio(0.4))
    assert sess._decode_now(final=False) == ""


def test_whisper_stream_window_is_capped(fake_engine):
    sess = WhisperStreamSession(
        model_size="small",
        language="zh",
        min_window_sec=0.2,
        max_window_sec=2.0,
    )
    sess._started = True
    sess.feed(_audio(10.0))
    audio = sess._window_audio()
    assert audio is not None
    assert len(audio) <= 2.0 * 16000 + 1


def test_whisper_stream_finish_returns_final(fake_engine):
    sess = WhisperStreamSession(
        model_size="small",
        language="zh",
        min_window_sec=0.2,
        max_window_sec=8.0,
    )
    sess._started = True
    sess.feed(_audio(1.0))
    assert sess.finish() == "测试文本"
    assert sess.is_loaded()


def test_whisper_stream_start_and_finish_lifecycle(fake_engine):
    sess = WhisperStreamSession(
        model_size="small",
        language="zh",
        interval_sec=0.02,
        min_window_sec=0.2,
        max_window_sec=8.0,
    )
    partials = []
    sess._on_partial = partials.append
    sess.start()
    sess.feed(_audio(0.8))
    deadline = time.monotonic() + 2.0
    while not partials and time.monotonic() < deadline:
        time.sleep(0.02)
    assert partials, "background decode thread should emit a partial"
    assert sess.finish() == "测试文本"


def test_doubao_stream_feed_converts_float32_to_int16():
    sess = DoubaoStreamSession.__new__(DoubaoStreamSession)
    sess._started = True
    sess._stop = threading.Event()
    sess._feed_queue = queue.Queue()
    audio = np.array([0.0, 0.5, -0.5, 1.0], dtype=np.float32)
    sess.feed(audio)
    pcm = sess._feed_queue.get_nowait()
    expected = _audio_to_pcm_int16(audio).tobytes()
    assert pcm == expected
    assert len(pcm) == audio.size * 2


def test_config_new_realtime_fields_clamped():
    cfg = AppConfig(
        mic_agc_max_gain=9999,
        mic_agc_noise_gate=0.9,
        whisper_stream_interval_ms=10,
        whisper_stream_min_sec=10,
        whisper_stream_window_sec=100,
    )
    assert cfg.mic_agc_max_gain == 200.0
    assert cfg.mic_agc_noise_gate == 0.05
    assert cfg.whisper_stream_interval_ms == 120
    assert cfg.whisper_stream_min_sec == 3.0
    assert cfg.whisper_stream_window_sec == 20.0
    assert cfg.mic_agc_enabled is True
    assert cfg.whisper_stream_enabled is True
