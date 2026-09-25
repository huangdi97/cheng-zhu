"""Probabilistic interviewer-state tracker.

WHY: Interviewer intent can only ever be a probability, never a fact. This
module keeps a deterministic, rule-based probabilistic model serving the
Answer Planner as a soft hint. Internal only: never written into long-term
candidate facts (see memory_policy), never displayed as a deterministic
psychological verdict. No LLM calls, no fabricated facts.
"""
from __future__ import annotations

from dataclasses import replace

from services.intelligence.types import InterviewerState, now_ts

_FOCUS_CAP = 0.95
_CONCERN_CAP = 0.90
_DROP_BELOW = 0.05
_SIGNAL_CAP = 8
_FOCUS_STEP = 0.10
_CONCERN_STEP = 0.12

# question_type -> interviewer dimensions it puts under the spotlight.
_QUESTION_TYPE_FOCUS: dict[str, tuple[str, ...]] = {
    "KNOWLEDGE": ("engineering_depth",),
    "DEBUGGING": ("engineering_depth",),
    "PROJECT_DEEP_DIVE": ("engineering_depth", "authenticity"),
    "BEHAVIORAL": ("authenticity", "communication"),
    "PRODUCT": ("product_thinking",),
    "SYSTEM_DESIGN": ("system_design",),
    "CODING": ("coding",),
}

# intent keyword -> dimension (substring match; ascii keywords lowercase).
_INTENT_FOCUS: tuple[tuple[str, str], ...] = (
    ("原理", "engineering_depth"), ("底层", "engineering_depth"), ("深入", "engineering_depth"),
    ("深度", "engineering_depth"), ("真实", "authenticity"), ("亲自", "authenticity"),
    ("实际做过", "authenticity"), ("产品", "product_thinking"), ("用户价值", "product_thinking"),
    ("表达", "communication"), ("沟通", "communication"), ("说清楚", "communication"),
    ("架构", "system_design"), ("系统设计", "system_design"), ("方案设计", "system_design"),
    ("手写", "coding"), ("算法实现", "coding"), ("编码", "coding"),
)

# intent keywords probing a tradeoff decision -> topic-level concern.
_CONCERN_INTENT_KEYWORDS: tuple[str, ...] = ("取舍", "tradeoff", "why_not", "why not", "为什么不是")


def _raise_focus(focus: dict[str, float], dims: tuple[str, ...]) -> None:
    """Raise matching dimension probabilities by one bounded step."""
    for dim in dims:
        focus[dim] = min(_FOCUS_CAP, focus.get(dim, 0.0) + _FOCUS_STEP)


def _pick_highest(values: dict[str, float]) -> str:
    """Deterministic argmax (first key wins ties; definition order is fixed)."""
    if not values:
        return ""
    return max(values, key=lambda key: values[key])


def update_interviewer_state(
    state: InterviewerState,
    *,
    question_type: str = "",
    intent: str = "",
    topic: str = "",
    accepted_signal: bool = False,
) -> InterviewerState:
    """Rule-based probability update; returns a NEW InterviewerState (input
    treated as immutable). All probabilities stay within [0, 0.95]."""
    focus = dict(state.possible_focus)
    concerns = dict(state.possible_concerns)
    lowered = intent.lower() if intent else ""
    if question_type:
        _raise_focus(focus, _QUESTION_TYPE_FOCUS.get(question_type.upper(), ()))
    for keyword, dim in _INTENT_FOCUS:
        if keyword in lowered:
            _raise_focus(focus, (dim,))
    if lowered and topic and any(k in lowered for k in _CONCERN_INTENT_KEYWORDS):
        concerns[topic] = min(_CONCERN_CAP, concerns.get(topic, 0.0) + _CONCERN_STEP)
    signals = list(state.accepted_signals)
    if accepted_signal and topic:
        signals = (signals + [topic])[-_SIGNAL_CAP:]
    strong_concerns = {key: value for key, value in concerns.items() if value > 0.5}
    return replace(state, possible_focus=focus, possible_concerns=concerns, accepted_signals=signals,
                   desired_next_signal=_pick_highest(strong_concerns) if strong_concerns else _pick_highest(focus),
                   confidence=max([*focus.values(), *concerns.values()], default=0.0), updated_at=now_ts())


def decay(state: InterviewerState, *, factor: float = 0.85) -> InterviewerState:
    """Multiply every probability by `factor`, drop keys falling below the
    noise floor (0.05), and recompute confidence. Deterministic."""
    focus = {k: v * factor for k, v in state.possible_focus.items() if v * factor >= _DROP_BELOW}
    concerns = {k: v * factor for k, v in state.possible_concerns.items() if v * factor >= _DROP_BELOW}
    return replace(state, possible_focus=focus, possible_concerns=concerns,
                   confidence=max([*focus.values(), *concerns.values()], default=0.0), updated_at=now_ts())


def planner_hint(state: InterviewerState | None) -> str:
    """Short probabilistic hint for the Answer Planner prompt, or "" when the
    state is None/empty. Phrasing stays probabilistic on purpose: NEVER a
    deterministic psychological verdict like '面试官认为你不行'."""
    if state is None:
        return ""
    strong_concerns = {k: v for k, v in state.possible_concerns.items() if v > 0.5}
    if strong_concerns:
        key = _pick_highest(strong_concerns)
        return f"面试官可能仍有疑虑：{key}（{strong_concerns[key]:.1f}）"
    if state.possible_focus:
        key = _pick_highest(state.possible_focus)
        return f"面试官可能在验证：{key}（{state.possible_focus[key]:.1f}）"
    return ""
