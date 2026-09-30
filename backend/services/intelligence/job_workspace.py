"""Job Workspace (Stage L1/L2): Candidate x Job preparation surface.

Composes the deterministic pieces the Intelligence Core already owns into the
Prepare workspace: Gap Map, Attack Surface, Question Graph and Stories. The
same Gap Map feeds Mock so practice follows the candidate's real gaps instead
of a random question bank.

 INVARIANT:
  - Everything produced here is a *question* or a *preparation hint*, never a
    personal fact. Story prompts point the candidate at their own material;
    they never invent an event (canonical 29: 没有真实故事，不编事件).
  - Learning signals come only from policy-approved memory kinds
    (knowledge_weakness / repeated_topic), see memory_policy.
"""
from __future__ import annotations

import json
import re
from typing import Any

from core.logger import get_logger
from services.intelligence.candidate_representation import extract_experience_expansion
from services.intelligence.job_representation import build_job_representation, compute_alignment

_log = get_logger("intelligence.job_workspace")

_GAP_LIMIT = 12
_ATTACK_LIMIT = 6
_PROBES_PER_CLAIM = 4
_GAP_QUESTION_ROOTS = 4
_STORY_PROMPT_LIMIT = 4
_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
_FACT_STATUSES = frozenset({"VERIFIED", "SUPPORTED"})
_METRIC = re.compile(r"\d+(?:\.\d+)?\s*(?:%|倍|万|千|ms|QPS|qps|x|X|人|天)")
# Behavioral competencies every workspace should have a real story for.
_DEFAULT_COMPETENCIES = ("ownership", "团队协作", "解决困难问题", "失败与反思")


def _topic_key(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


# ---------------------------------------------------------------------------
# Storage-backed inputs (every read degrades to empty; Prepare must not break)
# ---------------------------------------------------------------------------


def active_claims() -> list[dict[str, Any]]:
    """Active candidate's claims (id/type/text/truth_status)."""
    try:
        from services.storage import intelligence as intel_storage

        candidate_id = intel_storage.active_candidate_id()
        return intel_storage.list_claims(candidate_id) if candidate_id else []
    except Exception as exc:  # noqa: BLE001
        _log.warning("workspace claims read failed: %s", exc)
        return []


def alignment_resume_text(resume_text: str) -> str:
    """compute_alignment matches requirement terms against resume text; when
    the caller omits it, fall back to the stored active profile so alignment
    still reflects the candidate instead of reporting only gaps."""
    if (resume_text or "").strip():
        return resume_text
    try:
        from services.storage import intelligence as intel_storage

        candidate_id = intel_storage.active_candidate_id()
        if not candidate_id:
            return ""
        profile = intel_storage.get_candidate_profile(candidate_id) or {}
        return str(profile.get("profile_text") or "")
    except Exception as exc:  # noqa: BLE001
        _log.warning("workspace profile read failed: %s", exc)
        return ""


def learning_signals() -> dict[str, list[dict[str, Any]]]:
    """Cross-session learning written back by Review (policy-approved kinds)."""
    try:
        from services.storage import intelligence as intel_storage

        return {
            "knowledge_weakness": intel_storage.list_memory_items("knowledge_weakness", limit=20),
            "repeated_topic": intel_storage.list_memory_items("repeated_topic", limit=20),
        }
    except Exception as exc:  # noqa: BLE001
        _log.warning("workspace learning signals read failed: %s", exc)
        return {"knowledge_weakness": [], "repeated_topic": []}


def stored_stories() -> list[dict[str, Any]]:
    try:
        from services.storage import intelligence as intel_storage

        candidate_id = intel_storage.active_candidate_id()
        return intel_storage.list_stories(candidate_id) if candidate_id else []
    except Exception as exc:  # noqa: BLE001
        _log.warning("workspace stories read failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Pure composition
# ---------------------------------------------------------------------------


def build_gap_map(alignment: list[dict], signals: dict[str, list[dict]]) -> list[dict[str, Any]]:
    """Explainable gaps from job alignment + cross-session review learning."""
    gaps: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(topic: str, status: str, source: str, priority: str, reason: str, claim_ids: list[str] | None = None) -> None:
        key = _topic_key(topic)
        if not key or key in seen:
            return
        seen.add(key)
        gaps.append({
            "topic": topic[:80], "status": status, "source": source, "priority": priority,
            "reason": reason, "evidence_claim_ids": list(claim_ids or [])[:6],
        })

    for item in alignment:
        status = str(item.get("status") or "")
        topic = str(item.get("requirement_text") or "")
        claim_ids = item.get("evidence_claim_ids") or []
        if status == "GAP":
            priority = "high" if item.get("source") == "must_have" else "medium"
            _add(topic, status, "job_alignment", priority, "岗位要求，但你的材料里没有对应证据，需要准备", claim_ids)
        elif status == "KNOWLEDGE_MATCH":
            _add(topic, status, "job_alignment", "medium", "可以用通用知识回答，但没有证据时不能说做过", claim_ids)
        elif status == "PARTIAL_MATCH":
            _add(topic, status, "job_alignment", "low", "只有技能层面提及，准备项目细节或事实边界话术", claim_ids)

    for row in signals.get("knowledge_weakness", []):
        confirmations = int(row.get("confirmations") or 1)
        priority = "high" if confirmations >= 2 else "medium"
        _add(str(row.get("text") or ""), "REVIEW_WEAKNESS", "review", priority,
             f"复盘中暴露的薄弱点（出现 {confirmations} 次）")
    for row in signals.get("repeated_topic", []):
        _add(str(row.get("text") or ""), "REPEATED_TOPIC", "review", "medium", "多场面试反复被追问的主题")

    gaps.sort(key=lambda gap: _PRIORITY_RANK.get(gap["priority"], 3))
    return gaps[:_GAP_LIMIT]


def build_attack_surface(claims: list[dict], alignment: list[dict]) -> list[dict[str, Any]]:
    """Resume claims an interviewer is most likely to dig into, with probes.
    Job-aligned and metric-bearing claims come first (interviewers ask for numbers)."""
    aligned_ids = {cid for item in alignment for cid in (item.get("evidence_claim_ids") or [])}
    surface: list[tuple[int, dict[str, Any]]] = []
    for claim in claims:
        if str(claim.get("truth_status") or "") not in _FACT_STATUSES or claim.get("type") != "fact":
            continue
        text = str(claim.get("text") or "").strip()
        if not text:
            continue
        has_metric = bool(_METRIC.search(text))
        job_aligned = claim.get("id") in aligned_ids
        risks = []
        if has_metric:
            risks.append("指标会被追问口径与来源")
        if job_aligned:
            risks.append("与岗位要求直接相关")
        surface.append((
            (0 if job_aligned else 1) + (0 if has_metric else 1),
            {
                "claim_id": claim.get("id", ""), "text": text[:160],
                "truth_status": claim.get("truth_status"), "job_aligned": job_aligned,
                "risks": risks, "probes": extract_experience_expansion(text)[:_PROBES_PER_CLAIM],
            },
        ))
    surface.sort(key=lambda pair: pair[0])
    return [item for _, item in surface[:_ATTACK_LIMIT]]


def build_question_graph(attack_surface: list[dict], gap_map: list[dict]) -> list[dict[str, Any]]:
    """A question *tree* (parent_id links), not a question list: deep-dive
    chains for claims and knowledge -> boundary -> design chains for gaps."""
    nodes: list[dict[str, Any]] = []

    def _node(text: str, kind: str, source: str, parent_id: str = "") -> str:
        node_id = f"q{len(nodes) + 1}"
        nodes.append({"id": node_id, "text": text, "kind": kind, "source": source, "parent_id": parent_id})
        return node_id

    for item in attack_surface:
        root = _node(f"讲讲这段经历：{item['text'][:60]}", "PROJECT_DEEP_DIVE", item["claim_id"])
        for probe in item["probes"]:
            _node(probe, "FOLLOW_UP", item["claim_id"], root)

    for gap in gap_map[:_GAP_QUESTION_ROOTS]:
        topic = gap["topic"][:40]
        root = _node(f"谈谈你对「{topic}」的理解？", "KNOWLEDGE", gap["source"])
        boundary = _node(f"你实际做过「{topic}」相关的事情吗？", "EXPERIENCE_BOUNDARY", gap["source"], root)
        _node(f"如果让你来落地「{topic}」，你会怎么做？", "OPEN_DESIGN", gap["source"], boundary)
    return nodes


def build_stories(stories: list[dict], competencies: list[str], claims: list[dict]) -> dict[str, Any]:
    """Real stories from storage + prompts for competencies still lacking one.
    Prompts name candidate-owned lines to mine; they never contain an event."""
    real = []
    covered: set[str] = set()
    for story in stories:
        try:
            tags = json.loads(story.get("tags_json") or "[]")
        except (TypeError, json.JSONDecodeError):
            tags = []
        tags = [str(tag) for tag in tags if str(tag).strip()]
        covered.update(_topic_key(tag) for tag in tags)
        real.append({
            "id": story.get("id", ""), "title": story.get("title", ""),
            "tags": tags, "truth_status": story.get("truth_status", ""),
        })
    fact_lines = [
        str(claim.get("text") or "")[:80] for claim in claims
        if str(claim.get("truth_status") or "") in _FACT_STATUSES and claim.get("type") == "fact"
    ]
    wanted = list(dict.fromkeys([*competencies, *_DEFAULT_COMPETENCIES]))
    prompts = [
        {
            "competency": competency,
            "hint": f"从你的真实经历里找一个体现「{competency}」的事件，按 情境/挑战/行动/结果/反思 整理",
            "candidate_sources": fact_lines[:2],
        }
        for competency in wanted if _topic_key(competency) not in covered
    ][:_STORY_PROMPT_LIMIT]
    return {"items": real, "prompts": prompts}


def compose_workspace(
    job_payload: dict[str, Any],
    alignment: list[dict],
    claims: list[dict],
    stories: list[dict],
    signals: dict[str, list[dict]],
) -> dict[str, Any]:
    gap_map = build_gap_map(alignment, signals)
    attack_surface = build_attack_surface(claims, alignment)
    return {
        "gap_map": gap_map,
        "attack_surface": attack_surface,
        "question_graph": build_question_graph(attack_surface, gap_map),
        "stories": build_stories(stories, list(job_payload.get("competencies") or []), claims),
    }


# ---------------------------------------------------------------------------
# Mock (Stage L2): gap-driven questions instead of a random bank
# ---------------------------------------------------------------------------


def mock_gap_focus(jd_text: str, resume_text: str, limit: int = 3) -> dict[str, Any]:
    """Gap terms + opening questions for a practice session on this JD.
    Computed from the prep space's own JD (not the latest saved job) so one
    space's gaps never leak into another; never persists anything."""
    if not (jd_text or "").strip():
        return {"terms": [], "questions": []}
    job = build_job_representation(jd_text)
    claims = active_claims()
    alignment = compute_alignment(
        job,
        alignment_resume_text(resume_text),
        claim_texts=[str(claim.get("text", "")) for claim in claims],
        claim_ids=[str(claim.get("id", "")) for claim in claims],
    )
    gaps = [gap for gap in build_gap_map(alignment, learning_signals()) if gap["priority"] != "low"][:limit]
    questions = [
        {
            "question": f"谈谈你对「{gap['topic'][:40]}」的理解？如果实际没做过，也请说明你会怎么落地。",
            "type": "gap",
            "why": gap["reason"],
        }
        for gap in gaps
    ]
    return {"terms": [gap["topic"][:40] for gap in gaps], "questions": questions}
