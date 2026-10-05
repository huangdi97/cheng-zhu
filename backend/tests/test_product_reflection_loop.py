"""v1.3 G6/G15/G19 + v1.4 G27: Fact Inbox, Pins, Reflection write-back loop.

The Stage 8 chain is exercised end to end through the real services:
Goal (Next Focus = System Design) → Practice session → Reflection finds
ownership → ReflectionAction writes back → reopen Goal → Next Focus is
ownership → Practice defaults pick ownership.
"""
import pytest

from services.product import events, fact_inbox, goals, next_focus, pins, practice, reflection
from services.storage import intelligence as intel
from services.storage import product as store


def _candidate_with_claims(claims):
    intel.save_candidate_profile("cand-1", profile_text="WenNian 项目")
    intel.save_claims("cand-1", claims)
    return "cand-1"


# ---------------------------------------------------------------------------
# Fact Inbox
# ---------------------------------------------------------------------------


def test_fact_inbox_shows_what_the_material_supports_and_resolves_through_core_axes(product_env):
    _candidate_with_claims([
        {"id": "c-lead", "text": "我负责完整 RAG 架构设计", "truth_status": "INFERRED", "source": "resume"},
        {"id": "c-ok", "text": "使用 Python 开发后端服务", "truth_status": "SUPPORTED", "source": "resume"},
    ])
    intel.save_evidence_batch("cand-1", [{"id": "ev1", "text": "WenNian：参与设计 RAG 架构", "source": "resume"}],
                              [("c-lead", "ev1")])
    box = fact_inbox.inbox()
    card = next(i for i in box["items"] if i["id"] == "c-lead")
    assert card["risk"] == "HIGH" and card["supported_label"].startswith("参与")
    assert card["primary_actions"][:2] == ["LEAD", "PARTICIPATE"]
    assert all(i["id"] != "c-ok" for i in box["items"])  # direct, low-risk: not a burden

    fact_inbox.resolve("c-lead", "PARTICIPATE")
    row = next(c for c in intel.list_claims("cand-1") if c["id"] == "c-lead")
    assert row["user_assertion_status"] == "USER_CONFIRMED"
    assert "参与" in row["text"] and "负责" not in row["text"]
    assert row["provenance_status"] == "SUPPORTING_EVIDENCE"  # confirming never raised provenance
    assert fact_inbox.metrics()["resolved"] == 1


def test_fact_inbox_burden_guard_switches_to_high_only(product_env):
    claims = [{"id": f"c{i}", "text": f"熟悉组件{i}", "truth_status": "UNKNOWN"} for i in range(20)]
    claims.append({"id": "c-high", "text": "我主导了 30% 成本下降", "truth_status": "UNKNOWN"})
    _candidate_with_claims(claims)
    box = fact_inbox.inbox()
    assert box["policy"]["mode"] == "HIGH_ONLY" and "BACKLOG_GROWING" in box["policy"]["reasons"]
    assert [i["id"] for i in box["items"]] == ["c-high"]
    assert box["batch"]["count"] == 20
    result = fact_inbox.batch_resolve(box["batch"]["ids"], "DISMISS")
    assert len(result["done"]) == 20
    with pytest.raises(fact_inbox.FactInboxError):
        fact_inbox.batch_resolve(["c-high"], "DELETE_DRAFT")


def test_fact_inbox_merge_add_source_and_delete_draft(product_env):
    _candidate_with_claims([
        {"id": "a", "text": "负责 Redis 缓存 设计", "truth_status": "UNKNOWN"},
        {"id": "b", "text": "负责 Redis 缓存 设计 与 优化", "truth_status": "UNKNOWN"},
        {"id": "d", "text": "草稿事实", "truth_status": "UNKNOWN"},
    ])
    assert ["a", "b"] in fact_inbox.inbox()["merge_suggestions"]
    fact_inbox.resolve("a", "MERGE", {"merge_ids": ["b"]})
    assert {c["id"] for c in intel.list_claims("cand-1")} == {"a", "d"}
    fact_inbox.resolve("a", "ADD_SOURCE", {"source_text": "设计文档 v2：Redis 缓存方案由我设计"})
    row = next(c for c in intel.list_claims("cand-1") if c["id"] == "a")
    assert row["provenance_status"] == "SUPPORTING_EVIDENCE"
    fact_inbox.resolve("d", "DELETE_DRAFT")
    assert {c["id"] for c in intel.list_claims("cand-1")} == {"a"}


# ---------------------------------------------------------------------------
# Pin Moment
# ---------------------------------------------------------------------------


def test_pin_appears_first_in_reflection_and_promotes_only_on_request(product_env):
    goal = goals.create_goal("MindRank", "AIDD Agent Engineer")
    s = practice.start({"goal_id": goal["id"], "round": "TECHNICAL", "sources": ["ROLE_BANK"], "questions": 3})
    practice.answer(s["practice_id"], "我们用了缓存。")
    practice.answer(s["practice_id"], "我们用了队列。")
    pin = pins.create_pin(s["practice_id"], session_kind="PRACTICE", tag="BAD_ANSWER",
                          question="Redis 集群怎么扩容？", note="没答上来", goal_id=goal["id"])
    practice.finish(s["practice_id"])
    before = [i["id"] for i in next_focus.active_items(goal["id"]) if i["source_kind"] == "PIN"]
    assert before == []  # pins never become Next Focus automatically

    r = reflection.build("PRACTICE", s["practice_id"])
    first = r["first_screen"]
    assert list(first)[:2] == ["next_step", "pinned_moments"]
    assert first["pinned_moments"][0]["id"] == pin["id"]
    assert first["next_step"]["kind"] == "USER_PIN"  # the user's own judgement leads
    assert store.get("pin_moment", pin["id"])["used_in_reflection"] is True

    out = reflection.apply_action("SET_NEXT_FOCUS", session_kind="PRACTICE", session_ref=s["practice_id"],
                                  finding=first["next_step"])
    top = next_focus.active_items(goal["id"])[0]
    assert top["source_kind"] == "PIN" and top["title"] == "Redis 集群怎么扩容？"
    assert out["next_focus"]["id"] == top["id"]
    assert events.counts().get("next_focus_from_pin") == 1


# ---------------------------------------------------------------------------
# Reflection → Next Focus write-back (Stage 8)
# ---------------------------------------------------------------------------


def test_reflection_rewrites_next_focus_and_practice_defaults(product_env):
    goal = goals.create_goal("MindRank", "AIDD Agent Engineer", "任职要求：系统设计能力")
    next_focus.set_user_focus(goal["id"], "SYSTEM_DESIGN", "System Design", "岗位要求系统设计")
    assert next_focus.active_items(goal["id"])[0]["type"] == "SYSTEM_DESIGN"

    s = practice.start({"goal_id": goal["id"], "round": "PROJECT_DEEP_DIVE", "sources": ["ROLE_BANK"],
                        "questions": 2, "closing": False})
    practice.answer(s["practice_id"], "我们团队一起做的，大家分工合作。")
    practice.answer(s["practice_id"], "我们后来又一起优化了。")
    r = reflection.build("PRACTICE", s["practice_id"])
    ownership = next(f for f in r["first_screen"]["to_improve"] if f["kind"] == "OWNERSHIP")
    assert ownership["actual_speech"] and "我们" in ownership["actual_speech"]

    reflection.apply_action("SET_NEXT_FOCUS", session_kind="PRACTICE", session_ref=s["practice_id"], finding=ownership)
    store._READY_PATHS.clear()  # noqa: SLF001 — "reopen" from a fresh process
    reopened = goals.open_goal(goal["id"])
    top = next_focus.active_items(reopened["id"])[0]
    assert top["type"] == "OWNERSHIP" and top["source_kind"] == "REFLECTION"
    defaults = next_focus.practice_defaults(goal["id"])
    assert defaults["focus"]["type"] == "OWNERSHIP" and defaults["round"] == "PROJECT_DEEP_DIVE"
    nxt = practice.start({"goal_id": goal["id"], "round": defaults["round"], "focus": defaults["focus"],
                          "sources": ["RECENT_WEAKNESS", "ROLE_BANK"], "questions": 2})
    assert nxt["question"]["source"] == "RECENT_WEAKNESS"
    assert "完全由你负责" in nxt["question"]["question"]


@pytest.mark.parametrize("kind,expected_round", [
    ("KNOWLEDGE_GAP", "TECHNICAL"), ("OWNERSHIP", "PROJECT_DEEP_DIVE"), ("STORY_GAP", "BEHAVIORAL"),
    ("FACT_BOUNDARY", "PROJECT_DEEP_DIVE"), ("SYSTEM_DESIGN", "SYSTEM_DESIGN"), ("DELIVERY", "BEHAVIORAL"),
    ("FOLLOWUP_RESILIENCE", "TECHNICAL"), ("CODING", "TECHNICAL"), ("CLOSING_QUESTION", "HIRING_MANAGER"),
    ("USER_PIN", "TECHNICAL"),
])
def test_ten_finding_kinds_write_back_to_next_focus_and_practice_default(product_env, kind, expected_round):
    goal = goals.create_goal("MindRank", "AIDD Agent Engineer")
    s = practice.start({"goal_id": goal["id"], "round": "TECHNICAL", "sources": ["ROLE_BANK"], "questions": 1,
                        "closing": False})
    practice.answer(s["practice_id"], "我们做了一个缓存。")
    finding = {"id": f"f-{kind}", "kind": kind, "kind_label": kind, "finding": "测试发现", "actual_speech": "我们做了一个缓存。"}
    out = reflection.apply_action("PRACTICE_THIS", session_kind="PRACTICE", session_ref=s["practice_id"], finding=finding)
    top = next_focus.active_items(goal["id"])[0]
    assert top["type"] == kind and top["origin"] == "USER"
    assert out["practice_defaults"]["round"] == expected_round
    assert store.select("reflection_action", "goal_id = ?", (goal["id"],))[0]["action"] == "PRACTICE_THIS"
    started = practice.start({"goal_id": goal["id"], "round": out["practice_defaults"]["round"],
                              "focus": out["practice_defaults"]["focus"], "sources": ["ROLE_BANK"], "questions": 1})
    assert started["question"]["source"] == "RECENT_WEAKNESS"


def test_reflection_actions_write_back_for_real(product_env):
    goal = goals.create_goal("MindRank", "AIDD Agent Engineer")
    s = practice.start({"goal_id": goal["id"], "round": "BEHAVIORAL", "sources": ["ROLE_BANK"], "questions": 1,
                        "closing": False})
    practice.answer(s["practice_id"], "结论是我负责推进上线。首先对齐目标，其次拆分任务，最后复盘，延迟降低 30%。")
    intel.save_candidate_profile("cand-1", profile_text="x")
    finding = {"id": "f1", "kind": "STORY_GAP", "question": "讲一次你推动上线的经历",
               "actual_speech": "结论是我负责推进上线。首先对齐目标"}
    story = reflection.apply_action("CREATE_STORY", session_kind="PRACTICE", session_ref=s["practice_id"], finding=finding)
    saved = [x for x in intel.list_all_stories() if x["id"] == story["story"]["id"]]
    assert saved and saved[0]["situation"].startswith("结论是我负责推进上线")  # user's own words only
    note = reflection.apply_action("ADD_QUICK_NOTE", session_kind="PRACTICE", session_ref=s["practice_id"],
                                   finding={"id": "f2", "kind": "CLOSING_QUESTION", "action_hint": "想问：团队规模？"})
    assert note["quick_note"]["scope"] == "GOAL" and note["quick_note"]["goal_id"] == goal["id"]
    with pytest.raises(reflection.ReflectionError):
        reflection.apply_action("ADD_SOURCE", session_kind="PRACTICE", session_ref=s["practice_id"], finding={"id": "x"})


def test_session_claim_review_actions(product_env, monkeypatch):
    from services.intelligence import session_claims

    calls = []
    monkeypatch.setattr(session_claims, "confirm_in_review",
                        lambda cid, candidate_id, decision: calls.append((cid, decision)) or {"id": cid})
    monkeypatch.setattr(session_claims, "resolve", lambda cid, action: calls.append((cid, action)) or {"id": cid})
    for action, expected in (("CONFIRM_FACT", "confirm"), ("MARK_MISTAKE", "deny"), ("DONT_REMEMBER", "forget")):
        reflection.apply_action(action, session_kind="REVIEW", session_ref="1",
                                finding={"id": "sc:1", "kind": "FACT_BOUNDARY", "session_claim_id": "sc_1"})
        assert calls[-1] == ("sc_1", expected)
    assert ("sc_1", "slip") in calls
