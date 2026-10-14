"""Pilot workspace orchestration must reduce operator error without inventing evidence."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from services import build_provenance
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


def _packaged_runtime(runtime_sha: str = "b" * 64) -> dict:
    return {
        "contract_version": "v2.0-R1-build-provenance-1",
        "app_version": "2.0.0-beta.10",
        "source_sha": "a" * 40,
        "release_channel": "PRERELEASE",
        "runtime_fingerprint": {
            "contract_version": "v2.0-R1-runtime-fingerprint-1",
            "sha256": runtime_sha,
            "files": 42,
        },
        "runtime_origin": "PACKAGED_EMBEDDED",
        "claim_boundary": "SOURCE_BUILD_PROVENANCE_NOT_REAL_USER_OR_BEHAVIORAL_EQUIVALENCE_PROOF",
    }


def _ended_session(space_id: str, *, title: str, runtime_sha: str = "b" * 64) -> dict:
    session = conversations.create_session(space_id, title=title, consent_ack=True)
    original = build_provenance.current_build_provenance
    build_provenance.current_build_provenance = lambda: _packaged_runtime(runtime_sha)
    try:
        conversations.start_session(session["id"])
    finally:
        build_provenance.current_build_provenance = original
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
    assert result["source"]["product_schema_version"] >= 13
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
    frozen_policy = json.loads(
        (workspace / "stable-promotion-policy.json").read_text(encoding="utf-8")
    )
    assert frozen_policy["policy_version"] == "v2.0-R1-stable-promotion-8"
    assert frozen_policy["stable_metric_coverage_policy"] == "COMPLETE_FROZEN_ELIGIBLE_POPULATION"
    assert result["policy"]["cross_session_space_user_binding"] == "SINGLE_PSEUDONYMOUS_USER_REF"
    assert result["runtime_baseline"]["contract_version"] == mod.RUNTIME_BASELINE_CONTRACT
    assert result["runtime_baseline"]["runtime_origin"] == "PACKAGED_EMBEDDED"
    assert result["runtime_baseline"]["runtime_fingerprint"]["sha256"] == "b" * 64
    assert result["runtime_baseline"]["sessions"] == 2
    assert result["toolchain"]["contract_version"] == mod.TOOLCHAIN_FINGERPRINT_CONTRACT
    assert result["toolchain"]["workspace_contract"] == mod.WORKSPACE_CONTRACT
    assert result["toolchain"]["human_eval_report_contract"] == mod.human_eval.REPORT_CONTRACT_VERSION
    assert {row["path"] for row in result["toolchain"]["files"]} == set(mod.TOOLCHAIN_RELATIVE_PATHS)
    assert all(len(row["sha256"]) == 64 for row in result["toolchain"]["files"])

    with pytest.raises(FileExistsError, match="workspace already exists"):
        mod.init_workspace(Path(store.DB_PATH), data["assignments"], workspace)


def test_workspace_toolchain_fingerprint_fails_closed_on_drift(product_env, tmp_path):
    mod = _load()
    data = _workspace_fixture(product_env, tmp_path)
    workspace = data["workspace"]
    result = mod.init_workspace(Path(store.DB_PATH), data["assignments"], workspace)
    frozen = result["toolchain"]
    assert frozen == mod._toolchain_fingerprint()

    workspace_path = workspace / "workspace.json"
    metadata = json.loads(workspace_path.read_text(encoding="utf-8"))
    original = json.loads(json.dumps(metadata))
    metadata["toolchain"]["files"][0]["sha256"] = "0" * 64
    workspace_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="toolchain drift"):
        mod.finalize_workspace(
            Path(store.DB_PATH),
            workspace,
            attestations=mod.pilot_manifest.REQUIRED_ATTESTATIONS,
            critical_incidents=0,
        )
    assert not (workspace / "pilot-manifest.final.json").exists()

    workspace_path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")
    finalization = mod.finalize_workspace(
        Path(store.DB_PATH),
        workspace,
        attestations=mod.pilot_manifest.REQUIRED_ATTESTATIONS,
        critical_incidents=0,
    )
    assert finalization["toolchain"] == frozen

    # Evaluation re-checks the same frozen toolchain instead of trusting only
    # the finalization file.
    metadata = json.loads(workspace_path.read_text(encoding="utf-8"))
    metadata["toolchain"]["files"][-1]["sha256"] = "f" * 64
    workspace_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="toolchain drift"):
        mod.evaluate_workspace(workspace, [])


def test_workspace_rejects_policy_that_allows_annotation_count_inflation(product_env, tmp_path):
    mod = _load()
    data = _workspace_fixture(product_env, tmp_path)
    policy = json.loads(mod.DEFAULT_POLICY.read_text(encoding="utf-8"))

    weak_sample = dict(policy)
    weak_sample["metric_sample_unit"] = "ANNOTATION_ROWS"
    weak_path = tmp_path / "weak-sample-policy.json"
    weak_path.write_text(json.dumps(weak_sample), encoding="utf-8")
    with pytest.raises(ValueError, match="UNIQUE_EVENT_PER_METRIC"):
        mod.init_workspace(
            Path(store.DB_PATH),
            data["assignments"],
            tmp_path / "weak-sample-workspace",
            policy_path=weak_path,
        )

    weak_duplicate = dict(policy)
    weak_duplicate["duplicate_event_metric_policy"] = "ALLOW"
    weak_duplicate_path = tmp_path / "weak-duplicate-policy.json"
    weak_duplicate_path.write_text(json.dumps(weak_duplicate), encoding="utf-8")
    with pytest.raises(ValueError, match="FAIL_CLOSED"):
        mod.init_workspace(
            Path(store.DB_PATH),
            data["assignments"],
            tmp_path / "weak-duplicate-workspace",
            policy_path=weak_duplicate_path,
        )

    weak_binding = dict(policy)
    weak_binding["cross_session_space_user_binding"] = "ALLOW_MIXED_USERS"
    weak_binding_path = tmp_path / "weak-space-user-policy.json"
    weak_binding_path.write_text(json.dumps(weak_binding), encoding="utf-8")
    with pytest.raises(ValueError, match="user binding"):
        mod.init_workspace(
            Path(store.DB_PATH),
            data["assignments"],
            tmp_path / "weak-space-user-workspace",
            policy_path=weak_binding_path,
        )


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
    assert project["runtime_baseline_ready"] is True
    assert project["runtime_build"]["runtime_fingerprint_sha256"] == "b" * 64
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


def test_finalize_rechecks_selected_cohort_after_final_manifest_live_db_read(product_env, tmp_path, monkeypatch):
    mod = _load()
    data = _workspace_fixture(product_env, tmp_path)
    workspace = data["workspace"]
    mod.init_workspace(Path(store.DB_PATH), data["assignments"], workspace)

    selected_id = data["project_session"]["id"]
    original = conversations.require_session(selected_id)
    original_ended_at = original["ended_at"]
    real_build = mod.pilot_manifest.build_manifest

    def build_then_drift(*args, **kwargs):
        manifest, summary = real_build(*args, **kwargs)
        # Simulate a selected-cohort mutation after build_manifest has consumed
        # its independent live DB read but before finalize persists evidence.
        store.update(
            "conversation_session",
            selected_id,
            {"ended_at": float(original_ended_at) + 1.0},
        )
        return manifest, summary

    monkeypatch.setattr(mod.pilot_manifest, "build_manifest", build_then_drift)
    with pytest.raises(ValueError, match="during final manifest build"):
        mod.finalize_workspace(
            Path(store.DB_PATH),
            workspace,
            attestations=mod.pilot_manifest.REQUIRED_ATTESTATIONS,
            critical_incidents=0,
        )

    assert not (workspace / "pilot-manifest.final.json").exists()
    assert not (workspace / "finalization.json").exists()

    # Restore the selected cohort and the canonical builder; a clean retry can
    # then finalize the exact frozen workspace.
    store.update(
        "conversation_session",
        selected_id,
        {"ended_at": original_ended_at},
    )
    monkeypatch.setattr(mod.pilot_manifest, "build_manifest", real_build)
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


def test_evaluate_workspace_rejects_invented_or_mutated_independent_review_rows(product_env, tmp_path):
    mod = _load()
    data = _workspace_fixture(product_env, tmp_path)
    mod.init_workspace(Path(store.DB_PATH), data["assignments"], data["workspace"])
    mod.finalize_workspace(
        Path(store.DB_PATH),
        data["workspace"],
        attestations=mod.pilot_manifest.REQUIRED_ATTESTATIONS,
        critical_incidents=0,
    )

    invented = tmp_path / "invented-event.jsonl"
    invented.write_text(
        json.dumps({
            "kind": "direct_question",
            "session_id": data["project_session"]["id"],
            "space_id": data["project"]["id"],
            "profile": "PROJECT_SYNC",
            "event_id": "seg-never-existed",
            "timestamp": 1.0,
            "reviewer": "independent-reviewer-a",
            "label_source": "INDEPENDENT_HUMAN_REVIEW",
            "predicted": True,
            "actual": True,
            "prediction_unavailable": False,
            "system": {
                "channel": "PRIMARY_AUDIO",
                "provider": "fake",
                "source": "fake",
                "text": "fabricated",
                "direct_question_prediction": {
                    "eligible": True,
                    "predicted": True,
                    "detector_version": "heuristic-v1",
                    "channel": "PRIMARY_AUDIO",
                    "ai_assistance": "AI_ALLOWED",
                },
            },
            "notes": "",
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not present in frozen independent-review seed"):
        mod.evaluate_workspace(data["workspace"], [invented])
    assert not (data["workspace"] / "evaluation").exists()

    seed_rows = [
        json.loads(line)
        for line in (data["workspace"] / "independent-review.seed.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    frozen = next(
        row for row in seed_rows
        if row["kind"] == "direct_question"
        and row["event_id"] == "seg-selected-project"
    )
    mutated = dict(frozen)
    mutated["reviewer"] = "independent-reviewer-b"
    mutated["label_source"] = "INDEPENDENT_HUMAN_REVIEW"
    mutated["actual"] = True
    mutated["predicted"] = not frozen["predicted"]

    mutated_path = tmp_path / "mutated-prediction.jsonl"
    mutated_path.write_text(
        json.dumps(mutated, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="immutable seed provenance mismatch"):
        mod.evaluate_workspace(data["workspace"], [mutated_path])
    assert not (data["workspace"] / "evaluation").exists()

    mutated_origin = dict(frozen)
    mutated_origin["reviewer"] = "independent-reviewer-c"
    mutated_origin["label_source"] = "INDEPENDENT_HUMAN_REVIEW"
    mutated_origin["actual"] = True
    mutated_origin["system"] = dict(frozen["system"])
    mutated_origin["system"]["text"] = "rewritten transcript provenance"

    mutated_origin_path = tmp_path / "mutated-origin.jsonl"
    mutated_origin_path.write_text(
        json.dumps(mutated_origin, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="immutable seed provenance mismatch"):
        mod.evaluate_workspace(data["workspace"], [mutated_origin_path])
    assert not (data["workspace"] / "evaluation").exists()


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

    original_seed = seed.read_bytes()
    seed.write_bytes(original_seed + b"\n")
    seed_hash_review = tmp_path / "seed-hash-review.jsonl"
    seed_hash_review.write_text(
        json.dumps({
            "kind": "continue",
            "session_id": data["project_session"]["id"],
            "space_id": data["project"]["id"],
            "profile": "PROJECT_SYNC",
            "reviewer": "independent-seed-hash-check",
            "label_source": "INDEPENDENT_HUMAN_REVIEW",
            "writeback_accurate": True,
            "notes": "",
        }) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="independent-review.seed.jsonl hash drift"):
        mod.evaluate_workspace(data["workspace"], [seed_hash_review])
    seed.write_bytes(original_seed)

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
    assert manifest["contract_version"] == mod.WORKSPACE_CONTRACT
    assert manifest["toolchain"] == mod._toolchain_fingerprint()
    assert manifest["inputs"]["independent_review_seed_sha256"] == mod._sha256(seed)
    assert manifest["inputs"]["independent_review_seed_rows"] > 0
    assert manifest["inputs"]["verified_independent_review_rows"] == 1
    assert manifest["inputs"]["review_seed_binding"] == "EVENT_LEVEL_IMMUTABLE_PROVENANCE_VERIFIED"
    assert manifest["inputs"]["independent_reviews"][0]["filename"] == review.name
    assert str(review.resolve()) not in json.dumps(manifest)

    with pytest.raises(FileExistsError, match="evaluation already exists"):
        mod.evaluate_workspace(data["workspace"], [review])


def test_workspace_stable_metric_coverage_prevents_objective_cherry_picking():
    mod = _load()
    policy = json.loads(mod.DEFAULT_POLICY.read_text(encoding="utf-8"))

    seed_rows = [
        {
            "kind": "direct_question",
            "session_id": "cv-dq",
            "space_id": "cs-dq",
            "profile": "PROJECT_SYNC",
            "event_id": "cts-good",
            "predicted": True,
            "actual": None,
            "reviewer": "",
            "label_source": "",
            "notes": "",
        },
        {
            "kind": "direct_question",
            "session_id": "cv-dq",
            "space_id": "cs-dq",
            "profile": "PROJECT_SYNC",
            "event_id": "cts-bad",
            "predicted": True,
            "actual": None,
            "reviewer": "",
            "label_source": "",
            "notes": "",
        },
        {
            "kind": "continue",
            "session_id": "cv-dq",
            "space_id": "cs-dq",
            "profile": "PROJECT_SYNC",
            "reviewer": "",
            "label_source": "",
            "writeback_accurate": None,
            "notes": "",
        },
    ]
    seed_index = {
        mod._review_seed_key(row): row
        for row in seed_rows
    }

    favorable_subset = [
        {
            **seed_rows[0],
            "reviewer": "independent-a",
            "label_source": "INDEPENDENT_HUMAN_REVIEW",
            "actual": True,
        },
        {
            **seed_rows[2],
            "reviewer": "independent-a",
            "label_source": "INDEPENDENT_HUMAN_REVIEW",
            "writeback_accurate": True,
        },
    ]
    coverage = mod._stable_metric_coverage(seed_index, favorable_subset, policy)
    assert coverage["complete"] is False
    assert coverage["required_event_metric_pairs"] == 5
    assert coverage["covered_event_metric_pairs"] == 3
    assert coverage["missing_event_metric_pairs"] == 2
    assert {
        row["metric"] for row in coverage["missing_examples"]
    } == {"direct_question_precision", "direct_question_recall"}

    complete = favorable_subset + [{
        **seed_rows[1],
        "reviewer": "independent-b",
        "label_source": "INDEPENDENT_HUMAN_REVIEW",
        "actual": False,
    }]
    coverage = mod._stable_metric_coverage(seed_index, complete, policy)
    assert coverage["complete"] is True
    assert coverage["covered_event_metric_pairs"] == coverage["required_event_metric_pairs"] == 5
    assert coverage["missing_event_metric_pairs"] == 0


def test_workspace_stable_metric_coverage_requires_allowed_source_and_non_null_fields():
    mod = _load()
    policy = json.loads(mod.DEFAULT_POLICY.read_text(encoding="utf-8"))
    seed = {
        "kind": "truth_item",
        "session_id": "cv-truth",
        "space_id": "cs-truth",
        "profile": "DESIGN_REVIEW",
        "event_id": "ci-1",
        "predicted_type": "Decision",
        "predicted_state": "AGREED",
        "actual_type": None,
        "actual_state": None,
        "reviewer": "",
        "label_source": "",
        "notes": "",
    }
    seed_index = {mod._review_seed_key(seed): seed}

    wrong_source = [{
        **seed,
        "reviewer": "reviewer-a",
        "label_source": "LOCAL_IN_PRODUCT_EXPLICIT_SELF_REPORT",
        "actual_type": "Decision",
        "actual_state": "AGREED",
    }]
    coverage = mod._stable_metric_coverage(seed_index, wrong_source, policy)
    assert coverage["complete"] is False

    null_state = [{
        **seed,
        "reviewer": "reviewer-a",
        "label_source": "INDEPENDENT_HUMAN_REVIEW",
        "actual_type": "Decision",
        "actual_state": None,
    }]
    coverage = mod._stable_metric_coverage(seed_index, null_state, policy)
    assert coverage["complete"] is False

    valid = [{
        **seed,
        "reviewer": "reviewer-a",
        "label_source": "INDEPENDENT_HUMAN_REVIEW",
        "actual_type": "Decision",
        "actual_state": "AGREED",
    }]
    coverage = mod._stable_metric_coverage(seed_index, valid, policy)
    assert coverage["complete"] is True


def test_workspace_stable_metric_coverage_blocks_self_report_cherry_picking():
    mod = _load()
    policy = json.loads(mod.DEFAULT_POLICY.read_text(encoding="utf-8"))

    seed_rows = [
        {
            "kind": "guidance",
            "session_id": "cv-self",
            "space_id": "cs-self",
            "profile": "PROJECT_SYNC",
            "event_id": "g-1",
            "guidance_class": "PROACTIVE",
            "system": {
                "origin": {
                    "kind": "TRANSCRIPT_AUTO",
                    "transcript_segment_id": "cts-1",
                    "decision_class": "ARBITER",
                },
            },
            "reviewer": "",
            "label_source": "",
            "useful": None,
            "interruption_regret": None,
            "source_correct": None,
            "recall_correct": None,
            "notes": "",
        },
        {
            "kind": "session_outcome",
            "session_id": "cv-self",
            "space_id": "cs-self",
            "profile": "PROJECT_SYNC",
            "reviewer": "",
            "label_source": "",
            "cognitive_load_delta": None,
            "would_reuse_space": None,
            "notes": "",
        },
    ]
    seed_index = {mod._review_seed_key(row): row for row in seed_rows}

    favorable_only = [{
        **seed_rows[0],
        "reviewer": "IN_PRODUCT_SELF_REPORT",
        "label_source": "LOCAL_IN_PRODUCT_EXPLICIT_SELF_REPORT",
        "useful": True,
        "interruption_regret": False,
    }]
    coverage = mod._stable_metric_coverage(seed_index, favorable_only, policy)
    assert coverage["complete"] is False
    assert coverage["required_by_metric"]["interruption_regret"] == 1
    assert coverage["required_by_metric"]["mean_cognitive_load_delta"] == 1
    assert coverage["required_by_metric"]["space_reuse_intent_rate"] == 1
    assert coverage["missing_event_metric_pairs"] >= 3

    completed = favorable_only + [{
        **seed_rows[1],
        "reviewer": "IN_PRODUCT_SELF_REPORT",
        "label_source": "LOCAL_IN_PRODUCT_EXPLICIT_SELF_REPORT",
        "cognitive_load_delta": 1,
        "would_reuse_space": False,
    }, {
        **seed_rows[0],
        "reviewer": "independent-source-check",
        "label_source": "INDEPENDENT_HUMAN_REVIEW",
        "source_correct": False,
    }]
    coverage = mod._stable_metric_coverage(seed_index, completed, policy)
    # opportunity_precision can be satisfied by the self-report useful label,
    # interruption_regret by self-report, source accuracy by independent review,
    # and both session outcomes by self-report.
    assert coverage["complete"] is True
    assert coverage["missing_event_metric_pairs"] == 0


def test_workspace_stable_metric_coverage_rejects_top_level_forged_runtime_origin():
    mod = _load()
    policy = json.loads(mod.DEFAULT_POLICY.read_text(encoding="utf-8"))
    forged = {
        "kind": "guidance",
        "session_id": "cv-forged",
        "space_id": "cs-forged",
        "profile": "PROJECT_SYNC",
        "event_id": "g-forged",
        "guidance_class": "PROACTIVE",
        "runtime_origin": {
            "kind": "TRANSCRIPT_AUTO",
            "transcript_segment_id": "cts-forged",
            "decision_class": "ARBITER",
        },
        "reviewer": "",
        "label_source": "",
        "useful": None,
        "interruption_regret": None,
        "source_correct": None,
        "recall_correct": None,
        "notes": "",
    }
    seed_index = {mod._review_seed_key(forged): forged}
    assert mod._stable_metric_coverage(seed_index, [], policy)["required_event_metric_pairs"] == 0


def test_workspace_stable_metric_coverage_accepts_one_allowed_source_for_multi_source_metric():
    mod = _load()
    policy = json.loads(mod.DEFAULT_POLICY.read_text(encoding="utf-8"))
    seed = {
        "kind": "silence",
        "session_id": "cv-silence",
        "space_id": "cs-silence",
        "profile": "DESIGN_REVIEW",
        "event_id": "g-silent",
        "system": {
            "origin": {
                "kind": "TRANSCRIPT_AUTO",
                "transcript_segment_id": "cts-silent",
                "decision_class": "ARBITER",
            },
        },
        "reviewer": "",
        "label_source": "",
        "silence_correct": None,
        "notes": "",
    }
    seed_index = {mod._review_seed_key(seed): seed}
    self_report = [{
        **seed,
        "reviewer": "IN_PRODUCT_SELF_REPORT",
        "label_source": "LOCAL_IN_PRODUCT_EXPLICIT_SELF_REPORT",
        "silence_correct": False,
    }]
    coverage = mod._stable_metric_coverage(seed_index, self_report, policy)
    assert coverage["complete"] is True
    assert coverage["required_by_metric"] == {"useful_silence_rate": 1}
    assert coverage["covered_by_metric"] == {"useful_silence_rate": 1}


def test_workspace_rejects_pre_v13_or_source_checkout_session_provenance(product_env, tmp_path):
    mod = _load()
    space = conversations.create_space("Historical", "PROJECT_SYNC")
    # This uses the test/source checkout runtime rather than packaged provenance.
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    conversations.end_session(session["id"])

    with pytest.raises(ValueError, match="PACKAGED_EMBEDDED|packaged runtime provenance"):
        mod.init_workspace(
            Path(store.DB_PATH),
            [(session["id"], "pilot-user-historical")],
            tmp_path / "historical-workspace",
        )


def test_workspace_rejects_mixed_packaged_runtime_fingerprints(product_env, tmp_path):
    mod = _load()
    project = conversations.create_space("Runtime A", "PROJECT_SYNC")
    design = conversations.create_space("Runtime B", "DESIGN_REVIEW")
    first = _ended_session(project["id"], title="A", runtime_sha="b" * 64)
    second = _ended_session(design["id"], title="B", runtime_sha="c" * 64)

    with pytest.raises(ValueError, match="different product runtime fingerprints"):
        mod.init_workspace(
            Path(store.DB_PATH),
            [
                (first["id"], "pilot-user-a"),
                (second["id"], "pilot-user-b"),
            ],
            tmp_path / "mixed-runtime-workspace",
        )
