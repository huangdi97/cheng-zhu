"""Chengzhu v2.0 Personal Conversation Intelligence executable contracts.

This module stays storage/UI agnostic, but it is no longer a hypothetical
future-profile placeholder: Conversation runtime, routes, product.db entities
and product UI exist.  The contract deliberately separates productized launch
wedges from templates whose specialized behavior still needs validation.

Truth rule:
    a model candidate is not a confirmed conversation fact.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


CONVERSATION_CONTRACT_VERSION = "v2.0-R1"


class ConversationProfileKind(str, Enum):
    INTERVIEW = "INTERVIEW"
    PROJECT_SYNC = "PROJECT_SYNC"
    DESIGN_REVIEW = "DESIGN_REVIEW"
    PRESENTATION_QA = "PRESENTATION_QA"
    ONE_ON_ONE = "ONE_ON_ONE"
    CLIENT_CALL = "CLIENT_CALL"
    NEGOTIATION = "NEGOTIATION"
    # Kept as a compatibility umbrella for older v1 future-profile references.
    MEETING = "MEETING"


class GuidanceKind(str, Enum):
    RECALL = "RECALL"
    TALKING_POINT = "TALKING_POINT"
    ANSWER_CUE = "ANSWER_CUE"
    QUESTION = "QUESTION"
    RISK = "RISK"
    DELIVERY = "DELIVERY"
    CONTRIBUTION_OPPORTUNITY = "CONTRIBUTION_OPPORTUNITY"


class AssistanceMode(str, Enum):
    QUIET = "QUIET"
    BALANCED = "BALANCED"
    ACTIVE = "ACTIVE"
    PRESENTATION = "PRESENTATION"
    ONE_ON_ONE = "ONE_ON_ONE"


class ExpressionAction(str, Enum):
    SILENT = "SILENT"
    ANSWER = "ANSWER"
    RECALL = "RECALL"
    ADD_TALKING_POINT = "ADD_TALKING_POINT"
    ASK_QUESTION = "ASK_QUESTION"
    FLAG_RISK = "FLAG_RISK"
    CLARIFY = "CLARIFY"
    SUMMARIZE = "SUMMARIZE"
    COMMIT_NEXT_STEP = "COMMIT_NEXT_STEP"


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


class EpistemicStatus(str, Enum):
    OBSERVED = "OBSERVED"
    USER_CONFIRMED = "USER_CONFIRMED"
    SOURCE_CONFIRMED = "SOURCE_CONFIRMED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class ReviewStatus(str, Enum):
    AI_EXTRACTED = "AI_EXTRACTED"
    USER_CONFIRMED = "USER_CONFIRMED"
    USER_EDITED = "USER_EDITED"
    USER_REJECTED = "USER_REJECTED"
    SOURCE_CONFIRMED = "SOURCE_CONFIRMED"


class CaptureMode(str, Enum):
    TRANSCRIPT = "TRANSCRIPT"
    NOTES_ONLY = "NOTES_ONLY"
    NO_CAPTURE = "NO_CAPTURE"


class ProcessingMode(str, Enum):
    LOCAL = "LOCAL"
    CLOUD = "CLOUD"
    OFF = "OFF"


class AiAssistancePolicy(str, Enum):
    FORBIDDEN = "AI_FORBIDDEN"
    LIMITED = "AI_LIMITED"
    ALLOWED = "AI_ALLOWED"
    EXPECTED = "AI_EXPECTED"


class HumanAssistancePolicy(str, Enum):
    FORBIDDEN = "HUMAN_FORBIDDEN"
    PRACTICE_ONLY = "HUMAN_PRACTICE_ONLY"
    ALLOWED = "HUMAN_ALLOWED"


@dataclass
class ConversationSessionPolicy:
    transcript_retention: str = "SPACE_POLICY"
    screen_context: str = "OFF"
    ai_assistance: AiAssistancePolicy = AiAssistancePolicy.ALLOWED
    human_assistance: HumanAssistancePolicy = HumanAssistancePolicy.PRACTICE_ONLY
    share_privacy: str = "OFF"
    external_writeback: str = "REVIEW_REQUIRED"
    participant_consent_status: str = "NOT_RECORDED"
    participant_transparency_plan: str = "NOT_RECORDED"
    connector_permissions: list[str] = field(default_factory=list)
    speaker_biometric_identity: str = "OFF"
    emotion_sentiment_profiling: str = "OFF"
    hidden_intent_claims: str = "OFF"


class SourceKind(str, Enum):
    TRANSCRIPT_SEGMENT = "TRANSCRIPT_SEGMENT"
    USER_NOTE = "USER_NOTE"
    QUICK_NOTE = "QUICK_NOTE"
    DOCUMENT = "DOCUMENT"
    CALENDAR = "CALENDAR"
    CONNECTOR = "CONNECTOR"
    SCREEN_CONTEXT = "SCREEN_CONTEXT"
    USER_ASSERTION = "USER_ASSERTION"
    MODEL_INFERENCE = "MODEL_INFERENCE"


@dataclass(frozen=True)
class SourceRef:
    id: str
    kind: SourceKind
    excerpt: str = ""
    uri: str = ""
    session_id: str = ""
    timestamp_ms: int | None = None
    visibility: str = "PRIVATE"


@dataclass
class ConversationProfile:
    key: ConversationProfileKind
    label: str
    guidance_kinds: tuple[GuidanceKind, ...]
    productized: bool
    default_mode: AssistanceMode = AssistanceMode.BALANCED
    design_complete: bool = True
    runtime_available: bool = False
    launch_wedge: bool = False
    specialized_behavior_validated: bool = False


@dataclass
class ConversationSpace:
    id: str
    profile: ConversationProfileKind
    title: str
    default_mode: AssistanceMode = AssistanceMode.BALANCED
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationGoal:
    id: str
    profile: ConversationProfileKind
    title: str
    counterparty: str = ""
    space_id: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class CounterpartyObservation:
    kind: str
    value: str
    source_refs: list[SourceRef] = field(default_factory=list)
    confidence: float = 0.0
    epistemic_status: EpistemicStatus = EpistemicStatus.UNKNOWN
    persistence: str = "SESSION"


@dataclass
class CounterpartyState:
    concerns: list[str] = field(default_factory=list)
    disclosures: list[str] = field(default_factory=list)
    open_threads: list[str] = field(default_factory=list)
    observations: list[CounterpartyObservation] = field(default_factory=list)


@dataclass
class ConversationItem:
    id: str
    item_type: ConversationItemType
    state: ConversationItemState
    title: str
    source_refs: list[SourceRef] = field(default_factory=list)
    epistemic_status: EpistemicStatus = EpistemicStatus.UNKNOWN
    review_status: ReviewStatus = ReviewStatus.AI_EXTRACTED
    owner_id: str = ""
    speaker_id: str = ""
    due_at: str = ""
    supersedes_id: str = ""
    confidence: float = 0.0


@dataclass
class ConversationState:
    phase: str
    current_topic: str = ""
    user_speaking: bool = False
    direct_question_pending: bool = False
    counterparty: CounterpartyState = field(default_factory=CounterpartyState)
    items: list[ConversationItem | dict[str, Any]] = field(default_factory=list)
    open_threads: list[str] = field(default_factory=list)


@dataclass
class ExpressionIntent:
    action: ExpressionAction = ExpressionAction.SILENT
    kind: GuidanceKind | None = None
    summary: str = ""
    sources: list[str] = field(default_factory=list)
    target_participant_id: str = ""


@dataclass
class ExpressionPlan:
    action: ExpressionAction = ExpressionAction.SILENT
    guidance_kind: GuidanceKind | None = None
    target_participant_id: str = ""
    text: str = ""
    source_refs: list[SourceRef] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    max_length: int = 0
    render_as: str = "SILENCE"
    suppression_reasons: list[str] = field(default_factory=list)


@dataclass
class OpportunityScore:
    relevance: float = 0.0
    novelty: float = 0.0
    provenance_strength: float = 0.0
    role_relevance: float = 0.0
    goal_relevance: float = 0.0
    urgency: float = 0.0
    decision_impact: float = 0.0
    interruption_cost: float = 0.0
    already_mentioned: float = 0.0
    uncertainty: float = 0.0
    social_risk: float = 0.0
    stale_context_risk: float = 0.0

    @property
    def value(self) -> float:
        benefit = (
            self.relevance
            + self.novelty
            + self.provenance_strength
            + self.role_relevance
            + self.goal_relevance
            + self.urgency
            + self.decision_impact
        )
        cost = (
            self.interruption_cost
            + self.already_mentioned
            + self.uncertainty
            + self.social_risk
            + self.stale_context_risk
        )
        return benefit - cost


@dataclass
class GuidanceCandidate:
    id: str
    kind: GuidanceKind
    expression_action: ExpressionAction
    text: str
    source_refs: list[SourceRef] = field(default_factory=list)
    score: OpportunityScore | None = None
    suppression_reasons: list[str] = field(default_factory=list)
    expires_at: str = ""


PROFILES: tuple[ConversationProfile, ...] = (
    ConversationProfile(
        ConversationProfileKind.INTERVIEW,
        "面试",
        (GuidanceKind.ANSWER_CUE, GuidanceKind.QUESTION, GuidanceKind.RISK, GuidanceKind.DELIVERY),
        productized=True,
        runtime_available=True,
        specialized_behavior_validated=True,
    ),
    ConversationProfile(
        ConversationProfileKind.PROJECT_SYNC,
        "项目同步",
        (
            GuidanceKind.RECALL,
            GuidanceKind.QUESTION,
            GuidanceKind.RISK,
            GuidanceKind.CONTRIBUTION_OPPORTUNITY,
            GuidanceKind.TALKING_POINT,
        ),
        productized=False,
        runtime_available=True,
        launch_wedge=True,
    ),
    ConversationProfile(
        ConversationProfileKind.DESIGN_REVIEW,
        "设计评审",
        (
            GuidanceKind.RECALL,
            GuidanceKind.TALKING_POINT,
            GuidanceKind.QUESTION,
            GuidanceKind.RISK,
            GuidanceKind.CONTRIBUTION_OPPORTUNITY,
        ),
        productized=False,
        runtime_available=True,
        launch_wedge=True,
    ),
    ConversationProfile(
        ConversationProfileKind.PRESENTATION_QA,
        "演示 / Q&A",
        (GuidanceKind.ANSWER_CUE, GuidanceKind.RECALL, GuidanceKind.QUESTION, GuidanceKind.DELIVERY),
        productized=False,
        runtime_available=True,
        default_mode=AssistanceMode.PRESENTATION,
    ),
    ConversationProfile(
        ConversationProfileKind.ONE_ON_ONE,
        "1:1",
        (GuidanceKind.RECALL, GuidanceKind.QUESTION, GuidanceKind.TALKING_POINT, GuidanceKind.RISK),
        productized=False,
        runtime_available=True,
        default_mode=AssistanceMode.ONE_ON_ONE,
    ),
    ConversationProfile(
        ConversationProfileKind.CLIENT_CALL,
        "客户会",
        (
            GuidanceKind.RECALL,
            GuidanceKind.ANSWER_CUE,
            GuidanceKind.QUESTION,
            GuidanceKind.RISK,
            GuidanceKind.CONTRIBUTION_OPPORTUNITY,
        ),
        productized=False,
        runtime_available=True,
    ),
    ConversationProfile(
        ConversationProfileKind.NEGOTIATION,
        "谈判",
        (
            GuidanceKind.RECALL,
            GuidanceKind.TALKING_POINT,
            GuidanceKind.QUESTION,
            GuidanceKind.RISK,
            GuidanceKind.CONTRIBUTION_OPPORTUNITY,
        ),
        productized=False,
        runtime_available=True,
    ),
    ConversationProfile(
        ConversationProfileKind.MEETING,
        "会议（兼容抽象）",
        tuple(GuidanceKind),
        productized=False,
        runtime_available=True,
    ),
)


def profile(kind: ConversationProfileKind) -> ConversationProfile:
    for item in PROFILES:
        if item.key is kind:
            return item
    raise KeyError(kind)


def interview_goal_as_conversation_goal(goal: dict[str, Any]) -> ConversationGoal:
    return ConversationGoal(
        id=str(goal["id"]),
        profile=ConversationProfileKind.INTERVIEW,
        title=str(goal.get("title") or ""),
        counterparty=str(goal.get("company") or ""),
        attributes={"role": goal.get("role", ""), "stage": goal.get("stage", "")},
    )


def can_promote_item(item: ConversationItem, target: ConversationItemState) -> bool:
    """Conservative v2 contract guard; runtime may add stricter profile rules."""
    if target is ConversationItemState.AGREED:
        return (
            item.item_type is ConversationItemType.DECISION
            and bool(item.source_refs)
            and item.review_status
            in {ReviewStatus.USER_CONFIRMED, ReviewStatus.USER_EDITED, ReviewStatus.SOURCE_CONFIRMED}
        )
    if target is ConversationItemState.COMMITTED:
        return (
            item.item_type in {ConversationItemType.COMMITMENT, ConversationItemType.TASK}
            and bool(item.owner_id)
            and bool(item.source_refs)
            and item.review_status
            in {ReviewStatus.USER_CONFIRMED, ReviewStatus.USER_EDITED, ReviewStatus.SOURCE_CONFIRMED}
        )
    if target is ConversationItemState.DONE:
        return item.state is ConversationItemState.COMMITTED
    if target is ConversationItemState.SUPERSEDED:
        return bool(item.supersedes_id) or item.state in {
            ConversationItemState.PROPOSED,
            ConversationItemState.AGREED,
            ConversationItemState.COMMITTED,
        }
    return True
