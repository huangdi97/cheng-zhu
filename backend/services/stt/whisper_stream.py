"""Local faster-whisper sliding-window streaming preview for Cheng Zhu.

Feeds growing 16k mono float32 audio; a background decode thread periodically
transcribes the current window (language fixed, beam_size=1,
condition_on_previous_text=False) and emits partial text via on_partial.

Design:
- Engines are shared at module level (one per model/language pair) and loaded
  once, so a new utterance never pays a re-load cost. A module-level infer
  lock serializes decodes across sessions (interviewer + candidate can both be
  live); a decode is ~100-300ms, so contention is negligible.
- The shared engine is separate from the authoritative batch engine used by
  ``services/stt/factory.py`` (which holds its own ``_whisper_infer_lock``),
  so partial decodes never block the final transcription.
- Additive only: if the model fails to load/decode, partials simply stop; the
  batch path remains authoritative, so this never regresses final output.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

import numpy as np

from core.logger import get_logger
from .engines import STTEngine

_log = get_logger("stt.whisper_stream")

DEFAULT_INTERVAL_SEC = 0.3
DEFAULT_MIN_WINDOW_SEC = 0.6
DEFAULT_MAX_WINDOW_SEC = 8.0
MIN_INTERVAL_SEC = 0.12
TARGET_SAMPLE_RATE = 16000

# Shared streaming engines: key = (model_size, language)
_stream_engines: dict[tuple[str, str], STTEngine] = {}
_stream_engines_lock = threading.Lock()
_stream_infer_lock = threading.Lock()


def _get_stream_engine(model_size: str, language: str) -> STTEngine:
    key = ((model_size or "base").strip(), (language or "zh").strip() or "zh")
    with _stream_engines_lock:
        engine = _stream_engines.get(key)
        if engine is None:
            engine = STTEngine(model_size=key[0], language=key[1])
            _stream_engines[key] = engine
        return engine


def _reset_stream_engines_for_tests() -> None:
    """Test hook: drop cached shared engines."""
    with _stream_engines_lock:
        _stream_engines.clear()


class WhisperStreamSession:
    """Sliding-window local Whisper partials for one utterance/segment."""

    def __init__(
        self,
        *,
        model_size: str = "base",
        language: str = "zh",
        position: str = "后端开发",
        on_partial: Optional[Callable[[str], None]] = None,
        interval_sec: float = DEFAULT_INTERVAL_SEC,
        min_window_sec: float = DEFAULT_MIN_WINDOW_SEC,
        max_window_sec: float = DEFAULT_MAX_WINDOW_SEC,
        engine: Optional[STTEngine] = None,
    ):
        self._engine = engine if engine is not None else _get_stream_engine(model_size, language)
        self._language = (language or "zh").strip() or "zh"
        self._position = position or "后端开发"
        self._on_partial = on_partial
        self._interval_sec = max(MIN_INTERVAL_SEC, float(interval_sec or DEFAULT_INTERVAL_SEC))
        self._min_window_sec = max(0.2, float(min_window_sec or DEFAULT_MIN_WINDOW_SEC))
        self._max_window_sec = max(2.0, float(max_window_sec or DEFAULT_MAX_WINDOW_SEC))
        self._buffer: list[np.ndarray] = []
        self._buffer_samples = 0
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._started = False
        self._last_text = ""
        self._last_decode_mono = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="whisper-stream",
        )
        self._thread.start()

    def feed(self, audio: np.ndarray) -> None:
        if not self._started or self._stop.is_set():
            return
        if audio is None or len(audio) == 0:
            return
        audio = np.asarray(audio, dtype=np.float32).ravel()
        if len(audio) == 0:
            return
        with self._lock:
            self._buffer.append(audio)
            self._buffer_samples += len(audio)
        self._wake.set()

    def finish(self) -> str:
        if not self._started:
            return ""
        self._stop.set()
        self._wake.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=10)
        return self._decode_now(final=True)

    def is_loaded(self) -> bool:
        return bool(self._engine is not None and self._engine.is_loaded)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run(self) -> None:
        try:
            if not self._engine.is_loaded:
                _log.info("WhisperStream loading model=%s language=%s", self._engine.model_size, self._language)
                self._engine.load_model()
        except Exception as e:
            _log.warning("WhisperStream model load failed: %s", e)
            return
        while not self._stop.is_set():
            now = time.monotonic()
            since_last = now - self._last_decode_mono
            if since_last < self._interval_sec:
                self._wake.wait(max(0.01, self._interval_sec - since_last))
                self._wake.clear()
                continue
            self._wake.clear()
            self._decode_now(final=False)
            self._last_decode_mono = time.monotonic()

    def _window_audio(self) -> Optional[np.ndarray]:
        with self._lock:
            if not self._buffer:
                return None
            audio = np.concatenate(self._buffer) if len(self._buffer) > 1 else self._buffer[0]
        max_samples = int(self._max_window_sec * TARGET_SAMPLE_RATE)
        if len(audio) > max_samples:
            audio = audio[-max_samples:]
        return audio

    def _decode_now(self, *, final: bool) -> str:
        # Serialize with the authoritative batch path: when the caller passes a
        # shared factory engine, concurrent model use is unsafe. The factory
        # lock is re-entrant-safe here because it is only held briefly
        # (~100-300ms) per decode.
        try:
            from services.stt.factory import _whisper_infer_lock as _lock
        except Exception:
            _lock = _stream_infer_lock
        if not _lock.acquire(blocking=False):
            return ""
        try:
            audio = self._window_audio()
            if audio is None or len(audio) < int(self._min_window_sec * TARGET_SAMPLE_RATE):
                return ""
            text = self._engine.transcribe_fast(
                audio,
                TARGET_SAMPLE_RATE,
                position=self._position,
                language=self._language,
            )
            text = (text or "").strip()
            if not text or text == self._last_text:
                return text
            self._last_text = text
            if self._on_partial is not None:
                try:
                    self._on_partial(text)
                except Exception:
                    pass
            return text
        except Exception as e:
            _log.debug("WhisperStream decode failed: %s", e)
            return ""
        finally:
            _lock.release()
