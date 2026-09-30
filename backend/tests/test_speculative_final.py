"""Speculative final decode (v1.2-R2 latency closure, local Whisper profile).

In the trailing silence the pending audio is decoded once; the result feeds
the end-of-turn detector / provisional cue and is reused as the
authoritative transcription when the VAD flushes the same audio.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.assist import pipeline  # noqa: E402
from services.intelligence.live_turn import LiveTurnTracker  # noqa: E402


def _segment(**kw):
    base = dict(audio=np.ones(16000, dtype=np.float32) * 0.1, sample_rate=16000, started_mono=1.0,
                ended_mono=2.0, audio_sec=1.0, flush_reason="silence", capture_is_loopback=False)
    base.update(kw)
    return pipeline.InterviewerSegment(**base)


def _run_worker(monkeypatch, segments, stt_text="消息队列怎么保证不丢消息？"):
    calls: list[int] = []
    published: list[str] = []

    def _stt(audio, *_a, **_k):
        calls.append(len(audio))
        return stt_text

    monkeypatch.setattr(pipeline, "transcribe_with_fallback", _stt)
    monkeypatch.setattr(pipeline, "broadcast", lambda _d: None)
    monkeypatch.setattr(pipeline, "_append_transcription_fragment", lambda _c, _s, pub, _n, _f: published.append(pub))
    monkeypatch.setattr(pipeline, "_maybe_emit_copilot_hint", lambda _t: None)
    monkeypatch.setattr(pipeline, "get_config", lambda: SimpleNamespace(position="", language="zh", transcription_min_sig_chars=1))
    runtime = pipeline._new_interviewer_runtime()
    tracker = LiveTurnTracker(clock=lambda: 10.0)
    runtime.turn_tracker = tracker
    for seg in segments:
        runtime.segment_queue.put(seg)
    runtime.drain_event.set()
    worker = threading.Thread(target=pipeline._interviewer_asr_worker, args=(runtime, SimpleNamespace(), None), daemon=True)
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive()
    return calls, published, runtime, tracker


def test_flushed_segment_reuses_the_speculative_decode(monkeypatch):
    spec = _segment(flush_reason="speculative", speculative=True, spec_key=12000)
    final = _segment(audio=np.ones(20000, dtype=np.float32) * 0.1, spec_key=12000)
    calls, published, runtime, _tracker = _run_worker(monkeypatch, [spec, final])
    assert calls == [16000], "the flushed segment must not be decoded a second time"
    assert published == ["消息队列怎么保证不丢消息？"]
    assert runtime.spec_results == {}


def test_speculative_result_is_never_published_by_itself(monkeypatch):
    calls, published, runtime, _tracker = _run_worker(
        monkeypatch, [_segment(flush_reason="speculative", speculative=True, spec_key=5)]
    )
    assert calls == [16000] and published == []
    assert runtime.spec_results == {5: "消息队列怎么保证不丢消息？"}


def test_segment_with_other_key_is_transcribed_normally(monkeypatch):
    spec = _segment(flush_reason="speculative", speculative=True, spec_key=100)
    final = _segment(audio=np.ones(24000, dtype=np.float32) * 0.1, spec_key=None)
    calls, published, *_ = _run_worker(monkeypatch, [spec, final])
    assert calls == [16000, 24000] and len(published) == 1


def test_speculative_decode_feeds_tracker_as_end_covering_partial(monkeypatch):
    tracker = LiveTurnTracker(clock=lambda: 10.0)
    tracker.expect_speculative(16000)
    tracker.on_speculative_final(16000, "消息队列怎么保证不丢消息？", covered_samples=20000)
    assert tracker.probe(0.6, voiced_end_samples=16000)
    assert tracker.provisional_question() == "消息队列怎么保证不丢消息？"


def test_stale_speculative_result_after_new_speech_is_ignored():
    tracker = LiveTurnTracker(clock=lambda: 10.0)
    tracker.expect_speculative(16000)
    tracker.note_voice(9.9)  # the speaker kept talking
    tracker.on_speculative_final(16000, "我们先聊聊缓存", covered_samples=20000)
    assert tracker.text == ""


def test_speculative_final_only_for_local_whisper():
    on = SimpleNamespace(stt_provider="whisper", assist_adaptive_eot=True, assist_speculative_final=True)
    assert pipeline._speculative_final_enabled(on)
    assert not pipeline._speculative_final_enabled(SimpleNamespace(**{**vars(on), "stt_provider": "doubao"}))
    assert not pipeline._speculative_final_enabled(SimpleNamespace(**{**vars(on), "assist_speculative_final": False}))
