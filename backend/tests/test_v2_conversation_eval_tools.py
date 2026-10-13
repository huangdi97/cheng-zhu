"""v2 Conversation evaluation tooling must preserve the evidence boundary."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from services.product import conversation_feedback, conversations
from services.storage import product as store


ROOT = Path(__file__).resolve().parents[2]


def _auto_system(segment_id: str, decision_class: str = "SHOWN") -> dict:
    return {
        "origin": {
            "kind": "TRANSCRIPT_AUTO",
            "runtime": "AUTOMATIC_TRANSCRIPT_GUIDANCE",
            "transcript_segment_id": segment_id,
            "channel": "PRIMARY_AUDIO",
            "ai_assistance": "AI_ALLOWED",
            "assistance_mode": "BALANCED",
            "decision_class": decision_class,
        }
    }


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_human_eval_missing_labels_stay_insufficient():
    human_eval = _load("v2_human_eval_missing", "scripts/v2_conversation_human_eval.py")
    report = human_eval.aggregate([
        {
            "kind": "guidance",
            "session_id": "cs_1",
            "reviewer": "reviewer",
            "guidance_class": "PROACTIVE",
            "useful": None,
            "interruption_regret": None,
            "source_correct": None,
        }
    ])
    assert report["status"] == "INSUFFICIENT_EVIDENCE"
    assert report["metrics"]["opportunity_precision"]["value"] is None
    assert report["metrics"]["opportunity_precision"]["n"] == 0
    assert report["claims"]["PMF_PROVEN"] is False
    assert report["claims"]["REAL_CONVERSATION_USER_EVIDENCE_AVAILABLE"] is False


def test_human_eval_uses_only_explicit_human_labels():
    human_eval = _load("v2_human_eval_labeled", "scripts/v2_conversation_human_eval.py")
    report = human_eval.aggregate([
        {
            "kind": "guidance",
            "session_id": "cs_1",
            "reviewer": "reviewer",
            "guidance_class": "PROACTIVE",
            "useful": True,
            "interruption_regret": False,
            "source_correct": True,
            "system": _auto_system("seg-guidance-1"),
        },
        {
            "kind": "guidance",
            "session_id": "cs_1",
            "reviewer": "reviewer",
            "guidance_class": "PROACTIVE",
            "useful": False,
            "interruption_regret": True,
            "source_correct": False,
            "system": _auto_system("seg-guidance-2"),
        },
        {
            "kind": "silence",
            "session_id": "cs_1",
            "reviewer": "reviewer",
            "silence_correct": True,
            "system": _auto_system("seg-silence-1", "ARBITER"),
        },
        {
            "kind": "direct_question",
            "session_id": "cs_1",
            "reviewer": "reviewer",
            "predicted": True,
            "actual": True,
        },
    ])
    assert report["status"] == "HAS_HUMAN_LABELS"
    assert report["metrics"]["opportunity_precision"] == {"value": 0.5, "n": 2}
    assert report["metrics"]["interruption_regret"] == {"value": 0.5, "n": 2}
    assert report["metrics"]["source_attribution_accuracy"] == {"value": 0.5, "n": 2}
    assert report["metrics"]["useful_silence_rate"] == {"value": 1.0, "n": 1}
    assert report["metrics"]["direct_question_precision"] == {"value": 1.0, "n": 1}
    assert report["claims"]["PMF_PROVEN"] is False
    assert report["claims"]["HUMAN_LABELS_AVAILABLE"] is True
    assert report["claims"]["REAL_CONVERSATION_USER_EVIDENCE_AVAILABLE"] is False


def test_label_seed_is_unlabeled_review_queue(product_env, tmp_path):
    seed = _load("v2_label_seed", "scripts/v2_conversation_label_seed.py")
    space = conversations.create_space("Dogfood Seed", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    segment_id = "cts-seed-auto"
    store.insert("conversation_transcript_segment", {
        "id": segment_id,
        "space_id": space["id"],
        "session_id": session["id"],
        "channel": "PRIMARY_AUDIO",
        "text": "为什么？",
        "provider": "whisper",
        "source": "SYSTEM_LOOPBACK",
        "is_final": True,
        "analysis": {
            "direct_question": {
                "eligible": True,
                "predicted": True,
                "detector_version": "heuristic-v1",
                "channel": "PRIMARY_AUDIO",
                "ai_assistance": "AI_ALLOWED",
            },
        },
        "created_at": store.now(),
    })
    shown = conversations.guidance_from_transcript(
        session["id"],
        "为什么？",
        channel="PRIMARY_AUDIO",
        frozen_direct_question={
            "eligible": True,
            "predicted": True,
            "detector_version": "heuristic-v1",
            "channel": "PRIMARY_AUDIO",
            "ai_assistance": "AI_ALLOWED",
        },
        transcript_segment_id=segment_id,
    )
    assert shown and shown["origin"]["kind"] == "TRANSCRIPT_AUTO"
    conversations.add_item(
        session["id"],
        item_type="OpenQuestion",
        title="谁负责 rollback？",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "未明确", "visibility": "PRIVATE"}],
    )
    conversations.end_session(session["id"])

    rows = seed.export_rows(Path(store.DB_PATH))
    guidance = next(row for row in rows if row["kind"] == "guidance")
    truth = next(row for row in rows if row["kind"] == "truth_item")
    outcome = next(row for row in rows if row["kind"] == "session_outcome")

    assert guidance["reviewer"] == ""
    assert guidance["useful"] is None
    assert guidance["source_correct"] is None
    assert truth["actual_type"] is None
    assert truth["actual_state"] is None
    assert outcome["cognitive_load_delta"] is None
    assert outcome["would_reuse_space"] is None


def test_seed_cli_refuses_to_overwrite_source_database_or_existing_labels(tmp_path, monkeypatch):
    import sys

    import pytest

    seed = _load("v2_label_seed_safe_output", "scripts/v2_conversation_label_seed.py")
    db = tmp_path / "product.db"
    original_db = b"existing-private-database"
    db.write_bytes(original_db)
    monkeypatch.setattr(sys, "argv", ["seed", "--db", str(db), "--out", str(db)])
    with pytest.raises(SystemExit):
        seed.main()
    assert db.read_bytes() == original_db

    existing = tmp_path / "labels.seed.jsonl"
    existing.write_text('{"reviewer":"human","useful":true}\n', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["seed", "--db", str(db), "--out", str(existing)])
    with pytest.raises(SystemExit):
        seed.main()
    assert existing.read_text(encoding="utf-8") == '{"reviewer":"human","useful":true}\n'


def test_human_eval_rejects_duplicate_reviewer_event(tmp_path):
    import json

    import pytest

    human_eval = _load("v2_human_eval_dedup", "scripts/v2_conversation_human_eval.py")
    row = {
        "kind": "guidance",
        "session_id": "cs_1",
        "event_id": "g_1",
        "reviewer": "Alice",
        "guidance_class": "PROACTIVE",
        "useful": True,
    }
    labels = tmp_path / "labels.jsonl"
    labels.write_text(json.dumps(row) + "\n" + json.dumps({**row, "reviewer": "alice"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate label"):
        human_eval.load_rows(labels)

    labels.write_text(json.dumps(row) + "\n" + json.dumps({**row, "reviewer": "Bob"}) + "\n", encoding="utf-8")
    assert len(human_eval.load_rows(labels)) == 2


def test_human_eval_stable_sample_unit_rejects_duplicate_event_metric_across_reviewers_or_sources():
    import pytest

    human_eval = _load("v2_human_eval_unique_event_metric", "scripts/v2_conversation_human_eval.py")
    base = {
        "kind": "guidance",
        "session_id": "cv-1",
        "space_id": "cs-1",
        "profile": "PROJECT_SYNC",
        "event_id": "g-1",
        "guidance_class": "PROACTIVE",
        "system": _auto_system("seg-1"),
        "useful": True,
    }

    with pytest.raises(ValueError, match="unique events, not annotations"):
        human_eval.aggregate([
            {**base, "reviewer": "reviewer-a", "label_source": "INDEPENDENT_HUMAN_REVIEW"},
            {**base, "reviewer": "reviewer-b", "label_source": "INDEPENDENT_HUMAN_REVIEW"},
        ])

    with pytest.raises(ValueError, match="unique events, not annotations"):
        human_eval.aggregate([
            {**base, "reviewer": "IN_PRODUCT_SELF_REPORT", "label_source": "LOCAL_IN_PRODUCT_EXPLICIT_SELF_REPORT"},
            {**base, "reviewer": "reviewer-a", "label_source": "INDEPENDENT_HUMAN_REVIEW"},
        ])

    # Two reviewers may still annotate different metric dimensions of the same
    # event; sample inflation is blocked per event × metric, not per event.
    report = human_eval.aggregate([
        {
            **base,
            "reviewer": "reviewer-a",
            "label_source": "INDEPENDENT_HUMAN_REVIEW",
            "useful": True,
            "interruption_regret": None,
        },
        {
            **base,
            "reviewer": "reviewer-b",
            "label_source": "INDEPENDENT_HUMAN_REVIEW",
            "useful": None,
            "interruption_regret": False,
        },
    ])
    assert report["metric_population"]["sample_unit"] == "UNIQUE_EVENT_PER_METRIC"
    assert report["metric_population"]["unique_metric_observations"] == {
        "interruption_regret": 1,
        "opportunity_precision": 1,
    }
    assert report["metrics"]["opportunity_precision"]["n"] == 1
    assert report["metrics"]["interruption_regret"]["n"] == 1


def test_human_eval_rejects_non_rubric_or_nonfinite_cognitive_labels(tmp_path):
    import json

    import pytest

    human_eval = _load("v2_human_eval_cognitive", "scripts/v2_conversation_human_eval.py")
    labels = tmp_path / "labels.jsonl"
    base = {"kind": "session_outcome", "session_id": "cs_1", "reviewer": "Alice"}
    for invalid in (True, 3, -3, "1", float("nan"), float("inf")):
        labels.write_text(
            json.dumps({**base, "cognitive_load_delta": invalid}) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError):
            human_eval.load_rows(labels)

    rows = [
        {**base, "cognitive_load_delta": True},
        {**base, "cognitive_load_delta": 99},
        {**base, "cognitive_load_delta": float("nan")},
        {**base, "session_id": "cs_valid_1", "cognitive_load_delta": -2},
        {**base, "session_id": "cs_valid_2", "cognitive_load_delta": 2},
    ]
    assert human_eval.aggregate(rows)["metrics"]["mean_cognitive_load_delta"] == {"value": 0.0, "n": 2}


def test_human_eval_cli_never_overwrites_its_labels(tmp_path, monkeypatch):
    import json
    import sys

    import pytest

    human_eval = _load("v2_human_eval_safe_output", "scripts/v2_conversation_human_eval.py")
    labels = tmp_path / "labeled.jsonl"
    original = json.dumps({
        "kind": "silence",
        "session_id": "cs_1",
        "reviewer": "Alice",
        "silence_correct": True,
    }) + "\n"
    labels.write_text(original, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["human-eval", str(labels), "--out", str(labels)])
    with pytest.raises(SystemExit):
        human_eval.main()
    assert labels.read_text(encoding="utf-8") == original

    report = tmp_path / "report.txt"
    monkeypatch.setattr(sys, "argv", [
        "human-eval", str(labels), "--out", str(report), "--markdown-out", str(report),
    ])
    with pytest.raises(SystemExit):
        human_eval.main()
    assert not report.exists()


def test_ai_candidate_prediction_snapshot_survives_review_mutation(product_env):
    space = conversations.create_space("Prediction Freeze", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    item = conversations.add_item(
        session["id"],
        item_type="Decision",
        title="采用 offline migration v2",
        state="PROPOSED",
        source_refs=[{"kind": "TRANSCRIPT_SEGMENT", "id": "seg-1", "visibility": "PRIVATE"}],
        confidence=0.87,
        epistemic_status="INFERRED",
        review_status="AI_EXTRACTED",
    )
    frozen = item["prediction"]
    assert frozen["type"] == "Decision"
    assert frozen["state"] == "PROPOSED"
    assert frozen["title"] == "采用 offline migration v2"

    reviewed = conversations.review_item(item["id"], "CONFIRM")
    assert reviewed["state"] == "AGREED"
    assert reviewed["review_status"] == "USER_CONFIRMED"
    assert reviewed["prediction"] == frozen
    assert reviewed["prediction"]["state"] == "PROPOSED"


def test_label_seed_does_not_leak_reviewed_legacy_truth_into_prediction(product_env):
    seed = _load("v2_label_seed_no_leakage", "scripts/v2_conversation_label_seed.py")
    space = conversations.create_space("Legacy Seed", "DESIGN_REVIEW")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    item = conversations.add_item(
        session["id"],
        item_type="Decision",
        title="旧数据候选",
        state="PROPOSED",
        source_refs=[{"kind": "USER_NOTE", "visibility": "PRIVATE"}],
    )
    # Simulate a pre-v10 row: no immutable prediction snapshot existed yet.
    store.update("conversation_item", item["id"], {"prediction": {}})
    conversations.review_item(item["id"], "CONFIRM")
    conversations.end_session(session["id"])

    row = next(
        value for value in seed.export_rows(Path(store.DB_PATH))
        if value["kind"] == "truth_item" and value["event_id"] == item["id"]
    )
    assert row["predicted_type"] is None
    assert row["predicted_state"] is None
    assert row["prediction_unavailable"] is True


def test_local_feedback_is_explicit_upsert_and_never_identity_proof(product_env):
    import pytest

    space = conversations.create_space("Pilot Feedback", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    shown = conversations.evaluate_guidance(session["id"], {
        "candidate_text": "补充 rollback owner",
        "source_refs": [{"kind": "USER_NOTE", "excerpt": "rollback owner 未定", "visibility": "PRIVATE"}],
        "relevance": 1,
        "novelty": 1,
        "provenance_strength": 1,
        "goal_relevance": 1,
        "decision_impact": 1,
    })["guidance"]
    assert shown and shown["status"] == "SHOWN"

    first = conversation_feedback.upsert_feedback(
        session["id"],
        kind="GUIDANCE",
        target_id=shown["id"],
        labels={"useful": True, "interruption_regret": False, "source_correct": True},
    )
    second = conversation_feedback.upsert_feedback(
        session["id"],
        kind="GUIDANCE",
        target_id=shown["id"],
        labels={"useful": False},
    )
    assert first["id"] == second["id"]
    assert second["labels"]["useful"] is False
    assert len(conversation_feedback.list_feedback(session["id"])) == 1

    with pytest.raises(ValueError, match="recall_correct"):
        conversation_feedback.upsert_feedback(
            session["id"],
            kind="GUIDANCE",
            target_id=shown["id"],
            labels={"recall_correct": True},
        )
    with pytest.raises(ValueError, match="Session 结束"):
        conversation_feedback.upsert_feedback(
            session["id"],
            kind="SESSION_OUTCOME",
            labels={"would_reuse_space": True},
        )
    with pytest.raises(ValueError, match="reviewer_kind"):
        conversation_feedback.upsert_feedback(
            session["id"],
            kind="GUIDANCE",
            target_id=shown["id"],
            labels={"useful": True},
            reviewer_kind="VERIFIED_EXTERNAL_USER",
        )

    conversations.end_session(session["id"])
    outcome = conversation_feedback.upsert_feedback(
        session["id"],
        kind="SESSION_OUTCOME",
        labels={"cognitive_load_delta": -1, "would_reuse_space": True},
    )
    assert outcome["reviewer_kind"] == "SELF_USER"
    queue = conversation_feedback.review_queue(session["id"])
    assert queue["real_user_validated"] is False
    assert queue["pmf_proven"] is False
    assert queue["evidence_boundary"] == "LOCAL_EXPLICIT_SELF_REPORT_NOT_REAL_USER_IDENTITY_PROOF"


def test_feedback_export_uses_only_explicit_rows_not_guidance_actions(product_env):
    exporter = _load("v2_feedback_export", "scripts/v2_conversation_feedback_export.py")
    space = conversations.create_space("Feedback Export", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])

    unlabeled = conversations.evaluate_guidance(session["id"], {
        "direct_question": "状态如何？",
    })["guidance"]
    assert unlabeled
    conversations.set_guidance_action(unlabeled["id"], "DISMISSED")

    segment_id = "cts-feedback-auto"
    store.insert("conversation_transcript_segment", {
        "id": segment_id,
        "space_id": space["id"],
        "session_id": session["id"],
        "channel": "PRIMARY_AUDIO",
        "text": "状态如何？",
        "provider": "whisper",
        "source": "SYSTEM_LOOPBACK",
        "is_final": True,
        "analysis": {
            "direct_question": {
                "eligible": True,
                "predicted": True,
                "detector_version": "heuristic-v1",
                "channel": "PRIMARY_AUDIO",
                "ai_assistance": "AI_ALLOWED",
            },
        },
        "created_at": store.now(),
    })
    labeled = conversations.guidance_from_transcript(
        session["id"],
        "状态如何？",
        channel="PRIMARY_AUDIO",
        frozen_direct_question={
            "eligible": True,
            "predicted": True,
            "detector_version": "heuristic-v1",
            "channel": "PRIMARY_AUDIO",
            "ai_assistance": "AI_ALLOWED",
        },
        transcript_segment_id=segment_id,
    )
    assert labeled and labeled["origin"]["transcript_segment_id"] == segment_id
    conversation_feedback.upsert_feedback(
        session["id"],
        kind="GUIDANCE",
        target_id=labeled["id"],
        labels={"useful": True, "source_correct": True},
    )
    conversations.end_session(session["id"])
    conversation_feedback.upsert_feedback(
        session["id"],
        kind="CONTINUE",
        labels={"writeback_accurate": True},
    )

    rows = exporter.export_rows(Path(store.DB_PATH))
    assert {row["event_id"] for row in rows if row["kind"] == "guidance"} == {labeled["id"]}
    assert all(row["reviewer"] == "IN_PRODUCT_SELF_REPORT" for row in rows)
    assert any(row["kind"] == "continue" and row["writeback_accurate"] is True for row in rows)


def test_session_export_contains_local_feedback_but_keeps_claim_boundary(product_env):
    space = conversations.create_space("Feedback Export Contract", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    conversations.end_session(session["id"])
    feedback = conversation_feedback.upsert_feedback(
        session["id"],
        kind="SESSION_OUTCOME",
        labels={"cognitive_load_delta": 0, "would_reuse_space": False},
    )
    exported = conversations.export_session(session["id"])
    assert "human_feedback" in exported["export_manifest"]["categories"]
    assert [row["id"] for row in exported["human_feedback"]] == [feedback["id"]]
    diagnostics = conversations.diagnostics()
    assert diagnostics["runtime"]["explicit_human_feedback_rows"] >= 1
    assert diagnostics["evidence"]["real_conversation_user_evidence"] == "REAL_CONVERSATION_USER_EVIDENCE_PENDING"
    assert diagnostics["evidence"]["pmf"] == "PMF_PROVEN_FALSE"


def test_human_eval_global_dedup_spans_multiple_label_files(tmp_path):
    import json
    import pytest

    human_eval = _load("v2_human_eval_multifile", "scripts/v2_conversation_human_eval.py")
    row = {
        "kind": "guidance",
        "session_id": "cs_multi",
        "event_id": "g_multi",
        "reviewer": "IN_PRODUCT_SELF_REPORT",
        "guidance_class": "PROACTIVE",
        "useful": True,
    }
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    first.write_text(json.dumps(row) + "\n", encoding="utf-8")
    second.write_text(json.dumps(row) + "\n", encoding="utf-8")
    seen = set()
    assert len(human_eval.load_rows(first, seen=seen)) == 1
    with pytest.raises(ValueError, match="duplicate label"):
        human_eval.load_rows(second, seen=seen)


def test_human_eval_excludes_manual_and_forced_silence_from_stable_live_populations():
    human_eval = _load("v2_human_eval_runtime_population", "scripts/v2_conversation_human_eval.py")
    rows = [
        {
            "kind": "guidance", "session_id": "s", "reviewer": "r",
            "guidance_class": "PROACTIVE", "useful": True, "interruption_regret": False,
            "source_correct": True, "system": _auto_system("seg-auto"),
        },
        {
            "kind": "guidance", "session_id": "s", "reviewer": "r",
            "guidance_class": "PROACTIVE", "useful": False, "interruption_regret": True,
            "source_correct": False, "system": {},
        },
        {
            "kind": "silence", "session_id": "s", "reviewer": "r",
            "silence_correct": True, "system": _auto_system("seg-arbiter", "ARBITER"),
        },
        {
            "kind": "silence", "session_id": "s", "reviewer": "r",
            "silence_correct": True, "system": _auto_system("seg-quiet", "MODE_FORCED"),
        },
    ]
    report = human_eval.aggregate(rows)
    assert report["metrics"]["opportunity_precision"] == {"value": 1.0, "n": 1}
    assert report["metrics"]["interruption_regret"] == {"value": 0.0, "n": 1}
    assert report["metrics"]["source_attribution_accuracy"] == {"value": 1.0, "n": 1}
    assert report["metrics"]["useful_silence_rate"] == {"value": 1.0, "n": 1}
    assert report["metric_population"]["excluded_non_auto_guidance_rows"] == 1
    assert report["metric_population"]["excluded_non_arbiter_or_non_auto_silence_rows"] == 1


def test_human_eval_decision_commitment_precision_uses_only_predicted_target_classes():
    human_eval = _load("v2_human_eval_truth_population", "scripts/v2_conversation_human_eval.py")
    rows = [
        {
            "kind": "truth_item", "session_id": "s", "reviewer": "r", "event_id": "d1",
            "predicted_type": "Decision", "predicted_state": "PROPOSED",
            "actual_type": "Decision", "actual_state": "PROPOSED",
        },
        {
            "kind": "truth_item", "session_id": "s", "reviewer": "r", "event_id": "c1",
            "predicted_type": "Commitment", "predicted_state": "PROPOSED",
            "actual_type": "Commitment", "actual_state": "COMMITTED",
        },
        {
            "kind": "truth_item", "session_id": "s", "reviewer": "r", "event_id": "t1",
            "predicted_type": "Task", "predicted_state": "PROPOSED",
            "actual_type": "Task", "actual_state": "PROPOSED",
        },
        {
            "kind": "truth_item", "session_id": "s", "reviewer": "r", "event_id": "q1",
            "predicted_type": "OpenQuestion", "predicted_state": "PROPOSED",
            "actual_type": "OpenQuestion", "actual_state": "PROPOSED",
        },
        {
            "kind": "truth_item", "session_id": "s", "reviewer": "r", "event_id": "r1",
            "predicted_type": "Risk", "predicted_state": "PROPOSED",
            "actual_type": "Risk", "actual_state": "PROPOSED",
        },
    ]
    report = human_eval.aggregate(rows)
    assert report["metrics"]["decision_commitment_state_precision"] == {"value": 0.666667, "n": 3}
    assert report["metric_population"]["decision_commitment_task_predicted_rows"] == 3
    assert report["metric_population"]["excluded_other_truth_item_rows"] == 2


def test_feedback_review_queue_excludes_manual_and_forced_silence(product_env):
    space = conversations.create_space("Runtime Feedback Queue", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])

    manual = conversations.evaluate_guidance(session["id"], {"direct_question": "manual?"})["guidance"]
    assert manual and not manual.get("origin")

    auto = conversations._persist_guidance(
        session["id"],
        kind="CONTRIBUTION_OPPORTUNITY",
        action="ADD_TALKING_POINT",
        text="auto",
        source_refs=[],
        status="SHOWN",
        reason="TRANSCRIPT_SOURCE_OPPORTUNITY",
        origin=_auto_system("seg-auto")["origin"],
    )
    arbiter_silent = conversations._persist_guidance(
        session["id"],
        kind="RECALL",
        action="SILENT",
        text="",
        source_refs=[],
        status="SUPPRESSED",
        reason="TRANSCRIPT_NO_GROUNDED_OPPORTUNITY",
        origin=_auto_system("seg-silent", "ARBITER")["origin"],
    )
    forced_silent = conversations._persist_guidance(
        session["id"],
        kind="RECALL",
        action="SILENT",
        text="",
        source_refs=[],
        status="SUPPRESSED",
        reason="TRANSCRIPT_MODE_QUIET",
        origin=_auto_system("seg-forced", "MODE_FORCED")["origin"],
    )

    queue = conversation_feedback.review_queue(session["id"])
    assert [entry["event"]["id"] for entry in queue["guidance"]] == [auto["id"]]
    assert [entry["event"]["id"] for entry in queue["silence"]] == [arbiter_silent["id"]]
    flat = repr(queue)
    assert manual["id"] not in flat
    assert forced_silent["id"] not in flat


def test_label_seed_uses_frozen_direct_question_prediction_and_marks_legacy_unavailable(product_env):
    seed = _load("v2_label_seed_direct_question_snapshot", "scripts/v2_conversation_label_seed.py")
    space = conversations.create_space("DQ Eval", "PROJECT_SYNC")
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])

    store.insert("conversation_transcript_segment", {
        "id": "cts-dq-true",
        "space_id": space["id"],
        "session_id": session["id"],
        "channel": "PRIMARY_AUDIO",
        "text": "为什么采用 v2？",
        "provider": "whisper",
        "source": "SYSTEM_LOOPBACK",
        "is_final": True,
        "analysis": {
            "direct_question": {
                "eligible": True,
                "predicted": True,
                "detector_version": "heuristic-v1",
                "channel": "PRIMARY_AUDIO",
            },
        },
        "created_at": 1.0,
    })
    store.insert("conversation_transcript_segment", {
        "id": "cts-dq-false",
        "space_id": space["id"],
        "session_id": session["id"],
        "channel": "PRIMARY_AUDIO",
        "text": "我们继续讨论 v2",
        "provider": "whisper",
        "source": "SYSTEM_LOOPBACK",
        "is_final": True,
        "analysis": {
            "direct_question": {
                "eligible": True,
                "predicted": False,
                "detector_version": "heuristic-v1",
                "channel": "PRIMARY_AUDIO",
            },
        },
        "created_at": 2.0,
    })
    store.insert("conversation_transcript_segment", {
        "id": "cts-dq-disabled",
        "space_id": space["id"],
        "session_id": session["id"],
        "channel": "PRIMARY_AUDIO",
        "text": "为什么这个 session 没启用 AI？",
        "provider": "whisper",
        "source": "SYSTEM_LOOPBACK",
        "is_final": True,
        "analysis": {
            "direct_question": {
                "eligible": False,
                "predicted": False,
                "detector_version": "heuristic-v1",
                "channel": "PRIMARY_AUDIO",
                "ai_assistance": "AI_FORBIDDEN",
            },
        },
        "created_at": 2.5,
    })
    store.insert("conversation_transcript_segment", {
        "id": "cts-dq-legacy",
        "space_id": space["id"],
        "session_id": session["id"],
        "channel": "PRIMARY_AUDIO",
        "text": "这个历史句子看起来像问题吗？",
        "provider": "whisper",
        "source": "SYSTEM_LOOPBACK",
        "is_final": True,
        "analysis": {},
        "created_at": 3.0,
    })
    store.insert("conversation_transcript_segment", {
        "id": "cts-self-mic",
        "space_id": space["id"],
        "session_id": session["id"],
        "channel": "SELF_MIC",
        "text": "我自己说的话不进入 direct-question reviewer queue？",
        "provider": "whisper",
        "source": "SELF_MIC",
        "is_final": True,
        "analysis": {
            "direct_question": {
                "eligible": False,
                "predicted": False,
                "detector_version": "heuristic-v1",
                "channel": "SELF_MIC",
            },
        },
        "created_at": 4.0,
    })
    conversations.end_session(session["id"])

    rows = [
        row for row in seed.export_rows(Path(store.DB_PATH))
        if row["kind"] == "direct_question"
    ]
    by_id = {row["event_id"]: row for row in rows}
    assert by_id["cts-dq-true"]["predicted"] is True
    assert by_id["cts-dq-true"]["prediction_unavailable"] is False
    assert by_id["cts-dq-false"]["predicted"] is False
    assert by_id["cts-dq-false"]["prediction_unavailable"] is False
    assert by_id["cts-dq-legacy"]["predicted"] is None
    assert by_id["cts-dq-legacy"]["prediction_unavailable"] is True
    assert "cts-dq-disabled" not in by_id
    assert "cts-self-mic" not in by_id
    assert by_id["cts-dq-true"]["actual"] is None
    assert by_id["cts-dq-true"]["reviewer"] == ""
    assert by_id["cts-dq-true"]["label_source"] == ""
    assert by_id["cts-dq-true"]["system"]["direct_question_prediction"]["detector_version"] == "heuristic-v1"


def test_human_eval_emits_cohort_binding_and_profile_source_metrics():
    human_eval = _load("v2_human_eval_cohort_binding", "scripts/v2_conversation_human_eval.py")
    rows = [
        {
            "kind": "session_outcome",
            "session_id": "cv-project-real",
            "space_id": "cs-project-real",
            "profile": "PROJECT_SYNC",
            "reviewer": "IN_PRODUCT_SELF_REPORT",
            "label_source": "LOCAL_IN_PRODUCT_EXPLICIT_SELF_REPORT",
            "cognitive_load_delta": -1,
            "would_reuse_space": True,
        },
        {
            "kind": "session_outcome",
            "session_id": "cv-design-real",
            "space_id": "cs-design-real",
            "profile": "DESIGN_REVIEW",
            "reviewer": "IN_PRODUCT_SELF_REPORT",
            "label_source": "LOCAL_IN_PRODUCT_EXPLICIT_SELF_REPORT",
            "cognitive_load_delta": 0,
            "would_reuse_space": False,
        },
    ]
    report = human_eval.aggregate(rows)
    assert report["report_contract_version"] == "v2.0-R1-human-eval-5"
    assert report["cohort"]["status"] == "COMPLETE"
    assert report["cohort"]["sessions"] == [
        {
            "session_id": "cv-design-real",
            "profile": "DESIGN_REVIEW",
            "space_id": "cs-design-real",
        },
        {
            "session_id": "cv-project-real",
            "profile": "PROJECT_SYNC",
            "space_id": "cs-project-real",
        },
    ]
    project = report["metrics_by_profile_and_label_source"]["PROJECT_SYNC"][
        "LOCAL_IN_PRODUCT_EXPLICIT_SELF_REPORT"
    ]
    design = report["metrics_by_profile_and_label_source"]["DESIGN_REVIEW"][
        "LOCAL_IN_PRODUCT_EXPLICIT_SELF_REPORT"
    ]
    assert project["mean_cognitive_load_delta"] == {"value": -1.0, "n": 1}
    assert project["space_reuse_intent_rate"] == {"value": 1.0, "n": 1}
    assert design["mean_cognitive_load_delta"] == {"value": 0.0, "n": 1}
    assert design["space_reuse_intent_rate"] == {"value": 0.0, "n": 1}


def test_human_eval_marks_conflicting_session_profile_or_space_as_incomplete():
    human_eval = _load("v2_human_eval_cohort_conflict", "scripts/v2_conversation_human_eval.py")
    rows = [
        {
            "kind": "continue",
            "session_id": "cv-same",
            "space_id": "cs-one",
            "profile": "PROJECT_SYNC",
            "reviewer": "r1",
            "label_source": "INDEPENDENT_HUMAN_REVIEW",
            "writeback_accurate": None,
        },
        {
            "kind": "continue",
            "session_id": "cv-same",
            "space_id": "cs-two",
            "profile": "DESIGN_REVIEW",
            "reviewer": "r2",
            "label_source": "INDEPENDENT_HUMAN_REVIEW",
            "writeback_accurate": None,
        },
    ]
    report = human_eval.aggregate(rows)
    assert report["cohort"]["status"] == "INCOMPLETE"
    assert any("inconsistent profile/space" in value for value in report["cohort"]["errors"])


def test_human_eval_longitudinal_recall_utility_requires_prior_session_same_space_provenance():
    human_eval = _load("v2_human_eval_longitudinal_recall", "scripts/v2_conversation_human_eval.py")

    def recall_row(event_id: str, source_session: str, source_space: str, *, with_item_ref: bool = True):
        system = _auto_system(f"seg-{event_id}")
        system["source_refs"] = (
            [{
                "kind": "CONVERSATION_ITEM",
                "id": f"ci-{event_id}",
                "space_id": source_space,
                "session_id": source_session,
                "review_status": "USER_CONFIRMED",
                "state": "AGREED",
                "visibility": "PRIVATE",
            }]
            if with_item_ref else
            [{"kind": "TRANSCRIPT_SEGMENT", "id": f"legacy-{event_id}", "visibility": "PRIVATE"}]
        )
        return {
            "kind": "guidance",
            "session_id": "cv-current",
            "space_id": "cs-current",
            "profile": "PROJECT_SYNC",
            "event_id": event_id,
            "reviewer": "IN_PRODUCT_SELF_REPORT",
            "label_source": "LOCAL_IN_PRODUCT_EXPLICIT_SELF_REPORT",
            "guidance_class": "RECALL",
            "useful": True,
            "recall_correct": None,
            "system": system,
        }

    report = human_eval.aggregate([
        recall_row("g-long", "cv-prior", "cs-current"),
        recall_row("g-same-session", "cv-current", "cs-current"),
        recall_row("g-cross-space", "cv-prior-other", "cs-other"),
        recall_row("g-legacy", "", "", with_item_ref=False),
    ])

    assert report["report_contract_version"] == "v2.0-R1-human-eval-6"
    assert report["metrics"]["longitudinal_recall_utility_rate"] == {"value": 1.0, "n": 1}
    population = report["metric_population"]
    assert population["auto_recall_rows"] == 4
    assert population["longitudinal_recall_rows"] == 1
    assert population["excluded_recall_without_prior_session_item_provenance"] == 3
    assert population["unique_metric_observations"]["longitudinal_recall_utility_rate"] == 1


def test_feedback_export_preserves_prior_session_recall_provenance_for_longitudinal_value(product_env):
    exporter = _load("v2_feedback_export_longitudinal", "scripts/v2_conversation_feedback_export.py")
    human_eval = _load("v2_human_eval_longitudinal_export", "scripts/v2_conversation_human_eval.py")

    space = conversations.create_space("Longitudinal Feedback", "PROJECT_SYNC")
    prior = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(prior["id"])
    decision = conversations.add_item(
        prior["id"],
        item_type="Decision",
        title="offline migration 采用 v2",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "明确采用 v2", "visibility": "PRIVATE"}],
        epistemic_status="OBSERVED",
    )
    conversations.review_item(decision["id"], "CONFIRM")
    conversations.end_session(prior["id"])

    current = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(current["id"])
    segment_id = "cts-longitudinal-feedback"
    store.insert("conversation_transcript_segment", {
        "id": segment_id,
        "space_id": space["id"],
        "session_id": current["id"],
        "channel": "PRIMARY_AUDIO",
        "text": "我们回到 offline migration",
        "provider": "whisper",
        "source": "SYSTEM_LOOPBACK",
        "is_final": True,
        "analysis": {
            "direct_question": {
                "eligible": True,
                "predicted": False,
                "detector_version": "heuristic-v1",
                "channel": "PRIMARY_AUDIO",
                "ai_assistance": "AI_ALLOWED",
            },
        },
        "created_at": store.now(),
    })
    recall = conversations.guidance_from_transcript(
        current["id"],
        "我们回到 offline migration",
        channel="PRIMARY_AUDIO",
        frozen_direct_question={
            "eligible": True,
            "predicted": False,
            "detector_version": "heuristic-v1",
            "channel": "PRIMARY_AUDIO",
            "ai_assistance": "AI_ALLOWED",
        },
        transcript_segment_id=segment_id,
    )
    assert recall and recall["kind"] == "RECALL"
    assert recall["source_refs"][0]["kind"] == "CONVERSATION_ITEM"
    assert recall["source_refs"][0]["session_id"] == prior["id"]

    conversation_feedback.upsert_feedback(
        current["id"],
        kind="GUIDANCE",
        target_id=recall["id"],
        labels={"useful": True},
    )
    conversations.end_session(current["id"])

    rows = exporter.export_rows(Path(store.DB_PATH))
    exported = next(row for row in rows if row.get("event_id") == recall["id"])
    assert exported["system"]["source_refs"][0]["kind"] == "CONVERSATION_ITEM"
    assert exported["system"]["source_refs"][0]["id"] == decision["id"]
    assert exported["system"]["source_refs"][0]["session_id"] == prior["id"]

    report = human_eval.aggregate([exported])
    assert report["metrics"]["longitudinal_recall_utility_rate"] == {"value": 1.0, "n": 1}
