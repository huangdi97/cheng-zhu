import pytest

from services.privacy import at_rest, exposure


@pytest.fixture()
def data_root(tmp_path, monkeypatch):
    """Point the scan at a temp profile instead of the developer's real one."""
    from services.storage import resume_history as rh

    monkeypatch.setattr(exposure, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(rh, "DB_PATH", str(tmp_path / "resume_history.db"))
    uploads = tmp_path / "resume_uploads"
    uploads.mkdir()
    monkeypatch.setattr(rh, "_uploads_dir", lambda: str(uploads))
    return tmp_path, rh, uploads


def test_scan_reports_clean_profile(data_root, monkeypatch):
    root, rh, uploads = data_root
    rh.init_db()
    rh.add_upload("简历：RAG 检索链路，Redis session state。".encode(), "clean.txt")
    (root / "product.db").write_bytes(b"SQLite format 3\x00")
    monkeypatch.setattr(exposure, "_disk_encryption", lambda: {"checked": True, "protected": True, "source": "test"})

    result = exposure.scan()

    assert result["verdict"] in {"clean", "exposed"}
    assert result["databases"][0]["name"] == "product.db"
    assert result["resume_uploads"]["total"] == 1
    if at_rest.available():
        assert result["resume_uploads"]["protected"] == 1
        assert result["resume_uploads"]["plaintext"] == 0
        assert result["resume_rows"]["protected"] == result["resume_rows"]["total"]
        assert result["verdict"] == "clean"
        assert result["gaps"] == []
    else:
        assert result["resume_uploads"]["plaintext"] == 1
        assert result["verdict"] == "exposed"
        assert any("未加密" in gap for gap in result["gaps"])


def test_scan_calls_out_plaintext_rows(data_root, monkeypatch):
    _root, rh, _uploads = data_root
    rh.init_db()
    with rh._conn() as conn:  # noqa: SLF001 - fixture setup
        conn.execute(
            "INSERT INTO resume_entries (original_filename, stored_basename, file_size, created_at,"
            " last_used_at, parsed_ok, preview, parse_error, resume_summary)"
            " VALUES ('old.pdf', 'old.pdf', 1, 0, 0, 1, '明文预览', NULL, '明文全文')"
        )
    monkeypatch.setattr(exposure, "_disk_encryption", lambda: {"checked": True, "protected": True, "source": "test"})

    result = exposure.scan()

    assert result["resume_rows"]["total"] == 1
    assert result["resume_rows"]["protected"] == 0
    assert any("简历文本" in gap for gap in result["gaps"])
    assert result["verdict"] == "exposed"


def test_undetermined_disk_encryption_is_not_a_pass(data_root, monkeypatch):
    _root, rh, _uploads = data_root
    rh.init_db()
    monkeypatch.setattr(
        exposure,
        "_disk_encryption",
        lambda: {"checked": True, "protected": None, "source": "test", "note": "未实现"},
    )

    result = exposure.scan()

    # None means "unknown": it must not be reported as a gap, and it must not be
    # reported as protection either.
    assert result["disk_encryption"]["protected"] is None
    assert not any("磁盘" in gap for gap in result["gaps"])


@pytest.mark.parametrize(
    "text,expected",
    [
        ("BitLocker Drive Encryption: Protection On", True),
        ("Protection Status: Protection Off", False),
        ("", None),
    ],
)
def test_bitlocker_parser(monkeypatch, text, expected):
    monkeypatch.setattr(exposure, "_run", lambda *a, **k: text or None)
    assert exposure._bitlocker()["protected"] is expected  # noqa: SLF001


def test_filevault_parser(monkeypatch):
    monkeypatch.setattr(exposure, "_run", lambda *a, **k: "FileVault is On.")
    assert exposure._filevault()["protected"] is True  # noqa: SLF001

def test_endpoint_returns_the_report(data_root, monkeypatch):
    import importlib

    from fastapi.testclient import TestClient

    root, rh, _uploads = data_root
    rh.init_db()
    monkeypatch.setattr(
        exposure,
        "_disk_encryption",
        lambda: {"checked": True, "protected": None, "source": "test"},
    )
    app = importlib.import_module("main").app

    response = TestClient(app).get("/api/privacy/exposure")

    assert response.status_code == 200
    body = response.json()
    assert body["data_dir"] == str(root)
    assert set(body) >= {"gaps", "verdict", "resume_uploads", "resume_rows", "disk_encryption"}