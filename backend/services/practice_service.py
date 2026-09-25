"""模拟面试练习服务：AI 面试官逐题提问、基于回答追问、逐题评分反馈、整场落库复盘。

练习会话保存在内存（本地单用户足够）；结束时把整场问答写入「面试复盘」，
复用 review 的逐题分析与整场总结链路。
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from typing import Any, Optional

from core.config import get_config
from core.logger import get_logger
from services import prep_service, review_analysis
from services.storage import prep_space as prep_storage
from services.storage import review as review_storage

logger = get_logger("practice.service")

_PRACTICE_LOCK = threading.Lock()
_SESSIONS: dict[str, dict[str, Any]] = {}

MIN_ROUNDS = 1
MAX_ROUNDS = 12


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _ensure_questions(space: dict[str, Any]) -> list[dict[str, Any]]:
    """准备空间已生成真题则直接使用，否则现场生成并回存。"""
    questions = space.get("questions") or []
    if questions:
        return [q for q in questions if isinstance(q, dict) and str(q.get("question") or "").strip()]
    role = space.get("role") or ""
    company = space.get("company") or ""
    jd = space.get("jd_text") or ""
    resume = space.get("resume_text") or ""
    insight = space.get("insight_markdown") or ""
    cards = [c.get("card", {}) for c in space.get("skill_cards", []) if isinstance(c, dict)]
    generated = prep_service.generate_questions(role, company, jd, resume, insight, cards)
    prep_storage.update_questions(space["id"], generated, "done")
    return generated


def _weak_keywords(profile: dict[str, Any]) -> list[str]:
    """把画像里的弱项文本拆成关键词，用于出题命中。"""
    terms: list[str] = []
    for w in profile.get("weaknesses", [])[:10]:
        if not isinstance(w, str):
            continue
        # 拆掉常见修饰词，保留主题词
        cleaned = re.sub(r"(深度|广度|不够|不足|欠缺|缺少|较弱|薄弱|回答|讲解|表达|细节|案例|实战|经验)$", "", w.strip())
        cleaned = cleaned.strip("，。、；:： ")
        if cleaned and len(cleaned) >= 2 and cleaned not in terms:
            terms.append(cleaned)
    return terms[:8]


def _order_by_weak_points(
    questions: list[dict[str, Any]],
    weak_terms: list[str],
) -> list[dict[str, Any]]:
    """按弱项命中度稳定排序：命中弱项的题优先，其余保持原顺序。"""
    if not weak_terms or not questions:
        return questions

    def _score(q: dict[str, Any]) -> int:
        text = f"{q.get('question') or ''} {q.get('why') or ''} {q.get('type') or ''}"
        return sum(1 for term in weak_terms if term and term in text)

    return sorted(questions, key=lambda q: -_score(q))


def _pick_next(session: dict[str, Any]) -> Optional[dict[str, Any]]:
    """优先使用上一题分析里生成的「可能追问」实现真实追问，否则用预测真题池。"""
    if session["pending_followups"]:
        q = session["pending_followups"].pop(0)
        return {"question": q, "type": "follow_up", "why": "基于你上一题回答的追问"}
    pool = session["question_pool"]
    if session["cursor"] < len(pool):
        item = pool[session["cursor"]]
        session["cursor"] += 1
        return {
            "question": str(item.get("question") or "").strip(),
            "type": str(item.get("type") or "technical").strip()[:20],
            "why": str(item.get("why") or "").strip(),
        }
    return None


def start_session(space_id: int, rounds: int = 5) -> dict[str, Any]:
    space = prep_storage.get_space(space_id)
    if not space:
        raise ValueError("准备空间不存在")
    questions = _ensure_questions(space)
    if not questions:
        raise ValueError("没有可用的面试题，请先在准备空间生成预测真题")
    rounds = max(MIN_ROUNDS, min(int(rounds or 5), MAX_ROUNDS))
    pid = _new_id()
    # 长期画像闭环：读最近复盘弱项，优先命中薄弱点的题
    profile = review_storage.recent_profile(limit=6)
    weak_terms = _weak_keywords(profile)
    ordered_pool = _order_by_weak_points(questions, weak_terms)
    session: dict[str, Any] = {
        "id": pid,
        "space_id": space_id,
        "rounds": rounds,
        "cursor": 0,
        "question_pool": ordered_pool,
        "pending_followups": [],
        "turns": [],
        "current_question": None,
        "status": "active",
        "created_at": time.time(),
        "weak_terms": weak_terms,
    }
    session["current_question"] = _pick_next(session)
    with _PRACTICE_LOCK:
        _SESSIONS[pid] = session
    return {
        "practice_id": pid,
        "question": session["current_question"],
        "rounds": rounds,
        "weak_points": profile.get("weaknesses", [])[:5],
        "weak_terms": weak_terms,
    }


def get_session(practice_id: str) -> Optional[dict[str, Any]]:
    with _PRACTICE_LOCK:
        return _SESSIONS.get(practice_id)


def _feedback_payload(turn: dict[str, Any]) -> dict[str, Any]:
    analysis = turn.get("analysis") or {}
    evidence = analysis.get("evidence") or {}
    return {
        "strengths": analysis.get("strengths", []),
        "risks": analysis.get("risks", []),
        "scorecard": analysis.get("scorecard", {}),
        "improvement_advice": evidence.get("improvement_advice", ""),
        "follow_up_questions": evidence.get("follow_up_questions", []),
        "tags": evidence.get("tags", []),
    }


def _avg_score(turns: list[dict[str, Any]]) -> Optional[float]:
    values: list[float] = []
    for t in turns:
        scorecard = (t.get("analysis") or {}).get("scorecard") or {}
        for v in scorecard.values():
            try:
                values.append(float(v))
            except (TypeError, ValueError):
                pass
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _build_report(session: dict[str, Any]) -> dict[str, Any]:
    turns = session["turns"]
    space = prep_storage.get_space(session["space_id"]) or {}
    role = space.get("role") or ""
    company = space.get("company") or ""
    title = f"模拟面试 - {role}" if role else "模拟面试"

    summary_turns = [
        {
            "question_text": t["question"].get("question", ""),
            "candidate_answer_text": t.get("answer", ""),
            "strengths": (t.get("analysis") or {}).get("strengths", []),
            "risks": (t.get("analysis") or {}).get("risks", []),
        }
        for t in turns
    ]
    summary = review_analysis.generate_summary(summary_turns, review_source="practice")
    summary_markdown = summary.get("summary_markdown", "")
    strong_points = summary.get("strong_points", [])
    weak_points = summary.get("weak_points", [])

    review_session_id = review_storage.create_session(
        started_at=session["created_at"],
        interviewer_enabled=True,
        candidate_enabled=True,
        source="practice",
        title=title,
        company=company,
        role=role,
    )
    for idx, t in enumerate(turns, start=1):
        analysis = t.get("analysis") or {}
        review_storage.add_turn(
            session_id=review_session_id,
            qa_id=f"practice-{session['id']}-{idx}",
            seq=idx,
            question_text=t["question"].get("question", ""),
            candidate_answer_text=t.get("answer", ""),
            analysis_status="completed",
            strengths=analysis.get("strengths", []),
            risks=analysis.get("risks", []),
            evidence=analysis.get("evidence", {}),
            scorecard=analysis.get("scorecard", {}),
        )
    review_storage.end_session(
        review_session_id,
        status="completed",
        ended_at=time.time(),
        summary_markdown=summary_markdown,
        strong_points=strong_points,
        weak_points=weak_points,
    )

    return {
        "review_session_id": review_session_id,
        "summary_markdown": summary_markdown,
        "strong_points": strong_points,
        "weak_points": weak_points,
        "turn_count": len(turns),
        "avg_score": _avg_score(turns),
    }


def submit_answer(practice_id: str, answer: str) -> dict[str, Any]:
    answer = (answer or "").strip()
    if not answer:
        raise ValueError("回答不能为空")
    session = get_session(practice_id)
    if not session:
        raise ValueError("练习会话不存在或已结束")
    if session["status"] != "active":
        raise ValueError("练习已结束")
    question = session.get("current_question")
    if not question:
        raise ValueError("当前没有待回答问题")

    analysis = review_analysis.analyze_turn(
        question.get("question", ""),
        answer,
        reference_answer="",
        apply_asr_correction=False,
        review_source="practice",
    )
    turn = {"question": question, "answer": answer, "analysis": analysis}
    session["turns"].append(turn)

    followups = (analysis.get("evidence") or {}).get("follow_up_questions", [])
    session["pending_followups"] = [str(x) for x in followups][:2]

    feedback = _feedback_payload(turn)
    answered = len(session["turns"])
    if answered >= session["rounds"]:
        session["status"] = "finished"
        report = _build_report(session)
        return {"done": True, "answered": answered, "feedback": feedback, "report": report}

    next_question = _pick_next(session)
    session["current_question"] = next_question
    return {"done": False, "answered": answered, "feedback": feedback, "next_question": next_question}


def finish_session(practice_id: str) -> dict[str, Any]:
    session = get_session(practice_id)
    if not session:
        raise ValueError("练习会话不存在")
    if session["status"] != "active":
        raise ValueError("练习已结束")
    if not session["turns"]:
        raise ValueError("还没有任何回答，无法结束")
    session["status"] = "finished"
    report = _build_report(session)
    return {"done": True, "report": report}