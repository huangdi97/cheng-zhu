"""Evidence Graph: claim-evidence relations over the Intelligence storage.

The graph is the constraint side of the core (master doc section 4): every
personal-fact claim stays linked to its provenance so the Truth Boundary and
the planner can distinguish verified experience from model inference.
"""
from __future__ import annotations

from typing import Any

from services.intelligence.types import TruthStatus


def claim_evidence_map(claims: list[dict[str, Any]]) -> dict[str, list[str]]:
    """claim_id -> [evidence_id] using the metadata carried by the builder."""
    mapping: dict[str, list[str]] = {}
    for claim in claims:
        evidence_id = str(claim.get("metadata", {}).get("evidence_id", "") or "")
        if evidence_id:
            mapping.setdefault(str(claim["id"]), []).append(evidence_id)
    return mapping


def claims_for_subject(claims: list[dict[str, Any]], subject_terms: list[str]) -> list[dict[str, Any]]:
    """Claims whose text covers every qualifier of the asked subject.

    Mirrors answer_grounding's composite-subject rule: matching just "Redis"
    would silently turn a narrower question ("Redis Cluster") into a broader
    claim.
    """
    matched: list[dict[str, Any]] = []
    for claim in claims:
        lowered = str(claim.get("text", "")).lower()
        if lowered and all(term.lower() in lowered for term in subject_terms):
            matched.append(claim)
    return matched


def strongest_claim(claims: list[dict[str, Any]], subject_terms: list[str]) -> dict[str, Any] | None:
    """Highest-confidence claim covering the subject, CONTRADICTED excluded."""
    matched = [c for c in claims_for_subject(claims, subject_terms) if str(c.get("truth_status", "")) != "CONTRADICTED"]
    if not matched:
        return None
    return max(matched, key=lambda claim: float(claim.get("confidence", 0.0)))


def contradicted_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in claims if str(c.get("truth_status", "")) == "CONTRADICTED"]


def evidence_strength_for_claims(claims: list[dict[str, Any]]) -> float:
    """Aggregate evidence strength for a set of claims (bounded [0,1])."""
    if not claims:
        return 0.0
    weights = {"VERIFIED": 1.0, "SUPPORTED": 0.9, "INFERRED": 0.5, "UNKNOWN": 0.2, "CONTRADICTED": 0.0}
    total = sum(weights.get(str(claim.get("truth_status", "")), 0.2) * float(claim.get("confidence", 0.5)) for claim in claims)
    return max(0.0, min(1.0, total / len(claims)))


def claim_status_summary(claims: list[dict[str, Any]]) -> dict[str, int]:
    """Per-status counts for observability and prepare/review surfaces."""
    summary = {status.value: 0 for status in TruthStatus}
    for claim in claims:
        status = str(claim.get("truth_status", "")).upper()
        if status in summary:
            summary[status] += 1
    return summary
