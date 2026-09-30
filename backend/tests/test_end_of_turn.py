"""Adaptive end of turn, provisional Fast Cue and reconcile (v1.2-R2 latency closure)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.assist.asr_state import AssistAsrStateMachine, reconcile_relation  # noqa: E402
from services.audio import VADBuffer  # noqa: E402
from services.intelligence import latency_clock  # noqa: E402
from services.intelligence.end_of_turn import (  # noqa: E402
    EndOfTurnConfig,
    EndOfTurnDetector,
    EotSignals,
    EotState,
)
from services.intelligence.live_turn import LiveTurnTracker  # noqa: E402

SR = 16000


def _eval(**kw):
    return EndOfTurnDetector().evaluate(EotSignals(**kw))


# -- detector -----------------------------------------------------------------


def test_fast_confirm_needs_complete_stable_covering_partial():
    d = _eval(silence_sec=0.6, partial_text="Redis 的持久化机制有哪些？", partial_covers_end=True, partial_stable_sec=0.3)
    assert d.state is EotState.CONFIRMED_END and d.reason == "fast_confirm"


def test_short_silence_always_continues():
    d = _eval(silence_sec=0.1, partial_text="Redis 的持久化机制有哪些？", partial_covers_end=True, partial_stable_sec=1.0)
    assert d.state is EotState.CONTINUE


def test_dangling_connectors_wait_for_more_speech():
    for text in ("如果数据扩大", "你说说这个方案的优点，但是", "我们先聊聊缓存然后", "How would you scale it and"):
        d = _eval(silence_sec=0.8, partial_text=text, partial_covers_end=True, partial_stable_sec=1.0)
        assert d.state is EotState.CONTINUE, text


def test_open_condition_without_question_continues():
    d = _eval(silence_sec=0.7, partial_text="如果流量扩大十倍", partial_covers_end=True, partial_stable_sec=1.0)
    assert d.state is EotState.CONTINUE


def test_partial_behind_speech_end_is_only_likely():
    d = _eval(silence_sec=0.6, partial_text="消息队列怎么保证不丢消息", partial_covers_end=False, partial_stable_sec=1.0)
    assert d.state is EotState.LIKELY_END


def test_unstable_partial_is_only_likely():
    d = _eval(silence_sec=0.6, partial_text="消息队列怎么保证不丢消息", partial_covers_end=True, partial_stable_sec=0.05)
    assert d.state is EotState.LIKELY_END


def test_provider_endpoint_confirms():
    d = _eval(silence_sec=0.6, partial_text="How would you design a rate limiter?", provider_endpoint=True)
    assert d.state is EotState.CONFIRMED_END and d.reason == "provider_endpoint"


def test_hard_timeout_is_kept():
    d = _eval(silence_sec=1.2, partial_text="如果")
    assert d.state is EotState.CONFIRMED_END and d.reason == "hard_timeout"


def test_short_follow_up_complete_only_with_previous_question():
    base = dict(silence_sec=0.6, partial_text="为什么？", partial_covers_end=True, partial_stable_sec=0.5)
    assert _eval(**base).state is EotState.CONTINUE
    assert _eval(**base, previous_question="你们为什么选 Kafka").state is EotState.CONFIRMED_END


def test_speaker_pause_pattern_raises_min_silence():
    det = EndOfTurnDetector(EndOfTurnConfig(min_silence_sec=0.3))
    det.note_resumed_after(0.6)
    det.note_resumed_after(0.7)
    assert det.min_silence_sec() > 0.7
    sig = EotSignals(silence_sec=0.6, partial_text="消息队列怎么保证不丢消息", partial_covers_end=True, partial_stable_sec=1.0)
    assert det.evaluate(sig).state is EotState.CONTINUE


# -- VAD probe ------------------------------------------------------------------


def _frames(seconds: float, amp: float):
    n = int(SR * seconds)
    sig = (np.sin(np.arange(n) * 0.05) * amp).astype(np.float32) if amp else np.zeros(n, dtype=np.float32)
    return [sig[i:i + 320] for i in range(0, n, 320)]


def test_vad_probe_ends_segment_early_and_records_trailing_silence():
    vad = VADBuffer(sample_rate=SR, silence_threshold=0.01, silence_duration=1.2, min_speech_duration=0.3,
                    end_of_turn_probe=lambda silence: silence >= 0.3, end_of_turn_min_silence=0.25)
    out, reason, t = None, None, 0.0
    for frame in _frames(1.0, 0.3) + _frames(1.5, 0.0):
        t += len(frame) / SR
        out = vad.feed(frame)
        if out is not None:
            reason = vad.last_flush_reason
            break
    assert out is not None and reason == "eot"
    assert abs(t - 1.3) < 0.03
    assert 0.29 <= vad.last_flush_trailing_sec <= 0.33


def test_vad_without_probe_uses_hard_silence():
    vad = VADBuffer(sample_rate=SR, silence_threshold=0.01, silence_duration=1.2, min_speech_duration=0.3,
                    end_of_turn_probe=lambda silence: False)
    reason, t = None, 0.0
    for frame in _frames(1.0, 0.3) + _frames(1.5, 0.0):
        t += len(frame) / SR
        if vad.feed(frame) is not None:
            reason = vad.last_flush_reason
            break
    assert reason == "silence" and abs(t - 2.2) < 0.03


def test_vad_reports_resumed_pause():
    pauses = []
    vad = VADBuffer(sample_rate=SR, silence_threshold=0.01, silence_duration=1.2, on_speech_resumed=pauses.append)
    for frame in _frames(0.6, 0.3) + _frames(0.5, 0.0) + _frames(0.4, 0.3):
        vad.feed(frame)
    assert pauses and abs(pauses[0] - 0.5) < 0.03


# -- tracker -------------------------------------------------------------------


def test_local_tracker_requires_decode_covering_speech_end():
    tr = LiveTurnTracker(clock=lambda: 10.0)
    tr.on_local_decode("消息队列怎么保证不丢消息", covered_samples=SR * 2, now=9.0)
    # speech ended at 2.5 s of pending audio: the decode (2.0 s) is behind it
    assert not tr.probe(0.6, voiced_end_samples=int(SR * 2.5))
    assert tr.last_decision.reason == "partial_behind_speech_end"
    assert tr.provisional_question() == ""
    tr.on_local_decode("消息队列怎么保证不丢消息？", covered_samples=int(SR * 2.8), now=10.0)
    assert tr.probe(0.6, voiced_end_samples=int(SR * 2.5))
    assert tr.provisional_question() == "消息队列怎么保证不丢消息？"


def test_remote_tracker_uses_provider_lag_or_endpoint():
    now = {"t": 5.0}
    tr = LiveTurnTracker(clock=lambda: now["t"], remote_lag_sec=0.3)
    tr.note_voice(5.0)
    tr.on_remote_partial("How would you design a rate limiter?", now=5.05)
    now["t"] = 5.2
    assert not tr.probe(0.6, voiced_end_samples=0)  # lag not elapsed yet
    tr.on_remote_endpoint()
    assert tr.probe(0.61, voiced_end_samples=0)


# -- provisional cue + reconcile ---------------------------------------------------


class _Log:
    def info(self, *a, **k): ...
    def warning(self, *a, **k): ...
    def debug(self, *a, **k): ...


def _machine():
    events, cues, tasks = [], [], []
    now = {"t": 100.0}
    sm = AssistAsrStateMachine(
        broadcast=events.append,
        submit_answer_task=lambda task: tasks.append(task) or True,
        begin_asr_turn=lambda: len(tasks) + 1,
        record_asr_turn=lambda _t: None,
        is_high_churn_submission=lambda _c, _t: False,
        logger=_Log(),
        clock=lambda: now["t"],
        early_cue=lambda q, qa_id, meta: cues.append((q, qa_id, dict(meta))),
    )
    return sm, events, cues, tasks, now


CFG = SimpleNamespace(
    assist_auto_answer_mode="always", auto_detect=True, intelligence_early_cue=True, assist_provisional_cue=True,
    assist_provisional_ttl_sec=8.0, transcription_min_sig_chars=2, assist_transcription_merge_gap_sec=0.0,
    assist_asr_confirm_window_sec=0.45, assist_asr_group_max_wait_sec=1.2, assist_asr_fast_confirm_sec=1.15,
    assist_asr_late_constraint_grace_sec=1.2, assist_eot_fast_flush=True,
)
SESSION = SimpleNamespace(capture_is_loopback=False, add_transcription=lambda _t: None, get_last_qa=lambda: None)


def _confirm(sm, now, text):
    sm.append_transcription_fragment(CFG, SESSION, text, now["t"], False)
    now["t"] += 2.0
    sm.try_flush_question_group(CFG, SESSION, now["t"], False)


def test_provisional_then_same_final_does_not_re_emit():
    sm, events, cues, tasks, now = _machine()
    qa = sm.submit_provisional(CFG, SESSION, "Redis 的持久化机制有哪些？", "conversation_mic", now["t"])
    assert qa and cues[0][2]["provisional"] is True
    _confirm(sm, now, "Redis的持久化机制有哪些?")
    assert len(cues) == 1, "same question must not flash a second cue"
    assert tasks[0][4]["qa_id"] == qa and tasks[0][4]["early_cue_emitted"] is True
    assert tasks[0][4]["provisional_relation"] == "same"
    assert sm.provisional_stats["same"] == 1


def test_premature_partial_is_reconciled_on_the_same_card():
    sm, events, cues, tasks, now = _machine()
    qa = sm.submit_provisional(CFG, SESSION, "如果数据扩大一百倍会怎么样？", "conversation_mic", now["t"])
    _confirm(sm, now, "如果数据扩大一百倍，你会怎么设计缓存？")
    assert tasks[0][4]["qa_id"] == qa
    assert cues[-1][1] == qa and cues[-1][2]["reconciled"] == "corrected"
    assert "设计缓存" in cues[-1][0]


def test_different_final_question_replaces_cue():
    sm, events, cues, tasks, now = _machine()
    qa = sm.submit_provisional(CFG, SESSION, "讲讲你做过的订单系统重构。", "conversation_mic", now["t"])
    _confirm(sm, now, "为什么选择 Kafka 而不是 RabbitMQ？")
    assert cues[-1][1] == qa and cues[-1][2]["reconciled"] == "replaced"
    assert sm.provisional_stats["replaced"] == 1


def test_unconfirmed_provisional_is_retracted():
    sm, events, cues, tasks, now = _machine()
    qa = sm.submit_provisional(CFG, SESSION, "消息队列怎么保证不丢消息？", "conversation_mic", now["t"])
    now["t"] += 9.0
    sm.try_flush_question_group(CFG, SESSION, now["t"], False)
    assert {"type": "guidance_fast_retract", "id": qa, "reason": "not_confirmed"} in events
    assert not tasks


def test_provisional_disabled_by_config():
    sm, *_rest = _machine()
    cfg = SimpleNamespace(**{**vars(CFG), "assist_provisional_cue": False})
    assert sm.submit_provisional(cfg, SESSION, "消息队列怎么保证不丢消息？", "conversation_mic", 0.0) is None


def test_reconcile_relation():
    assert reconcile_relation("Redis的持久化机制有哪些？", "Redis 的持久化机制有哪些?") == "same"
    assert reconcile_relation("如果数据扩大", "如果数据扩大一百倍，你会怎么设计缓存？") == "corrected"
    assert reconcile_relation("讲讲你的项目", "为什么选择 Kafka") == "replaced"


# -- latency clock -------------------------------------------------------------


def test_provisional_turn_keeps_e_and_g0_and_moves_q1_on_confirmation():
    latency_clock.reset()
    latency_clock.mark_speech_end("s", 10.0)
    latency_clock.start_turn("s", "qa-p1", q1=10.4, provisional=True)
    latency_clock.mark("qa-p1", "G0", 10.41)
    latency_clock.start_turn("s", "qa-p1", q1=11.9)  # authoritative confirmation
    m = latency_clock.metrics("qa-p1")
    assert m["ttfug_user_ms"] == 410
    assert m["qbd_ms"] == 1900
    latency_clock.reset()


def test_provisional_in_a_two_part_turn_maps_to_the_new_speech():
    sm, events, cues, tasks, now = _machine()
    sm.append_transcription_fragment(CFG, SESSION, "我们先聊聊缓存。", now["t"], False)
    qa = sm.submit_provisional(CFG, SESSION, "为什么选择 Redis 而不是 Memcached？", "conversation_mic", now["t"])
    assert "Memcached" in cues[-1][0], "the provisional cue must be about the newest speech"
    sm.append_transcription_fragment(CFG, SESSION, "为什么选择Redis而不是Memcached?", now["t"] + 0.1, False)
    now["t"] += 2.0
    sm.try_flush_question_group(CFG, SESSION, now["t"], False)
    confirmed = [task for task in tasks if task[4]["qa_id"] == qa]
    assert confirmed and "Memcached" in confirmed[0][0]


def test_comma_pause_after_a_question_like_clause_keeps_listening():
    """'写一个函数判断链表有没有环，<0.46 s> 说一下你的思路' must not end at the comma."""
    d = _eval(silence_sec=0.46, partial_text="写一个函数判断链表有没有环", partial_covers_end=True, partial_stable_sec=0.4)
    assert d.state is EotState.CONTINUE


def test_no_speculative_decode_on_a_mid_sentence_pause():
    tr = LiveTurnTracker(clock=lambda: 10.0)
    tr.on_local_decode("你们的服务拆分之后，然后", covered_samples=SR * 2, now=9.0)
    assert not tr.should_speculate()
    tr.on_local_decode("如果流量扩大十倍", covered_samples=SR * 2, now=9.5)
    assert not tr.should_speculate()
    tr.on_local_decode("消息队列怎么保证不丢消息", covered_samples=SR * 2, now=9.9)
    assert tr.should_speculate()
    assert LiveTurnTracker().should_speculate(), "no partial yet: speculate"


def test_complete_final_text_shows_the_cue_before_the_confirm_windows():
    sm, events, cues, tasks, now = _machine()
    sm.append_transcription_fragment(CFG, SESSION, "消息队列怎么保证不丢消息？", now["t"], False)
    assert cues and cues[0][2]["provisional"] is True, "cue must not wait for merge + group windows"
    assert not tasks
    now["t"] += 2.0
    sm.try_flush_question_group(CFG, SESSION, now["t"], False)
    assert tasks[0][4]["qa_id"] == cues[0][1] and tasks[0][4]["provisional_relation"] == "same"
    assert len(cues) == 1


def test_incomplete_final_text_waits_for_confirmation():
    sm, events, cues, tasks, now = _machine()
    sm.append_transcription_fragment(CFG, SESSION, "我们先聊聊缓存", now["t"], False)
    assert not cues


def test_short_follow_up_is_fast_after_a_previous_question():
    """'为什么？' must not wait the full 2 s merge gap when it follows a question."""
    sm, events, cues, tasks, now = _machine()
    session = SimpleNamespace(capture_is_loopback=False, add_transcription=lambda _t: None,
                              get_last_qa=lambda: SimpleNamespace(question="你们为什么选择 Kafka？"))
    cfg = SimpleNamespace(**{**vars(CFG), "assist_transcription_merge_gap_sec": 2.0, "assist_eot_merge_gap_sec": 0.35})
    sm.append_transcription_fragment(cfg, session, "为什么？", now["t"], False)
    assert cues and cues[0][2]["provisional"] is True
    now["t"] += 0.4
    sm.try_flush_merge_buffer(cfg, session, now["t"])
    assert sm.pending_group is not None, "merge flushed after the short EOT gap, not the 2 s gap"
