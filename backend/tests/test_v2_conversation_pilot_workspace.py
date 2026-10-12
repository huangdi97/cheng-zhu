"""Pilot workspace orchestration must reduce operator error without inventing evidence."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from services.product import conversation_feedback, conversations
from services.storage import product as store


ROOT = Path(__file__).resolve().parents[2]


def _load():
    path = ROOT / "scripts" / "v2_conversation_pilot_workspace.py"
    spec = importlib.util.spec_from_file_location("v2_pilot_workspace_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ended_session(space_id: str, *, title: str) -> dict:
    session = conversations.create_session(space_id, title=title, consent_ack=True)
    conversations.start_session(session["id"])
    conversations.add_item(
        session["id"],
        item_type="OpenQuestion",
        title=f"{title} review candidate",
        source_refs=[{"kind": "USER_NOTE", "excerpt": "private review context", "visibility": "PRIVATE"}],
    )
    conversations.end_session(session["id"])
    return conversations.require_session(session["id"])


def _insert_transcript(session: dict, segment_id: str, text: str) -> None:
    store.insert("conversation_transcript_segment", {
        "id": segment_id,
        "space_id": session["space_id"],
        "session_id": session["id"],
        "channel": "PRIMARY_AUDIO",
        "text": text,
        "provider": "test",
        "source": "TEST",
        "is_final": True,
        "analysis": {
            "direct_question": {
                "eligible": True,
                "predicted": text.endswith("?"),
                "detector_version": "heuristic-v1",
                "channel": "PRIMARY_AUDIO",
                "ai_assistance": "AI_ALLOWED",
            },
        },
        "created_at": store.now(),
    })


def _workspace_fixture(product_env, tmp_path):
    project = conversations.create_space("Pilot Project", "PROJECT_SYNC")
    design = conversations.create_space("Pilot Design", "DESIGN_REVIEW")
    extra = conversations.create_space("Do Not Export", "PROJECT_SYNC")

    project_session = _ended_session(project["id"], title="Project selected")
    design_session = _ended_session(design["id"], title="Design selected")
    extra_session = _ended_session(extra["id"], title="Private unselected")

    _insert_transcript(project_session, "seg-selected-project", "为什么采用 v2?")
    _insert_transcript(design_session, "seg-selected-design", "design review status")
    _insert_transcript(extra_session, "seg-private-unselected", "UNSELECTED_PRIVATE_TRANSCRIPT")

    conversation_feedback.upsert_feedback(
        project_session["id"],
        kind="SESSION_OUTCOME",
        labels={"cognitive_load_delta": -1, "would_reuse_space": True},
    )

    workspace = tmp_path / "pilot-workspace"
    assignments = [
        (project_session["id"], "pilot-user-01"),
        (design_session["id"], "pilot-user-02"),
    ]
    return {
        "workspace": workspace,
        "assignments": assignments,
        "project": project,
        "design": design,
        "project_session": project_session,
        "design_session": design_session,
        "extra_session": extra_session,
    }


def test_init_workspace_is_selected_session_only_and_fail_closed(product_env, tmp_path):
    mod = _load()
    data = _workspace_fixture(product_env, tmp_path)

    result = mod.init_workspace(
        Path(store.DB_PATH),
        data["assignments"],
        data["workspace"],
    )

    workspace = data["workspace"]
    assert result["contract_version"] == mod.WORKSPACE_CONTRACT
    assert result["evidence_type"] == "LOCAL_OPERATOR_WORKSPACE_NOT_EVIDENCE"
    assert result["source"]["product_schema_version"] >= 12
    assert result["privacy"]["remote_upload"] is False
    assert result["claims"]["REAL_USER_VALIDATED"] is False
    assert result["claims"]["PMF_PROVEN"] is False

    draft = json.loads((workspace / "pilot-manifest.draft.json").read_text(encoding="utf-8"))
    assert draft["evidence_type"] == mod.pilot_manifest.DRAFT_EVIDENCE_TYPE
    selected = {
        row["session_id"]
        for profile in draft["profiles"].values()
        for row in profile["sessions"]
    }
    assert selected == {session_id for session_id, _ in data["assignments"]}

    seed = (workspace / "independent-review.seed.jsonl").read_text(encoding="utf-8")
    assert "UNSELECTED_PRIVATE_TRANSCRIPT" not in seed
    assert data["extra_session"]["id"] not in seed
    assert "为什么采用 v2?" in seed

    self_report = (workspace / "self-report.jsonl").read_text(encoding="utf-8")
    assert data["project_session"]["id"] in self_report
    assert data["extra_session"]["id"] not in self_report

    metadata_text = (workspace / "workspace.json").read_text(encoding="utf-8")
    assert str(Path(store.DB_PATH).resolve()) not in metadata_text
    assert result["source"]["database_sha256"]
    assert json.loads((workspace / "stable-promotion-policy.json").read_text(encoding="utf-8"))[
        "policy_version"
    ] == "v2.0-R1-stable-promotion-5"

    with pytest.raises(FileExistsError, match="workspace already exists"):
        mod.init_workspace(Path(store.DB_PATH), data["assignments"], workspace)


def test_finalize_workspace_requires_explicit_attestations_and_revalidates_db(product_env, tmp_path):
    mod = _load()
    data = _workspace_fixture(product_env, tmp_path)
    mod.init_workspace(Path(store.DB_PATH), data["assignments"], data["workspace"])

    with pytest.raises(ValueError, match="attestation"):
        mod.finalize_workspace(
            Path(store.DB_PATH),
            data["workspace"],
            attestations=[],
            critical_incidents=0,
        )

    policy_path = data["workspace"] / "stable-promotion-policy.json"
    original_policy = policy_path.read_bytes()
    policy_path.write_bytes(original_policy + b"\n")
    with pytest.raises(ValueError, match="hash drift"):
        mod.finalize_workspace(
            Path(store.DB_PATH),
            data["workspace"],
            attestations=mod.pilot_manifest.REQUIRED_ATTESTATIONS,
            critical_incidents=0,
        )
    policy_path.write_bytes(original_policy)

    finalization = mod.finalize_workspace(
        Path(store.DB_PATH),
        data["workspace"],
        attestations=mod.pilot_manifest.REQUIRED_ATTESTATIONS,
        critical_incidents=0,
    )
    final = json.loads(
        (data["workspace"] / "pilot-manifest.final.json").read_text(encoding="utf-8")
    )
    assert final["evidence_type"] == mod.pilot_manifest.FINAL_EVIDENCE_TYPE
    assert final["critical_incidents"] == 0
    assert set(final["attestations"]) == set(mod.pilot_manifest.REQUIRED_ATTESTATIONS)
    assert finalization["real_user_identity_system_verified"] is False
    assert finalization["real_world_authorization_system_verified"] is False
    assert finalization["participant_consent_system_verified"] is False
    assert finalization["pmf_proven"] is False

    with pytest.raises(FileExistsError, match="already been finalized"):
        mod.finalize_workspace(
            Path(store.DB_PATH),
            data["workspace"],
            attestations=mod.pilot_manifest.REQUIRED_ATTESTATIONS,
            critical_incidents=0,
        )


def test_evaluate_workspace_rejects_seed_and_preserves_no_go(product_env, tmp_path):
    mod = _load()
    data = _workspace_fixture(product_env, tmp_path)
    mod.init_workspace(Path(store.DB_PATH), data["assignments"], data["workspace"])
    mod.finalize_workspace(
        Path(store.DB_PATH),
        data["workspace"],
        attestations=mod.pilot_manifest.REQUIRED_ATTESTATIONS,
        critical_incidents=0,
    )

    seed = data["workspace"] / "independent-review.seed.jsonl"
    with pytest.raises(ValueError, match="unlabeled seed"):
        mod.evaluate_workspace(data["workspace"], [seed])

    final_manifest_path = data["workspace"] / "pilot-manifest.final.json"
    original_final_manifest = final_manifest_path.read_bytes()
    final_manifest_path.write_bytes(original_final_manifest + b"\n")
    dummy_review = tmp_path / "dummy-review.jsonl"
    dummy_review.write_text(
        json.dumps({
            "kind": "continue",
            "session_id": data["project_session"]["id"],
            "space_id": data["project"]["id"],
            "profile": "PROJECT_SYNC",
            "reviewer": "independent-dummy",
            "label_source": "INDEPENDENT_HUMAN_REVIEW",
            "writeback_accurate": True,
        }) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="hash drift"):
        mod.evaluate_workspace(data["workspace"], [dummy_review])
    final_manifest_path.write_bytes(original_final_manifest)

    review = tmp_path / "reviewer-a.jsonl"
    review.write_text(
        json.dumps({
            "kind": "continue",
            "session_id": data["project_session"]["id"],
            "space_id": data["project"]["id"],
            "profile": "PROJECT_SYNC",
            "reviewer": "independent-reviewer-a",
            "label_source": "INDEPENDENT_HUMAN_REVIEW",
            "writeback_accurate": True,
            "notes": "",
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    result = mod.evaluate_workspace(data["workspace"], [review])
    assert result["human_report"]["status"] == "HAS_HUMAN_LABELS"
    assert result["stable_readiness"]["status"] == "NO_GO"
    assert result["stable_readiness"]["claims"]["V2_STABLE_RELEASE"] is False
    assert result["stable_readiness"]["claims"]["PMF_PROVEN"] is False

    evaluation = data["workspace"] / "evaluation"
    assert (evaluation / "human-report.json").is_file()
    assert (evaluation / "stable-readiness.json").is_file()
    manifest = json.loads((evaluation / "evaluation-manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "NO_GO"
    assert manifest["inputs"]["independent_reviews"][0]["filename"] == review.name
    assert str(review.resolve()) not in json.dumps(manifest)

    with pytest.raises(FileExistsError, match="evaluation already exists"):
        mod.evaluate_workspace(data["workspace"], [review])
