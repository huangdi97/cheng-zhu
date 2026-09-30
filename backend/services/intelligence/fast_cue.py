"""Fast Cue (R2 Stages J/K): the scannable first screen, before Deep Answer.

Level 0 is deterministic and local. It only rearranges what the system
already holds — personal evidence from the frozen pack, KB passages, the
job focus, and boundary / risk notes. It never invents knowledge content
to look fast.

Level 1 (optional) asks a small, fast model to turn the question plus the
already-selected sources into 3-5 short spoken points (60-100 tokens). Its
output is claim-checked: any first-person claim without pack support is
dropped, and on failure L0 stands.

Every cue carries a source from the taxonomy:
  PERSONAL_EVIDENCE — may support "I actually did X" (claim + provenance)
  KB_KNOWLEDGE      — knowledge from the user's files, never personal proof
  WORLD_KNOWLEDGE   — model knowledge; never "in my project I…"
  HUMAN_COACH       — advice; never evidence, never user-confirmed

Cues are content ("RAG 更适合频繁更新的知识"), not structure labels
("结论 / 机制 / 边界 / 验证").
"""
from __future__ import annotations

import re
import time
import uuid
from typing import Any, Iterable, Optional

from services.intelligence.semantics import AssertionPolicy, CueSource
from services.intelligence.types import ResponseMode

# Structure words that must never be shown as a whole cue.
STRUCTURE_LABELS = {
    "结论", "机制", "边界", "验证", "场景", "职责", "关键动作", "结果", "反思", "直接回答", "机制/因果",
    "clarify", "requirements", "architecture", "data", "scale", "reliability", "trade-offs", "code",
}
_MAX_CUE_CHARS = 42
_FIRST_PERSON = re.compile(r"(?:我|我们|本人)[^，。,]{0,18}?(?:用过|用了|做过|负责|主导|上线|落地|部署|搭建|实现)")
_PERSONAL_MODES = {
    ResponseMode.EXPERIENCE.value,
    ResponseMode.EXPERIENCE_KNOWLEDGE.value,
    ResponseMode.BEHAVIORAL.value,
}
_BOUNDARY_MODES = {ResponseMode.EXPERIENCE_BOUNDARY_KNOWLEDGE.value}


def _clip(text: str, limit: int = _MAX_CUE_CHARS) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip(" -•·*#>")
    for sep in ("。", "；", ";", "\n"):
        if sep in value[: limit + 8]:
            value = value.split(sep, 1)[0]
            break
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _is_label(text: str) -> bool:
    return str(text or "").strip().strip("：:").lower() in STRUCTURE_LABELS


def _overlap(question: str, text: str) -> int:
    q = str(question or "").lower()
    tokens = re.findall(r"[a-z][a-z0-9+#.\-]{1,}|[一-鿿]{2}", str(text or "").lower())
    return sum(1 for t in set(tokens) if t in q)


def _subject(question: str) -> str:
    terms = re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]*(?:\s+[A-Z][A-Za-z0-9+#.\-]*)*", question or "")
    return terms[0] if terms else ""


def _cue(text: str, source: CueSource, ref: str = "", provenance: str = "") -> dict[str, Any]:
    return {"text": text, "source": source.value, "ref": ref, "provenance": provenance}


def build_l0(
    *,
    question_raw: str,
    resolved_question: str,
    plan_meta: dict[str, Any],
    response_mode: str,
    compiled_items: Iterable[Any] = (),
    kb_hits: Iterable[Any] = (),
    job_requirements: Iterable[str] = (),
    session_constraints: str = "",
) -> dict[str, Any]:
    """Deterministic cue set. Returns the guidance_fast body (no timing)."""
    assertion = str(plan_meta.get("assertion_policy", AssertionPolicy.KNOWLEDGE_ONLY.value))
    cues: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    knowledge_sources: list[dict[str, Any]] = []
    cautions: list[str] = []
    question = resolved_question or question_raw

    personal = [
        item for item in compiled_items
        if (getattr(item, "metadata", {}) or {}).get("cue_source") == CueSource.PERSONAL_EVIDENCE.value
        and (getattr(item, "metadata", {}) or {}).get("provenance") in {"DIRECT_EVIDENCE", "SUPPORTING_EVIDENCE"}
    ]
    # Only personal items that share a term with the question are relevant
    # anchors; an unrelated story or skill line is noise, not a cue.
    personal = [it for it in personal if _overlap(question, getattr(it, "text", "")) > 0]
    personal.sort(key=lambda it: -_overlap(question, getattr(it, "text", "")))

    if response_mode in _BOUNDARY_MODES or assertion in {AssertionPolicy.REQUIRE_BOUNDARY.value, AssertionPolicy.BLOCK_ASSERTION.value}:
        subject = _subject(question)
        cues.append(
            _cue(
                f"先说边界：材料里没有「{subject}」的直接经历" if subject else "先说边界：这点没有可确认的亲历",
                CueSource.PERSONAL_EVIDENCE,
                provenance="NO_EVIDENCE",
            )
        )
        cautions.append("没有来源支持，不要说成“我做过/我负责”")

    allow_personal = assertion in {AssertionPolicy.ALLOW_PERSONAL_ASSERTION.value, AssertionPolicy.ALLOW_WITH_QUALIFIER.value}
    if response_mode in _PERSONAL_MODES | _BOUNDARY_MODES or allow_personal:
        for item in personal[:3]:
            meta = getattr(item, "metadata", {}) or {}
            text = _clip(getattr(item, "text", ""))
            if not text or _is_label(text):
                continue
            prefix = "可衔接：" if response_mode in _BOUNDARY_MODES or not allow_personal else "你的："
            cues.append(_cue(prefix + text, CueSource.PERSONAL_EVIDENCE, meta.get("source_id", ""), meta.get("provenance", "")))
            anchors.append({"text": text, "source_id": meta.get("source_id", ""), "provenance": meta.get("provenance", "")})
        if assertion == AssertionPolicy.ALLOW_WITH_QUALIFIER.value:
            cautions.append("只有支持材料/本人确认：不要新增指标、角色或规模")

    for hit in list(kb_hits)[:3]:
        text = _clip(getattr(hit, "text", "") or (hit.get("text", "") if isinstance(hit, dict) else ""))
        path = str(getattr(hit, "path", "") or (hit.get("path", "") if isinstance(hit, dict) else ""))
        if not text or _is_label(text) or _FIRST_PERSON.search(text):
            continue
        if len(cues) < 5:
            cues.append(_cue(text, CueSource.KB_KNOWLEDGE, path))
        knowledge_sources.append({"type": CueSource.KB_KNOWLEDGE.value, "ref": path})

    # The job requirement is context about the role, not a knowledge or
    # personal source, so it is shown as job_focus rather than as a cue.
    job_focus = next((_clip(req, 30) for req in job_requirements if req and _overlap(question, req)), "")

    if session_constraints:
        cautions.append("不要扩展你本场口述但暂无来源的内容")
    if plan_meta.get("truth_requirement") == "SCREEN_CONTEXT_REQUIRED":
        cautions.append("先确认屏幕上的题面再作答")

    return {
        "question_raw": question_raw,
        "resolved_question": resolved_question,
        "direction": _direction(response_mode, assertion),
        "cues": cues[:5],
        "evidence_anchors": anchors,
        "knowledge_sources": knowledge_sources,
        "cautions": cautions,
        "job_focus": job_focus,
        "response_mode": response_mode,
        "dialogue_act": plan_meta.get("dialogue_act", ""),
        "content_type": plan_meta.get("content_type", ""),
        "truth_requirement": plan_meta.get("truth_requirement", ""),
        "assertion_policy": assertion,
        "level": "L0",
    }


_DIRECTIONS = {
    ResponseMode.EXPERIENCE.value: "讲你真实做过的事：先结论，再动作与结果",
    ResponseMode.EXPERIENCE_KNOWLEDGE.value: "先讲项目事实，再讲原理与取舍",
    ResponseMode.EXPERIENCE_BOUNDARY_KNOWLEDGE.value: "先说边界，再讲理解与落地做法",
    ResponseMode.KNOWLEDGE.value: "直接回答知识点，不套简历",
    ResponseMode.HYPOTHETICAL.value: "用条件句：如果…我会…",
    ResponseMode.OPEN_DESIGN.value: "先澄清约束，再给方案与取舍",
    ResponseMode.SYSTEM_DESIGN.value: "澄清需求 → 容量 → 架构 → 取舍",
    ResponseMode.CODING.value: "先讲思路和复杂度，再写代码",
    ResponseMode.OOD.value: "先列核心对象，再讲职责与关系",
    ResponseMode.BEHAVIORAL.value: "用真实故事：情境 → 行动 → 结果",
    ResponseMode.PRODUCT_CASE.value: "先澄清用户与目标，再给框架",
    ResponseMode.NEGOTIATION.value: "先表明立场，再给依据与条件",
}


def _direction(mode: str, assertion: str) -> str:
    return _DIRECTIONS.get(mode, "直接回应问题")


def finalize(body: dict[str, Any], *, qa_id: str, source: str = "AI", timing: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """WS contract for ``guidance_fast``."""
    timing = timing or {}
    return {
        "type": "guidance_fast",
        "id": qa_id,
        "cue_id": f"cue-{uuid.uuid4().hex[:10]}",
        **body,
        "source": source,
        "ttfug_user_ms": timing.get("ttfug_user_ms"),
        "ttfug_internal_ms": timing.get("ttfug_internal_ms"),
        "emitted_at": time.time(),
    }


# ---------------------------------------------------------------------------
# Level 1: tiny/fast model rewrite, claim-checked, falls back to L0
# ---------------------------------------------------------------------------

L1_SYSTEM = (
    "你是面试现场提示器。只输出 3-5 行要点，每行不超过 24 个字，以“• ”开头。"
    "要点必须是可以直接说出口的内容，不要输出“结论/机制/边界/验证”这类结构标签。"
    "不得新增候选人的个人经历、指标、角色或项目细节；个人经历只能来自[个人来源]。"
    "如果没有[个人来源]，不得写“我做过/我负责/我们上线了”。"
)


def l1_messages(question: str, l0: dict[str, Any]) -> list[dict[str, str]]:
    personal = [c["text"] for c in l0.get("cues", []) if c.get("source") == CueSource.PERSONAL_EVIDENCE.value]
    kb = [c["text"] for c in l0.get("cues", []) if c.get("source") == CueSource.KB_KNOWLEDGE.value]
    parts = [f"[问题] {question}", f"[回答方向] {l0.get('direction', '')}"]
    if personal:
        parts.append("[个人来源] " + "；".join(personal))
    if kb:
        parts.append("[资料] " + "；".join(kb))
    if l0.get("cautions"):
        parts.append("[注意] " + "；".join(l0["cautions"]))
    return [{"role": "user", "content": "\n".join(parts)}]


def parse_l1(text: str, l0: dict[str, Any], evidence_corpus: str) -> Optional[list[dict[str, Any]]]:
    """Parse and claim-check L1 output; None means keep L0."""
    lines = [re.sub(r"^[\s•\-*·\d.、]+", "", line).strip() for line in str(text or "").splitlines()]
    lines = [line for line in lines if line and not _is_label(line)]
    if not 2 <= len(lines) <= 6:
        return None
    corpus = (evidence_corpus or "").lower()
    cues: list[dict[str, Any]] = []
    for line in lines[:5]:
        claim = _FIRST_PERSON.search(line)
        if claim:
            terms = re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]{1,}", line)
            if not corpus or any(term.lower() not in corpus for term in terms) or not terms:
                continue  # unsupported first-person claim: drop the line
            cues.append(_cue(_clip(line), CueSource.PERSONAL_EVIDENCE))
        else:
            cues.append(_cue(_clip(line), CueSource.WORLD_KNOWLEDGE))
    return cues if len(cues) >= 2 else None
