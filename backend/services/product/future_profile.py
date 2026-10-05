"""Personal Conversation Intelligence — Future Profile contracts (canonical §22).

Interview is the first proven profile; Conversation is the future second
profile. These are *contracts only*: no tables, no UI, no navigation. They
pin down the general vocabulary so v1.3 shared layers (Goal, Quick Notes,
Pins, Next Focus, product events) stay free of hard-coded ``job`` concepts.

Mapping kept open:
  Candidate -> Person · Job Goal -> Goal · Interview State -> Conversation State
  Interviewer State -> Counterparty State · Answer Planner -> Expression Planner
  InterviewPack -> Session Pack family
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConversationProfileKind(str, Enum):
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
    ANSWER_CUE = "ANSWER_CUE"  # the only kind the Interview runtime emits today (Fast Cue)
    QUESTION = "QUESTION"  # Closing Mode suggestions
    RISK = "RISK"  # fact-boundary warnings
    DELIVERY = "DELIVERY"
    CONTRIBUTION_OPPORTUNITY = "CONTRIBUTION_OPPORTUNITY"


class ConversationItemType(str, Enum):
    DECISION = "Decision"
    COMMITMENT = "Commitment"
    TASK = "Task"
    DEADLINE = "Deadline"
    RISK = "Risk"
    ASSUMPTION = "Assumption"
    OPEN_QUESTION = "OpenQuestion"
    PROPOSAL = "Proposal"
    OBJECTION = "Objection"
    METRIC = "Metric"
    STATUS = "Status"


class ConversationItemState(str, Enum):
    PROPOSED = "PROPOSED"
    AGREED = "AGREED"
    COMMITTED = "COMMITTED"
    DONE = "DONE"
    SUPERSEDED = "SUPERSEDED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ConversationProfile:
    """A kind of conversation the core can serve (Interview only today)."""

    key: ConversationProfileKind
    label: str
    guidance_kinds: tuple[GuidanceKind, ...]
    productized: bool


@dataclass
class ConversationGoal:
    """General form of a Goal: what the person wants from a series of conversations."""

    id: str
    profile: ConversationProfileKind
    title: str
    counterparty: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class CounterpartyState:
    concerns: list[str] = field(default_factory=list)
    disclosures: list[str] = field(default_factory=list)
    open_threads: list[str] = field(default_factory=list)


@dataclass
class ConversationState:
    phase: str
    counterparty: CounterpartyState = field(default_factory=CounterpartyState)
    items: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExpressionIntent:
    """What the person intends to express next (general form of an answer plan)."""

    kind: GuidanceKind
    summary: str
    sources: list[str] = field(default_factory=list)


PROFILES: tuple[ConversationProfile, ...] = (
    ConversationProfile(
        ConversationProfileKind.INTERVIEW,
        "面试",
        (GuidanceKind.ANSWER_CUE, GuidanceKind.QUESTION, GuidanceKind.RISK, GuidanceKind.DELIVERY),
        productized=True,
    ),
    ConversationProfile(ConversationProfileKind.MEETING, "会议（未来）", tuple(GuidanceKind), productized=False),
    ConversationProfile(
        ConversationProfileKind.PRESENTATION_QA, "演示 / Q&A（未来）", tuple(GuidanceKind), productized=False
    ),
    ConversationProfile(ConversationProfileKind.ONE_ON_ONE, "1:1（未来）", tuple(GuidanceKind), productized=False),
    ConversationProfile(
        ConversationProfileKind.DESIGN_REVIEW, "设计评审（未来）", tuple(GuidanceKind), productized=False
    ),
    ConversationProfile(
        ConversationProfileKind.CLIENT_CALL, "客户会（未来）", tuple(GuidanceKind), productized=False
    ),
    ConversationProfile(
        ConversationProfileKind.NEGOTIATION, "谈判（未来）", tuple(GuidanceKind), productized=False
    ),
)


def profile(kind: ConversationProfileKind) -> ConversationProfile:
    """Return the canonical contract for one conversation profile."""
    for item in PROFILES:
        if item.key is kind:
            return item
    raise KeyError(kind)


def interview_goal_as_conversation_goal(goal: dict[str, Any]) -> ConversationGoal:
    """Proves the current Goal maps onto the future-general contract without job-only fields."""
    return ConversationGoal(
        id=str(goal["id"]),
        profile=ConversationProfileKind.INTERVIEW,
        title=str(goal.get("title") or ""),
        counterparty=str(goal.get("company") or ""),
        attributes={"role": goal.get("role", ""), "stage": goal.get("stage", "")},
    )
