"""Context Compiler: compile the minimal sufficient context package.

The core of v1.0 (master doc section 14): instead of stuffing every available
document into the prompt, providers contribute candidates, the compiler scores
them with explainable weights, and selects the smallest package that still
covers the question. Token budget splits Fast (realtime) from Deep.

R2 (Stage G): the compiler is the ONLY context authority on the Live path.
- Live providers read the frozen InterviewPack, never global "latest" rows.
- Every fragment carries fragment_id / source_type / source_id / content_hash
  and one logical fragment appears at most once in the final prompt.
- When compilation succeeds, build_system_prompt must not re-inject resume,
  KB hits or memo; only an explicit failure sets compiler_fallback=True.
"""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any, Protocol

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
_PROVIDER_FETCH_LIMIT = 24


class ContextProvider(Protocol):
    """Every provider contributes scored candidates for one question."""

    source_type: ContextSource

    def collect(self, question_text: str, *, limit: int = 8) -> list[ContextItem]:
        ...


# ---------------------------------------------------------------------------
# Generic providers (also used by Prepare-side tools and tests)
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
                    id=f"resume-{_digest(line)}",
                    source_type=self.source_type,
                    text=line[:400],
                    evidence_strength=0.8,
                    token_estimate=estimate_tokens(line[:400]),
                    metadata={"cue_source": "PERSONAL_EVIDENCE", "provenance": "DIRECT_EVIDENCE"},
                )
            )
        return items[:limit]


class EvidenceProvider:
    """Prepare-side provider (reads the active candidate). The Live path uses
    InterviewPackEvidenceProvider instead."""

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
                metadata={"cue_source": "PERSONAL_EVIDENCE", "provenance": "DIRECT_EVIDENCE"},
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
        items = []
        for idx, hit in enumerate(self._hits[:limit]):
            text = str(getattr(hit, "text", "") or (hit.get("text", "") if isinstance(hit, dict) else ""))[:400]
            path = str(getattr(hit, "path", "") or (hit.get("path", "") if isinstance(hit, dict) else ""))
            items.append(
                ContextItem(
                    id=f"kb-{idx}",
                    source_type=self.source_type,
                    text=text,
                    evidence_strength=0.4,
                    token_estimate=estimate_tokens(text),
                    # KB supports knowledge only, never personal experience,
                    # unless the file was explicitly marked an Evidence Source.
                    metadata={"path": path, "source_id": path or f"kb-{idx}", "cue_source": "KB_KNOWLEDGE"},
                )
            )
        return items


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


WorldKnowledgePermissionProvider = WorldKnowledgeProvider


# ---------------------------------------------------------------------------
# R2 InterviewPack providers: the Live path reads ONLY the frozen pack.
# ---------------------------------------------------------------------------

_PROVENANCE_STRENGTH = {
    "DIRECT_EVIDENCE": 0.9,
    "SUPPORTING_EVIDENCE": 0.65,
    "NO_EVIDENCE": 0.3,
    "CONFLICTING_EVIDENCE": 0.1,
}


class InterviewPackCandidateProvider:
    source_type = ContextSource.RESUME

    def __init__(self, pack):
        self._pack = pack

    def collect(self, question_text: str, *, limit: int = 8) -> list[ContextItem]:
        return ResumeProvider(self._pack.profile_text).collect(question_text, limit=limit)


class InterviewPackEvidenceProvider:
    """Claims (with their R2 axes) and evidence refs frozen into the pack."""

    source_type = ContextSource.EVIDENCE

    def __init__(self, pack):
        self._pack = pack

    def collect(self, question_text: str, *, limit: int = 8) -> list[ContextItem]:
        items: list[ContextItem] = []
        for claim in self._pack.claims:
            prov = str(claim.get("provenance_status", "NO_EVIDENCE"))
            text = str(claim.get("text", ""))[:400]
            items.append(
                ContextItem(
                    id=str(claim.get("id")),
                    source_type=self.source_type,
                    text=text,
                    evidence_strength=_PROVENANCE_STRENGTH.get(prov, 0.3),
                    token_estimate=estimate_tokens(text),
                    metadata={
                        "source_id": str(claim.get("id")),
                        "cue_source": "PERSONAL_EVIDENCE",
                        "provenance": prov,
                        "user_assertion": str(claim.get("user_assertion_status", "UNREVIEWED")),
                    },
                )
            )
        for ref in self._pack.evidence_refs:
            text = str(ref.get("text", ""))[:400]
            items.append(
                ContextItem(
                    id=str(ref.get("id")),
                    source_type=self.source_type,
                    text=text,
                    evidence_strength=0.85,
                    topic=str(ref.get("source", "")),
                    token_estimate=estimate_tokens(text),
                    metadata={"source_id": str(ref.get("id")), "cue_source": "PERSONAL_EVIDENCE", "provenance": "DIRECT_EVIDENCE"},
                )
            )
        return items[: max(limit, 24)]


class InterviewPackSkillCardProvider:
    source_type = ContextSource.CANDIDATE_GRAPH

    def __init__(self, pack):
        self._pack = pack

    def collect(self, question_text: str, *, limit: int = 6) -> list[ContextItem]:
        items = []
        for entry in self._pack.skill_cards:
            card = entry.get("card") or {}
            facts = card.get("facts") or card.get("highlights") or []
            summary = str(card.get("summary", "") or "")
            parts = [summary, *[str(f) for f in facts[:4]]]
            text = f"{entry.get('project_name', '')}：" + "；".join(p for p in parts if p)
            items.append(
                ContextItem(
                    id=str(entry.get("id")),
                    source_type=self.source_type,
                    text=text[:500],
                    evidence_strength=0.75,
                    token_estimate=estimate_tokens(text[:500]),
                    metadata={"source_id": str(entry.get("id")), "cue_source": "PERSONAL_EVIDENCE", "provenance": "SUPPORTING_EVIDENCE"},
                )
            )
        return items[:limit]


_STORY_FIELDS = (("title", "故事"), ("situation", "S"), ("challenge", "C"), ("action", "A"), ("result", "R"), ("reflection", "反思"))


class InterviewPackStoryProvider:
    source_type = ContextSource.CANDIDATE_GRAPH

    def __init__(self, pack):
        self._pack = pack

    def collect(self, question_text: str, *, limit: int = 4) -> list[ContextItem]:
        items = []
        for story in self._pack.stories:
            text = "｜".join(f"{label}:{story.get(key)}" for key, label in _STORY_FIELDS if story.get(key))
            items.append(
                ContextItem(
                    id=str(story.get("id")),
                    source_type=self.source_type,
                    text=text[:500],
                    evidence_strength=0.7,
                    token_estimate=estimate_tokens(text[:500]),
                    metadata={"source_id": str(story.get("id")), "cue_source": "PERSONAL_EVIDENCE", "provenance": "SUPPORTING_EVIDENCE"},
                )
            )
        return items[:limit]


class LongTermMemoryProvider:
    """Controlled memory frozen into the pack (weakness / topics / style).
    Never contains personal experience; see memory_policy."""

    source_type = ContextSource.SESSION_MEMORY

    def __init__(self, pack):
        self._pack = pack

    def collect(self, question_text: str, *, limit: int = 3) -> list[ContextItem]:
        weak = [t for t in (self._pack.controlled_memory.get("knowledge_weakness") or []) if t][:3]
        if not weak:
            return []
        text = "历史薄弱点（仅提示，不是事实）：" + "；".join(weak)
        return [
            ContextItem(
                id="ltm-weakness",
                source_type=self.source_type,
                text=text,
                evidence_strength=0.3,
                token_estimate=estimate_tokens(text),
                metadata={"source_id": "controlled_memory"},
            )
        ]


def pack_job_provider(pack) -> JobProvider:
    job = pack.job
    summary = ""
    if job:
        head = " @ ".join(part for part in (str(job.get("title", "") or ""), str(job.get("company", "") or "")) if part)
        summary = (f"{head}：" if head else "") + "；".join(pack.job_requirements)
    return JobProvider(job_requirements=pack.job_requirements, job_summary=summary)


# ---------------------------------------------------------------------------
# Fragment identity + dedupe
# ---------------------------------------------------------------------------

_WS = re.compile(r"[\s·•\-–—*#>、，,。.;；:：]+")


def _normalize_fragment(text: str) -> str:
    return _WS.sub("", str(text or "").lower())


def _digest(text: str) -> str:
    return hashlib.sha1(_normalize_fragment(text).encode("utf-8")).hexdigest()[:12]


def assign_fragment_identity(item: ContextItem) -> ContextItem:
    """fragment_id / source_type / source_id / content_hash on every item."""
    item.metadata = {
        **item.metadata,
        "fragment_id": item.metadata.get("fragment_id") or f"{item.source_type.value}:{item.id}",
        "source_type": item.source_type.value,
        "source_id": item.metadata.get("source_id") or item.id,
        "content_hash": _digest(item.text),
    }
    return item


def dedupe_fragments(items: list[ContextItem]) -> tuple[list[ContextItem], list[dict[str, Any]]]:
    """One logical fragment appears at most once. Exact normalized duplicates
    and a fragment fully contained in a longer kept one are dropped; the
    stronger-evidence copy wins. Original provider order is preserved."""
    ranked = sorted(range(len(items)), key=lambda i: (-items[i].evidence_strength, -len(items[i].text)))
    kept_idx: list[int] = []
    kept_norm: list[str] = []
    seen: set[str] = set()
    dropped: list[dict[str, Any]] = []
    for idx in ranked:
        item = assign_fragment_identity(items[idx])
        norm = _normalize_fragment(item.text)
        if not norm:
            continue
        content_hash = item.metadata["content_hash"]
        duplicate = content_hash in seen or (len(norm) >= 12 and any(norm in other for other in kept_norm))
        if duplicate:
            dropped.append({"id": item.id, "reason": "duplicate_fragment", "content_hash": content_hash})
            continue
        seen.add(content_hash)
        kept_idx.append(idx)
        kept_norm.append(norm)
    return [items[i] for i in sorted(kept_idx)], dropped


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
                candidates.extend(provider.collect(question_text, limit=_PROVIDER_FETCH_LIMIT))
            except Exception as exc:  # noqa: BLE001
                # One failing provider must not lose the whole package.
                _log.warning("context provider %s failed: %s", provider.source_type.value, exc)
        candidates, duplicate_drops = dedupe_fragments(candidates)

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
        dropped: list[dict] = list(duplicate_drops)
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


_PROVENANCE_TAG = {
    "SUPPORTING_EVIDENCE": "有支持材料",
    "NO_EVIDENCE": "暂无证据",
    "CONFLICTING_EVIDENCE": "来源冲突",
}


def render_context_sections(context: CompiledContext) -> list[str]:
    """Render selected items as prompt sections grouped by source. Personal
    items that are not directly sourced carry a provenance tag — the tag is
    provenance, not truth."""
    by_source: dict[str, list[str]] = {}
    for item in context.items:
        tag = _PROVENANCE_TAG.get(str(item.metadata.get("provenance", "") or ""), "")
        if str(item.metadata.get("user_assertion", "")) == "USER_CONFIRMED":
            tag = f"{tag}·用户已确认" if tag else "用户已确认"
        text = f"({tag}) {item.text}" if tag else item.text
        by_source.setdefault(item.source_type.value, []).append(text)
    sections = []
    for source, texts in by_source.items():
        sections.append(f"[{source}]\n" + "\n".join(f"- {text}" for text in texts[:8]))
    return sections


# ---------------------------------------------------------------------------
# Live entry point
# ---------------------------------------------------------------------------

def compile_live_context(
    pack,
    question_text: str,
    *,
    memo_context: str = "",
    compact_state: str = "",
    kb_hits: list | None = None,
    screen_problem: str = "",
    deep: bool = False,
    active_topic: str = "",
    session_id: str = "",
) -> tuple[CompiledContext, list[str]]:
    """Compile the Live context from the frozen pack only.

    Raises on failure so the caller can set ``compiler_fallback=True``; it
    never returns a partial package that the legacy prompt then re-fills
    (that is what produced duplicate injection in v1.x).
    """
    hits = [hit for hit in (kb_hits or []) if pack.kb_path_allowed(str(getattr(hit, "path", "") or ""))]
    providers: list[ContextProvider] = [
        InterviewPackCandidateProvider(pack),
        InterviewPackEvidenceProvider(pack),
        InterviewPackSkillCardProvider(pack),
        InterviewPackStoryProvider(pack),
        SessionMemoryProvider(memo_context=memo_context, compact_state=compact_state),
        LongTermMemoryProvider(pack),
        pack_job_provider(pack),
        KBProvider(hits),
        ScreenProvider(screen_problem),
        WorldKnowledgePermissionProvider(),
    ]
    compiled = ContextCompiler(providers).compile(
        question_text,
        deep=deep,
        active_topic=active_topic,
        job_requirements=pack.job_requirements,
        session_id=session_id,
    )
    return compiled, render_context_sections(compiled)
