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
    assert result["source"]["database_file_sha256_advisory"]
    assert result["source"]["database_file_sha256_includes_wal"] is False
    assert result["source"]["logical_state_anchor"] == "selected-cohort.snapshot.json"

    snapshot = json.loads(
        (workspace / "selected-cohort.snapshot.json").read_text(encoding="utf-8")
    )
    assert snapshot["contract_version"] == mod.SELECTED_COHORT_SNAPSHOT_CONTRACT
    assert {row["session_id"] for row in snapshot["sessions"]} == {
        session_id for session_id, _ in data["assignments"]
    }
    assert all(row["frozen_pack_digest"] for row in snapshot["sessions"])
    snapshot_text = json.dumps(snapshot, ensure_ascii=False)
    assert "Pilot Project" not in snapshot_text
    assert "Pilot Design" not in snapshot_text
    assert "为什么采用 v2?" not in snapshot_text
    assert "private review context" not in snapshot_text

    snapshot_meta = result["outputs"]["selected_cohort_snapshot"]
    assert snapshot_meta["sessions"] == 2
    assert snapshot_meta["sha256"]
    assert snapshot_meta["logical_sha256"]
    assert json.loads((workspace / "stable-promotion-policy.json").read_text(encoding="utf-8"))[
        "policy_version"
    ] == "v2.0-R1-stable-promotion-5"

    with pytest.raises(FileExistsError, match="workspace already exists"):
        mod.init_workspace(Path(store.DB_PATH), data["assignments"], workspace)


def test_inspect_pilot_sessions_is_privacy_minimized_and_reports_quick_debrief(product_env, tmp_path):
    mod = _load()
    data = _workspace_fixture(product_env, tmp_path)

    conversation_feedback.upsert_feedback(
        data["project_session"]["id"],
        kind="CONTINUE",
        labels={"writeback_accurate": True},
    )

    report = mod.inspect_pilot_sessions(Path(store.DB_PATH))
    by_id = {row["session_id"]: row for row in report["sessions"]}
    project = by_id[data["project_session"]["id"]]

    assert report["inspection_type"] == "LOCAL_PRIVACY_MINIMIZED_PILOT_SESSION_INVENTORY"
    assert project["profile"] == "PROJECT_SYNC"
    assert project["structurally_selectable"] is True
    assert project["structural_blockers"] == []
    assert project["consent_ack_recorded"] is True
    assert project["frozen_pack_verified"] is True
    assert project["local_self_report"]["quick_debrief"] == {
        "continue_accuracy": True,
        "space_reuse_intent": True,
        "cognitive_load_delta": True,
        "completed": 3,
        "total": 3,
        "complete": True,
    }
    assert report["claims"]["STRUCTURALLY_SELECTABLE_IS_AUTHORIZED_REAL_USE"] is False
    assert report["claims"]["REAL_USER_IDENTITY_SYSTEM_VERIFIED"] is False
    assert report["claims"]["REAL_USER_VALIDATED"] is False
    assert report["claims"]["PMF_PROVEN"] is False

    serialized = json.dumps(report, ensure_ascii=False)
    assert "Pilot Project" not in serialized
    assert "Pilot Design" not in serialized
    assert "Do Not Export" not in serialized
    assert "Project selected" not in serialized
    assert "Private unselected" not in serialized
    assert "为什么采用 v2?" not in serialized
    assert "UNSELECTED_PRIVATE_TRANSCRIPT" not in serialized
    assert "private review context" not in serialized
    assert report["privacy"]["transcript_text_exported"] is False
    assert report["privacy"]["participants_exported"] is False
    assert report["privacy"]["user_refs_assigned"] is False


def test_inspect_pilot_sessions_explains_structural_blockers_without_authorizing_sessions(product_env):
    mod = _load()

    active_space = conversations.create_space("Active private title", "PROJECT_SYNC")
    active = conversations.create_session(active_space["id"], consent_ack=True)
    conversations.start_session(active["id"])

    client_space = conversations.create_space("Client private title", "CLIENT_CALL")
    client = _ended_session(client_space["id"], title="Client private session")

    blocked_space = conversations.create_space("Missing consent private title", "DESIGN_REVIEW")
    blocked = _ended_session(blocked_space["id"], title="Blocked private session")
    store.update("conversation_session", blocked["id"], {"consent_ack": False})

    report = mod.inspect_pilot_sessions(Path(store.DB_PATH))
    by_id = {row["session_id"]: row for row in report["sessions"]}

    assert by_id[active["id"]]["structurally_selectable"] is False
    assert "SESSION_NOT_ENDED" in by_id[active["id"]]["structural_blockers"]

    assert by_id[client["id"]]["structurally_selectable"] is False
    assert "PROFILE_NOT_LAUNCH_COHORT" in by_id[client["id"]]["structural_blockers"]

    assert by_id[blocked["id"]]["structurally_selectable"] is False
    assert "CONSENT_ACK_NOT_RECORDED" in by_id[blocked["id"]]["structural_blockers"]

    assert report["claims"]["REAL_WORLD_AUTHORIZATION_SYSTEM_VERIFIED"] is False
    assert report["claims"]["PARTICIPANT_CONSENT_SYSTEM_VERIFIED"] is False


def test_workspace_cohort_snapshot_ignores_unrelated_db_growth_but_blocks_selected_session_drift(product_env, tmp_path):
    mod = _load()
    data = _workspace_fixture(product_env, tmp_path)
    mod.init_workspace(Path(store.DB_PATH), data["assignments"], data["workspace"])

    # Unrelated local activity is allowed. The workspace freezes only the
    # selected cohort, not the entire WAL-backed product.db file.
    unrelated = conversations.create_space("Unrelated after init", "PROJECT_SYNC")
    _ended_session(unrelated["id"], title="Unrelated Session")
    finalization = mod.finalize_workspace(
        Path(store.DB_PATH),
        data["workspace"],
        attestations=mod.pilot_manifest.REQUIRED_ATTESTATIONS,
        critical_incidents=0,
    )
    assert finalization["selected_cohort_snapshot_sha256"]
    assert finalization["selected_cohort_logical_sha256"]


def test_workspace_finalize_fails_closed_on_selected_session_or_pack_drift(product_env, tmp_path):
    mod = _load()
    data = _workspace_fixture(product_env, tmp_path)
    workspace = data["workspace"]
    mod.init_workspace(Path(store.DB_PATH), data["assignments"], workspace)

    selected = conversations.require_session(data["project_session"]["id"])
    original_ended_at = selected["ended_at"]
    store.update(
        "conversation_session",
        selected["id"],
        {"ended_at": float(original_ended_at) + 1.0},
    )
    with pytest.raises(ValueError, match="selected cohort structural drift"):
        mod.finalize_workspace(
            Path(store.DB_PATH),
            workspace,
            attestations=mod.pilot_manifest.REQUIRED_ATTESTATIONS,
            critical_incidents=0,
        )
    store.update(
        "conversation_session",
        selected["id"],
        {"ended_at": original_ended_at},
    )

    pack_id = conversations.require_session(selected["id"])["pack_id"]
    pack = store.get("conversation_session_pack", pack_id)
    assert pack is not None
    original_digest = pack["digest"]
    store.update("conversation_session_pack", pack_id, {"digest": "drifted-pack-digest"})
    with pytest.raises(ValueError, match="payload digest mismatch"):
        mod.finalize_workspace(
            Path(store.DB_PATH),
            workspace,
            attestations=mod.pilot_manifest.REQUIRED_ATTESTATIONS,
            critical_incidents=0,
        )
    store.update("conversation_session_pack", pack_id, {"digest": original_digest})

    original_payload = pack["payload"]
    tampered_payload = {**original_payload, "_tampered_for_test": True}
    store.update("conversation_session_pack", pack_id, {"payload": tampered_payload})
    with pytest.raises(ValueError, match="payload digest mismatch"):
        mod.finalize_workspace(
            Path(store.DB_PATH),
            workspace,
            attestations=mod.pilot_manifest.REQUIRED_ATTESTATIONS,
            critical_incidents=0,
        )
    store.update("conversation_session_pack", pack_id, {"payload": original_payload})

    finalization = mod.finalize_workspace(
        Path(store.DB_PATH),
        workspace,
        attestations=mod.pilot_manifest.REQUIRED_ATTESTATIONS,
        critical_incidents=0,
    )
    assert finalization["selected_cohort_snapshot_sha256"]


def test_inspect_marks_corrupt_or_context_drifted_pack_ineligible(product_env, tmp_path):
    mod = _load()
    data = _workspace_fixture(product_env, tmp_path)

    selected = conversations.require_session(data["project_session"]["id"])
    pack = store.get("conversation_session_pack", selected["pack_id"])
    assert pack is not None
    original_digest = pack["digest"]

    store.update("conversation_session_pack", pack["id"], {"digest": "corrupt-digest"})
    report = mod.inspect_pilot_sessions(Path(store.DB_PATH))
    row = next(item for item in report["sessions"] if item["session_id"] == selected["id"])
    assert row["frozen_pack_verified"] is False
    assert row["structurally_selectable"] is False
    assert "FROZEN_SESSION_PACK_INTEGRITY_FAILED" in row["structural_blockers"]

    store.update("conversation_session_pack", pack["id"], {"digest": original_digest})
    store.update("conversation_session", selected["id"], {"assistance_mode": "QUIET"})
    report2 = mod.inspect_pilot_sessions(Path(store.DB_PATH))
    row2 = next(item for item in report2["sessions"] if item["session_id"] == selected["id"])
    assert row2["frozen_pack_verified"] is False
    assert "FROZEN_SESSION_PACK_INTEGRITY_FAILED" in row2["structural_blockers"]


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

    cohort_snapshot_path = data["workspace"] / "selected-cohort.snapshot.json"
    original_cohort_snapshot = cohort_snapshot_path.read_bytes()
    cohort_snapshot_path.write_bytes(original_cohort_snapshot + b"\n")
    dummy_for_snapshot = tmp_path / "dummy-snapshot-review.jsonl"
    dummy_for_snapshot.write_text(
        json.dumps({
            "kind": "continue",
            "session_id": data["project_session"]["id"],
            "space_id": data["project"]["id"],
            "profile": "PROJECT_SYNC",
            "reviewer": "independent-snapshot-check",
            "label_source": "INDEPENDENT_HUMAN_REVIEW",
            "writeback_accurate": True,
        }) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="selected-cohort.snapshot.json"):
        mod.evaluate_workspace(data["workspace"], [dummy_for_snapshot])
    cohort_snapshot_path.write_bytes(original_cohort_snapshot)

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
