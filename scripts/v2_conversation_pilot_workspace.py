#!/usr/bin/env python3
"""Create and evaluate a local Chengzhu Conversation real-pilot workspace.

This is an operator workflow orchestrator, not a new evidence source.

It composes the existing v2 tools while preserving their boundaries:
- init: freeze a privacy-sensitive local review workspace for explicitly chosen
  Sessions only;
- finalize: revalidate the same Session cohort against product.db and require
  explicit operator attestations;
- evaluate: combine explicit self-report + supplied human-review files, then
  run the frozen Stable Promotion policy.

Nothing here verifies real-user identity, real-world authorization, participant
consent or PMF. No files are uploaded. Existing workspaces/results are never
silently overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_CONTRACT = "v2.0-R1-pilot-workspace-2"
MIN_PRODUCT_SCHEMA = 12
DEFAULT_POLICY = ROOT / "docs" / "evals" / "V2_CONVERSATION_STABLE_PROMOTION_POLICY.json"


def _load_script(module_name: str, filename: str):
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper script: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


label_seed = _load_script("chengzhu_v2_label_seed", "v2_conversation_label_seed.py")
feedback_export = _load_script("chengzhu_v2_feedback_export", "v2_conversation_feedback_export.py")
human_eval = _load_script("chengzhu_v2_human_eval", "v2_conversation_human_eval.py")
pilot_manifest = _load_script("chengzhu_v2_pilot_manifest", "v2_conversation_pilot_manifest.py")
stable_readiness = _load_script("chengzhu_v2_stable_readiness", "v2_conversation_stable_readiness.py")


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _schema_version(db: Path) -> int:
    if not db.is_file():
        raise FileNotFoundError(db)
    conn = sqlite3.connect(str(db))
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


def _finite_optional_timestamp(value: Any) -> float | None:
    if type(value) not in (int, float):
        return None
    number = float(value)
    return number if math.isfinite(number) and number > 0 else None


def _iso_optional(value: float | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")


SELECTED_COHORT_SNAPSHOT_CONTRACT = "v2.0-R1-selected-cohort-snapshot-1"


def _canonical_json_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _selected_cohort_snapshot(
    db: Path,
    assignments: Iterable[tuple[str, str]],
) -> dict[str, Any]:
    """Freeze privacy-minimized logical facts for selected pilot Sessions.

    product.db uses SQLite WAL, so hashing only the main database file is not a
    complete logical-state fingerprint.  The shared manifest validator proves
    Session/Pack structural consistency and pack content digest without
    exporting private Pack payload.
    """
    pairs = [(str(session_id), str(user_ref)) for session_id, user_ref in assignments]
    if not pairs:
        raise ValueError("selected cohort snapshot requires at least one Session")
    ids = [session_id for session_id, _ in pairs]
    if len(ids) != len(set(ids)):
        raise ValueError("selected cohort snapshot contains duplicate session_id")

    facts = pilot_manifest.validated_session_facts(db, ids)
    sessions: list[dict[str, Any]] = []
    for session_id, user_ref in pairs:
        sessions.append({
            **facts[session_id],
            "user_ref": user_ref,
        })
    sessions.sort(key=lambda row: row["session_id"])
    return {
        "contract_version": SELECTED_COHORT_SNAPSHOT_CONTRACT,
        "sessions": sessions,
    }

def inspect_pilot_sessions(db: Path) -> dict[str, Any]:
    """Return privacy-minimized structural inventory for pilot cohort selection.

    This intentionally exports no Session title, Space title, participant,
    transcript, Guidance text, source excerpt or user_ref. It answers only:
    "which local Session IDs are structurally selectable by the cohort builder?"
    Authorization and identity remain explicit operator responsibilities.
    """
    db = Path(db)
    schema = _schema_version(db)
    if schema < MIN_PRODUCT_SCHEMA:
        raise ValueError(
            f"product.db schema v{schema} is too old for Stable pilot evidence; "
            f"require >= v{MIN_PRODUCT_SCHEMA}"
        )

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        required = {
            "conversation_session",
            "conversation_session_pack",
            "conversation_human_feedback",
        }
        if not required <= tables:
            missing = sorted(required - tables)
            raise ValueError("product.db 缺少 pilot inspection schema: " + ", ".join(missing))

        session_rows = conn.execute(
            "SELECT s.id, s.space_id, s.template, s.status, s.started_at, s.ended_at, "
            "s.capture_mode, s.processing_mode, s.assistance_mode, "
            "s.consent_ack, s.pack_id, p.id AS frozen_pack_id, "
            "p.digest AS frozen_pack_digest, p.payload_json AS frozen_pack_payload_json "
            "FROM conversation_session s "
            "LEFT JOIN conversation_session_pack p "
            "ON p.id = s.pack_id AND p.session_id = s.id AND p.space_id = s.space_id "
            "ORDER BY COALESCE(s.ended_at, s.started_at, s.created_at) DESC, s.id"
        ).fetchall()
        feedback_rows = conn.execute(
            "SELECT session_id, kind, labels_json "
            "FROM conversation_human_feedback "
            "WHERE reviewer_kind = 'SELF_USER'"
        ).fetchall()
    finally:
        conn.close()

    feedback: dict[str, dict[str, Any]] = {}
    for row in feedback_rows:
        session_id = str(row["session_id"])
        bucket = feedback.setdefault(session_id, {
            "rows": 0,
            "guidance_rows": 0,
            "silence_rows": 0,
            "continue_labels": {},
            "outcome_labels": {},
        })
        bucket["rows"] += 1
        kind = str(row["kind"] or "").upper()
        try:
            labels = json.loads(str(row["labels_json"] or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            labels = {}
        if not isinstance(labels, dict):
            labels = {}
        if kind == "GUIDANCE":
            bucket["guidance_rows"] += 1
        elif kind == "SILENCE":
            bucket["silence_rows"] += 1
        elif kind == "CONTINUE":
            bucket["continue_labels"] = labels
        elif kind == "SESSION_OUTCOME":
            bucket["outcome_labels"] = labels

    sessions: list[dict[str, Any]] = []
    profile_summary: dict[str, dict[str, int]] = {
        profile: {
            "sessions": 0,
            "structurally_selectable": 0,
            "quick_debrief_complete": 0,
        }
        for profile in pilot_manifest.REQUIRED_PROFILES
    }

    for row in session_rows:
        session_id = str(row["id"])
        profile = str(row["template"] or "").upper()
        status = str(row["status"] or "").upper()
        started_at = _finite_optional_timestamp(row["started_at"])
        ended_at = _finite_optional_timestamp(row["ended_at"])
        consent_ack_recorded = bool(row["consent_ack"])
        pack_id = str(row["pack_id"] or "").strip()
        frozen_pack_verified = False
        try:
            frozen_fact = pilot_manifest.validated_session_fact(dict(row), session_id)
            frozen_pack_verified = True
            profile = str(frozen_fact.get("profile") or profile).upper()
        except ValueError:
            frozen_fact = {}
        blockers: list[str] = []
        if profile not in pilot_manifest.REQUIRED_PROFILES:
            blockers.append("PROFILE_NOT_LAUNCH_COHORT")
        if status != "ENDED":
            blockers.append("SESSION_NOT_ENDED")
        if not consent_ack_recorded:
            blockers.append("CONSENT_ACK_NOT_RECORDED")
        if not frozen_pack_verified:
            blockers.append("FROZEN_SESSION_PACK_INTEGRITY_FAILED")
        if started_at is None:
            blockers.append("STARTED_AT_INVALID")
        if ended_at is None:
            blockers.append("ENDED_AT_INVALID")
        if started_at is not None and ended_at is not None and ended_at < started_at:
            blockers.append("ENDED_BEFORE_STARTED")

        local_feedback = feedback.get(session_id) or {
            "rows": 0,
            "guidance_rows": 0,
            "silence_rows": 0,
            "continue_labels": {},
            "outcome_labels": {},
        }
        continue_labels = local_feedback["continue_labels"]
        outcome_labels = local_feedback["outcome_labels"]
        quick_fields = {
            "continue_accuracy": isinstance(continue_labels.get("writeback_accurate"), bool),
            "space_reuse_intent": isinstance(outcome_labels.get("would_reuse_space"), bool),
            "cognitive_load_delta": (
                type(outcome_labels.get("cognitive_load_delta")) in (int, float)
                and math.isfinite(float(outcome_labels["cognitive_load_delta"]))
                and -2 <= float(outcome_labels["cognitive_load_delta"]) <= 2
            ),
        }
        quick_completed = sum(1 for value in quick_fields.values() if value)

        item = {
            "session_id": session_id,
            "space_id": str(row["space_id"] or ""),
            "profile": profile,
            "status": status,
            "started_at": _iso_optional(started_at),
            "ended_at": _iso_optional(ended_at),
            "consent_ack_recorded": consent_ack_recorded,
            "frozen_pack_verified": frozen_pack_verified,
            "structurally_selectable": not blockers,
            "structural_blockers": blockers,
            "local_self_report": {
                "explicit_rows": int(local_feedback["rows"]),
                "quick_debrief": {
                    **quick_fields,
                    "completed": quick_completed,
                    "total": 3,
                    "complete": quick_completed == 3,
                },
                "guidance_feedback_rows": int(local_feedback["guidance_rows"]),
                "silence_feedback_rows": int(local_feedback["silence_rows"]),
            },
        }
        sessions.append(item)

        if profile in profile_summary:
            profile_summary[profile]["sessions"] += 1
            if item["structurally_selectable"]:
                profile_summary[profile]["structurally_selectable"] += 1
            if item["local_self_report"]["quick_debrief"]["complete"]:
                profile_summary[profile]["quick_debrief_complete"] += 1

    return {
        "contract_version": WORKSPACE_CONTRACT,
        "inspection_type": "LOCAL_PRIVACY_MINIMIZED_PILOT_SESSION_INVENTORY",
        "product_schema_version": schema,
        "sessions": sessions,
        "summary": {
            "sessions": len(sessions),
            "structurally_selectable": sum(1 for row in sessions if row["structurally_selectable"]),
            "quick_debrief_complete": sum(
                1 for row in sessions
                if row["local_self_report"]["quick_debrief"]["complete"]
            ),
            "profiles": profile_summary,
        },
        "privacy": {
            "session_titles_exported": False,
            "space_titles_exported": False,
            "participants_exported": False,
            "transcript_text_exported": False,
            "guidance_text_exported": False,
            "source_excerpts_exported": False,
            "user_refs_assigned": False,
            "remote_upload": False,
        },
        "claims": {
            "STRUCTURALLY_SELECTABLE_IS_AUTHORIZED_REAL_USE": False,
            "REAL_USER_IDENTITY_SYSTEM_VERIFIED": False,
            "REAL_WORLD_AUTHORIZATION_SYSTEM_VERIFIED": False,
            "PARTICIPANT_CONSENT_SYSTEM_VERIFIED": False,
            "REAL_USER_VALIDATED": False,
            "V2_STABLE_RELEASE": False,
            "PMF_PROVEN": False,
        },
        "interpretation": (
            "This inventory exposes machine-verifiable local Session structure only. "
            "structurally_selectable means the manifest builder can accept the Session "
            "after the operator explicitly supplies a local pseudonymous user_ref; it "
            "does not prove identity, authorization, participant consent, real-world use or PMF."
        ),
    }


def _require_hash(path: Path, expected: str, label: str) -> None:
    actual = _sha256(path)
    if not expected or actual != expected:
        raise ValueError(
            f"{label} hash drift detected; preserve the old workspace and create a new one instead of mutating frozen evidence inputs"
        )


def _json_load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]], headers: Iterable[str]) -> int:
    count = 0
    with path.open("x", encoding="utf-8") as fh:
        for header in headers:
            fh.write(f"# {header}\n")
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def _assignments_from_manifest(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    assignments: list[tuple[str, str]] = []
    for profile in pilot_manifest.REQUIRED_PROFILES:
        block = (manifest.get("profiles") or {}).get(profile) or {}
        for row in block.get("sessions") or []:
            session_id = str(row.get("session_id") or "").strip()
            user_ref = str(row.get("user_ref") or "").strip()
            if not session_id or not user_ref:
                raise ValueError("draft manifest contains an incomplete Session/user_ref mapping")
            assignments.append((session_id, user_ref))
    if not assignments:
        raise ValueError("draft manifest contains no selected Sessions")
    if len({session_id for session_id, _ in assignments}) != len(assignments):
        raise ValueError("draft manifest contains duplicate session_id")
    return assignments


def _policy_contract_check(policy: dict[str, Any]) -> None:
    if str(policy.get("pilot_manifest_contract_version") or "") != pilot_manifest.CONTRACT_VERSION:
        raise ValueError("pilot manifest builder contract does not match the frozen workspace policy")
    if int(policy.get("cross_session_space_min_sessions") or 0) != pilot_manifest.CROSS_SESSION_SPACE_MIN_SESSIONS:
        raise ValueError("cross-session Space minimum does not match the frozen workspace policy")
    required = tuple(str(value) for value in (policy.get("required_attestations") or []))
    if set(required) != set(pilot_manifest.REQUIRED_ATTESTATIONS):
        raise ValueError("pilot attestation vocabulary does not match the frozen workspace policy")


def _workspace_readme() -> str:
    return """# Chengzhu v2 Real Pilot Workspace

This directory is **local evidence workspace**, not a release artifact and not proof of PMF.

## Files

- `workspace.json`: provenance for this workspace; contains hashes, counts and claim boundaries.
- `selected-cohort.snapshot.json`: privacy-minimized logical snapshot of selected Session structure + Frozen Session Pack identity/digest.
- `stable-promotion-policy.json`: the exact policy snapshot frozen when the workspace was initialized.
- `pilot-manifest.draft.json`: DB-derived cohort structure. It is intentionally not Stable-eligible.
- `independent-review.seed.jsonl`: privacy-sensitive review queue. It may contain transcript/source excerpts.
- `self-report.jsonl`: explicit in-product self-report labels only.
- `pilot-manifest.final.json`: created only by the explicit `finalize` step.
- `evaluation/`: created only by the explicit `evaluate` step.

## Required flow

1. Review `pilot-manifest.draft.json` and the selected Session/user pseudonym mapping.
2. Have independent reviewers fill a copy of `independent-review.seed.jsonl`.
   Use `label_source=INDEPENDENT_HUMAN_REVIEW` where required by policy.
3. Keep raw labels and review seeds local. Do not commit them to a public repository.
4. Finalize only after you can truthfully make every required operator attestation.
5. Evaluate with the finalized manifest plus independent-review file(s).

The workspace tool never verifies human identity, real-world authorization, participant consent or PMF.
A Stable Gate PASS only permits a separate stable-release review.
"""


def init_workspace(
    db: Path,
    assignments: Iterable[tuple[str, str]],
    out_dir: Path,
    *,
    policy_path: Path = DEFAULT_POLICY,
) -> dict[str, Any]:
    db = Path(db)
    out_dir = Path(out_dir)
    policy_path = Path(policy_path)
    if out_dir.exists():
        raise FileExistsError(f"workspace already exists: {out_dir}")
    schema = _schema_version(db)
    if schema < MIN_PRODUCT_SCHEMA:
        raise ValueError(
            f"product.db schema v{schema} is too old for Stable pilot evidence; "
            f"require >= v{MIN_PRODUCT_SCHEMA}"
        )
    policy = _json_load(policy_path)
    _policy_contract_check(policy)

    pairs = list(assignments)
    draft_manifest, cohort_summary = pilot_manifest.build_manifest(
        db,
        pairs,
        finalize=False,
    )
    selected_snapshot = _selected_cohort_snapshot(db, pairs)
    selected_ids = {session_id for session_id, _ in pairs}

    seed_rows = [
        row for row in label_seed.export_rows(db)
        if str(row.get("session_id") or "") in selected_ids
    ]
    self_report_rows = [
        row for row in feedback_export.export_rows(db)
        if str(row.get("session_id") or "") in selected_ids
    ]

    temp_dir = out_dir.with_name(out_dir.name + ".tmp")
    if temp_dir.exists():
        raise FileExistsError(f"temporary workspace already exists: {temp_dir}")
    temp_dir.parent.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir()
    try:
        policy_out = temp_dir / "stable-promotion-policy.json"
        # Keep the exact policy bytes, not a reserialized equivalent, so the
        # workspace hash is a byte-for-byte provenance anchor.
        shutil.copyfile(policy_path, policy_out)
        draft_out = temp_dir / "pilot-manifest.draft.json"
        _write_json(draft_out, draft_manifest)
        cohort_snapshot_out = temp_dir / "selected-cohort.snapshot.json"
        _write_json(cohort_snapshot_out, selected_snapshot)
        seed_out = temp_dir / "independent-review.seed.jsonl"
        seed_count = _write_jsonl(
            seed_out,
            seed_rows,
            (
                "UNLABELED INDEPENDENT REVIEW SEED — private local material; not evidence until reviewed.",
                "Do not overwrite this seed in-place; make a reviewer-specific copy.",
            ),
        )
        feedback_out = temp_dir / "self-report.jsonl"
        feedback_count = _write_jsonl(
            feedback_out,
            self_report_rows,
            (
                "LOCAL EXPLICIT SELF-REPORT — not verified identity or real-use authorization.",
                "Stable eligibility is metric-specific and enforced by the frozen policy.",
            ),
        )
        (temp_dir / "README.md").write_text(_workspace_readme(), encoding="utf-8")

        metadata = {
            "contract_version": WORKSPACE_CONTRACT,
            "created_at": _utc_now(),
            "evidence_type": "LOCAL_OPERATOR_WORKSPACE_NOT_EVIDENCE",
            "source": {
                "database_filename": db.name,
                "database_file_sha256_advisory": _sha256(db),
                "database_file_sha256_includes_wal": False,
                "logical_state_anchor": "selected-cohort.snapshot.json",
                "product_schema_version": schema,
            },
            "policy": {
                "policy_version": policy.get("policy_version"),
                "sha256": _sha256(policy_out),
                "pilot_manifest_contract_version": policy.get("pilot_manifest_contract_version"),
            },
            "cohort": cohort_summary,
            "selected_session_ids": sorted(selected_ids),
            "outputs": {
                "selected_cohort_snapshot": {
                    "path": cohort_snapshot_out.name,
                    "sha256": _sha256(cohort_snapshot_out),
                    "logical_sha256": _canonical_json_sha256(selected_snapshot),
                    "sessions": len(selected_snapshot["sessions"]),
                },
                "pilot_manifest_draft": {
                    "path": draft_out.name,
                    "sha256": _sha256(draft_out),
                },
                "independent_review_seed": {
                    "path": seed_out.name,
                    "sha256": _sha256(seed_out),
                    "rows": seed_count,
                },
                "self_report": {
                    "path": feedback_out.name,
                    "sha256": _sha256(feedback_out),
                    "rows": feedback_count,
                },
            },
            "privacy": {
                "remote_upload": False,
                "raw_review_material_must_remain_local": True,
                "absolute_source_db_path_recorded": False,
            },
            "claims": {
                "AUTHORIZED_REAL_USE_SYSTEM_VERIFIED": False,
                "REAL_USER_VALIDATED": False,
                "PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW": False,
                "V2_STABLE_RELEASE": False,
                "PMF_PROVEN": False,
            },
        }
        _write_json(temp_dir / "workspace.json", metadata)
        temp_dir.replace(out_dir)
        return metadata
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def finalize_workspace(
    db: Path,
    workspace: Path,
    *,
    attestations: Iterable[str],
    critical_incidents: int,
) -> dict[str, Any]:
    db = Path(db)
    workspace = Path(workspace)
    if not workspace.is_dir():
        raise FileNotFoundError(workspace)
    metadata = _json_load(workspace / "workspace.json")
    if metadata.get("contract_version") != WORKSPACE_CONTRACT:
        raise ValueError("unsupported pilot workspace contract")
    policy_path = workspace / "stable-promotion-policy.json"
    policy = _json_load(policy_path)
    _require_hash(
        policy_path,
        str((metadata.get("policy") or {}).get("sha256") or ""),
        "stable-promotion-policy.json",
    )
    _policy_contract_check(policy)
    draft_path = workspace / "pilot-manifest.draft.json"
    draft_meta = (metadata.get("outputs") or {}).get("pilot_manifest_draft") or {}
    _require_hash(
        draft_path,
        str(draft_meta.get("sha256") or ""),
        "pilot-manifest.draft.json",
    )
    draft = _json_load(draft_path)
    if draft.get("evidence_type") != pilot_manifest.DRAFT_EVIDENCE_TYPE:
        raise ValueError("workspace draft manifest is not fail-closed")
    assignments = _assignments_from_manifest(draft)

    cohort_snapshot_path = workspace / "selected-cohort.snapshot.json"
    cohort_snapshot_meta = (metadata.get("outputs") or {}).get("selected_cohort_snapshot") or {}
    _require_hash(
        cohort_snapshot_path,
        str(cohort_snapshot_meta.get("sha256") or ""),
        "selected-cohort.snapshot.json",
    )
    frozen_cohort_snapshot = _json_load(cohort_snapshot_path)
    if (
        frozen_cohort_snapshot.get("contract_version")
        != SELECTED_COHORT_SNAPSHOT_CONTRACT
    ):
        raise ValueError("unsupported selected cohort snapshot contract")
    live_cohort_snapshot = _selected_cohort_snapshot(db, assignments)
    if live_cohort_snapshot != frozen_cohort_snapshot:
        raise ValueError(
            "selected cohort structural drift detected; preserve the old workspace "
            "and create a new one instead of finalizing changed Session/Pack facts"
        )

    final_path = workspace / "pilot-manifest.final.json"
    finalization_path = workspace / "finalization.json"
    if final_path.exists() or finalization_path.exists():
        raise FileExistsError("workspace has already been finalized; create a new workspace to change cohort/attestations")

    final_manifest, cohort_summary = pilot_manifest.build_manifest(
        db,
        assignments,
        finalize=True,
        attestations=attestations,
        critical_incidents=critical_incidents,
    )

    # Close the check-then-use window between the pre-finalization cohort
    # revalidation above and build_manifest()'s independent live-DB read.
    # If any selected Session/Frozen Pack changed while the final manifest was
    # being built, do not persist a manifest from a different logical cohort
    # than selected-cohort.snapshot.json.
    post_manifest_cohort_snapshot = _selected_cohort_snapshot(db, assignments)
    if post_manifest_cohort_snapshot != frozen_cohort_snapshot:
        raise ValueError(
            "selected cohort structural drift detected during final manifest build; "
            "no final evidence was written"
        )

    _write_json(final_path, final_manifest)
    finalization = {
        "contract_version": WORKSPACE_CONTRACT,
        "finalized_at": _utc_now(),
        "source_database_filename": db.name,
        "source_database_file_sha256_advisory": _sha256(db),
        "selected_cohort_snapshot_sha256": _sha256(cohort_snapshot_path),
        "selected_cohort_logical_sha256": _canonical_json_sha256(frozen_cohort_snapshot),
        "draft_manifest_sha256": _sha256(draft_path),
        "final_manifest_sha256": _sha256(final_path),
        "policy_sha256": _sha256(workspace / "stable-promotion-policy.json"),
        "cohort": cohort_summary,
        "attestations_are_operator_declarations": True,
        "real_user_identity_system_verified": False,
        "real_world_authorization_system_verified": False,
        "participant_consent_system_verified": False,
        "pmf_proven": False,
    }
    _write_json(finalization_path, finalization)
    return finalization


def evaluate_workspace(
    workspace: Path,
    review_paths: Iterable[Path],
) -> dict[str, Any]:
    workspace = Path(workspace)
    if not workspace.is_dir():
        raise FileNotFoundError(workspace)
    metadata = _json_load(workspace / "workspace.json")
    if metadata.get("contract_version") != WORKSPACE_CONTRACT:
        raise ValueError("unsupported pilot workspace contract")

    final_manifest_path = workspace / "pilot-manifest.final.json"
    if not final_manifest_path.is_file():
        raise ValueError("workspace is not finalized; pilot-manifest.final.json is required")
    finalization_path = workspace / "finalization.json"
    if not finalization_path.is_file():
        raise ValueError("workspace is missing finalization.json provenance")
    finalization = _json_load(finalization_path)
    policy_path = workspace / "stable-promotion-policy.json"
    self_report_path = workspace / "self-report.jsonl"
    seed_path = workspace / "independent-review.seed.jsonl"
    cohort_snapshot_path = workspace / "selected-cohort.snapshot.json"

    cohort_snapshot_meta = (metadata.get("outputs") or {}).get("selected_cohort_snapshot") or {}
    _require_hash(
        cohort_snapshot_path,
        str(cohort_snapshot_meta.get("sha256") or ""),
        "selected-cohort.snapshot.json",
    )
    _require_hash(
        cohort_snapshot_path,
        str(finalization.get("selected_cohort_snapshot_sha256") or ""),
        "selected-cohort.snapshot.json finalization provenance",
    )
    _require_hash(
        policy_path,
        str((metadata.get("policy") or {}).get("sha256") or ""),
        "stable-promotion-policy.json",
    )
    self_report_meta = (metadata.get("outputs") or {}).get("self_report") or {}
    _require_hash(
        self_report_path,
        str(self_report_meta.get("sha256") or ""),
        "self-report.jsonl",
    )
    _require_hash(
        final_manifest_path,
        str(finalization.get("final_manifest_sha256") or ""),
        "pilot-manifest.final.json",
    )
    _require_hash(
        workspace / "pilot-manifest.draft.json",
        str(finalization.get("draft_manifest_sha256") or ""),
        "pilot-manifest.draft.json",
    )

    reviews = [Path(path) for path in review_paths]
    if not reviews:
        raise ValueError("at least one reviewed human-label JSONL is required")
    for path in reviews:
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.resolve() == seed_path.resolve():
            raise ValueError("the unlabeled seed cannot be used directly as human evidence")

    evaluation_dir = workspace / "evaluation"
    if evaluation_dir.exists():
        raise FileExistsError("evaluation already exists; preserve it and create a new workspace for a rerun")
    temp_dir = workspace / "evaluation.tmp"
    if temp_dir.exists():
        raise FileExistsError("temporary evaluation directory already exists")
    temp_dir.mkdir()
    try:
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()
        if self_report_path.is_file():
            rows.extend(human_eval.load_rows(self_report_path, seen=seen))
        for path in reviews:
            rows.extend(human_eval.load_rows(path, seen=seen))

        human_report = human_eval.aggregate(rows)
        human_json = temp_dir / "human-report.json"
        human_md = temp_dir / "human-report.md"
        _write_json(human_json, human_report)
        human_md.write_text(human_eval.markdown(human_report), encoding="utf-8")

        stable_report = stable_readiness.evaluate(
            human_report,
            _json_load(final_manifest_path),
            _json_load(policy_path),
        )
        stable_json = temp_dir / "stable-readiness.json"
        stable_md = temp_dir / "stable-readiness.md"
        _write_json(stable_json, stable_report)
        stable_md.write_text(stable_readiness.markdown(stable_report), encoding="utf-8")

        evaluation_manifest = {
            "contract_version": WORKSPACE_CONTRACT,
            "evaluated_at": _utc_now(),
            "inputs": {
                "selected_cohort_snapshot_sha256": _sha256(cohort_snapshot_path),
                "selected_cohort_logical_sha256": _canonical_json_sha256(
                    _json_load(cohort_snapshot_path)
                ),
                "pilot_manifest_final_sha256": _sha256(final_manifest_path),
                "policy_sha256": _sha256(policy_path),
                "self_report_sha256": _sha256(self_report_path) if self_report_path.is_file() else None,
                "independent_reviews": [
                    {"filename": path.name, "sha256": _sha256(path)}
                    for path in reviews
                ],
            },
            "outputs": {
                "human_report_sha256": _sha256(human_json),
                "stable_readiness_sha256": _sha256(stable_json),
            },
            "status": stable_report.get("status"),
            "claims": stable_report.get("claims"),
            "interpretation": (
                "This evaluation uses the policy snapshot frozen in the workspace. "
                "A PASS permits only a separate stable-release review; it does not publish a release or prove PMF."
            ),
        }
        _write_json(temp_dir / "evaluation-manifest.json", evaluation_manifest)
        temp_dir.replace(evaluation_dir)
        return {
            "human_report": human_report,
            "stable_readiness": stable_report,
            "evaluation_manifest": evaluation_manifest,
        }
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def _parse_cli_assignments(values: Iterable[str]) -> list[tuple[str, str]]:
    return [pilot_manifest.parse_assignment(value) for value in values]


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser(
        "inspect",
        help="list privacy-minimized local Session structure for explicit cohort selection",
    )
    inspect.add_argument("--db", required=True)
    inspect.add_argument(
        "--eligible-only",
        action="store_true",
        help="show only Sessions that pass machine-verifiable structural selection checks",
    )

    init = sub.add_parser("init", help="create a new local pilot workspace")
    init.add_argument("--db", required=True)
    init.add_argument("--session", action="append", default=[], metavar="SESSION_ID=USER_REF")
    init.add_argument("--out-dir", required=True)
    init.add_argument("--policy", default=str(DEFAULT_POLICY))

    finalize = sub.add_parser("finalize", help="explicitly finalize the selected pilot cohort")
    finalize.add_argument("--db", required=True)
    finalize.add_argument("--workspace", required=True)
    finalize.add_argument("--critical-incidents", required=True, type=int)
    finalize.add_argument(
        "--attest",
        action="append",
        default=[],
        choices=pilot_manifest.REQUIRED_ATTESTATIONS,
    )

    evaluate = sub.add_parser("evaluate", help="aggregate labels and run the frozen Stable gate")
    evaluate.add_argument("--workspace", required=True)
    evaluate.add_argument("--review", action="append", default=[])

    args = parser.parse_args()
    try:
        if args.command == "inspect":
            result = inspect_pilot_sessions(Path(args.db))
            if args.eligible_only:
                result = {
                    **result,
                    "sessions": [
                        row for row in result["sessions"]
                        if row["structurally_selectable"]
                    ],
                }
                result["summary"] = {
                    **result["summary"],
                    "displayed_sessions": len(result["sessions"]),
                }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if args.command == "init":
            result = init_workspace(
                Path(args.db),
                _parse_cli_assignments(args.session),
                Path(args.out_dir),
                policy_path=Path(args.policy),
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if args.command == "finalize":
            result = finalize_workspace(
                Path(args.db),
                Path(args.workspace),
                attestations=args.attest,
                critical_incidents=args.critical_incidents,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        result = evaluate_workspace(
            Path(args.workspace),
            [Path(value) for value in args.review],
        )
        print(json.dumps(result["stable_readiness"], ensure_ascii=False, indent=2))
        return 0 if result["stable_readiness"].get("status") != "NO_GO" else 2
    except (FileNotFoundError, FileExistsError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
