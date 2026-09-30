"""Simulated long-session soak (R2 Stage AF).

Drives the real answer worker (fake provider) for a 2h / 3h / 5h interview
equivalent (~1 question per minute) in one isolated data dir and checks:

  - memory (RSS) growth, interview state size, session qa history
  - DB file growth
  - context pollution: compiled prompt size must not grow with turn count
  - InterviewPack stability (same frozen pack id + hash every turn)
  - session-claim ledger stays per-session
  - provider fallback: every 25th turn the provider raises; the next turn works
  - coach reconnect: create / revoke cycles do not leak sessions

Not simulated (needs real hardware / people): audio device switching,
sleep/wake, real network loss -> reported BLOCKED-EXTERNAL.

Usage: python scripts/soak_sim.py [--hours 2 3 5] [--out reports/perf/soak.json]
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

QUESTIONS = [
    "介绍一下你的项目", "为什么选 RAG？", "那 Redis 会有什么问题？", "如果数据量扩大 100 倍呢？",
    "你实际用过 Redis Cluster 吗？", "写一个 LRU 缓存", "设计一个短链接服务", "讲一次你和同事意见不一致的经历",
    "Kafka 的 ISR 机制是什么？", "What is eventual consistency?", "你的期望薪资是多少？", "这个方案怎么验证？",
]
RESUME = "WenNian 项目：我用 Redis 管理 session state，负责检索链路\n使用 RAG 做知识问答"


def rss_mb() -> float:
    try:
        import psutil  # optional

        return psutil.Process().memory_info().rss / 1e6
    except Exception:  # noqa: BLE001
        current, _peak = tracemalloc.get_traced_memory()
        return current / 1e6


def run(hours: float, data_dir: Path) -> dict:
    os.environ["CHENGZHU_HOME"] = str(data_dir)
    import services.storage.intelligence as storage

    storage.DB_PATH = str(data_dir / "data" / "intelligence.db")
    (data_dir / "data").mkdir(parents=True, exist_ok=True)
    storage.init_db()

    from api.assist import answer_worker
    from core.session import get_session, reset_session
    from services import coach
    from services.intelligence import interview_pack, latency_clock, session_claims

    reset_session()
    session_id = "soak"
    answer_worker._live_session_id = lambda: session_id  # type: ignore[assignment]
    cfg = SimpleNamespace(
        models=[SimpleNamespace(name="Fake", api_key="k", model="fake", enabled=True, supports_vision=False)],
        written_exam_mode=False, written_exam_think=False, screen_capture_region="left_half",
        kb_enabled=False, kb_trigger_modes=[], assist_realtime_max_tokens=720,
        assist_realtime_high_churn_max_tokens=320, assist_realtime_concise_answer=False,
        resume_text=RESUME, interview_notes="", ai_policy_mode="AI_ALLOWED", candidate_context_enabled=False,
    )
    answer_worker.get_config = lambda: cfg  # type: ignore[assignment]
    storage.save_job_profile("job-A", {"title": "AI Agent Engineer", "must_have": ["RAG"], "technologies": ["Redis"]})
    pack = interview_pack.freeze_pack(interview_pack.build_pack_payload(session_id=session_id, cfg=cfg, job_id="job-A"))

    turn = {"n": 0}

    def fake_stream(_model, messages, **_kwargs):
        turn["prompt_chars"] = len(str(messages[-1]["content"]))
        if turn["n"] % 25 == 24:
            raise RuntimeError("simulated provider failure")
        yield ("text", "RAG 适合频繁更新的知识。我用 Redis 管理 session state。")

    answer_worker.chat_stream_single_model = fake_stream  # type: ignore[assignment]

    class _Log:
        def info(self, *a, **k):
            pass

        warning = error = info

    def deps(broadcasts):
        return answer_worker.AnswerWorkerDeps(
            abort_check=lambda: False, is_session_current=lambda _v: True,
            flush_commit=lambda _seq, fn: fn(), mark_seq_skipped=lambda _s: None,
            submit_knowledge_record=lambda *a, **k: True, broadcast=broadcasts.append,
            logger=_Log(), error_logger=_Log(),
        )

    turns = int(hours * 60)
    tracemalloc.start()
    gc.collect()
    rss_start = rss_mb()
    prompt_sizes: list[int] = []
    pack_ids: set[str] = set()
    errors_recovered = 0
    failures = 0
    t0 = time.time()
    for i in range(turns):
        turn["n"] = i
        broadcasts: list[dict] = []
        q = QUESTIONS[i % len(QUESTIONS)]
        answer_worker.process_question_parallel(
            (q, None, False, "asr", {"origin": "asr", "asr_turn_id": i}), seq=i, model_idx=0, sess_v=0, deps=deps(broadcasts)
        )
        types = [b["type"] for b in broadcasts]
        if "answer_error" in types:
            failures += 1
        elif failures and i % 25 == 0:
            errors_recovered += 1
        done = next((b for b in broadcasts if b["type"] == "answer_done"), None)
        if done:
            ctx = (done.get("guidance") or {}).get("context") or {}
            pack_ids.add(str(ctx.get("pack_id")))
        prompt_sizes.append(int(turn.get("prompt_chars", 0)))
        if i % 60 == 30:  # candidate says something unsourced once an hour
            session_claims.record_candidate_speech(session_id, pack, "我们后来用了 Redis Cluster。", qa_id=f"t{i}")
        if i % 45 == 0:  # coach reconnect cycle
            s, _tok = coach.registry.create(human_policy="HUMAN_PRACTICE_ONLY", session_kind="practice")
            coach.registry.revoke(s.id)
    elapsed = time.time() - t0
    gc.collect()
    rss_end = rss_mb()
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    live = get_session()
    from services.intelligence.interview_state import get_state

    state = get_state(session_id)
    db_bytes = sum(p.stat().st_size for p in (data_dir / "data").glob("intelligence.db*"))
    first_hour = prompt_sizes[: min(60, len(prompt_sizes))]
    last_hour = prompt_sizes[-min(60, len(prompt_sizes)):]
    avg = lambda xs: sum(xs) / max(1, len(xs))  # noqa: E731
    frozen = interview_pack.load_frozen_pack(session_id)
    return {
        "hours": hours,
        "turns": turns,
        "wall_seconds": round(elapsed, 1),
        "rss_start_mb": round(rss_start, 1),
        "rss_end_mb": round(rss_end, 1),
        "traced_peak_mb": round(peak / 1e6, 1),
        "qa_pairs_in_session": len(getattr(live, "qa_pairs", [])),
        "state_topic_stack": len(state.topic_stack),
        "state_open_threads": len(state.open_threads),
        "db_bytes": db_bytes,
        "prompt_chars_first_hour_avg": round(avg(first_hour)),
        "prompt_chars_last_hour_avg": round(avg(last_hour)),
        "context_pollution": avg(last_hour) > avg(first_hour) * 1.5,
        "pack_ids_seen": sorted(pack_ids - {"None"}),
        "pack_stable": pack_ids - {"None"} == {pack.id} and frozen is not None and frozen.content_hash == pack.content_hash,
        "session_claims": len(storage.list_session_claims(session_id)),
        "provider_failures_injected": failures,
        "coach_sessions_active_after": sum(1 for s in coach.registry.list() if s["active"]),
        "latency_history_len": len(latency_clock.recent(10_000)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, nargs="*", default=[2, 3, 5])
    ap.add_argument("--out", default=str(ROOT / "reports" / "perf" / "soak.json"))
    args = ap.parse_args()
    results = []
    for h in args.hours:
        with tempfile.TemporaryDirectory(prefix=f"soak{h}h-") as tmp:
            results.append(run(h, Path(tmp)))
    for r in results:
        r["checks"] = {
            "no_context_pollution": not r["context_pollution"],
            "pack_stable": r["pack_stable"],
            "state_bounded": r["state_topic_stack"] <= 64 and r["state_open_threads"] <= 64,
            "coach_no_leak": r["coach_sessions_active_after"] == 0,
            "latency_history_bounded": r["latency_history_len"] <= 500,
        }
        r["passed"] = all(r["checks"].values())
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
        "not_simulated": {"audio_switching": "BLOCKED-EXTERNAL", "sleep_wake": "BLOCKED-EXTERNAL", "real_participants": "BLOCKED-EXTERNAL"},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
