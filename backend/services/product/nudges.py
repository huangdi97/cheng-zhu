"""Nudge / Open Thread (canonical §14).

Proactive guidance that appears only in the gaps: never while the candidate
is speaking, never while a new question is pending or a cue is being
prepared, one at a time, and below Fast Cue and warnings in priority
(Fast Cue > Warning > Nudge).

``evaluate`` is pure apart from reading/writing this session's nudge rows,
so the suppression rules are unit-testable.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from services.product import events
from services.storage import product as store

KINDS = ("MISSING_DIMENSION", "LIKELY_FOLLOWUP", "FACT_BOUNDARY", "ASK_BACK_OPPORTUNITY")
PRIORITY = {"FAST_CUE": 0, "WARNING": 1, "NUDGE": 2}
COOLDOWN_S = 25.0
CONFIDENCE_THRESHOLD = 0.6
MIN_ANSWER_CHARS = 30

_DIMENSIONS: dict[str, tuple[str, re.Pattern[str], str]] = {
    "trade_off": ("取舍", re.compile(r"(取舍|权衡|代价|trade[- ]?off|缺点|相比|而不是)", re.I), "补一句为什么这样选、放弃了什么"),
    "metric": ("量化结果", re.compile(r"\d+(?:\.\d+)?\s*(?:%|倍|万|ms|QPS|qps|x|人|天)"), "补一个具体数字"),
    "ownership": ("你本人的动作", re.compile(r"我(?!们)(负责|设计|决定|写|推动|搭建|实现)"), "说清你本人做了什么"),
    "failure": ("失败场景", re.compile(r"(失败|降级|兜底|容错|回滚|异常|故障)"), "补一句失败时怎么兜底"),
    "scale": ("扩展性", re.compile(r"(扩展|水平|分片|扩容|10\s*倍|规模)"), "补一句规模上来以后怎么办"),
}
_EXPECTED = {
    "SYSTEM_DESIGN": ("trade_off", "scale", "failure"),
    "PROJECT_DEEP_DIVE": ("ownership", "metric", "trade_off"),
    "EXPERIENCE": ("ownership", "metric"),
    "BEHAVIORAL": ("ownership", "metric"),
    "KNOWLEDGE": ("trade_off",),
    "CODING": ("failure",),
}
_TECH_TERM = re.compile(r"(Redis|Kafka|MySQL|RAG|Agent|向量|缓存|分布式锁|消息队列|一致性|分库分表|微调|重排|K8s|Kubernetes)", re.I)
_DISCLOSURE = re.compile(r"(我们团队|我们这边|我们现在|目前我们|接下来我们|我们正在|这个岗位|这个团队|我们的挑战|我们遇到)")


class NudgeState(dict):
    """Live context passed by the caller (all optional)."""


def _topic(kind: str, text: str) -> str:
    compact = re.sub(r"\s+", "", text.lower())[:40]
    return f"{kind}:{compact}"


def _session_rows(session_id: str) -> list[dict[str, Any]]:
    return store.select("nudge_event", "session_id = ?", (session_id,), "created_at DESC", 50)


def _candidates(state: dict[str, Any]) -> list[dict[str, Any]]:
    answer = str(state.get("candidate_text") or "")
    qtype = str(state.get("question_type") or "").upper()
    out: list[dict[str, Any]] = []
    for dim in _EXPECTED.get(qtype, ()):
        label, pattern, hint = _DIMENSIONS[dim]
        if not pattern.search(answer):
            out.append({"kind": "MISSING_DIMENSION", "text": f"还没提到{label}：{hint}", "topic": dim,
                        "confidence": 0.75 if len(answer) >= 80 else 0.62})
    for term in dict.fromkeys(m.group(0) for m in _TECH_TERM.finditer(answer)):
        out.append({"kind": "LIKELY_FOLLOWUP", "text": f"可能被追问：{term} 的失败场景和你当时的取舍", "topic": term.lower(),
                    "confidence": 0.65})
        break
    for warning in state.get("fact_warnings") or []:
        text = str(warning.get("text") if isinstance(warning, dict) else warning)
        if text:
            out.append({"kind": "FACT_BOUNDARY", "text": f"「{text[:30]}」在材料中没有来源，避免继续展开", "topic": text[:30],
                        "confidence": 0.8})
            break
    disclosure = next((s for s in state.get("interviewer_recent") or [] if _DISCLOSURE.search(str(s))), "")
    if disclosure:
        out.append({"kind": "ASK_BACK_OPPORTUNITY", "text": f"可以在收尾时追问：{str(disclosure)[:40]}…具体指什么？",
                    "topic": str(disclosure)[:30], "confidence": 0.62})
    return out


def suppression_reason(state: dict[str, Any], rows: list[dict[str, Any]], now: float) -> Optional[str]:
    if not state.get("proactive_enabled", True):
        return "DISABLED"
    if state.get("candidate_speaking"):
        return "SPEECH_ACTIVE"
    if state.get("new_question_pending"):
        return "NEW_QUESTION"
    if str(state.get("cue_state") or "") in ("PREPARING", "STREAMING"):
        return "CUE_PRIORITY"
    if any(r["status"] == "SHOWN" for r in rows):
        return "ONE_AT_A_TIME"
    shown = [r for r in rows if r["status"] in ("SHOWN", "DISMISSED", "USED")]
    if shown and now - float(shown[0]["created_at"]) < COOLDOWN_S:
        return "COOLDOWN"
    if len(str(state.get("candidate_text") or "")) < MIN_ANSWER_CHARS and not state.get("interviewer_recent"):
        return "NOT_ENOUGH_CONTEXT"
    return None


def evaluate(session_id: str, state: dict[str, Any]) -> dict[str, Any]:
    """Return {'nudge': row|None, 'suppressed': reason|None}."""
    now = store.now()
    rows = _session_rows(session_id)
    reason = suppression_reason(state, rows, now)
    if reason:
        return {"nudge": None, "suppressed": reason}
    seen_topics = {r["topic_key"] for r in rows}
    answer = str(state.get("candidate_text") or "").lower()
    for cand in sorted(_candidates(state), key=lambda c: -c["confidence"]):
        if cand["confidence"] < CONFIDENCE_THRESHOLD:
            continue
        key = _topic(cand["kind"], cand["topic"])
        if key in seen_topics:
            continue  # duplicate suppression
        if cand["kind"] == "LIKELY_FOLLOWUP" and ("失败" in answer or "兜底" in answer):
            continue  # already mentioned
        row = {"id": store.new_id("nd_"), "session_id": session_id, "kind": cand["kind"], "text": cand["text"],
               "topic_key": key, "status": "SHOWN", "reason": "", "created_at": now, "updated_at": now}
        store.insert("nudge_event", row)
        events.record("nudge_shown", session_id=session_id, kind=cand["kind"])
        return {"nudge": {**row, "priority": PRIORITY["NUDGE"], "confidence": cand["confidence"]}, "suppressed": None}
    return {"nudge": None, "suppressed": "NO_CANDIDATE"}


def set_status(nudge_id: str, status: str) -> Optional[dict[str, Any]]:
    if status not in ("DISMISSED", "USED", "CANCELLED"):
        raise ValueError("状态无效")
    row = store.get("nudge_event", nudge_id)
    if row is None:
        return None
    store.update("nudge_event", nudge_id, {"status": status, "updated_at": store.now()})
    if status == "DISMISSED":
        events.record("nudge_dismissed", session_id=row["session_id"], kind=row["kind"])
    elif status == "USED":
        events.record("nudge_actioned", session_id=row["session_id"], kind=row["kind"])
    return store.get("nudge_event", nudge_id)


def cancel_on_new_question(session_id: str) -> int:
    """New-question cancellation: an open nudge never outlives its question."""
    with store.connect() as conn:
        return conn.execute(
            "UPDATE nudge_event SET status = 'CANCELLED', reason = 'NEW_QUESTION', updated_at = ? "
            "WHERE session_id = ? AND status = 'SHOWN'", (store.now(), session_id)).rowcount


def record_disabled(session_id: str = "") -> None:
    events.record("nudge_disabled", session_id=session_id)


def session_stats(session_id: str) -> dict[str, int]:
    out = {"SHOWN": 0, "DISMISSED": 0, "USED": 0, "CANCELLED": 0}
    for row in _session_rows(session_id):
        out[row["status"]] = out.get(row["status"], 0) + 1
    return out
