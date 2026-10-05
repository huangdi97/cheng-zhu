"""Longitudinal synthetic dogfood (v1.4 §Longitudinal).

Drives the real product services through a fixed profile over simulated
days / sessions and checks continuity:

  Day 1 Resume + Goal · Day 2 Prepare + Practice · Day 3 Practice ·
  Day 4 Interview (mock review session) · Day 5 Reflection · Day 6 Reopen Goal ·
  Day 7 Practice the same weakness

Checks: state continuity, Next Focus, materials, quick notes, pins, story,
fact inbox, progress trend, and no cross-Goal context contamination.

This is SYNTHETIC evidence. It marks the store with ``dogfood_synthetic`` so
the validation report never presents it as real-user data. Run it only
against an isolated data directory (scripts/dogfood_longitudinal.py does).
"""
from __future__ import annotations

from typing import Any, Callable

from services.product import (events, fact_inbox, goals, live, materials, next_focus, pins, practice, quick_notes,
                              reflection, trends, validation)
from services.storage import product as store

DAY = 86400.0
PROFILE_RESUME = ("WenNian 项目：参与设计 RAG 架构，负责检索链路的重排模块，P95 延迟从 900ms 降到 400ms。\n"
                  "技能：熟悉 Python、Redis、Kafka。")
WEAK_ANSWER = "我们团队一起做的，大家一起讨论，最后上线了，效果还可以。"
STRONG_ANSWER = ("结论是我负责重排模块：我设计了两阶段召回，取舍是牺牲 5% 召回换 50% 延迟，代价是要维护缓存。"
                 "P95 从 900ms 降到 400ms。")


class Clock:
    def __init__(self, start: float):
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _practice(goal_id: str, answers: list[str], **cfg: Any) -> dict[str, Any]:
    base = {"goal_id": goal_id, "round": cfg.pop("round", "PROJECT_DEEP_DIVE"), "sources": ["RECENT_WEAKNESS", "ROLE_BANK"],
            "questions": len(answers), "closing": False, **cfg}
    s = practice.start(base)
    result: dict[str, Any] = {}
    for ans in answers:
        result = practice.answer(s["practice_id"], ans)
        if result.get("done"):
            break
    if not result.get("done"):
        practice.finish(s["practice_id"])
    return s


def _setup_candidate() -> None:
    from services.storage import intelligence as intel

    intel.save_candidate_profile("dogfood", profile_text=PROFILE_RESUME)
    intel.save_claims("dogfood", [
        {"id": "df-lead", "text": "我负责完整 RAG 架构设计", "truth_status": "INFERRED"},
        {"id": "df-redis", "text": "熟悉 Redis", "truth_status": "SUPPORTED"},
    ])


def run_week(set_clock: Callable[[Callable[[], float]], None]) -> dict[str, Any]:
    """7-day continuity. ``set_clock`` installs the simulated clock as store.now."""
    clock = Clock(1_790_000_000.0)
    set_clock(clock)
    store.meta_set(validation.SYNTHETIC_MARKER, "1")
    checks: dict[str, bool] = {}

    # Day 1 — resume + goals (and a second goal to test contamination)
    _setup_candidate()
    goal = goals.create_goal("MindRank", "AIDD Agent Engineer", "任职要求：\n熟悉 RAG\n熟悉 Redis 高可用\n系统设计能力")
    other = goals.create_goal("德睿智药", "AI Product", "负责 AI 产品规划")
    note = quick_notes.create_note("想问：团队现在最大的挑战？", scope="GOAL", goal_id=goal["id"], pinned=True, tags=["想问"])
    other_note = quick_notes.create_note("德睿专用：药物发现流程", scope="GOAL", goal_id=other["id"], pinned=True)
    mat = materials.create_material("WenNian 设计文档", text=PROFILE_RESUME * 2)
    goals.update_goal(goal["id"], {"selected_material_ids": [mat["id"]]})
    goals.add_interview(goal["id"], round_name="技术二面", scheduled_at=clock.t + 3 * DAY)

    # Day 2 — prepare + practice (weak ownership)
    clock.advance(DAY)
    goals.open_goal(goal["id"])
    first_focus = next_focus.recompute(goal["id"])
    checks["day2_next_focus_bounded"] = 1 <= len(first_focus) <= 3
    _practice(goal["id"], [WEAK_ANSWER, WEAK_ANSWER])

    # Day 3 — practice again, pin a bad moment
    clock.advance(DAY)
    s3 = _practice(goal["id"], [WEAK_ANSWER, "我们做了缓存。"])
    pin = pins.create_pin(s3["practice_id"], session_kind="PRACTICE", tag="BAD_ANSWER", question="你本人负责哪部分？",
                          goal_id=goal["id"])

    # Day 4 — mock interview through Go Live (session-scoped overlay)
    clock.advance(DAY)
    from core.config import session_overlay

    started = live.start(goal["id"], {})
    pack_notes = [n["id"] for n in __import__("services.intelligence.interview_pack", fromlist=["x"])
                  .load_frozen_pack(started["session_id"]).user_notes]
    checks["day4_pack_has_goal_note"] = note["id"] in pack_notes
    checks["day4_no_cross_goal_note"] = other_note["id"] not in pack_notes

    # v1.4 question C/F: synthetic dogfood must exercise the *usage* signals,
    # not merely prove those event names exist. These remain explicitly marked
    # SYNTHETIC_DOGFOOD and can never be promoted to real-user evidence.
    events.record("fast_cue_rendered", goal_id=goal["id"], session_id=started["session_id"])
    events.record("fast_cue_expanded", goal_id=goal["id"], session_id=started["session_id"])
    events.record("speech_after_cue", goal_id=goal["id"], session_id=started["session_id"])
    events.record("deep_opened", goal_id=goal["id"], session_id=started["session_id"])
    events.record("fast_cue_helpful", goal_id=goal["id"], session_id=started["session_id"])
    events.record("quick_note_opened_in_live", goal_id=goal["id"], session_id=started["session_id"])
    from services.storage import review

    rid = review.create_session(started_at=clock.t, interviewer_enabled=True, candidate_enabled=True)
    review.add_turn(session_id=rid, qa_id="q1", seq=1, question_text="讲讲你负责的 RAG 项目",
                    candidate_answer_text=WEAK_ANSWER)
    live.end(started["session_id"])
    checks["day4_overlay_cleared"] = session_overlay() == {}

    # Day 5 — reflection → write back
    clock.advance(DAY)
    r = reflection.build("REVIEW", str(rid))
    own = next((f for f in r["first_screen"]["to_improve"] if f["kind"] == "OWNERSHIP"), None)
    checks["day5_reflection_found_ownership"] = own is not None
    if own:
        reflection.apply_action("SET_NEXT_FOCUS", session_kind="REVIEW", session_ref=str(rid), finding=own)
    r3 = reflection.build("PRACTICE", s3["practice_id"])
    checks["day5_pin_first"] = bool(r3["first_screen"]["pinned_moments"]) and \
        r3["first_screen"]["pinned_moments"][0]["id"] == pin["id"]

    # v1.4 question F: prove Reflection can deliberately create a Quick Note
    # without silently turning it into Evidence / Memory.
    reflected_note = None
    if own:
        reflected_note = reflection.apply_action(
            "ADD_QUICK_NOTE",
            session_kind="REVIEW",
            session_ref=str(rid),
            finding=own,
            goal_id=goal["id"],
            payload={"content": "下一场先明确个人职责与决策边界", "tags": ["NEXT_FOCUS"]},
        ).get("quick_note")
    checks["day5_reflection_can_create_quick_note"] = bool(
        reflected_note
        and quick_notes.get_note(str(reflected_note["id"]))
        and quick_notes.get_note(str(reflected_note["id"])).get("origin") == "REFLECTION"
    )

    # Day 6 — reopen (fresh process)
    clock.advance(DAY)
    store._READY_PATHS.clear()  # noqa: SLF001
    reopened = goals.open_goal(goal["id"])
    top = next_focus.active_items(goal["id"])[0]
    checks["day6_state_continuity"] = reopened["company"] == "MindRank" and reopened["selected_material_ids"] == [mat["id"]]
    checks["day6_next_focus_is_reflection_ownership"] = top["type"] == "OWNERSHIP" and top["source_kind"] == "REFLECTION"
    checks["day6_material_still_ready"] = materials.require_material(mat["id"])["lifecycle"]["state"] == "READY"
    checks["day6_quick_note_kept"] = quick_notes.get_note(note["id"]) is not None
    checks["day6_fact_inbox_has_lead_claim"] = any(i["id"] == "df-lead" for i in fact_inbox.inbox()["items"])

    # v1.4 question E: exercise the actual burden-resolution loop, not just
    # backlog creation. Resolve the intentionally over-strong "lead" wording
    # to participation, matching the resume evidence.
    fact_inbox.mark_opened()
    fact_inbox.resolve("df-lead", "PARTICIPATE")
    burden = fact_inbox.metrics()
    checks["day6_fact_inbox_resolution_recorded"] = burden["opened"] >= 1 and burden["resolved"] >= 1

    # Day 7 — practice the same weakness from defaults, now answered well
    clock.advance(DAY)
    defaults = next_focus.practice_defaults(goal["id"])
    s7 = _practice(goal["id"], [STRONG_ANSWER, STRONG_ANSWER], round=defaults["round"], focus=defaults["focus"])
    first_turn = practice.get(s7["practice_id"])["turns"][0]
    checks["day7_practice_starts_on_weakness"] = first_turn["source"] == "RECENT_WEAKNESS"
    tr = trends.trends(goal["id"])
    own_trend = next((d for d in tr["dimensions"] if d["dimension"] == "ownership"), None)
    checks["day7_progress_visible"] = own_trend is not None and own_trend["series"][-1] > own_trend["series"][0]
    other_focus = next_focus.active_items(other["id"])
    checks["no_cross_goal_focus"] = all(f["source_ref"] != str(rid) for f in other_focus)
    transfer = validation.practice_transfer(goal["id"])
    checks["transfer_measured"] = transfer["measured"] >= 1

    # A user pin is only promoted through an explicit reflection action. This
    # proves the F-path without changing the earlier Next Focus continuity
    # assertions that intentionally verify Reflection-origin ownership.
    pin_focus = reflection.apply_action(
        "SET_NEXT_FOCUS",
        session_kind="PRACTICE",
        session_ref=s3["practice_id"],
        finding={
            "id": f"pin:{pin['id']}",
            "kind": "USER_PIN",
            "pin_id": pin["id"],
            "title": "复盘这次没答好的地方",
            "goal_id": goal["id"],
            "source": "PIN",
        },
        goal_id=goal["id"],
    ).get("next_focus")
    checks["day7_pin_can_become_next_focus"] = bool(
        pin_focus and pin_focus.get("source_kind") == "PIN" and pin_focus.get("source_ref") == pin["id"]
    )

    value = validation.report()["F_quick_notes_and_pins"]
    checks["day7_value_metrics_cover_reflection_note_and_pin"] = (
        value["quick_notes"]["converted_from_reflection"] >= 1
        and value["pins"]["next_focus_from_pin"] >= 1
    )
    return {"checks": checks, "passed": all(checks.values()), "evidence": "SYNTHETIC_DOGFOOD",
            "transfer": transfer, "trend": tr}


def run_sessions(n: int, set_clock: Callable[[Callable[[], float]], None]) -> dict[str, Any]:
    """N-session continuity across two goals, alternating weak/strong answers."""
    clock = Clock(1_795_000_000.0)
    set_clock(clock)
    store.meta_set(validation.SYNTHETIC_MARKER, "1")
    _setup_candidate()
    g1 = goals.create_goal("MindRank", "AIDD Agent Engineer", "熟悉 RAG 与 Agent")
    g2 = goals.create_goal("德睿智药", "AI Product Manager", "负责 AI 产品")
    for i in range(n):
        clock.advance(DAY / 2)
        gid = g1["id"] if i % 2 == 0 else g2["id"]
        goals.open_goal(gid)
        defaults = next_focus.practice_defaults(gid)
        answer = WEAK_ANSWER if i < n // 2 else STRONG_ANSWER
        _practice(gid, [answer], round=defaults["round"] or "TECHNICAL", focus=defaults["focus"])
        if i % 5 == 4:
            next_focus.recompute(gid)
    links = goals.session_links(g1["id"]) + goals.session_links(g2["id"])
    sessions = store.select("practice_session")
    checks = {
        "all_sessions_persisted": len(sessions) == n and all(s["status"] == "DONE" for s in sessions),
        "every_session_linked_to_its_goal": len(links) == n and all(
            (s["goal_id"] == l["goal_id"]) for s in sessions for l in links if l["practice_id"] == s["id"]),
        "next_focus_bounded": all(len(next_focus.active_items(g)) <= 3 for g in (g1["id"], g2["id"])),
        "integrity_clean": __import__("services.product.data_export", fromlist=["x"]).integrity()["ok"],
    }
    return {"checks": checks, "passed": all(checks.values()), "sessions": n, "evidence": "SYNTHETIC_DOGFOOD"}
