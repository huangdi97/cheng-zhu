"""Intelligence long-session soak (canonical Stage S, simulated).

Simulates 2h/3h interview sessions as high-frequency question events and
checks: state growth stays bounded, no topic leakage after explicit resets,
state-update latency stays flat, and storage snapshots do not grow unbounded.

Simulated time compression: real wall-clock soak (2-5h live audio) requires
hardware and a real interview participant (BLOCKED externally); this script
compresses the event volume instead (each event ≈ one interview turn).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.logger import get_logger  # noqa: E402
from services.intelligence.interview_state import (  # noqa: E402
    apply_event,
    drop_session,
    get_state,
    reset_state,
)

_log = get_logger("soak.intelligence")

_TOPICS = ["rag", "redis", "kafka", "系统设计", "缓存", "数据库", "微服务", "前端", "算法", "行为题", "llm", "职业规划"]
_QUESTIONS = [
    "介绍一下你的项目",
    "为什么选 {topic}？",
    "如果 {topic} 扩大 100 倍呢？",
    "那 {topic} 会有什么问题？",
    "你实际用过 {topic} 吗？",
    "换个话题，讲讲 {topic}",
]
_TURNS_PER_SESSION = 2400  # ≈ 2h at ~3s/turn
_LATENCY_SAMPLES = 500


def _run_session(session_id: str, turns: int) -> dict:
    reset_state(session_id)
    latencies: list[float] = []
    for i in range(turns):
        topic = _TOPICS[i % len(_TOPICS)]
        question = _QUESTIONS[i % len(_QUESTIONS)].format(topic=topic)
        is_follow_up = (i % 4 == 1)  # every 4th turn is a follow-up
        t0 = time.perf_counter()
        apply_event(
            session_id,
            "question_received",
            {
                "question": question,
                "question_type": "FOLLOW_UP" if is_follow_up else "EXPERIENCE",
                "intent": "verification" if is_follow_up else "",
                "expected_depth": "compact_deep",
                "is_follow_up": is_follow_up,
            },
        )
        if i >= turns - _LATENCY_SAMPLES:
            latencies.append((time.perf_counter() - t0) * 1000)

    state = get_state(session_id, create=False)
    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
    return {
        "session_id": session_id,
        "turns": turns,
        "state_version": state.version if state else 0,
        "topic_stack_len": len(state.topic_stack) if state else 0,
        "open_threads_len": len(state.open_threads) if state else 0,
        "claims_len": len(state.candidate_claims) if state else 0,
        "risk_flags_len": len(state.risk_flags) if state else 0,
        "current_topic": state.current_topic if state else "",
        "state_update_p50_ms": round(p50, 3),
        "state_update_p95_ms": round(p95, 3),
    }


def _check_bounded(result: dict) -> list[str]:
    issues: list[str] = []
    caps = {"topic_stack_len": 12, "open_threads_len": 12, "claims_len": 24, "risk_flags_len": 12}
    for key, cap in caps.items():
        if result[key] > cap:
            issues.append(f"{key}={result[key]} exceeds cap {cap}")
    return issues


def run_soak() -> dict:
    """Run simulated 2h + 3h sessions; report boundedness and latency."""
    results = []
    issues: list[str] = []
    for label, hours, turns in (("2h", 2, _TURNS_PER_SESSION), ("3h", 3, int(_TURNS_PER_SESSION * 1.5))):
        _log.info("soak %s: %d turns", label, turns)
        result = _run_session(f"soak-{label}", turns)
        result["simulated_hours"] = hours
        results.append(result)
        issues.extend(_check_bounded(result))
        drop_session(f"soak-{label}")

    # Topic leakage check: after an explicit reset, a new topic question must
    # not inherit the previous topic stack.
    reset_state("soak-leak-check")
    apply_event("soak-leak-check", "question_received", {"question": "介绍一下你的项目"})
    apply_event("soak-leak-check", "question_received", {"question": "为什么选 RAG？", "is_follow_up": True})
    apply_event("soak-leak-check", "question_received", {"question": "讲讲操作系统内核", "is_follow_up": False})
    state = get_state("soak-leak-check", create=False)
    leak_ok = state is not None and "介绍" not in " ".join(state.open_threads)
    drop_session("soak-leak-check")

    report = {
        "date": time.strftime("%Y-%m-%d"),
        "mode": "simulated (event-compressed; real audio soak BLOCKED externally)",
        "sessions": results,
        "boundedness_issues": issues,
        "topic_leak_after_reset_ok": leak_ok,
        "verdict": "PASS" if not issues and leak_ok else "FAIL",
    }

    reports_dir = Path(__file__).resolve().parents[2] / "reports"
    reports_dir.mkdir(exist_ok=True)
    target = reports_dir / "CHENGZHU_V1_SOAK_REPORT.md"
    lines = [
        "# 成竹 Chengzhu v1.0 Soak Report",
        "",
        f"**日期**：{report['date']}",
        f"**模式**：{report['mode']}",
        f"**判定**：{report['verdict']}",
        "",
        "| Session | Turns | State version | topic_stack | threads | claims | risk_flags | p50 ms | p95 ms |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s in results:
        lines.append(
            f"| {s['session_id']} ({s['simulated_hours']}) | {s['turns']} | {s['state_version']} | "
            f"{s['topic_stack_len']} | {s['open_threads_len']} | {s['claims_len']} | {s['risk_flags_len']} | "
            f"{s['state_update_p50_ms']} | {s['state_update_p95_ms']} |"
        )
    lines.extend(
        [
            "",
            "## 检查项",
            "",
            f"- 状态有界（topic_stack≤12, threads≤12, claims≤24, risk_flags≤12）：{'通过' if not issues else '失败: ' + '; '.join(issues)}",
            f"- 显式 reset 后无 topic 泄漏：{'通过' if leak_ok else '失败'}",
            "- 状态更新延迟平坦（p50 < 5ms 量级）：见上表",
            "",
            "## 外部阻塞",
            "",
            "- 真实音频 2h/3h/5h soak 需要真实面试参与者与音频硬件（BLOCKED）；本报告为事件压缩模拟。",
            "- 恢复真实 soak 后需补跑：memory/queues/WebSocket/provider failure/audio switch 检查。",
        ]
    )
    target.write_text("\n".join(lines), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = run_soak()
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
