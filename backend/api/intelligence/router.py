"""Intelligence REST API: deterministic, storage-backed read/write surface.

 COMPATIBILITY:
  - Registered in main.py with prefix="/api/intelligence"; the router itself
    carries only tags so the public contract paths stay stable.
  - No LLM calls live here: every endpoint is deterministic or storage-backed,
    so the surface stays latency-free and offline-safe.
 PRIVACY:
  - /candidate returns a short profile preview; the full stored resume text
    never leaves the backend through this API.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.intelligence.candidate_representation import rebuild_and_persist
from services.intelligence.evidence_graph import claim_status_summary
from services.intelligence.interview_state import (
    compact_state_context,
    get_state,
    reset_state,
    restore_from_snapshot,
)
from services.intelligence.job_representation import (
    build_job_representation,
    compute_alignment,
    save_job,
)
from services.intelligence.types import TruthStatus
from services.storage import intelligence as intelligence_storage

router = APIRouter(tags=["intelligence"])

# PRIVACY: the persisted profile_text (storage keeps a 4000-char truncation)
# must never leave the backend in full; the API returns a 400-char preview.
_PROFILE_TEXT_PREVIEW_LIMIT = 400
_DEFAULT_LIST_LIMIT = 500
_MAX_LIST_LIMIT = 2000
# Post-rebuild evidence counting must stay exact; the cap only bounds the
# internal SELECT, the rows themselves are never returned.
_COUNT_LIMIT = 10000


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class RebuildCandidateRequest(BaseModel):
    resume_text: str = Field(max_length=200000)
    interview_notes: str = Field(default="", max_length=200000)
    resume_history_id: int | None = None


class UpdateClaimRequest(BaseModel):
    truth_status: str
    confidence: float | None = None


class RebuildJobRequest(BaseModel):
    jd_text: str = Field(max_length=200000)
    company: str = Field(default="", max_length=200)
    title: str = Field(default="", max_length=200)
    role: str = Field(default="", max_length=200)
    resume_text: str = Field(default="", max_length=200000)


class SessionRequest(BaseModel):
    session_id: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------


def _with_parsed_metadata(row: dict[str, Any]) -> dict[str, Any]:
    """Replace the raw metadata_json TEXT column with a parsed dict so API
    consumers never see storage-internal JSON strings."""
    payload = {key: value for key, value in row.items() if key != "metadata_json"}
    try:
        payload["metadata"] = json.loads(row.get("metadata_json") or "{}")
    except json.JSONDecodeError:
        payload["metadata"] = {}
    return payload


def _active_claim_texts() -> tuple[list[str], list[str]]:
    """Active candidate's claim texts + ids, used as alignment evidence links."""
    candidate_id = intelligence_storage.active_candidate_id()
    if not candidate_id:
        return [], []
    rows = intelligence_storage.list_claims(candidate_id)
    return (
        [str(row.get("text", "")) for row in rows],
        [str(row.get("id", "")) for row in rows],
    )


def _alignment_resume_text(resume_text: str) -> str:
    """compute_alignment matches requirement terms against resume text; when
    the caller omits it, fall back to the stored active profile so alignment
    still reflects the candidate instead of reporting only gaps."""
    if (resume_text or "").strip():
        return resume_text
    candidate_id = intelligence_storage.active_candidate_id()
    if not candidate_id:
        return ""
    profile = intelligence_storage.get_candidate_profile(candidate_id) or {}
    return str(profile.get("profile_text") or "")


# ---------------------------------------------------------------------------
# Candidate representation
# ---------------------------------------------------------------------------


@router.get("/candidate")
def get_active_candidate():
    """Active candidate representation: profile preview + claims + evidence."""
    candidate_id = intelligence_storage.active_candidate_id()
    if not candidate_id:
        return {"candidate_id": "", "exists": False}
    profile = intelligence_storage.get_candidate_profile(candidate_id) or {}
    # PRIVACY: preview only — the full resume text stays behind the backend.
    profile["profile_text"] = str(profile.get("profile_text") or "")[:_PROFILE_TEXT_PREVIEW_LIMIT]
    claims = intelligence_storage.list_claims(candidate_id)
    return {
        "candidate_id": candidate_id,
        "exists": True,
        "profile": profile,
        "claims": [_with_parsed_metadata(row) for row in claims],
        "evidence": [
            _with_parsed_metadata(row)
            for row in intelligence_storage.list_evidence(candidate_id)
        ],
        "claim_summary": claim_status_summary(claims),
    }


@router.post("/candidate/rebuild")
def rebuild_candidate(body: RebuildCandidateRequest):
    """Deterministic resume+notes rebuild; persists and becomes the active one."""
    rep = rebuild_and_persist(
        body.resume_text, body.interview_notes, resume_history_id=body.resume_history_id
    )
    # The rebuild generates a fresh candidate_id, so evidence rows stored under
    # it are exactly this batch; count them for the summary.
    evidence_count = len(
        intelligence_storage.list_evidence(rep.candidate_id, limit=_COUNT_LIMIT)
    )
    return {
        "candidate_id": rep.candidate_id,
        "claims": len(rep.claims),
        "evidence": evidence_count,
        "representation_summary": claim_status_summary(
            [claim.payload() for claim in rep.claims]
        ),
    }


# ---------------------------------------------------------------------------
# Claims / evidence
# ---------------------------------------------------------------------------


@router.get("/claims")
def list_active_claims(
    limit: int = Query(default=_DEFAULT_LIST_LIMIT, ge=1, le=_MAX_LIST_LIMIT),
):
    """Claims of the active candidate, strongest first."""
    candidate_id = intelligence_storage.active_candidate_id()
    if not candidate_id:
        return []
    rows = intelligence_storage.list_claims(candidate_id, limit=limit)
    return [_with_parsed_metadata(row) for row in rows]


@router.patch("/claims/{claim_id}")
def update_claim(claim_id: str, body: UpdateClaimRequest):
    """Manual truth-status correction: the user verdict overrides the model."""
    try:
        status = TruthStatus(body.truth_status)
    except ValueError:
        allowed = "/".join(item.value for item in TruthStatus)
        raise HTTPException(
            status_code=422, detail=f"truth_status 必须是 {allowed} 之一"
        ) from None
    updated = intelligence_storage.update_claim_status(claim_id, status.value, body.confidence)
    return {"id": claim_id, "truth_status": status.value, "updated": updated}


@router.get("/evidence")
def list_active_evidence(
    limit: int = Query(default=_DEFAULT_LIST_LIMIT, ge=1, le=_MAX_LIST_LIMIT),
):
    """Evidence rows of the active candidate, newest first."""
    candidate_id = intelligence_storage.active_candidate_id()
    if not candidate_id:
        return []
    return [
        _with_parsed_metadata(row)
        for row in intelligence_storage.list_evidence(candidate_id, limit=limit)
    ]


# ---------------------------------------------------------------------------
# Job representation
# ---------------------------------------------------------------------------


@router.get("/job")
def get_latest_job():
    """Latest saved job profile with parsed JSON fields and alignment."""
    job_id = intelligence_storage.latest_job_id()
    if not job_id:
        return {"exists": False}
    profile = intelligence_storage.get_job_profile(job_id)
    if profile is None:
        return {"exists": False}
    return {"exists": True, **profile}


@router.post("/job/rebuild")
def rebuild_job(body: RebuildJobRequest):
    """Structure a JD, compute explainable alignment, persist, and return it."""
    job = build_job_representation(
        body.jd_text, company=body.company, title=body.title, role=body.role
    )
    claim_texts, claim_ids = _active_claim_texts()
    alignment = compute_alignment(
        job,
        _alignment_resume_text(body.resume_text),
        claim_texts=claim_texts,
        claim_ids=claim_ids,
    )
    final_id = save_job(job, alignment=alignment)
    # save_job stored the alignment into the payload; expose it verbatim.
    payload = job.payload()
    payload["job_id"] = final_id
    return payload


# ---------------------------------------------------------------------------
# Interview state
# ---------------------------------------------------------------------------


@router.get("/state")
def get_interview_state(
    session_id: str = Query(min_length=1, description="Interview session id"),
):
    """Current interview state plus a compact prompt-ready context block."""
    state = get_state(session_id)
    return {**state.payload(), "compact_context": compact_state_context(state)}


@router.post("/state/reset")
def reset_interview_state(body: SessionRequest):
    """Explicit session reset; returns the fresh state payload."""
    return reset_state(body.session_id).payload()


@router.post("/state/restore")
def restore_interview_state(body: SessionRequest):
    """Crash recovery: rebuild the in-memory state from the latest snapshot."""
    return restore_from_snapshot(body.session_id).payload()
