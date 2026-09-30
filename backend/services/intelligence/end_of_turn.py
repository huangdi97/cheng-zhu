"""Adaptive end-of-turn detection (v1.2-R2 latency closure, Stage C).

A fixed VAD silence (1.2 s) is the single largest wait between the
interviewer finishing a question and the first cue. This module decides,
while the speaker is silent, whether the turn is over:

  CONTINUE       keep listening (sentence unfinished, partial still moving,
                 or the speaker is known to pause this long mid-sentence)
  LIKELY_END     the text reads as a finished question but the evidence is
                 not complete yet (partial does not cover the speech end /
                 not stable); keep waiting, do not act
  CONFIRMED_END  finish the turn now

Inputs: silence duration, streaming partial text, whether that partial was
decoded from audio that includes the speech end, how long it has been
stable, punctuation / question-terminal phrases, semantic completeness,
dangling connectors, the speaker's own mid-sentence pause pattern, the
provider's endpoint event and the previous question (short follow-ups).

The hard timeout (the product's ``silence_duration``) is never removed: the
detector can only end a turn earlier, never later.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from services.intelligence.eot import looks_like_complete_question


class EotState(str, Enum):
    CONTINUE = "CONTINUE"
    LIKELY_END = "LIKELY_END"
    CONFIRMED_END = "CONFIRMED_END"


@dataclass(frozen=True)
class EotDecision:
    state: EotState
    reason: str


@dataclass(frozen=True)
class EotSignals:
    silence_sec: float
    partial_text: str = ""
    # The newest partial was decoded from audio that includes the last
    # voiced frame (local streaming); remote providers report this through
    # ``provider_endpoint`` or by the partial arriving after the speech end.
    partial_covers_end: bool = False
    partial_stable_sec: float = 0.0
    provider_endpoint: bool = False
    previous_question: str = ""


# Sentence-final connectors: the speaker is mid-sentence.
_DANGLING_TAIL = re.compile(
    r"(?:然后|但是|不过|如果|因为|所以|而且|或者|还有|以及|比如|就是|那个|这个|假如|要是|比方说|和|跟|与|的|在|把|对|"
    r"\band|\bbut|\bif|\bbecause|\bso|\bor|\bthe|\ba|\ban|\bof|\bto|\bwith|\bfor|\blike|\bwhen|\bthat)[，,、\s…]*$",
    re.IGNORECASE,
)
# A clause that opens a condition but has not asked anything yet.
# (\b only for English: between two CJK characters there is no word boundary.)
_OPEN_CONDITION = re.compile(r"^(?:如果|假如|假设|要是|当|(?:if|when|suppose|assuming)\b)", re.IGNORECASE)
# Short follow-ups that are complete only relative to a previous question.
_FOLLOW_UP = re.compile(
    r"^(?:为什么|为啥|怎么说|然后呢|还有呢|具体呢|比如呢|举个例子|那.{0,12}呢|why|how so|such as|for example|and then|what else)[？?。.!！]?$",
    re.IGNORECASE,
)


def reads_mid_sentence(text: str) -> bool:
    """The partial clearly stops mid-sentence (dangling connector, or an
    open condition that has not asked anything yet)."""
    value = (text or "").strip()
    if not value:
        return False
    if _DANGLING_TAIL.search(value):
        return True
    return bool(_OPEN_CONDITION.search(value)) and not looks_like_complete_question(value)


@dataclass
class EndOfTurnConfig:
    # Normal comma pauses run 0.3-0.55 s; ending a turn inside one cuts the
    # speaker off whenever the first clause already reads as a question.
    min_silence_sec: float = 0.55
    stable_sec: float = 0.20
    hard_timeout_sec: float = 1.2
    # Never wait less than the speaker's own mid-sentence pauses + margin.
    pause_margin_sec: float = 0.12


@dataclass
class EndOfTurnDetector:
    config: EndOfTurnConfig = field(default_factory=EndOfTurnConfig)
    _internal_pauses: list[float] = field(default_factory=list)

    def note_resumed_after(self, silence_sec: float) -> None:
        """The speaker went quiet for ``silence_sec`` and then kept talking in
        the same turn. Long mid-sentence pauses raise this speaker's minimum
        end-of-turn silence (speaker pause pattern)."""
        if 0.15 <= silence_sec < self.config.hard_timeout_sec:
            self._internal_pauses.append(float(silence_sec))
            del self._internal_pauses[:-12]

    def min_silence_sec(self) -> float:
        base = self.config.min_silence_sec
        if len(self._internal_pauses) >= 2:
            ordered = sorted(self._internal_pauses)
            typical = ordered[int(round(0.8 * (len(ordered) - 1)))]
            base = max(base, typical + self.config.pause_margin_sec)
        return min(base, self.config.hard_timeout_sec)

    def evaluate(self, signals: EotSignals) -> EotDecision:
        silence = float(signals.silence_sec)
        if silence >= self.config.hard_timeout_sec:
            return EotDecision(EotState.CONFIRMED_END, "hard_timeout")
        if silence < self.min_silence_sec():
            return EotDecision(EotState.CONTINUE, "short_silence")
        text = (signals.partial_text or "").strip()
        if not text:
            return EotDecision(EotState.CONTINUE, "no_partial")
        if _DANGLING_TAIL.search(text):
            return EotDecision(EotState.CONTINUE, "dangling_connector")
        complete = looks_like_complete_question(text) or (
            bool(signals.previous_question.strip()) and bool(_FOLLOW_UP.match(text))
        )
        if not complete:
            if _OPEN_CONDITION.search(text):
                return EotDecision(EotState.CONTINUE, "open_condition")
            return EotDecision(EotState.CONTINUE, "not_a_complete_question")
        if signals.provider_endpoint:
            return EotDecision(EotState.CONFIRMED_END, "provider_endpoint")
        if not signals.partial_covers_end:
            return EotDecision(EotState.LIKELY_END, "partial_behind_speech_end")
        if signals.partial_stable_sec < self.config.stable_sec:
            return EotDecision(EotState.LIKELY_END, "partial_unstable")
        return EotDecision(EotState.CONFIRMED_END, "fast_confirm")
