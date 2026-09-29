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