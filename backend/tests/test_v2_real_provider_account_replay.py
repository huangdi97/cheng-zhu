"""Source-side real-provider replay harness safety contracts."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _load():
    path = ROOT / "scripts" / "v2_real_provider_account_replay.py"
    spec = importlib.util.spec_from_file_location("v2_real_provider_account_replay_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _args(**overrides):
    values = {
        "provider": "google-mail",
        "token_env": "TEST_REAL_PROVIDER_TOKEN",
        "target": "",
        "limit": 500,
        "execute_write": False,
        "confirm_write": "",
        "write_title": "Replay test",
        "write_body": "Replay body",
        "out": "",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_provider_contracts_keep_read_and_write_boundaries_explicit():
    mod = _load()
    assert mod.PROVIDERS["google-calendar"].capability == "calendar.read"
    assert mod.PROVIDERS["google-calendar"].mode == "READ"
    assert mod.PROVIDERS["google-drive"].capability == "docs.read"
    assert mod.PROVIDERS["google-drive"].mode == "READ"
    assert mod.PROVIDERS["google-mail"].capability == "email.send"
    assert mod.PROVIDERS["google-mail"].confirm_marker == "SEND_EMAIL"
    assert mod.PROVIDERS["microsoft-todo"].capability == "task.create"
    assert mod.PROVIDERS["microsoft-todo"].confirm_marker == "CREATE_TASK"

    with pytest.raises(ValueError, match="read-only"):
        mod._validate_cli(
            mod.PROVIDERS["google-calendar"],
            _args(provider="google-calendar", execute_write=True, confirm_write="SEND_EMAIL"),
        )

    with pytest.raises(ValueError, match="confirm-write SEND_EMAIL"):
        mod._validate_cli(
            mod.PROVIDERS["google-mail"],
            _args(execute_write=True, target="replay@example.test", confirm_write=""),
        )

    with pytest.raises(ValueError, match="explicit --target recipient"):
        mod._validate_cli(
            mod.PROVIDERS["google-mail"],
            _args(execute_write=True, target="", confirm_write="SEND_EMAIL"),
        )

    assert mod._validate_cli(
        mod.PROVIDERS["microsoft-todo"],
        _args(
            provider="microsoft-todo",
            execute_write=True,
            confirm_write="CREATE_TASK",
            target="default",
        ),
    ) == "default"

    with pytest.raises(ValueError, match="between 1 and 500"):
        mod._validate_cli(
            mod.PROVIDERS["google-drive"],
            _args(provider="google-drive", limit=501),
        )


def test_blocked_account_report_is_fail_closed_and_contains_no_credential_value():
    mod = _load()
    report = mod._blocked_report(
        mod.PROVIDERS["google-calendar"],
        "abc123",
        "MISSING_CALENDAR_TOKEN",
    )
    assert report["status"] == "BLOCKED_ACCOUNT"
    assert report["reason"] == "TOKEN_ENV_NOT_SET"
    assert report["claims"] == {
        "REAL_ACCOUNT_AUTH_VALIDATED": False,
        "REAL_PROVIDER_READ_REPLAY_VALIDATED": False,
        "REAL_PROVIDER_WRITE_REPLAY_VALIDATED": False,
        "V2_STABLE_RELEASE": False,
        "REAL_USER_VALIDATED": False,
        "PMF_PROVEN": False,
    }
    serialized = json.dumps(report)
    assert "Bearer " not in serialized
    assert "ya29." not in serialized


def test_public_connection_hashes_account_hint_instead_of_exporting_it():
    mod = _load()
    row = mod._public_connection({
        "id": "cci-1",
        "status": "CONNECTED",
        "provider_id": "GOOGLE_MAIL",
        "credential_ref_present": True,
        "account_hint": "private-user@example.test",
        "granted_capabilities": ["email.send"],
        "provider_scopes": ["openid", "email", "gmail.send"],
    })
    assert row["account_hint_sha256"] == mod._hash_text("private-user@example.test")
    assert "private-user@example.test" not in json.dumps(row)
    assert row["credential_ref_returned"] is False


class _FakeServer:
    def shutdown(self):
        return None


def _mock_common_runtime(monkeypatch, mod, *, adapter_modes):
    monkeypatch.setattr(mod, "_source_sha", lambda: "source-sha")
    monkeypatch.setattr(mod, "_start_fake_provider", lambda: (_FakeServer(), "http://127.0.0.1:1/v1"))
    monkeypatch.setattr(mod, "_start_backend", lambda **_kwargs: object())
    monkeypatch.setattr(mod, "_stop_backend", lambda _process: None)

    availability = iter(adapter_modes)
    monkeypatch.setattr(
        mod,
        "_catalog_item",
        lambda _base, _provider_id: {"adapter_available": next(availability)},
    )

    def fake_http(_base, method, path, body=None, timeout=90.0):
        del timeout
        if method == "POST" and path.endswith("/integrations/connections"):
            return {
                "id": "conn-1",
                "status": "DISCONNECTED",
                "provider_id": body["provider_id"],
                "credential_ref_present": True,
                "granted_capabilities": body["granted_capabilities"],
                "provider_scopes": ["scope-a"],
            }
        if method == "POST" and path.endswith("/verify"):
            return {
                "id": "conn-1",
                "status": "CONNECTED",
                "provider_id": "GOOGLE_MAIL",
                "account_hint": "real-private-account@example.test",
                "provider_scopes": ["scope-a"],
            }
        raise AssertionError(f"unexpected HTTP call in harness unit test: {method} {path}")

    monkeypatch.setattr(mod, "_http", fake_http)


def test_write_provider_default_replay_stops_before_external_side_effect(monkeypatch):
    mod = _load()
    monkeypatch.setenv("TEST_REAL_PROVIDER_TOKEN", "token-value-must-not-export")
    _mock_common_runtime(monkeypatch, mod, adapter_modes=[False, True])
    called = {}

    def fake_write(_base, _home, spec, _connection_id, target, _token, report, *, execute_write, title, content):
        called.update({
            "provider": spec.key,
            "target": target,
            "execute_write": execute_write,
            "title": title,
            "content": content,
        })
        report["real_account_replay"] = {
            "mode": "WRITE_PROVIDER_AUTH_ONLY",
            "external_write_attempted": False,
            "result": "PASS_REAL_ACCOUNT_AUTH_PRODUCT_REPLAY_WRITE_NOT_EXECUTED",
        }

    monkeypatch.setattr(mod, "_write_replay", fake_write)
    report, code = mod.run_replay(_args())
    assert code == 0
    assert called["execute_write"] is False
    assert report["claims"]["REAL_ACCOUNT_AUTH_VALIDATED"] is True
    assert report["claims"]["REAL_PROVIDER_WRITE_REPLAY_VALIDATED"] is False
    assert report["claims"]["REAL_PROVIDER_READ_REPLAY_VALIDATED"] is False
    assert report["real_account_replay"]["external_write_attempted"] is False
    serialized = json.dumps(report)
    assert "token-value-must-not-export" not in serialized
    assert "real-private-account@example.test" not in serialized


def test_read_and_explicit_write_claims_are_separate(monkeypatch):
    mod = _load()
    monkeypatch.setenv("TEST_REAL_PROVIDER_TOKEN", "token-value")

    # Read replay.
    _mock_common_runtime(monkeypatch, mod, adapter_modes=[False, True])

    def fake_read(_base, _home, spec, _connection_id, target, _token, report, limit):
        assert spec.mode == "READ"
        assert limit == 500
        report["real_account_replay"] = {
            "mode": "READ",
            "target_sha256": mod._hash_text(target),
            "external_write_attempted": False,
            "result": "PASS_REAL_ACCOUNT_READ_PRODUCT_REPLAY",
        }

    monkeypatch.setattr(mod, "_read_replay", fake_read)
    read_report, read_code = mod.run_replay(
        _args(provider="google-drive", target="root")
    )
    assert read_code == 0
    assert read_report["claims"]["REAL_ACCOUNT_AUTH_VALIDATED"] is True
    assert read_report["claims"]["REAL_PROVIDER_READ_REPLAY_VALIDATED"] is True
    assert read_report["claims"]["REAL_PROVIDER_WRITE_REPLAY_VALIDATED"] is False

    # Explicit write replay.
    _mock_common_runtime(monkeypatch, mod, adapter_modes=[False, True])

    def fake_write(_base, _home, spec, _connection_id, target, _token, report, *, execute_write, title, content):
        assert spec.key == "microsoft-todo"
        assert target == "default"
        assert execute_write is True
        assert title and content
        report["real_account_replay"] = {
            "mode": "WRITE",
            "external_write_attempted": True,
            "result": "PASS_REAL_ACCOUNT_WRITE_PRODUCT_REPLAY",
        }

    monkeypatch.setattr(mod, "_write_replay", fake_write)
    write_report, write_code = mod.run_replay(
        _args(
            provider="microsoft-todo",
            target="default",
            execute_write=True,
            confirm_write="CREATE_TASK",
        )
    )
    assert write_code == 0
    assert write_report["claims"]["REAL_ACCOUNT_AUTH_VALIDATED"] is True
    assert write_report["claims"]["REAL_PROVIDER_READ_REPLAY_VALIDATED"] is False
    assert write_report["claims"]["REAL_PROVIDER_WRITE_REPLAY_VALIDATED"] is True


def test_evidence_output_never_overwrites_existing_file(tmp_path):
    mod = _load()
    out = tmp_path / "provider-replay.json"
    mod._write_report(str(out), {"status": "FIRST"})
    with pytest.raises(FileExistsError):
        mod._write_report(str(out), {"status": "SECOND"})
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "FIRST"
