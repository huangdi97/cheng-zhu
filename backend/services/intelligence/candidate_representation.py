"""Stage A Candidate Representation: deterministic resume-to-structure builder.

WHY: a resume upload must produce structured entities (claims, evidence,
experiences, projects, skills, education, metrics) instead of raw text.  Fully
deterministic — no LLM calls, no network, no latency — so the intelligence core
always has a question-node baseline before any model runs.

SAFETY: content is question nodes / 待补信息, never fabricated personal facts;
truth_status comes only from the source material itself (action verbs ->
SUPPORTED, skill-only 熟悉/了解/掌握 -> INFERRED; nothing beyond the source line).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from core.logger import get_logger
from services.intelligence.types import CandidateRepresentation, Claim, Evidence, EvidenceSource, TruthStatus, new_id

_log = get_logger("services.intelligence.candidate_representation")

# Same action-verb vocabulary as services.answer_grounding._EVIDENCE_ACTION.
_ACTION_VERB = re.compile(
    r"做过|使用|采用|负责|参与|实现|落地|部署|维护|开发|设计|搭建|处理|优化|治理|实践|"
    r"worked|used|built|owned|implemented|deployed|maintained|designed|developed|optimized", re.IGNORECASE,
)
_SKILL_VERB = re.compile(r"熟悉|了解|掌握|精通|擅长")  # self-assessment, never project evidence
_DEGREE = re.compile(r"本科|硕士|研究生|博士|学士|大专|专科|中专|高中|MBA|bachelor|master|phd", re.IGNORECASE)
# Lookarounds keep "10000" (a metric) from being read as the date "1000".
_PERIOD = re.compile(
    r"(?<!\d)\d{4}(?:[./年]\d{1,2})?月?(?!\d)(?:\s*[-–—~至到]\s*(?<!\d)\d{4}(?:[./年]\d{1,2})?月?(?!\d)"
    r"|\s*[-–—~至到]\s*(?:至今|present|now|current)|\s*(?:至今|present|now|current))?", re.IGNORECASE,
)
_METRIC = re.compile(
    r"(\d+(?:\.\d+)?)\s{0,2}"
    r"(%|百分之|万QPS|qps|万|亿|千|日|并发|延迟|分钟|毫秒|小时|秒|ms|GB|MB|KB|TB|人|倍|x)", re.IGNORECASE,
)
_PLAIN_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_HEADER_PREFIX_NOISE = re.compile(r"^(?:[#*•·>\-–—]+\s*|\d+[.、)）]\s*)+")
_HEADER_PUNCT = " \t:：、.。,，;；-—–~～()（）[]【】|｜/0123456789"

_SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "education": ("教育经历", "教育背景", "教育培训", "教育", "education", "academic"),
    "work": ("工作经历", "工作经验", "work experience", "工作", "experience", "employment", "career"),
    "project": ("项目经历", "项目经验", "project experience", "项目", "projects", "project"),
    "skill": ("技能栈", "专业技能", "technical skills", "技能", "skills", "skill"),
}
# Longest keywords first: 教育经历 must win over 教育, projects over project.
_HEADER_MATCHERS: list[tuple[str, str]] = sorted(
    ((key, kw) for key, kws in _SECTION_KEYWORDS.items() for kw in kws), key=lambda item: len(item[1]), reverse=True,
)

_PROFILE_TEXT_LIMIT = 4000  # profile_text persisted to SQLite is a truncated resume
_EXPANSION_LIMIT = 12
_EXPANSION_BASE = (
    "为什么要做这个项目？当时的背景和目标是什么？", "整体架构是怎么设计的？",
    "核心数据规模有多大？数据是怎么流转的？", "效果是怎么评估的？有哪些核心指标？",
    "延迟表现怎么样？有没有做过优化？", "成本大概是什么量级？有没有算过？",
    "技术上做过哪些取舍？为什么这样选？", "遇到过哪些失败场景？当时是怎么处理的？",
    "如果流量再涨10倍，现在的架构还撑得住吗？", "如果重做一次，你会改掉哪些设计？",
)
_MODEL_QUESTIONS = ("模型效果是怎么评估的？", "训练/检索数据是怎么准备和清洗的？")
_EXPANSION_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("缓存", ("缓存的一致性是怎么保证的？", "缓存的失效/过期策略是怎么设计的？")),
    ("分布式", ("分布式下的数据一致性是怎么保证的？", "有没有做过容灾或故障演练？")),
    ("模型", _MODEL_QUESTIONS),
    ("llm", _MODEL_QUESTIONS),
    ("rag", _MODEL_QUESTIONS),
)

def _stable_hash(candidate_id: str, norm_text: str) -> str:
    # hashlib (not builtin hash): stable across processes, so rebuilds upsert.
    return hashlib.sha1(f"{candidate_id}|{norm_text}".encode("utf-8")).hexdigest()[:12]

def _detect_section(line: str) -> tuple[str, str]:
    """(section_key, inline_content); '技能：Python, Go' headers carry inline content."""
    for candidate in (line, _HEADER_PREFIX_NOISE.sub("", line).strip()):
        lowered = candidate.lower()
        for section, keyword in _HEADER_MATCHERS:
            if lowered.startswith(keyword):
                rest = candidate[len(keyword):].lstrip(_HEADER_PUNCT)
                return (section, "") if not rest else (section, rest)
    return "", ""

@dataclass
class _ParseState:
    """Mutable accumulator for one deterministic build; internal only."""
    candidate_id: str = ""
    experiences: list[dict[str, Any]] = field(default_factory=list)
    projects: list[dict[str, Any]] = field(default_factory=list)
    skills: list[dict[str, Any]] = field(default_factory=list)
    education: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    evidences: list[Evidence] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)
    skill_names: set[str] = field(default_factory=set)
    # INVARIANT: normalized line -> (evidence, claim or None); duplicates never
    # create a second claim/evidence, they only bump merge counts in metadata.
    seen: dict[str, tuple[Evidence, Claim | None]] = field(default_factory=dict)

def _bump_merged(metadata_json: str) -> str:
    """Count duplicate merges in metadata; merges are never silent."""
    try:
        meta = json.loads(metadata_json)
    except json.JSONDecodeError:
        meta = {}
    meta["merged"] = int(meta.get("merged", 0)) + 1
    return json.dumps(meta, ensure_ascii=False)

def _register_source_line(state: _ParseState, line: str, norm: str, source: str) -> bool:
    """One Evidence per unique source line (+ its claim); duplicates only bump
    merge counts and return True. Action verbs -> SUPPORTED fact, skill -> INFERRED."""
    if norm in state.seen:
        evidence, claim = state.seen[norm]
        evidence.metadata_json = _bump_merged(evidence.metadata_json)
        if claim is not None:
            claim.metadata_json = _bump_merged(claim.metadata_json)
        return True
    evidence = Evidence(
        id=f"ev-{_stable_hash(state.candidate_id, norm)}",
        candidate_id=state.candidate_id, source=source, text=line,
    )
    state.evidences.append(evidence)
    # SAFETY: skill-only verbs (熟悉/了解 alone) are self-assessment -> INFERRED,
    # never SUPPORTED; plain description lines get evidence but no claim.
    is_fact = _ACTION_VERB.search(norm) is not None
    claim: Claim | None = None
    if is_fact or _SKILL_VERB.search(norm):
        claim = Claim(
            id=f"cl-{_stable_hash(state.candidate_id, norm)}", candidate_id=state.candidate_id,
            type="fact" if is_fact else "skill", text=line, source=source,
            truth_status=TruthStatus.SUPPORTED if is_fact else TruthStatus.INFERRED,
            confidence=0.8 if is_fact else 0.6,
            metadata_json=json.dumps({"evidence_id": evidence.id}, ensure_ascii=False),
        )
        state.claims.append(claim)
        state.links.append((claim.id, evidence.id))
    state.seen[norm] = (evidence, claim)
    return False

def _split_parts(text: str) -> list[str]:
    # "/" stays inside fields: "阿里巴巴/蚂蚁金服" is one company, not two.
    return [part for part in re.split(r"\s*[|｜·•]\s*|\s+", text) if part]

def _parse_work_entry(line: str) -> dict[str, Any] | None:
    """Work lines need a period or two fields; plain descriptions get no entry."""
    period_match = _PERIOD.search(line)
    rest = line.replace(period_match.group(0), " ") if period_match else line
    parts = _split_parts(rest)
    if not period_match and len(parts) < 2:
        return None
    return {
        "company": parts[0] if parts else "", "title": " ".join(parts[1:]),
        "period": period_match.group(0).strip() if period_match else "", "text": line,
    }

def _parse_project_entry(line: str) -> dict[str, Any]:
    period_match = _PERIOD.search(line)
    period = period_match.group(0).strip() if period_match else ""
    name_match = re.match(r"([^:：|｜]{1,30})[:：|｜]", line)
    name = name_match.group(1).strip() if name_match else (line if len(line) <= 30 else "")
    if period:
        name = re.sub(r"[ ：：,，—–-]", "", name.replace(period, ""))
    return {"name": name, "period": period, "text": line}

def _parse_skill_tokens(line: str) -> list[str]:
    # Strip a short '语言：' style label so the label never becomes a skill.
    line = re.sub(r"^[^:：]{1,10}[:：]\s*", "", line)
    tokens = re.split(r"[,，、;；|｜/]|\s{2,}", line)
    return [token.strip(" \t.。") for token in tokens if token.strip(" \t.。")]

def _parse_education_entry(line: str) -> dict[str, Any] | None:
    period_match, degree_match = _PERIOD.search(line), _DEGREE.search(line)
    rest = line
    if period_match:
        rest = rest.replace(period_match.group(0), " ")
    if degree_match:
        rest = rest.replace(degree_match.group(0), " ")
    parts = _split_parts(rest)
    if not parts and not degree_match:
        return None
    return {
        "school": parts[0] if parts else "", "major": parts[1] if len(parts) > 1 else "",
        "degree": degree_match.group(0) if degree_match else "",
        "period": period_match.group(0).strip() if period_match else "", "text": line,
    }

def _extract_metrics(line: str) -> list[dict[str, Any]]:
    """Numbers with units (百分比/QPS/万/日/并发/延迟/%/...); bare numbers only
    without a unit match, skipping date fragments."""
    spans = [(m.start(), m.end()) for m in _PERIOD.finditer(line)]
    metrics = [
        {"value": m.group(1), "unit": m.group(2), "text": m.group(0).strip(), "context": line}
        for m in _METRIC.finditer(line)
    ]
    if metrics:
        return metrics
    return [
        {"value": m.group(0), "unit": "", "text": m.group(0), "context": line}
        for m in _PLAIN_NUMBER.finditer(line)
        if not any(s <= m.start() and m.end() <= e for s, e in spans)
    ]

def _consume_content(state: _ParseState, line: str, section: str, source: str) -> None:
    """One source line -> evidence + optional claim + section entities + metrics."""
    norm = re.sub(r"\s+", "", line).lower()  # dedupe key: whitespace gone + case-insensitive
    if _register_source_line(state, line, norm, source):
        return
    if section == "work":
        entry = _parse_work_entry(line)
        if entry is not None:
            state.experiences.append(entry)
    elif section == "project":
        state.projects.append(_parse_project_entry(line))
    elif section == "skill":
        for name in _parse_skill_tokens(line):
            if name.lower() not in state.skill_names:
                state.skill_names.add(name.lower())
                state.skills.append({"name": name})
    elif section == "education":
        entry = _parse_education_entry(line)
        if entry is not None:
            state.education.append(entry)
    state.metrics.extend(_extract_metrics(line))

def _build_representation(resume_text: str, interview_notes: str, candidate_id: str) -> tuple[CandidateRepresentation, list[Evidence], list[tuple[str, str]]]:
    """Shared pipeline for the two public builders; evidence + links are returned
    alongside so persistence needs no second parse."""
    cid = candidate_id or new_id("cand-")
    # SAFETY: an empty resume yields an empty representation (no claims, no exception).
    if not (resume_text or "").strip():
        return CandidateRepresentation(candidate_id=cid), [], []
    state = _ParseState(candidate_id=cid)
    current_section = ""  # a section header stays active until the next header
    for raw_line in resume_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        section, inline = _detect_section(line)
        current_section = section or current_section
        if section and not inline:
            continue
        # '技能：Python, Go' — a section header also contributes its inline content
        _consume_content(state, inline if section else line, current_section, EvidenceSource.RESUME.value)
    for raw_line in (interview_notes or "").splitlines():
        line = raw_line.strip()
        if line:  # notes bypass resume sections; user-confirmed source material
            _consume_content(state, line, "", EvidenceSource.USER_CONFIRMED.value)
    rep = CandidateRepresentation(
        candidate_id=cid, profile_text=resume_text.strip(), experiences=state.experiences,
        projects=state.projects, claims=state.claims, skills=state.skills,
        metrics=state.metrics, education=state.education,
    )
    return rep, state.evidences, state.links

def build_candidate_representation(resume_text: str, interview_notes: str = "", *, candidate_id: str = "") -> CandidateRepresentation:
    """Deterministic resume(+notes) -> structured representation; no LLM calls,
    empty input returns an empty representation."""
    rep, _evidences, _links = _build_representation(resume_text, interview_notes, candidate_id)
    return rep

def rebuild_and_persist(
    resume_text: str, interview_notes: str = "", *, candidate_id: str = "",
    resume_history_id: int | None = None,
) -> CandidateRepresentation:
    """Build then persist; persistence failures are logged and never break the
    in-memory build."""
    rep, evidences, links = _build_representation(resume_text, interview_notes, candidate_id)
    try:
        # Lazy import inside the function: avoids storage-layer import cycles.
        from services.storage import intelligence as intelligence_storage
        previous_candidate_id = intelligence_storage.active_candidate_id()
        intelligence_storage.save_candidate_profile(
            rep.candidate_id, display_name="", resume_history_id=resume_history_id,
            profile_text=rep.profile_text[:_PROFILE_TEXT_LIMIT],
        )
        intelligence_storage.save_claims(rep.candidate_id, [_claim_storage_dict(c) for c in rep.claims])
        intelligence_storage.save_evidence_batch(rep.candidate_id, [asdict(e) for e in evidences], links)
        if previous_candidate_id and previous_candidate_id != rep.candidate_id:
            carry_over_user_verdicts(previous_candidate_id, rep.candidate_id)
    except Exception as exc:  # persistence must not break in-memory build
        _log.warning("candidate representation persistence failed: %s", exc)
    return rep

def _norm_claim(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def carry_over_user_verdicts(old_candidate_id: str, new_candidate_id: str) -> int:
    """R2: a resume rebuild must not erase what the user decided.

    - A claim the user confirmed / denied keeps that verdict when the same
      statement is rebuilt from the new resume (provenance comes from the new
      sources; the user axis is carried).
    - Claims that did not come from the resume (Review-confirmed session
      statements, user-added facts) are copied to the new candidate as-is.
    Returns the number of claims carried.
    """
    from services.storage import intelligence as storage

    new_rows = {_norm_claim(r["text"]): r for r in storage.list_claims(new_candidate_id, limit=5000)}
    carried = 0
    for old in storage.list_claims(old_candidate_id, limit=5000):
        verdict = str(old.get("user_assertion_status") or "UNREVIEWED")
        non_resume = str(old.get("source") or "") in {"session_statement", "user_added"}
        if verdict == "UNREVIEWED" and not non_resume:
            continue
        match = new_rows.get(_norm_claim(old["text"]))
        if match is not None:
            storage.update_claim_axes(match["id"], user_assertion_status=verdict)
            carried += 1
            continue
        if not non_resume:
            continue
        storage.save_claims(new_candidate_id, [{
            "id": old["id"],
            "type": old.get("type", "fact"),
            "text": old["text"],
            "source": old.get("source", ""),
            "truth_status": old.get("truth_status", "UNKNOWN"),
            "confidence": float(old.get("confidence") or 0.3),
            "metadata": json.loads(old.get("metadata_json") or "{}"),
        }])
        storage.update_claim_axes(
            old["id"],
            provenance_status=str(old.get("provenance_status") or "NO_EVIDENCE"),
            user_assertion_status=verdict,
        )
        carried += 1
    return carried


def _claim_storage_dict(claim: Claim) -> dict[str, Any]:
    """save_claims expects metadata as a dict; the dataclass keeps JSON text."""
    return {**claim.payload(), "metadata": json.loads(claim.metadata_json)}

def extract_experience_expansion(experience_text: str) -> list[str]:
    """Follow-up question-node dimensions for one experience/project line.
    Deterministic + keyword-aware (缓存/分布式/模型); question nodes, never facts."""
    if not (experience_text or "").strip():
        return []
    lowered = experience_text.lower()
    questions = list(_EXPANSION_BASE)
    for keyword, extra in _EXPANSION_KEYWORDS:
        if keyword in lowered:
            questions.extend(extra)
    return list(dict.fromkeys(questions))[:_EXPANSION_LIMIT]
