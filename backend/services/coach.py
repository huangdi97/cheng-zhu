"""Human Coach MVP (R2 Stage U).

Positioning: Mock / practice / career coaching / pair interview / sessions
where the interviewer explicitly allows outside help. It is not a hidden
helper for formal interviews: HUMAN_PRACTICE_ONLY (the default) refuses Live
sessions, and AI_ALLOWED never implies HUMAN_ALLOWED.

 SECURITY:
  - Tokens: 32 random bytes, returned once, stored only as SHA-256 hashes.
  - TTL + explicit revoke; revoked/expired tokens fail closed.
  - Permissions (transcript / ai_cue / resume_jd) are enforced server-side.
  - Per-token rate limit on cues.
  - Tokens are never logged. The helper URL carries the token in the URL
    fragment (#t=...), which browsers never send to the server.
  - Helpers can only read the permitted views and send text/voice
    suggestions; there is no remote keyboard / mouse / control surface.
 INVARIANT:
  - A coach cue is advice: source=HUMAN_COACH, never evidence, never
    user-confirmed, never written to facts or memory.
"""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from services.intelligence.policy import human_coach_allowed, resolve_human_policy

DEFAULT_TTL_MIN = 120
MAX_TTL_MIN = 480
RATE_LIMIT_PER_MIN = 20
MAX_TEXT_CHARS = 280
MAX_VOICE_BYTES = 1_000_000
PERMISSIONS = ("transcript", "ai_cue", "resume_jd")


class CoachPolicyError(PermissionError):
    pass


class CoachAuthError(PermissionError):
    pass


class CoachRateLimited(RuntimeError):
    pass


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass
class CoachSession:
    id: str
    token_hash: str
    session_kind: str  # "practice" | "live"
    permissions: dict[str, bool]
    created_at: float
    expires_at: float
    live_session_id: str = ""
    revoked: bool = False
    cue_times: deque = field(default_factory=lambda: deque(maxlen=RATE_LIMIT_PER_MIN * 2))
    cue_count: int = 0
    last_seen_at: float = 0.0

    def active(self, now: Optional[float] = None) -> bool:
        return not self.revoked and (now or time.time()) < self.expires_at

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_kind": self.session_kind,
            "permissions": dict(self.permissions),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "revoked": self.revoked,
            "active": self.active(),
            "cue_count": self.cue_count,
            "connected": bool(self.last_seen_at and time.time() - self.last_seen_at < 15),
        }


class CoachRegistry:
    def __init__(self, clock: Callable[[], float] = time.time):
        self._lock = threading.Lock()
        self._by_id: dict[str, CoachSession] = {}
        self._by_hash: dict[str, str] = {}
        self._voice: dict[str, tuple[bytes, str, float]] = {}
        self._clock = clock

    # -- candidate side ---------------------------------------------------
    def create(
        self,
        *,
        human_policy: str,
        session_kind: str,
        permissions: Optional[dict[str, bool]] = None,
        ttl_min: int = DEFAULT_TTL_MIN,
        live_session_id: str = "",
    ) -> tuple[CoachSession, str]:
        kind = "live" if session_kind == "live" else "practice"
        if not human_coach_allowed(human_policy, session_kind=kind):
            policy = resolve_human_policy(human_policy)
            reason = (
                "人工协助策略为「禁止」。"
                if policy == "HUMAN_FORBIDDEN"
                else "人工协助默认仅用于演练/练习；正式场次需面试方明确允许并在本场策略中设为「允许」。"
            )
            raise CoachPolicyError(reason)
        perms = {p: bool((permissions or {}).get(p, p == "transcript")) for p in PERMISSIONS}
        token = secrets.token_urlsafe(32)
        now = self._clock()
        ttl = max(5, min(MAX_TTL_MIN, int(ttl_min or DEFAULT_TTL_MIN)))
        session = CoachSession(
            id=f"coach-{uuid.uuid4().hex[:12]}",
            token_hash=_hash(token),
            session_kind=kind,
            permissions=perms,
            created_at=now,
            expires_at=now + ttl * 60,
            live_session_id=live_session_id,
        )
        with self._lock:
            self._by_id[session.id] = session
            self._by_hash[session.token_hash] = session.id
        return session, token

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [s.public() for s in self._by_id.values()]

    def revoke(self, session_id: str) -> bool:
        with self._lock:
            session = self._by_id.get(session_id)
            if session is None:
                return False
            session.revoked = True
            return True

    def revoke_all(self) -> int:
        with self._lock:
            count = 0
            for s in self._by_id.values():
                if not s.revoked:
                    s.revoked = True
                    count += 1
            return count

    # -- helper side --------------------------------------------------------
    def authenticate(self, token: str) -> CoachSession:
        if not token:
            raise CoachAuthError("missing token")
        with self._lock:
            sid = self._by_hash.get(_hash(token))
            session = self._by_id.get(sid or "")
        if session is None or not session.active(self._clock()):
            raise CoachAuthError("invalid, expired or revoked")
        session.last_seen_at = self._clock()
        return session

    def check_policy(self, session: CoachSession, human_policy: str) -> None:
        """Re-checked on every cue: a policy tightened mid-session wins."""
        if not human_coach_allowed(human_policy, session_kind=session.session_kind):
            raise CoachPolicyError("当前人工协助策略不允许发送建议")

    def take_rate(self, session: CoachSession) -> None:
        now = self._clock()
        while session.cue_times and now - session.cue_times[0] > 60:
            session.cue_times.popleft()
        if len(session.cue_times) >= RATE_LIMIT_PER_MIN:
            raise CoachRateLimited("too many suggestions; wait a moment")
        session.cue_times.append(now)
        session.cue_count += 1

    def store_voice(self, data: bytes, mime: str) -> str:
        if len(data) > MAX_VOICE_BYTES:
            raise ValueError("voice clip too large")
        vid = uuid.uuid4().hex[:16]
        with self._lock:
            self._voice[vid] = (data, mime or "audio/webm", self._clock())
            # keep memory bounded: drop clips older than 30 minutes
            for key in [k for k, (_d, _m, t) in self._voice.items() if self._clock() - t > 1800]:
                self._voice.pop(key, None)
        return vid

    def get_voice(self, vid: str) -> Optional[tuple[bytes, str]]:
        with self._lock:
            item = self._voice.get(vid)
        return (item[0], item[1]) if item else None


registry = CoachRegistry()


def coach_cue_payload(session: CoachSession, *, text: str = "", voice_id: str = "") -> dict[str, Any]:
    return {
        "type": "coach_cue",
        "id": f"cc-{uuid.uuid4().hex[:10]}",
        "coach_session_id": session.id,
        "text": text[:MAX_TEXT_CHARS],
        "voice_url": f"/api/coach/voice/{voice_id}" if voice_id else "",
        "source": "HUMAN_COACH",
        # Advice only: never evidence, never user-confirmed, never memorized.
        "is_evidence": False,
        "created_at": time.time(),
    }


def public_base_url() -> str:
    """Public Internet relay adapter. Without real relay infrastructure this
    is empty and remote (non-LAN) coaching is BLOCKED-EXTERNAL."""
    import os

    return (os.environ.get("COACH_PUBLIC_BASE_URL") or "").strip().rstrip("/")
