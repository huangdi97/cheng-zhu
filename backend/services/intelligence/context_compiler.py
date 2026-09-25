"""Context Compiler: compile the minimal sufficient context package.

The core of v1.0 (master doc section 14): instead of stuffing every available
document into the prompt, providers contribute candidates, the compiler scores
them with explainable weights, and selects the smallest package that still
covers the question. Token budget splits Fast (realtime) from Deep.
"""
from __future__ import annotations

import time
from typing import Protocol

from core.logger import get_logger
from services.intelligence.retrieval import (
    ScoreWeights,
    ScoredItem,
    estimate_tokens,
    rerank,
    score_item,
)
from services.intelligence.telemetry import record_guidance_event
from services.intelligence.types import (
    CompiledContext,
    ContextItem,
    ContextSource,
)

_log = get_logger("intelligence.context_compiler")

# Fast path keeps the first screen usable in realtime; Deep allows more depth.
FAST_BUDGET_TOKENS = 1400
DEEP_BUDGET_TOKENS = 3200
_FAST_SELECT_LIMIT = 6
_DEEP_SELECT_LIMIT = 12


class ContextProvider(Protocol):
    """Every provider contributes scored candidates for one question."""

    source_type: ContextSource

    def collect(self, question_text: str, *, limit: int = 8) -> list[ContextItem]:
        ...


# ---------------------------------------------------------------------------
# Default providers wired to existing local data
# ---------------------------------------------------------------------------

class ResumeProvider:
    source_type = ContextSource.RESUME

    def __init__(self, resume_text: str):
        self._resume_text = resume_text or ""

    def collect(self, question_text: str, *, limit: int = 8) -> list[ContextItem]:
        if not self._resume_text.strip():
            return []
        lines = [line.strip() for line in self._resume_text.splitlines() if line.strip()]
        items: list[ContextItem] = []
        for line in lines[:24]:
            items.append(
                ContextItem(
                    id=f"resume-{abs(hash(line)) % 10**10}",
                    source_type=self.source_type,
                    text=line[:400],
                    evidence_strength=0.8,
                    token_estimate=estimate_tokens(line[:400]),
                )
            )
        return items[:limit]


class EvidenceProvider:
    source_type = ContextSource.EVIDENCE

    def collect(self, question_text: str, *, limit: int = 8) -> list[ContextItem]:
        try:
            from services.storage import intelligence as intel_storage

            candidate_id = intel_storage.active_candidate_id()
            if not candidate_id:
                return []
            rows = intel_storage.list_evidence(candidate_id, limit=24)
        except Exception as exc:  # noqa: BLE001
            _log.warning("evidence provider failed: %s", exc)
            return []
        return [
            ContextItem(
                id=row["id"],
                source_type=self.source_type,
                text=str(row["text"])[:400],
                evidence_strength=0.9,
                topic=str(row.get("source", "")),
                token_estimate=estimate_tokens(str(row["text"])[:400]),
            )
            for row in rows
        ][:limit]


class SessionMemoryProvider:
    source_type = ContextSource.SESSION_MEMORY

    def __init__(self, memo_context: str = "", compact_state: str = ""):
        self._memo_context = memo_context or ""
        self._compact_state = compact_state or ""

    def collect(self, question_text: str, *, limit: int = 8) -> list[ContextItem]:
        items: list[ContextItem] = []
        if self._compact_state:
            items.append(
                ContextItem(
                    id="session-state",
                    source_type=self.source_type,
                    text=self._compact_state[:600],
                    evidence_strength=0.6,
                    token_estimate=estimate_tokens(self._compact_state[:600]),
                )
            )
        if self._memo_context:
            items.append(
                ContextItem(
                    id="session-memo",
                    source_type=self.source_type,
                    text=self._memo_context[:600],
                    evidence_strength=0.5,
                    token_estimate=estimate_tokens(self._memo_context[:600]),
                )
            )
        return items[:limit]


class JobProvider:
    source_type = ContextSource.JOB

    def __init__(self, job_requirements: list[str] | None = None, job_summary: str = ""):
        self._requirements = job_requirements or []
        self._summary = job_summary or ""

    def collect(self, question_text: str, *, limit: int = 4) -> list[ContextItem]:
        if not self._summary and not self._requirements:
            return []
        text = self._summary or "；".join(self._requirements[:8])
        return [
            ContextItem(
                id="job-context",
                source_type=self.source_type,
                text=text[:500],
                evidence_strength=0.7,
                token_estimate=estimate_tokens(text[:500]),
                metadata={"importance": 0.7},
            )
        ]


class KBProvider:
    source_type = ContextSource.KB

    def __init__(self, hits: list | None = None):
        self._hits = hits or []

    def collect(self, question_text: str, *, limit: int = 6) -> list[ContextItem]:
        return [
            ContextItem(
                id=f"kb-{idx}",
                source_type=self.source_type,
                text=str(getattr(hit, "text", "") or hit.get("text", ""))[:400],
                evidence_strength=0.4,
                token_estimate=estimate_tokens(str(getattr(hit, "text", "") or "")[:400]),
                metadata={"path": getattr(hit, "path", "")},
            )
            for idx, hit in enumerate(self._hits[:limit])
        ]


class ScreenProvider:
    source_type = ContextSource.SCREEN

    def __init__(self, screen_problem: str = ""):
        self._screen_problem = screen_problem or ""

    def collect(self, question_text: str, *, limit: int = 2) -> list[ContextItem]:
        if not self._screen_problem:
            return []
        return [
            ContextItem(
                id="screen-context",
                source_type=self.source_type,
                text=self._screen_problem[:500],
                evidence_strength=0.7,
                token_estimate=estimate_tokens(self._screen_problem[:500]),
            )
        ]


class WorldKnowledgeProvider:
    """The model's own knowledge is not a prompt item; this provider exists so
    routing can record that world knowledge was allowed for this question."""

    source_type = ContextSource.WORLD_KNOWLEDGE

    def collect(self, question_text: str, *, limit: int = 1) -> list[ContextItem]:
        return []


def token_budget(*, deep: bool) -> int:
    return DEEP_BUDGET_TOKENS if deep else FAST_BUDGET_TOKENS


class ContextCompiler:
    """Scores provider candidates and selects the minimal sufficient package."""

    def __init__(self, providers: list[ContextProvider], weights: ScoreWeights | None = None):
        self._providers = providers
        self._weights = weights or ScoreWeights()

    def compile(
        self,
        question_text: str,
        *,
        deep: bool = False,
        active_topic: str = "",
        job_requirements: list[str] | None = None,
        session_id: str = "",
    ) -> CompiledContext:
        t0 = time.monotonic()
        limit = _DEEP_SELECT_LIMIT if deep else _FAST_SELECT_LIMIT
        candidates: list[ContextItem] = []
        for provider in self._providers:
            try:
                candidates.extend(provider.collect(question_text, limit=limit))
            except Exception as exc:  # noqa: BLE001
                # One failing provider must not lose the whole package.
                _log.warning("context provider %s failed: %s", provider.source_type.value, exc)

        scored: list[ScoredItem] = []
        selected_texts: list[str] = []
        for item in candidates:
            result = score_item(
                item,
                question=question_text,
                active_topic=active_topic,
                job_requirements=job_requirements,
                already_selected=selected_texts,
                weights=self._weights,
            )
            scored.append(result)

        ordered = rerank(scored)
        budget = token_budget(deep=deep)
        items: list[ContextItem] = []
        dropped: list[dict] = []
        total = 0
        for entry in ordered:
            reason = ""
            if len(items) >= limit:
                reason = "select_limit"
            elif total + entry.item.token_estimate > budget:
                reason = "token_budget"
            elif entry.score <= 0:
                reason = "score_floor"
            if reason:
                dropped.append({"id": entry.item.id, "reason": reason, "score": entry.score})
                continue
            item = entry.item
            item.metadata = {**item.metadata, "score": entry.score, "score_breakdown": entry.breakdown}
            items.append(item)
            selected_texts.append(item.text)
            total += entry.item.token_estimate

        latency_ms = int((time.monotonic() - t0) * 1000)
        context = CompiledContext(
            items=items,
            dropped=dropped,
            total_token_estimate=total,
            budget=budget,
            latency_ms=latency_ms,
        )
        if session_id:
            try:
                record_guidance_event(
                    session_id,
                    "context_compiled",
                    latency_ms=latency_ms,
                    context_ids=[item.id for item in items],
                )
            except Exception:  # noqa: BLE001
                pass
        return context


def render_context_sections(context: CompiledContext) -> list[str]:
    """Render selected items as prompt sections grouped by source."""
    by_source: dict[str, list[str]] = {}
    for item in context.items:
        by_source.setdefault(item.source_type.value, []).append(item.text)
    sections = []
    for source, texts in by_source.items():
        sections.append(f"[{source}]\n" + "\n".join(f"- {text}" for text in texts[:8]))
    return sections
