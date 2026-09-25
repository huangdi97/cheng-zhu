from __future__ import annotations

import io
import sys
import wave
from pathlib import Path

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.review.router import _decode_audio_to_pcm16k


def _make_wav_bytes(seconds: float = 1.5, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    n = int(rate * seconds)
    samples = (np.sin(np.linspace(0, 2 * np.pi * 440, n)) * 1000).astype(np.int16)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


def test_decode_wav_to_pcm16k():
    pcm = _decode_audio_to_pcm16k(_make_wav_bytes())
    assert pcm is not None
    assert pcm.dtype == np.int16
    assert len(pcm) >= 16000


def test_decode_rejects_empty_and_garbage():
    assert _decode_audio_to_pcm16k(b"") is None
    assert _decode_audio_to_pcm16k(b"not audio data at all") is None
