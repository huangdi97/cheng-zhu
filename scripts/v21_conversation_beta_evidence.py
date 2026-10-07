#!/usr/bin/env python3
"""Generate deterministic Chengzhu v2.1 Conversation Beta engineering evidence.

This artifact proves local runtime/evaluation plumbing only. It deliberately
does NOT claim real-user usefulness, precision, cognitive-load reduction, or
PMF.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import core.config as config_module  # noqa: E402
from services.product import conversations  # noqa: E402
from services.storage import intelligence as intel_storage  # noqa: E402
from services.storage import product  # noqa: E402
from services.storage.product_migrations import LATEST_SCHEMA_VERSION  # noqa: E402


def _configure(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    product.DB_PATH = str(root / "product.db")
    intel_storage.DB_PATH = str(root / "intelligence.db")
    product._READY_PATHS.clear()  # noqa: SLF001
    product._COLUMNS_CACHE.clear()  # noqa: SLF001
    config_module._save_config = lambda cfg: True  # type: ignore[assignment]  # noqa: ARG005, SLF001
    config_module._config = config_module._raw_config().model_copy(deep=True)  # noqa: SLF001
    config_module._effective = None  # noqa: SLF001
    intel_storage.init_db()
    product.init_db()
    config_module.clear_session_overlay()


def _run() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="chengzhu-v21-conversation-") as td:
        _configure(Path(td))

        space = conversations.create_space(
            "v2.1 Beta Evidence",
            "PROJECT_SYNC",
            default_goal="验证 local dogfood evidence contract",
        )
        session = conversations.create_session(
            space["id"],
            title="Synthetic Project Sync",
            capture_mode="NOTES_ONLY",
            processing_mode="LOCAL",
            assistance_mode="BALANCED",
            consent_ack=True,
            policy={
                "ai_assistance": "AI_ALLOWED",
                "external_writeback": "REVIEW_REQUIRED",
                "participant_consent_status": "NOT_APPLICABLE",
                "participant_transparency_plan": "NOT_APPLICABLE",
            },
        )
        preflight = conversations.preflight(session["id"])
        started = conversations.start_session(session["id"])

        guidance = conversations.evaluate_guidance(session["id"], {
            "direct_question": "为什么要保留 provenance？",
            "source_refs": [{"kind": "USER_NOTE", "excerpt": "synthetic evidence", "visibility": "PRIVATE"}],
        })["guidance"]
        useful = conversations.record_guidance_feedback(
            guidance["id"], "USEFUL", "synthetic label: useful"
        )
        late = conversations.record_guidance_feedback(
            guidance["id"], "TOO_LATE", "synthetic label: too late"
        )
        missed = conversations.record_missed_moment(
            session["id"],
            "SHOULD_HAVE_SURFACED_SOURCE",
            "synthetic missed moment",
            current_topic="provenance",
            source_refs=[{"kind": "USER_NOTE", "excerpt": "synthetic missed source"}],
        )

        ended = conversations.end_session(session["id"])
        reuse = conversations.record_session_feedback(
            session["id"], "WOULD_REUSE_SPACE", "synthetic outcome label"
        )
        helped = conversations.record_session_feedback(
            session["id"], "CONTINUE_HELPED_NEXT_PREP", "synthetic outcome label"
        )

        before_retention = conversations.evaluation_export(space["id"])
        diagnostics = conversations.diagnostics()
        exported_space = conversations.export_space(space["id"])

        conversations.update_space(space["id"], {
            "retention_policy": {
                "preset": "CUSTOM",
                "transcript_days": 30,
                "guidance_days": 0,
                "draft_days": 30,
                "confirmed_items": "KEEP",
                "audio_retention": "OFF",
            }
        })
        retention_preview = conversations.retention_preview(space["id"])
        retention_result = conversations.apply_retention(space["id"], confirm=True)
        after_retention = conversations.evaluation_export(space["id"])

        feedback_rows = conversations.feedback_events(session_id=session["id"])
        guidance_labels_after = [
            row for row in feedback_rows
            if row["kind"] == "GUIDANCE_QUALITY"
        ]

        checks = {
            "schema_v6": product.schema_version() == LATEST_SCHEMA_VERSION == 6,
            "preflight_clear": not preflight["blockers"],
            "session_pack_frozen": bool(started["pack"]["digest"]),
            "guidance_shown": bool(guidance and guidance["id"]),
            "guidance_human_labels_recorded": {
                useful["label"], late["label"]
            } == {"USEFUL", "TOO_LATE"},
            "missed_moment_recorded": missed["kind"] == "MISSED_MOMENT",
            "session_ended": ended["session"]["status"] == "ENDED",
            "session_outcomes_recorded": {
                reuse["label"], helped["label"]
            } == {"WOULD_REUSE_SPACE", "CONTINUE_HELPED_NEXT_PREP"},
            "evaluation_export_local_only": (
                before_retention["contract"] == "v2.1-R1"
                and before_retention["evidence_boundary"]["remote_telemetry"] is False
                and before_retention["evidence_boundary"]["human_labels"] is True
            ),
            "five_explicit_feedback_events": before_retention["summary"]["feedback_events"] == 5,
            "space_export_separates_feedback": (
                "feedback" in exported_space["export_manifest"]["categories"]
                and len(exported_space["feedback"]) == 5
            ),
            "retention_declares_feedback_kept": (
                retention_preview["kept"]["dogfood_feedback"]
                == "KEEP_UNTIL_SESSION_OR_SPACE_DELETE"
            ),
            "guidance_retention_executed": retention_result["deleted"]["guidance_events"] >= 1,
            "feedback_survives_guidance_retention": after_retention["summary"]["feedback_events"] == 5,
            "retained_guidance_labels_detached_safely": (
                len(guidance_labels_after) == 2
                and all(row["guidance_id"] is None for row in guidance_labels_after)
            ),
            "diagnostics_separate_human_labels": (
                diagnostics["evaluation"]["human_label_ledger"]["total"] == 5
                and "not quality or PMF" in diagnostics["evaluation"]["human_label_ledger"]["interpretation"]
            ),
            "no_remote_feedback_telemetry": diagnostics["privacy"]["remote_feedback_telemetry"] == "OFF",
            "real_user_evidence_still_pending": (
                diagnostics["evidence"]["real_conversation_user_evidence"]
                == "REAL_CONVERSATION_USER_EVIDENCE_PENDING"
            ),
            "pmf_still_false": diagnostics["evidence"]["pmf"] == "PMF_PROVEN_FALSE",
        }
        return {
            "passed": all(bool(value) for value in checks.values()),
            "evidence_type": "SYNTHETIC_CONVERSATION_BETA_ENGINEERING",
            "contract": "v2.1-R1",
            "real_user_evidence": "REAL_CONVERSATION_USER_EVIDENCE_PENDING",
            "pmf": "PMF_PROVEN_FALSE",
            "checks": checks,
            "evaluation_summary": before_retention["summary"],
            "retention": {
                "preview": retention_preview,
                "result": retention_result,
                "after_feedback_events": after_retention["summary"]["feedback_events"],
            },
            "diagnostics_evidence": diagnostics["evidence"],
        }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Chengzhu v2.1 Conversation Beta Engineering Evidence",
        "",
        "> Evidence type: SYNTHETIC_CONVERSATION_BETA_ENGINEERING. This proves deterministic local engineering behavior only; it is not real-user evidence and not PMF proof.",
        "",
        "## Gate summary",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- {'PASS' if value else 'FAIL'}: {key}")
    lines += [
        "",
        "## Explicit evidence boundary",
        "",
        f"- real_user_evidence: {payload['real_user_evidence']}",
        f"- pmf: {payload['pmf']}",
        "- feedback storage: local product.db only",
        "- remote feedback telemetry: OFF",
        "- human labels remain separate from automatic telemetry proxies",
        "",
        "## Evaluation summary",
        "",
        json.dumps(payload["evaluation_summary"], ensure_ascii=False, indent=2),
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=str(ROOT / "artifacts" / "validation"))
    args = parser.parse_args()
    out = Path(args.out_dir)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    payload = _run()
    (out / "v2.1-conversation-beta-engineering.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "V2_1_CONVERSATION_BETA_ENGINEERING.md").write_text(
        _markdown(payload), encoding="utf-8"
    )
    print(json.dumps({
        "ok": payload["passed"],
        "evidence_type": payload["evidence_type"],
        "real_user_evidence": payload["real_user_evidence"],
        "pmf": payload["pmf"],
        "out_dir": str(out),
    }, ensure_ascii=False))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
