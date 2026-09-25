"""Truth Boundary: unified personal-fact constraint for the intelligence core.

 COMPATIBILITY:
  - services.answer_grounding.py keeps its deterministic rules and stays the
    safety foundation; this module is the facade that raises it to the
    unified Truth Boundary (output space + claim policy + post-generation
    checker). Grounding is never weakened by new features.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from services.answer_grounding import (
    ExperienceGrounding,
    analyze_experience_grounding,
    enforce_experience_answer,
)
from services.intelligence.types import OutputSpace, TruthCheckResult, TruthStatus

# Claim policy: what language each truth status allows (master doc 9.3).
_CLAIM_POLICY: dict[str, str] = {
    "VERIFIED": "允许第一人称事实表达",
    "SUPPORTED": "允许谨慎第一人称；所有细节只能来自既有证据",
    "INFERRED": "不得升级成‘我做过’；只能表达推断",
    "UNKNOWN": "必须设边界；先说明没有可确认的经历",
    "CONTRADICTED": "禁止确定性声称；必须说明与证据矛盾",
}

# Post-generation violation detectors (master doc B4).
_METRIC_RE = re.compile(r"\d+(?:\.\d+)?%?")
_INTERNAL_LEAK = re.compile(
    r"(?:简历|候选人材料|事实备注|证据|资料|系统|助手).{0,18}(?:没有|未|不足|缺少|无法)|"
    r"(?:没有|未|无法|不能).{0,18}(?:挂载|提供|加载|读取).{0,18}(?:简历|候选人材料|资料|经历|事实|回答)|"
    r"(?:无法|不能).{0,8}(?:确认|核验).{0,12}(?:经历|资料|事实|回答)",
    re.IGNORECASE,
)
_POSITIVE_CLAIM = re.compile(
    r"(?:我|我们)(?:确实|曾经|之前|实际|有|在.{0,16})?(?:做过|用过|使用过|负责过|参与过|实现过|落地过|部署过|开发过|设计过|搭建过)"
    r"|(?:我|本人|我们)\s*(?:用|使用|负责|参与|实现|落地|部署|维护|开发|设计|搭建)",
    re.IGNORECASE,
)
_NEGATION_PREFIX = re.compile(r"(?:没有|没|未|从未|不|尚未).{0,8}$", re.IGNORECASE)
_HYPOTHETICAL_MARKERS = ("如果", "假如", "假设", "要是", "比如", "would", "if ")
_SUBJECT_SUBSTITUTION_HINT = re.compile(r"(?:这块我主要是|换个话题|说到这个|其实我更熟悉)", re.IGNORECASE)


def claim_policy_text(status: TruthStatus | str) -> str:
    """Prompt-ready claim policy line for one truth status."""
    value = status.value if isinstance(status, TruthStatus) else str(status)
    return _CLAIM_POLICY.get(value, _CLAIM_POLICY["UNKNOWN"])


def classify_output_space(grounding: ExperienceGrounding) -> OutputSpace:
    """Mandatory output-space classification from the deterministic grounding."""
    if not grounding.applicable:
        return OutputSpace.KNOWLEDGE_JUDGMENT
    if grounding.status == "supported":
        return OutputSpace.PERSONAL_FACT
    if grounding.status in {"unsupported", "explicit_negative", "no_profile"}:
        return OutputSpace.HYPOTHETICAL
    return OutputSpace.KNOWLEDGE_JUDGMENT


def map_grounding_status(status: str) -> TruthStatus:
    """Map the legacy grounding status to the unified TruthStatus enum."""
    return {
        "supported": TruthStatus.SUPPORTED,
        "related_only": TruthStatus.INFERRED,
        "explicit_negative": TruthStatus.CONTRADICTED,
        "unsupported": TruthStatus.UNKNOWN,
        "no_profile": TruthStatus.UNKNOWN,
        "not_applicable": TruthStatus.UNKNOWN,
    }.get(status, TruthStatus.UNKNOWN)


@dataclass(frozen=True)
class TruthBoundary:
    """Unified truth boundary for one question."""

    grounding: ExperienceGrounding
    output_space: OutputSpace
    truth_status: TruthStatus

    @property
    def applicable(self) -> bool:
        return self.grounding.applicable

    @property
    def conservative(self) -> bool:
        return self.grounding.conservative

    def public_payload(self) -> dict:
        return {
            **self.grounding.public_payload(),
            "output_space": self.output_space.value,
            "truth_status": self.truth_status.value,
        }

    def prompt_contract(self) -> str:
        contract = self.grounding.prompt_contract()
        if not contract:
            return ""
        return contract + (
            f"- 输出空间：{self.output_space.value}（{claim_policy_text(self.truth_status)}）。\n"
        )


def analyze_truth_boundary(
    question: str,
    *,
    resume_text: str = "",
    interview_notes: str = "",
) -> TruthBoundary:
    """Deterministic pre-generation truth boundary for one question."""
    grounding = analyze_experience_grounding(
        question,
        resume_text=resume_text,
        interview_notes=interview_notes,
    )
    return TruthBoundary(
        grounding=grounding,
        output_space=classify_output_space(grounding),
        truth_status=map_grounding_status(grounding.status),
    )


def enforce_truth(answer: str, boundary: TruthBoundary) -> tuple[str, bool]:
    """Keep model phrasing only when it stays inside locked facts."""
    return enforce_experience_answer(answer, boundary.grounding)


def check_generated_answer(
    answer: str,
    *,
    boundary: TruthBoundary,
    evidence_texts: list[str] | None = None,
    question_text: str = "",
) -> TruthCheckResult:
    """Post-generation checker (master doc B4).

    Detects unsupported personal claims, unexpected metrics, subject
    substitution, evidence mismatch, internal system leakage and contradictions;
    on violation rewrites via the deterministic bounded answer.
    """
    text = (answer or "").strip()
    violations: list[dict] = []
    actions: list[str] = []
    evidence_blob = " ".join(evidence_texts or []).lower()

    if text:
        if _INTERNAL_LEAK.search(text):
            violations.append({"kind": "internal_system_leakage", "detail": "答案泄露内部系统信息"})
        if _SUBJECT_SUBSTITUTION_HINT.search(text) and boundary.applicable:
            violations.append({"kind": "subject_substitution", "detail": "疑似偷换对象"})
        if boundary.applicable and boundary.truth_status in {TruthStatus.SUPPORTED, TruthStatus.VERIFIED}:
            for number in _METRIC_RE.findall(text):
                if number not in evidence_blob and number not in question_text.lower():
                    violations.append({"kind": "unexpected_metric", "detail": f"证据外指标 {number}"})
                    break
        if boundary.applicable and boundary.truth_status in {
            TruthStatus.UNKNOWN,
            TruthStatus.INFERRED,
            TruthStatus.CONTRADICTED,
        }:
            for match in _POSITIVE_CLAIM.finditer(text):
                prefix = text[max(0, match.start() - 16):match.start()]
                if not _NEGATION_PREFIX.search(prefix) and "如果" not in text[max(0, match.start() - 24):match.start()]:
                    violations.append({"kind": "unsupported_personal_claim", "detail": "无证据第一人称经历声称"})
                    break

    if violations:
        final_text, rewritten = enforce_truth(text, boundary)
        actions.append("rewrite_to_deterministic")
        if rewritten:
            return TruthCheckResult(
                original_text=text,
                final_text=final_text,
                passed=False,
                violations=violations,
                actions=actions,
                fallback_used=True,
            )
        # Grounding judged the prose acceptable (e.g. honest negation);
        # violations were conservative false positives.
        return TruthCheckResult(
            original_text=text,
            final_text=text,
            passed=True,
            violations=[],
            actions=["grounding_kept_prose"],
        )
    return TruthCheckResult(original_text=text, final_text=text, passed=True)
