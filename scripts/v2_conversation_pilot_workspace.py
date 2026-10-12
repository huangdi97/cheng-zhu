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
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_CONTRACT = "v2.0-R1-pilot-workspace-1"
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
                "database_sha256": _sha256(db),
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
    _write_json(final_path, final_manifest)
    finalization = {
        "contract_version": WORKSPACE_CONTRACT,
        "finalized_at": _utc_now(),
        "source_database_filename": db.name,
        "source_database_sha256": _sha256(db),
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
