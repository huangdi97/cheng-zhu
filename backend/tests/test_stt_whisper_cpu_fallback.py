from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.stt.engines import STTEngine  # noqa: E402


class _BrokenCudaModel:
    def transcribe(self, *_args, **_kwargs):
        raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")


class _CpuModel:
    def transcribe(self, *_args, **_kwargs):
        return iter([SimpleNamespace(text="CPU 兜底成功", no_speech_prob=0.0)]), None


def test_whisper_runtime_cuda_error_retries_once_on_cpu(monkeypatch):
    engine = STTEngine(model_size="base", language="zh")
    engine._model = _BrokenCudaModel()
    engine._device = "cuda"
    switched: list[bool] = []

    def switch_to_cpu():
        switched.append(True)
        engine._model = _CpuModel()
        engine._device = "cpu"

    monkeypatch.setattr(engine, "_fallback_to_cpu", switch_to_cpu)

    text = engine.transcribe(np.ones(16000, dtype=np.float32) * 0.1)

    assert text == "CPU 兜底成功"
    assert switched == [True]


def test_non_cuda_runtime_error_is_not_hidden():
    assert STTEngine._is_cuda_runtime_error(RuntimeError("decoder failed")) is False
