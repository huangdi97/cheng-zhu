"""Intelligence Core shared types.

Every cross-module contract of the Chengzhu intelligence layer lives here so
that modules interact through explicit, typed interfaces instead of raw dicts.
All models are pure data: business rules stay in the dedicated service modules.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


def now_ts() -> float:
    return time.time()


def new_id(prefix: str = "") -> str:
    """Stable identifier for intelligence entities (UUID-based)."""
    return f"{prefix}{uuid.uuid4().hex}"


class TruthStatus(str, Enum):
    """Unified claim truth status. A model may escalate UNKNOWN->INFERRED-like
    reasoning but must never fabricate VERIFIED without evidence."""

    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"
    CONTRADICTED = "CONTRADICTED"


class OutputSpace(str, Enum):
    """Mandatory output-space distinction: personal facts stay constrained,
    knowledge and hypothetical reasoning stay free."""

    PERSONAL_FACT = "PERSONAL_FACT"
    KNOWLEDGE_JUDGMENT = "KNOWLEDGE_JUDGMENT"
    HYPOTHETICAL = "HYPOTHETICAL"


class EvidenceSource(str, Enum):
    RESUME = "resume"
    USER_CONFIRMED = "user_confirmed"
    PROJECT_DOCUMENT = "project_document"
    GITHUB_CODE = "github_code"
    README = "readme"
    INTERVIEW_TRANSCRIPT = "interview_transcript"
    IMPORTED_NOTE = "imported_note"
    EXTERNAL_PROFILE = "external_profile"
    KB_NOTE = "kb_note"


class AlignmentStatus(str, Enum):
    """Explainable candidate-job alignment states. Never output a fake
    precise percentage like '93% match'."""

    STRONG_MATCH = "STRONG_MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    KNOWLEDGE_MATCH = "KNOWLEDGE_MATCH"
    GAP = "GAP"
    UNKNOWN = "UNKNOWN"


class QuestionType(str, Enum):
    """Full interview question taxonomy (master doc section 13.1)."""

    SELF_INTRODUCTION = "SELF_INTRODUCTION"
    EXPERIENCE = "EXPERIENCE"
    PROJECT_DEEP_DIVE = "PROJECT_DEEP_DIVE"
    BEHAVIORAL = "BEHAVIORAL"
    KNOWLEDGE = "KNOWLEDGE"
    CODING = "CODING"
    SYSTEM_DESIGN = "SYSTEM_DESIGN"
    OOD = "OOD"
    DEBUGGING = "DEBUGGING"
    HYPOTHETICAL = "HYPOTHETICAL"
    CASE = "CASE"
    PRODUCT = "PRODUCT"
    BUSINESS = "BUSINESS"
    ROLE_FIT = "ROLE_FIT"
    COMPANY = "COMPANY"
    CAREER = "CAREER"
    SALARY = "SALARY"
    NEGOTIATION = "NEGOTIATION"
    FOLLOW_UP = "FOLLOW_UP"
    CLARIFICATION = "CLARIFICATION"
    META = "META"


class ResponseMode(str, Enum):
    """Answer planner response modes (master doc section 17)."""

    EXPERIENCE = "EXPERIENCE"
    EXPERIENCE_KNOWLEDGE = "EXPERIENCE_KNOWLEDGE"
    KNOWLEDGE = "KNOWLEDGE"
    HYPOTHETICAL = "HYPOTHETICAL"
    OPEN_DESIGN = "OPEN_DESIGN"
    BEHAVIORAL = "BEHAVIORAL"
    EXPERIENCE_BOUNDARY_KNOWLEDGE = "EXPERIENCE_BOUNDARY_KNOWLEDGE"
    CODING = "CODING"
    SYSTEM_DESIGN = "SYSTEM_DESIGN"
    CASE = "CASE"
    NEGOTIATION = "NEGOTIATION"
    OOD = "OOD"
    PRODUCT_CASE = "PRODUCT_CASE"


class DepthProfile(str, Enum):
    """Answer depth shapes; mirrors services.answer_depth.AnswerDepthProfile."""

    CONCISE = "concise"
    STRUCTURED = "structured"
    DEEP = "deep"
    COMPACT_DEEP = "compact_deep"


class ContextSource(str, Enum):
    """Unified context provider identifiers (master doc section 14.3)."""

    RESUME = "resume"
    CANDIDATE_GRAPH = "candidate_graph"
    EVIDENCE = "evidence"
    RECENT_DIALOGUE = "recent_dialogue"
    SESSION_MEMORY = "session_memory"
    JOB = "job"
    KB = "kb"
    SCREEN = "screen"
    WORLD_KNOWLEDGE = "world_knowledge"


class InterviewPhase(str, Enum):
    OPENING = "opening"
    PROJECT_DEEP_DIVE = "project_deep_dive"
    TECHNICAL_DEEP_DIVE = "technical_deep_dive"
    CODING = "coding"
    SYSTEM_DESIGN = "system_design"
    BEHAVIORAL = "behavioral"
    ROLE_FIT = "role_fit"
    HR = "hr"
    CLOSING = "closing"


@dataclass
class Claim:
    """A personal-fact claim extracted from candidate-owned material."""

    id: str
    candidate_id: str
    type: str
    text: str
    source: str
    truth_status: TruthStatus = TruthStatus.SUPPORTED
    confidence: float = 0.5
    created_at: float = field(default_factory=now_ts)
    updated_at: float = field(default_factory=now_ts)
    metadata_json: str = "{}"

    def payload(self) -> dict[str, Any]:
        data = asdict(self)
        data["truth_status"] = self.truth_status.value
        return data


@dataclass
class Evidence:
    """One provenance item backing zero or more claims."""

    id: str
    candidate_id: str
    source: str
    text: str
    created_at: float = field(default_factory=now_ts)
    updated_at: float = field(default_factory=now_ts)
    metadata_json: str = "{}"


@dataclass
class CandidateRepresentation:
    """Structured representation of the candidate built from resume + notes."""

    candidate_id: str
    profile_text: str = ""
    experiences: list[dict[str, Any]] = field(default_factory=list)
    projects: list[dict[str, Any]] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    skills: list[dict[str, Any]] = field(default_factory=list)
    stories: list[dict[str, Any]] = field(default_factory=list)
    voice_profile: dict[str, Any] = field(default_factory=dict)
    metrics: list[dict[str, Any]] = field(default_factory=list)
    education: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=now_ts)
    updated_at: float = field(default_factory=now_ts)
    schema_version: int = 1

    def payload(self) -> dict[str, Any]:
        data = asdict(self)
        data["claims"] = [claim.payload() if isinstance(claim, Claim) else claim for claim in self.claims]
        return data


@dataclass
class JobRequirement:
    id: str
    job_id: str
    kind: str  # must_have / nice_to_have / technology / competency / responsibility
    text: str
    created_at: float = field(default_factory=now_ts)


@dataclass
class JobRepresentation:
    """Structured JD representation plus candidate alignment."""

    job_id: str
    company: str = ""
    title: str = ""
    level: str = ""
    jd_text: str = ""
    responsibilities: list[str] = field(default_factory=list)
    must_have: list[str] = field(default_factory=list)
    nice_to_have: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    competencies: list[str] = field(default_factory=list)
    likely_interview_dimensions: list[str] = field(default_factory=list)
    alignment: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=now_ts)
    updated_at: float = field(default_factory=now_ts)
    schema_version: int = 1

    def payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InterviewEvent:
    """One incremental state-update event; the state is the fold of events."""

    seq: int
    session_id: str
    kind: str  # question_received / topic_changed / claim_made / risk_flag ...
    payload_json: str = "{}"
    created_at: float = field(default_factory=now_ts)


@dataclass
class InterviewState:
    """Versioned interview state. Updated incrementally by events, never
    rewritten wholesale by an LLM each turn."""

    session_id: str
    version: int = 0
    phase: str = InterviewPhase.OPENING.value
    topic_stack: list[str] = field(default_factory=list)
    current_topic: str = ""
    previous_topic: str = ""
    open_threads: list[str] = field(default_factory=list)
    question_type: str = ""
    intent: str = ""
    candidate_claims: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    screen_problem: str = ""
    language: str = "zh-CN"
    expected_depth: str = ""
    updated_at: float = field(default_factory=now_ts)

    def payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InterviewerState:
    """Probabilistic interviewer inference. Internal only: serves the planner,
    never written to long-term facts, never shown as a deterministic verdict."""

    session_id: str
    possible_focus: dict[str, float] = field(default_factory=dict)
    possible_concerns: dict[str, float] = field(default_factory=dict)
    accepted_signals: list[str] = field(default_factory=list)
    desired_next_signal: str = ""
    confidence: float = 0.0
    updated_at: float = field(default_factory=now_ts)


@dataclass
class ContextItem:
    """One candidate context item produced by a provider."""

    id: str
    source_type: ContextSource
    text: str
    entities: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=now_ts)
    evidence_strength: float = 0.0
    topic: str = ""
    token_estimate: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompiledContext:
    """Minimal sufficient context package for one question."""

    items: list[ContextItem] = field(default_factory=list)
    dropped: list[dict[str, Any]] = field(default_factory=list)
    total_token_estimate: int = 0
    budget: int = 0
    latency_ms: int = 0
    rendered_prompt_sections: list[str] = field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        return {
            "items": [
                {
                    "id": item.id,
                    "source_type": item.source_type.value,
                    "text": item.text,
                    "evidence_strength": item.evidence_strength,
                    "topic": item.topic,
                    "token_estimate": item.token_estimate,
                    "score": item.metadata.get("score"),
                    "score_breakdown": item.metadata.get("score_breakdown"),
                }
                for item in self.items
            ],
            "dropped": self.dropped,
            "total_token_estimate": self.total_token_estimate,
            "budget": self.budget,
            "latency_ms": self.latency_ms,
        }


@dataclass
class AnswerPlan:
    """Structured plan produced by the Answer Planner (not the full answer)."""

    mode: ResponseMode
    intent: list[str] = field(default_factory=list)
    structure: list[str] = field(default_factory=list)
    must_use_claim_ids: list[str] = field(default_factory=list)
    forbidden_claim_ids: list[str] = field(default_factory=list)
    allow_world_knowledge: bool = True
    allow_hypothesis: bool = True
    depth: str = DepthProfile.STRUCTURED.value
    surface: str = "cue_first"
    question_type: str = ""
    personal_fact_required: bool = False
    plan_prompt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def payload(self) -> dict[str, Any]:
        data = asdict(self)
        data["mode"] = self.mode.value
        return data


@dataclass
class QuestionUnderstanding:
    """Result of question understanding + follow-up resolution."""

    question_type: QuestionType
    resolved_question: str
    intent: str = ""
    domain: str = ""
    expected_depth: DepthProfile = DepthProfile.STRUCTURED
    personal_fact_required: bool = False
    open_world_allowed: bool = True
    follow_up_target: str = ""
    topic_transition: bool = False
    is_follow_up: bool = False
    confidence: float = 0.75

    def payload(self) -> dict[str, Any]:
        return {
            "question_type": self.question_type.value,
            "resolved_question": self.resolved_question,
            "intent": self.intent,
            "domain": self.domain,
            "expected_depth": self.expected_depth.value,
            "personal_fact_required": self.personal_fact_required,
            "open_world_allowed": self.open_world_allowed,
            "follow_up_target": self.follow_up_target,
            "topic_transition": self.topic_transition,
            "is_follow_up": self.is_follow_up,
            "confidence": self.confidence,
        }


@dataclass
class TruthCheckResult:
    """Result of the post-generation truth check."""

    original_text: str
    final_text: str
    passed: bool
    violations: list[dict[str, Any]] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    fallback_used: bool = False


@dataclass
class VoiceProfileData:
    """Personal voice profile built from real candidate speech (never from
    assistant-generated answers)."""

    candidate_id: str
    answer_length_hint: str = "medium"
    first_sentence_style: str = "conclusion_first"
    directness: float = 0.5
    technical_density: float = 0.5
    example_preference: str = "when_needed"
    language: str = "zh-CN"
    filler_tendency: float = 0.3
    forbidden_cliches: list[str] = field(default_factory=list)
    explicit_preferences: dict[str, Any] = field(default_factory=dict)
    sample_count: int = 0
    enabled: bool = False


class AIPolicyMode(str, Enum):
    """Per-session AI policy awareness (master doc section 47)."""

    AI_FORBIDDEN = "AI_FORBIDDEN"
    AI_LIMITED = "AI_LIMITED"
    AI_ALLOWED = "AI_ALLOWED"
    AI_EXPECTED = "AI_EXPECTED"


OptionalField = Optional
