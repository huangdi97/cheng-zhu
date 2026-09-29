"""Tests for the Stage P AI policy gate and intelligence export."""
from types import SimpleNamespace

from services.intelligence.policy import (
    auto_answer_allowed,
    live_guidance_allowed,
    policy_block_payload,
    resolve_policy_mode,
)
from services.intelligence.types import AIPolicyMode
from services.question_turn_parser import is_auto_answer_enabled


def _cfg(policy_mode: str) -> SimpleNamespace:
    cfg = SimpleNamespace()
    cfg.ai_policy_mode = policy_mode
    cfg.assist_auto_answer_mode = "smart"
    cfg.auto_detect = True
    return cfg


def test_resolve_policy_mode_accepts_all_four_values():
    for raw, expected in (
        ("AI_FORBIDDEN", AIPolicyMode.AI_FORBIDDEN),
        ("AI_LIMITED", AIPolicyMode.AI_LIMITED),
        ("AI_ALLOWED", AIPolicyMode.AI_ALLOWED),
        ("AI_EXPECTED", AIPolicyMode.AI_EXPECTED),
    ):
        assert resolve_policy_mode(raw) == expected


def test_unknown_policy_mode_defaults_to_permissive():
    assert resolve_policy_mode("bogus") == AIPolicyMode.AI_ALLOWED
    assert resolve_policy_mode("") == AIPolicyMode.AI_ALLOWED
    assert resolve_policy_mode(None) == AIPolicyMode.AI_ALLOWED


def test_live_guidance_blocked_only_when_forbidden():
    assert not live_guidance_allowed(_cfg("AI_FORBIDDEN"))
    assert live_guidance_allowed(_cfg("AI_LIMITED"))
    assert live_guidance_allowed(_cfg("AI_ALLOWED"))
    assert live_guidance_allowed(_cfg("AI_EXPECTED"))


def test_auto_answer_disabled_for_limited_and_forbidden():
    assert not auto_answer_allowed(_cfg("AI_FORBIDDEN"))
    assert not auto_answer_allowed(_cfg("AI_LIMITED"))
    assert auto_answer_allowed(_cfg("AI_ALLOWED"))
    assert auto_answer_allowed(_cfg("AI_EXPECTED"))


def test_is_auto_answer_enabled_respects_policy():
    assert not is_auto_answer_enabled(_cfg("AI_FORBIDDEN"))
    assert not is_auto_answer_enabled(_cfg("AI_LIMITED"))
    assert is_auto_answer_enabled(_cfg("AI_ALLOWED"))
    assert is_auto_answer_enabled(_cfg("AI_EXPECTED"))


def test_is_auto_answer_enabled_off_mode_still_wins():
    cfg = _cfg("AI_ALLOWED")
    cfg.assist_auto_answer_mode = "off"
    assert not is_auto_answer_enabled(cfg)


def test_policy_block_payload_never_leaks_candidate_data():
    payload = policy_block_payload()
    assert payload["type"] == "answer_policy_blocked"
    assert "AI_FORBIDDEN" in payload["message"]
    # PRIVACY: must not contain resume/claim/answer content.
    assert "简历" not in payload["message"] or "面试政策" in payload["message"]


def test_export_endpoint_registered():
    from api.intelligence.router import router

    paths = {route.path for route in router.routes}
    assert "/export" in paths