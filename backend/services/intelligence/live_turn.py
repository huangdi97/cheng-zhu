"""Live interviewer turn tracker (v1.2-R2 latency closure, Stages C–E).

Glue between the streaming ASR partials, the VAD and the end-of-turn
detector for one interviewer audio stream:

  - local streaming Whisper reports every decode with how many fed samples
    the decoded window covered, so "the partial includes the speech end" is
    a fact, not a guess;
  - a streaming provider (Doubao) reports partials in near real time and a
    definite-utterance endpoint event;
  - the VAD asks ``probe(silence, voiced_end_samples)`` during trailing
    silence and ends the segment on CONFIRMED_END.

``provisional_question()`` returns the partial that may drive an early
(provisional) Fast Cue: it must cover the speech end and read as a
complete question. Everything here is read-only with respect to interview
state; the ASR state machine owns confirmation and reconcile.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from services.intelligence.end_of_turn import (
    EndOfTurnConfig,
    EndOfTurnDetector,
    EotDecision,
    EotSignals,
    EotState,
    is_complete_turn,
    reads_mid_sentence,
)


@dataclass
class TurnTrace:
    """Forensic time points of the current turn (monotonic seconds)."""
    first_partial: Optional[float] = None
    partial_stable: Optional[float] = None
    likely_end: Optional[float] = None
    confirmed_end: Optional[float] = None
    confirm_reason: str = ""


class LiveTurnTracker:
    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        config: Optional[EndOfTurnConfig] = None,
        remote_lag_sec: float = 0.30,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.sample_rate = sample_rate
        self.detector = EndOfTurnDetector(config or EndOfTurnConfig())
        self.remote_lag_sec = remote_lag_sec
        self.clock = clock
        self.previous_question = ""
        self._lock = threading.Lock()
        self.trace = TurnTrace()
        self._reset_locked()

    def _reset_locked(self) -> None:
        self.text = ""
        self.changed_mono = 0.0
        self.covered_samples: Optional[int] = None
        self.remote = False
        self.endpoint = False
        self.last_voice_mono = 0.0
        self.voiced_end_samples = 0
        self.last_decision: Optional[EotDecision] = None
        self.spec_key: Optional[int] = None
        self.trace = TurnTrace()

    def reset(self, previous_question: str = "") -> None:
        with self._lock:
            self._reset_locked()
            if previous_question:
                self.previous_question = previous_question

    # -- inputs -----------------------------------------------------------

    def note_voice(self, now: Optional[float] = None) -> None:
        with self._lock:
            self.last_voice_mono = self.clock() if now is None else now
            self.endpoint = False
            self.spec_key = None

    def on_local_decode(self, text: str, covered_samples: int, now: Optional[float] = None) -> None:
        now = self.clock() if now is None else now
        value = (text or "").strip()
        with self._lock:
            if value != self.text:
                self.text = value
                self.changed_mono = now
                if self.trace.first_partial is None and value:
                    self.trace.first_partial = now
            self.covered_samples = int(covered_samples)
            self.remote = False

    def expect_speculative(self, key: int) -> None:
        with self._lock:
            self.spec_key = int(key)

    def on_speculative_final(self, key: int, text: str, covered_samples: int, now: Optional[float] = None) -> None:
        """A full decode of the pending audio (speculative final). Ignored if
        the speaker spoke again since it was started (key changed)."""
        with self._lock:
            if self.spec_key != int(key) or self.voiced_end_samples > int(key):
                return
        self.on_local_decode(text, covered_samples, now=now)

    def on_remote_partial(self, text: str, now: Optional[float] = None) -> None:
        now = self.clock() if now is None else now
        value = (text or "").strip()
        with self._lock:
            if value and value != self.text:
                self.text = value
                self.changed_mono = now
                if self.trace.first_partial is None:
                    self.trace.first_partial = now
            self.remote = True

    def on_remote_endpoint(self, now: Optional[float] = None) -> None:
        with self._lock:
            self.endpoint = True

    # -- decisions --------------------------------------------------------

    def _covers_end(self, now: float) -> bool:
        if self.remote:
            return now - self.last_voice_mono >= self.remote_lag_sec
        return self.covered_samples is not None and self.covered_samples >= self.voiced_end_samples

    def _stable_sec(self, now: float) -> float:
        if self.remote:
            return max(0.0, now - max(self.changed_mono, self.last_voice_mono))
        unchanged = max(0.0, now - self.changed_mono) if self.changed_mono else 0.0
        if self.covered_samples is None:
            return unchanged
        # A window that already includes trailing silence after the last
        # voiced frame will not change with more silence.
        tail = (self.covered_samples - self.voiced_end_samples) / float(self.sample_rate)
        return max(unchanged, tail)

    def probe(self, silence_sec: float, voiced_end_samples: int, now: Optional[float] = None) -> bool:
        now = self.clock() if now is None else now
        with self._lock:
            self.voiced_end_samples = int(voiced_end_samples)
            covers = self._covers_end(now)
            stable = self._stable_sec(now)
            decision = self.detector.evaluate(EotSignals(
                silence_sec=silence_sec,
                partial_text=self.text,
                partial_covers_end=covers,
                partial_stable_sec=stable,
                provider_endpoint=self.endpoint,
                previous_question=self.previous_question,
            ))
            self.last_decision = decision
            if covers and stable >= self.detector.config.stable_sec and self.trace.partial_stable is None:
                self.trace.partial_stable = now
            if decision.state is EotState.LIKELY_END and self.trace.likely_end is None:
                self.trace.likely_end = now
            if decision.state is EotState.CONFIRMED_END and self.trace.confirmed_end is None:
                self.trace.confirmed_end = now
                self.trace.confirm_reason = decision.reason
            return decision.state is EotState.CONFIRMED_END

    def should_speculate(self) -> bool:
        """Skip the speculative final when the newest partial clearly stops
        mid-sentence: a pause there is a thinking pause, and a wasted decode
        would make the real final wait behind it on a busy CPU."""
        with self._lock:
            return not reads_mid_sentence(self.text)

    def provisional_question(self, now: Optional[float] = None) -> str:
        """The partial that may drive a provisional Fast Cue, or ""."""
        now = self.clock() if now is None else now
        with self._lock:
            if not self.text or not self._covers_end(now):
                return ""
            if self.last_decision is not None and self.last_decision.reason in {
                "dangling_connector",
                "open_condition",
                "not_a_complete_question",
            }:
                return ""
            return self.text if is_complete_turn(self.text, self.previous_question) else ""
