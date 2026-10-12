"""Pilot manifest builder must reduce clerical work without inventing real-user evidence."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from services.product import conversations
from services.storage import product as store


ROOT = Path(__file__).resolve().parents[2]


def _module():
    spec = importlib.util.spec_from_file_location(
        "v2_pilot_manifest_builder",
        ROOT / "scripts" / "v2_conversation_pilot_manifest.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ended_session(profile: str, title: str, monkeypatch, clock: list[float]):
    space = conversations.create_space(title, profile)
    session = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(session["id"])
    clock[0] += 60
    conversations.end_session(session["id"])
    return space, conversations.require_session(session["id"])


def _required_attestations(module):
    return list(module.REQUIRED_ATTESTATIONS)


def test_pilot_manifest_default_is_draft_and_derives_db_truth_without_content(product_env, monkeypatch):
    module = _module()
    clock = [1_800_000_000.0]
    monkeypatch.setattr(store, "now", lambda: clock[0])

    project_space, project = _ended_session("PROJECT_SYNC", "Sensitive Project Title", monkeypatch, clock)
    clock[0] += 60
    design_space, design = _ended_session("DESIGN_REVIEW", "Secret Design Review", monkeypatch, clock)

    store.insert("conversation_transcript_segment", {
        "id": "cts-private-builder",
        "space_id": project_space["id"],
        "session_id": project["id"],
        "channel": "PRIMARY_AUDIO",
        "text": "PRIVATE TRANSCRIPT MUST NOT ENTER MANIFEST",
        "provider": "test",
        "source": "TEST",
        "is_final": True,
        "analysis": {},
        "created_at": clock[0],
    })

    manifest, summary = module.build_manifest(
        Path(store.DB_PATH),
        [
            (project["id"], "pilot-user-01"),
            (design["id"], "pilot-user-02"),
        ],
    )

    assert manifest["contract_version"] == "v2.0-R1-pilot-cohort-2"
    assert manifest["evidence_type"] == "DRAFT_AUTHORIZED_REAL_CONVERSATION_PILOT"
    assert manifest["critical_incidents"] is None
    assert manifest["attestations"] == []
    assert manifest["profiles"]["PROJECT_SYNC"]["sessions"] == [{
        "session_id": project["id"],
        "space_id": project_space["id"],
        "user_ref": "pilot-user-01",
    }]
    assert manifest["profiles"]["DESIGN_REVIEW"]["sessions"] == [{
        "session_id": design["id"],
        "space_id": design_space["id"],
        "user_ref": "pilot-user-02",
    }]
    assert manifest["period"]["started_at"].endswith("Z")
    assert manifest["period"]["ended_at"].endswith("Z")
    serialized = json.dumps(manifest, ensure_ascii=False)
    assert "Sensitive Project Title" not in serialized
    assert "Secret Design Review" not in serialized
    assert "PRIVATE TRANSCRIPT MUST NOT ENTER MANIFEST" not in serialized
    assert summary["real_user_identity_system_verified"] is False
    assert summary["authorization_system_verified"] is False
    assert summary["pmf_proven"] is False


def test_pilot_manifest_finalize_requires_every_explicit_attestation_and_incident_count(product_env, monkeypatch):
    module = _module()
    clock = [1_800_100_000.0]
    monkeypatch.setattr(store, "now", lambda: clock[0])
    _space, session = _ended_session("PROJECT_SYNC", "Pilot", monkeypatch, clock)
    assignment = [(session["id"], "pilot-user-01")]

    with pytest.raises(ValueError, match="finalize 缺少显式 attestation"):
        module.build_manifest(
            Path(store.DB_PATH),
            assignment,
            finalize=True,
            attestations=["AUTHORIZED_REAL_USE"],
            critical_incidents=0,
        )

    with pytest.raises(ValueError, match="critical-incidents|critical_incidents"):
        module.build_manifest(
            Path(store.DB_PATH),
            assignment,
            finalize=True,
            attestations=_required_attestations(module),
            critical_incidents=None,
        )

    manifest, summary = module.build_manifest(
        Path(store.DB_PATH),
        assignment,
        finalize=True,
        attestations=_required_attestations(module),
        critical_incidents=0,
    )
    assert manifest["evidence_type"] == "AUTHORIZED_REAL_CONVERSATION_PILOT"
    assert manifest["critical_incidents"] == 0
    assert manifest["attestations"] == _required_attestations(module)
    assert summary["mode"] == "FINAL"
    assert summary["authorization_system_verified"] is False


def test_pilot_manifest_draft_refuses_attestations_or_incident_claims(product_env, monkeypatch):
    module = _module()
    clock = [1_800_200_000.0]
    monkeypatch.setattr(store, "now", lambda: clock[0])
    _space, session = _ended_session("PROJECT_SYNC", "Pilot", monkeypatch, clock)

    with pytest.raises(ValueError, match="DRAFT"):
        module.build_manifest(
            Path(store.DB_PATH),
            [(session["id"], "pilot-user-01")],
            attestations=["AUTHORIZED_REAL_USE"],
        )
    with pytest.raises(ValueError, match="DRAFT"):
        module.build_manifest(
            Path(store.DB_PATH),
            [(session["id"], "pilot-user-01")],
            critical_incidents=0,
        )


def test_pilot_manifest_rejects_active_unknown_duplicate_and_non_launch_sessions(product_env, monkeypatch):
    module = _module()
    clock = [1_800_300_000.0]
    monkeypatch.setattr(store, "now", lambda: clock[0])

    project_space = conversations.create_space("Active", "PROJECT_SYNC")
    active = conversations.create_session(project_space["id"], consent_ack=True)
    conversations.start_session(active["id"])
    with pytest.raises(ValueError, match="ENDED"):
        module.build_manifest(
            Path(store.DB_PATH),
            [(active["id"], "pilot-user-01")],
        )

    with pytest.raises(ValueError, match="不存在 Session"):
        module.build_manifest(
            Path(store.DB_PATH),
            [("cv-does-not-exist", "pilot-user-01")],
        )

    clock[0] += 60
    conversations.end_session(active["id"])
    with pytest.raises(ValueError, match="重复 session_id"):
        module.build_manifest(
            Path(store.DB_PATH),
            [
                (active["id"], "pilot-user-01"),
                (active["id"], "pilot-user-01"),
            ],
        )

    client_space = conversations.create_space("Client", "CLIENT_CALL")
    client = conversations.create_session(client_space["id"], consent_ack=True)
    conversations.start_session(client["id"])
    clock[0] += 60
    conversations.end_session(client["id"])
    with pytest.raises(ValueError, match="不属于 Stable launch cohort"):
        module.build_manifest(
            Path(store.DB_PATH),
            [(client["id"], "pilot-user-02")],
        )


def test_pilot_manifest_requires_consent_ack_and_frozen_pack_provenance(product_env, monkeypatch):
    module = _module()
    clock = [1_800_350_000.0]
    monkeypatch.setattr(store, "now", lambda: clock[0])

    _space, session = _ended_session("PROJECT_SYNC", "Pilot provenance", monkeypatch, clock)

    store.update("conversation_session", session["id"], {"consent_ack": False})
    with pytest.raises(ValueError, match="consent_ack"):
        module.build_manifest(
            Path(store.DB_PATH),
            [(session["id"], "pilot-user-01")],
        )

    store.update("conversation_session", session["id"], {"consent_ack": True, "pack_id": ""})
    with pytest.raises(ValueError, match="Frozen Session Pack"):
        module.build_manifest(
            Path(store.DB_PATH),
            [(session["id"], "pilot-user-01")],
        )


def test_pilot_manifest_verifies_pack_content_and_frozen_session_context(product_env, monkeypatch):
    module = _module()
    clock = [1_800_375_000.0]
    monkeypatch.setattr(store, "now", lambda: clock[0])

    _space, session = _ended_session("PROJECT_SYNC", "Frozen provenance", monkeypatch, clock)
    session = conversations.require_session(session["id"])
    pack = store.get("conversation_session_pack", session["pack_id"])
    assert pack is not None

    original_payload = pack["payload"]
    original_digest = pack["digest"]

    # Stored digest alone is not trusted: payload bytes/structure must hash to it.
    store.update(
        "conversation_session_pack",
        pack["id"],
        {"payload": {**original_payload, "_tampered_for_test": True}},
    )
    with pytest.raises(ValueError, match="payload digest mismatch"):
        module.build_manifest(
            Path(store.DB_PATH),
            [(session["id"], "pilot-user-01")],
        )
    store.update("conversation_session_pack", pack["id"], {"payload": original_payload})

    store.update("conversation_session_pack", pack["id"], {"digest": "fake-digest"})
    with pytest.raises(ValueError, match="payload digest mismatch"):
        module.build_manifest(
            Path(store.DB_PATH),
            [(session["id"], "pilot-user-01")],
        )
    store.update("conversation_session_pack", pack["id"], {"digest": original_digest})

    # The mutable Session row cannot silently redefine the profile that was
    # frozen at Start Session.
    store.update("conversation_session", session["id"], {"template": "DESIGN_REVIEW"})
    with pytest.raises(ValueError, match="profile"):
        module.build_manifest(
            Path(store.DB_PATH),
            [(session["id"], "pilot-user-01")],
        )
    store.update("conversation_session", session["id"], {"template": "PROJECT_SYNC"})

    manifest, _summary = module.build_manifest(
        Path(store.DB_PATH),
        [(session["id"], "pilot-user-01")],
    )
    assert manifest["profiles"]["PROJECT_SYNC"]["sessions"][0]["session_id"] == session["id"]


def test_pilot_manifest_user_ref_is_pseudonym_shaped_not_email_or_free_text():
    module = _module()
    assert module.parse_assignment("cv_123=pilot-user_01") == ("cv_123", "pilot-user_01")

    for invalid in (
        "cv_123=",
        "cv_123=user@example.com",
        "cv_123=Real Name",
        "no-equals-sign",
    ):
        with pytest.raises(ValueError):
            module.parse_assignment(invalid)

    with pytest.raises(ValueError, match="user_ref"):
        module.build_manifest(
            Path("/definitely/not-used.db"),
            [("cv_123", "user@example.com")],
        )


def test_pilot_manifest_summary_derives_profile_counts_from_selected_sessions(product_env, monkeypatch):
    module = _module()
    clock = [1_800_400_000.0]
    monkeypatch.setattr(store, "now", lambda: clock[0])

    space = conversations.create_space("Repeated Space", "PROJECT_SYNC")
    sessions = []
    for _ in range(2):
        session = conversations.create_session(space["id"], consent_ack=True)
        conversations.start_session(session["id"])
        clock[0] += 30
        conversations.end_session(session["id"])
        sessions.append(conversations.require_session(session["id"]))
        clock[0] += 30

    _manifest, summary = module.build_manifest(
        Path(store.DB_PATH),
        [
            (sessions[0]["id"], "pilot-user-01"),
            (sessions[1]["id"], "pilot-user-01"),
        ],
    )
    assert summary["cross_session_space_min_sessions"] == 3
    assert summary["profiles"]["PROJECT_SYNC"] == {
        "sessions": 2,
        "distinct_pseudonymous_users": 1,
        "cross_session_spaces": 0,
    }

    third = conversations.create_session(space["id"], consent_ack=True)
    conversations.start_session(third["id"])
    clock[0] += 30
    conversations.end_session(third["id"])
    third = conversations.require_session(third["id"])
    _manifest3, summary3 = module.build_manifest(
        Path(store.DB_PATH),
        [
            (sessions[0]["id"], "pilot-user-01"),
            (sessions[1]["id"], "pilot-user-01"),
            (third["id"], "pilot-user-01"),
        ],
    )
    assert summary3["profiles"]["PROJECT_SYNC"]["cross_session_spaces"] == 1
    assert summary["profiles"]["DESIGN_REVIEW"] == {
        "sessions": 0,
        "distinct_pseudonymous_users": 0,
        "cross_session_spaces": 0,
    }


def test_static_pilot_manifest_template_is_fail_closed():
    template = json.loads(
        (ROOT / "docs" / "evals" / "v2_conversation_real_pilot_manifest.template.json")
        .read_text(encoding="utf-8")
    )
    assert template["contract_version"] == "v2.0-R1-pilot-cohort-2"
    assert template["evidence_type"] == "DRAFT_AUTHORIZED_REAL_CONVERSATION_PILOT"
    assert template["critical_incidents"] is None
    assert template["attestations"] == []


def test_pilot_builder_contract_tracks_machine_readable_stable_policy():
    module = _module()
    policy = json.loads(
        (ROOT / "docs" / "evals" / "V2_CONVERSATION_STABLE_PROMOTION_POLICY.json")
        .read_text(encoding="utf-8")
    )
    assert policy["policy_version"] == "v2.0-R1-stable-promotion-6"
    assert module.CONTRACT_VERSION == policy["pilot_manifest_contract_version"]
    assert list(module.REQUIRED_PROFILES) == policy["metric_profiles"]
    assert list(module.REQUIRED_ATTESTATIONS) == policy["required_attestations"]
    assert (
        module.CROSS_SESSION_SPACE_MIN_SESSIONS
        == policy["cross_session_space_min_sessions"]
        == 3
    )
