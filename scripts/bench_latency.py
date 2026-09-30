"""Controlled latency benchmark + forensics (v1.2-R2 latency closure, Stages A/B/F/G/H).

    python scripts/bench_latency.py [--repeats 2] [--modes baseline,r2_prev,local,streaming_sim]

Corpus: backend/evals/latency_corpus (scripts/latency_corpus.py).

Sample-accurate simulated timeline (20 ms frames). Every component on it is
the real product code with product defaults (``AppConfig()``):

  real VADBuffer (+ adaptive end-of-turn probe in the final modes)
  real LiveTurnTracker / EndOfTurnDetector
  real product Whisper engine (``STTEngine``: beam 3, VAD filter, initial
      prompt, hotwords, sticky language) for the authoritative batch final,
      charged at its measured wall time
  real ``transcribe_fast`` streaming-preview decodes (local profile), charged
      at wall time, sharing one CPU decoder with the batch final (the product
      serializes both on ``_whisper_infer_lock``)
  real AssistAsrStateMachine (merge gap, EOT fast flush, group confirm,
      provisional cue + reconcile)
  real Fast Cue L0 (``emit_early_cue``), charged at wall time

Modes
  baseline       v1.x path: no early cue, no EOT merge flush, fixed 1.2 s VAD,
                 streaming preview finish() blocks the capture thread at flush
  r2_prev        f04f217 defaults (early cue at group confirm, EOT merge flush),
                 old frontend: the cue renders only when answer_start creates
                 the card (after the 1.2 s late-constraint grace)
  local          final code, Local CPU Profile (local Whisper streaming preview)
  streaming_sim  final code, Streaming Provider Profile, SIMULATED: partials
                 are real Whisper text of the audio so far, delivered with a
                 modeled provider lag (250 ms) and a modeled endpoint event
                 (Doubao end_window 320 ms + lag); the provider's final is
                 modeled at 600 ms. Not a measurement of any real provider.

All times are on one monotonic simulated clock; E is the ground-truth speech
end of the clean speech. TTFUG_user = first *useful* cue (question contains
the expected keywords, or the confirmed question) - E, at render time.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import wave
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

CORPUS = BACKEND / "evals" / "latency_corpus"
SR = 16000
FRAME = 320
TAIL_SEC = 14.0  # long enough that a slow decode on a busy CPU still lands
PREMATURE_TOLERANCE = 0.15  # a cut-off word is longer than the ground-truth threshold jitter

# Modeled constants (documented in the report; not measured here)
GRACE_WORKER_OVERHEAD = 0.15   # answer worker pre-LLM work before answer_start (packaged TTFUG_internal ~156 ms)
FAKE_TTFA = 0.53               # fake provider first token after dispatch (packaged smoke)
PROVIDER_LAG = 0.25            # streaming provider partial lag (modeled)
PROVIDER_END_WINDOW = 0.32     # Doubao end_window_size configured in doubao_stream.py
PROVIDER_FINAL = 0.60          # provider non-stream final after segment flush (modeled)
SIM_PARTIAL_STEP = 0.40        # streaming_sim partial update step (audio seconds)


def _load(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


def _norm(text: str) -> str:
    return "".join(ch for ch in (text or "").lower() if not ch.isspace())


def _contains(text: str, keywords: list[str]) -> bool:
    body = _norm(text)
    # "a|b" = equivalent forms (e.g. 一百倍|100倍); ASR misrecognitions stay misses
    return bool(keywords) and all(any(_norm(alt) in body for alt in k.split("|")) for k in keywords)


class _Log:
    def info(self, *a, **k): ...
    def warning(self, *a, **k): ...
    def debug(self, *a, **k): ...


def _mode_cfg(cfg_base, mode: str):
    final = mode in ("local", "streaming_sim")
    return cfg_base.model_copy(update={
        "assist_eot_fast_flush": mode != "baseline",
        "intelligence_early_cue": mode != "baseline",
        "assist_adaptive_eot": final,
        "assist_provisional_cue": final,
    })


def _pipeline_vad_value(name: str) -> float:
    from api.assist import pipeline

    return float(getattr(pipeline, name))


def run_case(case: dict, mode: str, batch_engine, cfg_base, sim_cache: dict) -> dict:
    from api.assist.answer_worker import emit_early_cue
    from api.assist.asr_state import AssistAsrStateMachine
    from services.audio import VADBuffer
    from services.intelligence.end_of_turn import EndOfTurnConfig
    from services.intelligence.live_turn import LiveTurnTracker
    from services.stt import postprocess_interview_transcription, transcription_for_publish
    from services.stt.factory import get_stt_engine

    cfg = _mode_cfg(cfg_base, mode)
    final_code = mode in ("local", "streaming_sim")
    remote = mode == "streaming_sim"
    audio = np.concatenate([_load(CORPUS / case["audio"]), np.zeros(int(SR * TAIL_SEC), dtype=np.float32)])
    gt_end = case.get("speech_end_ground_truth")
    expect = case.get("question_expected") or []

    clock = {"t": 0.0}
    ev: dict = {}          # forensic time points (first occurrence)
    cues: list[dict] = []  # every cue emit
    tasks: list[tuple[float, str, dict]] = []
    flushes: list[dict] = []
    decodes: list[dict] = []

    def mark(name, value=None):
        ev.setdefault(name, round(clock["t"] if value is None else value, 3))

    def early_cue(question, qa_id, meta):
        mark("guidance_fast_created")
        t0 = time.perf_counter()
        emit_early_cue(question, qa_id, meta, broadcast=lambda _p: None)
        wall = time.perf_counter() - t0
        cues.append({"t": clock["t"] + wall, "qa_id": qa_id, "question": question,
                     "provisional": bool(meta.get("provisional")), "reconciled": meta.get("reconciled", ""),
                     "compute_ms": round(wall * 1000, 2)})

    prev_q = case.get("previous_question") or ""
    session = SimpleNamespace(
        capture_is_loopback=False,
        add_transcription=lambda _t: None,
        get_last_qa=lambda: SimpleNamespace(question=prev_q) if prev_q else None,
    )
    sm = AssistAsrStateMachine(
        broadcast=lambda d: d.get("type") == "question_parse_status" and d.get("stage") == "assembling" and mark("question_candidate"),
        submit_answer_task=lambda task: tasks.append((clock["t"], task[0], task[4])) or True,
        begin_asr_turn=lambda: len(tasks) + 1,
        record_asr_turn=lambda _t: None,
        is_high_churn_submission=lambda _c, _t: False,
        logger=_Log(),
        clock=lambda: clock["t"],
        early_cue=early_cue if mode != "baseline" else None,
    )
    tracker = LiveTurnTracker(
        sample_rate=SR,
        config=EndOfTurnConfig(min_silence_sec=cfg.assist_eot_min_silence_sec, hard_timeout_sec=cfg.silence_duration),
        remote_lag_sec=PROVIDER_LAG + 0.05,
        clock=lambda: clock["t"],
    )
    tracker.previous_question = prev_q
    vad = VADBuffer(
        sample_rate=SR,
        silence_threshold=cfg.silence_threshold,
        silence_duration=cfg.silence_duration,
        max_speech_duration=cfg.assist_vad_max_speech_sec,
        min_speech_duration=cfg.assist_vad_min_speech_sec,
        # same preroll / rollover as the product's interviewer VAD: Whisper
        # needs the audio just before the first voiced frame
        preroll_duration=_pipeline_vad_value("_interviewer_vad_preroll_sec"),
        rollover_duration=_pipeline_vad_value("_interviewer_vad_rollover_sec"),
    )
    if final_code:
        vad.end_of_turn_probe = lambda silence: tracker.probe(silence, vad.voiced_end_samples)
        vad.end_of_turn_min_silence = tracker.detector.config.min_silence_sec
        vad.on_speech_resumed = tracker.detector.note_resumed_after

    # --- shared CPU decoder (product: _whisper_infer_lock) --------------------
    cpu = {"busy_until": 0.0}
    stream = {"gen": 0, "next_at": 0.0, "inflight": None}
    batch_queue: deque = deque()
    batch_results: list[tuple[float, str]] = []
    # speculative final (local profile, final code): ASR worker job in the tail
    speculative_on = mode == "local"
    worker = {"free_at": 0.0}
    spec = {"key": None, "results": {}, "events": []}   # events: (ready, key, text, covered)
    remote_partials: list[tuple[float, str, int]] = []   # (deliver_t, text, gen)
    endpoint_at = {"t": None, "gen": -1}
    last_voice = {"t": 0.0}
    stream_lang_engine = None

    def stream_engine():
        nonlocal stream_lang_engine
        if stream_lang_engine is None:
            lang = getattr(batch_engine, "sticky_language", None) or "zh"
            stream_lang_engine = get_stt_engine(provider="whisper", model_size="base", language=lang)
            if not stream_lang_engine.is_loaded:
                stream_lang_engine.load_model()
        return stream_lang_engine

    def sim_partial(start_sample: int, end_sample: int) -> str:
        key = (case["id"], start_sample, end_sample)
        if key not in sim_cache:
            lang = "en" if case.get("lang") == "en" else "zh"
            eng = get_stt_engine(provider="whisper", model_size="base", language=lang)
            sim_cache[key] = eng.transcribe_fast(audio[start_sample:end_sample])
        return sim_cache[key]

    seg_start_sample = {"v": None}
    total = len(audio)
    stop_after = None
    i = 0
    while i < total:
        frame = audio[i:i + FRAME]
        i += FRAME
        t = i / SR
        clock["t"] = t
        rms = float(np.sqrt(np.mean(frame ** 2))) if len(frame) else 0.0
        voiced = rms > cfg.silence_threshold
        if voiced:
            mark("speech_start")
            last_voice["t"] = t
            tracker.note_voice(t)

        # deliver local streaming decodes
        inflight = stream["inflight"]
        if inflight and inflight[0] <= t:
            stream["inflight"] = None
            done_t, text, covered, gen = inflight
            if gen == stream["gen"] and text:
                tracker.on_local_decode(text, covered, now=done_t)
                sm.note_speech_activity(done_t)
                mark("partial_first", done_t)
        # deliver simulated provider partials / endpoint
        while remote_partials and remote_partials[0][0] <= t:
            dt, text, gen = remote_partials.pop(0)
            if gen == stream["gen"] and text:
                tracker.on_remote_partial(text, now=dt)
                sm.note_speech_activity(dt)
                mark("partial_first", dt)
        if remote and endpoint_at["t"] is not None and endpoint_at["t"] <= t and endpoint_at["gen"] == stream["gen"]:
            tracker.on_remote_endpoint()
            endpoint_at["t"] = None
        # deliver speculative finals to the tracker
        while spec["events"] and spec["events"][0][0] <= t:
            rt, key, text, covered = spec["events"].pop(0)
            spec["results"][key] = (rt, text)
            if text:
                tracker.on_speculative_final(key, text, covered, now=rt)
                mark("partial_first", rt)
        # deliver authoritative finals
        while batch_results and batch_results[0][0] <= t:
            rt, pub = batch_results.pop(0)
            mark("asr_final", rt)
            if pub:
                sm.append_transcription_fragment(cfg, session, pub, rt, False)

        seg = vad.feed(frame)
        if seg is None:
            if vad.has_pending_audio:
                if seg_start_sample["v"] is None:
                    seg_start_sample["v"] = i - vad._speech_audio_samples
                fed = vad._speech_audio_samples
                if remote:
                    # provider partial for the audio so far, every SIM_PARTIAL_STEP
                    step = int(SIM_PARTIAL_STEP * SR)
                    if fed >= int(0.6 * SR) and fed % step < FRAME:
                        text = sim_partial(seg_start_sample["v"], seg_start_sample["v"] + fed)
                        remote_partials.append((t + PROVIDER_LAG, text, stream["gen"]))
                    if not voiced and vad.trailing_silence_sec > 0 and endpoint_at["gen"] != stream["gen"]:
                        endpoint_at.update(t=last_voice["t"] + PROVIDER_END_WINDOW + PROVIDER_LAG, gen=stream["gen"])
                    if voiced and endpoint_at["gen"] == stream["gen"]:
                        endpoint_at.update(t=None, gen=-1)
                in_tail = speculative_on and vad.trailing_silence_sec >= cfg.assist_speculative_min_silence_sec
                if (
                    not remote
                    and in_tail
                    and spec["key"] != vad.voiced_end_samples
                    and tracker.should_speculate()
                    and worker["free_at"] <= t
                    and not batch_queue
                ):
                    key = vad.voiced_end_samples
                    spec["key"] = key
                    tracker.expect_speculative(key)
                    spec_audio = vad.pending_audio()
                    start = max(t, cpu["busy_until"])
                    t0 = time.perf_counter()
                    raw = batch_engine.transcribe(spec_audio)
                    ready = start + (time.perf_counter() - t0)
                    decodes.append({"kind": "speculative", "start": round(start, 3), "wall_ms": round((ready - start) * 1000),
                                    "audio_s": round(len(spec_audio) / SR, 2), "text": raw})
                    cpu["busy_until"] = ready
                    worker["free_at"] = ready
                    spec["events"].append((ready, key, raw, len(spec_audio)))
                    spec["events"].sort(key=lambda e: e[0])
                if remote:
                    pass
                elif (
                    not in_tail
                    and stream["inflight"] is None
                    and t >= stream["next_at"]
                    and fed >= int(0.6 * SR)
                    and fed != stream.get("last_fed")
                ):
                    if t >= cpu["busy_until"]:
                        stream["last_fed"] = fed
                        window = vad.pending_audio()[-int(8.0 * SR):]
                        t0 = time.perf_counter()
                        text = stream_engine().transcribe_fast(window)
                        wall = time.perf_counter() - t0
                        stream["inflight"] = (t + wall, (text or "").strip(), fed, stream["gen"])
                        decodes.append({"kind": "stream", "start": round(t, 3), "wall_ms": round(wall * 1000), "covered_s": round(fed / SR, 2), "text": text})
                        cpu["busy_until"] = t + wall
                        stream["next_at"] = t + wall + max(cfg.whisper_stream_interval_ms / 1000.0, 1.5 * wall if final_code else 0.0)
                    else:
                        stream["next_at"] = t + cfg.whisper_stream_interval_ms / 1000.0
        else:
            reason = vad.last_flush_reason or "silence"
            trailing = float(getattr(vad, "last_flush_trailing_sec", 0.0) or 0.0) if reason in ("eot", "silence") else 0.0
            provisional = tracker.provisional_question(now=t) if final_code and reason in ("eot", "silence") else ""
            enqueue_t = t
            if not remote:
                if not final_code:
                    # old code: finish() joins the preview thread and decodes once
                    # more on the capture thread before the segment is queued
                    join_t = max(t, stream["inflight"][0]) if stream["inflight"] else t
                    t0 = time.perf_counter()
                    if len(seg) >= int(0.6 * SR):
                        stream_engine().transcribe_fast(seg[-int(8.0 * SR):])
                    wall = time.perf_counter() - t0
                    enqueue_t = join_t + wall
                    cpu["busy_until"] = max(cpu["busy_until"], enqueue_t)
                    stream["inflight"] = None
            flush_spec_key = spec["key"] if spec["key"] is not None and spec["key"] == tracker.voiced_end_samples else None
            spec["key"] = None
            stream["gen"] += 1
            stream["next_at"] = 0.0
            stream["last_fed"] = None
            flushes.append({"t": round(t, 3), "reason": reason, "trailing": round(trailing, 3),
                            "e_est": round(t - trailing, 3), "provisional": provisional,
                            "tracker_reason": tracker.trace.confirm_reason})
            mark("vad_end")
            mark("speech_end_estimate", t - trailing)
            if tracker.trace.partial_stable is not None:
                mark("partial_stable", tracker.trace.partial_stable)
            batch_queue.append((enqueue_t, seg, flush_spec_key))
            if provisional:
                sm.submit_provisional(cfg, session, provisional, "conversation_mic", t)
            tracker.reset(previous_question=prev_q)
            seg_start_sample["v"] = None

        # batch worker (sequential; blocks on the shared decoder)
        while batch_queue:
            enq_t, seg_audio, seg_key = batch_queue.popleft()
            if remote:
                start = enq_t
                raw = batch_engine_remote_text(case, seg_audio, sim_cache)
                ready = start + PROVIDER_FINAL
            else:
                start = max(enq_t, worker["free_at"])
                pending_spec = [e for e in spec["events"] if e[1] == seg_key]
                if seg_key is not None and (seg_key in spec["results"] or pending_spec):
                    # the worker already decoded this audio speculatively
                    spec_ready, raw = spec["results"].pop(seg_key) if seg_key in spec["results"] else (pending_spec[0][0], pending_spec[0][2])
                    ready = max(start, spec_ready)
                    decodes.append({"kind": "batch_reused", "start": round(start, 3), "wall_ms": 0, "text": raw})
                else:
                    start = max(start, cpu["busy_until"])
                    t0 = time.perf_counter()
                    raw = batch_engine.transcribe(seg_audio)
                    ready = start + (time.perf_counter() - t0)
                    decodes.append({"kind": "batch", "start": round(start, 3), "wall_ms": round((ready - start) * 1000), "audio_s": round(len(seg_audio) / SR, 2), "text": raw})
                    cpu["busy_until"] = ready
                worker["free_at"] = ready
            pub = transcription_for_publish(postprocess_interview_transcription(raw), cfg.transcription_min_sig_chars) or ""
            batch_results.append((ready, pub))
            batch_results.sort()

        sm.try_flush_merge_buffer(cfg, session, t)
        sm.try_flush_question_group(cfg, session, t)
        if tasks and stop_after is None:
            stop_after = t + 3.0
        if stop_after is not None and t >= stop_after and not batch_results and not batch_queue:
            break

    # ---------------------------------------------------------------- results
    row = {"case": case["id"], "mode": mode, "type": case["content_type"], "lang": case.get("lang"),
           "condition": case.get("condition"), "gt_end": gt_end, "events": ev, "flushes": flushes,
           "provisional_stats": dict(sm.provisional_stats), "cue_emits": cues, "decodes": decodes}
    if gt_end is None:
        row["false_trigger"] = bool(tasks or cues)
        return row
    if not tasks:
        row["error"] = "no question submitted"
        return row
    q1, question, meta = tasks[0]
    qa_id = meta["qa_id"]
    ev["question_confirmed"] = round(q1, 3)
    card_cues = [c for c in cues if c["qa_id"] == qa_id]
    useful = [c for c in card_cues if _contains(c["question"], expect)]
    if not useful:
        useful = [c for c in card_cues if c["t"] >= q1 - 1e-6] or card_cues
    grace = float(getattr(cfg, "assist_asr_late_constraint_grace_sec", 1.2) or 1.2)
    answer_start = q1 + grace + GRACE_WORKER_OVERHEAD
    deep_first = answer_start + FAKE_TTFA
    if useful:
        g0 = useful[0]["t"]
        ev["guidance_fast_broadcast"] = round(g0, 3)
        rendered = g0 if final_code else max(g0, answer_start)
    else:
        g0 = None
        rendered = answer_start + 0.003  # baseline: cue computed by the answer worker
    ev["guidance_fast_rendered"] = round(rendered, 3)
    ev["deep_first_token"] = round(deep_first, 3)
    ev["deep_done"] = round(deep_first + 0.14, 3)
    first_cue_t = card_cues[0]["t"] if card_cues else None
    eot_flushes = [f for f in flushes if f["reason"] == "eot"]
    row.update({
        "question": question,
        "question_ok": _contains(question, expect),
        "provisional_relation": meta.get("provisional_relation", ""),
        "submissions": len(tasks),
        "qbd_ms": round((q1 - gt_end) * 1000),
        "ttfug_user_ms": round((rendered - gt_end) * 1000),
        "ttfug_user_emit_ms": round((g0 - gt_end) * 1000) if g0 is not None else None,
        "ttfug_internal_ms": round((rendered - q1) * 1000),
        "ttfa_ms": round((deep_first - q1) * 1000),
        "ttd_ms": round((deep_first + 0.14 - q1) * 1000),
        "cue_before_deep": rendered < deep_first,
        "e_estimate_error_ms": round((flushes[-1]["e_est"] - gt_end) * 1000) if flushes else None,
        "premature_end": any(f["t"] - f["trailing"] < gt_end - PREMATURE_TOLERANCE for f in eot_flushes),
        "premature_cue": first_cue_t is not None and first_cue_t < gt_end - PREMATURE_TOLERANCE,
        "cue_renders": len(card_cues),
        "question_replaced": meta.get("provisional_relation") == "replaced" or sm.provisional_stats["retracted"] > 0,
        "cue_compute_ms": card_cues[0]["compute_ms"] if card_cues else None,
    })
    return row


def batch_engine_remote_text(case: dict, seg_audio: np.ndarray, sim_cache: dict) -> str:
    """Streaming profile final: the provider's final text (modeled with the
    same Whisper text a provider-quality recognizer would return)."""
    from services.stt.factory import get_stt_engine

    key = (case["id"], "final", len(seg_audio), float(np.sum(np.abs(seg_audio[:3200]))))
    if key not in sim_cache:
        lang = "en" if case.get("lang") == "en" else "zh"
        sim_cache[key] = get_stt_engine(provider="whisper", model_size="base", language=lang).transcribe(seg_audio)
    return sim_cache[key]


def pct(values, p):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    k = max(0, min(len(vals) - 1, round(p / 100 * (len(vals) - 1))))
    return vals[k]


def summarize(rows: list[dict], mode: str) -> dict:
    ok = [r for r in rows if r["mode"] == mode and "ttfug_user_ms" in r]
    speech = [r for r in rows if r["mode"] == mode and r.get("gt_end") is not None]
    silence = [r for r in rows if r["mode"] == mode and r.get("gt_end") is None]
    prov = [r for r in ok if r["provisional_stats"]["emitted"]]
    out = {
        "n": len(ok),
        "errors": [r["case"] for r in speech if "error" in r],
        "false_trigger_on_silence": sum(r.get("false_trigger", False) for r in silence),
        "question_ok_rate": round(sum(r["question_ok"] for r in ok) / max(1, len(ok)), 3),
        "premature_end_rate": round(sum(r["premature_end"] for r in ok) / max(1, len(ok)), 3),
        "premature_cue_rate": round(sum(r["premature_cue"] for r in ok) / max(1, len(ok)), 3),
        "question_replacement_rate": round(sum(r["question_replaced"] for r in ok) / max(1, len(ok)), 3),
        "provisional_emitted": len(prov),
        "provisional_relations": {k: sum(1 for r in ok if r["provisional_relation"] == k) for k in ("same", "corrected", "replaced")},
        "multi_render_cards": sum(1 for r in ok if r["cue_renders"] > 1),
        "cue_before_deep_rate": round(sum(r["cue_before_deep"] for r in ok) / max(1, len(ok)), 3),
    }
    for key in ("qbd_ms", "ttfug_user_ms", "ttfug_user_emit_ms", "ttfug_internal_ms", "ttfa_ms", "ttd_ms", "cue_compute_ms"):
        vals = [r.get(key) for r in ok]
        out[key] = {"p50": pct(vals, 50), "p95": pct(vals, 95), "max": pct(vals, 100)}
    return out


def stage_breakdown(rows: list[dict], mode: str) -> dict:
    """Median forensic intervals relative to the ground-truth speech end."""
    ok = [r for r in rows if r["mode"] == mode and "ttfug_user_ms" in r]
    names = ["partial_first", "partial_stable", "speech_end_estimate", "vad_end", "asr_final", "question_candidate",
             "question_confirmed", "guidance_fast_created", "guidance_fast_broadcast", "guidance_fast_rendered",
             "deep_first_token", "deep_done"]
    out = {}
    for name in names:
        vals = [round((r["events"][name] - r["gt_end"]) * 1000) for r in ok if name in r["events"]]
        out[name] = {"n": len(vals), "p50_ms_after_E": pct(vals, 50), "p95_ms_after_E": pct(vals, 95)}
    return out


def _calibrate(engine) -> dict:
    """A fixed decode (zh-short, product engine) + system CPU load, so the
    numbers can be read against how busy the machine was."""
    try:
        import psutil

        load = psutil.cpu_percent(interval=1.0)
    except Exception:  # noqa: BLE001
        load = None
    clip = _load(CORPUS / "zh-short.wav")
    t0 = time.perf_counter()
    engine.transcribe(clip)
    return {"system_cpu_percent": load, "calibration_decode_ms": round((time.perf_counter() - t0) * 1000)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--modes", default="baseline,r2_prev,local,streaming_sim")
    ap.add_argument("--cases", default="")
    ap.add_argument("--out", default=str(ROOT / "reports" / "perf" / "latency_bench.json"))
    args = ap.parse_args()

    from core.config import AppConfig
    from services.stt.engines import STTEngine

    STTEngine._best_device = staticmethod(lambda: ("cpu", "int8"))  # CPU-only profile on every machine
    from services.stt.factory import get_stt_engine

    # Load + warm every engine outside the timed regions (model load is not latency).
    warm = np.zeros(SR, dtype=np.float32)
    for lang in ("zh", "en"):
        eng = get_stt_engine(provider="whisper", model_size="base", language=lang)
        eng.load_model()
        eng.transcribe_fast(warm)
    cfg_base = AppConfig()  # product defaults
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    if args.cases:
        wanted = set(args.cases.split(","))
        manifest = [c for c in manifest if c["id"] in wanted]
    modes = [m for m in args.modes.split(",") if m]
    rows: list[dict] = []
    sim_cache: dict = {}
    load_log: dict = {}
    for mode in modes:
        # the final local profile gets the repeats (variance); others run once
        repeats = args.repeats if mode == "local" else 1
        for rep in range(repeats):
            # one engine per session run: sticky language evolves like a real session
            batch_engine = STTEngine("base", cfg_base.whisper_language)
            batch_engine.load_model()
            batch_engine.transcribe(warm)
            load_log.setdefault(mode, []).append({"repeat": rep, "before": _calibrate(batch_engine)})
            for case in manifest:
                row = run_case(case, mode, batch_engine, cfg_base, sim_cache)
                row["repeat"] = rep
                rows.append(row)
                print(f"{mode:14s} {case['id']:20s} ttfug={row.get('ttfug_user_ms')} qbd={row.get('qbd_ms')} "
                      f"ok={row.get('question_ok')} rel={row.get('provisional_relation', '')} q={row.get('question', '')[:40]!r}",
                      flush=True)
            load_log[mode][-1]["after"] = _calibrate(batch_engine)
    summary = {m: summarize(rows, m) for m in modes}
    stages = {m: stage_breakdown(rows, m) for m in modes}
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "machine": {"cpu_threads": __import__("os").cpu_count(), "stt": "faster-whisper base int8 CPU (product STTEngine)"},
        "defaults": {k: getattr(cfg_base, k, None) for k in (
            "silence_duration", "assist_eot_min_silence_sec", "assist_speculative_min_silence_sec", "assist_transcription_merge_gap_sec",
            "assist_eot_merge_gap_sec", "assist_asr_confirm_window_sec", "assist_asr_late_constraint_grace_sec",
            "whisper_language", "whisper_stream_interval_ms", "assist_auto_answer_mode")},
        "modeled_constants": {"answer_start_after_grace_s": GRACE_WORKER_OVERHEAD, "fake_ttfa_s": FAKE_TTFA,
                              "provider_lag_s": PROVIDER_LAG, "provider_end_window_s": PROVIDER_END_WINDOW,
                              "provider_final_s": PROVIDER_FINAL, "sim_partial_step_s": SIM_PARTIAL_STEP},
        "load": load_log,
        "summary": summary,
        "stages": stages,
        "rows": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
