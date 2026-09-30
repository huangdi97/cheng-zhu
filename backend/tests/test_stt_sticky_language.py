"""Sticky Whisper language in auto mode (v1.2-R2 latency closure).

Auto language detection costs a second encoder pass (~0.5 s for base on
CPU) on every decode; after two confident agreeing detections the language
is pinned, re-checked every STICKY_RECHECK decodes, and unpinned on change.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.stt.engines import STTEngine  # noqa: E402


class _FakeModel:
    def __init__(self, heard):
        self.heard = list(heard)
        self.calls: list = []

    def transcribe(self, audio, **kwargs):
        forced = kwargs.get("language")
        self.calls.append(forced)
        if forced:
            lang, prob = forced, 1.0
        else:
            lang, prob = self.heard.pop(0) if self.heard else ("zh", 0.99)
        seg = SimpleNamespace(text="你好", no_speech_prob=0.0)
        return iter([seg]), SimpleNamespace(language=lang, language_probability=prob)


def _engine(heard, language="auto"):
    engine = STTEngine("base", language)
    engine._model = _FakeModel(heard)
    return engine


AUDIO = np.zeros(16000 * 2, dtype=np.float32)


def test_pins_after_two_confident_agreeing_detections_and_rechecks():
    engine = _engine([("zh", 0.95), ("zh", 0.97), ("zh", 0.9)])
    for _ in range(6):
        engine.transcribe(AUDIO)
    # detect, detect (pin), pinned x3, re-detect
    assert engine._model.calls == [None, None, "zh", "zh", "zh", None]
    assert engine.sticky_language == "zh"


def test_low_confidence_never_pins():
    engine = _engine([("en", 0.6)] * 4)
    for _ in range(4):
        engine.transcribe(AUDIO)
    assert engine._model.calls == [None] * 4
    assert engine.sticky_language is None


def test_language_change_on_recheck_unpins():
    engine = _engine([("zh", 0.95), ("zh", 0.95), ("en", 0.95), ("en", 0.95)])
    for _ in range(6):
        engine.transcribe(AUDIO)
    # detect, detect (pin zh), pinned x3, re-detect hears en -> unpin
    assert engine._model.calls[-1] is None and engine.sticky_language is None
    engine.transcribe(AUDIO)  # second agreeing "en" detection pins en
    assert engine.sticky_language == "en"


def test_short_audio_does_not_teach_language():
    engine = _engine([("en", 0.99)] * 3)
    for _ in range(3):
        engine.transcribe_fast(np.zeros(16000, dtype=np.float32))
    assert engine.sticky_language is None


def test_explicit_language_is_never_overridden():
    engine = _engine([("en", 0.99)] * 3, language="zh")
    for _ in range(3):
        engine.transcribe(AUDIO)
    assert engine._model.calls == ["zh", "zh", "zh"]


class _WrongPinModel(_FakeModel):
    """Hears nothing under a wrong pinned language, text under detection."""

    def transcribe(self, audio, **kwargs):
        forced = kwargs.get("language")
        self.calls.append(forced)
        if forced == "zh":
            return iter([]), SimpleNamespace(language="zh", language_probability=1.0)
        seg = SimpleNamespace(text="Tell me about a time you disagreed", no_speech_prob=0.0, avg_logprob=-0.3)
        return iter([seg]), SimpleNamespace(language="en", language_probability=0.99)


def test_wrong_pin_never_loses_the_question():
    engine = STTEngine("base", "auto")
    engine._model = _WrongPinModel([])
    engine._sticky_lang = "zh"  # pinned by earlier Chinese questions
    text = engine.transcribe(AUDIO)
    assert "Tell me about a time" in text
    assert engine._model.calls == ["zh", None]
    assert engine.sticky_language is None
