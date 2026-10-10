from urllib.parse import parse_qs, urlparse

import pytest

from services.product import conversation_integrations, conversations
from services.product.google_drive_connector import (
    GoogleDriveProviderError,
    GoogleDriveRestAdapter,
    GoogleDriveTargetError,
    register_google_drive_adapter_from_env,
)


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.responses = []

    def queue(self, status, payload, headers=None):
        self.responses.append((status, headers or {}, payload))

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({
            "method": method,
            "url": url,
            "headers": dict(headers),
            "body": body,
            "timeout": timeout,
        })
        if not self.responses:
            raise AssertionError(f"Unexpected Google Drive request: {method} {url}")
        status, response_headers, payload = self.responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return status, response_headers, payload


def _connection(ref="provider:google-drive:env:CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN", folder="root"):
    return {
        "id": "ccn_gdrive_test",
        "provider_id": "GOOGLE_DRIVE",
        "credential_ref": ref,
        "granted_capabilities": ["docs.read"],
        "provider_scopes": ["https://www.googleapis.com/auth/drive.readonly"],
        "status": "CONNECTED",
        "account_hint": folder,
    }


def _folder(folder_id="folder-1", name="Architecture"):
    return {
        "id": folder_id,
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "trashed": False,
    }


def _file(file_id="doc-1", name="Architecture Brief", mime="application/vnd.google-apps.document"):
    return {
        "id": file_id,
        "name": name,
        "mimeType": mime,
        "modifiedTime": "2026-10-10T08:00:00Z",
        "webViewLink": f"https://drive.google.com/file/d/{file_id}/view?secret=no",
        "parents": ["folder-1"],
        "trashed": False,
        "size": "120",
        "md5Checksum": "md5-example",
        "capabilities": {"canDownload": True},
    }


def test_google_drive_adapter_requires_https_api_base():
    with pytest.raises(ValueError, match="HTTPS"):
        GoogleDriveRestAdapter(api_base="http://drive.test", transport=FakeTransport())


def test_google_drive_scope_is_drive_readonly(product_env):
    connection = conversation_integrations.create_connection(
        "GOOGLE_DRIVE",
        granted_capabilities=["docs.read"],
        credential_ref="provider:google-drive:env:CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN",
        account_hint="root",
    )
    assert connection["provider_scopes"] == ["https://www.googleapis.com/auth/drive.readonly"]
    with pytest.raises(ValueError, match="最小权限集合"):
        conversation_integrations.create_connection(
            "GOOGLE_DRIVE",
            granted_capabilities=["docs.read"],
            provider_scopes=["https://www.googleapis.com/auth/drive.metadata.readonly"],
            credential_ref="provider:google-drive:env:CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN",
        )


def test_google_drive_health_uses_external_env_credential_and_about_probe(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN", "ya29.drive_test_secret")
    transport = FakeTransport()
    transport.queue(200, {"user": {"displayName": "Lei", "emailAddress": "lei@example.test"}})
    adapter = GoogleDriveRestAdapter(transport=transport)

    assert adapter.health(None)["ok"] is True
    health = adapter.health(_connection(folder="folder-1"))
    assert health["ok"] is True
    assert health["account_hint"] == "folder-1"
    assert health["account_identity"] == "lei@example.test"
    assert health["verify"] == "ACCOUNT_READ_PROBE_ONLY"
    call = transport.calls[0]
    assert call["method"] == "GET"
    assert urlparse(call["url"]).path.endswith("/about")
    assert call["headers"]["Authorization"] == "Bearer ya29.drive_test_secret"


def test_google_drive_rejects_nonopaque_or_missing_env_reference(monkeypatch):
    adapter = GoogleDriveRestAdapter(transport=FakeTransport())
    with pytest.raises(ValueError, match="credential_ref"):
        adapter.health({**_connection(), "credential_ref": "ya29.secret"})
    monkeypatch.delenv("MISSING_DRIVE_TOKEN", raising=False)
    with pytest.raises(ValueError, match="未设置"):
        adapter.health({**_connection(), "credential_ref": "provider:google-drive:env:MISSING_DRIVE_TOKEN"})


def test_google_drive_sync_validates_folder_and_exports_workspace_docs(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN", "ya29.drive_test_secret")
    transport = FakeTransport()
    transport.queue(200, _folder())
    transport.queue(200, {"files": [_file()], "nextPageToken": ""})
    transport.queue(200, b"Architecture says rollback owner is Alex and migration uses v2.")
    adapter = GoogleDriveRestAdapter(transport=transport)

    result = adapter.read_context(
        connection=_connection(folder="folder-1"),
        capability="docs.read",
        query={"folder_id": "folder-1"},
        cursor="",
        limit=500,
    )
    assert result["folder_id"] == "folder-1"
    assert result["refresh"] == "FULL_TARGET_REFRESH"
    assert result["next_cursor"] == "gdrive-folder:folder-1"
    assert len(result["items"]) == 1
    doc = result["items"][0]
    assert doc["external_kind"] == "DOCUMENT"
    assert doc["external_id"] == "doc-1"
    assert "rollback owner is Alex" in doc["excerpt"]
    assert doc["metadata"]["content_available"] is True
    assert doc["metadata"]["export_mime"] == "text/plain"
    assert doc["metadata"]["content_scope"] == "TEXT_EXPORT_EXCERPT_20K"
    assert doc["metadata"]["partial_content"] is False
    assert doc["metadata"]["retrieval_scope"] == "FIRST_20000_CHARS"
    assert doc["metadata"]["source_text_bytes"] > 0
    assert len(doc["metadata"]["full_content_digest_sha256"]) == 64

    folder_call, list_call, export_call = transport.calls
    assert urlparse(folder_call["url"]).path.endswith("/files/folder-1")
    assert parse_qs(urlparse(folder_call["url"]).query)["supportsAllDrives"] == ["true"]
    params = parse_qs(urlparse(list_call["url"]).query)
    assert params["q"] == ["'folder-1' in parents and trashed = false"]
    assert params["pageSize"] == ["100"]
    assert params["supportsAllDrives"] == ["true"]
    assert params["includeItemsFromAllDrives"] == ["true"]
    export_params = parse_qs(urlparse(export_call["url"]).query)
    assert urlparse(export_call["url"]).path.endswith("/files/doc-1/export")
    assert export_params["mimeType"] == ["text/plain"]


def test_google_drive_folder_sync_consumes_all_pages_before_returning(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN", "ya29.drive_test_secret")
    transport = FakeTransport()
    first = _file("doc-1", "First")
    second = _file("doc-2", "Second")
    transport.queue(200, _folder())
    transport.queue(200, {"files": [first], "nextPageToken": "page-2"})
    transport.queue(200, {"files": [second]})
    transport.queue(200, b"first text")
    transport.queue(200, b"second text")
    adapter = GoogleDriveRestAdapter(transport=transport)

    result = adapter.read_context(
        connection=_connection(folder="folder-1"),
        capability="docs.read",
        query={"folder_id": "folder-1"},
        cursor="stale-ignored-for-full-refresh",
        limit=500,
    )
    assert [x["external_id"] for x in result["items"]] == ["doc-1", "doc-2"]
    first_list = parse_qs(urlparse(transport.calls[1]["url"]).query)
    second_list = parse_qs(urlparse(transport.calls[2]["url"]).query)
    assert "pageToken" not in first_list
    assert second_list["pageToken"] == ["page-2"]


def test_google_drive_sheets_are_explicitly_partial_first_sheet_csv(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN", "ya29.drive_test_secret")
    transport = FakeTransport()
    sheet = _file("sheet-1", "Decision Matrix", "application/vnd.google-apps.spreadsheet")
    transport.queue(200, _folder())
    transport.queue(200, {"files": [sheet]})
    transport.queue(200, b"Option,Score\nA,8\nB,9\n")
    adapter = GoogleDriveRestAdapter(transport=transport)

    result = adapter.read_context(
        connection=_connection(folder="folder-1"),
        capability="docs.read",
        query={"folder_id": "folder-1"},
        cursor="",
        limit=500,
    )
    snap = result["items"][0]
    assert snap["metadata"]["export_mime"] == "text/csv"
    assert snap["metadata"]["partial_content"] is True
    assert snap["metadata"]["content_scope"] == "FIRST_SHEET_CSV_EXCERPT_20K"
    assert snap["metadata"]["retrieval_scope"] == "FIRST_20000_CHARS"
    assert len(snap["metadata"]["full_content_digest_sha256"]) == 64
    assert "Option,Score" in snap["excerpt"]




def test_google_drive_full_content_digest_changes_revision_even_when_first_20k_is_identical(product_env, monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN", "ya29.drive_test_secret")
    prefix = "A" * 20_000
    first_body = (prefix + " tail-one").encode()
    second_body = (prefix + " tail-two").encode()
    transport = FakeTransport()
    adapter = GoogleDriveRestAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    transport.queue(200, {"user": {"emailAddress": "lei@example.test"}})
    connection = conversation_integrations.create_connection(
        "GOOGLE_DRIVE",
        granted_capabilities=["docs.read"],
        credential_ref="provider:google-drive:env:CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN",
        account_hint="folder-1",
    )
    conversation_integrations.verify_and_connect(connection["id"])
    space = conversations.create_space("Revision Truth", "DESIGN_REVIEW")

    for body in (first_body, second_body):
        transport.queue(200, {"user": {"emailAddress": "lei@example.test"}})
        transport.queue(200, _folder())
        transport.queue(200, {"files": [_file()]})
        transport.queue(200, body)
        result = conversation_integrations.sync_connection(
            connection["id"],
            space["id"],
            capabilities=["docs.read"],
            query={"folder_id": "folder-1"},
            limit=500,
        )
        assert result["snapshots"][0]["excerpt"] == prefix

    rows = conversation_integrations.list_snapshots(space["id"], connection_id=connection["id"])
    assert len(rows) == 2
    assert rows[0]["excerpt"] == rows[1]["excerpt"] == prefix
    assert rows[0]["metadata"]["full_content_digest_sha256"] != rows[1]["metadata"]["full_content_digest_sha256"]
    assert rows[0]["content_hash"] != rows[1]["content_hash"]


def test_google_drive_binary_file_is_metadata_only_not_fake_read(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN", "ya29.drive_test_secret")
    transport = FakeTransport()
    pdf = _file("pdf-1", "Spec.pdf", "application/pdf")
    transport.queue(200, _folder())
    transport.queue(200, {"files": [pdf]})
    adapter = GoogleDriveRestAdapter(transport=transport)

    result = adapter.read_context(
        connection=_connection(folder="folder-1"),
        capability="docs.read",
        query={"folder_id": "folder-1"},
        cursor="",
        limit=500,
    )
    snap = result["items"][0]
    assert snap["excerpt"] == ""
    assert snap["metadata"]["content_available"] is False
    assert snap["metadata"]["content_scope"] == "METADATA_ONLY"
    assert snap["metadata"]["content_unavailable_reason"] == "UNSUPPORTED_OR_BINARY"
    assert len(transport.calls) == 2  # folder probe + list, no fake PDF content read


def test_google_drive_text_blob_uses_alt_media(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN", "ya29.drive_test_secret")
    transport = FakeTransport()
    blob = _file("md-1", "notes.md", "text/markdown")
    transport.queue(200, _folder())
    transport.queue(200, {"files": [blob]})
    transport.queue(200, b"# Rollout\nOwner: Alex")
    adapter = GoogleDriveRestAdapter(transport=transport)

    result = adapter.read_context(
        connection=_connection(folder="folder-1"),
        capability="docs.read",
        query={"folder_id": "folder-1"},
        cursor="",
        limit=500,
    )
    assert result["items"][0]["metadata"]["content_scope"] == "TEXT_BLOB_EXCERPT_20K"
    params = parse_qs(urlparse(transport.calls[2]["url"]).query)
    assert params["alt"] == ["media"]


def test_google_drive_target_failure_is_nonfatal_but_auth_failure_is_fatal(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN", "ya29.drive_test_secret")
    adapter = GoogleDriveRestAdapter(transport=FakeTransport())

    adapter._transport.queue(404, GoogleDriveProviderError(404, "Google Drive HTTP 404: not found"))
    with pytest.raises(GoogleDriveTargetError):
        adapter.read_context(
            connection=_connection(folder="missing"),
            capability="docs.read",
            query={"folder_id": "missing"},
            cursor="",
            limit=500,
        )

    adapter._transport.queue(401, GoogleDriveProviderError(401, "Google Drive HTTP 401: invalid token"))
    with pytest.raises(GoogleDriveProviderError):
        adapter.read_context(
            connection=_connection(folder="root"),
            capability="docs.read",
            query={"folder_id": "root"},
            cursor="",
            limit=500,
        )




def test_google_drive_more_than_500_files_fails_before_any_content_download(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN", "ya29.drive_test_secret")
    transport = FakeTransport()
    transport.queue(200, _folder())
    # Six pages make the adapter cross the 500 direct-child safety ceiling.
    for page in range(6):
        rows = [_file(f"doc-{page}-{i}", f"Doc {page}-{i}") for i in range(100)]
        transport.queue(200, {
            "files": rows,
            "nextPageToken": f"page-{page + 2}" if page < 5 else "",
        })
    adapter = GoogleDriveRestAdapter(transport=transport)

    with pytest.raises(ValueError, match="超过安全上限 500"):
        adapter.read_context(
            connection=_connection(folder="folder-1"),
            capability="docs.read",
            query={"folder_id": "folder-1"},
            cursor="",
            limit=500,
        )
    # 1 folder probe + 6 list pages; no export/media request should happen.
    assert len(transport.calls) == 7
    assert not any("/export" in call["url"] or "alt=media" in call["url"] for call in transport.calls)


def test_google_drive_target_must_be_an_actual_nontrashed_folder(monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN", "ya29.drive_test_secret")
    transport = FakeTransport()
    transport.queue(200, _file("not-folder", "Not a folder", "application/vnd.google-apps.document"))
    adapter = GoogleDriveRestAdapter(transport=transport)
    with pytest.raises(ValueError, match="不是 folder"):
        adapter.read_context(
            connection=_connection(folder="not-folder"),
            capability="docs.read",
            query={"folder_id": "not-folder"},
            cursor="",
            limit=500,
        )

    transport2 = FakeTransport()
    trashed = _folder("folder-trash")
    trashed["trashed"] = True
    transport2.queue(200, trashed)
    adapter2 = GoogleDriveRestAdapter(transport=transport2)
    with pytest.raises(ValueError, match="回收站"):
        adapter2.read_context(
            connection=_connection(folder="folder-trash"),
            capability="docs.read",
            query={"folder_id": "folder-trash"},
            cursor="",
            limit=500,
        )


def test_google_drive_registration_is_explicit_opt_in(product_env, monkeypatch):
    conversation_integrations.clear_adapters_for_tests()
    monkeypatch.delenv("CHENGZHU_GOOGLE_DRIVE_CONNECTOR_ENABLE", raising=False)
    assert register_google_drive_adapter_from_env()["registered"] is False
    row = next(x for x in conversation_integrations.catalog() if x["provider_id"] == "GOOGLE_DRIVE")
    assert row["adapter_available"] is False
    assert row["sync"] == "FULL_TARGET_REFRESH"

    monkeypatch.setenv("CHENGZHU_GOOGLE_DRIVE_CONNECTOR_ENABLE", "1")
    registered = register_google_drive_adapter_from_env()
    assert registered["registered"] is True
    row = next(x for x in conversation_integrations.catalog() if x["provider_id"] == "GOOGLE_DRIVE")
    assert row["adapter_available"] is True
    assert row["write_capabilities"] == []


def test_google_drive_integration_boundary_stores_immutable_document_and_pack_freezes_it(product_env, monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN", "ya29.drive_test_secret")
    transport = FakeTransport()
    adapter = GoogleDriveRestAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    # Verify account token through about.get.
    transport.queue(200, {"user": {"emailAddress": "lei@example.test"}})
    connection = conversation_integrations.create_connection(
        "GOOGLE_DRIVE",
        display_name="Design Docs",
        granted_capabilities=["docs.read"],
        credential_ref="provider:google-drive:env:CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN",
        account_hint="folder-1",
    )
    connected = conversation_integrations.verify_and_connect(connection["id"])
    assert connected["status"] == "CONNECTED"

    space = conversations.create_space("Architecture", "DESIGN_REVIEW")

    # Sync re-checks account health, then proves the explicit folder target.
    transport.queue(200, {"user": {"emailAddress": "lei@example.test"}})
    transport.queue(200, _folder())
    transport.queue(200, {"files": [_file()]})
    transport.queue(200, b"Architecture decision source: rollout uses staged migration.")
    synced = conversation_integrations.sync_connection(
        connection["id"],
        space["id"],
        capabilities=["docs.read"],
        query={"folder_id": "folder-1"},
        limit=500,
    )
    snapshot = synced["snapshots"][0]
    assert snapshot["external_kind"] == "DOCUMENT"
    assert snapshot["capability"] == "docs.read"
    assert snapshot["excerpt"].startswith("Architecture decision source")
    assert snapshot["source_url"] == "https://drive.google.com/file/d/doc-1/view"
    assert "ya29.drive_test_secret" not in str(snapshot)
    assert "secret=no" not in str(snapshot)

    conversations.update_space(space["id"], {"selected_connector_snapshot_ids": [snapshot["id"]]})
    session = conversations.create_session(
        space["id"],
        consent_ack=True,
        policy={"connector_permissions": ["docs.read"]},
    )
    started = conversations.start_session(session["id"])
    frozen = started["pack"]["payload"]["connector_snapshots"]
    assert len(frozen) == 1
    assert frozen[0]["id"] == snapshot["id"]
    assert frozen[0]["content_hash"] == snapshot["content_hash"]
    assert started["pack"]["payload"]["connector_runtime"]["grants"][0]["provider_id"] == "GOOGLE_DRIVE"


def test_google_drive_sync_folder_target_failure_keeps_verified_connection_connected(product_env, monkeypatch):
    monkeypatch.setenv("CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN", "ya29.drive_test_secret")
    transport = FakeTransport()
    adapter = GoogleDriveRestAdapter(transport=transport)
    conversation_integrations.register_adapter(adapter)

    transport.queue(200, {"user": {"emailAddress": "lei@example.test"}})
    connection = conversation_integrations.create_connection(
        "GOOGLE_DRIVE",
        granted_capabilities=["docs.read"],
        credential_ref="provider:google-drive:env:CHENGZHU_GOOGLE_DRIVE_ACCESS_TOKEN",
        account_hint="folder-1",
    )
    conversation_integrations.verify_and_connect(connection["id"])
    space = conversations.create_space("Target Error", "DESIGN_REVIEW")

    transport.queue(200, {"user": {"emailAddress": "lei@example.test"}})
    transport.queue(404, GoogleDriveProviderError(404, "Google Drive HTTP 404: Not Found"))
    with pytest.raises(ValueError, match="404"):
        conversation_integrations.sync_connection(
            connection["id"],
            space["id"],
            capabilities=["docs.read"],
            query={"folder_id": "missing"},
            limit=500,
        )
    after = next(x for x in conversation_integrations.list_connections() if x["id"] == connection["id"])
    assert after["status"] == "CONNECTED"
    assert "404" in after["last_error"]
