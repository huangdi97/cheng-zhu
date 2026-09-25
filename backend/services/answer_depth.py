"""Deterministic answer-depth and interview-continuity contracts.

The realtime path used to have one global "short answer" switch.  That is
useful for a plain definition, but it makes open-ended interview questions
such as "你怎么看合成数据" collapse into a shallow slogan.  This module
keeps the decision deterministic and cheap: it classifies the *shape* of the
question, then emits a small contract for the LLM.  It never supplies facts
or claims about the candidate.

The same module builds a bounded conversation bridge.  A bridge is included
only when the current question is a clear follow-up or shares topic anchors
with a recent Q&A.  Unrelated questions therefore keep the low-latency path
and do not receive noisy history.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Literal, Sequence


AnswerDepthProfile = Literal["concise", "structured", "deep", "compact_deep"]


_FOLLOWUP_CUES = (
    "那", "那么", "刚才", "刚刚", "前面", "上面", "上一轮", "接着", "继续",
    "展开", "详细", "具体", "深入", "补充", "举个例子", "为什么不", "怎么验证",
    "how did you", "how would you", "why not", "you just said", "you mentioned",
    "elaborate", "give an example", "tell me more", "follow up",
)

_OPEN_ENDED_CUES = (
    "看法", "怎么看", "如何评价", "谈谈", "评价一下", "优缺点", "利弊", "取舍",
    "权衡", "适用场景", "边界", "本质", "为什么", "为何", "怎么保证", "如何保证",
    "怎么设计", "如何设计", "如何落地", "怎么落地", "怎么验证", "如何验证",
    "怎么排查", "如何排查", "风险", "挑战", "影响", "是否值得", "应该怎么选",
    "what do you think", "how do you evaluate", "trade-off", "tradeoffs", "pros and cons",
    "why", "how would you design", "how do you validate", "what are the risks",
)

_FACTUAL_CUES = (
    "是什么", "全称", "默认端口", "多少", "几个", "列出", "定义", "含义", "缩写",
    "what is", "which port", "how many", "define", "full name",
)

_EXPERIENCE_YES_NO = (
    "做过吗", "用过吗", "有没有经验", "是否负责过", "接触过吗", "主导过吗",
    "did you use", "have you used", "have you worked", "did you build",
)

_SYNTHETIC_DATA_CUES = (
    "合成数据", "synthetic data", "数据生成", "生成数据", "仿真数据", "模拟数据",
    "data synthesis", "synthetic dataset", "data generation",
)

_STOPWORDS = frozenset(
    {
        "什么", "怎么", "如何", "为什么", "为何", "是否", "哪些", "介绍", "一下",
        "说说", "讲讲", "这个", "那个", "然后", "另外", "还有", "问题", "可以",
        "能不能", "可不可以", "你们", "我们", "项目", "里面", "具体", "详细",
        "the", "what", "how", "why", "can", "could", "would", "you", "your",
        "about", "this", "that", "and", "or", "are", "is",
    }
)


def _normalize(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _contains_any(text: str, phrases: Iterable[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _topic_terms(text: str) -> set[str]:
    normalized = _normalize(text)
    if not normalized:
        return set()
    terms: set[str] = set()
    for token in re.findall(r"[a-z][a-z0-9+#._-]{1,}|\d+(?:\.\d+)?", normalized):
        if token not in _STOPWORDS:
            terms.add(token)
    for block in re.findall(r"[\u4e00-\u9fff]+", normalized):
        # Bigrams retain useful technical anchors (合成/成数/数据, Kafka/缓存,
        # etc.) without requiring a tokenizer or an LLM call.
        for size in (2, 3):
            for start in range(0, len(block) - size + 1):
                term = block[start : start + size]
                if term not in _STOPWORDS:
                    terms.add(term)
    return terms


def topic_overlap(left: str, right: str) -> float:
    """Return a bounded lexical overlap score for continuity gating."""
    a, b = _topic_terms(left), _topic_terms(right)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def classify_answer_depth(
    question: str,
    *,
    question_type: str = "",
    relation_to_previous: str = "",
    high_churn_short_answer: bool = False,
) -> AnswerDepthProfile:
    """Choose the answer shape without making a factual claim.

    ``concise`` is deliberately retained for direct lookup/definition
    questions.  Open opinions, design/troubleshooting questions and explicit
    follow-ups get a multi-layer contract even when the realtime concise
    switch is on.  High-churn follow-ups use the same dimensions in a smaller
    envelope so the assistant can keep up with speech.
    """
    text = _normalize(question)
    qtype = _normalize(question_type)
    relation = _normalize(relation_to_previous)
    if not text:
        return "concise"
    if _contains_any(text, _EXPERIENCE_YES_NO):
        return "concise"

    explicit_followup = relation in {"follow_up", "followup", "continuation"}
    explicit_followup = explicit_followup or _contains_any(text, _FOLLOWUP_CUES)
    open_ended = _contains_any(text, _OPEN_ENDED_CUES)
    factual = _contains_any(text, _FACTUAL_CUES) and not open_ended
    complex_type = qtype in {"system_design", "troubleshooting", "behavioral", "project"}
    synthetic = _contains_any(text, _SYNTHETIC_DATA_CUES)

    if synthetic or open_ended or complex_type or explicit_followup:
        return "compact_deep" if high_churn_short_answer else "deep"
    if factual:
        return "concise"
    if qtype in {"technical", "coding", "general"} and len(text) >= 18:
        return "structured"
    return "concise"


def build_answer_depth_contract(
    question: str,
    *,
    profile: AnswerDepthProfile = "concise",
    question_type: str = "",
    relation_to_previous: str = "",
) -> str:
    """Build a prompt-only depth contract for the current question."""
    if profile == "concise":
        return ""

    prefix = (
        "\n本题回答深度协议（这是输出质量要求，不是要朗读给面试官的元话术）：\n"
        "- 先用 1-2 句直接回答当前问题，再展开原因；不要只给定义、口号或名词堆砌。\n"
    )
    if profile == "structured":
        return prefix + (
            "- 至少补一层机制或因果链，再给一个工程边界/取舍；只覆盖与题目直接相关的内容。\n"
            "- 如果是追问，优先补上一轮没有说过的验证、反例或失败场景，不要重播上一轮答案。\n"
        )

    if profile == "compact_deep":
        compact_line = (
            "- 受实时语音节奏限制，控制在约 180-300 字，但至少覆盖 3 个不同维度：判断、原因/机制、边界、验证指标。\n"
        )
    else:
        compact_line = (
            "- 这是开放题/追问，按‘结论 → 机制与因果 → 工程取舍/风险 → 验证指标 → 条件化结论’展开；每层只保留最有价值的 1-2 句。\n"
        )
    body = prefix + compact_line + (
        "- ‘看法/评价/是否值得’类问题必须明确立场和适用条件，同时说清什么时候不该用、最大的失败模式是什么，以及用什么指标或实验验证；不要把多个优点罗列完就结束。\n"
        "- 设计/排障类问题必须说明关键决策为什么这样选、替代方案牺牲什么、如何观测、灰度/回滚或止损。\n"
        "- 可以使用匿名或假设工程例子，但必须标明‘比如/如果’，不能把上下文或假设写成候选人亲历；个人经历仍以简历和实际口述为准。\n"
        "- 若当前问题承接上一轮，先回答当前新增问点，再明确连接上一轮的对象/决策；只复用相关事实，并补一个新角度（机制、边界、指标或反例）。\n"
    )
    if _contains_any(_normalize(question), _SYNTHETIC_DATA_CUES):
        body += (
            "- 合成数据专项深度要求：区分生成目标（训练/测试/仿真/隐私保护），说明生成机制与真实分布的关系；至少讨论 fidelity（像不像）、utility（对下游任务是否有用）、privacy/leakage（是否泄露真实样本）、长尾/稀有事件覆盖、数据泄漏与分布漂移。\n"
            "- 还要给出真实数据、合成数据或混合数据的选择条件，以及离线指标 + 真实线上/回放验证的闭环；不能用‘成本低、隐私好、扩充样本’三句概括。\n"
        )
    return body


@dataclass(frozen=True)
class _ContextCandidate:
    question: str
    answer: str
    score: float
    is_last: bool = False


def _qa_value(qa: Any, field: str) -> str:
    if isinstance(qa, dict):
        return str(qa.get(field) or "").strip()
    return str(getattr(qa, field, "") or "").strip()


def _clip(text: str, max_chars: int) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= max_chars:
        return clean
    return clean[: max(0, max_chars - 1)].rstrip() + "…"


def _is_followup_text(text: str) -> bool:
    normalized = _normalize(text)
    return len(normalized) <= 72 and _contains_any(normalized, _FOLLOWUP_CUES)


def build_conversation_bridge(
    current_question: str,
    *,
    recent_qas: Sequence[Any] = (),
    candidate_answer: str = "",
    relation_to_previous: str = "",
    force: bool = False,
    max_chars: int = 2600,
) -> str:
    """Return bounded, relevant Q&A context for a new LLM request.

    The bridge is intentionally a *reference* section.  It tells the model
    which prior words can be connected, while making the current question the
    only task and preventing assistant suggestions from becoming candidate
    facts.
    """
    current = _normalize(current_question)
    if not current or not recent_qas:
        return ""
    relation = _normalize(relation_to_previous)
    explicit_followup = force or relation in {"follow_up", "followup", "continuation"} or _is_followup_text(current)
    candidates: list[_ContextCandidate] = []
    qas = list(recent_qas)[-5:]
    for idx, qa in enumerate(qas):
        question = _qa_value(qa, "question")
        answer = _qa_value(qa, "answer")
        if not question and not answer:
            continue
        # A long answer can dilute the overlap of a very relevant question.
        # Score the interviewer wording and the answer separately, then keep
        # the stronger signal.
        score = max(topic_overlap(current, question), topic_overlap(current, answer))
        if idx == len(qas) - 1:
            score += 0.03
        if explicit_followup and idx == len(qas) - 1:
            score = max(score, 0.18)
        if score >= 0.08 or (explicit_followup and idx == len(qas) - 1):
            candidates.append(_ContextCandidate(question, answer, score, idx == len(qas) - 1))

    if not candidates:
        return ""
    # Relevance wins over recency.  Recency is only the tie-breaker; otherwise
    # an unrelated latest turn could displace an older but truly connected
    # answer and make the bridge noisy.
    candidates.sort(key=lambda item: (item.score, item.is_last), reverse=True)
    selected = candidates[:2]

    lines = [
        "[面试连续上下文：仅作承接参考]",
        "当前面试官问题是唯一需要直接回答的任务；以下内容只用于继承前文对象、决策和候选人已经说过的线索。",
    ]
    for idx, item in enumerate(selected, start=1):
        lines.append(f"相关前文 {idx} - 面试官：{_clip(item.question, 420)}")
        if item.answer:
            lines.append(f"相关前文 {idx} - 助手建议答案（不等于候选人事实）：{_clip(item.answer, 620)}")
        if item.is_last and candidate_answer:
            lines.append(
                "相关前文 - 候选人实际口述转写（可能有 ASR 误差，仅作线索）："
                + _clip(candidate_answer, 760)
            )
    lines.extend(
        [
            "承接规则：先回答当前新增问点；只有当前问题确实承接时才引用前文，不要整段复读。",
            "如果前文是助手建议而不是候选人实际口述，不得把其中的项目、数字或经历改写成候选人做过。",
            "需要延伸时优先补充一个前文没有覆盖的机制、取舍、失败边界、验证指标或反例。",
        ]
    )
    result = "\n".join(lines)
    return result if len(result) <= max_chars else result[: max(0, max_chars - 1)].rstrip() + "…"
