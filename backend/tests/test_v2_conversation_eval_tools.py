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
