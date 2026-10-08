#!/usr/bin/env python3
"""Generate deterministic Chengzhu v2 Conversation engineering evidence.

This script uses isolated temporary SQLite stores and deterministic local
Conversation services. It is engineering evidence only:

    SYNTHETIC_ENGINEERING_EVIDENCE != REAL_USER_VALIDATION != PMF

The checks intentionally cover the v2 product loop and truth/privacy boundaries
that can be proven without an interactive desktop, external connectors or real
participants.
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
from services.product import conversations, materials, quick_notes  # noqa: E402
from services.storage import intelligence as intel_storage  # noqa: E402
from services.storage import job_tracker, prep_space, product, review  # noqa: E402


def _configure(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    product.DB_PATH = str(root / "product.db")
    intel_storage.DB_PATH = str(root / "intelligence.db")
    prep_space.DB_PATH = str(root / "prep.db")
    review.DB_PATH = str(root / "review.db")
    job_tracker.DB_PATH = str(root / "job_tracker.db")
    product._READY_PATHS.clear()  # noqa: SLF001
    product._COLUMNS_CACHE.clear()  # noqa: SLF001

    config_module._save_config = lambda cfg: True  # type: ignore[assignment]  # noqa: ARG005, SLF001
    config_module._config = config_module._raw_config().model_copy(deep=True)  # noqa: SLF001
    config_module._effective = None  # noqa: SLF001

    import services.product.data_export as data_export_module
    import services.storage.paths as storage_paths

    storage_paths.exports_dir = lambda: str(root)  # type: ignore[assignment]
    data_export_module.exports_dir = lambda: str(root)  # type: ignore[assignment]

    intel_storage.init_db()
    prep_space.init_db()
    review.init_db()
    job_tracker.init_db()
    product.init_db()
    config_module.clear_session_overlay()


def _check(name: str, value: bool, details: Any = None) -> dict[str, Any]:
    return {"name": name, "passed": bool(value), "details": details}


def _run() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="chengzhu-v2-conversation-evidence-") as td:
        root = Path(td)
        _configure(root)
        checks: list[dict[str, Any]] = []

        source = materials.create_material(
            "Q4 Benchmark",
            kind="PROJECT",
            usage="FACTS",
            text=(
                "Q4 benchmark validated offline migration at 10x data scale. "
                "Rollback owner remained unresolved. "
            ) * 4,
        )
        note = quick_notes.create_note(
            "提醒：先确认 rollback owner；这条 Quick Note 不是证据。",
            title="Review reminder",
        )
        space = conversations.create_space(
            "Architecture Review",
            "DESIGN_REVIEW",
            default_goal="决定 offline migration 方案并确认 rollback owner",
            selected_source_ids=[source["id"]],
            selected_quick_note_ids=[note["id"]],
        )
        conversations.add_participant(
            space["id"],
            display_name="Alex",
            role="CTO",
            explicit_priority="迁移稳定性",
            explicit_concern="rollback 风险",
            decision_authority="架构方案批准人",
            relationship_context="客户技术负责人",
            source_refs=[{"kind": "USER_NOTE", "excerpt": "Alex 明确关注 rollback 风险"}],
        )
        session = conversations.create_session(
            space["id"],
            title="Architecture Review #1",
            capture_mode="NOTES_ONLY",
            processing_mode="LOCAL",
            assistance_mode="BALANCED",
            consent_ack=True,
            policy={
                "ai_assistance": "AI_ALLOWED",
                "human_assistance": "HUMAN_PRACTICE_ONLY",
                "screen_context": "OFF",
                "share_privacy": "OFF",
                "external_writeback": "REVIEW_REQUIRED",
                "participant_consent_status": "USER_REPORTS_ALLOWED",
                "participant_transparency_plan": "USER_WILL_NOTIFY_VERBALLY",
            },
        )

        preflight = conversations.preflight(session["id"])
        checks.append(_check("preflight_has_no_blockers", not preflight["blockers"], preflight["blockers"]))
        checks.append(_check(
            "pack_preview_has_ready_source",
            len(preflight["pack_preview"]["sources"]) == 1
            and preflight["pack_preview"]["sources"][0]["material_id"] == source["id"],
        ))
        checks.append(_check(
            "privacy_defaults_are_fail_closed",
            preflight["policy"]["screen_context"] == "OFF"
            and preflight["policy"]["share_privacy"] == "OFF"
            and preflight["policy"]["speaker_biometric_identity"] == "OFF"
            and preflight["policy"]["emotion_sentiment_profiling"] == "OFF"
            and preflight["policy"]["hidden_intent_claims"] == "OFF",
        ))

        started = conversations.start_session(session["id"])
        pack = started["pack"]
        frozen_version = pack["payload"]["sources"][0]["version_id"]
        frozen_digest = pack["digest"]
        checks.append(_check("session_pack_has_digest", bool(frozen_digest), frozen_digest))

        # Mutating a source after Start must never rewrite the frozen Session Pack.
        materials.replace_material(
            source["id"],
            text=("Replacement now claims 50x scale; it must not enter the already-started session. " * 4),
        )
        context_after_replace = conversations.session_context(session["id"])
        checks.append(_check(
            "session_pack_is_immutable_after_source_replace",
            context_after_replace["sources"][0]["version_id"] == frozen_version
            and context_after_replace["pack_digest"] == frozen_digest,
        ))
        frozen_ask = conversations.ask(session["id"], "10x data scale")
        replacement_ask = conversations.ask(session["id"], "50x data scale")
        checks.append(_check(
            "manual_ask_uses_frozen_source_version",
            frozen_ask["grounded"] is True and replacement_ask["grounded"] is False,
            {"frozen": frozen_ask, "replacement": replacement_ask},
        ))

        provenance = [{"kind": "USER_NOTE", "excerpt": "明确决定采用 v2", "visibility": "PRIVATE"}]
        decision = conversations.add_item(
            session["id"],
            item_type="Decision",
            title="offline migration 采用 v2",
            source_refs=provenance,
            epistemic_status="OBSERVED",
        )
        checks.append(_check(
            "model_candidate_is_not_truth",
            decision["state"] == "PROPOSED" and decision["review_status"] == "AI_EXTRACTED",
        ))
        confirmed_decision = conversations.review_item(decision["id"], "CONFIRM")
        checks.append(_check(
            "review_promotes_decision_with_provenance",
            confirmed_decision["state"] == "AGREED"
            and confirmed_decision["review_status"] == "USER_CONFIRMED"
            and bool(confirmed_decision["source_refs"]),
        ))

        question = conversations.add_item(
            session["id"],
            item_type="OpenQuestion",
            title="谁负责 rollback drill？",
            source_refs=[{"kind": "USER_NOTE", "excerpt": "rollback owner 尚未明确", "visibility": "PRIVATE"}],
            epistemic_status="OBSERVED",
        )
        confirmed_question = conversations.review_item(question["id"], "CONFIRM")
        detail = conversations.space_detail(space["id"])
        checks.append(_check(
            "reviewed_open_question_projects_longitudinal_thread",
            confirmed_question["review_status"] == "USER_CONFIRMED"
            and any(t["text"] == question["title"] and t["status"] == "OPEN" for t in detail["threads"]),
        ))

        silent = conversations.evaluate_guidance(session["id"], {
            "candidate_text": "现在插一句 benchmark",
            "source_refs": [{"kind": "DOCUMENT", "id": source["id"], "visibility": "PRIVATE"}],
            "user_speaking": True,
            "relevance": 1,
            "novelty": 1,
            "provenance_strength": 1,
        })
        checks.append(_check(
            "user_speaking_suppresses_proactive_guidance",
            silent["guidance"] is None and silent["suppressed"] == "USER_SPEAKING",
        ))

        direct = conversations.evaluate_guidance(session["id"], {
            "direct_question": "之前为什么用 v2？",
            "source_refs": provenance,
        })
        checks.append(_check(
            "direct_question_has_priority",
            bool(direct["guidance"]) and direct["guidance"]["kind"] == "ANSWER_CUE",
        ))
        conversations.set_guidance_action(direct["guidance"]["id"], "PINNED")

        summary = conversations.end_session(session["id"])
        checks.append(_check(
            "continue_separates_reviewed_truth_and_pins",
            any(x["id"] == decision["id"] for x in summary["decisions"])
            and any(x["id"] == question["id"] for x in summary["open_questions"])
            and any(x["id"] == direct["guidance"]["id"] for x in summary["pins"]),
        ))

        draft = conversations.derived_writeback_draft(session["id"], "UPDATE_DECISION_LOG_DRAFT")
        approved = conversations.review_draft_action(draft["id"], "APPROVE")
        checks.append(_check(
            "reviewed_writeback_stays_local",
            approved["status"] == "APPROVED"
            and approved["payload"].get("external_execution") is False
            and "external_id" not in approved,
        ))

        history = conversations.conversation_history()
        checks.append(_check(
            "conversation_history_is_profile_native",
            bool(history)
            and history[0]["space_id"] == space["id"]
            and history[0]["space_profile"] == "DESIGN_REVIEW",
        ))

        diagnostics = conversations.diagnostics()
        checks.append(_check(
            "diagnostics_keep_real_user_metrics_unclaimed",
            "opportunity_precision" in diagnostics["evaluation"]["requires_human_labels"]
            and "interruption_regret" in diagnostics["evaluation"]["requires_human_labels"]
            and diagnostics["health"]["external_writeback_execution"] == "DRAFT_ONLY_NO_CONNECTOR_EXECUTION",
        ))

        blocked = conversations.create_session(
            space["id"],
            title="Blocked policy proof",
            consent_ack=True,
            policy={
                "screen_context": "MANUAL",
                "share_privacy": "PRIVATE_OVERLAY",
                "human_assistance": "HUMAN_ALLOWED",
                "connector_permissions": ["calendar.read"],
            },
        )
        blocked_preflight = conversations.preflight(blocked["id"])
        blocker_keys = {x["key"] for x in blocked_preflight["blockers"]}
        checks.append(_check(
            "unwired_capabilities_fail_closed",
            {"screen_context_runtime", "share_privacy_runtime", "human_assistance_runtime", "connector_runtime"}
            <= blocker_keys,
            sorted(blocker_keys),
        ))

        passed = all(x["passed"] for x in checks)
        return {
            "evidence_type": "SYNTHETIC_ENGINEERING_EVIDENCE",
            "product": "Chengzhu v2 Conversation Beta",
            "passed": passed,
            "checks": checks,
            "pack_digest": frozen_digest,
            "frozen_source_version": frozen_version,
            "diagnostics": diagnostics,
            "claims": {
                "V2_RUNTIME_AVAILABLE": True,
                "V2_PRODUCTIZED_RELEASE": False,
                "REAL_CONVERSATION_USER_EVIDENCE_PENDING": True,
                "PMF_PROVEN": False,
            },
        }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Chengzhu v2 Conversation Engineering Evidence",
        "",
        "> Evidence type: SYNTHETIC_ENGINEERING_EVIDENCE. This artifact proves deterministic engineering contracts only. It is not real-user validation and not PMF evidence.",
        "",
        "## Gate summary",
        "",
    ]
    for check in payload["checks"]:
        lines.append(f"- {'PASS' if check['passed'] else 'FAIL'} · {check['name']}")
    lines += [
        "",
        "## Frozen evidence",
        "",
        f"- Session Pack digest: `{payload['pack_digest']}`",
        f"- Frozen source version: `{payload['frozen_source_version']}`",
        "",
        "## Evidence boundary",
        "",
        "- V2_RUNTIME_AVAILABLE: TRUE",
        "- V2_PRODUCTIZED_RELEASE: FALSE",
        "- REAL_CONVERSATION_USER_EVIDENCE_PENDING: TRUE",
        "- PMF_PROVEN: FALSE",
        "",
        "Metrics such as Opportunity Precision, Interruption Regret, Useful Silence and real cognitive-load reduction remain human-label / real-user questions.",
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
    (out / "v2-conversation-engineering-evidence.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "V2_CONVERSATION_ENGINEERING_EVIDENCE.md").write_text(
        _markdown(payload), encoding="utf-8"
    )
    print(json.dumps({
        "ok": payload["passed"],
        "evidence_type": payload["evidence_type"],
        "checks": {x["name"]: x["passed"] for x in payload["checks"]},
        "claims": payload["claims"],
        "out_dir": str(out),
    }, ensure_ascii=False))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
