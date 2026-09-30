"""v1.2.1: the frozen sidecar must not crash printing Chinese on a cp1252 locale.

v1.2.0 exited at first launch on English-locale Windows: PyInstaller ignores
PYTHONIOENCODING, stdout was cp1252, and the first Chinese print raised
UnicodeEncodeError inside the FastAPI lifespan.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import sidecar  # noqa: E402


def _cp1252_stream():
    return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")


def test_cp1252_stdout_reproduces_the_v1_2_0_crash():
    stream = _cp1252_stream()
    with pytest.raises(UnicodeEncodeError):
        print("[Config] 已从 config.example.json 创建 config.json", file=stream)
        stream.flush()


def test_force_utf8_stdio_makes_chinese_prints_safe(monkeypatch):
    out, err = _cp1252_stream(), _cp1252_stream()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    sidecar._force_utf8_stdio()
    print("[Config] 已从 config.example.json 创建 config.json")
    print("配置文件解析失败", file=sys.stderr)
    sys.stdout.flush()
    assert out.encoding == "utf-8" and err.encoding == "utf-8"
    assert "已从".encode("utf-8") in out.buffer.getvalue()


def test_force_utf8_stdio_tolerates_streams_without_reconfigure(monkeypatch):
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    sidecar._force_utf8_stdio()  # must not raise
