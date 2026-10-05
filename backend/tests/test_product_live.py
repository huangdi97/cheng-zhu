"""v1.3 G14/G16/G17/G18/G20: Preflight, Live start/end, Nudge, Closing, Language, Settings layers."""
import pytest

import core.config as config_module
from services.product import closing, goals, live, materials, nudges, quick_notes, settings_layers
from services.storage import product as store

PROJECT_TEXT = "WenNian 项目：我参与设计 RAG 架构，负责检索链路的重排模块，把 P95 延迟从 900ms 降到 400ms。" * 2


# ---------------------------------------------------------------------------
# Nudge
# ---------------------------------------------------------------------------

BASE = {"candidate_text": "我们用 Redis 做缓存，然后把热点数据放进去，整体效果还可以，大概就是这样做的。",
        "question_type": "SYSTEM_DESIGN", "proactive_enabled": True}


def test_nudge_shows_one_at_a_time_and_respects_priority(product_env):
    first = nudges.evaluate("s1", BASE)
    assert first["nudge"] and first["nudge"]["priority"] == nudges.PRIORITY["NUDGE"] > nudges.PRIORITY["FAST_CUE"]
    assert nudges.evaluate("s1", BASE)["suppressed"] == "ONE_AT_A_TIME"


@pytest.mark.parametrize("override,reason", [
    ({"candidate_speaking": True}, "SPEECH_ACTIVE"),
    ({"new_question_pending": True}, "NEW_QUESTION"),
    ({"cue_state": "PREPARING"}, "CUE_PRIORITY"),
    ({"proactive_enabled": False}, "DISABLED"),
    ({"candidate_text": "嗯", "interviewer_recent": []}, "NOT_ENOUGH_CONTEXT"),
])
def test_nudge_suppression_rules(product_env, override, reason):
    assert nudges.evaluate("s2", {**BASE, **override})["suppressed"] == reason


def test_nudge_cooldown_duplicate_and_new_question_cancel(product_env, monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(store, "now", lambda: t[0])
    shown = nudges.evaluate("s3", BASE)["nudge"]
    nudges.set_status(shown["id"], "DISMISSED")
    t[0] += 5
    assert nudges.evaluate("s3", BASE)["suppressed"] == "COOLDOWN"
    t[0] += 60
    second = nudges.evaluate("s3", BASE)["nudge"]
    assert second and second["topic_key"] != shown["topic_key"]  # duplicate suppressed
    assert nudges.cancel_on_new_question("s3") == 1
    assert nudges.session_stats("s3")["CANCELLED"] == 1


def test_nudge_already_mentioned_is_suppressed(product_env):
    text = "我们用 Redis 做缓存，失败时降级兜底，取舍是延迟优先，规模上来以后水平扩展分片。"
    out = nudges.evaluate("s4", {**BASE, "candidate_text": text})
    assert out["nudge"] is None or out["nudge"]["kind"] != "MISSING_DIMENSION"


# ---------------------------------------------------------------------------
# Closing
# ---------------------------------------------------------------------------


def test_closing_detection():
    assert closing.detect("好的，我这边问完了，你有什么想问我们的吗？") == "INTERVIEW_CLOSING"
    assert closing.detect("Do you have any questions for us?") == "INTERVIEW_CLOSING"
    assert closing.detect("我想问一下团队现在的规模") == "CANDIDATE_QUESTION"
    assert closing.detect("讲讲你的 RAG 项目") is None


def test_closing_uses_this_interview_before_generic():
    goal = {"company": "MindRank", "role": "AIDD Agent Engineer", "jd": "负责 Agent 平台与评测体系"}
    transcript = [{"speaker": "interviewer", "text": "我们团队现在在做多 Agent 的评测平台，下半年要上线。"},
                  {"speaker": "candidate", "text": "明白。"}]
    out = closing.suggest(goal=goal, transcript=transcript, ask_notes=[{"content": "想问：试用期考核标准？"}],
                          open_threads=["Redis 集群迁移"])
    kinds = [s["kind"] for s in out]
    assert kinds[0] == "CONTEXTUAL_FOLLOWUP" and "评测平台" in out[0]["text"]
    assert "GENERIC" not in kinds and "公司文化" not in repr(out)
    assert kinds.index("SUCCESS_CRITERIA") < kinds.index("TEAM_CHALLENGE")
    assert [s["kind"] for s in closing.suggest()] == ["GENERIC"] * 3


# ---------------------------------------------------------------------------
# Language layering + settings layers
# ---------------------------------------------------------------------------


def test_language_layers_are_independent_in_the_prompt():
    from services.llm.prompts import _answer_language_rule

    follow = _answer_language_rule("FOLLOW_INTERVIEW", "KEEP_ENGLISH")
    assert "相同的语言" in follow and "保留英文原文" in follow
    en_bilingual = _answer_language_rule("English", "BILINGUAL")
    assert "英文回答" in en_bilingual and "中英并列" in en_bilingual
    legacy = _answer_language_rule("中文", "AUTO")
    assert legacy == _answer_language_rule("中文")  # AUTO keeps the v1.2 rule byte-for-byte


def test_settings_layers_resolve_origin_and_session_overlay_is_not_persisted(product_env):
    goal = goals.create_goal("A", "B")
    settings_layers.set_override("GOAL", goal["id"], "answer_language", "English")
    settings_layers.set_override("SESSION", "live-1", "technical_term_policy", "BILINGUAL")
    r = settings_layers.resolve(goal["id"], "live-1")
    assert r["answer_language"]["origin"] == "GOAL" and r["answer_language"]["origin_label"] == "Goal 默认"
    assert r["technical_term_policy"]["origin"] == "SESSION"
    assert r["whisper_language"]["origin"] in ("GLOBAL", "SYSTEM")
    persisted_answer_language = config_module.persisted_config().answer_language
    settings_layers.apply_session(goal["id"], "live-1")
    assert config_module.get_config().answer_language == "English"
    config_module.update_config({"max_tokens": 1024})
    assert config_module.persisted_config().answer_language == persisted_answer_language
    config_module.update_config({"temperature": 0.3})  # a global edit during the session
    assert config_module.persisted_config().technical_term_policy != "BILINGUAL"
    assert config_module.get_config().technical_term_policy == "BILINGUAL"
    settings_layers.end_session()
    assert config_module.get_config().technical_term_policy == config_module.persisted_config().technical_term_policy
    with pytest.raises(settings_layers.SettingsLayerError):
        settings_layers.set_override("GOAL", goal["id"], "api_key", "x")
    with pytest.raises(settings_layers.SettingsLayerError):
        settings_layers.set_override("GOAL", goal["id"], "answer_language", "Klingon")


# ---------------------------------------------------------------------------
# Preflight / Live
# ---------------------------------------------------------------------------


def test_preflight_lists_every_input_with_origin(product_env):
    goal = goals.create_goal("MindRank", "AIDD Agent Engineer", "熟悉 RAG")
    settings_layers.set_override("GOAL", goal["id"], "share_privacy_mode", "PRIVATE_OVERLAY")
    out = live.preflight(goal["id"], {"answer_language": "FOLLOW_INTERVIEW"})
    keys = [i["key"] for i in out["items"]]
    for k in ("goal", "resume", "skill_cards", "stories", "knowledge", "quick_notes", "answer_language",
              "whisper_language", "active_model", "stt", "audio", "ai_policy_mode", "human_assistance_policy",
              "share_privacy_mode", "screen_context"):
        assert k in keys, k
    by_key = {i["key"]: i for i in out["items"]}
    assert by_key["answer_language"]["origin_label"] == "本场覆盖"
    assert by_key["share_privacy_mode"]["origin_label"] == "Goal 默认"
    assert by_key["skill_cards"]["label"] == "技能卡"
    assert by_key["stories"]["label"] == "故事"
    assert isinstance(by_key["active_model"]["value"], str) and by_key["active_model"]["value"]
    assert by_key["active_model"]["value"] != "0"
    assert by_key["technical_term_policy"]["value"] != "AUTO"
    assert by_key["stt"]["value"] != "whisper"
    assert "不是安全或不可检测保证" in out["share_privacy_note"]
    assert "pack_hash" not in repr(out) and "candidate_version" not in repr(out)


def test_go_live_freezes_goal_pack_with_notes_and_ready_materials_only(product_env, monkeypatch):
    from services.intelligence import interview_pack

    monkeypatch.setattr(live, "_current_session_id", lambda: "live-abc")
    goal = goals.create_goal("MindRank", "AIDD Agent Engineer", "任职要求：熟悉 RAG 与 Agent")
    note = quick_notes.create_note("想问：团队规模", scope="GOAL", goal_id=goal["id"], pinned=True)
    ready = materials.create_material("WenNian", text=PROJECT_TEXT)
    broken = materials.create_material("坏文件", text="x")
    goals.update_goal(goal["id"], {"selected_material_ids": [ready["id"], broken["id"]],
                                   "selected_quick_note_ids": [note["id"]]})
    persisted_before = config_module.persisted_config().model_dump()
    out = live.start(goal["id"], {"answer_language": "English"})
    pack = interview_pack.load_frozen_pack("live-abc")
    assert pack and pack.goal_id == goal["id"]
    assert [n["id"] for n in pack.user_notes] == [note["id"]] and pack.user_notes[0]["is_evidence"] is False
    assert [m["material_id"] for m in pack.goal_materials] == [ready["id"]]
    assert pack.payload["goal_materials_skipped"][0]["material_id"] == broken["id"]
    assert config_module.get_config().answer_language == "English"
    assert config_module.get_config().position == "AIDD Agent Engineer"
    assert config_module.persisted_config().model_dump() == persisted_before  # session-only, never saved
    assert out["session_id"] == "live-abc"

    from services.storage import review

    rid = review.create_session(started_at=store.now(), interviewer_enabled=True, candidate_enabled=True)
    ended = live.end("live-abc")
    assert ended["review_session_id"] == rid and ended["goal_id"] == goal["id"]
    assert goals.goal_for_review_session(rid) == goal["id"]
    assert config_module.session_overlay() == {}
