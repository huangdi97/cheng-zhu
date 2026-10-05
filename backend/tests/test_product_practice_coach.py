"""v1.3 G7/G11/G12/G13: materials lifecycle, Practice 3.0, panel, banks, rubrics, coaches."""
import pytest

from services.product import coach, goals, materials, practice, question_banks, rubrics, trends
from services.storage import product as store

PROJECT_TEXT = "WenNian 项目：我参与设计 RAG 架构，负责检索链路的重排模块，把 P95 延迟从 900ms 降到 400ms。" * 2


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------


def test_material_lifecycle_ready_failed_and_replace_keeps_old_active(product_env):
    m = materials.create_material("WenNian", text=PROJECT_TEXT)
    assert m["lifecycle"]["state"] == "READY"
    v1 = m["lifecycle"]["active_version"]["id"]

    bad = materials.create_material("扫描件", text="太短")
    assert bad["lifecycle"]["state"] == "FAILED"
    assert "可读文本过少" in bad["lifecycle"]["error"]
    assert bad["lifecycle"]["actions"] == ["view_reason", "retry", "replace"]
    fixed = materials.retry_material(bad["id"], text=PROJECT_TEXT)
    assert fixed["lifecycle"]["state"] == "READY"

    # replacement still processing: old READY version stays active (REPLACING)
    version = materials._new_version(m["id"], "v2.md")  # noqa: SLF001
    state = materials.require_material(m["id"])["lifecycle"]
    assert state["state"] == "REPLACING" and state["active_version"]["id"] == v1
    assert materials.ready_text(m["id"])["version_id"] == v1
    materials.process_version(version["id"], text=PROJECT_TEXT + " 新版本")
    after = materials.require_material(m["id"])["lifecycle"]
    assert after["state"] == "READY" and after["active_version"]["id"] == version["id"]


def test_failed_replacement_keeps_previous_ready_version(product_env):
    m = materials.create_material("WenNian", text=PROJECT_TEXT)
    materials.replace_material(m["id"], text="x")
    after = materials.require_material(m["id"])["lifecycle"]
    assert after["state"] == "READY" and after["error"]


def test_knowledge_base_material_is_never_personal_evidence(product_env):
    kb = materials.create_material("Redis 文档", kind="KB", usage="FACTS", text=PROJECT_TEXT)
    assert kb["usage"] == "REFERENCE"
    assert materials.ready_text(kb["id"])["is_personal_evidence"] is False
    with pytest.raises(materials.MaterialError):
        materials.set_usage(kb["id"], "FACTS")
    goal = goals.create_goal("A", "B")
    not_ready = materials.create_material("坏的", text="x")
    goals.update_goal(goal["id"], {"selected_material_ids": [kb["id"], not_ready["id"]]})
    packed = materials.materials_for_pack(goals.require_goal(goal["id"]))
    assert [m["material_id"] for m in packed["included"]] == [kb["id"]]
    assert packed["skipped"][0]["reason"] == "NOT_READY"


# ---------------------------------------------------------------------------
# Coaches
# ---------------------------------------------------------------------------


def test_content_coach_quotes_only_the_candidates_actual_speech():
    answer = "我们团队做了一个缓存系统。然后上线了。"
    out = coach.analyze_content("你在 Redis 缓存项目里具体负责什么？", answer, known_claims=[])
    assert out["findings"]
    for f in out["findings"]:
        assert f["evidence_from_actual_speech"] == "" or f["evidence_from_actual_speech"] in answer
        assert f["finding"] and f["action"]
    own = next(f for f in out["findings"] if f["signal"] == "ownership")
    assert "我们" in own["evidence_from_actual_speech"]


def test_content_coach_flags_unsupported_lead_claims_as_truth_boundary():
    answer = "我主导了完整的 RAG 架构设计，把延迟降低了 50%。"
    claims = [{"text": "参与 RAG 检索链路", "provenance_status": "NO_EVIDENCE"}]
    out = coach.analyze_content("讲讲 RAG 项目", answer, known_claims=claims)
    tb = [f for f in out["findings"] if f["signal"] == "truth_boundary"]
    assert tb and "主导" in tb[0]["evidence_from_actual_speech"]


def test_delivery_coach_is_actionable_and_has_no_score():
    long_answer = "嗯，那个，就是说，" * 3 + "我们先做了调研。" * 20 + "结论是选择了方案 A。"
    out = coach.analyze_delivery(long_answer, duration_ms=60_000)
    assert "score" not in repr(out).lower()
    assert out["metrics"]["fillers"] >= 5 and out["metrics"]["time_to_conclusion_s"] > 15
    assert any("15 秒结论训练" in a for a in out["advice"])
    scripted = coach.analyze_delivery("综上所述，" + "此外，系统具备高可用能力。" * 30 + "由此可见，方案可行。")
    assert scripted["metrics"]["possible_script_reading"] is True
    summary = coach.summarize_delivery([out, out, out])
    assert summary and "秒后出现" in summary[0]


def test_rubrics_are_per_role_public_and_never_a_total():
    for family in ("SWE", "AI_ML", "AI_PM", "DATA_ML", "PRODUCT"):
        r = rubrics.rubric_for(family)
        assert sum(d["weight"] for d in r["dimensions"]) == 100
        assert len(r["dimensions"]) == 8
    assert rubrics.rubric_for("AI_PM")["dimensions"][0]["key"] != rubrics.rubric_for("SWE")["dimensions"][0]["key"]
    gaps = rubrics.priority_gaps("SWE", {"ownership": 1.0, "depth": 3.8})
    assert gaps[0]["dimension"] == "ownership" and "score" not in gaps[0]


# ---------------------------------------------------------------------------
# Question banks
# ---------------------------------------------------------------------------


def test_question_bank_origins_and_no_fake_real_interview_label(product_env):
    question_banks.ensure_builtin_banks()
    role = question_banks.list_items(question_banks.role_bank_id("AI_ML"))
    assert role and all(i["origin"] == "CURATED" for i in role)
    assert all("真实面经" not in i["label"] for i in role)
    bank = question_banks.create_bank("我的题库")
    gen = question_banks.add_item(bank["id"], "讲讲 MoE", origin="GENERATED")
    imp = question_banks.add_item(bank["id"], "讲讲 RAG", origin="IMPORTED", source_url="https://example.com/post")
    labels = {i["id"]: i["label"] for i in question_banks.list_items(bank["id"])}
    assert "非真实面经" in labels[gen["id"]] and labels[imp["id"]] == "导入（有来源）"
    with pytest.raises(question_banks.QuestionBankError):
        question_banks.add_item(question_banks.role_bank_id("SWE"), "改内置题库")
    with pytest.raises(question_banks.QuestionBankError):
        question_banks.add_item(bank["id"], "伪造", origin="CURATED")


# ---------------------------------------------------------------------------
# Practice 3.0
# ---------------------------------------------------------------------------


def _start(goal_id=None, **cfg):
    base = {"goal_id": goal_id, "round": "PROJECT_DEEP_DIVE", "sources": ["ROLE_BANK"], "questions": 4}
    base.update(cfg)
    return practice.start(base)


def test_adaptive_interviewer_reacts_to_the_answer_not_a_playlist(product_env):
    goal = goals.create_goal("MindRank", "AIDD Agent Engineer")
    a = _start(goal["id"], demeanor="SKEPTICAL")
    weak = practice.answer(a["practice_id"], "我们团队一起做的，效果还可以。")
    assert weak["next_question"]["move"] in ("OWNERSHIP_PROBE", "CLARIFY", "QUANTIFY")

    b = _start(goal["id"], demeanor="SKEPTICAL")
    strong = practice.answer(b["practice_id"],
                             "结论是我负责重排模块：我设计了两阶段召回，取舍是牺牲 5% 召回换 50% 延迟，"
                             "代价是需要维护缓存。P95 从 900ms 降到 400ms，QPS 提升 2 倍。")
    assert strong["next_question"]["move"] != weak["next_question"]["move"]
    assert strong["feedback"]["content"]["kind"] == "CONTENT"
    assert strong["feedback"]["delivery"]["kind"] == "DELIVERY"


def test_demeanor_and_difficulty_change_the_follow_up_budget():
    assert practice.followup_budget("FRIENDLY", "WARMUP") == 0
    assert practice.followup_budget("STRONG_FOLLOWUP", "PRESSURE") == 4
    good = {s: 4 for s in coach.CONTENT_SIGNALS}
    assert practice.choose_move(good, demeanor="NEUTRAL", difficulty="PRESSURE", followups_on_topic=0,
                                round_name="SYSTEM_DESIGN") == "CONSTRAINT_CHANGE"
    assert practice.choose_move(good, demeanor="FRIENDLY", difficulty="STANDARD", followups_on_topic=0,
                                round_name="TECHNICAL") is None
    weak_truth = {**good, "truth_boundary": 2}
    assert practice.choose_move(weak_truth, demeanor="NEUTRAL", difficulty="STANDARD", followups_on_topic=0,
                                round_name="TECHNICAL") == "CONTRADICTION_PROBE"
    weak_trade = {**good, "trade_off": 1}
    assert practice.choose_move(weak_trade, demeanor="SKEPTICAL", difficulty="STANDARD", followups_on_topic=0,
                                round_name="TECHNICAL") == "CHALLENGE"


def test_practice_ends_with_closing_and_lands_in_review_and_goal(product_env):
    from services.storage import review

    goal = goals.create_goal("MindRank", "AIDD Agent Engineer")
    s = _start(goal["id"], demeanor="FRIENDLY", difficulty="WARMUP", questions=3)
    moves = [s["question"]["move"]]
    result = None
    for _ in range(10):
        result = practice.answer(s["practice_id"], "结论是我负责检索模块，取舍是延迟优先，P95 降到 400ms。")
        if result["done"]:
            break
        moves.append(result["next_question"]["move"])
    assert moves[-1] == "CLOSING" and result["done"]
    report = result["report"]
    assert report["review_session_id"] and review.get_session_detail(report["review_session_id"])["source"] == "practice"
    links = goals.session_links(goal["id"])
    assert links and links[0]["review_session_id"] == report["review_session_id"]
    prev = question_banks.list_items(f"qb_prev_{goal['id']}")
    assert prev and prev[0]["origin"] == "PREVIOUS_SESSION"


def test_panel_has_one_speaker_per_turn_and_follow_ups_stay_with_the_asker(product_env):
    goal = goals.create_goal("MindRank", "AIDD Agent Engineer")
    s = _start(goal["id"], personas=["TECH_LEAD", "HIRING_MANAGER", "PRODUCT_PARTNER"], demeanor="SKEPTICAL",
               round="TECHNICAL", questions=6)
    assert s["panel"]["is_panel"] and len(s["panel"]["personas"]) == 3
    assert s["question"]["persona_id"] == "TECH_LEAD"  # highest priority opens
    r = practice.answer(s["practice_id"], "我们一起做了一些优化，效果还行。")
    nq = r["next_question"]
    assert nq["persona_id"]  # exactly one speaker
    if nq["move"] == "OWNERSHIP_PROBE":
        assert nq["persona_id"] == "HIRING_MANAGER"
    turns = practice.get(s["practice_id"])["turns"]
    assert all(t["persona_id"] for t in turns)
    with pytest.raises(practice.PracticeError):
        _start(goal["id"], personas=["TECH_LEAD", "HIRING_MANAGER", "PRODUCT_PARTNER", "HR_PARTNER"])


def test_practice_persists_across_restart(product_env):
    s = _start(None, round="TECHNICAL")
    store._READY_PATHS.clear()  # noqa: SLF001 — simulate a fresh process
    again = practice.get(s["practice_id"])
    assert again["status"] == "ACTIVE" and again["turns"][0]["question"] == s["question"]["question"]


def test_progress_trends_describe_direction_without_scores(product_env):
    goal = goals.create_goal("MindRank", "AIDD Agent Engineer")
    for answer in ("我们做了。", "我们做了。", "我们做了一点。"):
        s = _start(goal["id"], demeanor="FRIENDLY", difficulty="WARMUP", questions=1, closing=False)
        practice.answer(s["practice_id"], answer)
    t = trends.trends(goal["id"])
    own = next(d for d in t["dimensions"] if d["dimension"] == "ownership")
    assert own["direction"] == "REPEATING" and "仍在重复" in own["text"]
    assert "percentile" not in repr(t).lower() and "probability" not in repr(t).lower()


def test_store_rows_survive_without_goal(product_env):
    s = _start(None, round="BEHAVIORAL")
    assert store.get("practice_session", s["practice_id"])["goal_id"] is None


def test_next_focus_reason_is_product_language_not_rubric_debug_output(product_env):
    from services.product import next_focus

    goal = goals.create_goal("MindRank", "AIDD Agent Engineer")
    for answer in ("我们做了。", "我们做了。"):
        s = _start(goal["id"], demeanor="FRIENDLY", difficulty="WARMUP", questions=1, closing=False)
        practice.answer(s["practice_id"], answer)
    rows = next_focus._practice_candidates(goals.require_goal(goal["id"]))  # noqa: SLF001
    assert rows
    reason = rows[0]["reason"]
    assert "最近" in reason and "练习" in reason
    assert "满级 4" not in reason
    assert "岗位权重" not in reason
    assert "第 1.0 级" not in reason
