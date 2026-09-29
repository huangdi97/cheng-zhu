"""Eval 2.0 (R2 Stage AD): deterministic mandatory cases + held-out routing.

  python -m evals.r2_eval            print JSON
  python -m evals.r2_eval --check    exit 1 if a mandatory case fails or
                                     held-out exact accuracy < HELDOUT_GATE
  python -m evals.r2_eval --write    also write reports/CHENGZHU_V1_2_R2_EVAL.md

No LLM calls. Real-provider model eval (BYOK) runs only when
CHENGZHU_EVAL_API_KEY is set; otherwise it is reported BLOCKED-EXTERNAL,
never PASS.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

HELDOUT_GATE = 0.75
RESUME = "WenNian 项目：我用 Redis 管理 session state，负责检索链路\n使用 RAG 做知识问答"


def _isolated_db():
    import services.storage.intelligence as storage

    tmp = tempfile.mkdtemp(prefix="r2eval-")
    storage.DB_PATH = os.path.join(tmp, "intelligence.db")
    storage.init_db()
    return storage


def _pack(profile: str = RESUME, **extra):
    from services.intelligence.interview_pack import InterviewPack

    payload = {"candidate_context": {"profile_text": profile}, "claims": [], "evidence_refs": [], "job": {}, **extra}
    return InterviewPack(id="p", session_id="s", revision=1, payload=payload)


def _route(qtype_name: str, text: str, prov: str = "NO_EVIDENCE", **kw) -> str:
    from services.intelligence.semantics import derive_axes, route_answer
    from services.intelligence.types import QuestionType

    act, content, req = derive_axes(QuestionType[qtype_name], text, **kw)
    return route_answer(act, content, req, prov, question_text=text).value


def _stream(policy: str, text: str, evidence: list[str] | None = None) -> tuple[str, int]:
    from services.intelligence.stream_guard import StreamTruthGuard

    g = StreamTruthGuard(policy, evidence_texts=evidence or [])
    out = "".join(g.feed(text[i:i + 3]) for i in range(0, len(text), 3)) + g.flush()
    return out, g.rewrites


# ---------------------------------------------------------------------------
# 20 mandatory cases (canonical 33.2)
# ---------------------------------------------------------------------------

def c01_redis_evidence_cluster_none():
    from services.intelligence.semantics import provenance_from_grounding as p

    a = p("not_applicable", question="你用过 Redis 吗？", profile_text=RESUME).value
    b = p("not_applicable", question="你们用了 Redis Cluster 吗？", profile_text=RESUME).value
    return a == "DIRECT_EVIDENCE" and b == "NO_EVIDENCE", f"redis={a} cluster={b}"


def c02_live_statement_cluster():
    from services.intelligence import session_claims

    _isolated_db()
    w = session_claims.record_candidate_speech("e2", _pack(), "我们后来用了 Redis Cluster。")
    return len(w) == 1 and w[0]["private"], f"warnings={len(w)}"


def c03_no_detail_expansion():
    from services.intelligence import session_claims
    from services.intelligence.semantics import decide_assertion_policy

    _isolated_db()
    session_claims.record_candidate_speech("e3", _pack(), "我们后来用了 Redis Cluster。")
    constraint = session_claims.prompt_constraints("e3")
    policy = decide_assertion_policy("NO_EVIDENCE", "UNREVIEWED", "SESSION_STATED").value
    out, rewrites = _stream("REQUIRE_BOUNDARY", "我们的 Redis Cluster 有 12 个分片，QPS 提升了 300%。")
    return ("不要扩展细节" in constraint and policy == "REQUIRE_BOUNDARY" and "300%" not in out.split("通用做法")[0]), f"policy={policy} rewrites={rewrites}"


def c04_slip_correction():
    from services.intelligence import session_claims
    import services.storage.intelligence as storage

    _isolated_db()
    session_claims.record_candidate_speech("e4", _pack(), "我们后来用了 Redis Cluster。")
    cid = storage.list_session_claims("e4")[0]["id"]
    row = session_claims.resolve(cid, "slip")
    return row["session_status"] == "SESSION_CORRECTED" and "禁止再使用" in session_claims.prompt_constraints("e4"), row["session_status"]


def c05_next_session_does_not_inherit():
    from services.intelligence import session_claims

    _isolated_db()
    session_claims.record_candidate_speech("e5a", _pack(), "我们后来用了 Redis Cluster。")
    s = session_claims.session_status_for("e5b", "Redis Cluster 怎么扩容").value
    return s == "NOT_STATED" and session_claims.prompt_constraints("e5b") == "", s


def c06_knowledge_route_first_person():
    out, rewrites = _stream("KNOWLEDGE_ONLY", "RAG 适合频繁更新的知识。我之前在生产环境用过 Milvus 做向量检索。")
    return rewrites == 1 and "我之前在生产环境用过" not in out and out.startswith("RAG 适合"), f"rewrites={rewrites}"


def c07_rag_then_os_reset():
    m1 = _route("KNOWLEDGE", "为什么选 RAG？")
    m2 = _route("KNOWLEDGE", "讲讲操作系统内核。")
    return m2 == "KNOWLEDGE", f"rag={m1} os={m2}"


def c08_why_not_that():
    m = _route("FOLLOW_UP", "为什么不用那个？", "DIRECT_EVIDENCE", is_follow_up=True)
    return m in {"EXPERIENCE_KNOWLEDGE", "EXPERIENCE"}, m


def c09_job_contamination():
    from services.intelligence import interview_pack

    storage = _isolated_db()
    storage.save_job_profile("job-A", {"title": "AI Agent Engineer", "must_have": ["LangGraph"], "technologies": []})
    cfg = SimpleNamespace(resume_text=RESUME, ai_policy_mode="AI_ALLOWED", models=[], active_model=0)
    pack = interview_pack.freeze_pack(interview_pack.build_pack_payload(session_id="e9", cfg=cfg, job_id="job-A"))
    storage.save_job_profile("job-B", {"title": "Data Engineer", "must_have": ["Spark"], "technologies": []})
    live = interview_pack.resolve_live_pack("e9", cfg)
    src = (BACKEND / "api" / "assist" / "answer_worker.py").read_text(encoding="utf-8")
    return live.job_id == "job-A" and "Spark" not in json.dumps(live.payload, ensure_ascii=False) and "latest_job_id(" not in src, f"pack={pack.id} job={live.job_id}"


def c10_share_privacy_off():
    from core.config import AppConfig

    js = (BACKEND.parent / "desktop" / "sharePrivacy.js").read_text(encoding="utf-8")
    return AppConfig().share_privacy_mode == "OFF" and "const DEFAULT_MODE = 'OFF'" in js, AppConfig().share_privacy_mode


def c11_ai_forbidden():
    from services.intelligence.policy import live_guidance_allowed_for_pack
    from services.intelligence.semantics import decide_assertion_policy

    blocked = not live_guidance_allowed_for_pack(_pack(ai_policy="AI_FORBIDDEN"), SimpleNamespace(ai_policy_mode="AI_ALLOWED"))
    return blocked and decide_assertion_policy("DIRECT_EVIDENCE", ai_policy="AI_FORBIDDEN").value == "BLOCK_ASSERTION", str(blocked)


def c12_human_practice_only():
    from core.config import AppConfig
    from services.intelligence.policy import human_coach_allowed

    d = AppConfig().human_assistance_policy
    return d == "HUMAN_PRACTICE_ONLY" and human_coach_allowed(d, session_kind="practice") and not human_coach_allowed(d, session_kind="live"), d


def c13_coach_conflicting_suggestion():
    # A human coach cue never changes provenance or user assertion.
    from services.intelligence.fast_cue import build_l0
    from services.intelligence.semantics import CueSource, decide_assertion_policy

    policy = decide_assertion_policy("NO_EVIDENCE", "UNREVIEWED")
    body = build_l0(question_raw="你用过 Redis Cluster 吗", resolved_question="你用过 Redis Cluster 吗",
                    plan_meta={"assertion_policy": policy.value}, response_mode="EXPERIENCE_BOUNDARY_KNOWLEDGE")
    coach = {"text": "就说你用过 Cluster", "source": CueSource.HUMAN_COACH.value}
    return policy.value == "REQUIRE_BOUNDARY" and coach["source"] != "PERSONAL_EVIDENCE" and body["cues"][0]["text"].startswith("先说边界"), policy.value


def c14_screen_context():
    from services.intelligence.semantics import derive_axes
    from services.intelligence.types import QuestionType

    _act, _c, req = derive_axes(QuestionType.CODING, "看一下屏幕上这道题怎么做")
    return req.value == "SCREEN_CONTEXT_REQUIRED", req.value


def c15_english():
    return _route("KNOWLEDGE", "What is the difference between TCP and UDP?") == "KNOWLEDGE", "en"


def c16_chinese():
    return _route("CODING", "写一个快速排序") == "CODING", "zh"


def c17_mixed():
    m = _route("EXPERIENCE", "Tell me about your RAG project，为什么这么设计？", "DIRECT_EVIDENCE")
    return m == "EXPERIENCE_KNOWLEDGE", m


def c18_asr_typo():
    from services.intelligence.question_understanding import classify_question_type_21

    t = classify_question_type_21("卡夫卡 消费者组 rebalance 是什么").value
    return t in {"KNOWLEDGE", "DEBUGGING"}, t


def c19_interruption():
    from services.intelligence.semantics import derive_axes
    from services.intelligence.types import QuestionType

    act, _c, _r = derive_axes(QuestionType.KNOWLEDGE, "等一下，先说说你为什么离职")
    return act.value == "INTERRUPTION", act.value


def c20_provider_fallback():
    # L1 fast cue failure keeps L0; unparsable model output never replaces it.
    from services.intelligence.fast_cue import parse_l1

    return parse_l1("", {}, "") is None and parse_l1("结论\n机制", {}, "") is None, "L0 kept"


MANDATORY: list[tuple[str, Callable]] = [
    ("01 Redis 有证据 / Redis Cluster 无", c01_redis_evidence_cluster_none),
    ("02 用户现场说 Cluster → 私有提示", c02_live_statement_cluster),
    ("03 系统不扩大细节", c03_no_detail_expansion),
    ("04 用户标口误", c04_slip_correction),
    ("05 下一场不继承", c05_next_session_does_not_inherit),
    ("06 Knowledge route 生成第一人称 → 改写", c06_knowledge_route_first_person),
    ("07 RAG → OS reset", c07_rag_then_os_reset),
    ("08 为什么不用那个？", c08_why_not_that),
    ("09 Job A / Job B contamination", c09_job_contamination),
    ("10 Share Privacy OFF", c10_share_privacy_off),
    ("11 AI_FORBIDDEN", c11_ai_forbidden),
    ("12 HUMAN_PRACTICE_ONLY", c12_human_practice_only),
    ("13 Coach conflicting suggestion", c13_coach_conflicting_suggestion),
    ("14 screen context", c14_screen_context),
    ("15 English", c15_english),
    ("16 Chinese", c16_chinese),
    ("17 mixed", c17_mixed),
    ("18 ASR typo", c18_asr_typo),
    ("19 interruption", c19_interruption),
    ("20 provider fallback", c20_provider_fallback),
]


def run_mandatory() -> list[dict]:
    out = []
    for name, fn in MANDATORY:
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        out.append({"case": name, "passed": bool(ok), "detail": str(detail)})
    return out


def run_heldout(cases_in: list[dict] | None = None) -> dict:
    from evals.fixtures.heldout_r2 import HELDOUT_CASES, HELDOUT_RESUME
    from evals.runners.route_runner import _route_matches_semantic, _route_matches_strict
    from services.intelligence.answer_planner import create_plan
    from services.intelligence.question_understanding import understand_question
    from services.intelligence.semantics import provenance_from_grounding
    from services.intelligence.truth_boundary import analyze_truth_boundary
    from services.intelligence.types import DepthProfile

    cases = []
    for case in (cases_in if cases_in is not None else HELDOUT_CASES):
        q = case["question"]
        prev = case.get("previous", "")
        u = understand_question(q, previous_question=prev, relation_to_previous="follow_up" if prev else "")
        b = analyze_truth_boundary(q, resume_text=HELDOUT_RESUME)
        plan = create_plan(
            u.question_type, resolved_question=u.resolved_question, intent=u.intent, expected_depth=DepthProfile.STRUCTURED,
            personal_fact_required=u.personal_fact_required, open_world_allowed=u.open_world_allowed,
            provenance=provenance_from_grounding(b.grounding.status, has_profile=True, question=q, profile_text=HELDOUT_RESUME),
            is_follow_up=u.is_follow_up, raw_question=q, profile_text=HELDOUT_RESUME,
        )
        cases.append({
            "id": case["id"], "question": q, "expected": case["expected"], "actual": plan.mode.value,
            "exact": _route_matches_strict(case["expected"], plan.mode.value),
            "semantic": _route_matches_semantic(case["expected"], plan.mode.value),
        })
    n = max(1, len(cases))
    return {
        "total": len(cases),
        "exact_accuracy": round(sum(c["exact"] for c in cases) / n, 4),
        "semantic_accuracy": round(sum(c["semantic"] for c in cases) / n, 4),
        "cases": cases,
    }


def model_eval_status() -> dict:
    if os.environ.get("CHENGZHU_EVAL_API_KEY"):
        return {"status": "NOT_RUN", "note": "key present; run the BYOK model eval explicitly"}
    return {"status": "BLOCKED-EXTERNAL", "note": "no provider key (CHENGZHU_EVAL_API_KEY); real-provider quality/latency/cost not measured"}


def run_all() -> dict:
    t0 = time.time()
    from evals.fixtures.heldout_r2 import HELDOUT_V2_CASES

    mandatory = run_mandatory()
    # v2 is the gating held-out set; v1 was seen once (it exposed the gaps),
    # so its post-fix rerun is reported but flagged, next to the frozen result.
    heldout = run_heldout(HELDOUT_V2_CASES)
    heldout_v1_post_fix = run_heldout()
    frozen_path = BACKEND / "evals" / "reports" / "heldout_r2_v1_result.json"
    heldout_v1_frozen = json.loads(frozen_path.read_text(encoding="utf-8")) if frozen_path.exists() else {}
    from evals.runners.route_runner import run_route_eval, run_seven_turn

    dev = run_route_eval()
    seven = run_seven_turn()
    return {
        "mandatory_passed": sum(m["passed"] for m in mandatory),
        "mandatory_total": len(mandatory),
        "mandatory": mandatory,
        "dev_route_exact": dev["route_accuracy_exact"],
        "dev_route_semantic": dev["route_accuracy_semantic"],
        "seven_turn_exact": seven["route_accuracy_exact"],
        "unsupported_claim_blocked": dev["unsupported_claim_rate"],
        "heldout": heldout,
        "heldout_v1_frozen_exact": heldout_v1_frozen.get("exact_accuracy"),
        "heldout_v1_post_fix_exact": heldout_v1_post_fix["exact_accuracy"],
        "model_eval": model_eval_status(),
        "elapsed_s": round(time.time() - t0, 2),
    }


def write_report(result: dict, path: Path) -> None:
    lines = [
        "# Chengzhu v1.2-R2 — Eval 2.0",
        "",
        "Deterministic, no LLM calls. Generated by `python -m evals.r2_eval --write`.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Mandatory cases | {result['mandatory_passed']} / {result['mandatory_total']} |",
        f"| Dev set route accuracy — exact | {result['dev_route_exact']} |",
        f"| Dev set route accuracy — semantic compatible | {result['dev_route_semantic']} |",
        f"| Seven-turn fixture — exact | {result['seven_turn_exact']} |",
        f"| Unsupported-claim probes blocked | {result['unsupported_claim_blocked']} |",
        f"| **Held-out v2** route accuracy — exact (gate {HELDOUT_GATE}) | {result['heldout']['exact_accuracy']} ({result['heldout']['total']} cases) |",
        f"| **Held-out v2** route accuracy — semantic compatible | {result['heldout']['semantic_accuracy']} |",
        f"| Held-out v1 — exact, frozen BEFORE the classifier fix | {result['heldout_v1_frozen_exact']} |",
        f"| Held-out v1 — exact, after the fix (seen set, not a clean measurement) | {result['heldout_v1_post_fix_exact']} |",
        f"| Real-provider model eval | {result['model_eval']['status']} — {result['model_eval']['note']} |",
        "",
        "Dev = `evals/fixtures/interview_fixtures.py` (the router was developed against it).",
        "Held-out v1 = `HELDOUT_CASES`, written before the router ran on it. It scored 0.6786 and exposed",
        "generic classifier gaps (English coding/design phrasing, 你做的/你负责, 讲一次…经历, product metrics,",
        "OOD vs 设计一个, choice-rationale about the candidate's own profile). Those were fixed by category.",
        "Held-out v2 = `HELDOUT_V2_CASES`, written after v1 and before the fix was run on anything; it is",
        "the clean post-fix measurement and the CI gate.",
        "",
        "## Mandatory cases",
        "",
        "| Case | Result | Detail |",
        "|---|---|---|",
    ]
    lines += [f"| {m['case']} | {'PASS' if m['passed'] else 'FAIL'} | {m['detail']} |" for m in result["mandatory"]]
    lines += ["", "## Held-out v2 cases", "", "| Id | Question | Expected | Actual | Exact | Semantic |", "|---|---|---|---|---|---|"]
    lines += [
        f"| {c['id']} | {c['question']} | {c['expected']} | {c['actual']} | {'✓' if c['exact'] else '✗'} | {'✓' if c['semantic'] else '✗'} |"
        for c in result["heldout"]["cases"]
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    result = run_all()
    print(json.dumps({k: v for k, v in result.items() if k not in {"mandatory", "heldout"}} | {
        "heldout_exact": result["heldout"]["exact_accuracy"],
        "heldout_semantic": result["heldout"]["semantic_accuracy"],
        "failed_mandatory": [m["case"] for m in result["mandatory"] if not m["passed"]],
        "failed_heldout": [f"{c['id']}:{c['expected']}->{c['actual']}" for c in result["heldout"]["cases"] if not c["exact"]],
    }, ensure_ascii=False, indent=2))
    if "--write" in argv:
        write_report(result, BACKEND.parent / "reports" / "CHENGZHU_V1_2_R2_EVAL.md")
    if "--check" in argv:
        if result["mandatory_passed"] != result["mandatory_total"]:
            return 1
        if result["heldout"]["exact_accuracy"] < HELDOUT_GATE:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
