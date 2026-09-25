"""Interview State service: versioned state updated by incremental events.

 INVARIANT:
  - The state is the fold of InterviewEvents; an LLM never rewrites the whole
    state each turn (that would reintroduce topic pollution and drift).
  - Every committed version is persisted as a snapshot so crash recovery and
    session switching can restore exactly where the interview was.
"""
from __future__ import annotations

import json
import re
import threading

from core.logger import get_logger
from services.intelligence.types import InterviewEvent, InterviewPhase, InterviewState, new_id

_log = get_logger("intelligence.interview_state")

_LOCK = threading.Lock()
_STATES: dict[str, InterviewState] = {}
_SEQ: dict[str, int] = {}



_TOPIC_TOKEN = re.compile(r"[\u4e00-\u9fff]{2,}|[a-zA-Z][a-zA-Z0-9+#.\-/]{2,}")
_PHASE_HINTS: tuple[tuple[str, str], ...] = (
    (r"薪资|到岗|offer", InterviewPhase.HR.value),
    (r"写代码|算法题|leetcode", InterviewPhase.CODING.value),
    (r"系统设计|架构设计", InterviewPhase.SYSTEM_DESIGN.value),
    (r"冲突|领导力|行为|压力", InterviewPhase.BEHAVIORAL.value),
    (r"你的项目|项目里|介绍一下你的", InterviewPhase.PROJECT_DEEP_DIVE.value),
)
_MAX_TOPICS = 12


def _topic_of(text: str) -> str:
    """Deterministic topic label: first meaningful anchor chunk."""
    match = _TOPIC_TOKEN.search((text or "").lower())
    if not match:
        return ""
    return match.group()[:24]


def get_state(session_id: str, *, create: bool = True) -> InterviewState:
    with _LOCK:
        state = _STATES.get(session_id)
        if state is None and create:
            state = InterviewState(session_id=session_id)
            _STATES[session_id] = state
        return state


def reset_state(session_id: str) -> InterviewState:
    """Reset the active topic (new session / explicit topic reset)."""
    with _LOCK:
        state = InterviewState(session_id=session_id)
        _STATES[session_id] = state
        _SEQ[session_id] = 0
    return state


def drop_session(session_id: str) -> None:
    with _LOCK:
        _STATES.pop(session_id, None)
        _SEQ.pop(session_id, None)


def apply_event(session_id: str, kind: str, payload: dict | None = None) -> InterviewState:
    """Fold one incremental event into the state and bump the version.

    Supported kinds: question_received, topic_changed, claim_made,
    risk_flag_added, thread_opened, thread_closed, screen_problem,
    language_changed. Unknown kinds are ignored (forward compatibility).
    """
    payload = payload or {}
    state = get_state(session_id)
    with _LOCK:
        seq = _SEQ.get(session_id, 0) + 1
        _SEQ[session_id] = seq
        event = InterviewEvent(
            seq=seq,
            session_id=session_id,
            kind=kind,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        updated = _fold(state, event)
        _STATES[session_id] = updated
    _persist_snapshot(updated)
    return updated


def _fold(state: InterviewState, event: InterviewEvent) -> InterviewState:
    payload: dict = {}
    try:
        payload = json.loads(event.payload_json or "{}")
    except (json.JSONDecodeError, TypeError):
        payload = {}
    data = state.payload()
    data["version"] = state.version + 1
    kind = event.kind

    if kind == "question_received":
        question = str(payload.get("question", "") or "")
        question_type = str(payload.get("question_type", "") or "")
        if question:
            data["previous_topic"] = data["current_topic"]
            topic = _topic_of(question)
            if topic and topic != data["current_topic"]:
                # Explicit new topic resets the thread stack; a follow-up keeps it.
                if payload.get("is_follow_up"):
                    data["current_topic"] = topic
                else:
                    data["current_topic"] = topic
                    data["topic_stack"] = ([*data["topic_stack"], data["previous_topic"]])[-_MAX_TOPICS:] if data["previous_topic"] else data["topic_stack"]
                    data["open_threads"] = []
            data["question_type"] = question_type
            data["intent"] = str(payload.get("intent", "") or "")
            data["expected_depth"] = str(payload.get("expected_depth", "") or "")
            for hint, phase in _PHASE_HINTS:
                if hint in question.lower():
                    data["phase"] = phase
                    break
    elif kind == "topic_changed":
        new_topic = str(payload.get("topic", "") or "")
        if new_topic:
            data["previous_topic"] = data["current_topic"]
            data["current_topic"] = new_topic
            data["topic_stack"] = ([*data["topic_stack"], data["previous_topic"]])[-_MAX_TOPICS:] if data["previous_topic"] else data["topic_stack"]
    elif kind == "claim_made":
        claim = str(payload.get("claim", "") or "")
        if claim and claim not in data["candidate_claims"]:
            data["candidate_claims"] = [*data["candidate_claims"], claim][-24:]
    elif kind == "risk_flag_added":
        flag = str(payload.get("flag", "") or "")
        if flag and flag not in data["risk_flags"]:
            data["risk_flags"] = [*data["risk_flags"], flag][-12:]
    elif kind == "thread_opened":
        thread = str(payload.get("thread", "") or "")
        if thread and thread not in data["open_threads"]:
            data["open_threads"] = [*data["open_threads"], thread][-12:]
    elif kind == "thread_closed":
        thread = str(payload.get("thread", "") or "")
        data["open_threads"] = [item for item in data["open_threads"] if item != thread]
    elif kind == "screen_problem":
        data["screen_problem"] = str(payload.get("problem", "") or "")[:200]
    elif kind == "language_changed":
        data["language"] = str(payload.get("language", "") or data["language"])

    data["updated_at"] = event.created_at
    return InterviewState(**data)


def _persist_snapshot(state: InterviewState) -> None:
    try:
        from services.storage import intelligence as intel_storage

        intel_storage.save_state_snapshot(state.session_id, state.version, json.dumps(state.payload(), ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        # Persistence is a mirror, not the source of truth; the in-memory
        # state remains authoritative for the live session.
        _log.warning("interview state snapshot persist failed: %s", exc)


def restore_from_snapshot(session_id: str) -> InterviewState:
    """Crash recovery: rebuild in-memory state from the latest snapshot."""
    try:
        from services.storage import intelligence as intel_storage

        snapshot = intel_storage.latest_state_snapshot(session_id)
    except Exception as exc:  # noqa: BLE001
        _log.warning("interview state restore read failed: %s", exc)
        snapshot = None
    if not snapshot or not isinstance(snapshot.get("state"), dict):
        return get_state(session_id)
    data = dict(snapshot["state"])
    data.setdefault("session_id", session_id)
    with _LOCK:
        state = InterviewState(**{key: value for key, value in data.items() if key in InterviewState.__dataclass_fields__})
        _STATES[session_id] = state
    return state


def compact_state_context(state: InterviewState | None) -> str:
    """Render a small, prompt-ready state block (master doc section 11)."""
    if state is None or (not state.current_topic and not state.open_threads and not state.candidate_claims):
        return ""
    lines = ["[面试状态：增量维护，仅作承接参考]"]
    if state.current_topic:
        lines.append(f"当前主题：{state.current_topic}")
    if state.previous_topic and state.previous_topic != state.current_topic:
        lines.append(f"上一主题：{state.previous_topic}")
    if state.question_type:
        lines.append(f"当前题型：{state.question_type}")
    if state.intent:
        lines.append(f"当前意图：{state.intent}")
    if state.candidate_claims:
        lines.append("候选人已声称：" + "；".join(state.candidate_claims[:5]))
    if state.open_threads:
        lines.append("未闭合追问：" + "；".join(state.open_threads[:5]))
    if state.risk_flags:
        lines.append("风险标记：" + "；".join(state.risk_flags[:4]))
    if state.screen_problem:
        lines.append(f"屏幕题目：{state.screen_problem}")
    return "\n".join(lines)
