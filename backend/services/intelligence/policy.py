"""Interview AI policy awareness (canonical Stage P / section 47).

Semantics per policy mode:
- AI_FORBIDDEN: Prepare/Mock/Review keep working (they never call the live
  answer path), but realtime live AI guidance is disabled by default.
- AI_LIMITED: live guidance allowed, auto-answer off (transcription only).
- AI_ALLOWED / AI_EXPECTED: full realtime guidance.

 INVARIANT:
  - This gate is enforced in the answer path itself (server-side), never by
    hiding a button in the UI.
"""
from __future__ import annotations

from services.intelligence.types import AIPolicyMode

_ALIASES = {
    "AI_FORBIDDEN": AIPolicyMode.AI_FORBIDDEN,
    "AI_LIMITED": AIPolicyMode.AI_LIMITED,
    "AI_ALLOWED": AIPolicyMode.AI_ALLOWED,
    "AI_EXPECTED": AIPolicyMode.AI_EXPECTED,
}


def resolve_policy_mode(raw: str | None) -> AIPolicyMode:
    """Normalize the config string to the enum; unknown values default to
    the permissive mode so a typo never silently blocks guidance."""
    value = str(raw or "").strip().upper()
    return _ALIASES.get(value, AIPolicyMode.AI_ALLOWED)


def live_guidance_allowed(cfg) -> bool:
    """Whether realtime AI guidance may run for the current session config."""
    return resolve_policy_mode(getattr(cfg, "ai_policy_mode", "")) != AIPolicyMode.AI_FORBIDDEN


def live_guidance_allowed_for_pack(pack, cfg) -> bool:
    """R2: a frozen InterviewPack carries the session's AI policy and is
    authoritative; an unfrozen session falls back to the config value."""
    if pack is not None and getattr(pack, "frozen", False):
        return resolve_policy_mode(getattr(pack, "ai_policy", "")) != AIPolicyMode.AI_FORBIDDEN
    return live_guidance_allowed(cfg)


HUMAN_POLICIES = ("HUMAN_FORBIDDEN", "HUMAN_PRACTICE_ONLY", "HUMAN_ALLOWED")


def resolve_human_policy(raw: str | None) -> str:
    """Unknown values fall back to the conservative default."""
    value = str(raw or "").strip().upper()
    return value if value in HUMAN_POLICIES else "HUMAN_PRACTICE_ONLY"


def human_coach_allowed(human_policy: str | None, *, session_kind: str) -> bool:
    """Human assistance is a separate axis from AI policy.

    session_kind: "practice" (Mock / Rehearse / coaching) or "live".
    AI_ALLOWED never implies HUMAN_ALLOWED; only the human policy decides.
    """
    policy = resolve_human_policy(human_policy)
    if policy == "HUMAN_FORBIDDEN":
        return False
    if policy == "HUMAN_PRACTICE_ONLY":
        return session_kind == "practice"
    return True


def auto_answer_allowed(cfg) -> bool:
    """Whether auto-answer (without explicit ask) may run; AI_LIMITED and
    AI_FORBIDDEN disable the smart auto-path."""
    mode = resolve_policy_mode(getattr(cfg, "ai_policy_mode", ""))
    return mode in {AIPolicyMode.AI_ALLOWED, AIPolicyMode.AI_EXPECTED}


def policy_block_payload() -> dict:
    """Broadcast payload when live guidance is policy-blocked.

    PRIVACY: never leaks candidate data; the message states only the policy
    state so a misconfigured AI_FORBIDDEN session is understandable.
    """
    return {
        "type": "answer_policy_blocked",
        "message": "当前会话标记为 AI_FORBIDDEN：实时 AI 引导已按策略关闭，请确认面试政策后重试。",
    }