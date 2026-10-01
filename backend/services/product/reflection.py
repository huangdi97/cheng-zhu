"""Reflection 3.0 (canonical §18) and its write-back.

First screen: Next Step · What went well · What to improve · Fact checks ·
Story opportunities · Pinned moments (pins come first). The turn timeline is
the second layer. Every finding links back to the question, the candidate's
*actual speech* and a source; AI answers are never quoted as the user's
performance.

Every action writes back for real:
  PRACTICE_THIS / SET_NEXT_FOCUS -> NextFocus (USER origin) on the Goal
  CONFIRM_FACT / MARK_MISTAKE / DONT_REMEMBER -> session claim review
      (confirm / deny / forget) or Fact Inbox resolution
  ADD_SOURCE -> claim provenance via Fact Inbox
  CREATE_STORY -> a user-owned story draft built from the user's own words
  ADD_QUICK_NOTE -> Quick Note (origin REFLECTION, never auto-written)
and is logged as a ReflectionAction.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Optional

from core.logger import get_logger
from services.product import coach, events, pins
from services.product.next_focus import TYPES as FOCUS_TYPES
from services.product.rubrics import DIMENSIONS
from services.storage import product as store

_log = get_logger("product.reflection")

SESSION_KINDS = ("PRACTICE", "REVIEW")
ACTIONS = ("PRACTICE_THIS", "SET_NEXT_FOCUS", "CONFIRM_FACT", "MARK_MISTAKE", "ADD_SOURCE", "CREATE_STORY",
           "ADD_QUICK_NOTE", "DONT_REMEMBER")
_CODING_Q = re.compile(r"(代码|算法|复杂度|实现一个|写一个|leetcode|coding|function|class )", re.I)
_SD_Q = re.compile(r"(设计一个|系统设计|架构|扩展|容量|高可用|design)", re.I)
_BEHAVIORAL_Q = re.compile(r"(讲一次|讲一个|经历|冲突|失败|挑战|最难|最自豪|分歧|tell me about a time)", re.I)


class ReflectionError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Loading sessions (one source of truth per kind — never copied)
# ---------------------------------------------------------------------------


def _practice_turns(practice_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    session = store.get("practice_session", practice_id)
    if session is None:
        raise ReflectionError("练习不存在")
    turns = store.select("practice_turn", "practice_id = ?", (practice_id,), "seq ASC")
    out = [{"id": t["id"], "seq": t["seq"], "question": t["question"], "answer": t["answer"], "move": t["move"],
            "persona": t.get("persona_id", ""), "content": t.get("content") or {}, "delivery": t.get("delivery") or {},
            "source": t.get("question_source", "")} for t in turns if t["answer"]]
    return session, out


def _review_turns(review_id: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from services.storage import review as review_storage

    detail = review_storage.get_session_detail(int(review_id))
    if detail is None:
        raise ReflectionError("场次不存在")
    claims = _known_claims()
    out = []
    for t in detail.get("turns", []):
        speech = str(t.get("candidate_answer_text") or "").strip()
        content = coach.analyze_content(t.get("question_text", ""), speech, known_claims=claims) if speech else {
            "signals": {}, "findings": [], "strengths": []}
        out.append({"id": str(t.get("qa_id") or t.get("id")), "seq": t.get("seq"), "question": t.get("question_text", ""),
                    "answer": speech, "move": "OPEN", "persona": "", "content": content, "delivery": {},
                    "source": "LIVE", "review_risks": t.get("risks") or [], "review_strengths": t.get("strengths") or []})
    return detail, out


def _known_claims() -> list[dict[str, Any]]:
    try:
        from services.intelligence.job_workspace import active_claims

        return active_claims()
    except Exception:  # noqa: BLE001
        return []


def _links_for(kind: str, ref: str) -> dict[str, Any]:
    if kind == "PRACTICE":
        found = store.select("goal_session_link", "practice_id = ?", (ref,), limit=1)
    else:
        found = store.select("goal_session_link", "review_session_id = ?", (int(ref),), limit=1)
    return found[0] if found else {}


# ---------------------------------------------------------------------------
# Finding classification
# ---------------------------------------------------------------------------


def classify(finding: dict[str, Any], question: str) -> str:
    """Map a content finding to a Next Focus / reflection kind."""
    signal = finding.get("signal")
    if signal == "truth_boundary":
        return "FACT_BOUNDARY"
    if signal == "ownership":
        return "OWNERSHIP"
    if signal == "followup_resilience":
        return "FOLLOWUP_RESILIENCE"
    if _CODING_Q.search(question):
        return "CODING"
    if signal == "trade_off" and _SD_Q.search(question):
        return "SYSTEM_DESIGN"
    if signal == "structure":
        return "DELIVERY"
    return "KNOWLEDGE_GAP"


def _finding_id(turn_id: str, kind: str) -> str:
    return f"{turn_id}:{kind}"


def build(session_kind: str, session_ref: str) -> dict[str, Any]:
    if session_kind not in SESSION_KINDS:
        raise ReflectionError("未知场次类型")
    if session_kind == "PRACTICE":
        session, turns = _practice_turns(session_ref)
        goal_id = session.get("goal_id")
        pin_session_ids = [session_ref]
        title = "练习复盘"
        delivery_on = True
    else:
        detail, turns = _review_turns(int(session_ref))
        link = _links_for("REVIEW", session_ref)
        goal_id = link.get("goal_id")
        _observe_real_session(goal_id, str(session_ref), turns, link.get("session_kind") or "REAL")
        pin_session_ids = [x for x in (link.get("live_session_id"), str(session_ref)) if x]
        title = detail.get("title") or "面试复盘"
        delivery_on = False

    pinned: list[dict[str, Any]] = []
    for sid in pin_session_ids:
        pinned += pins.pins_for_session(sid)
    for sid in pin_session_ids:
        pins.mark_used_in_reflection(sid)

    improve: list[dict[str, Any]] = []
    went_well: list[dict[str, Any]] = []
    fact_checks: list[dict[str, Any]] = []
    story_ops: list[dict[str, Any]] = []
    for t in turns:
        content = t.get("content") or {}
        for f in content.get("findings", []):
            kind = classify(f, t["question"])
            item = {"id": _finding_id(t["id"], kind), "kind": kind, "kind_label": FOCUS_TYPES[kind]["label"],
                    "dimension": f["dimension"], "dimension_label": DIMENSIONS.get(f["dimension"], f["dimension"]),
                    "finding": f["finding"], "action_hint": f["action"], "turn_id": t["id"], "question": t["question"],
                    "actual_speech": f.get("evidence_from_actual_speech") or "", "source": t.get("source", "")}
            (fact_checks if kind == "FACT_BOUNDARY" else improve).append(item)
        for s in content.get("strengths", []):
            went_well.append({"dimension": s["dimension"], "dimension_label": DIMENSIONS.get(s["dimension"], s["dimension"]),
                              "turn_id": t["id"], "question": t["question"],
                              "actual_speech": s.get("evidence_from_actual_speech") or ""})
        signals = content.get("signals") or {}
        if _BEHAVIORAL_Q.search(t["question"]) and t["answer"] and signals.get("structure", 0) >= 3:
            story_ops.append({"id": _finding_id(t["id"], "STORY"), "kind": "STORY_GAP", "turn_id": t["id"],
                              "question": t["question"], "actual_speech": t["answer"][:160],
                              "hint": "这段回答可以整理成一个 Story，下次直接复用。"})
        if t["move"] == "CLOSING" and len(t["answer"]) < 12:
            improve.append({"id": _finding_id(t["id"], "CLOSING_QUESTION"), "kind": "CLOSING_QUESTION",
                            "kind_label": FOCUS_TYPES["CLOSING_QUESTION"]["label"], "dimension": "communication",
                            "dimension_label": DIMENSIONS["communication"], "finding": "收尾环节没有提出有针对性的问题。",
                            "action_hint": "提前记一条「想问」速记。", "turn_id": t["id"], "question": t["question"],
                            "actual_speech": t["answer"], "source": t.get("source", "")})

    fact_checks += _session_claim_checks(session_kind, session_ref, pin_session_ids)
    delivery = coach.summarize_delivery([t["delivery"] for t in turns if t.get("delivery")]) if delivery_on else []
    if delivery:
        improve.append({"id": f"{session_ref}:DELIVERY", "kind": "DELIVERY", "kind_label": FOCUS_TYPES["DELIVERY"]["label"],
                        "dimension": "communication", "dimension_label": DIMENSIONS["communication"],
                        "finding": delivery[0], "action_hint": "下一轮做 15 秒结论训练。", "turn_id": "", "question": "",
                        "actual_speech": "", "source": "DELIVERY_LOCAL"})

    improve = _rank(improve)
    next_step = _next_step(pinned, improve, fact_checks, goal_id)
    events.record("reflection_opened", goal_id=goal_id or "", session_id=str(session_ref), kind=session_kind,
                  pins=len(pinned))
    return {
        "session_kind": session_kind, "session_ref": str(session_ref), "goal_id": goal_id, "title": title,
        "first_screen": {
            "next_step": next_step,
            "pinned_moments": pinned,
            "went_well": went_well[:4],
            "to_improve": improve[:5],
            "fact_checks": fact_checks[:6],
            "story_opportunities": story_ops[:3],
        },
        "delivery": delivery,
        "timeline": [{"turn_id": t["id"], "seq": t["seq"], "question": t["question"], "actual_speech": t["answer"],
                      "move": t["move"], "persona": t["persona"], "content": t.get("content") or {},
                      "delivery": t.get("delivery") or {}, "review_risks": t.get("review_risks", []),
                      "review_strengths": t.get("review_strengths", [])} for t in turns],
        "actions": list(ACTIONS),
        "ask_cue_feedback": session_kind == "REVIEW" and not _has_feedback("REVIEW", str(session_ref)),
    }


def _observe_real_session(goal_id: Optional[str], ref: str, turns: list[dict[str, Any]], kind: str) -> None:
    """Rubric observations for a reviewed session (once), so Practice → Session
    transfer can compare the same dimensions on real interviews."""
    if store.select("rubric_observation", "session_ref = ?", (f"review:{ref}",), limit=1):
        return
    now = store.now()
    with store.connect() as conn:
        for t in turns:
            for dim, level in coach.rubric_levels(t.get("content") or {}).items():
                store.insert("rubric_observation", {
                    "id": store.new_id("ro_"), "goal_id": goal_id, "session_kind": kind if kind != "GUIDED" else "PRACTICE",
                    "session_ref": f"review:{ref}", "turn_ref": t["id"], "dimension": dim, "level": level,
                    "note": "REVIEW", "created_at": now}, conn=conn)


def _rank(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(i["kind"] for i in items)
    seen: set[str] = set()
    ranked = []
    for item in sorted(items, key=lambda i: -counts[i["kind"]]):
        if item["kind"] in seen:
            continue
        seen.add(item["kind"])
        ranked.append({**item, "occurrences": counts[item["kind"]]})
    return ranked


def _next_step(pinned: list[dict[str, Any]], improve: list[dict[str, Any]], fact_checks: list[dict[str, Any]],
               goal_id: Optional[str]) -> Optional[dict[str, Any]]:
    bad_pin = next((p for p in pinned if p["tag"] in ("BAD_ANSWER", "PREP_NEXT")), None)
    if bad_pin:
        return {"kind": "USER_PIN", "title": bad_pin["question"] or bad_pin["note"] or "你标记的时刻",
                "reason": "你在场次中标记了这一刻。", "pin_id": bad_pin["id"], "goal_id": goal_id}
    if improve:
        top = improve[0]
        return {"kind": top["kind"], "title": top["kind_label"], "reason": f"{top['finding']}（出现 {top['occurrences']} 次）",
                "finding_id": top["id"], "goal_id": goal_id}
    if fact_checks:
        return {"kind": "FACT_BOUNDARY", "title": "确认事实边界", "reason": "本场有说法需要确认。", "goal_id": goal_id}
    return None


def _session_claim_checks(kind: str, ref: str, pin_session_ids: list[str]) -> list[dict[str, Any]]:
    if kind != "REVIEW":
        return []
    try:
        from services.storage import intelligence as intel_storage
        from services.storage import review as review_storage

        detail = review_storage.get_session_detail(int(ref)) or {}
        qa_ids = [str(t.get("qa_id", "")) for t in detail.get("turns", []) if t.get("qa_id")]
        rows = intel_storage.list_session_claims_by_qa(qa_ids)
    except Exception as exc:  # noqa: BLE001
        _log.debug("session claims unavailable: %s", exc)
        return []
    return [{"id": f"sc:{r['id']}", "kind": "FACT_BOUNDARY", "session_claim_id": r["id"], "finding": "本场说过、材料中没有来源的说法",
             "actual_speech": r.get("text", ""), "question": "", "review_state": r.get("review_state", "")}
            for r in rows if r.get("review_state") in ("PENDING", "HOLD_NO_EVIDENCE", "HOLD_NO_EXPAND", "CORRECTED", "")]


# ---------------------------------------------------------------------------
# Actions (write-back)
# ---------------------------------------------------------------------------


def apply_action(
    action: str,
    *,
    session_kind: str,
    session_ref: str,
    finding: dict[str, Any],
    goal_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if action not in ACTIONS:
        raise ReflectionError(f"未知操作：{action}")
    payload = payload or {}
    goal_id = goal_id or _links_for(session_kind, session_ref).get("goal_id") or finding.get("goal_id")
    kind = str(finding.get("kind") or "KNOWLEDGE_GAP")
    result: dict[str, Any] = {}
    if action in ("PRACTICE_THIS", "SET_NEXT_FOCUS"):
        if not goal_id:
            raise ReflectionError("这场还没有关联求职目标，请先选择目标")
        from services.product.next_focus import practice_defaults, set_user_focus

        if finding.get("pin_id"):
            result["next_focus"] = pins.promote_to_focus(str(finding["pin_id"]), goal_id)
        else:
            title = str(finding.get("title") or finding.get("kind_label") or FOCUS_TYPES.get(kind, {}).get("label", kind))
            reason = str(finding.get("reason") or finding.get("finding") or "来自复盘")
            if finding.get("actual_speech"):
                reason += f"（你说的：「{str(finding['actual_speech'])[:40]}」）"
            result["next_focus"] = set_user_focus(goal_id, kind if kind in FOCUS_TYPES else "RUBRIC", title, reason,
                                                  source_kind="REFLECTION", source_ref=str(finding.get("id") or ""))
        if action == "PRACTICE_THIS":
            result["practice_defaults"] = practice_defaults(goal_id)
    elif action in ("CONFIRM_FACT", "MARK_MISTAKE", "DONT_REMEMBER"):
        decision = {"CONFIRM_FACT": "confirm", "MARK_MISTAKE": "deny", "DONT_REMEMBER": "forget"}[action]
        if finding.get("session_claim_id"):
            from services.intelligence import session_claims
            from services.storage import intelligence as intel_storage

            if action == "MARK_MISTAKE":
                session_claims.resolve(str(finding["session_claim_id"]), "slip")
            result["session_claim"] = session_claims.confirm_in_review(
                str(finding["session_claim_id"]), candidate_id=intel_storage.active_candidate_id() or "local",
                decision=decision)
        elif finding.get("claim_id"):
            from services.product.fact_inbox import resolve

            result["fact"] = resolve(str(finding["claim_id"]), {"confirm": "CONFIRM", "deny": "DENY",
                                                                "forget": "DISMISS"}[decision])
        else:
            result["noted"] = decision
    elif action == "ADD_SOURCE":
        if not finding.get("claim_id"):
            raise ReflectionError("这条发现没有对应的长期事实，无法补来源")
        from services.product.fact_inbox import resolve

        result["fact"] = resolve(str(finding["claim_id"]), "ADD_SOURCE", payload)
    elif action == "CREATE_STORY":
        result["story"] = _create_story_draft(finding, payload)
    elif action == "ADD_QUICK_NOTE":
        from services.product.quick_notes import create_note

        content = str(payload.get("content") or finding.get("action_hint") or finding.get("finding") or "").strip()
        result["quick_note"] = create_note(content, title=str(payload.get("title") or finding.get("kind_label") or "复盘"),
                                           scope="GOAL" if goal_id else "GLOBAL", goal_id=goal_id, origin="REFLECTION",
                                           tags=payload.get("tags"))
    row = {"id": store.new_id("ra_"), "goal_id": goal_id, "session_kind": session_kind, "session_ref": str(session_ref),
           "finding_id": str(finding.get("id") or ""), "finding_kind": kind, "action": action,
           "payload": {k: v for k, v in payload.items() if k in ("tags", "source_ids")}, "result": _brief(result),
           "created_at": store.now()}
    store.insert("reflection_action", row)
    events.record("reflection_action", goal_id=goal_id or "", session_id=str(session_ref), action=action, kind=kind)
    if finding.get("pin_id") and action in ("PRACTICE_THIS", "SET_NEXT_FOCUS"):
        pass  # next_focus_from_pin recorded by pins.promote_to_focus
    elif action == "CREATE_STORY" and str(finding.get("source") or "") == "PIN":
        events.record("story_from_pin", goal_id=goal_id or "")
    return {"action": action, "reflection_action_id": row["id"], **result}


def _brief(result: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, value in result.items():
        if isinstance(value, dict):
            out[key] = {k: value.get(k) for k in ("id", "type", "title", "long_term_claim_id") if k in value}
        else:
            out[key] = value if isinstance(value, (str, int, float, bool)) else None
    return out


def _create_story_draft(finding: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Draft from the user's own words only — no invented events."""
    from services.storage import intelligence as intel_storage

    candidate_id = intel_storage.active_candidate_id() or "local"
    speech = str(payload.get("situation") or finding.get("actual_speech") or "").strip()
    if not speech:
        raise ReflectionError("这条发现没有你的原话，无法生成 Story 草稿")
    story_id = f"story_{store.new_id()}"
    title = str(payload.get("title") or finding.get("question") or "复盘中的故事")[:80]
    category = str(payload.get("category") or "")
    intel_storage.save_story(story_id, candidate_id, {
        "title": title, "situation": speech[:2000], "challenge": "", "action": "", "result": "",
        "reflection": "", "truth_status": "UNKNOWN"}, tags=[t for t in [category, "draft"] if t])
    return {"id": story_id, "title": title, "draft": True}


def _has_feedback(kind: str, ref: str) -> bool:
    return bool(store.select("session_feedback", "session_kind = ? AND session_ref = ?", (kind, ref), limit=1))


def record_feedback(session_kind: str, session_ref: str, question: str, answer: str) -> dict[str, Any]:
    if question != "fast_cue_helpful" or answer not in ("YES", "SOMEWHAT", "NO"):
        raise ReflectionError("反馈无效")
    row = {"id": store.new_id("fb_"), "session_kind": session_kind, "session_ref": str(session_ref),
           "question": question, "answer": answer, "created_at": store.now()}
    with store.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO session_feedback (id, session_kind, session_ref, question, answer, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?)", tuple(row.values()))
    events.record("session_feedback", session_id=str(session_ref), answer=answer)
    return row


def actions_for_goal(goal_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return store.select("reflection_action", "goal_id = ?", (goal_id,), "created_at DESC", limit)
