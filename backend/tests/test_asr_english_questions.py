"""English interview questions in smart auto-answer mode (v1.2-R2 latency closure).

Found by the controlled latency corpus: the default ``smart`` mode rejected
every English question without a Chinese cue word ("这段内容不像完整问题"),
so English interviews never got a Fast Cue or an answer.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.assist.asr_state import AssistAsrStateMachine  # noqa: E402
from services.stt import classify_asr_question_candidate  # noqa: E402
from services.stt.text_utils import is_viable_asr_question_group  # noqa: E402

QUESTIONS = [
    "How would you design a rate limiter for a public API?",
    "What is a deadlock",
    "Tell me about a time you disagreed with your team.",
    "If the database becomes the bottleneck, what would you change first?",
    "Can you write a function to reverse a linked list",
    "Why did you choose that approach",
    "Walk me through how you would design a URL shortener",
    "So how does Kafka guarantee exactly once semantics",
]
NOT_QUESTIONS = [
    "Thank you, that's all for today",
    "I think that's fine",
    "Let's move on",
    "Whatever happens we ship on Friday",
    "OK",
]


@pytest.mark.parametrize("text", QUESTIONS)
def test_english_questions_are_promoted_and_viable(text):
    assert classify_asr_question_candidate(text, 2)[0] == "promote"
    assert is_viable_asr_question_group([text], 2)


@pytest.mark.parametrize("text", NOT_QUESTIONS)
def test_english_statements_are_not_questions(text):
    assert not is_viable_asr_question_group([text], 2)


def test_smart_mode_submits_an_english_question():
    tasks = []
    now = {"t": 0.0}
    sm = AssistAsrStateMachine(
        broadcast=lambda _d: None,
        submit_answer_task=lambda task: tasks.append(task) or True,
        begin_asr_turn=lambda: 1,
        record_asr_turn=lambda _t: None,
        is_high_churn_submission=lambda _c, _t: False,
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, debug=lambda *a, **k: None),
        clock=lambda: now["t"],
    )
    cfg = SimpleNamespace(
        assist_auto_answer_mode="smart", auto_detect=True, intelligence_early_cue=False,
        transcription_min_sig_chars=2, assist_transcription_merge_gap_sec=2.0, assist_eot_fast_flush=True,
        assist_eot_merge_gap_sec=0.35,
    )
    session = SimpleNamespace(capture_is_loopback=False, add_transcription=lambda _t: None, get_last_qa=lambda: None)
    sm.append_transcription_fragment(cfg, session, "How would you design a rate limiter for a public API?", 0.0, False)
    for step in range(1, 40):
        now["t"] = step * 0.1
        sm.try_flush_merge_buffer(cfg, session, now["t"])
        sm.try_flush_question_group(cfg, session, now["t"])
    assert tasks and "rate limiter" in tasks[0][0]
