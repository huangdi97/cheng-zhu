"""Controlled long-term memory write-back policy.

WHY: Review / Mock analysis must never auto-write LLM inference into the
candidate's long-term facts. Only whitelisted memory kinds may be persisted,
and LLM-derived interviewer inference (possible_focus / possible_concerns /
planner hints) must NEVER pass through this module — interviewer state is a
probabilistic hint for the planner, never a stored fact about the candidate.

# SAFETY:
# - user_confirmed_fact requires an explicit user confirmation flag;
#   no automatic path may set it on the candidate's behalf.
# - knowledge_weakness / repeated_topic / communication_profile are the only
#   kinds an automatic pipeline may write, and only via can_write_back.
"""
from __future__ import annotations

from core.logger import get_logger

_log = get_logger(__name__)

WRITABLE_KINDS = frozenset({"knowledge_weakness", "repeated_topic", "user_confirmed_fact", "communication_profile"})
# Kinds an automatic (non-interactive) pipeline may write without confirmation.
AUTO_WRITABLE_KINDS = frozenset({"knowledge_weakness", "repeated_topic", "communication_profile"})


def can_write_back(kind: str, *, user_confirmed: bool = False) -> bool:
    """True when `kind` is whitelisted AND (user confirmed OR the kind is
    allowed without confirmation). Denied attempts log a warning, never raise."""
    if kind not in WRITABLE_KINDS:
        _log.warning("memory write-back denied: unknown kind %r", kind)
        return False
    if not user_confirmed and kind not in AUTO_WRITABLE_KINDS:
        _log.warning("memory write-back denied: %r requires explicit user confirmation", kind)
        return False
    return True


def write_back_memory(
    kind: str,
    text: str,
    *,
    candidate_id: str = "",
    session_id: str = "",
    user_confirmed: bool = False,
) -> bool:
    """Guard via can_write_back, then persist via storage.intelligence.
    Returns True on write, False on denial. Never raises for policy reasons."""
    if not can_write_back(kind, user_confirmed=user_confirmed):
        return False
    from services.storage.intelligence import upsert_memory_item

    upsert_memory_item(kind, text, candidate_id=candidate_id, session_id=session_id)
    return True
