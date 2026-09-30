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
# Stories (user-authored, never AI-invented) and voice preferences
# ---------------------------------------------------------------------------


class StoryRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    situation: str = Field(default="", max_length=4000)
    challenge: str = Field(default="", max_length=4000)
    action: str = Field(default="", max_length=4000)
    result: str = Field(default="", max_length=4000)
    reflection: str = Field(default="", max_length=4000)
    tags: list[str] = Field(default_factory=list)


@router.get("/stories")
def list_stories():
    return storage.list_all_stories()


@router.post("/stories")
def create_story(body: StoryRequest):
    import uuid

    story_id = f"story-{uuid.uuid4().hex[:12]}"
    storage.save_story(story_id, storage.active_candidate_id() or "local", body.model_dump(), body.tags)
    return {"id": story_id}


@router.put("/stories/{story_id}")
def update_story(story_id: str, body: StoryRequest):
    storage.save_story(story_id, storage.active_candidate_id() or "local", body.model_dump(), body.tags)
    return {"id": story_id}


@router.delete("/stories/{story_id}")
def delete_story(story_id: str):
    return {"id": story_id, "deleted": storage.delete_story(story_id)}


class VoicePreferences(BaseModel):
    conclusion_first: bool = True
    target_seconds: int = Field(default=60, ge=15, le=300)
    language: str = Field(default="zh-CN", max_length=20)
    term_style: str = Field(default="keep_english_terms", max_length=40)
    shape: str = Field(default="bullet", max_length=20)  # bullet / narrative
    banned_phrases: list[str] = Field(default_factory=list)


_VOICE_OWNER = "local"


@router.get("/voice-preferences")
def get_voice_preferences():
    row = storage.get_voice_profile(_VOICE_OWNER)
    prefs = (row or {}).get("profile", {}).get("explicit_preferences") if row else None
    return VoicePreferences(**(prefs or {})).model_dump()


@router.put("/voice-preferences")
def put_voice_preferences(body: VoicePreferences):
    storage.save_voice_profile(
        _VOICE_OWNER,
        json.dumps({"explicit_preferences": body.model_dump()}, ensure_ascii=False),
        sample_count=0,
        enabled=True,
    )
    return body.model_dump()


def voice_prompt_line(prefs: dict[str, Any]) -> str:
    """One style line for the answer prompt (enters the pack)."""
    if not prefs:
        return ""
    parts = []
    if prefs.get("conclusion_first", True):
        parts.append("先给结论")
    if prefs.get("target_seconds"):
        parts.append(f"口述约 {int(prefs['target_seconds'])} 秒")
    parts.append("要点式" if prefs.get("shape") == "bullet" else "叙述式")
    if prefs.get("term_style") == "keep_english_terms":
        parts.append("技术术语保留英文")
    banned = [str(p) for p in prefs.get("banned_phrases") or [] if str(p).strip()]
    if banned:
        parts.append("禁用：" + "、".join(banned[:8]))
    return "[我的表达] " + "；".join(parts)


@router.get("/skill-cards")
def list_skill_cards():
    from services.storage import prep_space

    out = []
    for lite in prep_space.list_spaces():
        space = prep_space.get_space(int(lite["id"])) or {}
        for card in space.get("skill_cards") or []:
            out.append({
                "id": card["id"],
                "space_id": space.get("id"),
                "space_title": space.get("title", ""),
                "project_name": card.get("project_name", ""),
                "status": card.get("status", ""),
                "user_reviewed": bool((card.get("card") or {}).get("user_reviewed")),
                "card": card.get("card") or {},
            })
    return out


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


@router.get("/review/{review_session_id}/r2")
def review_r2(review_session_id: int):
    """Review 2.0 for one review session: per-turn trace (raw / resolved
    question, Fast Cue, sources, context selection, latency, provider) and the
    session claims raised during it, joined on qa_id."""
    from services.storage import review as review_storage

    detail = review_storage.get_session_detail(review_session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="review session not found")
    qa_ids = [str(t.get("qa_id", "")) for t in detail.get("turns", []) if t.get("qa_id")]
    traces = storage.get_turn_traces(qa_ids)
    claims = storage.list_session_claims_by_qa(qa_ids)
    return {
        "review_session_id": review_session_id,
        "turns": [
            {
                "qa_id": t.get("qa_id"),
                "question": t.get("question_text", ""),
                "candidate_actual_speech": t.get("candidate_answer_text") or "",
                "trace": traces.get(str(t.get("qa_id", "")), {}),
            }
            for t in detail.get("turns", [])
        ],
        "session_claims": [
            {**row, "session_label": SESSION_LABELS.get(row["session_status"], ""), "provenance_label": PROVENANCE_LABELS.get(row["provenance_status"], "")}
            for row in claims
        ],
    }


# ---------------------------------------------------------------------------
# Latency + preflight
# ---------------------------------------------------------------------------


@router.get("/latency")
def latency_summary(limit: int = Query(default=200, ge=1, le=500)):
    return {"summary": latency_clock.summary(), "recent": latency_clock.recent(limit), "predictive": predictive.stats()}


def classify_provider_error(detail: str) -> dict[str, str]:
    """Turn a raw provider / STT error into a user-facing cause + next step
    (Stage AA: errors must never live only in a terminal)."""
    text = str(detail or "").lower()
    rules = [
        (("401", "unauthorized", "invalid api key", "incorrect api key", "authentication"), "auth", "API Key 无效或已过期", "在「设置 → 模型」里重新填写 API Key。"),
        (("403", "forbidden", "permission"), "forbidden", "账号无权访问该模型", "确认账号已开通该模型，或换一个模型名。"),
        (("404", "not found", "model_not_found", "does not exist"), "not_found", "模型名或接口地址不存在", "检查 Base URL 与模型名是否匹配服务商文档。"),
        (("429", "rate limit", "quota", "insufficient"), "quota", "额度不足或触发限流", "检查账户余额，或稍后重试。"),
        (("timeout", "timed out", "超时"), "timeout", "连接服务商超时", "检查网络 / 代理，或换一个更近的接口地址。"),
        (("connection", "resolve", "unreachable", "ssl", "proxy", "refused"), "network", "无法连接服务商", "检查网络、代理和 Base URL。"),
        (("download", "hugging", "hf_hub", "snapshot"), "stt_download", "本地识别模型下载失败", "检查网络后重试；也可以在「设置 → 语音」切换到云端识别。"),
        (("loading", "加载"), "loading", "模型正在加载", "首次加载本地识别模型需要一点时间，请稍候。"),
        (("no device", "invalid device", "device unavailable", "无可用设备"), "no_device", "没有可用的音频设备", "连接麦克风/耳机后点击重新检测。"),
        (("permission denied", "access denied", "拒绝"), "permission", "没有音频权限", "在系统设置里允许成竹使用麦克风后重试。"),
    ]
    for keys, kind, cause, action in rules:
        if any(k in text for k in keys):
            return {"kind": kind, "cause": cause, "action": action}
    return {"kind": "unknown", "cause": "未知错误", "action": "查看日志目录中的 app.log，或把错误信息反馈给我们。"}


@router.get("/diagnostics")
def diagnostics():
    """First-run / troubleshooting snapshot: where data lives, whether it is
    writable, models, STT and audio devices. No secrets are returned."""
    import tempfile

    from core.config import get_config
    from services.storage.paths import app_home, data_dir, is_packaged_home, logs_dir

    cfg = get_config()
    writable = True
    try:
        with tempfile.NamedTemporaryFile(dir=data_dir(), delete=True):
            pass
    except OSError:
        writable = False
    models = list(getattr(cfg, "models", []) or [])
    configured = [
        {"index": i, "name": str(getattr(m, "name", "")), "model": str(getattr(m, "model", "")), "has_key": bool(str(getattr(m, "api_key", "") or "").strip()) and not str(getattr(m, "api_key", "")).startswith("YOUR_"), "enabled": bool(getattr(m, "enabled", True))}
        for i, m in enumerate(models)
    ]
    audio: dict[str, Any] = {"devices": [], "error": ""}
    try:
        from services.audio import AudioCapture

        devices = AudioCapture.list_devices()
        audio["devices"] = [
            {"id": d.get("id"), "name": d.get("name"), "is_loopback": bool(d.get("is_loopback") or d.get("loopback"))}
            for d in devices
        ]
        audio["platform"] = AudioCapture.get_platform_info(devices=devices)
    except Exception as exc:  # noqa: BLE001
        audio["error"] = str(exc)
        audio["explain"] = classify_provider_error(str(exc))
    inputs = [d for d in audio["devices"] if not d["is_loopback"]]
    loopbacks = [d for d in audio["devices"] if d["is_loopback"]]
    return {
        "packaged": is_packaged_home(),
        "data_home": app_home(),
        "data_dir": data_dir(),
        "logs_dir": logs_dir(),
        "data_writable": writable,
        "models": configured,
        "has_usable_model": any(m["has_key"] and m["enabled"] for m in configured),
        "stt_provider": str(getattr(cfg, "stt_provider", "") or ""),
        "audio": audio,
        "has_microphone": bool(inputs),
        "has_system_audio": bool(loopbacks),
        "onboarding_completed": bool(getattr(cfg, "onboarding_completed", False)),
    }


class ExplainErrorRequest(BaseModel):
    detail: str = Field(default="", max_length=4000)


@router.post("/diagnostics/explain")
def explain_error(body: ExplainErrorRequest):
    return classify_provider_error(body.detail)


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
