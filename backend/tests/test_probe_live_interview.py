from __future__ import annotations

import importlib


def test_probe_event_contract_covers_realtime_chain():
    probe = importlib.import_module("scripts.probe_live_interview")

    assert probe.MILESTONE_EVENTS == {
        "interviewer_transcription_partial": "first_partial_ms",
        "transcription": "final_transcript_ms",
        "question_parse_status": "question_parse_ms",
        "answer_start": "answer_start_ms",
        "answer_chunk": "answer_first_chunk_ms",
        "answer_done": "answer_done_ms",
        "answer_error": "answer_error_ms",
    }


def test_probe_cli_supports_custom_audio_path():
    probe = importlib.import_module("scripts.probe_live_interview")

    assert "--audio-path" in probe.main.__code__.co_consts
