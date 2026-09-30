"""v1.2-R2 core gates: provenance axes, assertion policy, the single router,
session claims, InterviewPack freeze (Job A / Job B contamination), Context
Compiler authority + dedupe, Fast Cue before Deep, latency clock, stream
truth guard, human/AI policy separation.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import services.storage.intelligence as intel_storage  # noqa: E402
from services.intelligence import (  # noqa: E402
    fast_cue,
    interview_pack,
    latency_clock,
    session_claims,
)
from services.intelligence.context_compiler import (  # noqa: E402
    ContextCompiler,
    KBProvider,
    ResumeProvider,
    SessionMemoryProvider,
    compile_live_context,
    dedupe_fragments,
)
from services.intelligence.policy import human_coach_allowed, live_guidance_allowed_for_pack  # noqa: E402
from services.intelligence.semantics import (  # noqa: E402
    AssertionPolicy,
    ContentType,
    DialogueAct,
    ProvenanceStatus,
    SessionStatus,
    TruthRequirement,
    UserAssertionStatus,
    decide_assertion_policy,
    derive_axes,
    provenance_from_grounding,
    provenance_from_legacy,
    route_answer,
)
from services.intelligence.stream_guard import StreamTruthGuard  # noqa: E402
from services.intelligence.types import QuestionType, ResponseMode  # noqa: E402

RESUME = "WenNian 项目：我用 Redis 管理 session state，负责检索链路\n使用 RAG 做知识问答"


@pytest.fixture()
def tmp_intel_db(tmp_path, monkeypatch):
    monkeypatch.setattr(intel_storage, "DB_PATH", str(tmp_path / "intelligence.db"))
    intel_storage.init_db()
    yield tmp_path


# ---------------------------------------------------------------------------
# G2 Provenance / assertion semantics
# ---------------------------------------------------------------------------

def test_provenance_is_not_truth_legacy_verified_maps_to_direct_evidence():
    assert provenance_from_legacy("VERIFIED") == ProvenanceStatus.DIRECT_EVIDENCE
    assert provenance_from_legacy("INFERRED") == ProvenanceStatus.NO_EVIDENCE
    assert provenance_from_legacy("CONTRADICTED") == ProvenanceStatus.CONFLICTING_EVIDENCE


def test_redis_has_evidence_but_redis_cluster_does_not():
    assert provenance_from_grounding("not_applicable", question="你用过 Redis 吗？", profile_text=RESUME) == ProvenanceStatus.DIRECT_EVIDENCE
    assert provenance_from_grounding("not_applicable", question="你们当时用了 Redis Cluster 吗？", profile_text=RESUME) == ProvenanceStatus.NO_EVIDENCE
    assert provenance_from_grounding("related_only") == ProvenanceStatus.NO_EVIDENCE


@pytest.mark.parametrize(
    "prov,user,session,req,expected",
    [
        ("DIRECT_EVIDENCE", "UNREVIEWED", "NOT_STATED", "PERSONAL_FACT_REQUIRED", AssertionPolicy.ALLOW_PERSONAL_ASSERTION),
        ("SUPPORTING_EVIDENCE", "UNREVIEWED", "NOT_STATED", "PERSONAL_FACT_REQUIRED", AssertionPolicy.ALLOW_WITH_QUALIFIER),
        ("NO_EVIDENCE", "USER_CONFIRMED", "NOT_STATED", "PERSONAL_FACT_REQUIRED", AssertionPolicy.ALLOW_WITH_QUALIFIER),
        ("NO_EVIDENCE", "UNREVIEWED", "SESSION_STATED", "PERSONAL_FACT_REQUIRED", AssertionPolicy.REQUIRE_BOUNDARY),
        ("DIRECT_EVIDENCE", "UNREVIEWED", "SESSION_CORRECTED", "PERSONAL_FACT_REQUIRED", AssertionPolicy.BLOCK_ASSERTION),
        ("DIRECT_EVIDENCE", "USER_DENIED", "NOT_STATED", "PERSONAL_FACT_REQUIRED", AssertionPolicy.BLOCK_ASSERTION),
        ("CONFLICTING_EVIDENCE", "USER_CONFIRMED", "NOT_STATED", "PERSONAL_FACT_REQUIRED", AssertionPolicy.REQUIRE_BOUNDARY),
        ("DIRECT_EVIDENCE", "UNREVIEWED", "NOT_STATED", "KNOWLEDGE_ONLY", AssertionPolicy.KNOWLEDGE_ONLY),
        ("NO_EVIDENCE", "UNREVIEWED", "NOT_STATED", "PERSONAL_FACT_RELEVANT", AssertionPolicy.KNOWLEDGE_ONLY),
    ],
)
def test_assertion_policy_table(prov, user, session, req, expected):
    assert decide_assertion_policy(prov, user, session, req) == expected


def test_user_confirmation_does_not_change_provenance_axis():
    # Confirmation without a source unlocks only a qualified statement.
    policy = decide_assertion_policy(ProvenanceStatus.NO_EVIDENCE, UserAssertionStatus.USER_CONFIRMED)
    assert policy == AssertionPolicy.ALLOW_WITH_QUALIFIER
    assert policy != AssertionPolicy.ALLOW_PERSONAL_ASSERTION


def test_ai_forbidden_blocks_assertion():
    assert decide_assertion_policy("DIRECT_EVIDENCE", ai_policy="AI_FORBIDDEN") == AssertionPolicy.BLOCK_ASSERTION


# ---------------------------------------------------------------------------
# G6 Routing: one function, strict
# ---------------------------------------------------------------------------

def test_route_answer_is_the_only_table():
    import services.intelligence.answer_planner as planner

    assert not hasattr(planner, "_ROUTE_TABLE")


@pytest.mark.parametrize(
    "qtype,text,prov,expected",
    [
        (QuestionType.KNOWLEDGE, "RAG 和 fine-tuning 区别", "NO_EVIDENCE", ResponseMode.KNOWLEDGE),
        (QuestionType.CODING, "写一个 LRU", "NO_EVIDENCE", ResponseMode.CODING),
        (QuestionType.OOD, "设计停车场的类", "NO_EVIDENCE", ResponseMode.OOD),
        (QuestionType.PRODUCT, "怎么提升留存", "NO_EVIDENCE", ResponseMode.PRODUCT_CASE),
        (QuestionType.EXPERIENCE, "你用过 Redis Cluster 吗", "NO_EVIDENCE", ResponseMode.EXPERIENCE_BOUNDARY_KNOWLEDGE),
        (QuestionType.EXPERIENCE, "介绍你的项目", "DIRECT_EVIDENCE", ResponseMode.EXPERIENCE),
        (QuestionType.SYSTEM_DESIGN, "没用过的话，你会怎么迁？", "NO_EVIDENCE", ResponseMode.OPEN_DESIGN),
        (QuestionType.SYSTEM_DESIGN, "设计一个短链系统", "NO_EVIDENCE", ResponseMode.SYSTEM_DESIGN),
    ],
)
def test_route_answer_exact(qtype, text, prov, expected):
    act, content, req = derive_axes(qtype, text)
    assert route_answer(act, content, req, prov, question_text=text) == expected


def test_derive_axes_three_axes():
    act, content, req = derive_axes(QuestionType.KNOWLEDGE, "你确定吗？为什么不用 Kafka")
    assert act == DialogueAct.CHALLENGE
    assert content == ContentType.KNOWLEDGE
    assert req == TruthRequirement.KNOWLEDGE_ONLY
    act, content, req = derive_axes(QuestionType.FOLLOW_UP, "那 Redis 会有什么问题？", is_follow_up=True)
    assert act == DialogueAct.FOLLOW_UP and content == ContentType.KNOWLEDGE


def test_strict_eval_no_alias_leniency():
    sys.path.insert(0, str(BACKEND_DIR))
    from evals.runners.route_runner import _route_matches_semantic, _route_matches_strict, run_route_eval

    assert not _route_matches_strict("OPEN_DESIGN", "SYSTEM_DESIGN")
    assert _route_matches_semantic("OPEN_DESIGN", "SYSTEM_DESIGN")
    result = run_route_eval()
    assert "route_accuracy_exact" in result and "route_accuracy_semantic" in result
    assert result["route_accuracy_exact"] >= 0.9


# ---------------------------------------------------------------------------
# G3 Session claims
# ---------------------------------------------------------------------------

def _pack(profile: str = RESUME, **extra) -> interview_pack.InterviewPack:
    payload = {"candidate_context": {"profile_text": profile}, "claims": [], "evidence_refs": [], "job": {}, **extra}
    return interview_pack.InterviewPack(id="p1", session_id="s1", revision=1, payload=payload)


def test_session_statement_without_evidence_warns_and_never_promotes(tmp_intel_db):
    pack = _pack()
    warnings = session_claims.record_candidate_speech("s1", pack, "我们后来用了 Redis Cluster 做分片。", qa_id="qa-1")
    assert len(warnings) == 1
    assert warnings[0]["type"] == "session_claim_warning" and warnings[0]["private"] is True
    assert {a["id"] for a in warnings[0]["actions"]} == {"slip", "continue_no_expand", "later"}
    row = intel_storage.list_session_claims("s1")[0]
    assert row["session_status"] == "SESSION_STATED" and row["provenance_status"] == "NO_EVIDENCE"
    # Never a long-term claim by itself.
    assert intel_storage.list_claims("cand") == []
    # The prompt forbids expanding it.
    constraints = session_claims.prompt_constraints("s1")
    assert "不要扩展细节" in constraints and "Redis Cluster" in constraints
    # And it does not unlock personal assertion.
    assert session_claims.session_status_for("s1", "Redis Cluster 怎么扩容") == SessionStatus.SESSION_STATED
    assert decide_assertion_policy("NO_EVIDENCE", "UNREVIEWED", "SESSION_STATED") == AssertionPolicy.REQUIRE_BOUNDARY


def test_sourced_statement_records_without_warning(tmp_intel_db):
    warnings = session_claims.record_candidate_speech("s1", _pack(), "我用了 Redis 管理 session state。")
    assert warnings == []


def test_slip_correction_blocks_reuse_and_next_session_does_not_inherit(tmp_intel_db):
    session_claims.record_candidate_speech("s1", _pack(), "我们后来用了 Redis Cluster。")
    claim_id = intel_storage.list_session_claims("s1")[0]["id"]
    row = session_claims.resolve(claim_id, "slip")
    assert row["session_status"] == "SESSION_CORRECTED"
    assert session_claims.session_status_for("s1", "Redis Cluster 呢") == SessionStatus.SESSION_CORRECTED
    assert "禁止再使用" in session_claims.prompt_constraints("s1")
    # Re-saying it later in the session does not resurrect it.
    assert session_claims.record_candidate_speech("s1", _pack(), "我们后来用了 Redis Cluster。") == []
    # Next interview: nothing inherited.
    assert session_claims.session_status_for("s2", "Redis Cluster 呢") == SessionStatus.NOT_STATED
    assert session_claims.prompt_constraints("s2") == ""


def test_review_is_the_only_promotion_path_and_keeps_axes_separate(tmp_intel_db):
    session_claims.record_candidate_speech("s1", _pack(), "我们后来用了 Redis Cluster。")
    claim_id = intel_storage.list_session_claims("s1")[0]["id"]
    result = session_claims.confirm_in_review(claim_id, candidate_id="cand", decision="confirm")
    rows = intel_storage.list_claims("cand")
    assert rows[0]["id"] == result["long_term_claim_id"]
    assert rows[0]["user_assertion_status"] == "USER_CONFIRMED"
    assert rows[0]["provenance_status"] == "NO_EVIDENCE"


# ---------------------------------------------------------------------------
# G4 InterviewPack: Job A / Job B contamination
# ---------------------------------------------------------------------------

JD_A = "AI Agent Engineer\n任职要求：\n熟悉 LangGraph 多智能体编排\n熟悉 RAG 检索增强"
JD_B = "Data Engineer\n任职要求：\n精通 Apache Spark 批处理\n熟悉 Flink 实时数仓"


def _save_job(job_id: str, title: str, must_have: list[str], jd: str) -> None:
    intel_storage.save_job_profile(job_id, {"title": title, "jd_text": jd, "must_have": must_have, "technologies": []})


def test_job_a_pack_is_not_contaminated_by_later_job_b(tmp_intel_db, monkeypatch):
    from api.assist import answer_worker
    from core.session import reset_session

    reset_session()
    session_id = "sess-A"
    monkeypatch.setattr(answer_worker, "_live_session_id", lambda: session_id)
    cfg = SimpleNamespace(
        models=[SimpleNamespace(name="模型一", api_key="k", model="fake", enabled=True, supports_vision=False)],
        written_exam_mode=False, written_exam_think=False, screen_capture_region="left_half",
        kb_enabled=False, kb_trigger_modes=[], assist_realtime_max_tokens=720,
        assist_realtime_high_churn_max_tokens=320, assist_realtime_concise_answer=False,
        resume_text=RESUME, interview_notes="", ai_policy_mode="AI_ALLOWED",
    )
    monkeypatch.setattr(answer_worker, "get_config", lambda: cfg)
    import services.llm.prompts as prompts

    monkeypatch.setattr(prompts, "get_config", lambda: SimpleNamespace(
        resume_text=RESUME, language="zh", position="后端", jd_text=JD_B, assist_answer_align_jd_enabled=True,
        interview_notes="", kb_prompt_excerpt_chars=300, answer_language="中文", screen_capture_region="left_half",
        assist_realtime_concise_answer=True,
    ))

    # 1. Build / freeze Pack A
    _save_job("job-A", "AI Agent Engineer", ["LangGraph 多智能体编排", "RAG 检索增强"], JD_A)
    payload = interview_pack.build_pack_payload(session_id=session_id, cfg=cfg, job_id="job-A")
    pack_a = interview_pack.freeze_pack(payload)
    # 2. Afterwards analyze Job B (becomes the "latest" job)
    _save_job("job-B", "Data Engineer", ["Apache Spark 批处理", "Flink 实时数仓"], JD_B)
    assert intel_storage.latest_job_id() == "job-B"

    # 3/4. Live session A asks a question
    seen: dict = {}

    def fake_stream(_model, messages, **kwargs):
        seen["user"] = str(messages[-1]["content"])
        seen["system"] = str(kwargs.get("system_prompt", ""))
        yield ("text", "LangGraph 适合做多步编排。")

    monkeypatch.setattr(answer_worker, "chat_stream_single_model", fake_stream)
    broadcasts: list[dict] = []
    from tests.test_assist_answer_worker import _deps  # reuse the worker harness

    answer_worker.process_question_parallel(
        ("讲讲多智能体编排怎么做", None, False, "asr", {"origin": "asr", "asr_turn_id": 1}),
        seq=0, model_idx=0, sess_v=0, deps=_deps(broadcasts=broadcasts),
    )
    prompt = seen["user"] + "\n" + seen["system"]
    # 5. Assertions
    assert "Spark" not in prompt and "Flink" not in prompt and "Data Engineer" not in prompt
    assert "LangGraph" in prompt
    done = next(e for e in broadcasts if e["type"] == "answer_done")
    assert done["guidance"]["context"]["pack_id"] == pack_a.id
    assert done["guidance"]["context"]["pack_frozen"] is True
    assert interview_pack.load_frozen_pack(session_id).job_id == "job-A"


def test_pack_revision_keeps_original_row(tmp_intel_db):
    _save_job("job-A", "AI Agent Engineer", ["RAG"], JD_A)
    _save_job("job-B", "Data Engineer", ["Spark"], JD_B)
    cfg = SimpleNamespace(resume_text=RESUME, ai_policy_mode="AI_ALLOWED", models=[], active_model=0)
    pack = interview_pack.freeze_pack(interview_pack.build_pack_payload(session_id="s", cfg=cfg, job_id="job-A"))
    rev = interview_pack.revise_pack(pack.id, {"job": intel_storage.get_job_profile("job-B")})
    assert rev.revision == 2 and rev.parent_id == pack.id
    assert intel_storage.get_interview_pack(pack.id)["pack"]["job"]["id"] == "job-A"
    assert interview_pack.load_frozen_pack("s").job_id == "job-B"
    assert [r["revision"] for r in intel_storage.list_interview_pack_revisions("s")] == [1, 2]


def test_unfrozen_session_never_reads_latest_job(tmp_intel_db):
    _save_job("job-B", "Data Engineer", ["Spark"], JD_B)
    pack = interview_pack.resolve_live_pack("nope", SimpleNamespace(resume_text=RESUME, ai_policy_mode=""))
    assert pack.frozen is False and pack.job == {} and pack.job_requirements == []


def test_pack_never_holds_api_keys(tmp_intel_db):
    cfg = SimpleNamespace(resume_text=RESUME, ai_policy_mode="AI_ALLOWED", active_model=0,
                          models=[SimpleNamespace(name="M", model="m", api_key="sk-secret-123", base_url="https://x")])
    payload = interview_pack.build_pack_payload(session_id="s", cfg=cfg)
    assert "sk-secret-123" not in str(payload)


def test_live_path_has_no_latest_reads():
    source = (BACKEND_DIR / "api" / "assist" / "answer_worker.py").read_text(encoding="utf-8")
    for forbidden in ("latest_job_id(", "active_candidate_id(", "latest_candidate(", "latest_resume("):
        assert forbidden not in source, forbidden


# ---------------------------------------------------------------------------
# G5 Context authority + dedupe
# ---------------------------------------------------------------------------

def _count(haystack: str, needle: str) -> int:
    return haystack.count(needle)


def test_fragment_dedupe_gate():
    resume_line = "WenNian 项目：我用 Redis 管理 session state，负责检索链路"
    kb = [SimpleNamespace(text="RAG 更适合频繁更新的知识，来源可追溯", path="rag.md")] * 2
    compiled = ContextCompiler(
        [
            ResumeProvider(resume_line + "\n" + resume_line),
            SessionMemoryProvider(memo_context=resume_line),
            KBProvider(kb),
        ]
    ).compile("WenNian 的 Redis 和 RAG", deep=True)
    rendered = "\n".join(item.text for item in compiled.items)
    assert _count(rendered, resume_line) <= 1
    assert _count(rendered, "RAG 更适合频繁更新的知识") <= 1
    assert all("content_hash" in item.metadata and "fragment_id" in item.metadata for item in compiled.items)
    assert sum(1 for d in compiled.dropped if d["reason"] == "duplicate_fragment") >= 3


def test_dedupe_keeps_stronger_evidence_copy():
    a = ResumeProvider("我用 Redis 管理 session state").collect("x")[0]
    b = KBProvider([SimpleNamespace(text="我用 Redis 管理 session state", path="k")]).collect("x")[0]
    kept, dropped = dedupe_fragments([b, a])
    assert len(kept) == 1 and kept[0].source_type.value == "resume"


def test_system_prompt_does_not_reinject_when_authoritative(monkeypatch):
    import services.llm.prompts as prompts

    monkeypatch.setattr(prompts, "get_config", lambda: SimpleNamespace(
        resume_text="UNIQUE_RESUME_LINE", language="zh", position="后端", jd_text="UNIQUE_JD", assist_answer_align_jd_enabled=True,
        interview_notes="", kb_prompt_excerpt_chars=300, answer_language="中文", screen_capture_region="left_half",
        assist_realtime_concise_answer=True,
    ))
    hit = SimpleNamespace(text="UNIQUE_KB", path="a.md", section_path="", score=1.0, page=None, origin="text", excerpt=lambda n: "UNIQUE_KB")
    legacy = prompts.build_system_prompt(kb_hits=[hit], include_resume=True, memo_context="UNIQUE_MEMO")
    authoritative = prompts.build_system_prompt(kb_hits=[hit], include_resume=True, memo_context="UNIQUE_MEMO", context_authoritative=True)
    for token in ("UNIQUE_RESUME_LINE", "UNIQUE_JD", "UNIQUE_MEMO"):
        assert token in legacy
        assert token not in authoritative


def test_compile_live_context_filters_kb_by_pack_selection():
    pack = _pack(selected_kb={"mode": "explicit", "paths": ["allowed.md"]})
    hits = [SimpleNamespace(text="允许的资料内容片段", path="allowed.md"), SimpleNamespace(text="未选择的资料内容片段", path="other.md")]
    compiled, sections = compile_live_context(pack, "资料", kb_hits=hits, deep=True)
    rendered = "\n".join(sections)
    assert "允许的资料" in rendered and "未选择的资料" not in rendered


# ---------------------------------------------------------------------------
# G7/G8 Latency clock + Fast Cue
# ---------------------------------------------------------------------------

def test_latency_clock_user_perceived_metrics():
    latency_clock.reset()
    latency_clock.mark_speech_end("s", 100.0)
    latency_clock.mark_first_partial("s", 99.0)
    latency_clock.start_turn("s", "qa", q1=100.4)
    latency_clock.mark("qa", "G0", 100.9)
    latency_clock.mark("qa", "A0", 101.5)
    latency_clock.mark("qa", "D0", 104.0)
    m = latency_clock.finish_turn("qa")
    assert m["qbd_ms"] == 400 and m["ttfug_user_ms"] == 900
    assert m["ttfug_internal_ms"] == 500 and m["ttfa_ms"] == 1100 and m["ttfug_predictive_ms"] == 1900
    # First model token is TTFA, never TTFUG.
    assert m["ttfa_ms"] != m["ttfug_user_ms"]


def test_ttfug_user_is_none_without_speech_end():
    latency_clock.reset()
    latency_clock.start_turn("s", "qa2", q1=5.0)
    latency_clock.mark("qa2", "G0", 5.2)
    m = latency_clock.finish_turn("qa2")
    assert m["ttfug_user_ms"] is None and m["ttfug_internal_ms"] == 200


def test_fast_cue_l0_boundary_and_sources():
    compiled, _ = compile_live_context(_pack(), "你用过 Redis Cluster 吗", deep=False)
    body = fast_cue.build_l0(
        question_raw="你用过 Redis Cluster 吗",
        resolved_question="你用过 Redis Cluster 吗",
        plan_meta={"assertion_policy": "REQUIRE_BOUNDARY", "truth_requirement": "PERSONAL_FACT_REQUIRED"},
        response_mode="EXPERIENCE_BOUNDARY_KNOWLEDGE",
        compiled_items=compiled.items,
    )
    texts = [c["text"] for c in body["cues"]]
    assert texts[0].startswith("先说边界") and "Redis Cluster" in texts[0]
    assert any("可衔接" in t and "Redis" in t for t in texts)
    assert all(c["source"] in {"PERSONAL_EVIDENCE", "KB_KNOWLEDGE", "WORLD_KNOWLEDGE", "HUMAN_COACH"} for c in body["cues"])
    assert not any(fast_cue._is_label(t) for t in texts)
    assert body["cautions"]


def test_fast_cue_knowledge_route_uses_kb_not_personal_claim():
    hits = [SimpleNamespace(text="RAG 更适合频繁更新的知识，来源可追溯。", path="rag.md"), SimpleNamespace(text="我在项目里用过 RAG", path="x.md")]
    body = fast_cue.build_l0(
        question_raw="RAG 和微调怎么选", resolved_question="RAG 和微调怎么选",
        plan_meta={"assertion_policy": "KNOWLEDGE_ONLY"}, response_mode="KNOWLEDGE", compiled_items=[], kb_hits=hits,
    )
    assert [c["source"] for c in body["cues"]] == ["KB_KNOWLEDGE"]
    assert "来源可追溯" in body["cues"][0]["text"]


def test_fast_cue_l1_drops_unsupported_first_person_claims():
    cues = fast_cue.parse_l1("• RAG 适合频繁更新\n• 我在生产用过 Milvus\n• 来源可追溯", {}, "我用 Redis 管理 session state")
    assert [c["text"] for c in cues] == ["RAG 适合频繁更新", "来源可追溯"]
    assert fast_cue.parse_l1("结论\n机制\n边界", {}, "") is None


def test_guidance_fast_arrives_before_first_deep_token(monkeypatch, tmp_intel_db):
    from api.assist import answer_worker
    from core.session import reset_session
    from tests.test_assist_answer_worker import _cfg, _deps

    reset_session()
    cfg = _cfg()
    cfg.resume_text = RESUME
    monkeypatch.setattr(answer_worker, "get_config", lambda: cfg)
    monkeypatch.setattr(answer_worker, "chat_stream_single_model", lambda *_a, **_k: iter([("text", "RAG 适合频繁更新的知识。")]))
    broadcasts: list[dict] = []
    answer_worker.process_question_parallel(
        ("RAG 和微调怎么选", None, False, "asr", {"origin": "asr", "asr_turn_id": 1}),
        seq=0, model_idx=0, sess_v=0, deps=_deps(broadcasts=broadcasts),
    )
    types = [e["type"] for e in broadcasts]
    assert types.index("guidance_fast") < types.index("answer_chunk")
    cue = broadcasts[types.index("guidance_fast")]
    for key in ("question_raw", "resolved_question", "direction", "cues", "evidence_anchors", "knowledge_sources",
                "cautions", "response_mode", "dialogue_act", "content_type", "truth_requirement", "source",
                "ttfug_user_ms", "ttfug_internal_ms"):
        assert key in cue, key
    done = broadcasts[types.index("answer_done")]
    assert done["latency"]["ttfug_internal_ms"] is not None
    assert done["latency"]["ttfug_internal_ms"] <= done["latency"]["ttfa_ms"]


# ---------------------------------------------------------------------------
# G9 Stream truth guard
# ---------------------------------------------------------------------------

def _stream(guard: StreamTruthGuard, text: str, step: int = 3) -> str:
    return "".join(guard.feed(text[i:i + step]) for i in range(0, len(text), step)) + guard.flush()


def test_knowledge_route_first_person_claim_is_rewritten_mid_stream():
    guard = StreamTruthGuard("KNOWLEDGE_ONLY")
    first = guard.feed("RAG 适合频繁更新的知识。")
    assert first == "RAG 适合频繁更新的知识。"  # knowledge streams immediately
    out = first + _stream(guard, "我之前在生产环境用过 Redis Cluster 做分片。如果我来设计会先评估。")
    assert "我之前在生产环境用过" not in out
    assert "如果我来设计会先评估" in out
    assert guard.rewrites == 1


def test_supported_first_person_claim_passes():
    guard = StreamTruthGuard("ALLOW_PERSONAL_ASSERTION", evidence_texts=[RESUME])
    assert _stream(guard, "我用 Redis 管理 session state。") == "我用 Redis 管理 session state。"


def test_qualified_assertion_blocks_new_metrics():
    guard = StreamTruthGuard("ALLOW_WITH_QUALIFIER", evidence_texts=[RESUME])
    out = _stream(guard, "我用 Redis 管理 session state，QPS 提升了 300%。")
    assert "300%" not in out or "没有可确认" in out
    assert guard.rewrites == 1


def test_negated_statement_is_not_a_claim():
    guard = StreamTruthGuard("KNOWLEDGE_ONLY")
    assert _stream(guard, "我没有用过 Kafka。") == "我没有用过 Kafka。"


# ---------------------------------------------------------------------------
# G13 Policy separation
# ---------------------------------------------------------------------------

def test_human_policy_independent_of_ai_policy():
    assert human_coach_allowed("HUMAN_PRACTICE_ONLY", session_kind="practice") is True
    assert human_coach_allowed("HUMAN_PRACTICE_ONLY", session_kind="live") is False
    assert human_coach_allowed("", session_kind="live") is False  # default is practice-only
    assert human_coach_allowed("HUMAN_ALLOWED", session_kind="live") is True
    assert human_coach_allowed("HUMAN_FORBIDDEN", session_kind="practice") is False


def test_defaults_share_privacy_off_and_human_practice_only():
    from core.config import AppConfig

    cfg = AppConfig()
    assert cfg.share_privacy_mode == "OFF"
    assert cfg.human_assistance_policy == "HUMAN_PRACTICE_ONLY"
    assert cfg.speech_adoption_analytics_live is False


def test_frozen_pack_ai_policy_is_authoritative():
    pack = _pack(ai_policy="AI_FORBIDDEN")
    assert live_guidance_allowed_for_pack(pack, SimpleNamespace(ai_policy_mode="AI_ALLOWED")) is False
    unfrozen = interview_pack.InterviewPack(id="", session_id="s", revision=0, payload={"ai_policy": "AI_FORBIDDEN"}, frozen=False)
    assert live_guidance_allowed_for_pack(unfrozen, SimpleNamespace(ai_policy_mode="AI_ALLOWED")) is True


# ---------------------------------------------------------------------------
# Migration v2 backfill
# ---------------------------------------------------------------------------

def test_migration_v2_backfills_axes_from_legacy_status(tmp_path):
    import sqlite3

    from services.storage import intelligence_migrations as mig

    db = sqlite3.connect(tmp_path / "old.db")
    mig._apply_statements(db, mig._V1_TABLES + mig._V1_INDEXES)
    db.execute("PRAGMA user_version = 1")
    now = 1.0
    for cid, status in (("c1", "SUPPORTED"), ("c2", "INFERRED"), ("c3", "VERIFIED"), ("c4", "CONTRADICTED"), ("c5", "VERIFIED")):
        db.execute(
            "INSERT INTO claim (id, candidate_id, type, text, source, truth_status, confidence, metadata_json, created_at, updated_at) "
            "VALUES (?, 'cand', 'fact', ?, 'resume', ?, 0.5, '{}', ?, ?)",
            (cid, cid, status, now, now),
        )
    db.execute("INSERT INTO evidence (id, candidate_id, source, text, metadata_json, created_at, updated_at) VALUES ('e1','cand','resume','x','{}',1,1)")
    db.execute("INSERT INTO claim_evidence (claim_id, evidence_id, created_at) VALUES ('c3','e1',1)")
    db.commit()
    before = mig.ensure_schema(db)
    assert before == 1
    rows = {r[0]: (r[1], r[2]) for r in db.execute("SELECT id, provenance_status, user_assertion_status FROM claim")}
    assert rows["c1"] == ("DIRECT_EVIDENCE", "UNREVIEWED")
    assert rows["c2"] == ("SUPPORTING_EVIDENCE", "UNREVIEWED")
    assert rows["c3"] == ("DIRECT_EVIDENCE", "USER_CONFIRMED")
    assert rows["c4"] == ("CONFLICTING_EVIDENCE", "UNREVIEWED")
    assert rows["c5"] == ("NO_EVIDENCE", "USER_CONFIRMED")  # confirmed but no source: not evidence
    assert mig.ensure_schema(db) == mig.LATEST_SCHEMA_VERSION  # idempotent
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"interview_pack", "session_claim"} <= tables


# ---------------------------------------------------------------------------
# G11 Candidate: user verdicts survive a resume rebuild; stories; voice
# ---------------------------------------------------------------------------

def test_resume_rebuild_keeps_user_verdicts_and_review_confirmed_facts(tmp_intel_db):
    from services.intelligence.candidate_representation import rebuild_and_persist

    first = rebuild_and_persist("WenNian 项目\n负责检索链路，使用 Redis 管理 session state")
    rows = intel_storage.list_claims(first.candidate_id)
    target = next(r for r in rows if "Redis" in r["text"])
    intel_storage.update_claim_axes(target["id"], user_assertion_status="USER_DENIED")
    # a Review-confirmed session statement (not from the resume)
    intel_storage.save_claims(first.candidate_id, [{"id": "claim-x", "text": "我们后来用了 Redis Cluster", "source": "session_statement", "truth_status": "UNKNOWN"}])
    intel_storage.update_claim_axes("claim-x", provenance_status="NO_EVIDENCE", user_assertion_status="USER_CONFIRMED")

    second = rebuild_and_persist("WenNian 项目\n负责检索链路，使用 Redis 管理 session state\n新增：Kafka 削峰")
    assert second.candidate_id != first.candidate_id
    new_rows = intel_storage.list_claims(second.candidate_id)
    redis = next(r for r in new_rows if "Redis 管理" in r["text"])
    assert redis["user_assertion_status"] == "USER_DENIED"
    cluster = next(r for r in new_rows if r["id"] == "claim-x")
    assert cluster["user_assertion_status"] == "USER_CONFIRMED" and cluster["provenance_status"] == "NO_EVIDENCE"


def test_denied_claim_never_enters_pack(tmp_intel_db):
    intel_storage.save_candidate_profile("cand", profile_text=RESUME)
    intel_storage.save_claims("cand", [{"id": "c-deny", "text": "我主导了全公司架构", "source": "resume"}])
    intel_storage.update_claim_axes("c-deny", user_assertion_status="USER_DENIED")
    payload = interview_pack.build_pack_payload(session_id="s", cfg=SimpleNamespace(resume_text="", ai_policy_mode=""), candidate_id="cand")
    assert all(c["id"] != "c-deny" for c in payload["claims"])


def test_stories_are_user_owned_and_frozen_into_pack(tmp_intel_db):
    intel_storage.save_story("story-1", "cand-old", {"title": "灰度回滚", "situation": "上线故障", "action": "回滚", "result": "10 分钟恢复"})
    payload = interview_pack.build_pack_payload(session_id="s", cfg=SimpleNamespace(resume_text="", ai_policy_mode=""), candidate_id="cand-new")
    assert payload["stories"][0]["title"] == "灰度回滚"


def test_voice_prompt_line():
    from api.intelligence.r2_router import voice_prompt_line

    line = voice_prompt_line({"conclusion_first": True, "target_seconds": 45, "shape": "bullet", "term_style": "keep_english_terms", "banned_phrases": ["赋能", "抓手"]})
    assert line.startswith("[我的表达]") and "先给结论" in line and "45 秒" in line and "赋能" in line
    assert voice_prompt_line({}) == ""


def test_turn_trace_saved_for_review(monkeypatch, tmp_intel_db):
    from api.assist import answer_worker
    from core.session import reset_session
    from tests.test_assist_answer_worker import _cfg, _deps

    reset_session()
    cfg = _cfg()
    cfg.resume_text = RESUME
    monkeypatch.setattr(answer_worker, "get_config", lambda: cfg)
    monkeypatch.setattr(answer_worker, "chat_stream_single_model", lambda *_a, **_k: iter([("text", "RAG 适合频繁更新的知识。")]))
    broadcasts: list[dict] = []
    answer_worker.process_question_parallel(
        ("RAG 和微调怎么选", None, False, "asr", {"origin": "asr", "asr_turn_id": 1}),
        seq=0, model_idx=0, sess_v=0, deps=_deps(broadcasts=broadcasts),
    )
    qa_id = next(e for e in broadcasts if e["type"] == "answer_done")["id"]
    trace = intel_storage.get_turn_traces([qa_id])[qa_id]
    assert trace["question_raw"] == "RAG 和微调怎么选"
    assert trace["fast_cue"]["direction"]
    assert "ttfug_internal_ms" in trace["latency"]
    assert trace["axes"]["content_type"] == "KNOWLEDGE"
    assert all("api_key" not in str(v) for v in trace.values())


# ---------------------------------------------------------------------------
# G7 end-of-turn fast flush + early cue
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("Redis 的持久化机制有哪些？", True),
        ("消息队列怎么保证不丢消息", True),
        ("讲讲你做过的订单系统重构。", True),
        ("How would you design a rate limiter", True),
        ("我们先聊聊缓存和", False),
        ("如果流量扩大十倍，因为", False),
        ("好的", False),
        ("嗯那个", False),
    ],
)
def test_end_of_turn_cue(text, expected):
    from services.intelligence.eot import looks_like_complete_question

    assert looks_like_complete_question(text) is expected


def _asr_machine(submitted, early_calls, clock):
    from api.assist.asr_state import AssistAsrStateMachine

    class _L:
        def info(self, *a, **k):
            pass

        warning = debug = info

    return AssistAsrStateMachine(
        broadcast=lambda _d: None,
        submit_answer_task=lambda task: submitted.append((clock["t"], task)) or True,
        begin_asr_turn=lambda: 1,
        record_asr_turn=lambda _t: None,
        is_high_churn_submission=lambda _c, _t: False,
        logger=_L(),
        clock=lambda: clock["t"],
        early_cue=lambda q, qa_id, meta: early_calls.append((clock["t"], q, qa_id)),
    )


def test_complete_question_skips_merge_gap_and_emits_early_cue():
    from core.config import AppConfig
    from core.session import Session

    cfg = AppConfig().model_copy(update={"assist_auto_answer_mode": "always"})
    submitted, early, clock = [], [], {"t": 10.0}
    sm = _asr_machine(submitted, early, clock)
    session = Session(session_id="t")
    sm.append_transcription_fragment(cfg, session, "Redis 的持久化机制有哪些？", clock["t"], False)
    while not submitted and clock["t"] < 14:
        clock["t"] += 0.02
        sm.try_flush_merge_buffer(cfg, session, clock["t"])
        sm.try_flush_question_group(cfg, session, clock["t"])
    t_submit, task = submitted[0]
    # short end-of-turn gap (0.35 s) + group confirm, not the 2.0 s merge gap
    assert t_submit - 10.0 < 1.7
    assert early and early[0][2] == task[4]["qa_id"] and task[4]["early_cue_emitted"] is True
    # The deep answer still honors the late-constraint grace.
    assert task[4]["dispatch_after_mono"] > t_submit


def test_end_of_turn_gap_still_waits_for_ongoing_speech():
    from core.config import AppConfig
    from core.session import Session

    cfg = AppConfig().model_copy(update={"assist_auto_answer_mode": "always"})
    submitted, early, clock = [], [], {"t": 1.0}
    sm = _asr_machine(submitted, early, clock)
    session = Session(session_id="t")
    sm.append_transcription_fragment(cfg, session, "为什么选择 Redis", 1.0, False)
    sm.note_speech_activity(1.3)  # streaming partial: the interviewer keeps talking
    sm.try_flush_merge_buffer(cfg, session, 1.5)
    assert not session.transcription_history
    sm.append_transcription_fragment(cfg, session, "而不是 Memcached？", 2.0, False)
    sm.try_flush_merge_buffer(cfg, session, 2.4)
    assert session.transcription_history and "Memcached" in session.transcription_history[-1]


def test_baseline_flags_keep_old_timing():
    from core.config import AppConfig
    from core.session import Session

    cfg = AppConfig().model_copy(update={"assist_auto_answer_mode": "always", "assist_eot_fast_flush": False, "intelligence_early_cue": False})
    submitted, early, clock = [], [], {"t": 10.0}
    sm = _asr_machine(submitted, early, clock)
    session = Session(session_id="t")
    sm.append_transcription_fragment(cfg, session, "Redis 的持久化机制有哪些？", clock["t"], False)
    assert not session.transcription_history  # waiting for the merge gap
    while not submitted and clock["t"] < 16:
        clock["t"] += 0.02
        sm.try_flush_merge_buffer(cfg, session, clock["t"])
        sm.try_flush_question_group(cfg, session, clock["t"])
    assert submitted and submitted[0][0] - 10.0 >= 2.0 and not early


def test_early_cue_and_worker_share_qa_id_and_first_g0(monkeypatch, tmp_intel_db):
    from api.assist import answer_worker
    from core.session import reset_session
    from tests.test_assist_answer_worker import _cfg, _deps

    reset_session()
    latency_clock.reset()
    cfg = _cfg()
    cfg.resume_text = RESUME
    monkeypatch.setattr(answer_worker, "get_config", lambda: cfg)
    sent: list[dict] = []
    early = answer_worker.emit_early_cue("RAG 和微调怎么选", "qa-early-1", {"source": "asr"}, broadcast=sent.append)
    assert early["type"] == "guidance_fast" and early["early"] is True and early["id"] == "qa-early-1"
    monkeypatch.setattr(answer_worker, "chat_stream_single_model", lambda *_a, **_k: iter([("text", "RAG 适合频繁更新。")]))
    broadcasts: list[dict] = []
    answer_worker.process_question_parallel(
        ("RAG 和微调怎么选", None, False, "asr", {"origin": "asr", "qa_id": "qa-early-1", "early_cue_emitted": True}),
        seq=0, model_idx=0, sess_v=0, deps=_deps(broadcasts=broadcasts),
    )
    start = next(e for e in broadcasts if e["type"] == "answer_start")
    done = next(e for e in broadcasts if e["type"] == "answer_done")
    assert start["id"] == "qa-early-1" and done["id"] == "qa-early-1"
    # G0 is the early emit, so TTFUG_internal is measured from the early turn start.
    assert done["latency"]["ttfug_internal_ms"] is not None
    assert done["latency"]["ttfug_internal_ms"] <= done["latency"]["ttfa_ms"]
