"""Controlled prerecorded TTFUG benchmark (R2 Stage I / AE).

Timeline is sample-accurate and simulated; every component on it is real:

  audio (Windows SAPI, offline) -> real VADBuffer (product defaults)
    -> real faster-whisper STT (wall time measured, local 'base' model)
    -> real AssistAsrStateMachine (merge gap, group confirm, grace)
    -> real Fast Cue compute (early cue or answer-worker path, wall time)

  E  = last voiced 20 ms frame of the recording (speech end)
  Q1 = question group confirmed (task submitted)
  G0 = Fast Cue visible (server emit; UI render measured separately in e2e)

  QBD = Q1 - E,  TTFUG_user = G0 - E

Modes:
  baseline  assist_eot_fast_flush=False, intelligence_early_cue=False
  r2        both True (product defaults)
Nothing about the metric definitions changes between modes.

Usage:
  python scripts/bench_ttfug.py [--repeats 3] [--stt base] [--out reports/perf]
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

AUDIO_DIR = ROOT / "build" / "bench-audio"
SR = 16000
FRAME = 320  # 20 ms

CASES = [
    {"id": "zh-normal", "voice": "Microsoft Huihui Desktop", "rate": 0, "ssml": "Redis 的持久化机制有哪些？", "expect": "持久化"},
    {"id": "zh-request", "voice": "Microsoft Huihui Desktop", "rate": 0, "ssml": "讲讲你做过的订单系统重构。", "expect": "订单"},
    {"id": "zh-internal-pause", "voice": "Microsoft Huihui Desktop", "rate": 0, "ssml": "如果流量扩大十倍<break time=\"700ms\"/>你的系统哪里会先扛不住？", "expect": "扛不住"},
    {"id": "zh-long-pause", "voice": "Microsoft Huihui Desktop", "rate": 0, "ssml": "我们先聊聊缓存<break time=\"1400ms\"/>为什么选择 Redis 而不是 Memcached？", "expect": "Memcached"},
    {"id": "zh-slow", "voice": "Microsoft Huihui Desktop", "rate": -4, "ssml": "消息队列怎么保证不丢消息？", "expect": "消息"},
    {"id": "zh-fast", "voice": "Microsoft Huihui Desktop", "rate": 5, "ssml": "数据库索引为什么用 B 加树？", "expect": "索引"},
    {"id": "en-normal", "voice": "Microsoft Zira Desktop", "rate": 0, "ssml": "How would you design a rate limiter for a public API?", "expect": "rate limit"},
    {"id": "en-slow", "voice": "Microsoft David Desktop", "rate": -3, "ssml": "Tell me about a time you disagreed with your team.", "expect": "disagree"},
    {"id": "mixed", "voice": "Microsoft Huihui Desktop", "rate": 0, "ssml": "你在项目里用 Kafka 做过 exactly once 吗？", "expect": "Kafka"},
]


def synthesize() -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        out = AUDIO_DIR / f"{case['id']}.wav"
        if out.exists():
            continue
        lang = "zh-CN" if "Huihui" in case["voice"] else "en-US"
        ssml = (
            f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{lang}'>"
            f"<voice name='{case['voice']}'>{case['ssml']}</voice></speak>"
        )
        ssml_file = AUDIO_DIR / f"{case['id']}.ssml"
        ssml_file.write_text(ssml, encoding="utf-8")
        ps = (
            "Add-Type -AssemblyName System.Speech;"
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            f"$s.Rate={int(case['rate'])};"
            "$f=New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000,[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,[System.Speech.AudioFormat.AudioChannel]::Mono);"
            f"$s.SetOutputToWaveFile('{out}',$f);"
            f"$s.SpeakSsml([IO.File]::ReadAllText('{ssml_file}',[Text.Encoding]::UTF8));$s.Dispose()"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)


def load(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    return data


def speech_end_sec(audio: np.ndarray, threshold: float) -> float:
    last = 0
    for i in range(0, len(audio) - FRAME, FRAME):
        if float(np.sqrt(np.mean(audio[i:i + FRAME] ** 2))) > threshold:
            last = i + FRAME
    return last / SR


def run_case(case: dict, mode: str, stt, cfg_base) -> dict:
    from api.assist.asr_state import AssistAsrStateMachine
    from core.session import Session
    from services.audio import VADBuffer

    cfg = cfg_base.model_copy(update={
        "assist_eot_fast_flush": mode == "r2",
        "intelligence_early_cue": mode == "r2",
        "assist_auto_answer_mode": "always",
    })
    audio = np.concatenate([load(AUDIO_DIR / f"{case['id']}.wav"), np.zeros(int(SR * 4.0), dtype=np.float32)])
    e_sec = speech_end_sec(audio, cfg.silence_threshold)

    clock = {"t": 0.0}
    submitted: list[tuple[float, str, dict]] = []
    early: list[tuple[float, str]] = []
    cue_ms: list[float] = []

    def early_cue(question, qa_id, meta):
        from api.assist.answer_worker import emit_early_cue

        t0 = time.perf_counter()
        emit_early_cue(question, qa_id, meta, broadcast=lambda _p: None)
        ms = (time.perf_counter() - t0) * 1000
        cue_ms.append(ms)
        early.append((clock["t"] + ms / 1000, question))

    sm = AssistAsrStateMachine(
        broadcast=lambda _d: None,
        submit_answer_task=lambda task: submitted.append((clock["t"], task[0], task[4])) or True,
        begin_asr_turn=lambda: len(submitted) + 1,
        record_asr_turn=lambda _t: None,
        is_high_churn_submission=lambda _c, _t: False,
        logger=type("L", (), {"info": lambda *a, **k: None, "warning": lambda *a, **k: None, "debug": lambda *a, **k: None})(),
        clock=lambda: clock["t"],
        early_cue=early_cue if mode == "r2" else None,
    )
    session = Session(session_id="bench")
    vad = VADBuffer(
        sample_rate=SR,
        silence_threshold=cfg.silence_threshold,
        silence_duration=cfg.silence_duration,
        max_speech_duration=getattr(cfg, "assist_vad_max_speech_sec", 18.0),
        min_speech_duration=getattr(cfg, "assist_vad_min_speech_sec", 0.3),
    )
    stt_ms_total = 0.0
    flush_at = None
    pending: list[tuple[float, str]] = []
    for i in range(0, len(audio), FRAME):
        clock["t"] = (i + FRAME) / SR
        seg = vad.feed(audio[i:i + FRAME])
        if seg is not None:
            t0 = time.perf_counter()
            segments, _info = stt.transcribe(seg, language=None, beam_size=1, vad_filter=False)
            raw = "".join(s.text for s in segments).strip()
            ms = (time.perf_counter() - t0) * 1000
            # Same post-processing as the real interviewer ASR worker.
            from services.stt import postprocess_interview_transcription, transcription_for_publish
            from services.stt.text_utils import _postprocess

            # engine wrapper (_postprocess: t2s + term fixes), then the worker's steps
            text = transcription_for_publish(
                postprocess_interview_transcription(_postprocess(raw, "interview")),
                getattr(cfg, "transcription_min_sig_chars", 2),
            ) or ""
            if flush_at is None:
                flush_at = clock["t"]
            stt_ms_total += ms
            if text:
                pending.append((clock["t"] + ms / 1000, text))
        while pending and pending[0][0] <= clock["t"]:
            _pt, text = pending.pop(0)
            sm.append_transcription_fragment(cfg, session, text, clock["t"], False)
        sm.try_flush_merge_buffer(cfg, session, clock["t"])
        sm.try_flush_question_group(cfg, session, clock["t"])
        if submitted:
            break
    # Drain: keep ticking the state machine until the question is submitted.
    t_end = clock["t"] + 8.0
    while not submitted and clock["t"] < t_end:
        clock["t"] += FRAME / SR
        while pending and pending[0][0] <= clock["t"]:
            _pt, text = pending.pop(0)
            sm.append_transcription_fragment(cfg, session, text, clock["t"], False)
        sm.try_flush_merge_buffer(cfg, session, clock["t"])
        sm.try_flush_question_group(cfg, session, clock["t"])
    if not submitted:
        return {"case": case["id"], "mode": mode, "error": "no question submitted"}

    q1, question, meta = submitted[0]
    if mode == "r2" and early:
        g0 = early[0][0]
    else:
        # Baseline: the answer worker starts after dispatch_after (grace) and
        # emits the cue after its own pre-LLM work (measured, same L0 code).
        from api.assist.answer_worker import emit_early_cue

        t0 = time.perf_counter()
        emit_early_cue(question, f"bench-{case['id']}", {}, broadcast=lambda _p: None)
        worker_ms = (time.perf_counter() - t0) * 1000
        cue_ms.append(worker_ms)
        dispatch_after = float(meta.get("dispatch_after_mono", q1) or q1)
        g0 = max(q1, dispatch_after) + worker_ms / 1000
    return {
        "case": case["id"],
        "mode": mode,
        "question": question,
        "question_ok": case["expect"].lower().replace(" ", "") in question.lower().replace(" ", ""),
        "speech_end_s": round(e_sec, 3),
        "vad_wait_ms": round((flush_at - e_sec) * 1000) if flush_at is not None and flush_at >= e_sec else None,
        "stt_ms": round(stt_ms_total),
        "cue_compute_ms": round(cue_ms[0]) if cue_ms else None,
        "qbd_ms": round((q1 - e_sec) * 1000),
        "ttfug_user_ms": round((g0 - e_sec) * 1000),
    }


def pct(values: list[float], p: float) -> float | None:
    vals = sorted(values)
    if not vals:
        return None
    k = max(0, min(len(vals) - 1, round(p / 100 * (len(vals) - 1))))
    return vals[k]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--stt", default="base")
    ap.add_argument("--out", default=str(ROOT / "reports" / "perf"))
    args = ap.parse_args()

    synthesize()
    from faster_whisper import WhisperModel

    from core.config import AppConfig

    stt = WhisperModel(args.stt, device="cpu", compute_type="int8", local_files_only=True)
    cfg_base = AppConfig()  # product defaults, not a developer's local config
    rows = []
    for mode in ("baseline", "r2"):
        for _ in range(args.repeats):
            for case in CASES:
                rows.append(run_case(case, mode, stt, cfg_base))
    summary = {}
    for mode in ("baseline", "r2"):
        ok = [r for r in rows if r["mode"] == mode and "error" not in r]
        summary[mode] = {
            "n": len(ok),
            "errors": [r for r in rows if r["mode"] == mode and "error" in r],
            "question_ok_rate": round(sum(r["question_ok"] for r in ok) / max(1, len(ok)), 3),
            "qbd_p50": pct([r["qbd_ms"] for r in ok], 50),
            "qbd_p95": pct([r["qbd_ms"] for r in ok], 95),
            "ttfug_user_p50": pct([r["ttfug_user_ms"] for r in ok], 50),
            "ttfug_user_p95": pct([r["ttfug_user_ms"] for r in ok], 95),
            "stt_ms_p50": pct([r["stt_ms"] for r in ok], 50),
            "cue_compute_ms_p50": pct([r["cue_compute_ms"] for r in ok if r["cue_compute_ms"] is not None], 50),
        }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stt_model": args.stt,
        "defaults": {k: getattr(cfg_base, k, None) for k in ("silence_duration", "assist_transcription_merge_gap_sec", "assist_asr_confirm_window_sec", "assist_asr_group_max_wait_sec")},
        "summary": summary,
        "rows": rows,
        "median_of_means": {m: statistics.mean([r["ttfug_user_ms"] for r in rows if r["mode"] == m and "error" not in r] or [0]) for m in ("baseline", "r2")},
    }
    (out / "ttfug_bench.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
