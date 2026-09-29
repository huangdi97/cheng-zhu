"""R2 Intelligence API: InterviewPack, Facts & Sources, Session Claims,
latency, preflight.

Mounted under /api/intelligence next to the v1 router. Deterministic and
storage-backed; no LLM calls.

 PRIVACY:
  - Pack payloads never contain provider keys (interview_pack builds only
    model names). The full pack view is local-only like every other route.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.intelligence import interview_pack, latency_clock, predictive, session_claims
from services.intelligence.semantics import (
    PROVENANCE_LABELS,
    SESSION_LABELS,
    USER_ASSERTION_LABELS,
    ProvenanceStatus,
    UserAssertionStatus,
)
from services.storage import intelligence as storage

router = APIRouter(tags=["intelligence-r2"])


def _current_session_id(session_id: Optional[str]) -> str:
    if session_id:
        return session_id
    from core.session import session_id as _sid

    return str(_sid() or "default")


# ---------------------------------------------------------------------------
# Facts & sources (three independent axes)
# ---------------------------------------------------------------------------


def _fact_row(row: dict[str, Any]) -> dict[str, Any]:
    prov = str(row.get("provenance_status") or "NO_EVIDENCE")
    user = str(row.get("user_assertion_status") or "UNREVIEWED")
    try:
        structured = json.loads(row.get("structured_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        structured = {}
    return {
        "id": row["id"],
        "text": row["text"],
        "type": row.get("type", "fact"),
        "source": row.get("source", ""),
        "provenance_status": prov,
        "provenance_label": PROVENANCE_LABELS.get(prov, prov),
        "user_assertion_status": user,
        "user_assertion_label": USER_ASSERTION_LABELS.get(user, user),
        "structured": structured,
        "source_ids": storage.claim_evidence_ids(row["id"]),
        "updated_at": row.get("updated_at"),
    }


@router.get("/facts")
def list_facts(limit: int = Query(default=500, ge=1, le=2000)):
    """"事实与来源": provenance and user confirmation shown side by side,
    never merged into a single "verified" verdict."""
    candidate_id = storage.active_candidate_id()
    if not candidate_id:
        return {"candidate_id": "", "facts": [], "evidence": []}
    return {
        "candidate_id": candidate_id,
        "facts": [_fact_row(row) for row in storage.list_claims(candidate_id, limit=limit)],
        "evidence": [
            {"id": row["id"], "source": row.get("source", ""), "text": row["text"][:400]}
            for row in storage.list_evidence(candidate_id, limit=limit)
        ],
    }


class FactAxesRequest(BaseModel):
    user_assertion_status: Optional[str] = None
    provenance_status: Optional[str] = None
    text: Optional[str] = Field(default=None, max_length=2000)
    structured: Optional[dict[str, Any]] = None
    source_ids: Optional[list[str]] = None


@router.patch("/facts/{claim_id}")
def update_fact(claim_id: str, body: FactAxesRequest):
    """User confirm / deny / edit / add source. Confirming never changes
    provenance; adding a source is the only way provenance improves."""
    if body.user_assertion_status is not None:
        try:
            UserAssertionStatus(body.user_assertion_status)
        except ValueError:
            raise HTTPException(status_code=422, detail="user_assertion_status 无效") from None
    provenance = body.provenance_status
    if provenance is not None:
        try:
            ProvenanceStatus(provenance)
        except ValueError:
            raise HTTPException(status_code=422, detail="provenance_status 无效") from None
    if body.source_ids is not None and provenance is None:
        provenance = ProvenanceStatus.SUPPORTING_EVIDENCE.value if body.source_ids else None
    if body.text is not None:
        rows = [r for r in storage.list_claims(storage.active_candidate_id()) if r["id"] == claim_id]
        if not rows:
            raise HTTPException(status_code=404, detail="claim not found")
        row = rows[0]
        storage.save_claims(
            row["candidate_id"],
            [{"id": claim_id, "type": row.get("type", "fact"), "text": body.text, "source": row.get("source", ""),
              "truth_status": row.get("truth_status", "UNKNOWN"), "confidence": row.get("confidence", 0.5)}],
        )
    updated = storage.update_claim_axes(
        claim_id,
        provenance_status=provenance,
        user_assertion_status=body.user_assertion_status,
        structured=body.structured,
        source_ids=body.source_ids,
    )
    if body.source_ids:
        now_links = [(claim_id, sid) for sid in body.source_ids]
        storage.save_evidence_batch(storage.active_candidate_id(), [], now_links)
    if not updated:
        raise HTTPException(status_code=404, detail="claim not found")
    return {"id": claim_id, "updated": True}


@router.delete("/facts/{claim_id}")
def delete_fact(claim_id: str):
    return {"id": claim_id, "deleted": storage.delete_claim(claim_id)}


@router.get("/facts/{claim_id}/sessions")
def fact_usage(claim_id: str):
    """Which frozen packs (sessions) carried this fact."""
    rows = storage._read(  # noqa: SLF001 - read-only helper reuse
        "SELECT id, session_id, revision, created_at FROM interview_pack WHERE pack_json LIKE ? ORDER BY created_at DESC LIMIT 50",
        (f'%"id": "{claim_id}"%',),
    )
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# InterviewPack
# ---------------------------------------------------------------------------


class FreezePackRequest(BaseModel):
    session_id: Optional[str] = None
    job_id: str = ""
    prep_space_id: Optional[int] = None
    selected_kb_paths: Optional[list[str]] = None
    ai_policy: str = ""
    human_assistance_policy: str = ""
    share_privacy_policy: str = ""
    screen_context_policy: str = ""
    answer_preferences: dict[str, Any] = Field(default_factory=dict)


@router.post("/pack/freeze")
def freeze_pack(body: FreezePackRequest):
    from core.config import get_config

    session_id = _current_session_id(body.session_id)
    cfg = get_config()
    prefs = dict(body.answer_preferences or {})
    prefs.setdefault("notes", str(getattr(cfg, "interview_notes", "") or ""))
    payload = interview_pack.build_pack_payload(
        session_id=session_id,
        cfg=cfg,
        job_id=body.job_id,
        prep_space_id=body.prep_space_id,
        selected_kb_paths=body.selected_kb_paths,
        human_assistance_policy=body.human_assistance_policy,
        share_privacy_policy=body.share_privacy_policy,
        screen_context_policy=body.screen_context_policy,
        ai_policy=body.ai_policy,
        answer_preferences=prefs,
    )
    if body.job_id and not payload.get("job"):
        raise HTTPException(status_code=404, detail="job not found")
    pack = interview_pack.freeze_pack(payload)
    return pack.summary()


@router.get("/pack")
def get_pack(session_id: Optional[str] = None):
    sid = _current_session_id(session_id)
    pack = interview_pack.load_frozen_pack(sid)
    return {
        "session_id": sid,
        "frozen": pack is not None,
        "pack": pack.summary() if pack else None,
        "revisions": storage.list_interview_pack_revisions(sid),
    }


@router.get("/pack/{pack_id}")
def get_pack_detail(pack_id: str):
    row = storage.get_interview_pack(pack_id)
    if row is None:
        raise HTTPException(status_code=404, detail="pack not found")
    return {k: v for k, v in row.items()}


class RevisePackRequest(BaseModel):
    job_id: Optional[str] = None
    refresh_candidate: bool = False
    reason: str = "user_update"


@router.post("/pack/{pack_id}/revise")
def revise_pack(pack_id: str, body: RevisePackRequest):
    """"更新本场资料": a new revision; the original pack row is untouched."""
    base = storage.get_interview_pack(pack_id)
    if base is None:
        raise HTTPException(status_code=404, detail="pack not found")
    changes: dict[str, Any] = {}
    if body.job_id is not None:
        job = storage.get_job_profile(body.job_id) if body.job_id else {}
        if body.job_id and not job:
            raise HTTPException(status_code=404, detail="job not found")
        changes.update({"job": job or {}, "job_alignment": (job or {}).get("alignment") or {}, "company_context": {"company": (job or {}).get("company", "")}})
    if body.refresh_candidate:
        fresh = interview_pack.build_pack_payload(session_id=base["session_id"], job_id=str((base["pack"].get("job") or {}).get("id", "")))
        for key in ("candidate_context", "claims", "evidence_refs", "stories", "voice_profile", "controlled_memory"):
            changes[key] = fresh.get(key)
    pack = interview_pack.revise_pack(pack_id, changes, reason=body.reason)
    return pack.summary()


# ---------------------------------------------------------------------------
# Session claims
# ---------------------------------------------------------------------------


@router.get("/session-claims")
def list_session_claims(session_id: Optional[str] = None):
    sid = _current_session_id(session_id)
    return [
        {**item, "session_label": SESSION_LABELS.get(item["session_status"], ""), "provenance_label": PROVENANCE_LABELS.get(item["provenance_status"], "")}
        for item in session_claims.review_items(sid)
    ]


class ResolveRequest(BaseModel):
    action: str


@router.post("/session-claims/{claim_id}/resolve")
def resolve_session_claim(claim_id: str, body: ResolveRequest):
    row = session_claims.resolve(claim_id, body.action)
    if row is None:
        raise HTTPException(status_code=404, detail="session claim or action not found")
    return row


class ReviewDecisionRequest(BaseModel):
    decision: str


@router.post("/session-claims/{claim_id}/review")
def review_session_claim(claim_id: str, body: ReviewDecisionRequest):
    """Review is the only place a session statement can become long-term."""
    candidate_id = storage.active_candidate_id() or "local"
    result = session_claims.confirm_in_review(claim_id, candidate_id=candidate_id, decision=body.decision)
    if result is None:
        raise HTTPException(status_code=404, detail="session claim or decision not found")
    return result


# ---------------------------------------------------------------------------
# Latency + preflight
# ---------------------------------------------------------------------------


@router.get("/latency")
def latency_summary(limit: int = Query(default=200, ge=1, le=500)):
    return {"summary": latency_clock.summary(), "recent": latency_clock.recent(limit), "predictive": predictive.stats()}


@router.get("/preflight")
def preflight(session_id: Optional[str] = None):
    """Preflight R2 checklist. A formal session requires a frozen pack."""
    from core.config import get_config
    from services.intelligence.policy import human_coach_allowed, resolve_policy_mode

    cfg = get_config()
    sid = _current_session_id(session_id)
    pack = interview_pack.load_frozen_pack(sid)
    ai_policy = pack.ai_policy if pack else str(getattr(cfg, "ai_policy_mode", "AI_ALLOWED"))
    human_policy = pack.human_assistance_policy if pack else str(getattr(cfg, "human_assistance_policy", "HUMAN_PRACTICE_ONLY"))
    share = pack.share_privacy_policy if pack else str(getattr(cfg, "share_privacy_mode", "OFF"))
    models = list(getattr(cfg, "models", []) or [])
    active = models[int(getattr(cfg, "active_model", 0) or 0)] if models else None
    items = [
        {"key": "job", "ok": bool(pack and pack.job_id), "detail": (pack.job.get("title", "") if pack else "") or "未选择岗位"},
        {"key": "interview_pack", "ok": pack is not None, "detail": f"rev {pack.revision} · {pack.content_hash}" if pack else "未冻结：正式上场前必须冻结"},
        {"key": "llm", "ok": bool(active and getattr(active, "api_key", "")), "detail": str(getattr(active, "name", "") or "") if active else "未配置"},
        {"key": "stt", "ok": bool(getattr(cfg, "stt_provider", "")), "detail": str(getattr(cfg, "stt_provider", ""))},
        {"key": "ai_policy", "ok": True, "detail": resolve_policy_mode(ai_policy).value},
        {
            "key": "human_assistance_policy",
            "ok": True,
            "detail": human_policy,
            "live_coach_enabled": human_coach_allowed(human_policy, session_kind="live"),
            "reason": "" if human_coach_allowed(human_policy, session_kind="live") else "当前策略不允许在正式场次使用人工协助（仅练习可用）",
        },
        {"key": "share_privacy", "ok": True, "detail": share, "note": "减少私人资料出现在受支持的共享/录制路径中；不是安全或“不可检测”保证。"},
        {"key": "screen_context", "ok": True, "detail": (pack.payload.get("screen_context_policy") if pack else "ON_REQUEST")},
        {"key": "model_profile", "ok": True, "detail": (pack.payload.get("model_profile") if pack else {})},
        {"key": "storage", "ok": True, "detail": storage.DB_PATH},
    ]
    return {"session_id": sid, "can_start_formal_session": pack is not None, "items": items}
