"""Future-compatible Personal Conversation Intelligence contracts.

v1.x remains Interview-first. These types intentionally contain no persistence,
routing, Meeting UI, or runtime orchestration; they preserve the abstraction
boundary required by the v1.3-R2 canonical so the verified Interview Core does
not become impossible to generalize later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConversationProfile(str, Enum):
    INTERVIEW = "INTERVIEW"
    MEETING = "MEETING"
    PRESENTATION_QA = "PRESENTATION_QA"
    ONE_ON_ONE = "ONE_ON_ONE"
    DESIGN_REVIEW = "DESIGN_REVIEW"
    CLIENT_CALL = "CLIENT_CALL"
    NEGOTIATION = "NEGOTIATION"


class GuidanceKind(str, Enum):
    RECALL = "RECALL"
    TALKING_POINT = "TALKING_POINT"
    ANSWER_CUE = "ANSWER_CUE"
    QUESTION = "QUESTION"
    RISK = "RISK"
    DELIVERY = "DELIVERY"
    CONTRIBUTION_OPPORTUNITY = "CONTRIBUTION_OPPORTUNITY"


class ExpressionIntent(str, Enum):
    ANSWER = "ANSWER"
    ADD_CONTEXT = "ADD_CONTEXT"
    ASK = "ASK"
    CLARIFY = "CLARIFY"
    CHALLENGE = "CHALLENGE"
    WARN = "WARN"
    SUMMARIZE = "SUMMARIZE"
    STAY_SILENT = "STAY_SILENT"


class ConversationFactKind(str, Enum):
    DECISION = "DECISION"
    COMMITMENT = "COMMITMENT"
    TASK = "TASK"
    DEADLINE = "DEADLINE"
    RISK = "RISK"
    ASSUMPTION = "ASSUMPTION"
    OPEN_QUESTION = "OPEN_QUESTION"
    PROPOSAL = "PROPOSAL"
    OBJECTION = "OBJECTION"
    METRIC = "METRIC"
    STATUS = "STATUS"


class ConversationFactState(str, Enum):
    PROPOSED = "PROPOSED"
    AGREED = "AGREED"
    COMMITTED = "COMMITTED"
    DONE = "DONE"
    SUPERSEDED = "SUPERSEDED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ConversationGoal:
    id: str
    title: str
    objective: str = ""
    profile: ConversationProfile = ConversationProfile.INTERVIEW
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CounterpartyState:
    """Observed interaction state only; never inferred private mental state."""

    id: str = ""
    display_name: str = ""
    role: str = ""
    observed_priorities: tuple[str, ...] = ()
    explicit_constraints: tuple[str, ...] = ()
    open_threads: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConversationState:
    profile: ConversationProfile
    goal_id: str
    current_topic: str = ""
    current_speaker_id: str = ""
    active_question: str = ""
    open_threads: tuple[str, ...] = ()
    counterparties: tuple[CounterpartyState, ...] = ()


@dataclass(frozen=True)
class ConversationGuidance:
    kind: GuidanceKind
    text: str
    intent: ExpressionIntent
    source_refs: tuple[str, ...] = ()
    confidence: float | None = None
    interrupt_cost: float | None = None
