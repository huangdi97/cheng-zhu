"""Open-world reasoning: No resume evidence is NOT the same as no answer.

The fundamental fork from resume-only products (master doc section 18): the
router must allow knowledge questions with zero personal evidence to proceed
normally, while experience-verification questions without evidence keep the
truth boundary and must not claim experience.
"""
from __future__ import annotations

from dataclasses import dataclass

from services.intelligence.types import QuestionType, ResponseMode

# Question types that never require personal evidence.
_KNOWLEDGE_ONLY_TYPES = frozenset(
    {
        QuestionType.KNOWLEDGE,
        QuestionType.CODING,
        QuestionType.SYSTEM_DESIGN,
        QuestionType.OOD,
        QuestionType.DEBUGGING,
        QuestionType.CASE,
        QuestionType.PRODUCT,
        QuestionType.BUSINESS,
        QuestionType.COMPANY,
        QuestionType.META,
    }
)


@dataclass(frozen=True)
class WorldRoute:
    """Routing decision for one question."""

    allow_personal_evidence: bool
    allow_world_knowledge: bool
    allow_reasoning: bool
    deny_answer: bool
    reason: str = ""

    def payload(self) -> dict:
        return {
            "allow_personal_evidence": self.allow_personal_evidence,
            "allow_world_knowledge": self.allow_world_knowledge,
            "allow_reasoning": self.allow_reasoning,
            "deny_answer": self.deny_answer,
            "reason": self.reason,
        }


def route_open_world(
    qtype: QuestionType,
    *,
    has_personal_evidence: bool,
    personal_fact_required: bool = False,
    hypothetical: bool = False,
) -> WorldRoute:
    """Open-world routing for one question.

    Rules (master doc 18):
    - Knowledge questions with zero personal evidence proceed normally
      (KNOWLEDGE mode, world knowledge allowed).
    - Experience-verification without evidence keeps the truth boundary and
      routes to EXPERIENCE_BOUNDARY_KNOWLEDGE — but still answers.
    - Hypothetical questions use conditional language and open design.
    - deny_answer is only for empty input, never for missing evidence.
    """
    if qtype in _KNOWLEDGE_ONLY_TYPES:
        return WorldRoute(
            allow_personal_evidence=False,
            allow_world_knowledge=True,
            allow_reasoning=True,
            deny_answer=False,
            reason="knowledge question: personal evidence not required",
        )
    if hypothetical:
        return WorldRoute(
            allow_personal_evidence=has_personal_evidence,
            allow_world_knowledge=True,
            allow_reasoning=True,
            deny_answer=False,
            reason="hypothetical: conditional reasoning allowed",
        )
    if personal_fact_required and not has_personal_evidence:
        return WorldRoute(
            allow_personal_evidence=False,
            allow_world_knowledge=True,
            allow_reasoning=True,
            deny_answer=False,
            reason="experience boundary: no evidence -> boundary + knowledge, still answer",
        )
    return WorldRoute(
        allow_personal_evidence=True,
        allow_world_knowledge=True,
        allow_reasoning=True,
        deny_answer=False,
        reason="personal experience with evidence",
    )


def expected_mode(route: WorldRoute, base_mode: ResponseMode) -> ResponseMode:
    """Response mode for an open-world route."""
    if route.deny_answer:
        return base_mode
    if route.reason.startswith("experience boundary"):
        return ResponseMode.EXPERIENCE_BOUNDARY_KNOWLEDGE
    if route.reason.startswith("hypothetical"):
        return ResponseMode.HYPOTHETICAL
    return base_mode
