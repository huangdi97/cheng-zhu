"""Goal-centered Practice 3.0 service.

The verified v1.2 review/evidence pipeline remains authoritative.  v1.3 adds
round/persona/demeanor/difficulty, question banks, panel turn-taking, separate
content/delivery feedback, and Reflection -> Next Focus write-back.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from typing import Any, Optional

from core.logger import get_logger
from services import prep_service, review_analysis
from services.storage import prep_space as prep_storage
from services.storage import product_experience as product_storage
from services.storage import review as review_storage

logger = get_logger("practice.service")

_PRACTICE_LOCK = threading.Lock()
_SESSIONS: dict[str, dict[str, Any]] = {}

MIN_ROUNDS = 1
MAX_ROUNDS = 12

_DEFAULT_CONFIG: dict[str, Any] = {
    "round_type": "technical",
    "persona": "Tech Lead",
    "demeanor": "neutral",
    "difficulty": "standard",
    "question_bank_ids": [],
    "panel_personas": [],
}

_ALLOWED_DEMEANOR = {"neutral", "friendly", "skeptical", "strong_followup", "fast_paced"}
_ALLOWED_DIFFICULTY = {"warmup", "standard", "pressure"}


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _normalize_config(raw: Optional[dict[str, Any]]) -> dict[str, Any]:
    cfg = {**_DEFAULT_CONFIG, **(raw or {})}
    demeanor = str(cfg.get("demeanor") or "neutral").strip().lower()
    difficulty = str(cfg.get("difficulty") or "standard").strip().lower()
    cfg["demeanor"] = demeanor if demeanor in _ALLOWED_DEMEANOR else "neutral"
    cfg["difficulty"] = difficulty if difficulty in _ALLOWED_DIFFICULTY else "standard"
    cfg["round_type"] = str(cfg.get("round_type") or "technical").strip()[:60]
    cfg["persona"] = str(cfg.get("persona") or "Tech Lead").strip()[:120]
    cfg["question_bank_ids"] = [
        int(v) for v in (cfg.get("question_bank_ids") or []) if str(v).isdigit()
    ][:8]
    panel = []
    for item in cfg.get("panel_personas") or []:
        if isinstance(item, dict):
            role = str(item.get("role") or item.get("name") or "").strip()
            if role:
                panel.append(
                    {
                        "role": role[:120],
                        "demeanor": str(item.get("demeanor") or cfg["demeanor"])[:40],
                        "domain": str(item.get("domain") or "")[:120],
                    }
                )
        elif str(item or "").strip():
            panel.append({"role": str(item).strip()[:120], "demeanor": cfg["demeanor"], "domain": ""})
    cfg["panel_personas"] = panel[:3]
    return cfg


def _ensure_questions(space: dict[str, Any]) -> list[dict[str, Any]]:
    questions = space.get("questions") or []
    if questions:
        return [q for q in questions if isinstance(q, dict) and str(q.get("question") or "").strip()]
    generated = prep_service.generate_questions(
        space.get("role") or "",
        space.get("company") or "",
        space.get("jd_text") or "",
        space.get("resume_text") or "",
        space.get("insight_markdown") or "",
        [c.get("card", {}) for c in space.get("skill_cards", []) if isinstance(c, dict)],
    )
    prep_storage.update_questions(space["id"], generated, "done")
    return generated


def _weak_keywords(profile: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for weak in profile.get("weaknesses", [])[:10]:
        if not isinstance(weak, str):
            continue
        cleaned = re.sub(
            r"(深度|广度|不够|不足|欠缺|缺少|较弱|薄弱|回答|讲解|表达|细节|案例|实战|经验)$",
            "",
            weak.strip(),
        ).strip("，。、；:： ")
        if cleaned and len(cleaned) >= 2 and cleaned not in terms:
            terms.append(cleaned)
    return terms[:8]


def _order_by_weak_points(
    questions: list[dict[str, Any]], weak_terms: list[str]
) -> list[dict[str, Any]]:
    if not weak_terms or not questions:
        return questions

    def score(q: dict[str, Any]) -> int:
        text = f"{q.get('question') or ''} {q.get('why') or ''} {q.get('type') or ''}"
        return sum(1 for term in weak_terms if term and term in text)

    return sorted(questions, key=lambda q: -score(q))


def _gap_focus(space: dict[str, Any]) -> dict[str, Any]:
    try:
        from services.intelligence.job_workspace import mock_gap_focus

        return mock_gap_focus(space.get("jd_text") or "", space.get("resume_text") or "")
    except Exception as exc:  # noqa: BLE001
        logger.warning("practice gap focus unavailable: %s", exc)
        return {"terms": [], "questions": []}


def _merge_gap_questions(
    gap_questions: list[dict[str, Any]], pool: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    existing = {str(q.get("question") or "").strip() for q in pool}
    fresh = [q for q in gap_questions if str(q.get("question") or "").strip() not in existing]
    if not fresh:
        return pool
    merged: list[dict[str, Any]] = pool[:1]
    rest = pool[1:]
    for gap_q in fresh:
        merged.append(gap_q)
        if rest:
            merged.append(rest.pop(0))
    return merged + rest


def _bank_questions(bank_ids: list[int]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in product_storage.list_question_items(bank_ids):
        question = str(item.get("question") or "").strip()
        if question:
            result.append(
                {
                    "question": question,
                    "type": str(item.get("category") or "general"),
                    "why": f"来自题库 · {item.get('origin') or 'UNKNOWN'}",
                    "difficulty": str(item.get("difficulty") or "standard"),
                    "origin": str(item.get("origin") or "USER_ADDED"),
                }
            )
    return result


def _persona_for_turn(session: dict[str, Any]) -> dict[str, str]:
    cfg = session["config"]
    panel = cfg.get("panel_personas") or []
    if panel:
        idx = len(session["turns"]) % len(panel)
        p = panel[idx]
        return {
            "role": str(p.get("role") or "Interviewer"),
            "demeanor": str(p.get("demeanor") or cfg["demeanor"]),
            "domain": str(p.get("domain") or ""),
        }
    return {"role": cfg["persona"], "demeanor": cfg["demeanor"], "domain": cfg["round_type"]}


def _decorate_question(session: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    persona = _persona_for_turn(session)
    return {
        "question": str(item.get("question") or "").strip(),
        "type": str(item.get("type") or "technical").strip()[:40],
        "why": str(item.get("why") or "").strip(),
        "origin": str(item.get("origin") or "GOAL"),
        "persona": persona,
        "round_type": session["config"]["round_type"],
        "difficulty": session["config"]["difficulty"],
    }


def _pick_next(session: dict[str, Any]) -> Optional[dict[str, Any]]:
    if session["pending_followups"]:
        q = session["pending_followups"].pop(0)
        return _decorate_question(
            session,
            {"question": q, "type": "follow_up", "why": "基于上一题真实回答的追问", "origin": "ADAPTIVE"},
        )

    pool = session["question_pool"]
    if session["cursor"] < len(pool):
        item = pool[session["cursor"]]
        session["cursor"] += 1
        return _decorate_question(session, item)
    return None


def _delivery_feedback(answer: str) -> dict[str, Any]:
    text = (answer or "").strip()
    chars = len(text)
    sentence_count = max(1, len(re.findall(r"[。！？.!?]", text)))
    first_break = re.search(r"[。！？.!?]", text)
    conclusion_chars = first_break.start() if first_break else min(chars, 80)
    findings: list[str] = []
    if chars > 900:
        findings.append("回答偏长；下一轮先给结论，再补两到三个关键点")
    if conclusion_chars > 180:
        findings.append("结论出现偏晚；尝试在前两句直接回答问题")
    if sentence_count > 10:
        findings.append("信息密度较高；可以减少重复并明确段落层级")
    return {
        "answer_chars": chars,
        "sentence_count": sentence_count,
        "time_to_conclusion_proxy_chars": conclusion_chars,
        "findings": findings,
    }


def start_session(
    space_id: int,
    rounds: int = 5,
    config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    space = prep_storage.get_space(space_id)
    if not space:
        raise ValueError("准备空间不存在")

    cfg = _normalize_config(config)
    questions = _ensure_questions(space)
    bank_questions = _bank_questions(cfg["question_bank_ids"])
    if not questions and not bank_questions:
        raise ValueError("没有可用的面试题，请先生成岗位问题或选择题库")

    rounds = max(MIN_ROUNDS, min(int(rounds or 5), MAX_ROUNDS))
    profile = review_storage.recent_profile(limit=6)
    gap_focus = _gap_focus(space)
    weak_terms = list(dict.fromkeys([*_weak_keywords(profile), *gap_focus["terms"]]))[:10]

    base = _order_by_weak_points(questions, weak_terms)
    pool = _merge_gap_questions(gap_focus["questions"], base)
    # User-selected banks supplement the Goal graph, but do not erase Goal context.
    if bank_questions:
        pool = pool[:1] + bank_questions + pool[1:]

    pid = _new_id()
    session: dict[str, Any] = {
        "id": pid,
        "space_id": space_id,
        "rounds": rounds,
        "cursor": 0,
        "question_pool": pool,
        "pending_followups": [],
        "turns": [],
        "current_question": None,
        "status": "active",
        "created_at": time.time(),
        "weak_terms": weak_terms,
        "config": cfg,
    }
    session["current_question"] = _pick_next(session)
    with _PRACTICE_LOCK:
        _SESSIONS[pid] = session

    product_storage.record_event(
        "practice_started",
        goal_id=space_id,
        session_id=pid,
        payload={
            "round_type": cfg["round_type"],
            "demeanor": cfg["demeanor"],
            "difficulty": cfg["difficulty"],
            "panel_size": len(cfg["panel_personas"]),
        },
    )
    return {
        "practice_id": pid,
        "question": session["current_question"],
        "rounds": rounds,
        "weak_points": profile.get("weaknesses", [])[:5],
        "weak_terms": weak_terms,
        "gap_focus": gap_focus["terms"],
        "config": cfg,
    }


def get_session(practice_id: str) -> Optional[dict[str, Any]]:
    with _PRACTICE_LOCK:
        return _SESSIONS.get(practice_id)


def _feedback_payload(turn: dict[str, Any]) -> dict[str, Any]:
    analysis = turn.get("analysis") or {}
    evidence = analysis.get("evidence") or {}
    return {
        "content": {
            "strengths": analysis.get("strengths", []),
            "risks": analysis.get("risks", []),
            "scorecard": analysis.get("scorecard", {}),
            "improvement_advice": evidence.get("improvement_advice", ""),
            "follow_up_questions": evidence.get("follow_up_questions", []),
            "tags": evidence.get("tags", []),
        },
        "delivery": turn.get("delivery") or {},
        # Backward-compatible top-level fields used by the v1.2 UI.
        "strengths": analysis.get("strengths", []),
        "risks": analysis.get("risks", []),
        "scorecard": analysis.get("scorecard", {}),
        "improvement_advice": evidence.get("improvement_advice", ""),
        "follow_up_questions": evidence.get("follow_up_questions", []),
        "tags": evidence.get("tags", []),
    }


def _avg_score(turns: list[dict[str, Any]]) -> Optional[float]:
    values: list[float] = []
    for turn in turns:
        for value in ((turn.get("analysis") or {}).get("scorecard") or {}).values():
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                pass
    return round(sum(values) / len(values), 1) if values else None


def _write_next_focus(space_id: int, weak_points: list[str]) -> None:
    items = [
        {
            "type": "practice",
            "title": str(text)[:160],
            "reason": "来自刚结束的 Practice Reflection",
            "action": "PRACTICE",
            "priority": "high" if idx == 0 else "normal",
        }
        for idx, text in enumerate(weak_points[:3])
        if str(text).strip()
    ]
    if items:
        product_storage.upsert_goal_meta(space_id, next_focus=items)
        product_storage.record_event(
            "next_focus_changed", goal_id=space_id, payload={"source": "practice_reflection", "count": len(items)}
        )


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
    for idx, turn in enumerate(turns, start=1):
        analysis = turn.get("analysis") or {}
        evidence = dict(analysis.get("evidence", {}) or {})
        evidence["practice_persona"] = turn["question"].get("persona")
        evidence["delivery"] = turn.get("delivery") or {}
        review_storage.add_turn(
            session_id=review_session_id,
            qa_id=f"practice-{session['id']}-{idx}",
            seq=idx,
            question_text=turn["question"].get("question", ""),
            candidate_answer_text=turn.get("answer", ""),
            analysis_status="completed",
            strengths=analysis.get("strengths", []),
            risks=analysis.get("risks", []),
            evidence=evidence,
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

    _write_next_focus(session["space_id"], weak_points)
    product_storage.record_event(
        "practice_completed",
        goal_id=session["space_id"],
        session_id=session["id"],
        payload={"turn_count": len(turns), "review_session_id": review_session_id},
    )

    delivery_findings = []
    for turn in turns:
        delivery_findings.extend((turn.get("delivery") or {}).get("findings") or [])
    return {
        "review_session_id": review_session_id,
        "summary_markdown": summary_markdown,
        "strong_points": strong_points,
        "weak_points": weak_points,
        "turn_count": len(turns),
        "avg_score": _avg_score(turns),
        "content_coach": {"strong_points": strong_points, "weak_points": weak_points},
        "delivery_coach": {"findings": list(dict.fromkeys(delivery_findings))[:8]},
        "practice_config": session["config"],
    }


def _pressure_followup(question: str, answer: str, cfg: dict[str, Any]) -> list[str]:
    if cfg["difficulty"] != "pressure" and cfg["demeanor"] not in {"skeptical", "strong_followup"}:
        return []
    answer = (answer or "").strip()
    if len(answer) < 80:
        return [f"你的回答还比较概括。针对“{question[:45]}”，请给一个具体例子或量化依据。"]
    if cfg["demeanor"] == "skeptical":
        return ["如果我不同意这个判断，你最关键的证据或 trade-off 是什么？"]
    return ["继续往下讲：这里最大的失败模式是什么，你会如何验证？"]


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
    turn = {
        "question": question,
        "answer": answer,
        "analysis": analysis,
        "delivery": _delivery_feedback(answer),
    }
    session["turns"].append(turn)

    model_followups = [str(x) for x in ((analysis.get("evidence") or {}).get("follow_up_questions", [])) if str(x).strip()]
    pressure = _pressure_followup(question.get("question", ""), answer, session["config"])
    session["pending_followups"] = list(dict.fromkeys([*pressure, *model_followups]))[:2]

    feedback = _feedback_payload(turn)
    answered = len(session["turns"])
    if answered >= session["rounds"]:
        session["status"] = "finished"
        report = _build_report(session)
        return {"done": True, "answered": answered, "feedback": feedback, "report": report}

    next_question = _pick_next(session)
    session["current_question"] = next_question
    return {
        "done": False,
        "answered": answered,
        "feedback": feedback,
        "next_question": next_question,
    }


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
