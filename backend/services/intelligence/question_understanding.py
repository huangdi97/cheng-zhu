"""Question Understanding: 21-type taxonomy + follow-up resolution.

Building on services.question_turn_parser (speech segmentation stays there),
this module decides what the interviewer is really asking: the question type,
the resolved question, the intent, and whether a personal fact is required.

 INVARIANT:
  - Personal-fact questions keep ``personal_fact_required=True`` so the Truth
    Boundary locks the asked subject.
  - Open-world questions keep ``open_world_allowed=True``: no resume evidence
    is NOT the same as no answer.
"""
from __future__ import annotations

import re

from services.intelligence.types import DepthProfile, QuestionType, QuestionUnderstanding

_INTENT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"为什么不用|为什么没|怎么不|为何不用", "alternative_rejection"),
    (r"为什么选|为什么采用|为何选", "decision_rationale"),
    (r"如果|假如|假设|要是", "hypothetical_scale"),
    (r"怎么验证|如何验证|怎么评估|如何评估|怎么保证", "verification"),
    (r"怎么设计|如何设计|怎么实现|如何实现|怎么迁|如何迁|怎么落地", "open_design"),
    (r"怎么排查|如何排查|怎么定位|如何定位|线上问题|故障", "debugging"),
    (r"介绍一下|介绍下|说说|讲讲|谈谈", "introduction"),
    (r"取舍|权衡|利弊|优缺点", "tradeoff"),
    (r"你的角色|你负责|你做了什么|你的职责", "role_clarification"),
    (r"薪资|期望薪|到岗|加班", "compensation"),
)

_DOMAIN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"缓存|redis|memcached", "cache"),
    (r"消息队列|kafka|rabbitmq|mq|队列", "message_queue"),
    (r"数据库|mysql|postgres|mongo|分库分表|索引|事务", "database"),
    (r"llm|大模型|rag|agent|embedding|fine-?tun|微调|prompt", "ai_llm"),
    (r"分布式|高并发|高可用|微服务|k8s|kubernetes|云", "distributed_system"),
    (r"前端|react|vue|css|浏览器", "frontend"),
    (r"算法|复杂度|leetcode|数据结构|动态规划", "algorithm"),
    (r"系统设计|架构|容量|扩展性", "system_design"),
    (r"测试|质量|压测|用例", "testing"),
)

_EXPERIENCE_VERIFICATION = re.compile(
    r"(?:你|您|自己|之前|以前|工作|项目)?.{0,14}(?:做过|用过|使用过|接触过|负责过|参与过|实现过|"
    r"落地过|部署过|维护过|开发过|设计过|搭建过|用了|有.{0,24}经验)"
    r"|(?:有没有|是否有|有无).{0,32}(?:经验|经历)"
    r"|\b(?:have you|did you|do you have experience|worked with|used|built)\b",
    re.IGNORECASE,
)

_EXPERIENCE_YESNO_Q = re.compile(
    r"(?:做过|用过|使用过|接触过|负责过|参与过|实现过|落地过|部署过|维护过|开发过|设计过|搭建过|用了)[^。！!]{0,20}(?:吗|没有|么)"
    r"|(?:有没有|是否有).{0,32}(?:经验|经历)",
    re.IGNORECASE,
)
_SELF_INTRO = re.compile(r"自我介绍|介绍一下你自己|介绍下自己|self[- ]?introduction|tell me about yourself", re.IGNORECASE)

_HYPOTHETICAL = re.compile(r"如果|假如|假设|要是|扩大\s*\d*倍|规模扩大|流量增长|100\s*倍", re.IGNORECASE)
_HYPOTHETICAL_CLASSIFIER = _HYPOTHETICAL

# Bare follow-up cues that only make sense against the previous turn.
_BARE_FOLLOWUP = re.compile(r"^(?:为什么[??？]?$|然后呢[??？]?$|那怎么办[??？]?$|为什么不|为什么不用那个|如果再|那线上|那个呢|接着说|继续说|具体说说|展开讲)", re.IGNORECASE)

_QUESTION_SUFFIX = re.compile(r"[??？。!！]+$")
_STOPWORDS = {"什么", "怎么", "如何", "为什么", "哪些", "这个", "那个", "的", "了", "吗", "呢"}


def classify_question_type_21(text: str, *, relation_to_previous: str = "") -> QuestionType:
    """Deterministic 21-type classification (master doc section 13.1)."""
    value = (text or "").lower().strip()
    if not value:
        return QuestionType.META
    if _SELF_INTRO.search(value):
        return QuestionType.SELF_INTRODUCTION
    if re.search(r"写(?:一段)?代码|写一个|写个|实现(?:一下)?算法|leetcode|算法题|复杂度|手写|编程题|\bcoding\b", value):
        return QuestionType.CODING
    if re.search(r"系统设计|架构设计|容量规划|分库分表|设计一个|设计一套", value):
        return QuestionType.SYSTEM_DESIGN
    if _HYPOTHETICAL_CLASSIFIER.search(value):
        return QuestionType.HYPOTHETICAL
    if re.search(r"面向对象|面向对象设计|ood|类设计|多态|继承", value):
        return QuestionType.OOD
    if re.search(r"排查|定位|故障|线上问题|怎么 debug|debug|变慢|崩溃|超时", value):
        return QuestionType.DEBUGGING
    if re.search(r"薪资|期望薪|到岗|离职|加班|offer|背调", value):
        return QuestionType.SALARY
    if re.search(r"谈薪|谈判|negotiat|还价|议价", value):
        return QuestionType.NEGOTIATION
    if re.search(r"case[- ]?study|估算| estimation|咨询案例", value):
        return QuestionType.CASE
    if re.search(r"产品经理|用户增长|产品思维|产品题|需求分析", value):
        return QuestionType.PRODUCT
    if re.search(r"商业模式|商业化|盈利|市场", value):
        return QuestionType.BUSINESS
    if re.search(r"为什么选择我们|为什么想来|了解我们|对公司", value):
        return QuestionType.COMPANY
    if re.search(r"职业规划|五年|三年规划|career|发展计划", value):
        return QuestionType.CAREER
    if re.search(r"团队|协作|冲突|推动|失败经历|压力|挑战|领导力|行为|star", value):
        return QuestionType.BEHAVIORAL
    if re.search(r"你的项目|项目里|项目背景|你负责|简历|实习|上一家|技术难点|介绍一下你的|your project|your rag|your work|your experience", value):
        return QuestionType.EXPERIENCE
    if re.search(r"怎么迁|如何迁|你会怎么(?:做|设计|迁)|迁移方案", value):
        return QuestionType.SYSTEM_DESIGN
    if _EXPERIENCE_VERIFICATION.search(value):
        return QuestionType.EXPERIENCE
    if re.search(r"没听清|什么意思|再说一遍|你是说|clarif|具体指", value):
        return QuestionType.CLARIFICATION
    if relation_to_previous in {"follow_up", "followup", "continuation"} or _BARE_FOLLOWUP.match(value):
        return QuestionType.FOLLOW_UP
    if re.search(r"为什么|怎么看|如何评价|原理|区别|机制|底层|数据结构|事务|锁|缓存|网络|数据库|r任务|怎么选", value):
        return QuestionType.KNOWLEDGE
    return QuestionType.KNOWLEDGE


def detect_intent(text: str) -> str:
    for pattern, intent in _INTENT_PATTERNS:
        if re.search(pattern, (text or "").lower(), re.IGNORECASE):
            return intent
    return ""


def detect_domain(text: str) -> str:
    for pattern, domain in _DOMAIN_PATTERNS:
        if re.search(pattern, (text or "").lower(), re.IGNORECASE):
            return domain
    return ""


def _expected_depth(qtype: QuestionType, text: str) -> DepthProfile:
    value = (text or "").lower()
    if qtype in {QuestionType.CODING, QuestionType.SYSTEM_DESIGN}:
        return DepthProfile.DEEP
    if qtype in {QuestionType.FOLLOW_UP, QuestionType.CLARIFICATION}:
        return DepthProfile.COMPACT_DEEP
    if qtype == QuestionType.SALARY:
        return DepthProfile.CONCISE
    if _HYPOTHETICAL.search(value):
        return DepthProfile.DEEP
    if len(value) >= 18:
        return DepthProfile.STRUCTURED
    return DepthProfile.CONCISE


def _clean_target(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^(?:为什么|为何|怎么|如何|那|那么)", "", cleaned)
    return _QUESTION_SUFFIX.sub("", cleaned).strip(" ，,。")[:40]


def understand_question(
    question_text: str,
    *,
    interview_state=None,
    previous_question: str = "",
    relation_to_previous: str = "",
    open_threads: list[str] | None = None,
) -> QuestionUnderstanding:
    """Understand one question: type, intent, depth, fact requirement.

    ``interview_state`` is an optional InterviewState-like object (payload
    dict or dataclass); follow-up resolution against it lives in
    followup_resolver — this function only reads the topic it exposes.
    """
    raw = (question_text or "").strip()
    qtype = classify_question_type_21(raw, relation_to_previous=relation_to_previous)
    state_topic = ""
    if interview_state is not None:
        state_topic = str(getattr(interview_state, "current_topic", "") or "")
        if isinstance(interview_state, dict):
            state_topic = str(interview_state.get("current_topic", "") or "")
    state_relation = relation_to_previous
    if not state_relation and interview_state is not None:
        state_relation = str(getattr(interview_state, "question_type", "") or "")
        if isinstance(interview_state, dict):
            state_relation = str(interview_state.get("question_type", "") or "")

    is_follow_up = bool(
        relation_to_previous in {"follow_up", "followup", "continuation"}
        or _BARE_FOLLOWUP.match(raw.lower())
        or qtype == QuestionType.FOLLOW_UP
    )
    if (
        not is_follow_up
        and previous_question
        and qtype == QuestionType.KNOWLEDGE
        and re.match(r"^(?:为什么|为何|那|怎么)", raw.lower())
    ):
        # “为什么选 X？” following a project intro is a follow-up about the
        # candidate's decision, not a standalone knowledge question.
        is_follow_up = True
        qtype = QuestionType.FOLLOW_UP
    # A bare follow-up (“为什么？”) is a follow-up even when the previous
    # question is unknown; resolution then falls back to the state topic.
    resolved = raw
    follow_up_target = ""
    topic_transition = False
    if is_follow_up:
        target = _clean_target(raw) or state_topic
        threads = open_threads if open_threads is not None else []
        if not target and threads:
            target = threads[-1]
        follow_up_target = target
        if previous_question and target:
            resolved = f"{_QUESTION_SUFFIX.sub('', previous_question)} —— 追问：{_clean_target(raw) or target}？"
        elif target:
            resolved = f"关于{target}的追问：{raw}"
    elif state_topic and not _topic_overlap(raw, state_topic):
        topic_transition = True

    personal_fact_required = bool(
        qtype in {QuestionType.EXPERIENCE, QuestionType.PROJECT_DEEP_DIVE}
        and _EXPERIENCE_YESNO_Q.search(raw.lower())
    )
    open_world_allowed = bool(
        qtype
        in {
            QuestionType.KNOWLEDGE,
            QuestionType.HYPOTHETICAL,
            QuestionType.CODING,
            QuestionType.SYSTEM_DESIGN,
            QuestionType.OOD,
            QuestionType.CASE,
            QuestionType.PRODUCT,
            QuestionType.BUSINESS,
            QuestionType.COMPANY,
            QuestionType.DEBUGGING,
        }
        or not personal_fact_required
    )
    return QuestionUnderstanding(
        question_type=qtype,
        resolved_question=resolved,
        intent=detect_intent(raw),
        domain=detect_domain(raw),
        expected_depth=_expected_depth(qtype, raw),
        personal_fact_required=personal_fact_required,
        open_world_allowed=open_world_allowed,
        follow_up_target=follow_up_target,
        topic_transition=topic_transition,
        is_follow_up=is_follow_up,
        confidence=0.85 if qtype != QuestionType.KNOWLEDGE else 0.7,
    )


def _topic_overlap(text: str, topic: str) -> bool:
    """True when the question shares at least one anchor with the topic."""
    if not topic:
        return True
    lowered = (text or "").lower()
    # Anchor chunks come from the topic label itself (e.g. "redis"/"缓存",
    # the same token shape interview_state._TOPIC_TOKEN produces); a label
    # chunk appearing in the question means it stayed on topic.
    anchors = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z][a-zA-Z0-9+#.\-/]{2,}", topic.lower()) or [topic.lower()]
    return any(anchor in lowered for anchor in anchors)
