"""v1.2-R2 semantics: provenance axes, assertion policy, and the one router.

R2 retires the single TruthStatus axis as the carrier of every meaning.
Three independent axes describe a personal statement:

  ProvenanceStatus     — do the sources the system holds cover it?
  UserAssertionStatus  — did the user explicitly confirm / deny it?
  SessionStatus        — was it said aloud in the current session?

 INVARIANT:
  - Provenance is not truth: DIRECT_EVIDENCE means "a held source says so",
    never "this is verified to be true in reality".
  - Session-stated is not verified: SESSION_STATED never raises provenance
    and never becomes a long-term claim without user review.
  - Human advice is not evidence: HUMAN_COACH cues never change any axis.
  - ``route_answer`` is the ONLY question-to-response-mode table. Other
    modules must call it instead of keeping their own mapping.
"""
from __future__ import annotations

import re
from enum import Enum

from services.intelligence.types import QuestionType, ResponseMode, TruthStatus


class ProvenanceStatus(str, Enum):
    DIRECT_EVIDENCE = "DIRECT_EVIDENCE"
    SUPPORTING_EVIDENCE = "SUPPORTING_EVIDENCE"
    NO_EVIDENCE = "NO_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"


class UserAssertionStatus(str, Enum):
    UNREVIEWED = "UNREVIEWED"
    USER_CONFIRMED = "USER_CONFIRMED"
    USER_DENIED = "USER_DENIED"


class SessionStatus(str, Enum):
    NOT_STATED = "NOT_STATED"
    SESSION_STATED = "SESSION_STATED"
    SESSION_CORRECTED = "SESSION_CORRECTED"


class AssertionPolicy(str, Enum):
    ALLOW_PERSONAL_ASSERTION = "ALLOW_PERSONAL_ASSERTION"
    ALLOW_WITH_QUALIFIER = "ALLOW_WITH_QUALIFIER"
    REQUIRE_BOUNDARY = "REQUIRE_BOUNDARY"
    KNOWLEDGE_ONLY = "KNOWLEDGE_ONLY"
    BLOCK_ASSERTION = "BLOCK_ASSERTION"


class DialogueAct(str, Enum):
    NEW_QUESTION = "NEW_QUESTION"
    FOLLOW_UP = "FOLLOW_UP"
    CLARIFICATION = "CLARIFICATION"
    CHALLENGE = "CHALLENGE"
    INTERRUPTION = "INTERRUPTION"
    META = "META"
    TRANSITION = "TRANSITION"


class ContentType(str, Enum):
    INTRODUCTION = "INTRODUCTION"
    EXPERIENCE = "EXPERIENCE"
    PROJECT_DEEP_DIVE = "PROJECT_DEEP_DIVE"
    KNOWLEDGE = "KNOWLEDGE"
    CODING = "CODING"
    SYSTEM_DESIGN = "SYSTEM_DESIGN"
    OOD = "OOD"
    BEHAVIORAL = "BEHAVIORAL"
    PRODUCT = "PRODUCT"
    CASE = "CASE"
    DATA_ML = "DATA_ML"
    HYPOTHETICAL = "HYPOTHETICAL"
    RECRUITER = "RECRUITER"
    NEGOTIATION = "NEGOTIATION"
    COMPANY_ROLE_FIT = "COMPANY_ROLE_FIT"


class TruthRequirement(str, Enum):
    PERSONAL_FACT_REQUIRED = "PERSONAL_FACT_REQUIRED"
    PERSONAL_FACT_RELEVANT = "PERSONAL_FACT_RELEVANT"
    KNOWLEDGE_ONLY = "KNOWLEDGE_ONLY"
    HYPOTHETICAL_ALLOWED = "HYPOTHETICAL_ALLOWED"
    SCREEN_CONTEXT_REQUIRED = "SCREEN_CONTEXT_REQUIRED"


class CueSource(str, Enum):
    """Fast Cue source taxonomy (R2 Stage J)."""

    PERSONAL_EVIDENCE = "PERSONAL_EVIDENCE"
    KB_KNOWLEDGE = "KB_KNOWLEDGE"
    WORLD_KNOWLEDGE = "WORLD_KNOWLEDGE"
    HUMAN_COACH = "HUMAN_COACH"


# ---------------------------------------------------------------------------
# User-facing labels: never say "verified = true".
# ---------------------------------------------------------------------------

PROVENANCE_LABELS: dict[str, str] = {
    ProvenanceStatus.DIRECT_EVIDENCE.value: "有直接证据",
    ProvenanceStatus.SUPPORTING_EVIDENCE.value: "有支持材料",
    ProvenanceStatus.NO_EVIDENCE.value: "暂无证据",
    ProvenanceStatus.CONFLICTING_EVIDENCE.value: "来源冲突",
}
USER_ASSERTION_LABELS: dict[str, str] = {
    UserAssertionStatus.UNREVIEWED.value: "未确认",
    UserAssertionStatus.USER_CONFIRMED.value: "用户已确认",
    UserAssertionStatus.USER_DENIED.value: "用户已否认",
}
SESSION_LABELS: dict[str, str] = {
    SessionStatus.NOT_STATED.value: "",
    SessionStatus.SESSION_STATED.value: "本场曾口述",
    SessionStatus.SESSION_CORRECTED.value: "本场已纠正",
}


def provenance_from_legacy(status: str | TruthStatus) -> ProvenanceStatus:
    """Map the v1.0 single-axis TruthStatus to the R2 provenance axis.

    VERIFIED used to be shown as "true"; it only ever meant "a held source
    states it directly", which is exactly DIRECT_EVIDENCE.
    """
    value = status.value if isinstance(status, TruthStatus) else str(status or "").upper()
    return {
        "VERIFIED": ProvenanceStatus.DIRECT_EVIDENCE,
        "SUPPORTED": ProvenanceStatus.SUPPORTING_EVIDENCE,
        "INFERRED": ProvenanceStatus.NO_EVIDENCE,
        "UNKNOWN": ProvenanceStatus.NO_EVIDENCE,
        "CONTRADICTED": ProvenanceStatus.CONFLICTING_EVIDENCE,
    }.get(value, ProvenanceStatus.NO_EVIDENCE)


def provenance_from_grounding(
    grounding_status: str,
    *,
    has_profile: bool = True,
    question: str = "",
    profile_text: str = "",
) -> ProvenanceStatus:
    """Map the deterministic answer_grounding status to provenance.

    ``not_applicable`` means the question is open about the candidate ("tell
    me about your project") rather than checking one specific claim; the
    answer may then only draw on the held profile, which is direct evidence
    for whatever it states — provided a profile exists at all.
    """
    status = str(grounding_status or "")
    if status in {"not_applicable", ""}:
        if not has_profile:
            return ProvenanceStatus.NO_EVIDENCE
        covered = claim_coverage(question, profile_text) if profile_text else None
        return covered or ProvenanceStatus.DIRECT_EVIDENCE
    return {
        "supported": ProvenanceStatus.DIRECT_EVIDENCE,
        # related_only = the resume mentions something adjacent (Redis) but not
        # the asked subject (Redis Cluster): that is NOT evidence for it.
        "explicit_negative": ProvenanceStatus.CONFLICTING_EVIDENCE,
    }.get(status, ProvenanceStatus.NO_EVIDENCE)


# Only experience checks ("用过/用了 X 吗", "有没有 X 经验"), not any "么".
_YESNO = re.compile(
    r"(?:用|做|搭|部署|上线|负责|实现|接触|维护)(?:过|了).{0,40}(?:吗|没有)[？?]?\s*$"
    r"|有没有.{0,40}(?:经验|经历|用过|做过)|是否.{0,40}(?:用过|做过|经验)"
    r"|\b(?:did you|have you) (?:use|used|build|built|run|ran|deploy|deployed)\b",
    re.IGNORECASE,
)
_TECH_PHRASE = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]*(?:\s+[A-Z][A-Za-z0-9+#.\-]*)*")
_EN_STOP = {"did", "you", "have", "do", "use", "used", "build", "built", "run", "ran", "deploy", "deployed", "in", "the", "a", "an", "production"}


def claim_coverage(question: str, profile_text: str) -> ProvenanceStatus | None:
    """Specific yes/no claim checks ("你们当时用了 Redis Cluster 吗"):
    every named technology phrase must appear in the held profile.
    Returns None when the question names no checkable phrase."""
    if not _YESNO.search(question or ""):
        return None
    phrases = []
    for raw in _TECH_PHRASE.findall(question or ""):
        # "use Kafka" -> "Kafka": drop question/verb words inside a phrase.
        words = [w for w in raw.split() if w.lower().strip("?.,") not in _EN_STOP]
        phrase = " ".join(words).strip(" ?.,")
        if len(phrase) > 1:
            phrases.append(phrase)
    if not phrases:
        return None
    profile = (profile_text or "").lower()
    if all(p.lower() in profile for p in phrases):
        return ProvenanceStatus.DIRECT_EVIDENCE
    return ProvenanceStatus.NO_EVIDENCE


def _coerce(enum_cls, value, default):
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(str(value or "").upper())
    except ValueError:
        return default


def decide_assertion_policy(
    provenance: ProvenanceStatus | str,
    user_assertion: UserAssertionStatus | str = UserAssertionStatus.UNREVIEWED,
    session_status: SessionStatus | str = SessionStatus.NOT_STATED,
    truth_requirement: TruthRequirement | str = TruthRequirement.PERSONAL_FACT_REQUIRED,
    *,
    ai_policy: str = "AI_ALLOWED",
) -> AssertionPolicy:
    """Decide whether this turn may say "I did X".

    Order matters: denial and correction beat everything; questions that do
    not ask about the candidate never unlock personal assertion; evidence
    unlocks it; a user's own confirmation without a source only unlocks a
    qualified statement that must not add detail.
    """
    prov = _coerce(ProvenanceStatus, provenance, ProvenanceStatus.NO_EVIDENCE)
    user = _coerce(UserAssertionStatus, user_assertion, UserAssertionStatus.UNREVIEWED)
    session = _coerce(SessionStatus, session_status, SessionStatus.NOT_STATED)
    req = _coerce(TruthRequirement, truth_requirement, TruthRequirement.PERSONAL_FACT_REQUIRED)

    if str(ai_policy or "").upper() == "AI_FORBIDDEN":
        return AssertionPolicy.BLOCK_ASSERTION
    if user == UserAssertionStatus.USER_DENIED or session == SessionStatus.SESSION_CORRECTED:
        return AssertionPolicy.BLOCK_ASSERTION
    if req in {
        TruthRequirement.KNOWLEDGE_ONLY,
        TruthRequirement.HYPOTHETICAL_ALLOWED,
        TruthRequirement.SCREEN_CONTEXT_REQUIRED,
    }:
        return AssertionPolicy.KNOWLEDGE_ONLY
    if prov == ProvenanceStatus.CONFLICTING_EVIDENCE:
        return AssertionPolicy.REQUIRE_BOUNDARY
    if prov == ProvenanceStatus.DIRECT_EVIDENCE:
        return AssertionPolicy.ALLOW_PERSONAL_ASSERTION
    if prov == ProvenanceStatus.SUPPORTING_EVIDENCE:
        return AssertionPolicy.ALLOW_WITH_QUALIFIER
    # NO_EVIDENCE from here on.
    if user == UserAssertionStatus.USER_CONFIRMED:
        return AssertionPolicy.ALLOW_WITH_QUALIFIER
    if req == TruthRequirement.PERSONAL_FACT_RELEVANT:
        return AssertionPolicy.KNOWLEDGE_ONLY
    # SESSION_STATED without evidence stays a boundary: saying it once does
    # not license expanding it.
    return AssertionPolicy.REQUIRE_BOUNDARY


ASSERTION_PROMPTS: dict[AssertionPolicy, str] = {
    AssertionPolicy.ALLOW_PERSONAL_ASSERTION: "个人陈述：有直接来源，可用第一人称陈述，但细节只能来自给定来源。",
    AssertionPolicy.ALLOW_WITH_QUALIFIER: "个人陈述：只有支持材料或用户本人确认，可谨慎第一人称，不得新增指标、角色、规模或架构细节。",
    AssertionPolicy.REQUIRE_BOUNDARY: "个人陈述：暂无来源支持。先说明事实边界，再讲理解与做法；禁止写成“我做过/我负责/我们上线了”。",
    AssertionPolicy.KNOWLEDGE_ONLY: "个人陈述：本题不需要个人经历，只讲知识/推理，不要出现“我之前在项目里…”。",
    AssertionPolicy.BLOCK_ASSERTION: "个人陈述：该陈述已被用户否认或纠正，禁止使用，也不要用新细节圆回来。",
}


# ---------------------------------------------------------------------------
# Question Understanding 2.0: derive the three axes from the 21-type result.
# ---------------------------------------------------------------------------

_CONTENT_FROM_QTYPE: dict[QuestionType, ContentType] = {
    QuestionType.SELF_INTRODUCTION: ContentType.INTRODUCTION,
    QuestionType.EXPERIENCE: ContentType.EXPERIENCE,
    QuestionType.PROJECT_DEEP_DIVE: ContentType.PROJECT_DEEP_DIVE,
    QuestionType.BEHAVIORAL: ContentType.BEHAVIORAL,
    QuestionType.KNOWLEDGE: ContentType.KNOWLEDGE,
    QuestionType.CODING: ContentType.CODING,
    QuestionType.SYSTEM_DESIGN: ContentType.SYSTEM_DESIGN,
    QuestionType.OOD: ContentType.OOD,
    QuestionType.DEBUGGING: ContentType.KNOWLEDGE,
    QuestionType.HYPOTHETICAL: ContentType.HYPOTHETICAL,
    QuestionType.CASE: ContentType.CASE,
    QuestionType.PRODUCT: ContentType.PRODUCT,
    QuestionType.BUSINESS: ContentType.CASE,
    QuestionType.ROLE_FIT: ContentType.COMPANY_ROLE_FIT,
    QuestionType.COMPANY: ContentType.COMPANY_ROLE_FIT,
    QuestionType.CAREER: ContentType.RECRUITER,
    QuestionType.SALARY: ContentType.NEGOTIATION,
    QuestionType.NEGOTIATION: ContentType.NEGOTIATION,
    QuestionType.FOLLOW_UP: ContentType.PROJECT_DEEP_DIVE,
    QuestionType.CLARIFICATION: ContentType.PROJECT_DEEP_DIVE,
    QuestionType.META: ContentType.KNOWLEDGE,
}

_DATA_ML = re.compile(r"特征工程|过拟合|欠拟合|召回率|准确率|auc|模型训练|梯度|损失函数|embedding|向量检索|a/b\s*test|ab\s*实验", re.IGNORECASE)
_CHALLENGE = re.compile(r"你确定|真的吗|不对吧|为什么不用|为什么没用|怎么不用|凭什么|有什么依据|are you sure|why not", re.IGNORECASE)
_INTERRUPT = re.compile(r"^(?:等等|等一下|打断一下|先停一下|hold on|wait)", re.IGNORECASE)
_META = re.compile(r"听得到吗|能听到吗|声音|网络卡|共享屏幕|can you hear|you're muted", re.IGNORECASE)
_TRANSITION = re.compile(r"^(?:好的?|行|ok(?:ay)?)[，,。 ]*(?:那|接下来|下面|我们)(?:聊聊|换个|来看|进入|问)", re.IGNORECASE)
_CLARIFY = re.compile(r"^(?:你是说|你的意思是|我没听清|能再说一遍|是指|do you mean)", re.IGNORECASE)
_SCREEN = re.compile(r"屏幕上|这道题|这段代码|看一下这个|题面|share(?:d)? screen|on (?:the|your) screen", re.IGNORECASE)


_RATIONALE = re.compile(r"为什么|为何|怎么考虑|取舍|权衡|why", re.IGNORECASE)
_DEICTIC = re.compile(r"这个|那个|这块|这里|刚才|上面|你们|你的|当时|这么|^为什么|^然后|^接着|^具体", re.IGNORECASE)


_CHOICE_RATIONALE = re.compile(r"为什么(?:选|用|采用|选择|不用|没用|要用)|怎么考虑|为何选|why did you (?:choose|pick|use)|why not use", re.IGNORECASE)
_PROFILE_PHRASE = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]{2,}|[\u4e00-\u9fff]{3,8}")


def _anchored_to_profile(text: str, profile_text: str) -> bool:
    """A choice-rationale question that names something from the candidate's
    own profile ("订单服务为什么选 PostgreSQL") asks about their decision."""
    if not _CHOICE_RATIONALE.search(text or ""):
        return False
    profile = (profile_text or "").lower()
    for phrase in _PROFILE_PHRASE.findall(text or ""):
        chunk = phrase.lower()
        if len(chunk) >= 3 and chunk in profile and chunk not in {"为什么", "怎么考虑"}:
            return True
    return False


def _follow_up_content(raw: str) -> ContentType:
    """A follow-up keeps the thread's project frame only when it points back
    at it ("这个怎么验证", "为什么不用 X"); a follow-up that names a new
    subject ("那 Redis 会有什么问题") is judged on its own content."""
    from services.intelligence.question_understanding import classify_question_type_21

    if _DEICTIC.search(raw):
        return ContentType.PROJECT_DEEP_DIVE
    standalone = classify_question_type_21(raw)
    if standalone in {QuestionType.FOLLOW_UP, QuestionType.CLARIFICATION}:
        return ContentType.PROJECT_DEEP_DIVE
    return _CONTENT_FROM_QTYPE.get(standalone, ContentType.KNOWLEDGE)


def derive_axes(
    question_type: QuestionType,
    text: str,
    *,
    is_follow_up: bool = False,
    personal_fact_required: bool = False,
    open_world_allowed: bool = True,
    raw_question: str = "",
    profile_text: str = "",
) -> tuple[DialogueAct, ContentType, TruthRequirement]:
    """Split one question into (dialogue act, content type, truth requirement).

    ``text`` is the resolved question; ``raw_question`` (when given) is what
    the interviewer literally said, used to classify a follow-up's content
    on its own terms instead of inheriting "project" from the thread.
    """
    value = (text or "").strip()
    raw = (raw_question or "").strip() or value
    if _INTERRUPT.search(value):
        act = DialogueAct.INTERRUPTION
    elif _META.search(value) or question_type == QuestionType.META and not value:
        act = DialogueAct.META
    elif _CLARIFY.search(value) or question_type == QuestionType.CLARIFICATION:
        act = DialogueAct.CLARIFICATION
    elif _CHALLENGE.search(value):
        act = DialogueAct.CHALLENGE
    elif _TRANSITION.search(value):
        act = DialogueAct.TRANSITION
    elif is_follow_up or question_type == QuestionType.FOLLOW_UP:
        act = DialogueAct.FOLLOW_UP
    else:
        act = DialogueAct.NEW_QUESTION

    content = _CONTENT_FROM_QTYPE.get(question_type, ContentType.KNOWLEDGE)
    if question_type in {QuestionType.FOLLOW_UP, QuestionType.CLARIFICATION}:
        content = _follow_up_content(raw)
    elif content == ContentType.EXPERIENCE and _RATIONALE.search(value):
        # "Tell me about your X, why this design" = experience + rationale.
        content = ContentType.PROJECT_DEEP_DIVE
    if content == ContentType.KNOWLEDGE and profile_text and _anchored_to_profile(value, profile_text):
        content = ContentType.PROJECT_DEEP_DIVE
    if content == ContentType.KNOWLEDGE and _DATA_ML.search(value):
        content = ContentType.DATA_ML

    if _SCREEN.search(value) and content in {ContentType.CODING, ContentType.KNOWLEDGE, ContentType.SYSTEM_DESIGN}:
        req = TruthRequirement.SCREEN_CONTEXT_REQUIRED
    elif personal_fact_required or content in {
        ContentType.INTRODUCTION,
        ContentType.EXPERIENCE,
        ContentType.PROJECT_DEEP_DIVE,
        ContentType.BEHAVIORAL,
    }:
        req = TruthRequirement.PERSONAL_FACT_REQUIRED
    elif content == ContentType.HYPOTHETICAL:
        req = TruthRequirement.HYPOTHETICAL_ALLOWED
    elif content in {ContentType.COMPANY_ROLE_FIT, ContentType.RECRUITER, ContentType.NEGOTIATION}:
        req = TruthRequirement.PERSONAL_FACT_RELEVANT
    else:
        req = TruthRequirement.KNOWLEDGE_ONLY
    return act, content, req


# ---------------------------------------------------------------------------
# The one routing function.
# ---------------------------------------------------------------------------

_DIRECT_CONTENT_ROUTES: dict[ContentType, ResponseMode] = {
    ContentType.CODING: ResponseMode.CODING,
    ContentType.SYSTEM_DESIGN: ResponseMode.SYSTEM_DESIGN,
    ContentType.OOD: ResponseMode.OOD,
    ContentType.PRODUCT: ResponseMode.PRODUCT_CASE,
    ContentType.CASE: ResponseMode.PRODUCT_CASE,
    ContentType.NEGOTIATION: ResponseMode.NEGOTIATION,
    ContentType.BEHAVIORAL: ResponseMode.BEHAVIORAL,
    ContentType.COMPANY_ROLE_FIT: ResponseMode.BEHAVIORAL,
    ContentType.RECRUITER: ResponseMode.BEHAVIORAL,
    ContentType.KNOWLEDGE: ResponseMode.KNOWLEDGE,
    ContentType.DATA_ML: ResponseMode.KNOWLEDGE,
}
_OPEN_DESIGN_HINT = re.compile(r"怎么设计|如何设计|怎么迁|如何迁|怎么落地|怎么搭|怎么改造|how would you (?:design|migrate)", re.IGNORECASE)
# A classic full system-design prompt ("设计一个短链系统") stays SYSTEM_DESIGN;
# an open, context-bound "how would you migrate/land it" is OPEN_DESIGN.
_CLASSIC_SYSTEM_DESIGN = re.compile(r"系统设计|设计一个|设计一套|容量规划|design a|design an", re.IGNORECASE)


def route_answer(
    dialogue_act: DialogueAct | str,
    content_type: ContentType | str,
    truth_requirement: TruthRequirement | str,
    provenance_state: ProvenanceStatus | str = ProvenanceStatus.NO_EVIDENCE,
    user_assertion_state: UserAssertionStatus | str = UserAssertionStatus.UNREVIEWED,
    policy: AssertionPolicy | str | None = None,
    *,
    question_text: str = "",
    session_status: SessionStatus | str = SessionStatus.NOT_STATED,
) -> ResponseMode:
    """Pure routing decision; the only table from question axes to mode."""
    content = _coerce(ContentType, content_type, ContentType.KNOWLEDGE)
    req = _coerce(TruthRequirement, truth_requirement, TruthRequirement.KNOWLEDGE_ONLY)
    assertion = (
        _coerce(AssertionPolicy, policy, AssertionPolicy.REQUIRE_BOUNDARY)
        if policy is not None
        else decide_assertion_policy(provenance_state, user_assertion_state, session_status, req)
    )
    _coerce(DialogueAct, dialogue_act, DialogueAct.NEW_QUESTION)  # validated; act does not change the mode table

    if content == ContentType.HYPOTHETICAL:
        return ResponseMode.OPEN_DESIGN if _OPEN_DESIGN_HINT.search(question_text or "") else ResponseMode.HYPOTHETICAL
    if (
        content == ContentType.SYSTEM_DESIGN
        and _OPEN_DESIGN_HINT.search(question_text or "")
        and not _CLASSIC_SYSTEM_DESIGN.search(question_text or "")
    ):
        return ResponseMode.OPEN_DESIGN
    if content in _DIRECT_CONTENT_ROUTES:
        mode = _DIRECT_CONTENT_ROUTES[content]
        if mode == ResponseMode.KNOWLEDGE and req == TruthRequirement.PERSONAL_FACT_REQUIRED:
            # A knowledge-looking question that asks "have you used X":
            # personal fact decides, knowledge follows.
            return _personal_route(ContentType.EXPERIENCE, assertion)
        return mode
    return _personal_route(content, assertion)


def _personal_route(content: ContentType, assertion: AssertionPolicy) -> ResponseMode:
    if assertion == AssertionPolicy.ALLOW_PERSONAL_ASSERTION:
        return ResponseMode.EXPERIENCE_KNOWLEDGE if content == ContentType.PROJECT_DEEP_DIVE else ResponseMode.EXPERIENCE
    if assertion == AssertionPolicy.ALLOW_WITH_QUALIFIER:
        return ResponseMode.EXPERIENCE_KNOWLEDGE
    return ResponseMode.EXPERIENCE_BOUNDARY_KNOWLEDGE


# Documented semantic compatibility used ONLY for the "semantic compatible"
# eval column; strict accuracy never consults it.
SEMANTIC_COMPATIBLE: dict[str, set[str]] = {
    "OPEN_DESIGN": {"OPEN_DESIGN", "SYSTEM_DESIGN", "HYPOTHETICAL"},
    "EXPERIENCE_KNOWLEDGE": {"EXPERIENCE_KNOWLEDGE", "EXPERIENCE"},
    "KNOWLEDGE": {"KNOWLEDGE", "EXPERIENCE_KNOWLEDGE"},
    "PRODUCT_CASE": {"PRODUCT_CASE", "CASE"},
}
