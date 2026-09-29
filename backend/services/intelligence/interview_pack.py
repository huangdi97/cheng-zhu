"""InterviewPack: the frozen, immutable runtime context of one interview.

R2 Stage F. Freezing copies the actual content (not version ids) of
everything Live is allowed to read into one object:

  candidate_context, claims, evidence_refs, skill_cards, stories,
  job, job_alignment, company_context, selected_kb, voice_profile,
  ai_policy, human_assistance_policy, share_privacy_policy,
  screen_context_policy, model_profile, answer_preferences,
  controlled_memory, source_versions, content_hashes, created_at

 INVARIANT:
  - Live reads ONLY: InterviewPack + current question + current session
    events + current screen context + allowed world knowledge. It never calls
    latest_job_id() / active_candidate_id() / the latest resume.
  - A frozen pack row is never mutated. "Update this session's material"
    creates an InterviewPackRevision (a new row, revision+1, parent_id set);
    old revisions stay for Review provenance.
  - A pack never holds provider API keys.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from core.logger import get_logger

_log = get_logger("intelligence.interview_pack")

PACK_SCHEMA_VERSION = 1

HUMAN_ASSISTANCE_POLICIES = ("HUMAN_FORBIDDEN", "HUMAN_PRACTICE_ONLY", "HUMAN_ALLOWED")
SHARE_PRIVACY_MODES = ("OFF", "PRIVATE_OVERLAY")
SCREEN_CONTEXT_POLICIES = ("OFF", "ON_REQUEST", "ALLOWED")

# Claims the user denied never enter a pack; everything else enters with its
# axes so the assertion policy can decide per turn.
_EXCLUDED_ASSERTIONS = {"USER_DENIED"}


def _hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def normalize_policy(value: str, allowed: tuple[str, ...], default: str) -> str:
    value = str(value or "").strip().upper()
    return value if value in allowed else default


@dataclass
class InterviewPack:
    """Read-only view over a frozen pack payload."""

    id: str
    session_id: str
    revision: int
    payload: dict[str, Any]
    frozen: bool = True
    content_hash: str = ""
    parent_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    # -- section accessors (return copies of plain data) --
    @property
    def candidate_context(self) -> dict[str, Any]:
        return dict(self.payload.get("candidate_context") or {})

    @property
    def profile_text(self) -> str:
        return str(self.candidate_context.get("profile_text", "") or "")

    @property
    def claims(self) -> list[dict[str, Any]]:
        return list(self.payload.get("claims") or [])

    @property
    def evidence_refs(self) -> list[dict[str, Any]]:
        return list(self.payload.get("evidence_refs") or [])

    @property
    def skill_cards(self) -> list[dict[str, Any]]:
        return list(self.payload.get("skill_cards") or [])

    @property
    def stories(self) -> list[dict[str, Any]]:
        return list(self.payload.get("stories") or [])

    @property
    def job(self) -> dict[str, Any]:
        return dict(self.payload.get("job") or {})

    @property
    def job_id(self) -> str:
        return str(self.job.get("id", "") or "")

    @property
    def job_requirements(self) -> list[str]:
        job = self.job
        return [*(job.get("must_have") or []), *(job.get("technologies") or [])][:8]

    @property
    def selected_kb(self) -> dict[str, Any]:
        return dict(self.payload.get("selected_kb") or {})

    @property
    def voice_profile(self) -> dict[str, Any]:
        return dict(self.payload.get("voice_profile") or {})

    @property
    def answer_preferences(self) -> dict[str, Any]:
        return dict(self.payload.get("answer_preferences") or {})

    @property
    def controlled_memory(self) -> dict[str, list[str]]:
        return dict(self.payload.get("controlled_memory") or {})

    @property
    def ai_policy(self) -> str:
        return str(self.payload.get("ai_policy", "AI_ALLOWED") or "AI_ALLOWED")

    @property
    def human_assistance_policy(self) -> str:
        return str(self.payload.get("human_assistance_policy", "HUMAN_PRACTICE_ONLY") or "HUMAN_PRACTICE_ONLY")

    @property
    def share_privacy_policy(self) -> str:
        return str(self.payload.get("share_privacy_policy", "OFF") or "OFF")

    def kb_path_allowed(self, path: str) -> bool:
        selected = self.selected_kb
        if selected.get("mode", "all_enabled") != "explicit":
            return True
        return str(path or "") in set(selected.get("paths") or [])

    def claim_axes_for(self, text: str) -> Optional[dict[str, Any]]:
        """First pack claim whose text contains / is contained by ``text``."""
        needle = (text or "").strip().lower()
        if not needle:
            return None
        for claim in self.claims:
            body = str(claim.get("text", "")).lower()
            if body and (body in needle or needle in body):
                return claim
        return None

    def summary(self) -> dict[str, Any]:
        job = self.job
        return {
            "id": self.id,
            "session_id": self.session_id,
            "revision": self.revision,
            "frozen": self.frozen,
            "content_hash": self.content_hash,
            "parent_id": self.parent_id,
            "job": {"id": job.get("id", ""), "title": job.get("title", ""), "company": job.get("company", "")},
            "counts": {
                "claims": len(self.claims),
                "evidence": len(self.evidence_refs),
                "skill_cards": len(self.skill_cards),
                "stories": len(self.stories),
            },
            "policies": {
                "ai_policy": self.ai_policy,
                "human_assistance_policy": self.human_assistance_policy,
                "share_privacy_policy": self.share_privacy_policy,
                "screen_context_policy": self.payload.get("screen_context_policy", "ON_REQUEST"),
            },
            "model_profile": self.payload.get("model_profile") or {},
            "content_hashes": self.payload.get("content_hashes") or {},
            "created_at": self.payload.get("created_at"),
        }


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def _model_profile(cfg) -> dict[str, Any]:
    """Model names only; keys and base URLs never enter the pack."""
    profile: dict[str, Any] = {}
    try:
        models = list(getattr(cfg, "models", []) or [])
        idx = int(getattr(cfg, "active_model", 0) or 0)
        if models:
            active = models[idx] if 0 <= idx < len(models) else models[0]
            profile["answer_model"] = str(getattr(active, "name", "") or "")
            profile["model"] = str(getattr(active, "model", "") or "")
    except Exception:  # noqa: BLE001
        pass
    profile["stt_engine"] = str(getattr(cfg, "stt_provider", "") or getattr(cfg, "stt_engine", "") or "")
    return profile


def _claims_snapshot(candidate_id: str) -> list[dict[str, Any]]:
    from services.storage import intelligence as storage

    out = []
    for row in storage.list_claims(candidate_id) if candidate_id else []:
        if str(row.get("user_assertion_status", "UNREVIEWED")) in _EXCLUDED_ASSERTIONS:
            continue
        try:
            structured = json.loads(row.get("structured_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            structured = {}
        out.append(
            {
                "id": row["id"],
                "type": row.get("type", "fact"),
                "text": row["text"],
                "source": row.get("source", ""),
                "provenance_status": row.get("provenance_status", "NO_EVIDENCE"),
                "user_assertion_status": row.get("user_assertion_status", "UNREVIEWED"),
                "structured": structured,
                "source_ids": storage.claim_evidence_ids(row["id"]),
            }
        )
    return out


def _skill_cards_snapshot(prep_space_id: Optional[int]) -> list[dict[str, Any]]:
    """Only user-reviewed cards enter a pack (Skill Builder -> Draft -> Review)."""
    if not prep_space_id:
        return []
    try:
        from services.storage import prep_space

        space = prep_space.get_space(int(prep_space_id)) or {}
    except Exception as exc:  # noqa: BLE001
        _log.warning("skill card snapshot failed: %s", exc)
        return []
    cards = []
    for entry in space.get("skill_cards") or []:
        card = entry.get("card") or {}
        if not card.get("user_reviewed"):
            continue
        cards.append({"id": f"skill-{entry.get('id')}", "project_name": entry.get("project_name", ""), "card": card})
    return cards


def build_pack_payload(
    *,
    session_id: str,
    cfg=None,
    job_id: str = "",
    candidate_id: str = "",
    prep_space_id: Optional[int] = None,
    selected_kb_paths: Optional[list[str]] = None,
    human_assistance_policy: str = "",
    share_privacy_policy: str = "",
    screen_context_policy: str = "",
    ai_policy: str = "",
    answer_preferences: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Collect the actual content to freeze. Called at Prepare/Preflight time,
    where reading "latest" profiles is legitimate (the user is choosing)."""
    from services.storage import intelligence as storage

    if cfg is None:
        from core.config import get_config

        cfg = get_config()
    candidate_id = candidate_id or storage.active_candidate_id()
    candidate_row = storage.get_candidate_profile(candidate_id) if candidate_id else None
    profile_text = str((candidate_row or {}).get("profile_text") or getattr(cfg, "resume_text", "") or "")
    job = storage.get_job_profile(job_id) if job_id else None
    voice = storage.get_voice_profile(candidate_id) if candidate_id else None
    stories = [
        {key: row.get(key, "") for key in ("id", "title", "situation", "challenge", "action", "result", "reflection")}
        for row in (storage.list_stories(candidate_id) if candidate_id else [])
    ]
    memory = {
        kind: [str(item.get("text", "")) for item in storage.list_memory_items(kind, limit=20)]
        for kind in ("knowledge_weakness", "repeated_topic", "communication_profile")
    }
    payload: dict[str, Any] = {
        "schema_version": PACK_SCHEMA_VERSION,
        "session_id": session_id,
        "candidate_context": {"candidate_id": candidate_id, "profile_text": profile_text},
        "claims": _claims_snapshot(candidate_id),
        "evidence_refs": [
            {"id": row["id"], "source": row.get("source", ""), "text": row["text"]}
            for row in (storage.list_evidence(candidate_id, limit=200) if candidate_id else [])
        ],
        "skill_cards": _skill_cards_snapshot(prep_space_id),
        "stories": stories,
        "job": job or {},
        "job_alignment": (job or {}).get("alignment") or {},
        "company_context": {"company": (job or {}).get("company", "")},
        "selected_kb": (
            {"mode": "explicit", "paths": sorted(set(selected_kb_paths))}
            if selected_kb_paths is not None
            else {"mode": "all_enabled", "paths": []}
        ),
        "voice_profile": (voice or {}).get("profile") or {},
        "ai_policy": str(ai_policy or getattr(cfg, "ai_policy_mode", "AI_ALLOWED") or "AI_ALLOWED").upper(),
        "human_assistance_policy": normalize_policy(
            human_assistance_policy or getattr(cfg, "human_assistance_policy", ""),
            HUMAN_ASSISTANCE_POLICIES,
            "HUMAN_PRACTICE_ONLY",
        ),
        "share_privacy_policy": normalize_policy(
            share_privacy_policy or getattr(cfg, "share_privacy_mode", ""), SHARE_PRIVACY_MODES, "OFF"
        ),
        "screen_context_policy": normalize_policy(screen_context_policy, SCREEN_CONTEXT_POLICIES, "ON_REQUEST"),
        "model_profile": _model_profile(cfg),
        "answer_preferences": dict(answer_preferences or {}),
        "controlled_memory": memory,
        "source_versions": {
            "candidate_updated_at": (candidate_row or {}).get("updated_at"),
            "job_updated_at": (job or {}).get("updated_at"),
            "prep_space_id": prep_space_id,
        },
        "created_at": time.time(),
    }
    payload["content_hashes"] = {
        key: _hash(payload.get(key))
        for key in ("candidate_context", "claims", "evidence_refs", "skill_cards", "stories", "job", "selected_kb", "voice_profile", "controlled_memory")
    }
    return payload


def freeze_pack(payload: dict[str, Any], *, reason: str = "freeze") -> InterviewPack:
    """Persist a new immutable pack (revision 1 of a new group)."""
    from services.storage import intelligence as storage

    pack_id = f"pack-{uuid.uuid4().hex[:16]}"
    content_hash = _hash({k: v for k, v in payload.items() if k != "created_at"})
    storage.insert_interview_pack(
        {
            "id": pack_id,
            "pack_group_id": pack_id,
            "session_id": payload["session_id"],
            "revision": 1,
            "job_id": str((payload.get("job") or {}).get("id", "") or ""),
            "pack_json": json.dumps(payload, ensure_ascii=False, default=str),
            "content_hash": content_hash,
            "reason": reason,
            "created_at": payload.get("created_at") or time.time(),
        }
    )
    return InterviewPack(id=pack_id, session_id=payload["session_id"], revision=1, payload=payload, content_hash=content_hash)


def revise_pack(pack_id: str, changes: dict[str, Any], *, reason: str = "user_update") -> InterviewPack:
    """Create an InterviewPackRevision; the original row is untouched."""
    from services.storage import intelligence as storage

    base = storage.get_interview_pack(pack_id)
    if base is None:
        raise KeyError(pack_id)
    payload = json.loads(json.dumps(base["pack"], ensure_ascii=False, default=str))
    for key, value in (changes or {}).items():
        if key in {"session_id", "schema_version", "content_hashes", "created_at"}:
            continue
        payload[key] = value
    payload["created_at"] = time.time()
    payload["content_hashes"] = {
        key: _hash(payload.get(key))
        for key in ("candidate_context", "claims", "evidence_refs", "skill_cards", "stories", "job", "selected_kb", "voice_profile", "controlled_memory")
    }
    latest = storage.latest_interview_pack(base["session_id"]) or base
    revision = int(latest["revision"]) + 1
    new_id = f"pack-{uuid.uuid4().hex[:16]}"
    content_hash = _hash({k: v for k, v in payload.items() if k != "created_at"})
    storage.insert_interview_pack(
        {
            "id": new_id,
            "pack_group_id": base["pack_group_id"],
            "session_id": base["session_id"],
            "revision": revision,
            "parent_id": latest["id"],
            "job_id": str((payload.get("job") or {}).get("id", "") or ""),
            "pack_json": json.dumps(payload, ensure_ascii=False, default=str),
            "content_hash": content_hash,
            "reason": reason,
            "created_at": payload["created_at"],
        }
    )
    return InterviewPack(
        id=new_id,
        session_id=base["session_id"],
        revision=revision,
        payload=payload,
        content_hash=content_hash,
        parent_id=latest["id"],
    )


def load_frozen_pack(session_id: str) -> Optional[InterviewPack]:
    from services.storage import intelligence as storage

    row = storage.latest_interview_pack(session_id)
    if not row:
        return None
    return InterviewPack(
        id=row["id"],
        session_id=row["session_id"],
        revision=int(row["revision"]),
        payload=row["pack"],
        content_hash=row["content_hash"],
        parent_id=row.get("parent_id", ""),
    )


def ephemeral_pack(session_id: str, cfg) -> InterviewPack:
    """Practice / unfrozen fallback: only the resume text configured for this
    run. Deliberately carries NO job and NO stored claims, so an unfrozen
    session can never pick up a job analyzed elsewhere."""
    payload = {
        "schema_version": PACK_SCHEMA_VERSION,
        "session_id": session_id,
        "candidate_context": {"candidate_id": "", "profile_text": str(getattr(cfg, "resume_text", "") or "")},
        "claims": [],
        "evidence_refs": [],
        "skill_cards": [],
        "stories": [],
        "job": {},
        "selected_kb": {"mode": "all_enabled", "paths": []},
        "ai_policy": str(getattr(cfg, "ai_policy_mode", "AI_ALLOWED") or "AI_ALLOWED").upper(),
        "human_assistance_policy": normalize_policy(
            getattr(cfg, "human_assistance_policy", ""), HUMAN_ASSISTANCE_POLICIES, "HUMAN_PRACTICE_ONLY"
        ),
        "share_privacy_policy": normalize_policy(getattr(cfg, "share_privacy_mode", ""), SHARE_PRIVACY_MODES, "OFF"),
        "controlled_memory": {},
        "created_at": time.time(),
    }
    return InterviewPack(id="", session_id=session_id, revision=0, payload=payload, frozen=False)


def resolve_live_pack(session_id: str, cfg) -> InterviewPack:
    """The only way the Live path obtains candidate/job context."""
    try:
        frozen = load_frozen_pack(session_id)
    except Exception as exc:  # noqa: BLE001
        _log.warning("load frozen pack failed session=%s: %s", session_id, exc)
        frozen = None
    return frozen or ephemeral_pack(session_id, cfg)
