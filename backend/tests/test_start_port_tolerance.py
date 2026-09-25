"""start.py ?????????????????????????/??????"""

import importlib.util
import socket
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
START_PY = ROOT / "start.py"


def load_start():
    spec = importlib.util.spec_from_file_location("start_launcher", START_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeUvicorn:
    calls = []

    @staticmethod
    def run(*args, **kwargs):
        _FakeUvicorn.calls.append((args, kwargs))


def _bind_ephemeral_port() -> tuple[socket.socket, int]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    return s, s.getsockname()[1]


def test_port_in_use_true_when_listening():
    start = load_start()
    s, port = _bind_ephemeral_port()
    try:
        assert start._port_in_use(port) is True
    finally:
        s.close()


def test_port_in_use_false_when_free():
    start = load_start()
    s, port = _bind_ephemeral_port()
    s.close()
    assert start._port_in_use(port) is False


def test_is_our_server_running_checks_api_config(monkeypatch):
    start = load_start()
    calls = []

    def fake_open(url, timeout=1.0):
        calls.append(url)
        return _FakeResponse()

    monkeypatch.setattr(start, "_port_in_use", lambda port: True)
    monkeypatch.setattr(start.urllib.request, "urlopen", fake_open)
    assert start._is_our_server_running(18080) is True
    assert calls == ["http://127.0.0.1:18080/api/config"]


def test_is_our_server_running_false_on_foreign_service(monkeypatch):
    start = load_start()
    monkeypatch.setattr(start, "_port_in_use", lambda port: True)

    def fake_open(url, timeout=1.0):
        raise OSError("connection refused")

    monkeypatch.setattr(start.urllib.request, "urlopen", fake_open)
    assert start._is_our_server_running(18080) is False


def test_start_server_reuses_existing_backend(monkeypatch):
    start = load_start()
    ensure_calls = []
    chdir_calls = []
    keepalive_calls = []

    monkeypatch.setattr(start, "_is_our_server_running", lambda port: True)
    monkeypatch.setattr(start, "ensure_port_available", lambda port: ensure_calls.append(port) or True)
    monkeypatch.setattr(start.os, "chdir", lambda d: chdir_calls.append(d))
    monkeypatch.setattr(start, "_idle_keepalive", lambda: keepalive_calls.append(True))
    start.start_server("127.0.0.1", 18080)
    assert ensure_calls == []
    assert chdir_calls == []
    assert keepalive_calls == [True]


def test_start_server_starts_backend_when_port_free(monkeypatch):
    start = load_start()
    ensure_calls = []
    keepalive_calls = []
    _FakeUvicorn.calls = []

    monkeypatch.setattr(start, "_is_our_server_running", lambda port: False)
    monkeypatch.setattr(start, "_port_in_use", lambda port: False)
    monkeypatch.setattr(start, "ensure_port_available", lambda port: ensure_calls.append(port) or True)
    monkeypatch.setattr(start, "_idle_keepalive", lambda: keepalive_calls.append(True))
    monkeypatch.setattr(start.os, "chdir", lambda d: None)
    monkeypatch.setitem(sys.modules, "uvicorn", _FakeUvicorn)
    start.start_server("127.0.0.1", 18080)
    assert ensure_calls == [18080]
    assert keepalive_calls == []
    assert len(_FakeUvicorn.calls) == 1
