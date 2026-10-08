"""v2 Conversation evaluation tooling must preserve the evidence boundary."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from services.product import conversations
from services.storage import product as store


ROOT = Path(__file__).resolve().parents[2]


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
        },
        {
            "kind": "guidance",
            "session_id": "cs_1",
            "reviewer": "reviewer",
            "guidance_class": "PROACTIVE",
            "useful": False,
            "interruption_regret": True,
            "source_correct": False,
        },
        {
            "kind": "silence",
            "session_id": "cs_1",
            "reviewer": "reviewer",
            "silence_correct": True,
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
    shown = conversations.evaluate_guidance(session["id"], {
        "direct_question": "为什么？",
        "source_refs": [{"kind": "USER_NOTE", "excerpt": "source", "visibility": "PRIVATE"}],
    })["guidance"]
    assert shown
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
        {**base, "cognitive_load_delta": -2},
        {**base, "cognitive_load_delta": 2},
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
