"""Deterministic factual grounding for personal-experience interview questions.

LLMs are good at phrasing an answer but must not decide whether the candidate
has actually done something.  This module detects experience-verification
questions, locks the asked subject, and derives a conservative evidence state
from user-owned resume/notes before a model is called.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal


GroundingStatus = Literal[
    "not_applicable",
    "supported",
    "related_only",
    "explicit_negative",
    "unsupported",
    "no_profile",
]


_EXPERIENCE_QUESTION = re.compile(
    r"(?:你|您|自己|个人|之前|以前|工作中|项目中|项目里|有没有|是否|有无)?.{0,14}"
    r"(?:做过|用过|使用过|接触过|负责过|参与过|实现过|落地过|部署过|"
    r"维护过|开发过|设计过|搭建过|处理过|有.{0,24}经验|熟悉过)"
    r"|(?:有没有|是否有|有无).{0,32}(?:经验|经历)",
    re.IGNORECASE,
)
_EN_EXPERIENCE_QUESTION = re.compile(
    r"\b(?:have you|did you|do you have experience|worked with|used|built|owned|implemented|deployed)\b",
    re.IGNORECASE,
)
_SUBJECT_AFTER_VERB = re.compile(
    r"(?:做过|用过|使用过|接触过|负责过|参与过|实现过|落地过|部署过|维护过|"
    r"开发过|设计过|搭建过|处理过|熟悉过)\s*(.+?)(?:吗|么|没有|没|呢|[?？]|$)",
    re.IGNORECASE,
)
_SUBJECT_AFTER_EXPERIENCE = re.compile(
    r"(?:有没有|是否有|有无|有)\s*(.+?)(?:的)?(?:相关)?(?:经验|经历)(?:吗|么|呢|[?？]|$)",
    re.IGNORECASE,
)
_SUBJECT_BEFORE_EXPERIENCE = re.compile(
    r"(?:对|关于|在|针对)\s*(.+?)\s*(?:有|具备|拥有)(?:的)?(?:相关)?(?:经验|经历)(?:吗|么|呢|[?？]|$)",
    re.IGNORECASE,
)
_EN_SUBJECT = re.compile(
    r"(?:worked with|used|built|owned|implemented|deployed|experience (?:with|in))\s+(.+?)(?:\?|$)",
    re.IGNORECASE,
)
_EVIDENCE_ACTION = re.compile(
    r"做过|使用|采用|负责|参与|实现|落地|部署|维护|开发|设计|搭建|处理|优化|治理|"
    r"项目|经历|实践|worked|used|built|owned|implemented|deployed|maintained|designed",
    re.IGNORECASE,
)
_POSITIVE_EXPERIENCE_CLAIM = re.compile(
    r"(?:我|我们)?(?:确实|曾经|之前|实际|有|在.{0,16})?"
    r"(?:做过|用过|使用过|接触过|负责过|参与过|实现过|落地过|部署过|"
    r"维护过|开发过|设计过|搭建过)",
    re.IGNORECASE,
)
_DIRECT_PROJECT_CLAIM = re.compile(
    r"(?:做过|用过|使用过|接触过|熟悉过|负责过|参与过|实现过|落地过|部署过|"
    r"维护过|开发过|设计过|搭建过|有.{0,6}(?:经验|经历))",
    re.IGNORECASE,
)
_INTERNAL_OUTPUT_LEAK = re.compile(
    r"(?:简历|候选人材料|事实备注|证据|资料|系统|助手).{0,18}"
    r"(?:没有|未|不足|缺少|无法)|"
    r"(?:没有|未|无法|不能).{0,18}(?:挂载|提供|加载|读取).{0,18}"
    r"(?:简历|候选人材料|资料|经历|事实|回答)|"
    r"(?:无法|不能).{0,8}(?:确认|核验).{0,12}(?:经历|资料|事实|回答)",
    re.IGNORECASE,
)
_EXTRA_CONCRETE_DETAIL_MARKERS = (
    "缓存旁路", "读写分离", "双删", "布隆", "分布式锁", "消息队列", "高可用", "集群",
    "主从", "哨兵", "分片", "限流", "降级", "重试", "幂等", "监控", "告警", "压测",
    "灰度", "回滚", "线上", "生产", "日均", "并发", "吞吐", "延迟", "成功率", "脏读",
    "缓存更新", "失效策略", "数据库", "读写", "过期策略", "TTL",
)
_OUTPUT_GENERIC_ASCII = {
    "i", "me", "my", "we", "the", "a", "an", "and", "or", "to", "of", "in", "on", "with",
    "for", "from", "as", "is", "was", "were", "have", "has", "had", "do", "did", "not", "no",
    "yes", "only", "some", "part", "limited", "direct", "project", "experience", "used", "use",
    "worked", "work", "built", "owned", "implemented", "designed", "mainly", "because", "but",
}
_GENERIC_TERMS = {
    "相关", "项目", "经验", "经历", "技术", "东西", "这个", "那个", "工作", "方面",
    "使用", "负责", "参与", "实现", "落地", "开发", "设计", "有没有", "是否",
    "哪些", "什么", "哪类", "哪一个", "哪些类型", "某个东西",
    "have", "you", "with", "experience", "worked", "used", "built",
}


_NO_DIRECT_EXPERIENCE = re.compile(
    r"(?:没有|没|未|从未|暂无|没有可确认的).{0,12}"
    r"(?:直接)?(?:做过|用过|使用过|接触过|负责过|参与过|实现过|落地过|"
    r"部署过|维护过|开发过|设计过|搭建过|项目经历|项目经验|直接经历)",
    re.IGNORECASE,
)
_RELATED_EXPERIENCE_BOUNDARY = re.compile(
    r"(?:有接触|接触过|部分相关|部分经验|有限接触|没有完整(?:项目)?(?:落地)?经验|"
    r"只有(?:部分|有限)相关经验)",
    re.IGNORECASE,
)
_UNSUPPORTED_PERSONAL_KNOWLEDGE = re.compile(
    r"(?:我|本人).{0,5}(?:掌握|熟悉|了解|精通|擅长|有.{0,4}经验|会用|用过|"
    r"做过|负责过|参与过|接触过|实践过)",
    re.IGNORECASE,
)


def _clean_subject(value: str) -> str:
    text = (value or "").strip(" ，,。.!！?？;；:：")
    text = re.sub(r"^(?:你|您|自己|个人|在项目里|在项目中)\s*", "", text)
    text = re.sub(r"(?:相关)?(?:项目|经验|经历)$", "", text).strip(" 的")
    text = re.sub(r"(?:的)?(?:使用|应用|实践)$", "", text).strip(" 的")
    return text[:80]


def _extract_subject(question: str) -> str:
    for pattern in (
        _SUBJECT_AFTER_VERB,
        _SUBJECT_AFTER_EXPERIENCE,
        _SUBJECT_BEFORE_EXPERIENCE,
        _EN_SUBJECT,
    ):
        match = pattern.search(question or "")
        if match:
            subject = _clean_subject(match.group(1))
            if subject:
                return subject
    return ""


def _is_open_subject(subject: str) -> bool:
    value = (subject or "").strip().lower()
    if value.startswith(("什么", "哪些", "哪种", "哪个", "哪一", "多少")):
        return True
    return bool(re.match(r"^(?:any|what|which|whatever)(?:\b|$)", value))


def _meaningful_terms(subject: str) -> list[str]:
    lowered = (subject or "").lower()
    terms: list[str] = []
    for token in re.findall(r"[a-z][a-z0-9+#.\-/]{1,}", lowered):
        if token not in _GENERIC_TERMS and token not in terms:
            terms.append(token)
    cjk_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)
    for chunk in cjk_chunks:
        if chunk in _GENERIC_TERMS:
            continue
        if len(chunk) <= 6:
            candidates = [chunk]
        else:
            candidates = [chunk[i:i + 4] for i in range(0, len(chunk) - 3)]
        for token in candidates:
            if token not in _GENERIC_TERMS and token not in terms:
                terms.append(token)
    return terms[:8]


def _matching_excerpt(facts: str, terms: list[str]) -> str:
    if not facts or not terms:
        return ""
    lines = [line.strip() for line in facts.splitlines() if line.strip()]
    lowered_terms = [term.lower() for term in terms]
    for line in lines:
        lowered = line.lower()
        # A composite subject such as “Redis 集群” or “Kafka in production”
        # is only directly supported when the same evidence line covers every
        # qualifier. Matching just “Redis” would silently turn a narrower
        # question into a broader claim.
        if all(term in lowered for term in lowered_terms):
            return line[:360]
    return ""


def _partial_matching_excerpt(facts: str, terms: list[str]) -> str:
    """Pick adjacent evidence when only part of a composite subject is known."""
    if not facts or not terms:
        return ""
    lines = [line.strip() for line in facts.splitlines() if line.strip()]
    lowered_terms = [term.lower() for term in terms]
    for line in lines:
        lowered = line.lower()
        if any(term in lowered for term in lowered_terms):
            return line[:360]
    return _related_excerpt(facts)


def _related_excerpt(facts: str) -> str:
    """Pick a nearby candidate project/skill line for an unseen topic."""
    lines = [line.strip() for line in facts.splitlines() if line.strip()]
    for line in lines:
        if _EVIDENCE_ACTION.search(line):
            return line[:360]
    return lines[0][:360] if lines else ""


def _has_explicit_negative_experience(excerpt: str, terms: list[str]) -> bool:
    """Detect a negative *experience* claim, not an unrelated missing metric.

    For example, “没有做过 Redis” is negative evidence, while
    “做过 Redis；没有提供线上规模” is still positive experience evidence.
    """
    if not excerpt or not terms:
        return False
    for term in terms:
        token = re.escape(term)
        before_subject = re.compile(
            rf"(?:没有|没|未|从未)\s*(?:直接)?\s*"
            rf"(?:做过|用过|使用过|接触过|负责过|参与过|实现过|落地过|部署过|"
            rf"维护过|开发过|设计过|搭建过)\s*.{{0,20}}{token}",
            re.IGNORECASE,
        )
        subject_then_negative = re.compile(
            rf"{token}.{{0,16}}(?:没有|没|未|无).{{0,8}}(?:经验|经历|做过|用过|使用过)",
            re.IGNORECASE,
        )
        no_experience_with = re.compile(
            rf"(?:无|没有|没).{{0,8}}{token}.{{0,8}}(?:经验|经历)|"
            rf"(?:never\s+(?:used|worked with)|no experience (?:with|in)|not used).{{0,20}}{token}",
            re.IGNORECASE,
        )
        if before_subject.search(excerpt) or subject_then_negative.search(excerpt) or no_experience_with.search(excerpt):
            return True
    return False


def _naturalize_excerpt(excerpt: str) -> str:
    """Turn one resume bullet into a short candidate-spoken clause."""
    text = (excerpt or "").strip(" \t\r\n-•。；;")
    if not text:
        return ""
    text = re.sub(r"^(?:技能|技术栈|熟悉|了解)[：:]\s*", "", text)
    # Resume bullets commonly use “Project: action”.  Keep the project name,
    # but make the clause sound like a spoken first-person answer.
    match = re.match(r"^(.{1,28}?)[：:] *(.+)$", text)
    if match and ("项目" in match.group(1) or re.search(r"project|system|service", match.group(1), re.I)):
        text = f"在{match.group(1).strip()}里，{match.group(2).strip()}"
    for source, target in (
        ("使用", "我用"),
        ("采用", "我采用"),
        ("负责", "我负责"),
        ("参与", "我参与"),
        ("实现", "我实现"),
        ("搭建", "我搭建"),
        ("设计", "我设计"),
        ("开发", "我开发"),
    ):
        if text.startswith(source):
            text = target + text[len(source):]
            break
    # The action often follows a project prefix after the first rewrite.
    text = re.sub(r"([，,；;]\s*)使用", r"\1我用", text, count=1)
    text = re.sub(r"([，,；;]\s*)负责", r"\1我负责", text, count=1)
    return text.rstrip("。；;，,")


def _answer_has_required_subject(answer: str, subject: str) -> bool:
    answer_lc = (answer or "").lower()
    terms = _meaningful_terms(subject)
    ascii_terms = [term for term in terms if re.fullmatch(r"[a-z][a-z0-9+#.\-/]*", term)]
    if ascii_terms:
        return all(term in answer_lc for term in ascii_terms)
    return bool(terms) and any(term in answer_lc for term in terms)


def _claim_is_negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 16):start]
    return bool(re.search(r"(?:没有|没|未|从未|不|尚未).{0,8}$", prefix, re.IGNORECASE))


def _has_positive_experience_claim(text: str) -> bool:
    for match in _POSITIVE_EXPERIENCE_CLAIM.finditer(text or ""):
        if not _claim_is_negated(text, match.start()):
            return True
    # Spoken answers often use the bare form “我用 Redis …” rather than
    # “我用过 Redis …”.  Keep that form factual too, but only with a
    # first-person subject; “用 Redis 可以…” is a general explanation.
    bare_claim = re.compile(
        r"(?:我|本人|我们)\s*(?:用|使用|负责|参与|实现|落地|部署|维护|开发|设计|搭建)",
        re.IGNORECASE,
    )
    return any(not _claim_is_negated(text, match.start()) for match in bare_claim.finditer(text or ""))


def _has_unsupported_personal_knowledge(text: str) -> bool:
    """Reject ungrounded first-person skill claims, but keep honest negations."""
    for match in _UNSUPPORTED_PERSONAL_KNOWLEDGE.finditer(text or ""):
        inner = re.search(
            r"(?:掌握|熟悉|了解|精通|擅长|有.{0,4}经验|会用|用过|做过|负责过|参与过|接触过|实践过)",
            match.group(),
            re.IGNORECASE,
        )
        claim_start = match.start() + (inner.start() if inner else 0)
        if not _claim_is_negated(text, claim_start):
            return True
    return False


def _direct_claim_about_subject(text: str, subject: str) -> bool:
    """Whether text promotes the asked subject into a positive experience claim."""
    terms = _meaningful_terms(subject)
    if not terms:
        return False
    for claim in _DIRECT_PROJECT_CLAIM.finditer(text or ""):
        if _claim_is_negated(text, claim.start()):
            continue
        window_start = max(0, claim.start() - 28)
        window_end = min(len(text), claim.end() + 36)
        window = text[window_start:window_end].lower()
        if any(term in window for term in terms):
            return True
    return False


def _evidence_anchor_in_answer(answer: str, evidence: str) -> bool:
    """Require an adjacent-experience claim to reuse a supplied fact anchor."""
    if not evidence:
        return False
    answer_lc = (answer or "").lower()
    evidence_terms = [
        token for token in re.findall(r"[a-z][a-z0-9+#.\-/]{1,}", evidence.lower())
        if token not in _OUTPUT_GENERIC_ASCII
    ]
    if any(token in answer_lc for token in evidence_terms):
        return True
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", evidence.lower()):
        if len(chunk) >= 2 and chunk in answer_lc:
            return True
    return False


def _generated_answer_is_grounded(answer: str, grounding: "ExperienceGrounding") -> bool:
    """Reject model prose that changes the candidate's factual state."""
    text = (answer or "").strip()
    if not text or not _answer_has_required_subject(text, grounding.subject):
        return False
    if _INTERNAL_OUTPUT_LEAK.search(text):
        return False
    if grounding.status == "no_profile":
        # With no profile, the model may still give a general explanation, but
        # it must first answer the yes/no experience question honestly. A
        # generic explanation without that boundary is easy to misread as a
        # claim that the candidate has done it.
        return bool(_NO_DIRECT_EXPERIENCE.search(text)) and not _has_unsupported_personal_knowledge(
            text
        ) and not _has_positive_experience_claim(text)
    if grounding.status in {"unsupported", "explicit_negative", "related_only"}:
        # Related technologies may be discussed, but the asked subject cannot
        # be promoted into a direct project claim.
        if _direct_claim_about_subject(text, grounding.subject):
            return False
        evidence_lc = (grounding.evidence_excerpt or "").lower()
        subject_lc = grounding.subject.lower()
        has_positive_claim = _has_positive_experience_claim(text)
        if has_positive_claim:
            for marker in _EXTRA_CONCRETE_DETAIL_MARKERS:
                if marker in text and marker not in evidence_lc and marker not in subject_lc:
                    return False
        if grounding.status == "related_only":
            # A skill-list hit is not project evidence, so do not let the
            # model upgrade “了解/接触” into “我做过”.
            return bool(
                _RELATED_EXPERIENCE_BOUNDARY.search(text)
                or _NO_DIRECT_EXPERIENCE.search(text)
            ) and not has_positive_claim
        if grounding.status == "explicit_negative":
            if not _NO_DIRECT_EXPERIENCE.search(text):
                return False
            if not _has_positive_experience_claim(text):
                return True
            # A negative note may still sit next to a real adjacent project;
            # permit that adjacent claim only when the answer reuses the
            # supplied anchor, never from model memory alone.
            return _evidence_anchor_in_answer(text, grounding.evidence_excerpt)
        if not _NO_DIRECT_EXPERIENCE.search(text):
            return False
        if has_positive_claim and not _evidence_anchor_in_answer(
            text, grounding.evidence_excerpt
        ):
            return False
        if has_positive_claim:
            allowed_tokens = set(
                re.findall(r"[a-z][a-z0-9+#.\-/]{1,}", evidence_lc + " " + grounding.subject.lower())
            )
            for token in re.findall(r"[A-Za-z][A-Za-z0-9+#.\-/]{1,}", text):
                lowered = token.lower()
                if lowered in _OUTPUT_GENERIC_ASCII:
                    continue
                if lowered not in allowed_tokens:
                    return False
        return True

    evidence_lc = (grounding.evidence_excerpt or "").lower()
    question_lc = grounding.subject.lower()
    for number in re.findall(r"\d+(?:\.\d+)?%?", text):
        if number not in evidence_lc and number not in question_lc:
            return False
    for marker in _EXTRA_CONCRETE_DETAIL_MARKERS:
        if marker in text and marker not in evidence_lc:
            return False
    # Technical English tokens are easy for a model to substitute (Kafka for
    # Redis, Python for Java, etc.), so only allow tokens present in the locked
    # evidence or the asked subject.
    allowed_tokens = set(re.findall(r"[a-z][a-z0-9+#.\-/]{1,}", evidence_lc + " " + question_lc))
    for token in re.findall(r"[A-Za-z][A-Za-z0-9+#.\-/]{1,}", text):
        lowered = token.lower()
        if lowered in _OUTPUT_GENERIC_ASCII:
            continue
        if lowered not in allowed_tokens:
            return False
    return _has_positive_experience_claim(text)


@dataclass(frozen=True)
class ExperienceGrounding:
    applicable: bool
    status: GroundingStatus
    subject: str = ""
    evidence_excerpt: str = ""

    @property
    def conservative(self) -> bool:
        return self.applicable and self.status != "supported"

    def public_payload(self) -> dict:
        """Return UI-safe status metadata without exposing resume excerpts."""
        return {
            "applicable": self.applicable,
            "status": self.status,
            "subject": self.subject,
            "conservative": self.conservative,
            "has_evidence": bool(self.evidence_excerpt),
        }

    def direct_answer(self) -> str:
        """Build a bounded, candidate-spoken answer from classified facts."""
        subject = self.subject or "这项技术"
        excerpt = _naturalize_excerpt(self.evidence_excerpt)
        if self.status == "supported":
            evidence = f"{excerpt}。" if excerpt else ""
            return f"做过，{evidence}".strip()
        if self.status == "related_only":
            evidence = f"主要是{excerpt}" if excerpt else ""
            return f"有接触，但没有完整项目落地经验。{evidence}。".strip()
        if self.status == "explicit_negative":
            if excerpt and re.search(r"了解|概念|学习|练习", excerpt):
                return f"没有直接做过 {subject} 项目，但我了解相关基础。"
            return f"没有直接做过 {subject} 项目，但我可以按通用方案说明怎么落地。"
        if self.status == "unsupported":
            if excerpt:
                return (
                    f"我没有直接做过 {subject}，但在相近项目里，{excerpt}。"
                    f"如果迁移到 {subject}，我会先结合具体场景和约束，再确定实现方案。"
                )
            return (
                f"我没有直接做过 {subject}，但可以按通用方法回答：先明确场景和约束，"
                "再选择方案、验证边界并补上监控和回滚。"
            )
        if self.status == "no_profile":
            return (
                f"我没有直接做过 {subject}；目前没有可确认的项目经历，但可以按通用方法回答："
                "先明确场景和约束，再选择方案、验证边界并补上监控和回滚。"
            )
        return (
            f"我对 {subject} 有接触，但还没有完整项目落地经验；我可以先按通用方法说明实现思路。"
        )

    def prompt_contract(self) -> str:
        if not self.applicable:
            return ""
        subject = self.subject or "这项技术"
        status_lines = {
            "supported": (
                "有直接实践证据。可以自然地回答做过，但所有项目、职责、技术细节、指标和结果只能来自下方唯一证据，不能补写。"
            ),
            "related_only": (
                "只有技能或知识层面的接触，不能声称负责过或完整落地过项目。最多回答有接触。"
            ),
            "explicit_negative": (
                "事实明确表示没有该对象的直接经历。必须坦诚回答没有做过，不得改成肯定或暗示项目经验。"
            ),
            "unsupported": (
                "没有直接证据证明做过该对象，但不能因此停止回答。先明确没有直接项目经验，再结合相近项目和通用技术方案回答；不得把迁移方案说成亲历。"
            ),
            "no_profile": (
                "当前没有候选人事实来源，不能声称做过，也不要把资料缺失告诉面试官。先说明没有可确认的直接经历，再用通用技术方法继续回答。"
            ),
        }
        evidence = f"\n可引用证据：{self.evidence_excerpt}" if self.evidence_excerpt else ""
        return (
            "[个人经历事实约束｜最高优先级]\n"
            "- 这是个人经历核验题，不是泛泛知识题。\n"
            f"- 当前被问对象：{subject}。必须回答这个对象，禁止偷换成别的技术或问题。\n"
            f"- 证据判定：{status_lines.get(self.status, status_lines['no_profile'])}\n"
            "- 首句必须先正面回答：做过 / 只有部分相关经验 / 没有直接做过。禁止用技术定义、方案介绍或‘这块我主要是’回避是非判断。\n"
            "- 输出 2-4 句自然口语，不要提简历、材料、证据、系统、助手或这条约束；不得虚构公司、项目、职责、线上规模、指标或结果。"
            "如果证据只够确认技术、项目动作和职责，就停在这个粒度，不要自行补充原理、机制或排障细节。"
            f"{evidence}\n"
        )


def analyze_experience_grounding(
    question: str,
    *,
    resume_text: str = "",
    interview_notes: str = "",
) -> ExperienceGrounding:
    raw = (question or "").strip()
    if not (_EXPERIENCE_QUESTION.search(raw) or _EN_EXPERIENCE_QUESTION.search(raw)):
        return ExperienceGrounding(False, "not_applicable")

    subject = _extract_subject(raw)
    # Open prompts such as “讲讲你做过的项目” need resume-grounded project
    # selection, but there is no concrete object for this object-locking guard.
    # Leave those to the existing resume rules instead of producing a generic
    # “这项技术” fallback.
    if not subject:
        return ExperienceGrounding(False, "not_applicable")
    if _is_open_subject(subject):
        return ExperienceGrounding(False, "not_applicable")
    terms = _meaningful_terms(subject)
    if not terms:
        return ExperienceGrounding(False, "not_applicable")
    facts = "\n".join(part.strip() for part in (resume_text, interview_notes) if (part or "").strip())
    if not facts:
        return ExperienceGrounding(True, "no_profile", subject)

    excerpt = _matching_excerpt(facts, terms)
    if not excerpt:
        return ExperienceGrounding(True, "unsupported", subject, _partial_matching_excerpt(facts, terms))
    if _has_explicit_negative_experience(excerpt, terms):
        return ExperienceGrounding(True, "explicit_negative", subject, excerpt)
    if _EVIDENCE_ACTION.search(excerpt):
        return ExperienceGrounding(True, "supported", subject, excerpt)
    return ExperienceGrounding(True, "related_only", subject, excerpt)


def enforce_experience_answer(answer: str, grounding: ExperienceGrounding) -> tuple[str, bool]:
    """Keep natural model phrasing only when it stays inside locked facts."""
    text = (answer or "").strip()
    if not grounding.applicable:
        return text, False
    if _generated_answer_is_grounded(text, grounding):
        return text, False
    bounded = grounding.direct_answer()
    return bounded, text != bounded
