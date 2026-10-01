"""Closing Mode (canonical §15).

Recognises INTERVIEW_CLOSING ("你有什么想问我们的？") and CANDIDATE_QUESTION
(the candidate is about to ask) and proposes questions to ask back, built
from what actually happened in *this* interview: interviewer disclosures,
open threads, the Goal, and the user's "想问" Quick Notes. Generic questions
are used only when there is no context at all.

Output order: contextual follow-up → success criteria → team / technical
challenge → unresolved thread.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from services.storage import product as store

_CLOSING = re.compile(
    r"(你有什么(问题)?(想|要)?问(我们|我)?的?|有什么(问题)?想(了解|问)|你还有什么(问题|想问)|"
    r"我这边(的问题)?(就)?(问完|没有)了|今天(就)?(先)?到这|最后.{0,6}有什么问题|反问环节|"
    r"do you have any questions|any questions for (me|us))", re.I)
_CANDIDATE_Q = re.compile(r"^(我想问|想请教|请问|我有个问题|I'd like to ask|can I ask)", re.I)
_DISCLOSURE = re.compile(r"(我们团队|我们这边|我们现在|目前我们|接下来|我们正在|我们计划|这个岗位|这个团队|我们的挑战|"
                         r"我们遇到|业务上|今年|下半年|我们主要)")
_TECH = re.compile(r"(Agent|RAG|大模型|LLM|推理|训练|评测|数据|平台|架构|系统|服务|迁移|重构|增长|算法|产品)", re.I)

GENERIC = [
    "这个岗位前三个月做成什么样算是成功？",
    "团队目前最大的技术挑战是什么？",
    "团队的协作方式和评审流程是怎样的？",
]


def detect(text: str) -> Optional[str]:
    """INTERVIEW_CLOSING | CANDIDATE_QUESTION | None."""
    t = (text or "").strip()
    if not t:
        return None
    if _CLOSING.search(t):
        return "INTERVIEW_CLOSING"
    if _CANDIDATE_Q.search(t):
        return "CANDIDATE_QUESTION"
    return None


def _disclosures(transcript: list[dict[str, Any]]) -> list[str]:
    out = []
    for turn in transcript:
        speaker = str(turn.get("speaker") or turn.get("role") or "")
        text = str(turn.get("text") or "")
        if speaker in ("interviewer", "other", "counterparty") and _DISCLOSURE.search(text) and not detect(text):
            sentence = next((s for s in re.split(r"[。！？!?\n]", text) if _DISCLOSURE.search(s)), text)
            out.append(sentence.strip()[:80])
    return out


def suggest(
    *,
    goal: Optional[dict[str, Any]] = None,
    transcript: Optional[list[dict[str, Any]]] = None,
    ask_notes: Optional[list[dict[str, Any]]] = None,
    open_threads: Optional[list[str]] = None,
    limit: int = 4,
) -> list[dict[str, Any]]:
    transcript = transcript or []
    role = str((goal or {}).get("role") or "").strip()
    company = str((goal or {}).get("company") or "").strip()
    jd = str((goal or {}).get("jd") or "")
    items: list[dict[str, Any]] = []

    for d in _disclosures(transcript)[:2]:
        topic = _TECH.search(d)
        items.append({"kind": "CONTEXTUAL_FOLLOWUP", "source": "INTERVIEW_TRANSCRIPT",
                      "text": f"您刚才提到「{d[:36]}」，这块目前进展到哪一步了？" + (f"{topic.group(0)}方面最需要新人补上什么？" if topic else ""),
                      "basis": d})
    for note in (ask_notes or [])[:2]:
        content = str(note.get("content") or note.get("title") or "").strip()
        if content:
            items.append({"kind": "CONTEXTUAL_FOLLOWUP", "source": "QUICK_NOTE", "text": content[:120], "basis": "你的速记（想问）"})
    if role or company:
        who = f"{company}的{role}" if company and role else (role or company)
        items.append({"kind": "SUCCESS_CRITERIA", "source": "GOAL",
                      "text": f"对{who}来说，入职前三个月做成什么样会被认为是成功的？", "basis": "求职目标"})
    tech = list(dict.fromkeys(m.group(0) for m in _TECH.finditer(jd)))[:2]
    if tech:
        items.append({"kind": "TEAM_CHALLENGE", "source": "GOAL_JD",
                      "text": f"团队在{'、'.join(tech)}上现在最难的问题是什么？", "basis": "JD"})
    for thread in (open_threads or [])[:1]:
        items.append({"kind": "UNRESOLVED_THREAD", "source": "OPEN_THREAD",
                      "text": f"刚才关于「{thread[:30]}」我还想确认一下：…", "basis": thread[:60]})

    if not items:
        items = [{"kind": "GENERIC", "source": "DEFAULT", "text": q, "basis": "没有本场上下文时的通用问题"} for q in GENERIC]
    seen: set[str] = set()
    unique = []
    for item in items:
        if item["text"] not in seen:
            seen.add(item["text"])
            unique.append(item)
    return unique[:limit]


def record(session_id: str, trigger: str, suggestions: list[dict[str, Any]]) -> dict[str, Any]:
    row = {"id": store.new_id("cl_"), "session_id": session_id, "trigger": trigger,
           "suggestions": suggestions, "created_at": store.now()}
    store.insert("closing_mode_event", row)
    return row
