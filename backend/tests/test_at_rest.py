import sys

import pytest

from services.privacy import at_rest


def test_status_tells_the_truth_about_platform():
    status = at_rest.status()
    assert status["available"] is (sys.platform == "win32")
    assert status["scheme"] == ("windows-dpapi" if sys.platform == "win32" else "none")
    # The limits are part of the contract, not a footnote someone can drop.
    assert "resume text columns" in status["covers"]
    assert "knowledge base and other stores" in status["does_not_cover"]
    assert "a compromised OS account" in status["does_not_cover"]


def test_plaintext_passes_through_untouched():
    assert at_rest.is_protected(b"%PDF-1.4") is False
    assert at_rest.unprotect(b"%PDF-1.4") == b"%PDF-1.4"


def test_protect_is_inert_without_dpapi(monkeypatch):
    monkeypatch.setattr(at_rest, "available", lambda: False)
    assert at_rest.protect(b"secret") is None


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
def test_roundtrip_and_tamper_detection():
    data = b"%PDF-1.4 resume bytes \xe4\xb8\xad\xe6\x96\x87"
    blob = at_rest.protect(data)
    assert blob is not None
    assert at_rest.is_protected(blob)
    # The plaintext must not survive anywhere in the protected payload.
    assert data not in blob
    assert at_rest.unprotect(blob) == data
    with pytest.raises(at_rest.AtRestError):
        at_rest.unprotect(blob[:-4] + b"xxxx")


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
def test_different_purpose_cannot_unwrap():
    blob = at_rest.protect(b"resume", purpose="resume")
    with pytest.raises(at_rest.AtRestError):
        at_rest.unprotect(blob, purpose="kb")

@pytest.fixture()
def resume_env(tmp_path, monkeypatch):
    import core.config as config_module
    from services.storage import resume_history as rh

    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(rh, "DB_PATH", str(tmp_path / "resume_history.db"))
    monkeypatch.setattr(rh, "_uploads_dir", lambda: str(uploads))
    monkeypatch.setattr(config_module, "_save_config", lambda cfg: True)
    monkeypatch.setattr(config_module, "_config", config_module._raw_config().model_copy(deep=True))
    rh.init_db()
    return rh, uploads


def test_upload_bytes_are_protected_at_rest(resume_env):
    """The uploaded document is what a user would least want copied, so the bytes on
    disk must not be the document when the platform can protect them — and must still
    round-trip through the storage layer either way."""
    rh, uploads = resume_env
    content = b"%PDF-1.4\n% fake resume for at-rest check\nWenNian RAG Redis\n"
    entry = rh.add_upload(content, "at_rest_check.txt")

    stored = list(uploads.iterdir())
    assert len(stored) == 1
    raw = stored[0].read_bytes()
    if at_rest.available():
        assert raw.startswith(at_rest.MAGIC)
        assert content not in raw
    else:
        assert raw == content

    back, _name, _base = rh._read_entry_bytes(entry["history_id"])
    assert back == content
def test_resume_text_columns_are_not_plaintext_on_disk(resume_env):
    """The parsed resume text is the other half of the exposure: it must not sit
    readable in the SQLite file, and it must still render in the UI."""
    rh, _uploads = resume_env
    marker = "WenNian-RAG-Redis-session-state"
    content = f"简历：负责 RAG 检索链路 {marker}，用 Redis 管理 session state。".encode()
    rh.add_upload(content, "at_rest_columns.txt")

    blob = b""
    for suffix in ("", "-wal"):
        path = rh.DB_PATH + suffix
        try:
            with open(path, "rb") as handle:
                blob += handle.read()
        except OSError:
            continue

    if at_rest.available():
        assert marker.encode() not in blob
    entry = rh.list_entries()[0]
    assert entry["parsed_ok"] is True
    detail = rh.get_entry_detail(entry["id"])
    assert marker in (detail.get("summary") or detail.get("preview") or "")