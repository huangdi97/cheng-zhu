from services.product import conversation_connectors


def setup_function():
    conversation_connectors.clear_registry()


def teardown_function():
    conversation_connectors.clear_registry()


def test_connector_registry_fails_closed_when_no_provider_exists():
    resolved = conversation_connectors.resolve_read_permissions(["calendar.read"])
    assert resolved["ok"] is False
    assert resolved["grants"] == []
    assert resolved["blocked"] == [
        {"capability": "calendar.read", "reason": "NO_AVAILABLE_PROVIDER"}
    ]


def test_connector_registry_grants_only_exact_healthy_capabilities():
    conversation_connectors.register_provider(
        "google-read",
        ["calendar.read", "docs.read"],
        account_label="work@example.com",
    )
    resolved = conversation_connectors.resolve_read_permissions(
        ["calendar.read", "docs.read"]
    )
    assert resolved["ok"] is True
    assert [x["provider_id"] for x in resolved["grants"]] == [
        "google-read",
        "google-read",
    ]

    missing = conversation_connectors.resolve_read_permissions(["mail.read"])
    assert missing["ok"] is False
    assert missing["blocked"][0]["reason"] == "NO_AVAILABLE_PROVIDER"


def test_session_permissions_cannot_smuggle_write_capabilities():
    conversation_connectors.register_provider(
        "writer",
        ["email.send", "task.create"],
    )
    resolved = conversation_connectors.resolve_read_permissions(["email.send"])
    assert resolved["ok"] is False
    assert resolved["grants"] == []
    assert resolved["blocked"] == [
        {
            "capability": "email.send",
            "reason": "WRITE_REQUIRES_EXPLICIT_EXECUTION_FLOW",
        }
    ]


def test_unknown_capability_is_rejected_deterministically():
    resolved = conversation_connectors.resolve_read_permissions(["crm.magic"])
    assert resolved["ok"] is False
    assert resolved["blocked"] == [
        {"capability": "crm.magic", "reason": "UNKNOWN_CAPABILITY"}
    ]


def test_connector_diagnostics_never_contains_secrets():
    conversation_connectors.register_provider(
        "calendar",
        ["calendar.read"],
        account_label="Personal Calendar",
    )
    diag = conversation_connectors.diagnostics()
    assert diag["provider_count"] == 1
    assert diag["available_capabilities"] == ["calendar.read"]
    assert diag["providers"][0]["account_label"] == "Personal Calendar"
    assert "token" not in str(diag).lower()
    assert "secret" not in str(diag).lower()


def test_connector_resolution_deduplicates_permissions_and_ignores_unrelated_providers():
    conversation_connectors.register_provider("calendar", ["calendar.read"])
    conversation_connectors.register_provider("docs", ["docs.read"])
    resolved = conversation_connectors.resolve_read_permissions([
        "calendar.read",
        "calendar.read",
    ])
    assert resolved["requested"] == ["calendar.read"]
    assert [x["provider_id"] for x in resolved["grants"]] == ["calendar"]
    assert [x["provider_id"] for x in resolved["providers"]] == ["calendar"]
