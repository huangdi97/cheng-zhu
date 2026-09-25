"""Semantic question-turn parsing for long interviewer utterances.

The parser deliberately separates *speech segmentation* from *answer goals*.
One interviewer turn may contain context, a primary question, several dependent
sub-questions, constraints, or multiple independent questions.  Only the last
case becomes multiple answer tasks.

The implementation is deterministic and latency-free.  Ambiguous candidates
can still pass through the existing lightweight LLM question judge later in the
dispatch pipeline.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Literal, Optional

from services.stt.text_utils import (
    classify_asr_question_candidate,
    is_backchannel_text,
    is_interview_boilerplate_text,
    normalize_transcription_for_analysis,
)


QuestionType = Literal[
    "coding",
    "system_design",
    "behavioral",
    "project",
    "troubleshooting",
    "technical",
    "hr",
    "general",
]


@dataclass
class QuestionCluster:
    primary_question: str
    subquestions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    context: list[str] = field(default_factory=list)
    question_type: QuestionType = "general"
    relation_to_previous: str = "new"
    confidence: float = 0.75

    def answer_prompt(self) -> str:
        lines = [
            "[结构化问题]",
            f"题型：{self.question_type}",
            f"主问题：{self.primary_question}",
        ]
        if self.context:
            lines.append("背景：" + "；".join(self.context))
        if self.subquestions:
            lines.append("需要完整覆盖的子问题：")
            lines.extend(f"{idx}. {item}" for idx, item in enumerate(self.subquestions, start=1))
        if self.constraints:
            lines.append("回答约束：")
            lines.extend(f"- {item}" for item in self.constraints)
        lines.append("必须忠实回答主问题字面含义，不得替换成更熟悉的相邻问题。若主问题在问是否做过/是否有经验，首句先回答做过、部分相关或没有直接做过，再解释依据。")
        lines.append("回答时先给可直接说出口的结论，再按上述问题顺序覆盖；不要遗漏子问题，也不要输出题型判断过程。")
        return "\n".join(lines)

    def display_question(self) -> str:
        count = len(self.subquestions)
        return self.primary_question if count == 0 else f"{self.primary_question}（含 {count} 个子问）"

    def task_question(self) -> str:
        """Human-readable query used for retrieval, follow-up checks and logs."""
        parts = [self.primary_question, *self.subquestions]
        text = "；".join(item for item in parts if item)
        if self.constraints:
            text += "；回答约束：" + "；".join(self.constraints)
        return text

    def payload(self) -> dict:
        return asdict(self)


@dataclass
class ParsedQuestionTurn:
    raw_text: str
    clusters: list[QuestionCluster] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)
    needs_confirmation: bool = False

    def payload(self) -> dict:
        return {
            "raw_text": self.raw_text,
            "clusters": [cluster.payload() for cluster in self.clusters],
            "ignored": list(self.ignored),
            "needs_confirmation": self.needs_confirmation,
        }


_HARD_SPLIT = re.compile(r"[？?；;。!！]+")
_SOFT_SPLIT = re.compile(
    r"[，,]\s*(?=(?:另外|还有一个|下一个|第二个问题|换个|顺便问|再问|"
    r"为什么|怎么|如何|有哪些|是否|能不能|可不可以|如果|项目里|你们|它|这个|那))",
    re.IGNORECASE,
)
_EXPLICIT_NEW = re.compile(
    r"^(?:另外|还有一个|下一个|第二个问题|换个(?:问题|话题)?|顺便问|再问(?:一个)?)",
    re.IGNORECASE,
)
_FOLLOWUP = re.compile(
    r"^(?:那|那么|这个|它|刚才|刚刚|你刚说|接着|继续|再|具体|详细|进一步|"
    r"为什么不|如果|还有呢|项目里|你们)",
    re.IGNORECASE,
)
_REPHRASE = re.compile(r"^(?:我是说|准确地说|具体来说|也就是说|换句话说|指的是)", re.IGNORECASE)
_CONSTRAINT = re.compile(
    r"(?:不要|别|先不|不用|无需|只讲|就讲|单独讲|需要结合|结合|重点讲|"
    r"用代码|写代码|给代码|不要代码|不要结合|从.+角度|以.+为例)",
    re.IGNORECASE,
)
_CONTEXT_CUE = re.compile(
    r"(?:背景是|当时|之前|目前|现在|我们这里|这个项目|这个系统|线上|日均|并发|数据量)",
    re.IGNORECASE,
)

_STOPWORDS = {
    "什么", "怎么", "如何", "为什么", "为何", "是否", "哪些", "介绍", "一下",
    "说说", "讲讲", "谈谈", "这个", "那个", "然后", "另外", "还有", "问题",
    "可以", "能不能", "可不可以", "你们", "项目", "里面", "具体", "详细",
}


def _clean_clause(text: str) -> str:
    text = normalize_transcription_for_analysis(text)
    return _EXPLICIT_NEW.sub("", text).strip(" ，,。.!！?？;；:：")


def _split_clauses(texts: list[str]) -> list[tuple[str, bool]]:
    clauses: list[tuple[str, bool]] = []
    for utterance in texts:
        raw = (utterance or "").strip()
        if not raw:
            continue
        hard_parts = [part for part in _HARD_SPLIT.split(raw) if part.strip()]
        if not hard_parts:
            hard_parts = [raw]
        for part in hard_parts:
            soft_parts = [item for item in _SOFT_SPLIT.split(part) if item.strip()]
            for item in soft_parts:
                explicit_new = bool(_EXPLICIT_NEW.match(item.strip()))
                cleaned = _clean_clause(item)
                if cleaned:
                    clauses.append((cleaned, explicit_new))
    return clauses


def _topic_tokens(text: str) -> set[str]:
    normalized = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9+#.-]+", " ", (text or "").lower())
    tokens = {token for token in normalized.split() if len(token) >= 2 and token not in _STOPWORDS}
    ascii_terms = set(re.findall(r"[a-z][a-z0-9+#.-]{1,}", normalized))
    cjk = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    cjk_terms = {cjk[i:i + 2] for i in range(max(0, len(cjk) - 1))}
    return tokens | ascii_terms | {term for term in cjk_terms if term not in _STOPWORDS}


def _topic_similarity(left: str, right: str) -> float:
    a, b = _topic_tokens(left), _topic_tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def classify_question_type(text: str) -> QuestionType:
    value = (text or "").lower()
    if re.search(r"写(?:一段)?代码|实现(?:一下)?|算法|复杂度|leetcode|sql|编程题|代码题", value):
        return "coding"
    if re.search(r"系统设计|架构|容量规划|高并发|高可用|扩展性|分库分表|限流|容灾", value):
        return "system_design"
    if re.search(r"排查|定位|故障|异常|变慢|超时|崩溃|线上问题|怎么 debug|debug", value):
        return "troubleshooting"
    if re.search(r"你的项目|项目里|项目背景|你负责|负责什么|你做过|简历|实习|上一家公司|技术难点", value):
        return "project"
    if re.search(r"冲突|协作|推动|失败经历|压力|挑战|领导力|star|行为题", value):
        return "behavioral"
    if re.search(r"薪资|到岗|离职|职业规划|为什么选择我们|加班|期望", value):
        return "hr"
    if re.search(r"原理|区别|机制|底层|为什么快|数据结构|事务|锁|缓存|网络|数据库", value):
        return "technical"
    return "general"


def _same_answer_goal(current: QuestionCluster, clause: str, explicit_new: bool) -> bool:
    if explicit_new:
        return False
    if _REPHRASE.match(clause) or _FOLLOWUP.match(clause):
        return True
    similarity = max(
        _topic_similarity(current.primary_question, clause),
        *(_topic_similarity(item, clause) for item in current.subquestions),
        0.0,
    )
    if similarity >= 0.12:
        return True
    current_type = current.question_type
    clause_type = classify_question_type(clause)
    # Several project/behavioral prompts often form one answer contract even
    # when each sub-question uses different nouns (background/action/result).
    if current_type in {"project", "behavioral"} and clause_type in {current_type, "general"}:
        return True
    return False


def parse_question_turn(
    utterances: list[str],
    *,
    previous_question: str = "",
) -> ParsedQuestionTurn:
    raw_text = " ".join((item or "").strip() for item in utterances if (item or "").strip()).strip()
    result = ParsedQuestionTurn(raw_text=raw_text)
    pending_context: list[str] = []

    for clause, explicit_new in _split_clauses(utterances):
        if is_backchannel_text(clause) or is_interview_boilerplate_text(clause):
            result.ignored.append(clause)
            continue
        if _CONSTRAINT.search(clause) and result.clusters:
            if clause not in result.clusters[-1].constraints:
                result.clusters[-1].constraints.append(clause)
            continue

        kind, cleaned = classify_asr_question_candidate(clause, 2)
        clause = cleaned or clause
        looks_contextual = kind == "ignore" or (
            kind == "candidate" and _CONTEXT_CUE.search(clause) and not re.search(r"什么|怎么|如何|为什么|吗|呢$", clause)
        )
        if looks_contextual:
            pending_context.append(clause)
            continue

        if not result.clusters:
            relation = "follow_up" if previous_question and _FOLLOWUP.match(clause) else "new"
            confidence = 0.9 if kind == "promote" else 0.66
            result.clusters.append(
                QuestionCluster(
                    primary_question=clause,
                    context=list(pending_context),
                    question_type=classify_question_type(clause),
                    relation_to_previous=relation,
                    confidence=confidence,
                )
            )
            pending_context.clear()
            continue

        current = result.clusters[-1]
        if _REPHRASE.match(clause):
            current.primary_question = _REPHRASE.sub("", clause).strip(" ，,。") or clause
            current.confidence = max(current.confidence, 0.88)
        elif _same_answer_goal(current, clause, explicit_new):
            if clause != current.primary_question and clause not in current.subquestions:
                current.subquestions.append(clause)
            current.question_type = (
                current.question_type
                if current.question_type != "general"
                else classify_question_type(clause)
            )
        else:
            result.clusters.append(
                QuestionCluster(
                    primary_question=clause,
                    context=list(pending_context),
                    question_type=classify_question_type(clause),
                    relation_to_previous="new",
                    confidence=0.9 if explicit_new or kind == "promote" else 0.64,
                )
            )
        pending_context.clear()

    if pending_context and result.clusters:
        result.clusters[-1].context.extend(pending_context)
    elif pending_context:
        result.ignored.extend(pending_context)

    result.needs_confirmation = any(cluster.confidence < 0.7 for cluster in result.clusters)
    return result


def is_auto_answer_enabled(cfg) -> bool:
    mode = str(getattr(cfg, "assist_auto_answer_mode", "smart") or "smart").lower()
    if mode == "off":
        return False
    return bool(getattr(cfg, "auto_detect", True))
