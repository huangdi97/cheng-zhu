"""Follow-up Resolver: resolve bare follow-ups against interview state.

Input “为什么不用那个？” must resolve against the last question, the active
topic, open threads and the candidate's latest claims — so the planner sees a
complete question instead of a dangling cue.
"""
from __future__ import annotations

import re

from services.intelligence.types import QuestionType

# Bare cues that carry no subject of their own.
_BARE_CUE = re.compile(
    r"^(?:为什么[??？]?$|为什么呀[??？]?$|然后呢[??？]?$|那怎么办[??？]?$|那线上怎么办[??？]?$|"
    r"那个呢[??？]?$|为什么不|为什么不用那个|为什么没用|如果再|那线上|接着说|继续说|具体说说|展开讲|"
    r"然后[??？]?$|所以呢[??？]?$)",
    re.IGNORECASE,
)
_EN_BARE_CUE = re.compile(
    r"^(?:why\??$|why not\??$|and then\??$|so what\??$|go on|tell me more|elaborate)",
    re.IGNORECASE,
)
_CUE_STRIP = re.compile(r"^(?:为什么|为何|怎么|如何|那|那么|所以|接着|继续|具体|展开)", re.IGNORECASE)
_SUFFIX = re.compile(r"[??？。!！]+$")
_STOPWORDS = {"什么", "怎么", "如何", "为什么", "哪些", "这个", "那个", "的", "了", "吗", "呢"}


def is_bare_followup(text: str) -> bool:
    value = (text or "").strip().lower()
    return bool(value) and bool(_BARE_CUE.match(value) or _EN_BARE_CUE.match(value))


def _clean_fragment(text: str) -> str:
    cleaned = _CUE_STRIP.sub("", (text or "").strip())
    return _SUFFIX.sub("", cleaned).strip(" ，,。")[:60]


def _topic_from_state(interview_state) -> str:
    if interview_state is None:
        return ""
    if isinstance(interview_state, dict):
        return str(interview_state.get("current_topic", "") or "").strip()
    return str(getattr(interview_state, "current_topic", "") or "").strip()


def _previous_question(interview_state, fallback: str) -> str:
    if interview_state is None:
        return fallback
    if isinstance(interview_state, dict):
        return str(interview_state.get("previous_question", "") or "").strip() or fallback
    return str(getattr(interview_state, "previous_question", "") or "").strip() or fallback


def _claims(interview_state) -> list[str]:
    if interview_state is None:
        return []
    if isinstance(interview_state, dict):
        return [str(item) for item in (interview_state.get("candidate_claims") or [])]
    return [str(item) for item in (getattr(interview_state, "candidate_claims", []) or [])]


def _threads(interview_state, extra: list[str] | None) -> list[str]:
    items: list[str] = []
    if interview_state is not None:
        if isinstance(interview_state, dict):
            items = [str(t) for t in (interview_state.get("open_threads") or [])]
        else:
            items = [str(t) for t in (getattr(interview_state, "open_threads", []) or [])]
    if extra:
        items.extend(str(t) for t in extra if t)
    return items


def _anchor_matches(fragment: str, candidate: str) -> bool:
    if not fragment or not candidate:
        return False
    frag_terms = {
        chunk for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", fragment.lower()) if chunk not in _STOPWORDS
    } | set(re.findall(r"[a-z][a-z0-9+#.\-/]{1,}", fragment.lower()))
    cand_lc = candidate.lower()
    return any(term in cand_lc for term in frag_terms) if frag_terms else False


def resolve_followup(
    question_text: str,
    *,
    interview_state=None,
    previous_question: str = "",
    open_threads: list[str] | None = None,
    recent_qas: list[dict] | None = None,
) -> tuple[str, str]:
    """Resolve a bare follow-up to a complete question.

    Returns ``(resolved_question, follow_up_target)``. When the input is not a
    bare follow-up it is returned unchanged with an empty target.
    """
    raw = (question_text or "").strip()
    if not raw or not is_bare_followup(raw):
        return raw, ""
    fragment = _clean_fragment(raw)
    prev = _previous_question(interview_state, previous_question)
    topic = _topic_from_state(interview_state)
    threads = _threads(interview_state, open_threads)
    claims = _claims(interview_state)

    target = ""
    # 1. The cue fragment usually names the subject directly (“不用那个”).
    if fragment:
        target = fragment
    # 2. Fall back to open threads (most recent unresolved thread first).
    if not target and threads:
        target = threads[-1]
    # 3. Fall back to the active topic.
    if not target:
        target = topic

    resolved = raw
    if target:
        if prev and _anchor_matches(target, prev):
            resolved = f"{_SUFFIX.sub('', prev).strip()} —— 追问：{target}？"
        elif claims and _anchor_matches(target, " ".join(claims)):
            resolved = f"关于你提到的{target}：追问：{raw}"
        elif prev:
            resolved = f"{_SUFFIX.sub('', prev).strip()} —— 追问：{raw}"
        else:
            resolved = f"关于{target}的追问：{raw}"
    elif prev:
        resolved = f"{_SUFFIX.sub('', prev).strip()} —— 追问：{raw}"
    return resolved, target


def followup_target_type(target: str) -> QuestionType:
    """Classify what the resolved target is about (planner hint)."""
    if not target:
        return QuestionType.META
    if re.search(r"取舍|tradeoff|利弊", target, re.IGNORECASE):
        return QuestionType.KNOWLEDGE
    return QuestionType.PROJECT_DEEP_DIVE
