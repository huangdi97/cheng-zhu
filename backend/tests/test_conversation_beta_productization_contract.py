from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_packaged_smoke_covers_conversation_beta_loop() -> None:
    text = (ROOT / "scripts" / "packaged_smoke.py").read_text(encoding="utf-8")
    for token in (
        "/api/product/conversation/spaces",
        "/preflight",
        "/start",
        "/items",
        "/review",
        "/ask",
        "/api/product/conversation/search",
        "/end",
        "/export",
        "/context",
        "/history",
        "/diagnostics",
        "conversation_pack_persisted_after_restart",
        "REAL_CONVERSATION_USER_EVIDENCE_PENDING",
    ):
        assert token in text


def test_packaged_browserwindow_and_fallback_capture_conversation_beta() -> None:
    for relative in (
        "frontend/scripts/capture-v13-packaged-window-evidence.mjs",
        "frontend/scripts/capture-v13-packaged-web-evidence.mjs",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        for token in (
            "conversation_beta",
            "PACKAGED_BETA_ENGINEERING_EVIDENCE_NOT_REAL_USER_VALIDATION",
            "conversation-home",
            "conversation-spaces",
            "conversation-space",
            "conversation-continue-panel",
            "conversation-live",
            "conversation-session-pulse",
            "conversation-history",
            "conversation-diagnostics",
            "conversation-390-prepare",
        ):
            assert token in text, f"{relative} missing {token}"


def test_release_gate_rejects_missing_conversation_beta_evidence() -> None:
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    start = text.index("- name: Validate Conversation Beta packaged UI evidence contract")
    end = text.index("- name: Upload packaged runtime UI evidence", start)
    section = text[start:end]
    for token in (
        "conversation_beta",
        "space_id",
        "prior_session_id",
        "live_session_id",
        "PACKAGED_BETA_ENGINEERING_EVIDENCE_NOT_REAL_USER_VALIDATION",
        "expected >= 9 Conversation packaged UI captures",
    ):
        assert token in section
