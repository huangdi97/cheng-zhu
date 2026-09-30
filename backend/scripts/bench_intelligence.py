"""Intelligence performance benchmark (canonical Stage W).

Measures the local overhead of each intelligence stage (the provider latency
is measured separately by the existing bench_prompt / live pipeline timings).

Budgets (master doc 37):
- Context Compiler P50 < 300 ms (local data)
- state update / question resolve / planner: p50 < 5 ms (pure rules)
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.intelligence.answer_planner import create_plan  # noqa: E402
from services.intelligence.context_compiler import (  # noqa: E402
    ContextCompiler,
    EvidenceProvider,
    JobProvider,
    KBProvider,
    ResumeProvider,
    SessionMemoryProvider,
)
from services.intelligence.interview_state import apply_event, reset_state  # noqa: E402
from services.intelligence.question_understanding import understand_question  # noqa: E402
from services.intelligence.realtime_bridge import build_intelligence_layer  # noqa: E402
from services.intelligence.truth_boundary import analyze_truth_boundary  # noqa: E402
from services.intelligence.types import QuestionType, DepthProfile  # noqa: E402

_RESUME = "\n".join(
    [
        "构建 RAG + Agent 系统，使用 Redis 保存部分 session state。",
        "负责核心检索链路，QPS 3万，P50 延迟 200ms。",
        "技术栈：Python, FastAPI, Redis, Kafka, Docker。",
        "优化混合检索与 rerank 链路，成本下降 40%。",
    ]
    * 6
)
_QUESTION = "为什么选 RAG？如果数据量扩大 100 倍呢？"
_RUNS = 200


def _p50_p95(values: list[float]) -> tuple[float, float]:
    ordered = sorted(values)
    return ordered[len(ordered) // 2], ordered[int(len(ordered) * 0.95)]


def _bench(label: str, fn) -> dict:
    values: list[float] = []
    for _ in range(_RUNS):
        t0 = time.perf_counter()
        fn()
        values.append((time.perf_counter() - t0) * 1000)
    p50, p95 = _p50_p95(values)
    return {"stage": label, "p50_ms": round(p50, 3), "p95_ms": round(p95, 3)}


def run_perf() -> dict:
    reset_state("perf")
    compiler = ContextCompiler(
        [
            ResumeProvider(_RESUME),
            EvidenceProvider(),
            SessionMemoryProvider(memo_context="已问过：项目；已声称：RAG"),
            JobProvider(job_requirements=["Python", "Redis", "Kafka"], job_summary="高级后端"),
            KBProvider(),
        ]
    )
    state = None

    def _question_resolve():
        nonlocal state
        state = apply_event("perf", "question_received", {"question": _QUESTION, "question_type": "KNOWLEDGE"})

    def _understand():
        understand_question(_QUESTION, interview_state=state, previous_question="介绍一下你的项目")

    def _boundary():
        analyze_truth_boundary(_QUESTION, resume_text=_RESUME)

    def _plan():
        create_plan(
            QuestionType(state.question_type) if state and state.question_type else QuestionType.KNOWLEDGE,
            resolved_question=_QUESTION,
            expected_depth=DepthProfile.DEEP,
        )

    def _compile():
        compiler.compile(_QUESTION, deep=False, active_topic="rag")

    def _bridge():
        build_intelligence_layer(
            _QUESTION,
            previous_question="介绍一下你的项目",
            session_id="perf",
            grounding_status="not_applicable",
        )

    results = [
        _bench("question_resolve (state update)", _question_resolve),
        _bench("question_understanding", _understand),
        _bench("truth_boundary (pre-generation)", _boundary),
        _bench("answer_planner", _plan),
        _bench("context_compiler (fast)", _compile),
        _bench("intelligence_layer (full bridge)", _bridge),
    ]

    report = {
        "date": time.strftime("%Y-%m-%d"),
        "runs": _RUNS,
        "results": results,
        "budgets": {
            "context_compiler_p50_max_ms": 300,
            "fast_path_first_cue_p50_max_ms": 1500,
            "rules_p50_target_ms": 5,
        },
        "verdict": "PASS" if all(r["p50_ms"] < 300 for r in results) else "CHECK",
    }

    reports_dir = Path(__file__).resolve().parents[2] / "reports"
    reports_dir.mkdir(exist_ok=True)
    target = reports_dir / "CHENGZHU_V1_PERF_BENCHMARK.md"
    lines = [
        "# 成竹 Chengzhu v1.0 Performance Benchmark",
        "",
        f"**日期**：{report['date']} | **runs**：{_RUNS} | **判定**：{report['verdict']}",
        "",
        "| Stage | p50 ms | p95 ms | Budget |",
        "| --- | --- | --- | --- |",
    ]
    for r in results:
        budget = "P50 < 300" if "compiler" in r["stage"] else "rules < 5"
        lines.append(f"| {r['stage']} | {r['p50_ms']} | {r['p95_ms']} | {budget} |")
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- 本地 overhead 与 provider latency 分开报告；provider 延迟见 live pipeline 的 first_token_ms/total_ms（telemetry）。",
            "- Fast path 第一可用提示 = ASR partial 更新 + deterministic 规则（<5ms）+ provider 首 token；LLM 首 token 延迟由 provider 主导。",
            "- state update 含 interview_state_snapshot 的 SQLite 写入（WAL）。",
        ]
    )
    target.write_text("\n".join(lines), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = run_perf()
    print(json.dumps(result, ensure_ascii=False, indent=2)[:1600])
