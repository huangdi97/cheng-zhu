"""v2.0 Personal Conversation Intelligence product service.

This is the first real runtime path for Conversation Profile.  It is additive
to the v1 Interview product: no Interview table is renamed or rewritten.

Truth rules:
- AI extraction is a candidate, never agreement.
- Decision AGREED requires source + explicit review.
- Commitment/Task COMMITTED requires owner + source + explicit review.
- proactive guidance is allowed to return SILENT/suppressed.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Optional

from services.product import conversation_connectors, conversation_integrations, conversation_screen, materials
from services.product.future_profile import (
    AssistanceMode,
    ConversationItemState,
    ConversationItemType,
    ExpressionAction,
    GuidanceKind,
    OpportunityScore,
)
from services.storage import intelligence as intelligence_store
from services.storage import product as store


SPACE_PROFILES = {
    "PROJECT_SYNC": {
        "label": "项目同步",
        "default_mode": "BALANCED",
        "guidance": ["RECALL", "QUESTION", "RISK", "CONTRIBUTION_OPPORTUNITY"],
        "playbook": {
            "success_conditions": [
                "明确本期状态变化与关键阻塞",
                "确认需要继续推进的 owner / commitment / deadline",
                "把未解决问题带入下一次同步",
            ],
            "priority_truth_types": ["Status", "Commitment", "Task", "Risk", "OpenQuestion", "Deadline", "Decision"],
            "prepare_prompts": ["哪里发生了变化？", "当前最大的 blocker 是什么？", "谁需要在何时完成下一步？"],
            "closing_objective": "形成可追溯的状态变化、owner 明确的下一步与未解决事项。",
            "boundaries": ["不把无来源的进度判断写成事实", "不把模糊时间直接升级成 reviewed Deadline"],
        },
    },
    "DESIGN_REVIEW": {
        "label": "设计评审",
        "default_mode": "BALANCED",
        "guidance": ["RECALL", "TALKING_POINT", "QUESTION", "RISK", "CONTRIBUTION_OPPORTUNITY"],
        "playbook": {
            "success_conditions": [
                "把设计选择与证据/约束放在同一上下文",
                "显式保留 objection / risk / unresolved trade-off",
                "若形成决策，保留 supersession 与后续验证项",
            ],
            "priority_truth_types": ["Decision", "Proposal", "Objection", "Risk", "Assumption", "OpenQuestion", "Metric"],
            "prepare_prompts": ["本次要决定什么？", "关键 trade-off / objection 是什么？", "哪条证据最能改变决策？"],
            "closing_objective": "得到有 provenance 的 Decision，或明确留下仍未解决的 trade-off / objection。",
            "boundaries": ["不把 Proposal 当 Decision", "不把模型推断的 trade-off 当成参与者明确立场"],
        },
    },
    "PRESENTATION_QA": {
        "label": "演示 / Q&A",
        "default_mode": "PRESENTATION",
        "guidance": ["ANSWER_CUE", "RECALL", "QUESTION", "DELIVERY"],
        "playbook": {
            "success_conditions": [
                "保持核心主张与最强证据一致",
                "回答问题时区分已知、未知与待补证据",
                "把 follow-up 问题和承诺带到会后",
            ],
            "priority_truth_types": ["Metric", "Status", "Decision", "OpenQuestion", "Commitment"],
            "prepare_prompts": ["最可能被追问的证据是什么？", "哪些数字/版本必须准确？", "答不上来时下一步承诺是什么？"],
            "closing_objective": "清楚回答已知问题，并把未知项与 follow-up 明确留下。",
            "boundaries": ["不为了完整回答而补造数字", "Quick Note / transcript 不自动升级成 confirmed fact"],
        },
    },
    "ONE_ON_ONE": {
        "label": "1:1",
        "default_mode": "ONE_ON_ONE",
        "guidance": ["RECALL", "QUESTION", "TALKING_POINT"],
        "playbook": {
            "success_conditions": [
                "明确双方已表达的目标、阻塞与期望",
                "把承诺与 follow-up 归属到明确 owner",
                "保留未知，不推断情绪、人格或隐藏意图",
            ],
            "priority_truth_types": ["Commitment", "OpenQuestion", "Status", "Risk", "Decision"],
            "prepare_prompts": ["上次未解决的 thread 是什么？", "对方明确表达过哪些 concern？", "本次需要确认的下一步是什么？"],
            "closing_objective": "形成双方都能回看的明确下一步，同时保留未解决问题。",
            "boundaries": ["不保存心理画像", "不把语气/情绪推断写成长久 Counterparty truth"],
        },
    },
    "CLIENT_CALL": {
        "label": "客户会",
        "default_mode": "BALANCED",
        "guidance": ["RECALL", "ANSWER_CUE", "QUESTION", "RISK", "CONTRIBUTION_OPPORTUNITY"],
        "playbook": {
            "success_conditions": [
                "准确回应客户明确提出的问题与 concern",
                "区分需求、承诺、风险与尚未确认事项",
                "所有 follow-up 都保留 owner / source / review 边界",
            ],
            "priority_truth_types": ["OpenQuestion", "Commitment", "Risk", "Decision", "Status", "Metric"],
            "prepare_prompts": ["客户明确关心什么？", "哪些承诺必须避免过度承诺？", "哪些问题需要会后补证据？"],
            "closing_objective": "留下来源清楚的客户问题、承诺与 follow-up，而不是一份模糊纪要。",
            "boundaries": ["不自动把客户话语解释成购买意向", "不自动执行 CRM / 邮件 / task 写回"],
        },
    },
    "NEGOTIATION": {
        "label": "谈判",
        "default_mode": "QUIET",
        "guidance": ["RECALL", "TALKING_POINT", "QUESTION", "RISK"],
        "playbook": {
            "success_conditions": [
                "只使用明确立场、约束、提议和来源清楚的事实",
                "区分 Proposal、Objection、Decision 与 Commitment",
                "在高 social-risk 时宁可 SILENT",
            ],
            "priority_truth_types": ["Proposal", "Objection", "Decision", "Commitment", "Risk", "OpenQuestion"],
            "prepare_prompts": ["双方明确提出了什么？", "哪些约束是已知事实？", "哪些条款仍未达成一致？"],
            "closing_objective": "精确记录已表达立场与达成/未达成事项，不推断隐藏底线。",
            "boundaries": ["不推断 hidden intent / bottom line", "不因谈判语气推断人格、压力或让步意愿"],
        },
    },
}

ASSISTANCE_MODES = {m.value for m in AssistanceMode}
CAPTURE_MODES = {"TRANSCRIPT", "NOTES_ONLY", "NO_CAPTURE"}
PROCESSING_MODES = {"LOCAL", "CLOUD", "OFF"}
RETENTION_PRESETS: dict[str, dict[str, Any]] = {
    "MINIMUM": {
        "preset": "MINIMUM",
        "transcript_days": 0,
        "guidance_days": 7,
        "draft_days": 7,
        "confirmed_items": "KEEP",
        "audio_retention": "OFF",
    },
    "STANDARD": {
        "preset": "STANDARD",
        "transcript_days": 30,
        "guidance_days": 30,
        "draft_days": 30,
        "confirmed_items": "KEEP",
        "audio_retention": "OFF",
    },
}

AI_ASSISTANCE_POLICIES = {"AI_FORBIDDEN", "AI_LIMITED", "AI_ALLOWED", "AI_EXPECTED"}
HUMAN_ASSISTANCE_POLICIES = {"HUMAN_FORBIDDEN", "HUMAN_PRACTICE_ONLY", "HUMAN_ALLOWED"}
SCREEN_CONTEXT_POLICIES = {"OFF", "MANUAL", "AUTO"}
SHARE_PRIVACY_POLICIES = {"OFF", "PRIVATE_OVERLAY"}
EXTERNAL_WRITEBACK_POLICIES = {"OFF", "REVIEW_REQUIRED"}
PARTICIPANT_CONSENT_STATUSES = {"NOT_RECORDED", "USER_REPORTS_ALLOWED", "USER_REPORTS_CONSENTED", "NOT_APPLICABLE"}
PARTICIPANT_TRANSPARENCY_PLANS = {
    "NOT_RECORDED",
    "USER_WILL_NOTIFY_VERBALLY",
    "USER_WILL_NOTIFY_IN_CHAT",
    "USER_REPORTS_ALREADY_NOTIFIED",
    "NOT_APPLICABLE",
}
DEFAULT_SESSION_POLICY: dict[str, Any] = {
    "transcript_retention": "SPACE_POLICY",
    "screen_context": "OFF",
    "ai_assistance": "AI_ALLOWED",
    "human_assistance": "HUMAN_PRACTICE_ONLY",
    "share_privacy": "OFF",
    "external_writeback": "REVIEW_REQUIRED",
    "participant_consent_status": "NOT_RECORDED",
    "participant_transparency_plan": "NOT_RECORDED",
    "connector_permissions": [],
    "speaker_biometric_identity": "OFF",
    "emotion_sentiment_profiling": "OFF",
    "hidden_intent_claims": "OFF",
}

TIME_AMBIGUITY_STATES = {"EXACT", "AMBIGUOUS", "UNSPECIFIED_TIMEZONE", "NOT_PARSED", "NOT_APPLICABLE"}


def _normalize_time_semantics(
    raw: Optional[dict[str, Any]],
    *,
    original_text: str = "",
    normalized_datetime: str = "",
    timezone: str = "",
    ambiguity: str = "",
) -> dict[str, str]:
    source = dict(raw or {})
    original = str(source.get("original_text") or original_text or "")[:1200]
    normalized = str(source.get("normalized_datetime") or normalized_datetime or "")[:160]
    zone = str(source.get("timezone") or timezone or "")[:120]
    state = str(source.get("ambiguity") or ambiguity or "").upper().strip()
    if not state:
        if not original and not normalized:
            state = "NOT_APPLICABLE"
        elif normalized and zone:
            state = "EXACT"
        elif normalized:
            state = "UNSPECIFIED_TIMEZONE"
        else:
            state = "AMBIGUOUS"
    if state not in TIME_AMBIGUITY_STATES:
        raise ValueError("时间歧义状态不支持")
    return {
        "original_text": original,
        "normalized_datetime": normalized,
        "timezone": zone,
        "ambiguity": state,
    }


def _time_semantics_resolved(value: Optional[dict[str, Any]]) -> bool:
    ts = _normalize_time_semantics(value)
    return bool(
        ts["ambiguity"] == "EXACT"
        and ts["normalized_datetime"]
        and ts["timezone"]
    )




def _normalize_session_policy(raw: Optional[dict[str, Any]], base: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    source = {**DEFAULT_SESSION_POLICY, **dict(base or {}), **dict(raw or {})}
    source["screen_context"] = _require_choice(str(source.get("screen_context") or "OFF"), SCREEN_CONTEXT_POLICIES, "屏幕上下文")
    source["ai_assistance"] = _require_choice(str(source.get("ai_assistance") or "AI_ALLOWED"), AI_ASSISTANCE_POLICIES, "AI Assistance")
    source["human_assistance"] = _require_choice(str(source.get("human_assistance") or "HUMAN_PRACTICE_ONLY"), HUMAN_ASSISTANCE_POLICIES, "Human Assistance")
    source["share_privacy"] = _require_choice(str(source.get("share_privacy") or "OFF"), SHARE_PRIVACY_POLICIES, "Share Privacy")
    source["external_writeback"] = _require_choice(str(source.get("external_writeback") or "REVIEW_REQUIRED"), EXTERNAL_WRITEBACK_POLICIES, "外部写回")
    source["participant_consent_status"] = _require_choice(
        str(source.get("participant_consent_status") or "NOT_RECORDED"),
        PARTICIPANT_CONSENT_STATUSES,
        "参与者同意状态",
    )
    source["participant_transparency_plan"] = _require_choice(
        str(source.get("participant_transparency_plan") or "NOT_RECORDED"),
        PARTICIPANT_TRANSPARENCY_PLANS,
        "参与者透明告知计划",
    )
    source["transcript_retention"] = str(source.get("transcript_retention") or "SPACE_POLICY")[:80]
    source["connector_permissions"] = [str(x)[:160] for x in (source.get("connector_permissions") or [])][:50]
    # These three policy guarantees are deliberately not user-relaxable in v2.
    source["speaker_biometric_identity"] = "OFF"
    source["emotion_sentiment_profiling"] = "OFF"
    source["hidden_intent_claims"] = "OFF"
    return source


SHARE_PRIVACY_RUNTIME_PROOF = "ELECTRON_CONTENT_PROTECTION_ACTIVE"


def share_privacy_runtime_status(
    session: dict[str, Any],
    runtime_proof: str = "",
) -> dict[str, Any]:
    """Resolve the desktop runtime needed by the Session Share Privacy policy.

    PRIVATE_OVERLAY is Electron's best-effort setContentProtection on the
    Chengzhu windows.  It reduces accidental exposure on supported capture
    paths; it is not a security / stealth / undetectability guarantee.
    """
    policy = _normalize_session_policy(session.get("policy"))
    requested = str(policy.get("share_privacy") or "OFF")
    if requested == "OFF":
        return {
            "requested": "OFF",
            "available": True,
            "requires_desktop": False,
            "proof_required": False,
            "verified": True,
            "runtime": "OFF",
            "proof_kind": "",
            "note": "本场未请求 Share Privacy。",
        }

    verified = str(runtime_proof or "") == SHARE_PRIVACY_RUNTIME_PROOF
    return {
        "requested": "PRIVATE_OVERLAY",
        "available": True,
        "requires_desktop": True,
        "proof_required": True,
        "verified": verified,
        "runtime": "ELECTRON_SET_CONTENT_PROTECTION",
        "proof_kind": SHARE_PRIVACY_RUNTIME_PROOF,
        "note": (
            "Electron content protection 只用于降低成竹窗口在受支持屏幕共享/录制路径中的意外暴露；"
            "不同 OS / 捕获方式行为不同，这不是安全或“不可检测”保证。"
        ),
    }


def resolved_ai_behavior(policy: dict[str, Any]) -> dict[str, Any]:
    level = str(policy.get("ai_assistance") or "AI_ALLOWED")
    automatic = level in {"AI_ALLOWED", "AI_EXPECTED"}
    manual = level != "AI_FORBIDDEN"
    return {
        "policy": level,
        "manual_ask": manual,
        "manual_guidance": manual,
        "automatic_transcript_guidance": automatic,
        "automatic_candidate_extraction": automatic,
        "expected_by_user_report": level == "AI_EXPECTED",
        "engine": "LOCAL_DETERMINISTIC",
    }


def processing_runtime_status(session: dict[str, Any], *, include_self_mic: bool = False) -> dict[str, Any]:
    """Resolve whether the shared STT transport satisfies this Session policy.

    LOCAL is fail-closed because the mature shared pipeline may auto-open
    Doubao streaming when credentials exist even when stt_provider=whisper.
    Capture start calls this again so a config change after Preflight cannot
    silently violate the frozen policy.
    """
    from core.config import get_config

    cfg = get_config()
    mode = str(session.get("processing_mode") or "LOCAL").upper()
    capture_mode = str(session.get("capture_mode") or "NOTES_ONLY").upper()
    policy = _normalize_session_policy(session.get("policy"))
    provider = str(getattr(cfg, "stt_provider", "whisper") or "whisper").strip().lower()
    has_doubao = bool(
        getattr(cfg, "doubao_stt_api_key", "")
        or getattr(cfg, "doubao_stt_access_token", "")
    )
    main_remote_possible = provider in {"doubao", "generic"} or (provider == "whisper" and has_doubao)

    candidate_provider = str(getattr(cfg, "candidate_stt_provider", "whisper") or "whisper").strip().lower()
    candidate_remote_enabled = bool(getattr(cfg, "candidate_remote_stt_enabled", False))
    self_mic_remote_possible = include_self_mic and (
        candidate_remote_enabled or candidate_provider in {"doubao", "generic"}
    )

    blockers: list[str] = []
    if mode == "OFF":
        if capture_mode == "TRANSCRIPT":
            blockers.append("Processing=OFF 时不能启用 TRANSCRIPT")
        if policy["ai_assistance"] != "AI_FORBIDDEN":
            blockers.append("Processing=OFF 时 AI Assistance 必须为 AI_FORBIDDEN")
    elif mode == "LOCAL":
        if capture_mode == "TRANSCRIPT" and main_remote_possible:
            blockers.append(
                "Local Processing 要求主音频 STT 确定留在设备；当前共享 STT 配置存在远程路径"
            )
        if self_mic_remote_possible:
            blockers.append(
                "Local Processing 下所选自麦路径存在远程 ASR；请关闭远程候选人 ASR 或改用本地 Whisper"
            )

    if capture_mode == "TRANSCRIPT":
        capture_path = "LOCAL_DEVICE_CAPTURE"
        stt_path = "REMOTE_POSSIBLE" if main_remote_possible else "LOCAL_ONLY"
    elif capture_mode == "NO_CAPTURE":
        capture_path = "NO_CAPTURE"
        stt_path = "NOT_USED"
    else:
        capture_path = "STRUCTURED_NOTES_ONLY"
        stt_path = "NOT_USED"

    # Current Conversation reasoning/arbiter/manual retrieval is deterministic
    # inside the local backend. No LLM provider is invoked by this v2 runtime
    # path. If/when cloud inference is introduced, this field must change based
    # on the resolved provider rather than the requested policy label.
    inference_path = "LOCAL_DETERMINISTIC"

    retention_path = "LOCAL_PRODUCT_DB"
    writeback_path = (
        "DISABLED"
        if policy["external_writeback"] == "OFF"
        else "LOCAL_REVIEWED_DRAFT_ONLY"
    )

    return {
        "mode": mode,
        "capture_mode": capture_mode,
        "configured_stt_provider": provider,
        "main_audio_remote_possible": main_remote_possible,
        "self_mic_remote_possible": self_mic_remote_possible,
        "data_path": {
            "capture": capture_path,
            "stt": stt_path,
            "inference": inference_path,
            "retention": retention_path,
            "writeback": writeback_path,
            "audio_retention": "OFF",
            "transcript_retention": policy["transcript_retention"],
        },
        "blockers": blockers,
    }


def _expression_profile() -> dict[str, Any]:
    """Reuse the user's existing '我的表达' preferences for Conversation.

    This is intentionally the same profile Interview uses; Conversation does
    not create a second voice/style truth store.
    """
    row = intelligence_store.get_voice_profile("local")
    profile = (row or {}).get("profile") if row else {}
    if not isinstance(profile, dict):
        return {}
    prefs = profile.get("explicit_preferences") or {}
    return dict(prefs) if isinstance(prefs, dict) else {}


def _counterparty_state(
    *,
    explicit_priority: str = "",
    explicit_concern: str = "",
    stated_position: str = "",
    decision_authority: str = "",
    relationship_context: str = "",
    source_refs: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    explicit = {
        "priority": str(explicit_priority or "")[:800],
        "concern": str(explicit_concern or "")[:1200],
        "stated_position": str(stated_position or "")[:1600],
        "decision_authority": str(decision_authority or "")[:500],
        "relationship_context": str(relationship_context or "")[:800],
    }
    known = {k: v for k, v in explicit.items() if v}
    refs = list(source_refs or [])[:20]
    if known and not refs:
        refs = [{"kind": "USER_INPUT", "excerpt": "用户明确录入的 Counterparty State"}]
    return {
        "known_explicit": known,
        "source_refs": refs,
        "confidence": 1.0 if known else 0.0,
        "temporary_inferences": [],
        "unknown": [key for key, value in explicit.items() if not value],
    }

ITEM_TYPES = {t.value for t in ConversationItemType}
ITEM_STATES = {s.value for s in ConversationItemState}
REVIEW_STATUSES = {"AI_EXTRACTED", "USER_CONFIRMED", "USER_EDITED", "USER_REJECTED", "SOURCE_CONFIRMED"}
EPISTEMIC_STATUSES = {"OBSERVED", "USER_CONFIRMED", "SOURCE_CONFIRMED", "INFERRED", "UNKNOWN"}


def templates() -> list[dict[str, Any]]:
    launch_wedges = {"PROJECT_SYNC", "DESIGN_REVIEW"}
    return [
        {
            "key": key,
            **value,
            "runtime_available": True,
            "launch_wedge": key in launch_wedges,
            "specialized_behavior_validated": False,
            "stable_release": False,
            "real_user_validated": False,
            "maturity": "BETA_WEDGE" if key in launch_wedges else "SHARED_RUNTIME_TEMPLATE",
        }
        for key, value in SPACE_PROFILES.items()
    ]


def profile_playbook(profile_key: str) -> dict[str, Any]:
    config = SPACE_PROFILES.get(str(profile_key or "").upper()) or {}
    playbook = config.get("playbook") or {}
    return {
        "profile": str(profile_key or "").upper(),
        "success_conditions": list(playbook.get("success_conditions") or []),
        "priority_truth_types": list(playbook.get("priority_truth_types") or []),
        "prepare_prompts": list(playbook.get("prepare_prompts") or []),
        "closing_objective": str(playbook.get("closing_objective") or ""),
        "boundaries": list(playbook.get("boundaries") or []),
    }


def _profile_outcome_evidence(session: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    """Reviewed output counts for this Profile, never a synthetic success score."""
    space = require_space(session["space_id"])
    # Continue must use the Playbook frozen at Session start. Today's template
    # cannot retroactively reclassify prior reviewed output.
    frozen = _frozen_pack_payload(session).get("profile_playbook")
    if isinstance(frozen, dict) and frozen.get("profile") == space["profile"]:
        playbook = dict(frozen)
    else:
        playbook = profile_playbook(space["profile"])
    allowed = set(playbook["priority_truth_types"])
    counts: dict[str, int] = {kind: 0 for kind in playbook["priority_truth_types"]}
    reviewed = []
    for item in items:
        if item.get("type") not in allowed:
            continue
        if item.get("review_status") not in THREAD_CONFIRMED_REVIEW:
            continue
        if item.get("state") in {"UNKNOWN"}:
            continue
        counts[item["type"]] = counts.get(item["type"], 0) + 1
        reviewed.append({
            "id": item["id"],
            "type": item["type"],
            "state": item["state"],
            "title": item["title"],
            "review_status": item["review_status"],
        })
    return {
        "profile": space["profile"],
        "closing_objective": playbook["closing_objective"],
        "priority_truth_types": playbook["priority_truth_types"],
        "reviewed_counts": counts,
        "reviewed_outputs": reviewed[:20],
        "interpretation": "Reviewed output evidence only; not a meeting-quality or success score.",
    }


def _require_choice(value: str, allowed: set[str], label: str) -> str:
    value = str(value or "").upper()
    if value not in allowed:
        raise ValueError(f"{label} 不支持：{value}")
    return value


def require_space(space_id: str) -> dict[str, Any]:
    row = store.get("conversation_space", space_id)
    if not row:
        raise ValueError("对话空间不存在")
    return row


def require_session(session_id: str) -> dict[str, Any]:
    row = store.get("conversation_session", session_id)
    if not row:
        raise ValueError("对话会话不存在")
    return row


def require_item(item_id: str) -> dict[str, Any]:
    row = store.get("conversation_item", item_id)
    if not row:
        raise ValueError("对话事项不存在")
    return row


def create_space(
    title: str,
    profile: str = "PROJECT_SYNC",
    *,
    description: str = "",
    default_goal: str = "",
    default_mode: str = "",
    project_id: str = "",
    relationship_key: str = "",
    selected_source_ids: Optional[list[str]] = None,
    selected_quick_note_ids: Optional[list[str]] = None,
    selected_connector_snapshot_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    title = str(title or "").strip()
    if not title:
        raise ValueError("对话空间名称不能为空")
    profile = str(profile or "").upper()
    if profile not in SPACE_PROFILES:
        raise ValueError(f"对话模板不支持：{profile}")
    mode = (default_mode or SPACE_PROFILES[profile]["default_mode"]).upper()
    _require_choice(mode, ASSISTANCE_MODES, "帮助方式")
    ts = store.now()
    row = {
        "id": store.new_id("cs_"),
        "profile": profile,
        "title": title[:160],
        "description": str(description or "")[:4000],
        "status": "ACTIVE",
        "project_id": str(project_id or "")[:200],
        "relationship_key": str(relationship_key or "")[:200],
        "default_goal": str(default_goal or "")[:1000],
        "default_mode": mode,
        "selected_source_ids": list(selected_source_ids or []),
        "selected_quick_note_ids": list(selected_quick_note_ids or []),
        "selected_connector_snapshot_ids": list(selected_connector_snapshot_ids or []),
        "retention_policy": {
            **dict(RETENTION_PRESETS["STANDARD"]),
            "connector_snapshot_days": 30,
        },
        "created_at": ts,
        "updated_at": ts,
    }
    store.insert("conversation_space", row)
    if row["default_goal"]:
        create_goal(row["id"], row["default_goal"])
    return require_space(row["id"])


def list_spaces(status: str = "ACTIVE") -> list[dict[str, Any]]:
    where = ""
    params: tuple[Any, ...] = ()
    if status:
        where, params = "status = ?", (status.upper(),)
    return store.select("conversation_space", where=where, params=params, order="updated_at DESC")


def list_space_summaries(status: str = "") -> list[dict[str, Any]]:
    rows = list_spaces(status)
    now = store.now()
    out: list[dict[str, Any]] = []
    for space in rows:
        upcoming = store.select(
            "conversation_session",
            where="space_id = ? AND status = 'UPCOMING' AND scheduled_at IS NOT NULL AND scheduled_at >= ?",
            params=(space["id"], now),
            order="scheduled_at ASC",
            limit=1,
        )
        recent = store.select(
            "conversation_session",
            where="space_id = ?",
            params=(space["id"],),
            order="COALESCE(ended_at, started_at, scheduled_at, created_at) DESC",
            limit=1,
        )
        open_commitments = int(store.scalar(
            "SELECT COUNT(*) FROM conversation_item WHERE space_id = ? "
            "AND type IN ('Commitment','Task') AND state = 'COMMITTED' "
            "AND review_status IN ('USER_CONFIRMED','USER_EDITED','SOURCE_CONFIRMED')",
            (space["id"],),
        ) or 0)
        open_questions = int(store.scalar(
            "SELECT COUNT(*) FROM conversation_item WHERE space_id = ? "
            "AND type = 'OpenQuestion' AND state NOT IN ('DONE','SUPERSEDED','UNKNOWN') "
            "AND review_status IN ('USER_CONFIRMED','USER_EDITED','SOURCE_CONFIRMED')",
            (space["id"],),
        ) or 0)
        out.append({
            **space,
            "default_goal": _primary_goal_title(space["id"]),
            "next_session": upcoming[0] if upcoming else None,
            "last_session": recent[0] if recent else None,
            "open_commitments_count": open_commitments,
            "open_questions_count": open_questions,
        })
    return out


def update_space(space_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    current = require_space(space_id)
    requested_default_goal = patch.get("default_goal") if "default_goal" in patch else None
    allowed = {
        "title", "description", "status", "project_id", "relationship_key",
        "default_mode", "selected_source_ids", "selected_quick_note_ids",
        "selected_connector_snapshot_ids", "retention_policy",
    }
    clean = {k: v for k, v in patch.items() if k in allowed}
    if "title" in clean:
        clean["title"] = str(clean["title"] or "").strip()[:160]
        if not clean["title"]:
            raise ValueError("对话空间名称不能为空")
    if "default_mode" in clean:
        clean["default_mode"] = _require_choice(str(clean["default_mode"]), ASSISTANCE_MODES, "帮助方式")
    if "status" in clean:
        clean["status"] = str(clean["status"]).upper()
        if clean["status"] not in {"ACTIVE", "ARCHIVED"}:
            raise ValueError("对话空间状态不支持")
    if "retention_policy" in clean:
        raw_policy = clean["retention_policy"] if isinstance(clean["retention_policy"], dict) else {}
        preset = str(raw_policy.get("preset") or "CUSTOM").upper()
        if preset in RETENTION_PRESETS:
            clean["retention_policy"] = dict(RETENTION_PRESETS[preset])
        else:
            def _days(key: str, default: int) -> int:
                try:
                    return max(0, min(3650, int(raw_policy.get(key, default))))
                except (TypeError, ValueError):
                    return default
            clean["retention_policy"] = {
                "preset": "CUSTOM",
                "transcript_days": _days("transcript_days", 30),
                "guidance_days": _days("guidance_days", 30),
                "draft_days": _days("draft_days", 30),
                "connector_snapshot_days": _days("connector_snapshot_days", 30),
                "confirmed_items": "KEEP",
                "audio_retention": "OFF",
            }
    clean["updated_at"] = store.now()
    if clean:
        store.update("conversation_space", space_id, clean)

    if "default_goal" in patch:
        title = str(requested_default_goal or "").strip()
        active = _active_goals(space_id)
        if not title:
            if active:
                raise ValueError("default_goal 只是 ACTIVE Conversation Goal 的投影；请通过 Goal lifecycle 显式 Resolve")
            _sync_primary_goal_projection(space_id)
        elif active:
            update_goal(active[0]["id"], {"title": title})
        else:
            create_goal(space_id, title)

    return require_space(space_id) if (clean or "default_goal" in patch) else current


def delete_space(space_id: str, *, confirm: bool = False) -> bool:
    require_space(space_id)
    if not confirm:
        raise ValueError("删除整个 Conversation Space 会彻底擦除其 Session、Items、Packs、Drafts 与 provenance tombstones；请明确确认")
    try:
        from services import coach as human_coach
        for session in list_sessions(space_id):
            human_coach.registry.revoke_for_target(session["id"], session_kind="conversation")
    except Exception:
        pass
    return store.delete("conversation_space", space_id)


def _active_goals(space_id: str) -> list[dict[str, Any]]:
    return store.select(
        "conversation_goal",
        where="space_id = ? AND status = 'ACTIVE'",
        params=(space_id,),
        order="priority DESC, created_at ASC",
    )


def _goals_for_session(session: dict[str, Any]) -> list[dict[str, Any]]:
    ids = set(session.get("goal_ids") or [])
    if not ids:
        return []
    return [
        goal for goal in store.select(
            "conversation_goal",
            where="space_id = ?",
            params=(session["space_id"],),
            order="priority DESC, created_at ASC",
        )
        if goal["id"] in ids
    ]


def _primary_goal_title(space_id: str) -> str:
    active = _active_goals(space_id)
    return str(active[0].get("title") or "") if active else ""


def _sync_primary_goal_projection(space_id: str) -> None:
    space = store.get("conversation_space", space_id)
    if not space:
        return
    projected = _primary_goal_title(space_id)
    if str(space.get("default_goal") or "") != projected:
        store.update("conversation_space", space_id, {
            "default_goal": projected,
            "updated_at": store.now(),
        })


def create_goal(space_id: str, title: str, outcome_definition: str = "", priority: int = 50) -> dict[str, Any]:
    require_space(space_id)
    title = str(title or "").strip()
    if not title:
        raise ValueError("对话目标不能为空")
    row = {
        "id": store.new_id("cg_"),
        "space_id": space_id,
        "title": title[:240],
        "outcome_definition": str(outcome_definition or "")[:2000],
        "status": "ACTIVE",
        "priority": max(0, min(100, int(priority))),
        "source": {"kind": "USER"},
        "created_at": store.now(),
        "resolved_at": None,
    }
    store.insert("conversation_goal", row)
    _sync_primary_goal_projection(space_id)
    return store.get("conversation_goal", row["id"]) or row


def update_goal(goal_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    goal = store.get("conversation_goal", goal_id)
    if not goal:
        raise ValueError("Conversation Goal 不存在")
    clean: dict[str, Any] = {}
    if "title" in patch:
        title = str(patch.get("title") or "").strip()
        if not title:
            raise ValueError("对话目标不能为空")
        clean["title"] = title[:240]
    if "outcome_definition" in patch:
        clean["outcome_definition"] = str(patch.get("outcome_definition") or "")[:2000]
    if "priority" in patch:
        clean["priority"] = max(0, min(100, int(patch.get("priority") or 0)))
    if "status" in patch:
        status = str(patch.get("status") or "").upper()
        if status not in {"ACTIVE", "RESOLVED"}:
            raise ValueError("Conversation Goal 状态只支持 ACTIVE / RESOLVED")
        clean["status"] = status
        clean["resolved_at"] = store.now() if status == "RESOLVED" else None
    if clean:
        store.update("conversation_goal", goal_id, clean)
        _sync_primary_goal_projection(goal["space_id"])
    return store.get("conversation_goal", goal_id) or goal


def add_participant(
    space_id: str,
    *,
    display_name: str = "",
    role: str = "",
    organization: str = "",
    session_id: str = "",
    identity_source: str = "USER",
    explicit_priority: str = "",
    explicit_concern: str = "",
    stated_position: str = "",
    decision_authority: str = "",
    relationship_context: str = "",
    source_refs: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    require_space(space_id)
    if session_id:
        require_session(session_id)
    ts = store.now()
    row = {
        "id": store.new_id("cp_"),
        "space_id": space_id,
        "session_id": session_id or None,
        "display_name": str(display_name or "")[:160],
        "role": str(role or "")[:160],
        "organization": str(organization or "")[:160],
        "identity_confidence": 1.0 if display_name else 0.0,
        "identity_source": str(identity_source or "USER")[:80],
        "visibility": "PRIVATE",
        "observations": [],
        "counterparty_state": _counterparty_state(
            explicit_priority=explicit_priority,
            explicit_concern=explicit_concern,
            stated_position=stated_position,
            decision_authority=decision_authority,
            relationship_context=relationship_context,
            source_refs=source_refs,
        ),
        "created_at": ts,
        "updated_at": ts,
    }
    store.insert("conversation_participant", row)
    return store.get("conversation_participant", row["id"]) or row


def update_participant(participant_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    participant = store.get("conversation_participant", participant_id)
    if not participant:
        raise ValueError("Conversation Participant 不存在")

    clean: dict[str, Any] = {}
    for key, limit in (("display_name", 160), ("role", 160), ("organization", 160)):
        if key in patch:
            clean[key] = str(patch.get(key) or "")[:limit]

    state = dict(participant.get("counterparty_state") or {})
    known = dict(state.get("known_explicit") or {})
    mapping = {
        "explicit_priority": ("priority", 800),
        "explicit_concern": ("concern", 1200),
        "stated_position": ("stated_position", 1600),
        "decision_authority": ("decision_authority", 500),
        "relationship_context": ("relationship_context", 800),
    }
    changed_explicit = False
    for incoming, (stored, limit) in mapping.items():
        if incoming not in patch:
            continue
        changed_explicit = True
        value = str(patch.get(incoming) or "")[:limit].strip()
        if value:
            known[stored] = value
        else:
            known.pop(stored, None)

    if changed_explicit or "source_refs" in patch:
        refs = list(patch.get("source_refs") or state.get("source_refs") or [])
        rebuilt = _counterparty_state(
            explicit_priority=str(known.get("priority") or ""),
            explicit_concern=str(known.get("concern") or ""),
            stated_position=str(known.get("stated_position") or ""),
            decision_authority=str(known.get("decision_authority") or ""),
            relationship_context=str(known.get("relationship_context") or ""),
            source_refs=refs,
        )
        clean["counterparty_state"] = rebuilt

    if "display_name" in clean:
        clean["identity_confidence"] = 1.0 if clean["display_name"] else 0.0
    clean["updated_at"] = store.now()
    store.update("conversation_participant", participant_id, clean)
    return store.get("conversation_participant", participant_id) or participant


def create_session(
    space_id: str,
    *,
    title: str = "",
    goal_ids: Optional[list[str]] = None,
    scheduled_at: Optional[float] = None,
    capture_mode: str = "NOTES_ONLY",
    processing_mode: str = "LOCAL",
    assistance_mode: str = "",
    consent_ack: bool = False,
    policy: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    space = require_space(space_id)
    capture = _require_choice(capture_mode, CAPTURE_MODES, "记录方式")
    processing = _require_choice(processing_mode, PROCESSING_MODES, "处理方式")
    mode = _require_choice(assistance_mode or space["default_mode"], ASSISTANCE_MODES, "帮助方式")
    ts = store.now()
    resolved_goal_ids = list(goal_ids or [])
    if not resolved_goal_ids:
        resolved_goal_ids = [
            goal["id"] for goal in store.select(
                "conversation_goal",
                where="space_id = ? AND status = 'ACTIVE'",
                params=(space_id,),
                order="priority DESC, created_at ASC",
            )
        ]
    else:
        valid_ids = {
            goal["id"] for goal in store.select(
                "conversation_goal",
                where="space_id = ?",
                params=(space_id,),
                order="created_at ASC",
            )
        }
        unknown = [goal_id for goal_id in resolved_goal_ids if goal_id not in valid_ids]
        if unknown:
            raise ValueError("Session Goal 必须属于当前 Conversation Space")
    row = {
        "id": store.new_id("cv_"),
        "space_id": space_id,
        "goal_ids": resolved_goal_ids,
        "template": space["profile"],
        "title": (str(title or "").strip() or space["title"])[:200],
        "scheduled_at": scheduled_at,
        "started_at": None,
        "ended_at": None,
        "capture_mode": capture,
        "processing_mode": processing,
        "assistance_mode": mode,
        "consent_ack": bool(consent_ack),
        "policy": _normalize_session_policy(policy),
        "pack_id": "",
        "status": "UPCOMING",
        "state": {"current_topic": "", "open_threads": [], "last_guidance_id": ""},
        "source_calendar_event": {},
        "created_at": ts,
        "updated_at": ts,
    }
    store.insert("conversation_session", row)
    return require_session(row["id"])


def list_sessions(space_id: str) -> list[dict[str, Any]]:
    require_space(space_id)
    return store.select(
        "conversation_session", where="space_id = ?", params=(space_id,),
        order="COALESCE(started_at, scheduled_at, created_at) DESC",
    )


def _pack_inputs(space: dict[str, Any]) -> dict[str, Any]:
    """Resolve the exact Ready sources and existing Quick Notes a new pack would freeze."""
    selected_sources: list[dict[str, Any]] = []
    skipped_sources: list[dict[str, str]] = []
    for source_id in space.get("selected_source_ids") or []:
        ready = materials.ready_text(str(source_id))
        if ready:
            selected_sources.append(ready)
        else:
            raw = store.get("material", str(source_id))
            skipped_sources.append({
                "id": str(source_id),
                "title": str((raw or {}).get("title") or ""),
                "reason": "NOT_READY_OR_MISSING",
            })

    selected_notes: list[dict[str, Any]] = []
    missing_note_ids: list[str] = []
    for note_id in space.get("selected_quick_note_ids") or []:
        note = store.get("quick_note", str(note_id))
        if note:
            selected_notes.append({
                "id": note["id"],
                "title": note.get("title", ""),
                "content": note.get("content", ""),
                "kind": "USER_NOTE",
            })
        else:
            missing_note_ids.append(str(note_id))
    return {
        "sources": selected_sources,
        "skipped_sources": skipped_sources,
        "quick_notes": selected_notes,
        "missing_quick_note_ids": missing_note_ids,
    }


def _preflight_context_fingerprint(
    session: dict[str, Any],
    space: dict[str, Any],
    pack_inputs: dict[str, Any],
    policy: dict[str, Any],
    processing_runtime: dict[str, Any],
    screen_runtime: dict[str, Any],
    connector_runtime: dict[str, Any],
) -> str:
    """Hash every mutable input that can materially change the eventual Pack.

    This is a TOCTOU guard, not a security signature. The user-facing Preview
    and Start must refer to the same context revision; if any relevant input
    changes after Preview, Start asks the user to run Preflight again.
    """
    goals = _goals_for_session(session)
    participants = store.select(
        "conversation_participant",
        where="space_id = ?",
        params=(space["id"],),
        order="created_at ASC",
    )
    confirmed = _confirmed_context_items(space["id"])
    threads = store.select(
        "conversation_open_thread",
        where="space_id = ? AND status = 'OPEN'",
        params=(space["id"],),
        order="created_at DESC",
    )
    prepared = prepare_space(space["id"])
    snapshot = {
        "session": {
            "id": session["id"],
            "title": session.get("title") or "",
            "scheduled_at": session.get("scheduled_at"),
            "goal_ids": list(session.get("goal_ids") or []),
            "capture_mode": session.get("capture_mode"),
            "processing_mode": session.get("processing_mode"),
            "assistance_mode": session.get("assistance_mode"),
            "consent_ack": bool(session.get("consent_ack")),
            "policy": policy,
        },
        "space": {
            "id": space["id"],
            "profile": space.get("profile"),
            "title": space.get("title"),
            "selected_source_ids": list(space.get("selected_source_ids") or []),
            "selected_quick_note_ids": list(space.get("selected_quick_note_ids") or []),
            "retention_policy": dict(space.get("retention_policy") or {}),
        },
        "goals": [
            {
                "id": g.get("id"),
                "title": g.get("title"),
                "outcome_definition": g.get("outcome_definition"),
                "priority": g.get("priority"),
                "status": g.get("status"),
                "updated_at": g.get("updated_at"),
            }
            for g in goals
        ],
        "sources": [
            {
                "material_id": s.get("material_id"),
                "version_id": s.get("version_id"),
                "content_hash": s.get("content_hash"),
                "text": s.get("text"),
            }
            for s in pack_inputs.get("sources") or []
        ],
        "skipped_sources": list(pack_inputs.get("skipped_sources") or []),
        "quick_notes": list(pack_inputs.get("quick_notes") or []),
        "missing_quick_note_ids": list(pack_inputs.get("missing_quick_note_ids") or []),
        "participants": participants,
        "confirmed_items": confirmed,
        "open_threads": threads,
        "expression_profile": _expression_profile(),
        "prepared": {
            "agenda": list(prepared.get("agenda") or []),
            "expected_questions": list(prepared.get("expected_questions") or []),
            "contribution_candidates": list(prepared.get("contribution_candidates") or []),
        },
        "processing_runtime": processing_runtime,
        "screen_runtime": screen_runtime,
        "connector_runtime": connector_runtime,
    }
    raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def preflight(session_id: str, *, record_fingerprint: bool = True) -> dict[str, Any]:
    session = require_session(session_id)
    space = require_space(session["space_id"])
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    consent_ok = not (session["capture_mode"] == "TRANSCRIPT" and not session["consent_ack"])
    if not consent_ok:
        blockers.append({"key": "consent", "label": "转写确认", "message": "开启转写前，请确认当前场景允许记录/转写。"})

    policy = _normalize_session_policy(session.get("policy"))
    ai_behavior = resolved_ai_behavior(policy)
    retention = dict(space.get("retention_policy") or RETENTION_PRESETS["STANDARD"])
    processing_runtime = processing_runtime_status(session)
    for message in processing_runtime["blockers"]:
        blockers.append({
            "key": "processing_runtime",
            "label": "处理方式",
            "message": message,
        })

    screen_runtime = conversation_screen.vision_runtime_status(session)
    for message in screen_runtime["blockers"]:
        blockers.append({
            "key": "screen_context_runtime",
            "label": "屏幕上下文",
            "message": message,
        })

    connector_runtime = conversation_connectors.resolve_read_permissions(policy.get("connector_permissions") or [])
    connector_ok = bool(connector_runtime["ok"])
    if not connector_ok:
        blocked_names = ", ".join(
            f"{item['capability']}:{item['reason']}" for item in connector_runtime["blocked"]
        )
        blockers.append({
            "key": "connector_runtime",
            "label": "连接器权限",
            "message": (
                "本场请求的 connector capability 没有真实可用 provider；"
                f"{blocked_names or 'NO_AVAILABLE_PROVIDER'}。不会用 placeholder 放行。"
            ),
        })

    share_privacy_runtime = share_privacy_runtime_status(session)
    share_ok = True
    if policy["share_privacy"] == "PRIVATE_OVERLAY":
        warnings.append({
            "key": "share_privacy_verify_at_start",
            "label": "屏幕共享保护",
            "message": (
                "本场将在桌面端点击“开始会话”时临时启用并验证 Electron content protection；"
                "Web fallback 没有该 bridge 时会 fail-closed。此能力只降低受支持捕获路径中的意外暴露，不提供“隐身/不可检测”保证。"
            ),
        })

    screen_ok = (
        policy["screen_context"] == "OFF"
        or (policy["screen_context"] in {"MANUAL", "AUTO"} and not screen_runtime["blockers"])
    )

    human_ok = True
    if policy["human_assistance"] == "HUMAN_ALLOWED":
        if policy["participant_transparency_plan"] == "NOT_RECORDED":
            human_ok = False
            blockers.append({
                "key": "human_assistance_transparency",
                "label": "Human Assistance",
                "message": "启用 Conversation Human Coach 前必须记录参与者透明告知计划；成竹不会自动通知其他参与者。",
            })
        else:
            warnings.append({
                "key": "human_coach_explicit_start",
                "label": "Human Assistance",
                "message": (
                    "Human Coach 不会随 Session 自动连接。进入 Live 后必须显式生成一次性教练链接，"
                    "并逐项授权 transcript / AI cue / frozen session context；建议始终标记为 HUMAN_COACH，绝不成为事实或证据。"
                ),
            })

    pack_inputs = _pack_inputs(space)
    for skipped in pack_inputs["skipped_sources"]:
        warnings.append({
            "key": "source_not_ready",
            "label": "带入来源",
            "message": f"“{skipped.get('title') or skipped['id']}” 当前不是 READY，本场 Session Pack 会明确跳过它。",
        })
    for note_id in pack_inputs["missing_quick_note_ids"]:
        warnings.append({
            "key": "quick_note_missing",
            "label": "Quick Note",
            "message": f"Quick Note {note_id} 已不存在，本场不会冻结它。",
        })
    if session["capture_mode"] == "TRANSCRIPT" and policy["participant_consent_status"] == "NOT_RECORDED":
        warnings.append({
            "key": "participant_consent_not_recorded",
            "label": "参与者同意状态",
            "message": "你已确认当前场景允许转写，但尚未记录参与者同意状态；成竹不会自行推断或验证该状态。",
        })
    if session["capture_mode"] == "TRANSCRIPT" and policy["participant_transparency_plan"] == "NOT_RECORDED":
        warnings.append({
            "key": "participant_transparency_not_recorded",
            "label": "透明告知计划",
            "message": "尚未记录你将如何让参与者知道正在使用转写/辅助。成竹当前不会自动发送 chat notice 或添加 watermark。",
        })

    context_fingerprint = _preflight_context_fingerprint(
        session, space, pack_inputs, policy, processing_runtime, screen_runtime, connector_runtime
    )
    if record_fingerprint and session["status"] == "UPCOMING":
        state = dict(session.get("state") or {})
        state["preflight_context_fingerprint"] = context_fingerprint
        store.update("conversation_session", session_id, {
            "state": state,
            "updated_at": store.now(),
        })

    session_goals = _goals_for_session(session)
    selected_source_count = len(space.get("selected_source_ids") or [])
    ready_source_count = len(pack_inputs["sources"])
    selected_note_count = len(space.get("selected_quick_note_ids") or [])
    ready_note_count = len(pack_inputs["quick_notes"])
    participant_consent_ok = (
        session["capture_mode"] != "TRANSCRIPT"
        or policy["participant_consent_status"] != "NOT_RECORDED"
    )
    participant_transparency_ok = (
        session["capture_mode"] != "TRANSCRIPT"
        or policy["participant_transparency_plan"] != "NOT_RECORDED"
    )
    ai_ok = not (
        session["processing_mode"] == "OFF"
        and policy["ai_assistance"] != "AI_FORBIDDEN"
    )

    items = [
        {"key": "goal", "label": "本次目标", "value": (session_goals[0]["title"] if session_goals else "可在会中补充"), "ok": True},
        {"key": "schedule", "label": "人工排期", "value": session.get("scheduled_at") or "未排期", "ok": True},
        {"key": "mode", "label": "帮助方式", "value": session["assistance_mode"], "ok": True},
        {"key": "capture", "label": "记录方式", "value": session["capture_mode"], "ok": consent_ok},
        {"key": "processing", "label": "处理方式", "value": session["processing_mode"], "ok": not processing_runtime["blockers"]},
        {"key": "stt_route", "label": "当前 STT 数据路径", "value": (
            "REMOTE_POSSIBLE" if processing_runtime["main_audio_remote_possible"] else "LOCAL_ONLY"
        ), "ok": not (session["processing_mode"] == "LOCAL" and processing_runtime["main_audio_remote_possible"])},
        {"key": "retention", "label": "转写保留", "value": f"{retention.get('preset', 'STANDARD')} · {retention.get('transcript_days', 30)}d", "ok": True},
        {"key": "sources", "label": "带入来源", "value": f"{ready_source_count}/{selected_source_count} Ready", "ok": ready_source_count == selected_source_count},
        {"key": "quick_notes", "label": "Quick Notes", "value": f"{ready_note_count}/{selected_note_count} available", "ok": ready_note_count == selected_note_count},
        {"key": "connectors", "label": "连接器权限", "value": len(policy.get("connector_permissions") or []), "ok": connector_ok},
        {"key": "participant_consent", "label": "参与者同意状态（用户报告）", "value": policy["participant_consent_status"], "ok": participant_consent_ok},
        {"key": "participant_transparency", "label": "参与者透明告知（用户计划）", "value": policy["participant_transparency_plan"], "ok": participant_transparency_ok},
        {"key": "screen", "label": "屏幕上下文", "value": (
            f"{policy['screen_context']} · {screen_runtime['route']}"
            if policy["screen_context"] in {"MANUAL", "AUTO"}
            else policy["screen_context"]
        ), "ok": screen_ok},
        {"key": "ai", "label": "AI Assistance", "value": policy["ai_assistance"], "ok": ai_ok},
        {"key": "ai_behavior", "label": "AI 自动行为", "value": (
            "AUTO_GUIDANCE_AND_EXTRACTION" if ai_behavior["automatic_transcript_guidance"]
            else "MANUAL_ONLY" if ai_behavior["manual_ask"]
            else "DISABLED"
        ), "ok": True},
        {"key": "human", "label": "Human Assistance", "value": (
            "HUMAN_ALLOWED · EXPLICIT_LINK" if policy["human_assistance"] == "HUMAN_ALLOWED"
            else policy["human_assistance"]
        ), "ok": human_ok},
        {"key": "share", "label": "屏幕共享保护", "value": (
            "PRIVATE_OVERLAY · VERIFY_AT_START" if policy["share_privacy"] == "PRIVATE_OVERLAY" else "OFF"
        ), "ok": share_ok},
        {"key": "writeback", "label": "外部写回", "value": policy["external_writeback"], "ok": True},
    ]
    return {
        "session": session,
        "space": space,
        "items": items,
        "blockers": blockers,
        "warnings": warnings,
        "context_fingerprint": context_fingerprint,
        "policy": policy,
        "resolved_ai_behavior": ai_behavior,
        "processing_runtime": processing_runtime,
        "screen_runtime": screen_runtime,
        "connector_runtime": connector_runtime,
        "share_privacy_runtime": share_privacy_runtime,
        "pack_preview": {
            "goal_ids": list(session.get("goal_ids") or []),
            "selected_source_ids": list(space.get("selected_source_ids") or []),
            "selected_quick_note_ids": list(space.get("selected_quick_note_ids") or []),
            "sources": [
                {
                    "material_id": source.get("material_id") or "",
                    "version_id": source.get("version_id") or "",
                    "title": source.get("title") or "",
                    "kind": source.get("kind") or "",
                    "usage": source.get("usage") or "",
                    "content_hash": source.get("content_hash") or "",
                    "is_personal_evidence": bool(source.get("is_personal_evidence")),
                }
                for source in pack_inputs["sources"]
            ],
            "skipped_sources": list(pack_inputs["skipped_sources"]),
            "quick_notes": [
                {"id": note.get("id") or "", "title": note.get("title") or ""}
                for note in pack_inputs["quick_notes"]
            ],
            "missing_quick_note_ids": list(pack_inputs["missing_quick_note_ids"]),
            "participants_count": int(store.scalar(
                "SELECT COUNT(*) FROM conversation_participant WHERE space_id = ?",
                (space["id"],),
            ) or 0),
            "confirmed_items_count": len(_confirmed_context_items(space["id"])),
            "expression_profile": _expression_profile(),
            "resolved_ai_behavior": ai_behavior,
            "processing_runtime": processing_runtime,
            "screen_runtime": screen_runtime,
            "connector_runtime": connector_runtime,
            "share_privacy_runtime": share_privacy_runtime,
            "policy": {
                **policy,
                "capture_mode": session["capture_mode"],
                "processing_mode": session["processing_mode"],
                "assistance_mode": session["assistance_mode"],
            },
        },
        "privacy_note": "记录、转写与第三方数据应遵循当前场景、组织政策与适用规则；参与者同意状态与透明告知计划仅来自用户报告，成竹不会自行验证、推断或自动通知其他参与者；也不会自动共享、自动发送或自动写入外部系统。",
    }

def _confirmed_context_items(space_id: str) -> list[dict[str, Any]]:
    return store.select(
        "conversation_item",
        where="space_id = ? AND review_status IN ('USER_CONFIRMED','USER_EDITED','SOURCE_CONFIRMED') "
              "AND state NOT IN ('SUPERSEDED')",
        params=(space_id,),
        order="created_at DESC",
        limit=100,
    )


def freeze_pack(
    session_id: str,
    *,
    share_privacy_runtime: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    session = require_session(session_id)
    space = require_space(session["space_id"])
    existing = store.select("conversation_session_pack", where="session_id = ?", params=(session_id,), limit=1)
    if existing:
        return existing[0]
    pack_inputs = _pack_inputs(space)
    participants = store.select("conversation_participant", where="space_id = ?", params=(space["id"],), order="created_at ASC")
    prepared = prepare_space(space["id"])
    frozen_goals = _goals_for_session(session)

    payload = {
        "contract": "v2.0-R1",
        "space": {"id": space["id"], "profile": space["profile"], "title": space["title"]},
        "goal_ids": session.get("goal_ids") or [],
        "selected_source_ids": space.get("selected_source_ids") or [],
        "sources": pack_inputs["sources"],
        "skipped_sources": pack_inputs["skipped_sources"],
        "quick_notes": pack_inputs["quick_notes"],
        "missing_quick_note_ids": pack_inputs["missing_quick_note_ids"],
        "confirmed_items": _confirmed_context_items(space["id"]),
        "participants": participants,
        "profile_playbook": profile_playbook(space["profile"]),
        "session_brief": {
            "title": session.get("title") or space.get("title") or "",
            "scheduled_at": session.get("scheduled_at"),
            "goal": frozen_goals[0]["title"] if frozen_goals else "",
            "goals": [
                {
                    "id": goal["id"],
                    "title": goal["title"],
                    "outcome_definition": goal.get("outcome_definition") or "",
                    "priority": goal.get("priority") or 0,
                }
                for goal in frozen_goals
            ],
            "agenda": list(prepared.get("agenda") or []),
            "expected_questions": list(prepared.get("expected_questions") or []),
            "open_threads": [
                {
                    "id": thread.get("id") or "",
                    "kind": thread.get("kind") or "",
                    "text": thread.get("text") or "",
                    "owner_id": thread.get("owner_id") or "",
                    "source_refs": list(thread.get("source_refs") or []),
                }
                for thread in (prepared.get("open_threads") or [])
            ],
            "unresolved_count": int((prepared.get("brief") or {}).get("unresolved_count") or 0),
            "known_participants": int((prepared.get("brief") or {}).get("known_participants") or 0),
            "contribution_candidates": list(prepared.get("contribution_candidates") or []),
        },
        "expression_profile": _expression_profile(),
        "resolved_ai_behavior": resolved_ai_behavior(_normalize_session_policy(session.get("policy"))),
        "processing_runtime": processing_runtime_status(session),
        "screen_runtime": conversation_screen.vision_runtime_status(session),
        "connector_runtime": conversation_connectors.resolve_read_permissions(
            _normalize_session_policy(session.get("policy")).get("connector_permissions") or []
        ),
        "share_privacy_runtime": (
            dict(share_privacy_runtime)
            if isinstance(share_privacy_runtime, dict)
            else share_privacy_runtime_status(session)
        ),
        "policy": {
            **_normalize_session_policy(session.get("policy")),
            "capture_mode": session["capture_mode"],
            "processing_mode": session["processing_mode"],
            "assistance_mode": session["assistance_mode"],
            "consent_ack": bool(session["consent_ack"]),
            "retention_policy": dict(space.get("retention_policy") or RETENTION_PRESETS["STANDARD"]),
        },
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    row = {
        "id": store.new_id("cpack_"),
        "session_id": session_id,
        "space_id": space["id"],
        "payload": payload,
        "digest": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "created_at": store.now(),
    }
    store.insert("conversation_session_pack", row)
    store.update("conversation_session", session_id, {"pack_id": row["id"], "updated_at": store.now()})
    return store.get("conversation_session_pack", row["id"]) or row


def start_session(
    session_id: str,
    *,
    share_privacy_runtime_proof: str = "",
) -> dict[str, Any]:
    before = require_session(session_id)
    expected_fingerprint = str((before.get("state") or {}).get("preflight_context_fingerprint") or "")
    check = preflight(session_id, record_fingerprint=False)
    if check["blockers"]:
        raise ValueError(check["blockers"][0]["message"])
    if expected_fingerprint and expected_fingerprint != check["context_fingerprint"]:
        raise ValueError("本场上下文自上次 Preflight 后已变化；请重新检查 Session Pack Preview 后再开始")
    session = check["session"]
    if session["status"] == "ENDED":
        raise ValueError("已结束的会话不能重新开始")
    share_runtime = share_privacy_runtime_status(session, share_privacy_runtime_proof)
    if share_runtime["requested"] == "PRIVATE_OVERLAY" and not share_runtime["verified"]:
        raise ValueError(
            "PRIVATE_OVERLAY 需要桌面端在开始前确认 Electron content protection 已启用；当前 runtime proof 缺失或无效。"
        )
    pack = freeze_pack(session_id, share_privacy_runtime=share_runtime)
    ts = store.now()
    state = dict(session.get("state") or {})
    frozen_brief = ((pack.get("payload") or {}).get("session_brief") or {})
    state["open_threads"] = [
        str(thread.get("id") or "")
        for thread in (frozen_brief.get("open_threads") or [])
        if thread.get("id")
    ]
    store.update("conversation_session", session_id, {
        "status": "ACTIVE",
        "started_at": session.get("started_at") or ts,
        "state": state,
        "updated_at": ts,
    })
    return {"session": require_session(session_id), "pack": pack}


def update_session(session_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    session = require_session(session_id)
    clean: dict[str, Any] = {}
    if "assistance_mode" in patch:
        clean["assistance_mode"] = _require_choice(str(patch["assistance_mode"]), ASSISTANCE_MODES, "帮助方式")
    if "consent_ack" in patch and session["status"] == "UPCOMING":
        clean["consent_ack"] = bool(patch["consent_ack"])
    if "capture_mode" in patch and session["status"] == "UPCOMING":
        clean["capture_mode"] = _require_choice(str(patch["capture_mode"]), CAPTURE_MODES, "记录方式")
    if "processing_mode" in patch and session["status"] == "UPCOMING":
        clean["processing_mode"] = _require_choice(str(patch["processing_mode"]), PROCESSING_MODES, "处理方式")
    if "policy" in patch and session["status"] == "UPCOMING":
        clean["policy"] = _normalize_session_policy(patch.get("policy"), session.get("policy"))
    if clean:
        clean["updated_at"] = store.now()
        store.update("conversation_session", session_id, clean)
    return require_session(session_id)


def _frozen_pack_payload(session: dict[str, Any]) -> dict[str, Any]:
    pack_id = str(session.get("pack_id") or "")
    row = store.get("conversation_session_pack", pack_id) if pack_id else None
    if row is None:
        rows = store.select(
            "conversation_session_pack",
            where="session_id = ?",
            params=(session["id"],),
            order="created_at DESC",
            limit=1,
        )
        row = rows[0] if rows else None
    payload = (row or {}).get("payload") if row else None
    return dict(payload) if isinstance(payload, dict) else {}


def conversation_state(session_id: str) -> dict[str, Any]:
    """Derived Conversation State read model; never a second truth store."""
    session = require_session(session_id)
    raw = dict(session.get("state") or {})
    status = str(session.get("status") or "")
    phase = "PREPARE" if status == "UPCOMING" else "PARTICIPATE" if status == "ACTIVE" else "CONTINUE" if status == "ENDED" else status
    items = store.select(
        "conversation_item",
        where="session_id = ?",
        params=(session_id,),
        order="created_at ASC",
        limit=200,
    )
    threads = store.select(
        "conversation_open_thread",
        where="space_id = ? AND status = 'OPEN'",
        params=(session["space_id"],),
        order="created_at DESC",
        limit=100,
    )
    return {
        "phase": phase,
        "current_topic": str(raw.get("current_topic") or ""),
        "user_speaking": bool(raw.get("user_speaking", False)),
        "direct_question_pending": bool(raw.get("direct_question_pending", False)),
        "audience_context": dict(raw.get("audience_context") or {}),
        "items": [
            {
                "id": item["id"],
                "type": item["type"],
                "state": item["state"],
                "title": item["title"],
                "review_status": item["review_status"],
            }
            for item in items
        ],
        "open_threads": [
            {"id": thread["id"], "kind": thread["kind"], "text": thread["text"], "owner_id": thread.get("owner_id") or ""}
            for thread in threads
        ],
        "last_guidance_id": str(raw.get("last_guidance_id") or ""),
    }


def session_context(session_id: str) -> dict[str, Any]:
    """Small Live read model derived from the frozen Session Pack.

    It deliberately omits full source bodies; Manual Ask can query them through
    the backend without dumping the whole private pack into the renderer.
    """
    session = require_session(session_id)
    payload = _frozen_pack_payload(session)
    pack_row = store.get("conversation_session_pack", str(session.get("pack_id") or "")) if session.get("pack_id") else None
    sources = [
        {
            "material_id": source.get("material_id") or "",
            "version_id": source.get("version_id") or "",
            "title": source.get("title") or "",
            "kind": source.get("kind") or "",
            "usage": source.get("usage") or "",
            "content_hash": source.get("content_hash") or "",
            "is_personal_evidence": bool(source.get("is_personal_evidence")),
        }
        for source in payload.get("sources") or []
    ]
    notes = [
        {"id": note.get("id") or "", "title": note.get("title") or ""}
        for note in payload.get("quick_notes") or []
    ]
    participants = []
    for p in payload.get("participants") or []:
        counterparty = p.get("counterparty_state") or {}
        if not isinstance(counterparty, dict):
            counterparty = {}
        participants.append({
            "id": p.get("id") or "",
            "display_name": p.get("display_name") or "",
            "role": p.get("role") or "",
            "organization": p.get("organization") or "",
            "counterparty_state": {
                "known_explicit": dict(counterparty.get("known_explicit") or {}),
                "source_refs": list(counterparty.get("source_refs") or []),
                "confidence": float(counterparty.get("confidence") or 0.0),
                "temporary_inferences": list(counterparty.get("temporary_inferences") or []),
                "unknown": list(counterparty.get("unknown") or []),
            },
        })
    return {
        "session_id": session_id,
        "conversation_state": conversation_state(session_id),
        "space": payload.get("space") or {"id": session["space_id"]},
        "brief": payload.get("session_brief") or {},
        "profile_playbook": payload.get("profile_playbook") or profile_playbook((payload.get("space") or {}).get("profile") or ""),
        "sources": sources,
        "quick_notes": notes,
        "participants": participants,
        "expression_profile": payload.get("expression_profile") or {},
        "resolved_ai_behavior": payload.get("resolved_ai_behavior") or resolved_ai_behavior(_normalize_session_policy(session.get("policy"))),
        "processing_runtime": payload.get("processing_runtime") or {},
        "screen_runtime": payload.get("screen_runtime") or {},
        "connector_runtime": payload.get("connector_runtime") or conversation_connectors.resolve_read_permissions(
            _normalize_session_policy(session.get("policy")).get("connector_permissions") or []
        ),
        "share_privacy_runtime": payload.get("share_privacy_runtime") or share_privacy_runtime_status(session),
        "policy": payload.get("policy") or _normalize_session_policy(session.get("policy")),
        "pack_digest": str((pack_row or {}).get("digest") or ""),
    }


def screen_context(session_id: str, limit: int = 20) -> list[dict[str, Any]]:
    require_session(session_id)
    return conversation_screen.list_context(session_id, limit)


def capture_screen_context(session_id: str, *, region: str = "configured") -> dict[str, Any]:
    session = require_session(session_id)
    payload = _frozen_pack_payload(session)
    frozen_runtime = dict(payload.get("screen_runtime") or {})
    return conversation_screen.capture_manual(
        session,
        region=region,
        frozen_runtime=frozen_runtime,
    )


def screen_auto_status(session_id: str) -> dict[str, Any]:
    require_session(session_id)
    return conversation_screen.auto_status(session_id)


def start_auto_screen_context(
    session_id: str,
    *,
    interval_seconds: int = 30,
    region: str = "configured",
) -> dict[str, Any]:
    session = require_session(session_id)
    payload = _frozen_pack_payload(session)
    frozen_runtime = dict(payload.get("screen_runtime") or {})
    return conversation_screen.start_auto(
        session,
        interval_seconds=interval_seconds,
        region=region,
        frozen_runtime=frozen_runtime,
    )


def pause_auto_screen_context(session_id: str) -> dict[str, Any]:
    require_session(session_id)
    return conversation_screen.pause_auto(session_id)


def resume_auto_screen_context(session_id: str) -> dict[str, Any]:
    require_session(session_id)
    return conversation_screen.resume_auto(session_id)


def stop_auto_screen_context(session_id: str) -> dict[str, Any]:
    require_session(session_id)
    return conversation_screen.stop_auto(session_id)


def _query_tokens(text: str) -> set[str]:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return set()
    for ch in "？?，,。；;：:/\\|()（）[]【】":
        normalized = normalized.replace(ch, " ")
    tokens = {x for x in normalized.split() if len(x) >= 2}
    if len(normalized.replace(" ", "")) >= 2:
        tokens.add(normalized.replace(" ", ""))
    return tokens


def _text_match_score(question: str, haystack: str) -> int:
    q = str(question or "").strip().lower()
    h = str(haystack or "").lower()
    if not q or not h:
        return 0

    q_tokens = _query_tokens(q)
    # Distinctive alphanumeric tokens such as 50x, v2, sha256, Q4 or 30%
    # carry factual identity. Only use *real segmented tokens* here: _query_tokens
    # also adds a compact no-space token for CJK substring matching, and treating
    # that synthetic token as a required numeric identity would incorrectly
    # reject legitimate queries such as "offline migration v2".
    segmented = q
    for ch in "？?，,。；;：:/\\|()（）[]【】":
        segmented = segmented.replace(ch, " ")
    base_tokens = {x for x in segmented.split() if len(x) >= 2}
    distinctive = {
        token for token in base_tokens
        if any(ch.isdigit() for ch in token)
    }
    if distinctive and any(token not in h for token in distinctive):
        return 0

    score = 4 if q in h else 0
    matched = 0
    for token in q_tokens:
        if token and token in h:
            score += 1
            matched += 1

    # For multi-token questions without an exact phrase, require more than one
    # meaningful overlap. This keeps Manual Ask precision-biased and avoids a
    # single generic word turning unrelated frozen context into "grounded".
    if not score:
        return 0
    if q not in h and len(q_tokens) >= 2 and matched < 2:
        return 0
    return score


def ask(session_id: str, question: str) -> dict[str, Any]:
    """Deterministic, source-aware Manual Ask over this session's frozen context.

    Ranking intentionally distinguishes authority:
    confirmed cross-session state > frozen Ready sources > frozen Quick Notes >
    current-session transcript.  Source-backed context is not automatically
    upgraded into confirmed truth.
    """
    session = require_session(session_id)
    policy = _normalize_session_policy(session.get("policy"))
    if policy["ai_assistance"] == "AI_FORBIDDEN":
        raise ValueError("本场 AI Assistance 已禁用；Manual Ask 不可用")
    question = str(question or "").strip()
    if not question:
        raise ValueError("问题不能为空")

    ranked: list[tuple[int, float, dict[str, Any]]] = []
    pack = _frozen_pack_payload(session)

    # 1) Confirmed state: highest authority and strongest ranking boost.
    for item in pack.get("confirmed_items") or _confirmed_context_items(session["space_id"]):
        haystack = " ".join([
            str(item.get("title") or ""),
            str(item.get("detail") or ""),
            str(item.get("source_excerpt") or ""),
        ])
        lexical = _text_match_score(question, haystack)
        if lexical:
            ranked.append((lexical + 8, float(item.get("updated_at") or 0), {
                "id": item.get("id") or "",
                "kind": "CONFIRMED_ITEM",
                "authority": "CONFIRMED_TRUTH",
                "title": str(item.get("title") or "")[:1000],
                "excerpt": str(item.get("source_excerpt") or item.get("detail") or item.get("title") or "")[:500],
                "item_type": item.get("type") or "",
                "state": item.get("state") or "",
                "review_status": item.get("review_status") or "",
                "source_refs": list(item.get("source_refs") or []),
            }))

    # 2) Ready source versions frozen when the session started.
    for source in pack.get("sources") or []:
        text_value = str(source.get("text") or "")
        haystack = " ".join([str(source.get("title") or ""), text_value])
        lexical = _text_match_score(question, haystack)
        if lexical:
            q_lower = question.lower()
            pos = text_value.lower().find(q_lower)
            excerpt_start = max(0, pos - 120) if pos >= 0 else 0
            excerpt = text_value[excerpt_start:excerpt_start + 500]
            ranked.append((lexical + 5, 0.0, {
                "id": str(source.get("material_id") or source.get("version_id") or ""),
                "kind": "FROZEN_SOURCE",
                "authority": "PERSONAL_EVIDENCE" if source.get("is_personal_evidence") else "REFERENCE_SOURCE",
                "title": str(source.get("title") or "本场来源")[:300],
                "excerpt": excerpt,
                "item_type": "",
                "state": "",
                "review_status": "",
                "source_refs": [{
                    "kind": "DOCUMENT",
                    "id": str(source.get("material_id") or ""),
                    "version_id": str(source.get("version_id") or ""),
                    "content_hash": str(source.get("content_hash") or ""),
                    "visibility": "PRIVATE",
                }],
            }))

    # 3) User-authored frozen notes are usable context, but explicitly not evidence.
    for note in pack.get("quick_notes") or []:
        haystack = " ".join([str(note.get("title") or ""), str(note.get("content") or "")])
        lexical = _text_match_score(question, haystack)
        if lexical:
            ranked.append((lexical + 3, 0.0, {
                "id": str(note.get("id") or ""),
                "kind": "QUICK_NOTE",
                "authority": "USER_NOTE_NOT_EVIDENCE",
                "title": str(note.get("title") or "Quick Note")[:300],
                "excerpt": str(note.get("content") or "")[:500],
                "item_type": "",
                "state": "",
                "review_status": "",
                "source_refs": [{"kind": "QUICK_NOTE", "id": str(note.get("id") or ""), "visibility": "PRIVATE"}],
            }))

    # 4) Manual screen observations are source-aware but never confirmed truth.
    for observation in conversation_screen.list_context(session_id, limit=40):
        lexical = _text_match_score(question, str(observation.get("text") or ""))
        if lexical:
            ranked.append((lexical + 2, float(observation.get("created_at") or 0), {
                "id": observation.get("id") or "",
                "kind": "SCREEN_CONTEXT",
                "authority": "OBSERVED_NOT_CONFIRMED",
                "title": "本场屏幕观察",
                "excerpt": str(observation.get("text") or "")[:500],
                "item_type": "",
                "state": "",
                "review_status": "",
                "source_refs": [{
                    "kind": "SCREEN_CONTEXT",
                    "id": observation.get("id") or "",
                    "session_id": session_id,
                    "timestamp": observation.get("created_at"),
                    "image_hash": observation.get("image_hash") or "",
                    "vision_model": observation.get("vision_model") or "",
                    "vision_route": observation.get("vision_route") or "",
                    "visibility": "PRIVATE",
                }],
            }))

    # 5) The current-session transcript supports catch-up, but remains observation.
    transcript = store.select(
        "conversation_transcript_segment",
        where="session_id = ?",
        params=(session_id,),
        order="created_at DESC",
        limit=120,
    )
    for seg in transcript:
        lexical = _text_match_score(question, str(seg.get("text") or ""))
        if lexical:
            ranked.append((lexical + 1, float(seg.get("created_at") or 0), {
                "id": seg.get("id") or "",
                "kind": "TRANSCRIPT_SEGMENT",
                "authority": "OBSERVED_NOT_CONFIRMED",
                "title": "本场转写",
                "excerpt": str(seg.get("text") or "")[:500],
                "item_type": "",
                "state": "",
                "review_status": "",
                "source_refs": [{
                    "kind": "TRANSCRIPT_SEGMENT",
                    "id": seg.get("id") or "",
                    "session_id": session_id,
                    "timestamp": seg.get("created_at"),
                    "visibility": "PRIVATE",
                }],
            }))

    ranked.sort(key=lambda pair: (pair[0], pair[1]), reverse=True)
    matches = [match for _, _, match in ranked[:6]]
    if not matches:
        return {
            "answer": "没有在本场冻结来源、已确认历史、屏幕观察或当前转写中找到足够直接的可追溯内容。",
            "matches": [],
            "grounded": False,
            "truth_confirmed": False,
        }

    top = matches[0]
    prefix = {
        "CONFIRMED_TRUTH": "已确认历史",
        "PERSONAL_EVIDENCE": "本场个人证据",
        "REFERENCE_SOURCE": "本场参考来源",
        "USER_NOTE_NOT_EVIDENCE": "本场 Quick Note",
        "OBSERVED_NOT_CONFIRMED": "本场转写观察",
    }.get(top["authority"], "可追溯来源")
    answer = f"{prefix}：{top['title']}"
    if top.get("excerpt") and top["excerpt"] != top["title"]:
        answer += f" — {top['excerpt']}"
    return {
        "answer": answer[:1800],
        "matches": matches,
        "grounded": True,
        "truth_confirmed": top["authority"] == "CONFIRMED_TRUTH",
    }

def _recall_for_topic(space_id: str, topic: str) -> Optional[dict[str, Any]]:
    """Small deterministic retrieval fallback for local/offline runtime."""
    topic = str(topic or "").strip().lower()
    if not topic:
        return None
    tokens = {x for x in topic.replace("/", " ").replace("-", " ").split() if len(x) >= 2}
    if not tokens:
        tokens = {topic}
    best: tuple[int, dict[str, Any]] | None = None
    for item in _confirmed_context_items(space_id):
        haystack = " ".join([str(item.get("title") or ""), str(item.get("detail") or ""), str(item.get("source_excerpt") or "")]).lower()
        score = sum(1 for token in tokens if token in haystack)
        if score and (best is None or score > best[0]):
            best = (score, item)
    return best[1] if best else None


OPEN_THREAD_ITEM_TYPES = {"OpenQuestion", "Risk", "Objection"}
THREAD_CONFIRMED_REVIEW = {"USER_CONFIRMED", "USER_EDITED", "SOURCE_CONFIRMED"}


def _thread_for_item(item: dict[str, Any]) -> Optional[dict[str, Any]]:
    # Scan the item's own session, not an arbitrary latest-500 window across
    # the entire Space. A long-lived Space must never re-create an older Thread
    # just because 500 newer projections have been stored.
    for thread in store.select(
        "conversation_open_thread",
        where="space_id = ? AND session_id = ?",
        params=(item["space_id"], item["session_id"]),
        order="created_at DESC",
    ):
        for ref in thread.get("source_refs") or []:
            if str(ref.get("kind") or "") == "CONVERSATION_ITEM" and str(ref.get("id") or "") == item["id"]:
                return thread
    return None


def _sync_open_thread(item: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Project reviewed unresolved items into the longitudinal Open Thread view.

    AI_EXTRACTED candidates never become persistent threads by themselves.
    The Conversation Item remains the truth object; the thread is only a
    continuity/read-model projection with a provenance edge back to that item.
    """
    if item.get("type") not in OPEN_THREAD_ITEM_TYPES:
        return None

    existing = _thread_for_item(item)
    active = (
        item.get("review_status") in THREAD_CONFIRMED_REVIEW
        and item.get("state") not in {"DONE", "SUPERSEDED", "UNKNOWN"}
    )
    now = store.now()
    item_ref = {
        "kind": "CONVERSATION_ITEM",
        "id": item["id"],
        "session_id": item.get("session_id") or "",
        "visibility": "PRIVATE",
    }
    source_refs = [item_ref, *list(item.get("source_refs") or [])]

    if active:
        if existing:
            store.update("conversation_open_thread", existing["id"], {
                "kind": item["type"],
                "text": item["title"],
                "owner_id": item.get("owner_id") or "",
                "status": "OPEN",
                "source_refs": source_refs,
                "resolved_at": None,
            })
            return store.get("conversation_open_thread", existing["id"])
        row = {
            "id": store.new_id("cot_"),
            "space_id": item["space_id"],
            "session_id": item.get("session_id") or "",
            "kind": item["type"],
            "text": item["title"],
            "owner_id": item.get("owner_id") or "",
            "status": "OPEN",
            "source_refs": source_refs,
            "created_at": now,
            "resolved_at": None,
        }
        store.insert("conversation_open_thread", row)
        return store.get("conversation_open_thread", row["id"])

    if existing and existing.get("status") == "OPEN":
        store.update("conversation_open_thread", existing["id"], {
            "status": "RESOLVED",
            "resolved_at": now,
            "text": item["title"],
            "owner_id": item.get("owner_id") or "",
            "source_refs": source_refs,
        })
        return store.get("conversation_open_thread", existing["id"])
    return existing


def resolve_open_thread(thread_id: str) -> dict[str, Any]:
    thread = store.get("conversation_open_thread", thread_id)
    if thread is None:
        raise ValueError("Open Thread 不存在")
    if thread.get("status") != "OPEN":
        return thread

    item_id = ""
    for ref in thread.get("source_refs") or []:
        if str(ref.get("kind") or "") == "CONVERSATION_ITEM":
            item_id = str(ref.get("id") or "")
            break
    if not item_id:
        raise ValueError("Open Thread 缺少对应 Conversation Item provenance，不能直接关闭")

    item = require_item(item_id)
    if item.get("space_id") != thread.get("space_id"):
        raise ValueError("Open Thread provenance 与当前 Space 不一致")
    review_item(item_id, "RESOLVE")
    refreshed = store.get("conversation_open_thread", thread_id)
    if refreshed is None:
        raise ValueError("Open Thread 关闭后读取失败")
    return refreshed


def add_item(
    session_id: str,
    *,
    item_type: str,
    title: str,
    state: str = "PROPOSED",
    detail: str = "",
    owner_id: str = "",
    speaker_id: str = "",
    due_at: str = "",
    time_semantics: Optional[dict[str, Any]] = None,
    source_refs: Optional[list[dict[str, Any]]] = None,
    source_excerpt: str = "",
    confidence: float = 0.0,
    epistemic_status: str = "UNKNOWN",
    review_status: str = "AI_EXTRACTED",
    supersedes_id: str = "",
) -> dict[str, Any]:
    session = require_session(session_id)
    item_type = item_type if item_type in ITEM_TYPES else item_type.title()
    if item_type not in ITEM_TYPES:
        raise ValueError(f"事项类型不支持：{item_type}")
    state = _require_choice(state, ITEM_STATES, "事项状态")
    review_status = _require_choice(review_status, REVIEW_STATUSES, "审核状态")
    epistemic_status = _require_choice(epistemic_status, EPISTEMIC_STATUSES, "认知状态")
    refs = list(source_refs or [])
    temporal = _normalize_time_semantics(
        time_semantics,
        original_text=(title if item_type == "Deadline" else ""),
        normalized_datetime=str(due_at or ""),
    )
    if item_type == "Deadline" and not refs:
        raise ValueError("Deadline 必须带来源")
    if state == "AGREED" and not (refs and review_status in {"USER_CONFIRMED", "USER_EDITED", "SOURCE_CONFIRMED"}):
        raise ValueError("Decision 升级为 AGREED 需要来源与明确确认")
    if state == "COMMITTED" and not (owner_id and refs and review_status in {"USER_CONFIRMED", "USER_EDITED", "SOURCE_CONFIRMED"}):
        raise ValueError("Commitment 升级为 COMMITTED 需要 owner、来源与明确确认")
    if item_type in {"Commitment", "Task"} and state == "COMMITTED" and temporal["original_text"] and temporal["ambiguity"] != "NOT_APPLICABLE" and not _time_semantics_resolved(temporal):
        raise ValueError("Commitment 的时间仍有歧义；写入 COMMITTED 前请补 normalized datetime 与 timezone")
    if item_type == "Deadline" and state in {"COMMITTED", "DONE"}:
        if review_status not in {"USER_CONFIRMED", "USER_EDITED", "SOURCE_CONFIRMED"} or not _time_semantics_resolved(temporal):
            raise ValueError("Deadline 写入长期状态前需要明确 review、normalized datetime 与 timezone")
    title = str(title or "").strip()
    if not title:
        raise ValueError("事项内容不能为空")
    ts = store.now()
    row = {
        "id": store.new_id("ci_"),
        "space_id": session["space_id"],
        "session_id": session_id,
        "type": item_type,
        "state": state,
        "title": title[:1000],
        "detail": str(detail or "")[:5000],
        "speaker_id": str(speaker_id or "")[:120],
        "owner_id": str(owner_id or "")[:120],
        "due_at": str(due_at or temporal.get("normalized_datetime") or "")[:120],
        "time_semantics": temporal,
        "source_refs": refs,
        "source_excerpt": str(source_excerpt or "")[:3000],
        "confidence": max(0.0, min(1.0, float(confidence or 0.0))),
        "epistemic_status": epistemic_status,
        "review_status": review_status,
        "supersedes_id": str(supersedes_id or "")[:120],
        "visibility": "PRIVATE",
        "created_at": ts,
        "updated_at": ts,
    }
    store.insert("conversation_item", row)
    saved = require_item(row["id"])
    _sync_open_thread(saved)
    return saved


def review_item(item_id: str, action: str, patch: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    item = require_item(item_id)
    action = str(action or "").upper()
    patch = dict(patch or {})
    update: dict[str, Any] = {}
    temporal = _normalize_time_semantics(
        patch.get("time_semantics") if isinstance(patch.get("time_semantics"), dict) else item.get("time_semantics"),
        original_text=str(item.get("title") or ""),
        normalized_datetime=str(patch.get("due_at") or item.get("due_at") or ""),
    )
    if "time_semantics" in patch or "due_at" in patch:
        update["time_semantics"] = temporal
        update["due_at"] = temporal.get("normalized_datetime") or str(patch.get("due_at") or item.get("due_at") or "")
    if action == "CONFIRM":
        update["review_status"] = "USER_CONFIRMED"
        if item["type"] == "Decision" and item["state"] == "PROPOSED":
            if not item.get("source_refs"):
                raise ValueError("Decision 确认前需要来源")
            update["state"] = "AGREED"
        elif item["type"] in {"Commitment", "Task"} and item["state"] == "PROPOSED":
            owner = str(patch.get("owner_id") or item.get("owner_id") or "")
            if not owner or not item.get("source_refs"):
                raise ValueError("Commitment 确认前需要 owner 与来源")
            if temporal["original_text"] and temporal["ambiguity"] != "NOT_APPLICABLE" and not _time_semantics_resolved(temporal):
                raise ValueError("Commitment 的时间仍有歧义；确认前请补 normalized datetime 与 timezone")
            update["owner_id"] = owner
            update["state"] = "COMMITTED"
        elif item["type"] == "Deadline" and item["state"] == "PROPOSED":
            if not item.get("source_refs"):
                raise ValueError("Deadline 确认前需要来源")
            if not _time_semantics_resolved(temporal):
                raise ValueError("Deadline 时间仍有歧义；确认前请补 normalized datetime 与 timezone")
            update["state"] = "COMMITTED"
    elif action == "EDIT":
        for key in ("title", "detail", "owner_id", "speaker_id", "source_excerpt"):
            if key in patch:
                update[key] = patch[key]
        if "time_semantics" in patch or "due_at" in patch:
            update["time_semantics"] = temporal
            update["due_at"] = temporal.get("normalized_datetime") or str(patch.get("due_at") or "")
        update["review_status"] = "USER_EDITED"
    elif action == "REJECT":
        update.update({"review_status": "USER_REJECTED", "state": "UNKNOWN"})
    elif action == "DONE":
        if item["state"] != "COMMITTED":
            raise ValueError("只有 COMMITTED 事项才能标记 DONE")
        update["state"] = "DONE"
        update["review_status"] = "USER_CONFIRMED"
    elif action == "RESOLVE":
        if item["type"] not in OPEN_THREAD_ITEM_TYPES:
            raise ValueError("只有 OpenQuestion / Risk / Objection 可以标记已解决")
        if item["review_status"] not in THREAD_CONFIRMED_REVIEW:
            raise ValueError("未确认事项不能直接标记已解决")
        update["state"] = "DONE"
        update["review_status"] = "USER_CONFIRMED"
    elif action == "SUPERSEDE":
        if item["type"] != "Decision":
            raise ValueError("只有 Decision 可以建立 supersession 链")
        if item["state"] != "PROPOSED":
            raise ValueError("只有新的 Proposed Decision 可以确认并替代旧 Decision")
        old_id = str(patch.get("supersedes_id") or "").strip()
        if not old_id or old_id == item_id:
            raise ValueError("必须选择一个不同的旧 Decision")
        old = require_item(old_id)
        if old["type"] != "Decision" or old["space_id"] != item["space_id"]:
            raise ValueError("只能替代同一 Conversation Space 中的 Decision")
        if old["state"] != "AGREED":
            raise ValueError("只能替代当前仍为 AGREED 的旧 Decision")
        if not item.get("source_refs"):
            raise ValueError("新 Decision 确认并替代旧 Decision 前需要来源")
        now = store.now()
        # Direction is explicit: NEW.supersedes_id -> OLD.id, while OLD becomes
        # SUPERSEDED. The old Decision remains queryable for provenance/history.
        store.update("conversation_item", old_id, {
            "state": "SUPERSEDED",
            "updated_at": now,
        })
        update["state"] = "AGREED"
        update["review_status"] = "USER_CONFIRMED"
        update["supersedes_id"] = old_id
    else:
        raise ValueError("审核动作不支持")
    update["updated_at"] = store.now()
    store.update("conversation_item", item_id, update)
    saved = require_item(item_id)
    _sync_open_thread(saved)
    return saved


def _candidate_kinds_from_sentence(sentence: str) -> list[str]:
    text = str(sentence or "").strip()
    lower = text.lower()
    kinds: list[str] = []

    question_markers = (
        "为什么", "怎么", "如何", "是否", "能不能", "有没有", "谁", "什么时候",
        "哪一个", "哪个", "what ", "why ", "how ", "who ", "when ", "which ",
    )
    if (
        "?" in text or "？" in text
        or any(lower.startswith(marker) for marker in question_markers)
    ):
        kinds.append("OpenQuestion")

    decision_markers = (
        "决定", "就按", "确定采用", "确认采用", "最终采用", "we decided",
        "we'll use", "we will use", "go with ", "decision is ",
    )
    if any(marker in lower for marker in decision_markers):
        kinds.append("Decision")

    commitment_markers = (
        "我来", "我负责", "我会", "我去", "我今天", "我明天",
        "i'll ", "i will ", "i can own ", "i'll own ",
    )
    if any(marker in lower for marker in commitment_markers):
        kinds.append("Commitment")

    deadline_markers = (
        "截止", "之前完成", "前完成", "周一前", "周二前", "周三前", "周四前", "周五前", "周六前", "周日前",
        "deadline", " by monday", " by tuesday", " by wednesday", " by thursday", " by friday",
    )
    if any(marker in lower for marker in deadline_markers):
        kinds.append("Deadline")

    risk_markers = (
        "明确风险", "风险是", "主要风险", "blocker", "is blocked", "blocking issue",
    )
    if any(marker in lower for marker in risk_markers):
        kinds.append("Risk")

    # One sentence may legitimately encode a commitment plus deadline. Preserve
    # distinct candidate types, but do not duplicate a type.
    return list(dict.fromkeys(kinds))


def extract_transcript_candidates(session_id: str) -> list[dict[str, Any]]:
    """Extract conservative review-only candidates from final transcript.

    Current beta uses deterministic explicit-language rules so inference stays
    local and auditable. Future model extraction may replace/augment this, but
    it must preserve the same PROPOSED + AI_EXTRACTED review boundary.
    """
    session = require_session(session_id)
    policy = _normalize_session_policy(session.get("policy"))
    if policy["ai_assistance"] not in {"AI_ALLOWED", "AI_EXPECTED"}:
        return []

    segments = store.select(
        "conversation_transcript_segment",
        where="session_id = ? AND is_final = 1",
        params=(session_id,),
        order="created_at ASC",
        limit=1000,
    )
    existing = {
        (str(item.get("type") or ""), str(item.get("title") or "").strip())
        for item in store.select(
            "conversation_item",
            where="session_id = ?",
            params=(session_id,),
            order="created_at ASC",
        )
    }
    created: list[dict[str, Any]] = []

    for seg in segments:
        raw = str(seg.get("text") or "").strip()
        if not raw:
            continue
        sentences = [
            part.strip(" \t\r\n。！？!?")
            for part in re.split(r"(?<=[。！？!?])\s*|\n+", raw)
            if part.strip()
        ]
        for sentence in sentences[:20]:
            if len(sentence) < 4:
                continue
            for item_type in _candidate_kinds_from_sentence(sentence):
                key = (item_type, sentence[:1000])
                if key in existing:
                    continue
                ref = {
                    "kind": "TRANSCRIPT_SEGMENT",
                    "id": seg.get("id") or "",
                    "session_id": session_id,
                    "timestamp": seg.get("created_at"),
                    "channel": seg.get("channel") or "",
                    "visibility": "PRIVATE",
                    "excerpt": sentence[:500],
                }
                owner_id = ""
                if item_type == "Commitment" and str(seg.get("channel") or "").upper() == "SELF_MIC":
                    owner_id = "me"
                saved = add_item(
                    session_id,
                    item_type=item_type,
                    title=sentence[:1000],
                    state="PROPOSED",
                    owner_id=owner_id,
                    time_semantics=({
                        "original_text": sentence[:1000],
                        "normalized_datetime": "",
                        "timezone": "",
                        "ambiguity": "AMBIGUOUS",
                    } if item_type == "Deadline" else None),
                    source_refs=[ref],
                    source_excerpt=sentence[:500],
                    confidence=0.85,
                    epistemic_status="INFERRED",
                    review_status="AI_EXTRACTED",
                )
                created.append(saved)
                existing.add(key)
    return created


def continue_summary(session_id: str) -> dict[str, Any]:
    session = require_session(session_id)
    items = store.select("conversation_item", where="session_id = ?", params=(session_id,), order="created_at ASC")
    decisions = [i for i in items if i["type"] == "Decision" and i["state"] == "AGREED"]
    commitments = [i for i in items if i["type"] in {"Commitment", "Task"} and i["state"] in {"COMMITTED", "DONE"}]
    open_questions = [i for i in items if i["type"] == "OpenQuestion" and i["state"] not in {"DONE", "SUPERSEDED", "UNKNOWN"}]
    reviewed_open_questions = [i for i in open_questions if i["review_status"] in THREAD_CONFIRMED_REVIEW]
    candidates = [i for i in items if i["review_status"] == "AI_EXTRACTED"]
    what_changed = [
        i for i in items
        if i["review_status"] in {"USER_CONFIRMED", "USER_EDITED", "SOURCE_CONFIRMED"}
        and i["state"] in {"AGREED", "COMMITTED", "DONE", "SUPERSEDED"}
    ]
    pins = store.select(
        "conversation_guidance_event",
        where="session_id = ? AND user_action = 'PINNED'",
        params=(session_id,),
        order="created_at ASC",
    )
    next_focus = None
    if reviewed_open_questions:
        next_focus = {"kind": "OPEN_QUESTION", "title": reviewed_open_questions[0]["title"], "source_ref": reviewed_open_questions[0]["id"]}
    else:
        space_threads = store.select(
            "conversation_open_thread",
            where="space_id = ? AND status = 'OPEN'",
            params=(session["space_id"],),
            order="created_at DESC",
            limit=1,
        )
        if space_threads:
            next_focus = {"kind": "OPEN_THREAD", "title": space_threads[0]["text"], "source_ref": space_threads[0]["id"]}
        else:
            owed = [i for i in commitments if i["state"] == "COMMITTED" and i.get("owner_id") in {"me", "SELF", "我"}]
            if owed:
                next_focus = {"kind": "COMMITMENT", "title": owed[0]["title"], "source_ref": owed[0]["id"]}
    return {
        "session": session,
        "profile_outcome": _profile_outcome_evidence(session, items),
        "decisions": decisions,
        "commitments": commitments,
        "open_questions": reviewed_open_questions,
        "candidates": candidates,
        "what_changed": what_changed,
        "pins": pins,
        "next_focus": next_focus,
        "review_required": len(candidates),
    }


def end_session(session_id: str) -> dict[str, Any]:
    session = require_session(session_id)
    ts = store.now()
    if session["status"] != "ENDED":
        # Candidate extraction runs while transcript/source provenance is still
        # available. It is idempotent and never upgrades truth state.
        extract_transcript_candidates(session_id)
        store.update("conversation_session", session_id, {"status": "ENDED", "ended_at": ts, "updated_at": ts})
    try:
        from services import coach as human_coach
        human_coach.registry.revoke_for_target(session_id, session_kind="conversation")
    except Exception:
        pass
    return continue_summary(session_id)


def _score(body: dict[str, Any]) -> OpportunityScore:
    keys = {
        "relevance", "novelty", "provenance_strength", "role_relevance", "goal_relevance", "urgency",
        "decision_impact", "interruption_cost", "already_mentioned", "uncertainty", "social_risk",
        "stale_context_risk",
    }
    values = {key: float(body.get(key) or 0.0) for key in keys}

    # Stakeholder-aware expression uses only explicit user-provided context.
    # Presence of a known audience modestly raises role relevance; textual
    # overlap raises it further. We never infer hidden intent, emotion or
    # personality from the other party.
    audience_parts = [
        str(body.get("audience_role") or ""),
        str(body.get("audience_priority") or ""),
        str(body.get("audience_concern") or ""),
        str(body.get("decision_authority") or ""),
        str(body.get("relationship_context") or ""),
    ]
    audience_text = " ".join(part for part in audience_parts if part).strip().lower()
    candidate_text = " ".join([
        str(body.get("candidate_text") or ""),
        str(body.get("current_topic") or ""),
        str(body.get("direct_question") or ""),
    ]).lower()
    if audience_text:
        values["role_relevance"] = max(values["role_relevance"], 0.5)
        tokens = {token for token in audience_text.replace("/", " ").replace("，", " ").split() if len(token) >= 2}
        if any(token in candidate_text for token in tokens):
            values["role_relevance"] = max(values["role_relevance"], 1.0)
    return OpportunityScore(**values)


def _expression_plan_for_guidance(event: dict[str, Any]) -> dict[str, Any]:
    """Derive the user-facing Expression Plan from the persisted Guidance event.

    Guidance remains the only persisted realtime event truth. This read model
    explains how the event should render, whom it targets, what sources justify
    it, and why a SILENT decision stayed silent.
    """
    session = require_session(str(event.get("session_id") or ""))
    state = dict(session.get("state") or {})
    audience = dict(state.get("audience_context") or {})
    status = str(event.get("status") or "")
    reason = str(event.get("reason") or "")
    source_refs = list(event.get("source_refs") or [])
    text = str(event.get("text") or "")
    kind = str(event.get("kind") or "")
    action = str(event.get("expression_action") or ExpressionAction.SILENT.value)

    suppressed = status != "SHOWN" or action == ExpressionAction.SILENT.value
    warnings: list[str] = []
    if suppressed and reason:
        warnings.append(f"Suppressed: {reason}")
    if not source_refs and kind in {"RECALL", "TALKING_POINT", "RISK", "CONTRIBUTION_OPPORTUNITY"} and not suppressed:
        warnings.append("No provenance attached; treat as session-state guidance, not confirmed fact.")
    if audience.get("explicit_concern"):
        warnings.append("Expression may prioritize the participant's explicitly stated concern; facts remain unchanged.")

    return {
        "action": action,
        "guidance_kind": kind or None,
        "target_participant_id": str(state.get("audience_participant_id") or ""),
        "text": text,
        "source_refs": source_refs,
        "warnings": warnings,
        "max_length": 0 if suppressed else 1200,
        "render_as": "SILENCE" if suppressed else "PRIMARY_CARD",
        "suppression_reasons": [reason] if suppressed and reason else [],
    }


def _guidance_view(event: dict[str, Any]) -> dict[str, Any]:
    return {**event, "expression_plan": _expression_plan_for_guidance(event)}


def _persist_guidance(
    session_id: str,
    *,
    kind: str,
    action: str,
    text: str,
    source_refs: list[dict[str, Any]],
    status: str,
    reason: str = "",
    score: Optional[OpportunityScore] = None,
) -> dict[str, Any]:
    ts = store.now()
    row = {
        "id": store.new_id("ge_"),
        "session_id": session_id,
        "candidate_id": store.new_id("gc_"),
        "kind": kind,
        "expression_action": action,
        "text": text,
        "source_refs": source_refs,
        "status": status,
        "reason": reason,
        "score": {"value": score.value, **score.__dict__} if score else {},
        "user_action": "NONE",
        "rendered_at": ts if status == "SHOWN" else None,
        "created_at": ts,
    }
    store.insert("conversation_guidance_event", row)
    saved = store.get("conversation_guidance_event", row["id"]) or row
    session = require_session(session_id)
    state = dict(session.get("state") or {})
    if status == "SHOWN":
        state["last_guidance_id"] = row["id"]
        store.update("conversation_session", session_id, {"state": state, "updated_at": ts})
    return _guidance_view(saved)


def _space_guidance_kinds(session: dict[str, Any]) -> set[str]:
    space = require_space(session["space_id"])
    config = SPACE_PROFILES.get(str(space.get("profile") or ""), {})
    return {str(kind) for kind in (config.get("guidance") or [])}


def _guidance_kind_allowed(session: dict[str, Any], kind: str) -> bool:
    # Direct questions and critical factual risk remain universal safety/value
    # lanes. Other proactive kinds must respect the selected Profile template.
    if kind in {"ANSWER_CUE", "RISK"}:
        return True
    return kind in _space_guidance_kinds(session)


def _delivery_cue(session: dict[str, Any], body: dict[str, Any]) -> str:
    expression = _expression_profile()
    audience = {
        "role": str(body.get("audience_role") or "").strip(),
        "priority": str(body.get("audience_priority") or "").strip(),
        "concern": str(body.get("audience_concern") or "").strip(),
    }
    focus = str(body.get("delivery_focus") or "").strip()
    mode = str(session.get("assistance_mode") or "BALANCED").upper()

    parts: list[str] = []
    if bool(expression.get("conclusion_first")):
        parts.append("先给结论")
    shape = str(expression.get("shape") or "").strip().lower()
    if shape == "bullet":
        parts.append("用 2–3 个要点展开")
    elif shape:
        parts.append(f"沿用表达结构 {shape}")

    seconds = expression.get("target_seconds")
    if isinstance(seconds, (int, float)) and seconds > 0:
        parts.append(f"控制在约 {int(seconds)} 秒")

    if mode == "PRESENTATION":
        parts.append("先主张，再给一条最强证据，最后回到下一步或 Q&A")
    elif mode == "ONE_ON_ONE":
        parts.append("先确认共同目标，再区分已知/未知，最后给出可执行 follow-up")

    if audience["role"]:
        parts.append(f"面向 {audience['role']} 只保留与其明确职责相关的内容")
    if audience["priority"]:
        parts.append(f"优先回应对方明确优先级：{audience['priority']}")
    if audience["concern"]:
        parts.append(f"显式处理对方已表达 concern：{audience['concern']}")
    if focus:
        parts.append(f"本次表达重点：{focus}")

    if not parts:
        parts = ["一句结论 + 一条有来源的依据 + 一个明确下一步"]
    return "；".join(parts)[:1200]


def _source_visibility_allows_guidance(source_refs: list[dict[str, Any]]) -> bool:
    blocked = {"BLOCKED", "NO_GUIDANCE", "HIDDEN"}
    return not any(str(ref.get("visibility") or "").upper() in blocked for ref in source_refs)


def _suggestion_budget_exhausted(session_id: str, mode: str, now: Optional[float] = None) -> bool:
    budgets = {"QUIET": 0, "BALANCED": 3, "ACTIVE": 6, "PRESENTATION": 4, "ONE_ON_ONE": 3}
    budget = budgets.get(mode, 3)
    if budget <= 0:
        return True
    cutoff = float(now if now is not None else store.now()) - 60.0
    shown = int(store.scalar(
        "SELECT COUNT(*) FROM conversation_guidance_event "
        "WHERE session_id = ? AND status = 'SHOWN' AND created_at >= ? "
        "AND reason NOT IN ('DIRECT_QUESTION','CRITICAL_RISK')",
        (session_id, cutoff),
    ) or 0)
    return shown >= budget


def _recent_duplicate_guidance(session_id: str, text: str, seconds: float = 90.0) -> bool:
    text = str(text or "").strip()
    if not text:
        return False
    return bool(store.select(
        "conversation_guidance_event",
        where="session_id = ? AND status = 'SHOWN' AND text = ? AND created_at >= ?",
        params=(session_id, text, store.now() - seconds),
        order="created_at DESC",
        limit=1,
    ))


def evaluate_guidance(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
    session = require_session(session_id)
    if session["status"] != "ACTIVE":
        raise ValueError("只有进行中的会话可以生成实时提示")
    policy = _normalize_session_policy(session.get("policy"))
    if policy["ai_assistance"] == "AI_FORBIDDEN":
        event = _persist_guidance(
            session_id,
            kind="RECALL",
            action=ExpressionAction.SILENT.value,
            text="",
            source_refs=list(body.get("source_refs") or []),
            status="SUPPRESSED",
            reason="POLICY_AI_FORBIDDEN",
        )
        return {"guidance": None, "suppressed": "POLICY_AI_FORBIDDEN", "event": event}
    state = dict(session.get("state") or {})
    current_topic = str(body.get("current_topic") or "").strip()[:500]
    if current_topic:
        state["current_topic"] = current_topic
    state["user_speaking"] = bool(body.get("user_speaking"))
    state["direct_question_pending"] = bool(str(body.get("direct_question") or "").strip())
    audience_context = {
        "role": str(body.get("audience_role") or "")[:240],
        "explicit_priority": str(body.get("audience_priority") or "")[:800],
        "explicit_concern": str(body.get("audience_concern") or "")[:1200],
        "decision_authority": str(body.get("decision_authority") or "")[:500],
        "relationship_context": str(body.get("relationship_context") or "")[:800],
    }
    if any(audience_context.values()):
        state["audience_context"] = {k: v for k, v in audience_context.items() if v}
    if "audience_participant_id" in body:
        # API model_dump always carries this key. An explicit empty value means
        # "do not bind this guidance to a known participant" and must clear a
        # prior target instead of leaking it across later turns.
        state["audience_participant_id"] = str(body.get("audience_participant_id") or "").strip()[:160]
    if current_topic or any(audience_context.values()) or "audience_participant_id" in body:
        store.update("conversation_session", session_id, {"state": state, "updated_at": store.now()})

    source_refs = list(body.get("source_refs") or [])
    direct_question = str(body.get("direct_question") or "").strip()
    if direct_question:
        # A new direct question supersedes stale proactive opportunities in the
        # presentation layer while preserving their audit trail.
        for prior in store.select(
            "conversation_guidance_event",
            where="session_id = ? AND status = 'SHOWN' AND kind IN ('CONTRIBUTION_OPPORTUNITY','TALKING_POINT') "
                  "AND user_action = 'NONE' AND created_at >= ?",
            params=(session_id, store.now() - 120.0),
            order="created_at DESC",
            limit=10,
        ):
            store.update("conversation_guidance_event", prior["id"], {"user_action": "CANCELLED_BY_DIRECT_QUESTION"})
        event = _persist_guidance(
            session_id,
            kind="ANSWER_CUE",
            action=ExpressionAction.ANSWER.value,
            text=str(body.get("answer_cue") or "先直接回答问题，再补一条有来源的事实。")[:1200],
            source_refs=source_refs,
            status="SHOWN",
            reason="DIRECT_QUESTION",
        )
        latest_state = dict((require_session(session_id).get("state") or {}))
        latest_state["direct_question_pending"] = False
        latest_state["last_guidance_id"] = event["id"]
        store.update("conversation_session", session_id, {"state": latest_state, "updated_at": store.now()})
        return {"guidance": event, "suppressed": None}

    critical_risk = str(body.get("critical_risk") or "").strip()
    if critical_risk:
        if not source_refs or not _source_visibility_allows_guidance(source_refs):
            event = _persist_guidance(
                session_id,
                kind="RISK",
                action=ExpressionAction.SILENT.value,
                text="",
                source_refs=source_refs,
                status="SUPPRESSED",
                reason="RISK_WITHOUT_ALLOWED_SOURCE",
            )
            return {"guidance": None, "suppressed": "RISK_WITHOUT_ALLOWED_SOURCE", "event": event}
        event = _persist_guidance(
            session_id,
            kind="RISK",
            action=ExpressionAction.FLAG_RISK.value,
            text=critical_risk[:1200],
            source_refs=source_refs,
            status="SHOWN",
            reason="CRITICAL_RISK",
        )
        return {"guidance": event, "suppressed": None}

    talking_point = str(body.get("talking_point") or "").strip()
    if talking_point:
        if not _guidance_kind_allowed(session, "TALKING_POINT"):
            event = _persist_guidance(
                session_id, kind="TALKING_POINT", action=ExpressionAction.SILENT.value,
                text="", source_refs=source_refs, status="SUPPRESSED", reason="PROFILE_GUIDANCE_NOT_ALLOWED",
            )
            return {"guidance": None, "suppressed": "PROFILE_GUIDANCE_NOT_ALLOWED", "event": event}
        if not source_refs or not _source_visibility_allows_guidance(source_refs):
            event = _persist_guidance(
                session_id, kind="TALKING_POINT", action=ExpressionAction.SILENT.value,
                text="", source_refs=source_refs, status="SUPPRESSED", reason="TALKING_POINT_WITHOUT_ALLOWED_SOURCE",
            )
            return {"guidance": None, "suppressed": "TALKING_POINT_WITHOUT_ALLOWED_SOURCE", "event": event}
        event = _persist_guidance(
            session_id,
            kind="TALKING_POINT",
            action=ExpressionAction.ADD_TALKING_POINT.value,
            text=talking_point[:1200],
            source_refs=source_refs,
            status="SHOWN",
            reason="MANUAL_TALKING_POINT",
        )
        return {"guidance": event, "suppressed": None}

    delivery_focus = str(body.get("delivery_focus") or "").strip()
    if delivery_focus:
        if not _guidance_kind_allowed(session, "DELIVERY"):
            event = _persist_guidance(
                session_id, kind="DELIVERY", action=ExpressionAction.SILENT.value,
                text="", source_refs=[], status="SUPPRESSED", reason="PROFILE_GUIDANCE_NOT_ALLOWED",
            )
            return {"guidance": None, "suppressed": "PROFILE_GUIDANCE_NOT_ALLOWED", "event": event}
        event = _persist_guidance(
            session_id,
            kind="DELIVERY",
            action=ExpressionAction.CLARIFY.value,
            text=_delivery_cue(session, body),
            source_refs=[],
            status="SHOWN",
            reason="EXPRESSION_PLANNER",
        )
        return {"guidance": event, "suppressed": None}

    if bool(body.get("user_speaking")):
        event = _persist_guidance(
            session_id, kind="CONTRIBUTION_OPPORTUNITY", action=ExpressionAction.SILENT.value,
            text="", source_refs=source_refs, status="SUPPRESSED", reason="USER_SPEAKING",
        )
        return {"guidance": None, "suppressed": "USER_SPEAKING", "event": event}

    mode = str(session.get("assistance_mode") or "BALANCED").upper()
    candidate_text = str(body.get("candidate_text") or "").strip()
    if candidate_text:
        if not _source_visibility_allows_guidance(source_refs):
            event = _persist_guidance(
                session_id, kind="CONTRIBUTION_OPPORTUNITY", action=ExpressionAction.SILENT.value,
                text="", source_refs=source_refs, status="SUPPRESSED", reason="SOURCE_VISIBILITY_BLOCKED",
            )
            return {"guidance": None, "suppressed": "SOURCE_VISIBILITY_BLOCKED", "event": event}
        if _recent_duplicate_guidance(session_id, candidate_text):
            event = _persist_guidance(
                session_id, kind="CONTRIBUTION_OPPORTUNITY", action=ExpressionAction.SILENT.value,
                text="", source_refs=source_refs, status="SUPPRESSED", reason="DUPLICATE_GUIDANCE",
            )
            return {"guidance": None, "suppressed": "DUPLICATE_GUIDANCE", "event": event}
        if float(body.get("social_risk") or 0.0) >= 1.5:
            event = _persist_guidance(
                session_id, kind="CONTRIBUTION_OPPORTUNITY", action=ExpressionAction.SILENT.value,
                text="", source_refs=source_refs, status="SUPPRESSED", reason="SOCIAL_RISK",
            )
            return {"guidance": None, "suppressed": "SOCIAL_RISK", "event": event}
        if float(body.get("stale_context_risk") or 0.0) >= 1.5:
            event = _persist_guidance(
                session_id, kind="CONTRIBUTION_OPPORTUNITY", action=ExpressionAction.SILENT.value,
                text="", source_refs=source_refs, status="SUPPRESSED", reason="STALE_CONTEXT",
            )
            return {"guidance": None, "suppressed": "STALE_CONTEXT", "event": event}
        if _suggestion_budget_exhausted(session_id, mode):
            event = _persist_guidance(
                session_id, kind="CONTRIBUTION_OPPORTUNITY", action=ExpressionAction.SILENT.value,
                text="", source_refs=source_refs, status="SUPPRESSED", reason="SUGGESTION_BUDGET",
            )
            return {"guidance": None, "suppressed": "SUGGESTION_BUDGET", "event": event}
        if not source_refs:
            event = _persist_guidance(
                session_id, kind="CONTRIBUTION_OPPORTUNITY", action=ExpressionAction.SILENT.value,
                text="", source_refs=[], status="SUPPRESSED", reason="NO_SOURCE",
            )
            return {"guidance": None, "suppressed": "NO_SOURCE", "event": event}
        score = _score(body)
        threshold = {"QUIET": float("inf"), "BALANCED": 2.5, "ACTIVE": 1.5, "PRESENTATION": 2.5, "ONE_ON_ONE": 3.0}.get(mode, 2.5)
        if score.value < threshold:
            event = _persist_guidance(
                session_id, kind="CONTRIBUTION_OPPORTUNITY", action=ExpressionAction.SILENT.value,
                text="", source_refs=source_refs, status="SUPPRESSED", reason="BELOW_THRESHOLD", score=score,
            )
            return {"guidance": None, "suppressed": "BELOW_THRESHOLD", "event": event}
        preferred_kind = "CONTRIBUTION_OPPORTUNITY"
        if mode in {"ACTIVE", "ONE_ON_ONE"} and _guidance_kind_allowed(session, "TALKING_POINT"):
            preferred_kind = "TALKING_POINT"
        elif not _guidance_kind_allowed(session, preferred_kind):
            if _guidance_kind_allowed(session, "TALKING_POINT"):
                preferred_kind = "TALKING_POINT"
            else:
                event = _persist_guidance(
                    session_id, kind="CONTRIBUTION_OPPORTUNITY", action=ExpressionAction.SILENT.value,
                    text="", source_refs=source_refs, status="SUPPRESSED", reason="PROFILE_GUIDANCE_NOT_ALLOWED", score=score,
                )
                return {"guidance": None, "suppressed": "PROFILE_GUIDANCE_NOT_ALLOWED", "event": event}
        event = _persist_guidance(
            session_id, kind=preferred_kind, action=ExpressionAction.ADD_TALKING_POINT.value,
            text=candidate_text[:1200], source_refs=source_refs, status="SHOWN",
            reason="HIGH_VALUE_OPPORTUNITY" if preferred_kind == "CONTRIBUTION_OPPORTUNITY" else "HIGH_VALUE_TALKING_POINT",
            score=score,
        )
        return {"guidance": event, "suppressed": None}

    recall = _recall_for_topic(session["space_id"], state.get("current_topic") or "")
    budget_exhausted = _suggestion_budget_exhausted(session_id, mode)
    if mode != "QUIET" and not budget_exhausted and _guidance_kind_allowed(session, "RECALL") and recall:
        refs = list(recall.get("source_refs") or [])
        if refs and _source_visibility_allows_guidance(refs):
            event = _persist_guidance(
                session_id, kind="RECALL", action=ExpressionAction.RECALL.value,
                text=recall["title"], source_refs=refs, status="SHOWN", reason="TOPIC_RECALL",
            )
            return {"guidance": event, "suppressed": None}

    open_questions = store.select(
        "conversation_item",
        where="space_id = ? AND type = 'OpenQuestion' "
              "AND state NOT IN ('DONE','SUPERSEDED','UNKNOWN') "
              "AND review_status IN ('USER_CONFIRMED','USER_EDITED','SOURCE_CONFIRMED')",
        params=(session["space_id"],), order="created_at DESC", limit=1,
    )
    if mode != "QUIET" and not budget_exhausted and _guidance_kind_allowed(session, "QUESTION") and open_questions:
        item = open_questions[0]
        refs = list(item.get("source_refs") or [])
        if refs and _source_visibility_allows_guidance(refs):
            event = _persist_guidance(
                session_id, kind="QUESTION", action=ExpressionAction.ASK_QUESTION.value,
                text=item["title"], source_refs=refs, status="SHOWN", reason="OPEN_QUESTION",
            )
            return {"guidance": event, "suppressed": None}

    reason = "SUGGESTION_BUDGET" if budget_exhausted and mode != "QUIET" else "NO_HIGH_VALUE_GUIDANCE"
    event = _persist_guidance(
        session_id, kind="RECALL", action=ExpressionAction.SILENT.value,
        text="", source_refs=[], status="SUPPRESSED", reason=reason,
    )
    return {"guidance": None, "suppressed": reason, "event": event}


def _looks_like_direct_question(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    if "?" in normalized or "？" in normalized:
        return True
    if normalized.endswith(("吗", "呢", "么")):
        return True
    head = normalized[:80]
    zh_markers = (
        "为什么", "怎么", "如何", "是否", "能不能", "可以不可以",
        "有没有", "哪个", "哪一个", "谁", "什么时候", "何时", "多少",
    )
    en_markers = (
        "what ", "why ", "how ", "who ", "when ", "which ",
        "can you ", "could you ", "do you ", "did you ", "is there ", "are there ",
    )
    return any(marker in head for marker in zh_markers) or any(head.startswith(marker) for marker in en_markers)


def guidance_from_transcript(
    session_id: str,
    text: str,
    *,
    channel: str = "PRIMARY_AUDIO",
) -> Optional[dict[str, Any]]:
    """Conservative automatic guidance from a final Conversation ASR segment.

    PRIMARY_AUDIO may trigger a direct-question cue or one sourced proactive
    recall/opportunity. SELF_MIC only updates the topic; it never interrupts
    the user with an automatic proactive card.
    """
    session = require_session(session_id)
    if session["status"] != "ACTIVE":
        return None
    policy = _normalize_session_policy(session.get("policy"))
    if policy["ai_assistance"] not in {"AI_ALLOWED", "AI_EXPECTED"}:
        return None

    cleaned = str(text or "").strip()[:500]
    if not cleaned:
        return None
    state = dict(session.get("state") or {})
    state["current_topic"] = cleaned
    store.update("conversation_session", session_id, {"state": state, "updated_at": store.now()})

    if str(channel or "").upper() == "SELF_MIC":
        return None

    # Direct questions are first-class and remain allowed in Quiet mode. Use
    # only pre-existing/frozen context as the answer cue source; the just-saved
    # transcript question itself is not an answer.
    if _looks_like_direct_question(cleaned):
        result = ask(session_id, cleaned)
        useful = next(
            (
                match for match in result.get("matches") or []
                if match.get("authority") != "OBSERVED_NOT_CONFIRMED"
            ),
            None,
        )
        if useful:
            refs = list(useful.get("source_refs") or [])
            if refs and not _source_visibility_allows_guidance(refs):
                useful = None
        if useful:
            answer_text = {
                "CONFIRMED_TRUTH": "已确认历史",
                "PERSONAL_EVIDENCE": "本场个人证据",
                "REFERENCE_SOURCE": "本场参考来源",
                "USER_NOTE_NOT_EVIDENCE": "本场 Quick Note（非证据）",
            }.get(str(useful.get("authority") or ""), "可追溯来源")
            cue = f"{answer_text}：{useful.get('title') or ''}"
            excerpt = str(useful.get("excerpt") or "").strip()
            if excerpt and excerpt != useful.get("title"):
                cue += f" — {excerpt[:260]}"
            refs = list(useful.get("source_refs") or [])
        else:
            cue = "这是一个直接问题；本场冻结来源里没有足够直接的可追溯答案。先回答已知部分，并明确不确定项。"
            refs = []

        recent = store.select(
            "conversation_guidance_event",
            where="session_id = ? AND reason = 'TRANSCRIPT_DIRECT_QUESTION' AND text = ? AND created_at >= ?",
            params=(session_id, cue, store.now() - 20.0),
            order="created_at DESC",
            limit=1,
        )
        if recent:
            return None
        return _persist_guidance(
            session_id,
            kind="ANSWER_CUE",
            action=ExpressionAction.ANSWER.value,
            text=cue[:1200],
            source_refs=refs,
            status="SHOWN",
            reason="TRANSCRIPT_DIRECT_QUESTION",
        )

    mode = str(session.get("assistance_mode") or "BALANCED").upper()
    if mode == "QUIET" or _suggestion_budget_exhausted(session_id, mode):
        return None

    # Reuse the frozen-context retrieval ranking. Only confirmed truth and
    # frozen Ready sources may become proactive cards. Quick Notes and current
    # transcript remain queryable through Manual Ask but are not promoted.
    result = ask(session_id, cleaned)
    useful = next(
        (
            match for match in result.get("matches") or []
            if match.get("authority") in {"CONFIRMED_TRUTH", "PERSONAL_EVIDENCE", "REFERENCE_SOURCE"}
        ),
        None,
    )
    if not useful:
        return None

    refs = list(useful.get("source_refs") or [])
    if not refs or not _source_visibility_allows_guidance(refs):
        return None

    authority = str(useful.get("authority") or "")
    if authority == "CONFIRMED_TRUTH":
        if not _guidance_kind_allowed(session, "RECALL"):
            return None
        kind = "RECALL"
        action = ExpressionAction.RECALL.value
        cue = str(useful.get("title") or "")[:1200]
        reason = "TRANSCRIPT_TOPIC_RECALL"
    else:
        if _guidance_kind_allowed(session, "CONTRIBUTION_OPPORTUNITY"):
            kind = "CONTRIBUTION_OPPORTUNITY"
            reason = "TRANSCRIPT_SOURCE_OPPORTUNITY"
        elif _guidance_kind_allowed(session, "TALKING_POINT"):
            kind = "TALKING_POINT"
            reason = "TRANSCRIPT_SOURCE_TALKING_POINT"
        else:
            return None
        action = ExpressionAction.ADD_TALKING_POINT.value
        cue = str(useful.get("excerpt") or useful.get("title") or "")[:1200]

    if not cue or _recent_duplicate_guidance(session_id, cue, seconds=45.0):
        return None
    return _persist_guidance(
        session_id,
        kind=kind,
        action=action,
        text=cue,
        source_refs=refs,
        status="SHOWN",
        reason=reason,
    )

def record_human_coach_cue(
    session_id: str,
    *,
    text: str = "",
    coach_session_id: str,
    voice_id: str = "",
) -> dict[str, Any]:
    """Persist Human Coach advice as auditable Guidance, never as truth/evidence."""
    session = require_session(session_id)
    policy = _normalize_session_policy(session.get("policy"))
    if session.get("status") != "ACTIVE":
        raise ValueError("Conversation Session 未处于进行中")
    if policy["human_assistance"] != "HUMAN_ALLOWED":
        raise ValueError("本场 Human Assistance policy 不允许人工教练")
    refs = [{
        "kind": "HUMAN_COACH_SESSION",
        "id": str(coach_session_id or ""),
        "voice_id": str(voice_id or ""),
        "visibility": "PRIVATE",
        "is_evidence": False,
    }]
    return _persist_guidance(
        session_id,
        kind="HUMAN_COACH",
        action="HUMAN_ADVICE",
        text=(str(text or "").strip() or ("语音教练建议" if voice_id else "人工教练建议"))[:1200],
        source_refs=refs,
        status="SHOWN",
        reason="HUMAN_COACH",
    )


def guidance_history(session_id: str, limit: int = 30) -> list[dict[str, Any]]:
    require_session(session_id)
    rows = store.select(
        "conversation_guidance_event",
        where="session_id = ?",
        params=(session_id,),
        order="created_at DESC",
        limit=max(1, min(100, int(limit))),
    )
    return [_guidance_view(row) for row in rows]


def set_guidance_action(guidance_id: str, action: str) -> dict[str, Any]:
    row = store.get("conversation_guidance_event", guidance_id)
    if not row:
        raise ValueError("实时提示不存在")
    action = str(action or "").upper()
    if action not in {"EXPANDED", "PINNED", "DISMISSED", "SNOOZED", "USED", "NONE"}:
        raise ValueError("提示动作不支持")
    store.update("conversation_guidance_event", guidance_id, {"user_action": action})
    return _guidance_view(store.get("conversation_guidance_event", guidance_id) or row)


def space_detail(space_id: str) -> dict[str, Any]:
    space = require_space(space_id)
    goals = store.select("conversation_goal", where="space_id = ?", params=(space_id,), order="priority DESC, created_at ASC")
    sessions = list_sessions(space_id)
    participants = store.select("conversation_participant", where="space_id = ?", params=(space_id,), order="created_at ASC")
    items = store.select("conversation_item", where="space_id = ?", params=(space_id,), order="created_at DESC", limit=200)
    threads = store.select("conversation_open_thread", where="space_id = ? AND status = 'OPEN'", params=(space_id,), order="created_at DESC")
    decisions = [i for i in items if i["type"] == "Decision"]
    commitments = [i for i in items if i["type"] in {"Commitment", "Task"}]
    open_questions = [i for i in items if i["type"] == "OpenQuestion"]
    objections = [i for i in items if i["type"] == "Objection"]
    upcoming = [s for s in sessions if s["status"] == "UPCOMING"]
    upcoming.sort(key=lambda s: s.get("scheduled_at") or float("inf"))
    ended = [s for s in sessions if s["status"] == "ENDED"]
    ended.sort(key=lambda s: s.get("ended_at") or 0, reverse=True)
    last_delta = None
    if ended:
        last = continue_summary(ended[0]["id"])
        last_delta = {
            "session_id": ended[0]["id"],
            "title": ended[0]["title"],
            "what_changed": last["what_changed"],
            "pins": last["pins"],
            "review_required": last["review_required"],
        }
    return {
        **space,
        "default_goal": next((g["title"] for g in goals if g["status"] == "ACTIVE"), ""),
        "goals": goals,
        "sessions": sessions,
        "participants": participants,
        "decisions": decisions,
        "commitments": commitments,
        "open_questions": open_questions,
        "objections": objections,
        "next_session": upcoming[0] if upcoming else None,
        "recent_decisions": [i for i in decisions if i["state"] == "AGREED"][:5],
        "last_session_delta": last_delta,
        "threads": threads,
    }


def prepare_space(space_id: str) -> dict[str, Any]:
    detail = space_detail(space_id)
    active = [
        i for i in detail["commitments"]
        if i["state"] == "COMMITTED"
        and i["review_status"] in THREAD_CONFIRMED_REVIEW
    ]
    unresolved = [
        i for i in detail["open_questions"]
        if i["state"] not in {"DONE", "SUPERSEDED", "UNKNOWN"}
        and i["review_status"] in THREAD_CONFIRMED_REVIEW
    ]
    decisions = [
        i for i in detail["decisions"]
        if i["state"] == "AGREED" and i["review_status"] in THREAD_CONFIRMED_REVIEW
    ]
    next_sessions = [s for s in detail["sessions"] if s["status"] == "UPCOMING"]
    next_sessions.sort(key=lambda s: s.get("scheduled_at") or float("inf"))
    return {
        "space": {k: detail[k] for k in ("id", "profile", "title", "description", "default_goal", "default_mode", "selected_source_ids", "selected_quick_note_ids")},
        "goals": detail["goals"],
        "next_session": next_sessions[0] if next_sessions else None,
        "open_commitments": active,
        "open_questions": unresolved,
        "open_threads": detail["threads"],
        "related_decisions": decisions[:12],
        "participants": detail["participants"],
        "selected_sources": detail.get("selected_source_ids") or [],
        "selected_quick_notes": detail.get("selected_quick_note_ids") or [],
        "brief": {
            "last_change": decisions[0] if decisions else None,
            "unresolved_count": len(active) + len(detail["threads"]),
            "known_participants": len(detail["participants"]),
        },
        "agenda": (
            [item["title"] for item in active[:3]]
            + [thread["text"] for thread in detail["threads"][:4]]
        ),
        "expected_questions": [item["title"] for item in unresolved[:5]],
        "contribution_candidates": [
            {"text": item["title"], "source_refs": item.get("source_refs") or [], "kind": "RECALL"}
            for item in decisions[:5] if item.get("source_refs")
        ],
        "profile_playbook": profile_playbook(detail["profile"]),
    }



def search_items(
    *,
    query: str = "",
    item_type: str = "",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Global Conversation search over item truth with provenance context.

    Results always carry Space, Session, review/state and source refs so the
    command/search surface cannot become an ungrounded AI answer box.
    """
    q = str(query or "").strip()
    requested = str(item_type or "").strip()
    allowed_types = {
        "Decision", "Commitment", "Task", "Deadline", "Risk", "Assumption",
        "OpenQuestion", "Proposal", "Objection", "Metric", "Status",
    }
    params: list[Any] = []
    clauses = ["1=1"]

    if requested:
        if requested == "Commitment":
            clauses.append("i.type IN ('Commitment','Task')")
        else:
            if requested not in allowed_types:
                raise ValueError("不支持的 Conversation Item 类型")
            clauses.append("i.type = ?")
            params.append(requested)

    if q:
        like = f"%{q}%"
        clauses.append("(i.title LIKE ? OR i.detail LIKE ? OR i.source_excerpt LIKE ?)")
        params.extend([like, like, like])

    params.append(max(1, min(200, int(limit))))
    rows = store.rows(
        "SELECT i.*, sp.title AS space_title, sp.profile AS space_profile, "
        "s.title AS session_title, s.started_at AS session_started_at, "
        "s.ended_at AS session_ended_at "
        "FROM conversation_item i "
        "JOIN conversation_space sp ON sp.id = i.space_id "
        "JOIN conversation_session s ON s.id = i.session_id "
        f"WHERE {' AND '.join(clauses)} "
        "ORDER BY i.updated_at DESC, i.created_at DESC LIMIT ?",
        tuple(params),
    )
    return rows


def export_session(session_id: str) -> dict[str, Any]:
    session = require_session(session_id)
    space = require_space(session["space_id"])
    transcript = store.select(
        "conversation_transcript_segment",
        where="session_id = ?",
        params=(session_id,),
        order="created_at ASC",
    )
    screen_context = store.select(
        "conversation_screen_context",
        where="session_id = ?",
        params=(session_id,),
        order="created_at ASC",
    )
    items = store.select(
        "conversation_item",
        where="session_id = ?",
        params=(session_id,),
        order="created_at ASC",
    )
    guidance = store.select(
        "conversation_guidance_event",
        where="session_id = ?",
        params=(session_id,),
        order="created_at ASC",
    )
    drafts = store.select(
        "conversation_draft_action",
        where="session_id = ?",
        params=(session_id,),
        order="created_at ASC",
    )
    packs = store.select(
        "conversation_session_pack",
        where="session_id = ?",
        params=(session_id,),
        order="created_at ASC",
    )
    confirmed = [
        item for item in items
        if item["review_status"] in {"USER_CONFIRMED", "USER_EDITED", "SOURCE_CONFIRMED"}
    ]
    candidates = [item for item in items if item["review_status"] == "AI_EXTRACTED"]
    source_manifest: list[dict[str, Any]] = []
    quick_notes: list[dict[str, Any]] = []
    for pack in packs:
        payload = dict(pack.get("payload") or {})
        for source in payload.get("sources") or []:
            source_manifest.append({
                "material_id": source.get("material_id") or "",
                "version_id": source.get("version_id") or "",
                "title": source.get("title") or "",
                "kind": source.get("kind") or "",
                "usage": source.get("usage") or "",
                "content_hash": source.get("content_hash") or "",
                "is_personal_evidence": bool(source.get("is_personal_evidence")),
            })
        for note in payload.get("quick_notes") or []:
            quick_notes.append({
                "id": note.get("id") or "",
                "title": note.get("title") or "",
                "content": note.get("content") or "",
                "kind": "USER_NOTE",
            })

    return {
        "kind": "CONVERSATION_SESSION",
        "contract": "v2.0-R1",
        "export_manifest": {
            "categories": [
                "session", "transcript", "screen_context_observations", "quick_notes", "confirmed_items",
                "unconfirmed_candidates", "guidance", "draft_actions",
                "source_manifest", "session_packs",
            ],
            "privacy": "LOCAL_EXPORT",
            "contains_external_secrets": False,
        },
        "space": {
            "id": space["id"],
            "title": space["title"],
            "profile": space["profile"],
        },
        "session": session,
        "transcript": transcript,
        "screen_context_observations": screen_context,
        "quick_notes": quick_notes,
        "confirmed_items": confirmed,
        "unconfirmed_candidates": candidates,
        "guidance": guidance,
        "draft_actions": drafts,
        "source_manifest": source_manifest,
        "session_packs": packs,
    }


def conversation_history(limit: int = 100) -> list[dict[str, Any]]:
    rows = store.rows(
        "SELECT s.*, sp.title AS space_title, sp.profile AS space_profile "
        "FROM conversation_session s JOIN conversation_space sp ON sp.id = s.space_id "
        "WHERE s.status = 'ENDED' "
        "ORDER BY COALESCE(s.ended_at, s.started_at, s.created_at) DESC LIMIT ?",
        (max(1, min(500, int(limit))),),
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        session_id = row["id"]
        row["decisions_count"] = int(store.scalar(
            "SELECT COUNT(*) FROM conversation_item WHERE session_id = ? AND type = 'Decision' AND state = 'AGREED'",
            (session_id,),
        ) or 0)
        row["commitments_count"] = int(store.scalar(
            "SELECT COUNT(*) FROM conversation_item WHERE session_id = ? AND type IN ('Commitment','Task') AND state IN ('COMMITTED','DONE')",
            (session_id,),
        ) or 0)
        row["open_questions_count"] = int(store.scalar(
            "SELECT COUNT(*) FROM conversation_item WHERE session_id = ? AND type = 'OpenQuestion' "
            "AND state NOT IN ('DONE','SUPERSEDED','UNKNOWN') AND review_status IN ('USER_CONFIRMED','USER_EDITED','SOURCE_CONFIRMED')",
            (session_id,),
        ) or 0)
        row["review_required"] = int(store.scalar(
            "SELECT COUNT(*) FROM conversation_item WHERE session_id = ? AND review_status = 'AI_EXTRACTED'",
            (session_id,),
        ) or 0)
        out.append(row)
    return out


def home_summary() -> dict[str, Any]:
    spaces = list_space_summaries("ACTIVE")
    if not spaces:
        return {
            "state": "EMPTY", "spaces": [], "next_session": None, "next_focus": None,
            "owed_by_me": [], "open_questions": [], "recent_change": None,
        }
    now = store.now()
    upcoming = store.select(
        "conversation_session",
        where="status = 'UPCOMING' AND scheduled_at IS NOT NULL AND scheduled_at >= ?",
        params=(now,), order="scheduled_at ASC", limit=1,
    )
    owed = store.select(
        "conversation_item",
        where="type IN ('Commitment','Task') AND state = 'COMMITTED' AND owner_id IN ('me','SELF','我')",
        order="created_at DESC", limit=8,
    )
    open_questions = store.select(
        "conversation_item",
        where="type = 'OpenQuestion' AND state NOT IN ('DONE','SUPERSEDED','UNKNOWN') "
              "AND review_status IN ('USER_CONFIRMED','USER_EDITED','SOURCE_CONFIRMED')",
        order="created_at DESC", limit=8,
    )
    changes = store.select(
        "conversation_item",
        where="review_status IN ('USER_CONFIRMED','USER_EDITED','SOURCE_CONFIRMED') "
              "AND state IN ('AGREED','COMMITTED','DONE','SUPERSEDED')",
        order="updated_at DESC", limit=1,
    )
    next_focus: Optional[dict[str, Any]] = None
    if upcoming:
        next_focus = {"kind": "PREPARE", "title": f"准备下一场：{upcoming[0]['title']}", "space_id": upcoming[0]["space_id"]}
    elif open_questions:
        next_focus = {"kind": "OPEN_QUESTION", "title": open_questions[0]["title"], "space_id": open_questions[0]["space_id"]}
    elif owed:
        next_focus = {"kind": "COMMITMENT", "title": owed[0]["title"], "space_id": owed[0]["space_id"]}
    return {
        "state": "ACTIVE",
        "spaces": spaces,
        "next_session": upcoming[0] if upcoming else None,
        "next_focus": next_focus,
        "owed_by_me": owed,
        "open_questions": open_questions,
        "recent_change": changes[0] if changes else None,
    }


DRAFT_ACTION_KINDS = {
    "FOLLOWUP_EMAIL_DRAFT",
    "CREATE_TASK_DRAFT",
    "CREATE_ISSUE_DRAFT",
    "UPDATE_DECISION_LOG_DRAFT",
}


def create_adhoc(
    *,
    title: str = "临时对话",
    profile: str = "PROJECT_SYNC",
    assistance_mode: str = "",
) -> dict[str, Any]:
    """Create and start an ad-hoc local session without Calendar/connectors."""
    space = create_space(title or "临时对话", profile, default_mode=assistance_mode)
    session = create_session(
        space["id"],
        title=title or "临时对话",
        capture_mode="NOTES_ONLY",
        processing_mode="LOCAL",
        assistance_mode=assistance_mode or space["default_mode"],
        consent_ack=True,
    )
    started = start_session(session["id"])
    return {"space": require_space(space["id"]), **started}


def _retention_cutoff(days: int, now: float) -> float:
    return now if days <= 0 else now - days * 86400.0


def retention_preview(space_id: str, now: Optional[float] = None) -> dict[str, Any]:
    space = require_space(space_id)
    policy = dict(space.get("retention_policy") or RETENTION_PRESETS["STANDARD"])
    now_value = float(now if now is not None else store.now())
    transcript_days = int(policy.get("transcript_days", 30) or 0)
    guidance_days = int(policy.get("guidance_days", 30) or 0)
    draft_days = int(policy.get("draft_days", 30) or 0)
    transcript_count = int(store.scalar(
        "SELECT COUNT(*) FROM conversation_transcript_segment WHERE space_id = ? AND created_at <= ?",
        (space_id, _retention_cutoff(transcript_days, now_value)),
    ) or 0)
    guidance_count = int(store.scalar(
        "SELECT COUNT(*) FROM conversation_guidance_event g "
        "JOIN conversation_session s ON s.id = g.session_id "
        "WHERE s.space_id = ? AND g.created_at <= ?",
        (space_id, _retention_cutoff(guidance_days, now_value)),
    ) or 0)
    draft_count = int(store.scalar(
        "SELECT COUNT(*) FROM conversation_draft_action WHERE space_id = ? AND created_at <= ?",
        (space_id, _retention_cutoff(draft_days, now_value)),
    ) or 0)
    screen_count = int(store.scalar(
        "SELECT COUNT(*) FROM conversation_screen_context WHERE space_id = ? AND created_at <= ?",
        (space_id, _retention_cutoff(transcript_days, now_value)),
    ) or 0)
    return {
        "space_id": space_id,
        "policy": policy,
        "would_delete": {
            "transcript_segments": transcript_count,
            "guidance_events": guidance_count,
            "draft_actions": draft_count,
            "screen_context_observations": screen_count,
        },
        "kept": {
            "confirmed_items": "KEEP",
            "session_packs": "KEEP",
            "provenance_tombstones": "KEEP",
        },
        "destructive": any((transcript_count, guidance_count, draft_count, screen_count)),
    }


def apply_retention(space_id: str, *, confirm: bool = False) -> dict[str, Any]:
    preview = retention_preview(space_id)
    if preview["destructive"] and not confirm:
        raise ValueError("Retention 会删除本地数据；请先预览并明确确认")
    policy = preview["policy"]
    now_value = store.now()
    deleted = {"transcript_segments": 0, "guidance_events": 0, "draft_actions": 0, "screen_context_observations": 0}

    transcript_cutoff = _retention_cutoff(int(policy.get("transcript_days", 30) or 0), now_value)
    for row in store.select(
        "conversation_transcript_segment",
        where="space_id = ? AND created_at <= ?",
        params=(space_id, transcript_cutoff),
    ):
        deleted["transcript_segments"] += int(store.delete("conversation_transcript_segment", row["id"]))

    for row in store.select(
        "conversation_screen_context",
        where="space_id = ? AND created_at <= ?",
        params=(space_id, transcript_cutoff),
    ):
        deleted["screen_context_observations"] += int(store.delete("conversation_screen_context", row["id"]))

    guidance_cutoff = _retention_cutoff(int(policy.get("guidance_days", 30) or 0), now_value)
    guidance_rows = store.rows(
        "SELECT g.* FROM conversation_guidance_event g "
        "JOIN conversation_session s ON s.id = g.session_id "
        "WHERE s.space_id = ? AND g.created_at <= ?",
        (space_id, guidance_cutoff),
    )
    for row in guidance_rows:
        deleted["guidance_events"] += int(store.delete("conversation_guidance_event", row["id"]))

    draft_cutoff = _retention_cutoff(int(policy.get("draft_days", 30) or 0), now_value)
    for row in store.select(
        "conversation_draft_action",
        where="space_id = ? AND created_at <= ?",
        params=(space_id, draft_cutoff),
    ):
        deleted["draft_actions"] += int(store.delete("conversation_draft_action", row["id"]))
    return {"space_id": space_id, "deleted": deleted, "policy": policy}


def delete_session(session_id: str, *, confirmed_policy: str = "BLOCK") -> dict[str, Any]:
    session = require_session(session_id)
    if session["status"] == "ACTIVE":
        raise ValueError("进行中的会话不能删除；请先结束")
    confirmed = store.select(
        "conversation_item",
        where="session_id = ? AND review_status IN ('USER_CONFIRMED','USER_EDITED','SOURCE_CONFIRMED')",
        params=(session_id,),
        order="created_at ASC",
    )
    policy = str(confirmed_policy or "BLOCK").upper()
    if confirmed and policy != "TOMBSTONE":
        raise ValueError("这场包含已确认事项；删除前必须选择 TOMBSTONE 保留 provenance 标记")
    tombstones = 0
    # One bounded-to-session read, instead of an O(items × Space threads)
    # provenance scan for every confirmed item being deleted.
    confirmed_ids = {item["id"] for item in confirmed}
    projected_thread_ids = [
        thread["id"]
        for thread in store.select(
            "conversation_open_thread",
            where="space_id = ? AND session_id = ?",
            params=(session["space_id"], session_id),
        )
        if any(
            str(ref.get("kind") or "") == "CONVERSATION_ITEM"
            and str(ref.get("id") or "") in confirmed_ids
            for ref in (thread.get("source_refs") or [])
        )
    ]
    if confirmed:
        ts = store.now()
        with store.connect() as conn:
            for item in confirmed:
                store.insert("conversation_provenance_tombstone", {
                    "id": store.new_id("cpt_"),
                    "original_item_id": item["id"],
                    "space_id": session["space_id"],
                    "deleted_session_id": session_id,
                    "type": item["type"],
                    "title": item["title"],
                    "state": item["state"],
                    "review_status": item["review_status"],
                    "source_refs": item.get("source_refs") or [],
                    "source_excerpt": item.get("source_excerpt") or "",
                    "deleted_at": ts,
                }, conn=conn)
                tombstones += 1
            for thread_id in projected_thread_ids:
                conn.execute("DELETE FROM conversation_open_thread WHERE id = ?", (thread_id,))
            conn.execute("DELETE FROM conversation_session WHERE id = ?", (session_id,))
    else:
        store.delete("conversation_session", session_id)
    try:
        from services import coach as human_coach
        human_coach.registry.revoke_for_target(session_id, session_kind="conversation")
    except Exception:
        pass
    return {
        "deleted": True,
        "session_id": session_id,
        "provenance_tombstones": tombstones,
        "removed_open_thread_projections": len(projected_thread_ids),
    }


def create_draft_action(
    session_id: str,
    *,
    kind: str,
    title: str = "",
    content: str = "",
    target: str = "",
    source_refs: Optional[list[dict[str, Any]]] = None,
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    session = require_session(session_id)
    policy = _normalize_session_policy(session.get("policy"))
    if policy["external_writeback"] == "OFF":
        raise ValueError("本场 External Write-back 已关闭；不会创建 follow-up/task/issue/decision-log 草稿")
    kind = str(kind or "").upper()
    if kind not in DRAFT_ACTION_KINDS:
        raise ValueError("DraftAction 类型不支持")
    if not (title or content):
        raise ValueError("DraftAction 不能为空")
    ts = store.now()
    row = {
        "id": store.new_id("cda_"),
        "space_id": session["space_id"],
        "session_id": session_id,
        "kind": kind,
        "title": str(title or "")[:300],
        "content": str(content or "")[:20_000],
        "target": str(target or "")[:500],
        "payload": dict(payload or {}),
        "source_refs": list(source_refs or []),
        "status": "DRAFT",
        "created_at": ts,
        "updated_at": ts,
    }
    store.insert("conversation_draft_action", row)
    return store.get("conversation_draft_action", row["id"]) or row


def list_draft_actions(space_id: str, status: str = "") -> list[dict[str, Any]]:
    require_space(space_id)
    if status:
        return store.select(
            "conversation_draft_action", where="space_id = ? AND status = ?",
            params=(space_id, status.upper()), order="created_at DESC",
        )
    return store.select("conversation_draft_action", where="space_id = ?", params=(space_id,), order="created_at DESC")


def review_draft_action(action_id: str, action: str) -> dict[str, Any]:
    row = store.get("conversation_draft_action", action_id)
    if not row:
        raise ValueError("DraftAction 不存在")
    action = str(action or "").upper()
    mapping = {"APPROVE": "APPROVED", "DISMISS": "DISMISSED", "RESET": "DRAFT"}
    if action not in mapping:
        raise ValueError("DraftAction 审核动作不支持")
    # APPROVED means the user reviewed the local draft. It deliberately does
    # not mean an external connector sent/created anything.
    store.update("conversation_draft_action", action_id, {"status": mapping[action], "updated_at": store.now()})
    return store.get("conversation_draft_action", action_id) or row


def followup_draft(session_id: str) -> dict[str, Any]:
    summary = continue_summary(session_id)
    reviewed_open_questions = list(summary["open_questions"])
    lines = ["这场之后："]
    if summary["decisions"]:
        lines.append("Decisions：" + "；".join(x["title"] for x in summary["decisions"]))
    if summary["commitments"]:
        lines.append("Commitments：" + "；".join(x["title"] for x in summary["commitments"]))
    if reviewed_open_questions:
        lines.append("Open Questions：" + "；".join(x["title"] for x in reviewed_open_questions))
    if len(lines) == 1:
        lines.append("当前没有已确认的 Decision / Commitment / Open Question；建议先完成逐项确认。")
    sources: list[dict[str, Any]] = []
    for item in summary["decisions"] + summary["commitments"] + reviewed_open_questions:
        sources.extend(item.get("source_refs") or [])
    # Continue deliberately separates reviewed open questions from the
    # AI_EXTRACTED review queue. Keep the excluded candidate ids in the draft
    # provenance so users can audit what was *not* promoted into follow-up.
    excluded = [item["id"] for item in summary["candidates"]]
    return create_draft_action(
        session_id,
        kind="FOLLOWUP_EMAIL_DRAFT",
        title=f"{summary['session']['title']} · Follow-up",
        content="\n".join(lines),
        source_refs=sources,
        payload={
            "excluded_unreviewed_item_ids": excluded,
            "execution": "LOCAL_REVIEW_ONLY",
            "external_execution": False,
        },
    )

def derived_writeback_draft(session_id: str, kind: str) -> dict[str, Any]:
    """Build a local review-only action draft from structured Continue state.

    This does not execute a connector.  It preserves each source reference and,
    for Open Questions, visibly carries review status so an AI-extracted
    question cannot masquerade as a confirmed organizational fact.
    """
    summary = continue_summary(session_id)
    requested = str(kind or "").upper()
    if requested == "CREATE_TASK_DRAFT":
        items = list(summary["commitments"])
        label = "Task Draft"
        lines = [
            f"- {item['title']}"
            + (f" · owner={item.get('owner_id')}" if item.get("owner_id") else "")
            + (f" · due={item.get('due_at')}" if item.get("due_at") else "")
            for item in items
        ]
    elif requested == "CREATE_ISSUE_DRAFT":
        items = list(summary["open_questions"])
        label = "Issue Draft"
        lines = [
            f"- {item['title']} · review={item.get('review_status') or 'UNKNOWN'}"
            for item in items
        ]
    elif requested == "UPDATE_DECISION_LOG_DRAFT":
        items = list(summary["decisions"])
        label = "Decision Log Draft"
        lines = [
            f"- {item['title']} · state={item.get('state') or 'UNKNOWN'}"
            for item in items
        ]
    else:
        raise ValueError("只支持 CREATE_TASK_DRAFT / CREATE_ISSUE_DRAFT / UPDATE_DECISION_LOG_DRAFT")

    if not items:
        raise ValueError(f"当前没有可生成 {label} 的结构化事项")

    sources: list[dict[str, Any]] = []
    for item in items:
        sources.extend(item.get("source_refs") or [])
    return create_draft_action(
        session_id,
        kind=requested,
        title=f"{summary['session']['title']} · {label}",
        content="\n".join(lines),
        source_refs=sources,
        payload={
            "derived_item_ids": [item["id"] for item in items],
            "execution": "LOCAL_REVIEW_ONLY",
            "external_execution": False,
        },
    )


def synthetic_demo() -> dict[str, Any]:
    """Deterministic onboarding dry run; never persisted and never real evidence."""
    return {
        "evidence": "SYNTHETIC_DEMO",
        "scenario": "DESIGN_REVIEW",
        "title": "Android Architecture Review · Dry Run",
        "goal": "明确 offline migration 方案并确认 rollback owner",
        "steps": [
            {
                "kind": "PROPOSAL",
                "title": "Proposal ≠ Decision",
                "input": "Alex：我建议 offline sync v2。",
                "output": "建议被记录为 Proposal；没有共识证据，不会写成 AGREED。",
                "state": "PROPOSED",
            },
            {
                "kind": "RECALL",
                "title": "跨场 Recall",
                "input": "话题回到 offline migration。",
                "output": "上次已确认：offline migration 采用 v2。",
                "source": "Synthetic prior Design Review · confirmed",
            },
            {
                "kind": "CONTRIBUTION_OPPORTUNITY",
                "title": "值得补充",
                "input": "讨论数据规模时，你有一条已选来源。",
                "output": "Q4 benchmark 已覆盖 10x data scale。",
                "source": "Synthetic Benchmark Note",
            },
            {
                "kind": "SILENT",
                "title": "Stay Silent",
                "input": "你正在连续表达，且没有新的高价值信息。",
                "output": "SILENT · USER_SPEAKING",
            },
            {
                "kind": "CONTINUE",
                "title": "会后逐项确认",
                "input": "模型提取：rollback owner = 未知。",
                "output": "保留为 Open Question / 待确认；不会猜 owner，也不会自动写外部系统。",
            },
        ],
        "privacy": {
            "capture_default": "NOTES_ONLY",
            "processing_default": "LOCAL",
            "audio_retention": "OFF",
            "external_writeback": "DRAFT_ONLY_REVIEW_REQUIRED",
        },
    }


def diagnostics() -> dict[str, Any]:
    """Local-only Conversation runtime health and engineering evidence.

    Counts describe this device only. They are deliberately not interpreted
    as product-market fit or real-user validation.
    """
    from services.product import conversation_capture
    from services.storage.product_migrations import LATEST_SCHEMA_VERSION

    spaces = int(store.scalar("SELECT COUNT(*) FROM conversation_space") or 0)
    sessions = int(store.scalar("SELECT COUNT(*) FROM conversation_session") or 0)
    active_sessions = int(store.scalar("SELECT COUNT(*) FROM conversation_session WHERE status = 'ACTIVE'") or 0)
    ended_sessions = int(store.scalar("SELECT COUNT(*) FROM conversation_session WHERE status = 'ENDED'") or 0)
    transcripts = int(store.scalar("SELECT COUNT(*) FROM conversation_transcript_segment") or 0)
    screen_observations = int(store.scalar("SELECT COUNT(*) FROM conversation_screen_context") or 0)
    confirmed_items = int(store.scalar(
        "SELECT COUNT(*) FROM conversation_item WHERE review_status IN ('USER_CONFIRMED','USER_EDITED','SOURCE_CONFIRMED')"
    ) or 0)
    pending_items = int(store.scalar(
        "SELECT COUNT(*) FROM conversation_item WHERE review_status = 'AI_EXTRACTED'"
    ) or 0)
    shown = int(store.scalar("SELECT COUNT(*) FROM conversation_guidance_event WHERE status = 'SHOWN'") or 0)
    suppressed = int(store.scalar("SELECT COUNT(*) FROM conversation_guidance_event WHERE status = 'SUPPRESSED'") or 0)
    sourced_shown = int(store.scalar(
        "SELECT COUNT(*) FROM conversation_guidance_event "
        "WHERE status = 'SHOWN' AND source_refs_json NOT IN ('[]','null','')"
    ) or 0)
    drafts = int(store.scalar("SELECT COUNT(*) FROM conversation_draft_action") or 0)
    approved_drafts = int(store.scalar(
        "SELECT COUNT(*) FROM conversation_draft_action WHERE status = 'APPROVED'"
    ) or 0)
    adopted_guidance = int(store.scalar(
        "SELECT COUNT(*) FROM conversation_guidance_event WHERE status = 'SHOWN' "
        "AND user_action IN ('USED','PINNED','EXPANDED')"
    ) or 0)
    dismissed_guidance = int(store.scalar(
        "SELECT COUNT(*) FROM conversation_guidance_event WHERE user_action = 'DISMISSED'"
    ) or 0)
    duplicate_suppressed = int(store.scalar(
        "SELECT COUNT(*) FROM conversation_guidance_event WHERE status = 'SUPPRESSED' "
        "AND reason = 'DUPLICATE_GUIDANCE'"
    ) or 0)
    policy_suppressed = int(store.scalar(
        "SELECT COUNT(*) FROM conversation_guidance_event WHERE status = 'SUPPRESSED' "
        "AND reason IN ('POLICY_AI_FORBIDDEN','SOURCE_VISIBILITY_BLOCKED','SOCIAL_RISK','STALE_CONTEXT','SUGGESTION_BUDGET')"
    ) or 0)
    capture = conversation_capture.status()
    return {
        "contract": "v2.0-R1",
        "schema_version": store.schema_version(),
        "expected_schema_version": LATEST_SCHEMA_VERSION,
        "capture": capture,
        "runtime": {
            "spaces": spaces,
            "sessions": sessions,
            "active_sessions": active_sessions,
            "ended_sessions": ended_sessions,
            "transcript_segments": transcripts,
            "screen_context_observations": screen_observations,
            "confirmed_items": confirmed_items,
            "pending_review_items": pending_items,
            "guidance_shown": shown,
            "guidance_suppressed": suppressed,
            "sourced_guidance_shown": sourced_shown,
            "draft_actions": drafts,
            "approved_drafts": approved_drafts,
            "guidance_adopted": adopted_guidance,
            "guidance_dismissed": dismissed_guidance,
            "duplicate_suppressed": duplicate_suppressed,
            "policy_suppressed": policy_suppressed,
        },
        "evaluation": {
            "observed_proxies": {
                "source_attribution_coverage": (sourced_shown / shown) if shown else None,
                "guidance_adoption_rate": (adopted_guidance / shown) if shown else None,
                "guidance_dismissal_rate": (dismissed_guidance / shown) if shown else None,
                "suppression_rate": (suppressed / (shown + suppressed)) if (shown + suppressed) else None,
                "duplicate_suppression_count": duplicate_suppressed,
                "review_queue_size": pending_items,
                "approved_draft_rate": (approved_drafts / drafts) if drafts else None,
            },
            "requires_human_labels": [
                "recall_precision",
                "source_attribution_accuracy",
                "direct_question_detection",
                "decision_commitment_state_precision",
                "opportunity_precision",
                "interruption_regret",
                "useful_silence_rate",
                "continue_writeback_accuracy",
                "real_cross_session_value",
                "real_user_cognitive_load",
            ],
            "interpretation": "Observed proxies are runtime telemetry on this local device; they are not precision/quality/PMF claims.",
        },
        "health": {
            "database": "AVAILABLE" if store.schema_version() == LATEST_SCHEMA_VERSION else "NEEDS_ACTION",
            "capture": "AVAILABLE" if not capture["active"] else "IN_USE",
            "continuity": "AVAILABLE" if spaces > 0 else "LIMITED",
            "review_queue": "NEEDS_ACTION" if pending_items > 0 else "AVAILABLE",
            "session_pack_context": "AVAILABLE",
            "retrieval": "AVAILABLE",
            "state_engine": "AVAILABLE",
            "guidance_arbiter": "AVAILABLE",
            "export_delete_integrity": "AVAILABLE",
            "processing_policy": "AVAILABLE",
            "speaker_diarization": "LIMITED_CHANNEL_ONLY",
            "external_connectors": (
                "AVAILABLE"
                if conversation_connectors.diagnostics()["available_capabilities"]
                else "NOT_CONFIGURED"
            ),
            "conversation_screen_context": "MANUAL_AND_EXPLICIT_AUTO_RUNTIME_AVAILABLE",
            "conversation_share_privacy": "DESKTOP_RUNTIME_AVAILABLE_VERIFY_AT_START",
            "conversation_human_coach": "RUNTIME_CANDIDATE_EXPLICIT_SESSION_LINK",
            "external_writeback_execution": "DRAFT_ONLY_NO_CONNECTOR_EXECUTION",
        },
        "evidence": {
            "engineering": "SYNTHETIC_AND_LOCAL_RUNTIME",
            "real_conversation_user_evidence": "REAL_CONVERSATION_USER_EVIDENCE_PENDING",
            "pmf": "PMF_PROVEN_FALSE",
        },
        "privacy": {
            "remote_telemetry": "OFF",
            "auto_external_writeback": "OFF",
            "speaker_biometric_identity": "OFF",
            "emotion_sentiment_profiling": "OFF",
            "hidden_intent_claims": "OFF",
            "screen_raw_image_persistence": "OFF",
            "share_privacy_default": "OFF",
            "share_privacy_runtime": "ELECTRON_CONTENT_PROTECTION_BEST_EFFORT",
            "share_privacy_undetectability_claim": "NEVER",
            "human_coach_default": "OFF_EXPLICIT_START_ONLY",
            "human_coach_truth_authority": "ADVICE_ONLY_NOT_EVIDENCE",
            "human_coach_public_relay": "BLOCKED_UNLESS_CONFIGURED",
        },
        "connectors": conversation_connectors.diagnostics(),
    }


def export_space(space_id: str) -> dict[str, Any]:
    detail = space_detail(space_id)
    items = store.select("conversation_item", where="space_id = ?", params=(space_id,), order="created_at ASC")
    transcript = store.select(
        "conversation_transcript_segment", where="space_id = ?", params=(space_id,), order="created_at ASC"
    )
    screen_context = store.select(
        "conversation_screen_context", where="space_id = ?", params=(space_id,), order="created_at ASC"
    )
    guidance = store.rows(
        "SELECT g.* FROM conversation_guidance_event g JOIN conversation_session s ON s.id = g.session_id "
        "WHERE s.space_id = ? ORDER BY g.created_at ASC",
        (space_id,),
    )
    notes: list[dict[str, Any]] = []
    for note_id in detail.get("selected_quick_note_ids") or []:
        note = store.get("quick_note", str(note_id))
        if note:
            notes.append(note)
    source_manifest: list[dict[str, Any]] = []
    for material_id in detail.get("selected_source_ids") or []:
        material = store.get("material", str(material_id))
        if material:
            source_manifest.append({
                "id": material["id"],
                "kind": material["kind"],
                "usage": material["usage"],
                "title": material["title"],
                "active_version_id": material.get("active_version_id") or "",
            })
        else:
            source_manifest.append({"id": str(material_id), "missing": True})
    confirmed = [
        item for item in items
        if item["review_status"] in {"USER_CONFIRMED", "USER_EDITED", "SOURCE_CONFIRMED"}
    ]
    candidates = [item for item in items if item["review_status"] == "AI_EXTRACTED"]
    tombstones = store.select(
        "conversation_provenance_tombstone",
        where="space_id = ?",
        params=(space_id,),
        order="deleted_at ASC",
    )
    # Explicit categories are primary. Legacy aggregate keys stay for tooling
    # compatibility but point to the same local data, not a second truth store.
    return {
        "kind": "CONVERSATION_SPACE",
        "contract": "v2.0-R1",
        "export_manifest": {
            "categories": [
                "transcript", "screen_context_observations", "notes", "confirmed_items", "unconfirmed_candidates",
                "guidance", "source_manifest", "open_threads", "draft_actions", "session_packs", "provenance_tombstones",
            ],
            "privacy": "LOCAL_EXPORT",
            "contains_external_secrets": False,
        },
        "space": {k: v for k, v in detail.items() if k not in {"goals", "sessions", "participants", "decisions", "commitments", "open_questions", "threads"}},
        "goals": detail["goals"],
        "sessions": detail["sessions"],
        "participants": detail["participants"],
        "transcript": transcript,
        "screen_context_observations": screen_context,
        "notes": notes,
        "confirmed_items": confirmed,
        "unconfirmed_candidates": candidates,
        "guidance": guidance,
        "source_manifest": source_manifest,
        "draft_actions": list_draft_actions(space_id),
        "provenance_tombstones": tombstones,
        "items": items,
        "open_threads": detail["threads"],
        "threads": detail["threads"],  # compatibility alias
        "session_packs": store.select("conversation_session_pack", where="space_id = ?", params=(space_id,), order="created_at ASC"),
        "packs": store.select("conversation_session_pack", where="space_id = ?", params=(space_id,), order="created_at ASC"),
    }
