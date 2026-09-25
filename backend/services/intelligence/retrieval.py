"""Hybrid retrieval scoring for the Context Compiler.

Score components stay deterministic and cheap (no cloud dependency): exact
entity match, lexical overlap, evidence strength, recency, topic continuity,
job alignment, contradiction risk, redundancy and stale-topic penalty.
Dense/semantic retrieval stays optional — when the KB later gains embeddings
the same interface accepts them without changing callers.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from services.intelligence.types import ContextItem, ContextSource

_STOPWORDS = frozenset(
    {
        "什么", "怎么", "如何", "为什么", "为何", "是否", "哪些", "介绍", "一下",
        "说说", "讲讲", "谈谈", "这个", "那个", "然后", "另外", "还有", "问题",
        "可以", "能不能", "你们", "我们", "项目", "里面", "具体", "详细",
        "the", "what", "how", "why", "can", "could", "would", "you", "your",
        "about", "this", "that", "and", "or", "are", "is", "was", "of", "in",
    }
)

# Default weights (master doc 14.2). Configurable and observable; v1.0 uses
# explainable rules, later versions may learn weights from evals.
DEFAULT_WEIGHTS: dict[str, float] = {
    "semantic_relevance": 0.28,
    "lexical_entity_match": 0.18,
    "evidence_strength": 0.14,
    "interview_recency": 0.10,
    "topic_continuity": 0.12,
    "job_alignment": 0.08,
    "candidate_importance": 0.05,
    "contradiction_risk": 0.10,
    "redundancy": 0.08,
    "stale_topic_penalty": 0.08,
}


@dataclass
class ScoreWeights:
    semantic_relevance: float = 0.28
    lexical_entity_match: float = 0.18
    evidence_strength: float = 0.14
    interview_recency: float = 0.10
    topic_continuity: float = 0.12
    job_alignment: float = 0.08
    candidate_importance: float = 0.05
    contradiction_risk: float = 0.10
    redundancy: float = 0.08
    stale_topic_penalty: float = 0.08

    def as_dict(self) -> dict[str, float]:
        return {
            "semantic_relevance": self.semantic_relevance,
            "lexical_entity_match": self.lexical_entity_match,
            "evidence_strength": self.evidence_strength,
            "interview_recency": self.interview_recency,
            "topic_continuity": self.topic_continuity,
            "job_alignment": self.job_alignment,
            "candidate_importance": self.candidate_importance,
            "contradiction_risk": self.contradiction_risk,
            "redundancy": self.redundancy,
            "stale_topic_penalty": self.stale_topic_penalty,
        }


@dataclass
class ScoredItem:
    item: ContextItem
    score: float
    breakdown: dict[str, float] = field(default_factory=dict)


def _topic_terms(text: str) -> set[str]:
    normalized = " ".join((text or "").lower().split())
    if not normalized:
        return set()
    terms: set[str] = set()
    for token in re.findall(r"[a-z][a-z0-9+#.\-_]{1,}|\d+(?:\.\d+)?", normalized):
        if token not in _STOPWORDS:
            terms.add(token)
    for block in re.findall(r"[\u4e00-\u9fff]+", normalized):
        for size in (2, 3):
            for start in range(0, len(block) - size + 1):
                term = block[start: start + size]
                if term not in _STOPWORDS:
                    terms.add(term)
    return terms


def semantic_relevance(question: str, text: str) -> float:
    """Bounded lexical-semantic relevance (Jaccard over topic terms)."""
    a, b = _topic_terms(question), _topic_terms(text)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def lexical_entity_match(question: str, text: str, entities: list[str] | None = None) -> float:
    """Exact/entity match: ASCII tech tokens and explicit entities."""
    lowered_q = (question or "").lower()
    lowered_t = (text or "").lower()
    entities = entities or []
    q_tokens = set(re.findall(r"[a-z][a-z0-9+#.\-/]{2,}", lowered_q))
    if not q_tokens and not entities:
        return 0.0
    hits = sum(1 for token in q_tokens if token in lowered_t)
    hits += sum(1 for entity in entities if entity.lower() in lowered_t)
    denom = len(q_tokens) + len(entities)
    return hits / max(1, denom)


def interview_recency(timestamp: float, now: float | None = None) -> float:
    """Linear decay over 10 minutes; dialogue items stay fresh longest."""
    now = now if now is not None else time.time()
    age = max(0.0, now - (timestamp or now))
    return max(0.0, 1.0 - age / 600.0)


def topic_continuity(item_topic: str, active_topic: str) -> float:
    if not item_topic or not active_topic:
        return 0.5
    if item_topic == active_topic:
        return 1.0
    a, b = _topic_terms(item_topic), _topic_terms(active_topic)
    if not a or not b:
        return 0.0
    return 0.3 * (len(a & b) / max(1, len(a | b)))


def job_alignment(item_text: str, job_requirements: list[str] | None = None) -> float:
    if not job_requirements:
        return 0.5
    lowered = (item_text or "").lower()
    if not lowered:
        return 0.0
    hits = sum(1 for req in job_requirements if req.lower() in lowered)
    return min(1.0, hits / max(1, min(3, len(job_requirements))))


def contradiction_risk(item: ContextItem) -> float:
    """CONTRADICTED claims are hard risks; UNKNOWN claims are soft risks."""
    status = str(item.metadata.get("truth_status", "")).upper()
    if status == "CONTRADICTED":
        return 1.0
    if status == "UNKNOWN":
        return 0.3
    return 0.0


def redundancy(text: str, already_selected: list[str]) -> float:
    lowered = (text or "").lower()
    if not lowered or not already_selected:
        return 0.0
    worst = 0.0
    for chosen in already_selected:
        a, b = _topic_terms(lowered), _topic_terms(chosen)
        if a and b:
            worst = max(worst, len(a & b) / max(1, len(a | b)))
    return worst


def score_item(
    item: ContextItem,
    *,
    question: str,
    active_topic: str = "",
    job_requirements: list[str] | None = None,
    already_selected: list[str] | None = None,
    weights: ScoreWeights | None = None,
    now: float | None = None,
) -> ScoredItem:
    """Explainable weighted score for one context candidate."""
    weights = weights or ScoreWeights()
    breakdown = {
        "semantic_relevance": semantic_relevance(question, item.text),
        "lexical_entity_match": lexical_entity_match(question, item.text, item.entities),
        "evidence_strength": max(0.0, min(1.0, item.evidence_strength)),
        "interview_recency": interview_recency(item.timestamp, now),
        "topic_continuity": topic_continuity(item.topic, active_topic),
        "job_alignment": job_alignment(item.text, job_requirements),
        "candidate_importance": max(0.0, min(1.0, float(item.metadata.get("importance", 0.5)))),
        "contradiction_risk": contradiction_risk(item),
    }
    selected = already_selected or []
    breakdown["redundancy"] = redundancy(item.text, selected)
    breakdown["stale_topic_penalty"] = (
        0.0 if not active_topic else (0.0 if item.topic == active_topic else 0.5 * (item.topic != "" and not topic_continuity(item.topic, active_topic)))
    )
    score = (
        weights.semantic_relevance * breakdown["semantic_relevance"]
        + weights.lexical_entity_match * breakdown["lexical_entity_match"]
        + weights.evidence_strength * breakdown["evidence_strength"]
        + weights.interview_recency * breakdown["interview_recency"]
        + weights.topic_continuity * breakdown["topic_continuity"]
        + weights.job_alignment * breakdown["job_alignment"]
        + weights.candidate_importance * breakdown["candidate_importance"]
        - weights.contradiction_risk * breakdown["contradiction_risk"]
        - weights.redundancy * breakdown["redundancy"]
        - weights.stale_topic_penalty * breakdown["stale_topic_penalty"]
    )
    return ScoredItem(item=item, score=round(score, 4), breakdown={k: round(v, 4) for k, v in breakdown.items()})


def rerank(scored: list[ScoredItem]) -> list[ScoredItem]:
    """Relevance first, recency as tie-breaker."""
    return sorted(scored, key=lambda entry: (entry.score, entry.item.timestamp), reverse=True)


def estimate_tokens(text: str) -> int:
    """Cheap token estimate: CJK chars ≈ 1 token each, ASCII ≈ 4 chars/token."""
    if not text:
        return 0
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    ascii_chars = len(text) - cjk
    return cjk + max(0, ascii_chars // 4)
