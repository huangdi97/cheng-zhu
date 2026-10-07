"""Conversation v2 packaged runtime smoke.

Runs the real built Chengzhu backend sidecar against an isolated CHENGZHU_HOME
and exercises the Conversation Profile through HTTP only.

This complements scripts/packaged_smoke.py instead of replacing it:
- packaged_smoke.py protects the stable Interview package contract
- conversation_packaged_smoke.py proves the additive v2 Conversation runtime

Hosted Windows runners are not reliable audio-hardware evidence. This script
therefore proves the full NOTES_ONLY product loop and records audio capture as
an explicit external hardware evidence gap rather than fabricating it.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

from packaged_smoke import SMOKE_NONCE, free_port, http_json, start, stop, wait_ready


ROOT = Path(__file__).resolve().parents[1]


def expected_product_schema() -> int | None:
    source = (ROOT / "backend" / "services" / "storage" / "product_migrations.py").read_text(encoding="utf-8")
    match = re.search(r"^LATEST_SCHEMA_VERSION\s*=\s*(\d+)", source, re.MULTILINE)
    return int(match.group(1)) if match else None


def post(base: str, path: str, body: dict | None = None) -> dict:
    return http_json(f"{base}{path}", "POST", body or {})


def get(base: str, path: str) -> dict:
    return http_json(f"{base}{path}")


def main() -> int:
    # GitHub Windows runners commonly expose a cp1252 console. Evidence
    # payloads contain Chinese product text; console encoding must never turn a
    # successful packaged runtime check into a false failure.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--frontend-dist", default="")
    ap.add_argument("--report", default="")
    ap.add_argument("--resources", default="")
    args = ap.parse_args()

    exe = Path(args.exe).resolve()
    home = Path(tempfile.mkdtemp(prefix="chengzhu-v2-conversation-packaged-"))
    (home / "config").mkdir(parents=True, exist_ok=True)
    # Deterministic Conversation runtime does not need a remote model. Keep STT
    # explicitly local so Processing=LOCAL has no remote path in Preflight.
    (home / "config" / "config.json").write_text(
        json.dumps({
            "stt_provider": "whisper",
            "doubao_stt_api_key": "",
            "doubao_stt_access_token": "",
            "candidate_stt_provider": "whisper",
            "candidate_remote_stt_enabled": False,
            "share_privacy_mode": "OFF",
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    proc = None
    checks: dict[str, object] = {}
    result: dict[str, object] = {
        "contract": "v2.0-R1",
        "evidence_type": "PACKAGED_CONVERSATION_RUNTIME_SMOKE",
        "exe": str(exe),
        "checks": checks,
        "external_evidence_gaps": {
            "real_audio_capture": "NOT_PROVEN_ON_HOSTED_WINDOWS_RUNNER",
            "real_human_conversation": "REAL_CONVERSATION_USER_EVIDENCE_PENDING",
            "pmf": "PMF_PROVEN_FALSE",
        },
    }
    ok = True

    try:
        proc = start(exe, port, home, args.frontend_dist)
        checks["cold_start_seconds"] = round(wait_ready(base, 120), 2)
        instance = get(base, "/api/instance")
        checks["instance_nonce_echo"] = instance.get("app") == "chengzhu" and instance.get("nonce") == SMOKE_NONCE
        ok &= bool(checks["instance_nonce_echo"])

        diag0 = get(base, "/api/product/conversation/diagnostics")
        expected_schema = expected_product_schema()
        checks["contract"] = diag0.get("contract")
        checks["product_schema_version"] = diag0.get("schema_version")
        checks["product_schema_expected"] = expected_schema
        checks["product_database_available"] = diag0.get("health", {}).get("database") == "AVAILABLE"
        ok &= (
            checks["contract"] == "v2.0-R1"
            and expected_schema is not None
            and diag0.get("schema_version") == expected_schema
            and bool(checks["product_database_available"])
        )

        templates = get(base, "/api/product/conversation/templates").get("items", [])
        profile_keys = {str(item.get("key") or "") for item in templates}
        checks["templates"] = sorted(profile_keys)
        checks["launch_templates_present"] = {"PROJECT_SYNC", "DESIGN_REVIEW"} <= profile_keys
        ok &= bool(checks["launch_templates_present"])

        space = post(base, "/api/product/conversation/spaces", {
            "title": "Packaged · Architecture Sync",
            "profile": "PROJECT_SYNC",
            "description": "Conversation packaged evidence",
            "default_goal": "决定 offline migration rollout",
        })
        space_id = str(space["id"])
        checks["space_id"] = space_id

        goal = post(base, f"/api/product/conversation/spaces/{space_id}/goals", {
            "title": "明确 rollout owner 与 rollback 条件",
            "outcome_definition": "Decision、owner、next step 都有来源",
            "priority": 90,
        })
        participant = post(base, f"/api/product/conversation/spaces/{space_id}/participants", {
            "display_name": "Alex",
            "role": "Backend",
            "explicit_priority": "迁移稳定性",
            "explicit_concern": "rollback 风险",
            "decision_authority": "架构方案批准人",
            "relationship_context": "项目后端负责人",
            "source_refs": [{"kind": "USER_INPUT", "excerpt": "用户明确录入 packaged evidence"}],
        })
        checks["counterparty_explicit_state"] = (
            participant.get("counterparty_state", {}).get("known_explicit", {}).get("priority") == "迁移稳定性"
        )
        ok &= bool(checks["counterparty_explicit_state"])

        prior = post(base, f"/api/product/conversation/spaces/{space_id}/sessions", {
            "title": "Prior Decision",
            "capture_mode": "NOTES_ONLY",
            "processing_mode": "LOCAL",
            "assistance_mode": "BALANCED",
            "consent_ack": False,
        })
        prior_id = str(prior["id"])
        preflight_prior = get(base, f"/api/product/conversation/sessions/{prior_id}/preflight")
        checks["prior_preflight_blockers"] = preflight_prior.get("blockers")
        ok &= preflight_prior.get("blockers") == []
        post(base, f"/api/product/conversation/sessions/{prior_id}/start")

        decision = post(base, f"/api/product/conversation/sessions/{prior_id}/items", {
            "item_type": "Decision",
            "title": "offline migration 采用 v2",
            "source_refs": [{
                "kind": "USER_NOTE",
                "excerpt": "明确决定 offline migration 使用 v2",
                "visibility": "PRIVATE",
            }],
            "source_excerpt": "明确决定 offline migration 使用 v2",
            "epistemic_status": "OBSERVED",
        })
        decision = post(base, f"/api/product/conversation/items/{decision['id']}/review", {
            "action": "CONFIRM",
            "patch": {},
        })
        checks["decision_agreed"] = decision.get("state") == "AGREED" and decision.get("review_status") == "USER_CONFIRMED"
        ok &= bool(checks["decision_agreed"])

        open_question = post(base, f"/api/product/conversation/sessions/{prior_id}/items", {
            "item_type": "OpenQuestion",
            "title": "谁负责 rollback drill？",
            "source_refs": [{
                "kind": "USER_NOTE",
                "excerpt": "rollback owner 尚未确认",
                "visibility": "PRIVATE",
            }],
            "source_excerpt": "rollback owner 尚未确认",
            "epistemic_status": "OBSERVED",
        })
        open_question = post(base, f"/api/product/conversation/items/{open_question['id']}/review", {
            "action": "CONFIRM",
            "patch": {},
        })
        post(base, f"/api/product/conversation/sessions/{prior_id}/end")

        detail = get(base, f"/api/product/conversation/spaces/{space_id}")
        open_threads = detail.get("threads") or []
        checks["reviewed_open_thread_projected"] = any(
            thread.get("text") == "谁负责 rollback drill？" and thread.get("status") == "OPEN"
            for thread in open_threads
        )
        ok &= bool(checks["reviewed_open_thread_projected"])

        live = post(base, f"/api/product/conversation/spaces/{space_id}/sessions", {
            "title": "Packaged Live",
            "goal_ids": [goal["id"]],
            "capture_mode": "NOTES_ONLY",
            "processing_mode": "LOCAL",
            "assistance_mode": "BALANCED",
            "consent_ack": False,
            "policy": {
                "ai_assistance": "AI_ALLOWED",
                "human_assistance": "HUMAN_PRACTICE_ONLY",
                "screen_context": "OFF",
                "share_privacy": "OFF",
                "external_writeback": "REVIEW_REQUIRED",
                "participant_consent_status": "NOT_APPLICABLE",
                "participant_transparency_plan": "NOT_APPLICABLE",
            },
        })
        live_id = str(live["id"])
        preflight = get(base, f"/api/product/conversation/sessions/{live_id}/preflight")
        checks["preflight_blockers"] = preflight.get("blockers")
        checks["preflight_data_path"] = preflight.get("processing_runtime")
        checks["preflight_pack_preview_confirmed"] = preflight.get("pack_preview", {}).get("confirmed_items_count")
        checks["preflight_pack_preview_threads"] = len(preflight.get("pack_preview", {}).get("open_threads") or [])
        ok &= preflight.get("blockers") == []
        ok &= preflight.get("processing_runtime", {}).get("mode") == "LOCAL"
        ok &= preflight.get("processing_runtime", {}).get("main_audio_remote_possible") is False

        started = post(base, f"/api/product/conversation/sessions/{live_id}/start")
        pack = started.get("pack") or {}
        pack_payload = pack.get("payload") or {}
        digest = str(pack.get("digest") or "")
        checks["pack_digest"] = digest
        checks["pack_contract"] = pack_payload.get("contract")
        checks["pack_goal_frozen"] = goal["id"] in (pack_payload.get("goal_ids") or [])
        checks["pack_confirmed_decision"] = any(
            item.get("id") == decision["id"] and item.get("state") == "AGREED"
            for item in pack_payload.get("confirmed_items") or []
        )
        checks["pack_open_thread"] = any(
            thread.get("text") == "谁负责 rollback drill？"
            for thread in (pack_payload.get("session_brief") or {}).get("open_threads") or []
        )
        ok &= bool(digest)
        ok &= checks["pack_contract"] == "v2.0-R1"
        ok &= bool(checks["pack_goal_frozen"])
        ok &= bool(checks["pack_confirmed_decision"])
        ok &= bool(checks["pack_open_thread"])

        context = get(base, f"/api/product/conversation/sessions/{live_id}/context")
        checks["session_context_digest_matches"] = context.get("pack_digest") == digest
        checks["session_context_data_path"] = context.get("processing_runtime")
        checks["session_context_open_threads"] = (context.get("brief") or {}).get("open_threads") or []
        ok &= bool(checks["session_context_digest_matches"])

        ask = post(base, f"/api/product/conversation/sessions/{live_id}/ask", {
            "question": "offline migration v2",
        })
        checks["manual_ask_grounded"] = ask.get("grounded") is True
        checks["manual_ask_truth_confirmed"] = ask.get("truth_confirmed") is True
        checks["manual_ask_top_authority"] = ((ask.get("matches") or [{}])[0]).get("authority")
        ok &= bool(checks["manual_ask_grounded"])
        ok &= bool(checks["manual_ask_truth_confirmed"])
        ok &= checks["manual_ask_top_authority"] == "CONFIRMED_TRUTH"

        guidance = post(base, f"/api/product/conversation/sessions/{live_id}/guidance/evaluate", {
            "direct_question": "为什么之前选择 v2？",
            "answer_cue": "先直接回答，再引用已确认 Decision。",
            "source_refs": decision.get("source_refs") or [],
            "audience_role": "Backend",
            "audience_priority": "迁移稳定性",
            "audience_concern": "rollback 风险",
            "decision_authority": "架构方案批准人",
            "relationship_context": "项目后端负责人",
        })
        event = guidance.get("guidance") or {}
        checks["direct_question_guidance_kind"] = event.get("kind")
        checks["direct_question_guidance_reason"] = event.get("reason")
        ok &= event.get("kind") == "ANSWER_CUE"
        ok &= event.get("reason") == "DIRECT_QUESTION"

        silent = post(base, f"/api/product/conversation/sessions/{live_id}/guidance/evaluate", {
            "candidate_text": "应该补充一个 benchmark",
            "source_refs": [{"kind": "USER_NOTE", "excerpt": "source", "visibility": "PRIVATE"}],
            "user_speaking": True,
            "relevance": 1,
            "novelty": 1,
            "provenance_strength": 1,
        })
        checks["silent_when_user_speaking"] = silent.get("suppressed") == "USER_SPEAKING"
        ok &= bool(checks["silent_when_user_speaking"])

        capture_status = get(base, f"/api/product/conversation/sessions/{live_id}/capture")
        checks["capture_status_available"] = capture_status.get("mode") == "IDLE"
        checks["capture_hardware_execution"] = "NOT_PROVEN_ON_HOSTED_WINDOWS_RUNNER"
        ok &= bool(checks["capture_status_available"])

        ended = post(base, f"/api/product/conversation/sessions/{live_id}/end")
        checks["continue_next_focus"] = ended.get("next_focus")
        checks["continue_review_required"] = ended.get("review_required")
        checks["continue_contains_prior_truth"] = any(
            item.get("title") == "offline migration 采用 v2"
            for item in ended.get("decisions") or []
        )
        # The prior confirmed Decision belongs to the prior Session, so Continue
        # should not pretend it changed in this live Session.
        ok &= checks["continue_contains_prior_truth"] is False

        draft = post(base, f"/api/product/conversation/sessions/{live_id}/draft-actions", {
            "kind": "FOLLOW_UP_EMAIL",
            "title": "Local review-only follow-up",
            "content": "本地草稿，不代表已发送。",
            "source_refs": decision.get("source_refs") or [],
            "payload": {"execution": "LOCAL_REVIEW_ONLY", "external_execution": False},
        })
        approved = post(base, f"/api/product/conversation/draft-actions/{draft['id']}/review", {"action": "APPROVE"})
        checks["draft_approved_locally"] = approved.get("status") == "APPROVED"
        checks["draft_external_execution_false"] = (approved.get("payload") or {}).get("external_execution") is False
        ok &= bool(checks["draft_approved_locally"]) and bool(checks["draft_external_execution_false"])

        history = get(base, "/api/product/conversation/history?limit=20").get("items") or []
        checks["history_contains_live_session"] = any(item.get("id") == live_id for item in history)
        ok &= bool(checks["history_contains_live_session"])

        exported = get(base, f"/api/product/conversation/spaces/{space_id}/export")
        checks["export_kind"] = exported.get("kind")
        checks["export_has_packs"] = bool(exported.get("session_packs"))
        checks["export_has_open_threads"] = bool(exported.get("open_threads"))
        ok &= exported.get("kind") == "CONVERSATION_SPACE"
        ok &= bool(checks["export_has_packs"])

        retention = get(base, f"/api/product/conversation/spaces/{space_id}/retention")
        checks["retention_preview_available"] = retention.get("space_id") == space_id
        ok &= bool(checks["retention_preview_available"])

        diag = get(base, "/api/product/conversation/diagnostics")
        checks["diagnostics_runtime"] = diag.get("runtime")
        checks["diagnostics_evidence"] = diag.get("evidence")
        checks["diagnostics_real_user_pending"] = (
            diag.get("evidence", {}).get("real_conversation_user_evidence")
            == "REAL_CONVERSATION_USER_EVIDENCE_PENDING"
        )
        ok &= bool(checks["diagnostics_real_user_pending"])

        # Restart the packaged sidecar against the same isolated home and prove
        # Conversation persistence is not source-tree-only.
        stop(proc)
        proc = start(exe, port, home, args.frontend_dist)
        checks["restart_seconds"] = round(wait_ready(base, 120), 2)
        after_space = get(base, f"/api/product/conversation/spaces/{space_id}")
        after_history = get(base, "/api/product/conversation/history?limit=20").get("items") or []
        after_context = get(base, f"/api/product/conversation/sessions/{live_id}/context")
        checks["space_persisted_after_restart"] = after_space.get("id") == space_id
        checks["history_persisted_after_restart"] = any(item.get("id") == live_id for item in after_history)
        checks["pack_digest_persisted_after_restart"] = after_context.get("pack_digest") == digest
        ok &= bool(checks["space_persisted_after_restart"])
        ok &= bool(checks["history_persisted_after_restart"])
        ok &= bool(checks["pack_digest_persisted_after_restart"])

        product_db = home / "data" / "product.db"
        product_user_version = (
            sqlite3.connect(product_db).execute("PRAGMA user_version").fetchone()[0]
            if product_db.exists() else None
        )
        checks["product_db_user_version"] = product_user_version
        ok &= expected_schema is not None and product_user_version == expected_schema

        if args.frontend_dist:
            checks["frontend_dist_present"] = Path(args.frontend_dist).resolve().is_dir()
            ok &= bool(checks["frontend_dist_present"])
        if args.resources:
            resources = Path(args.resources)
            checks["resources_present"] = resources.is_dir()
            ok &= bool(checks["resources_present"])

    except Exception as exc:  # noqa: BLE001
        checks["error"] = f"{type(exc).__name__}: {exc}"
        ok = False
    finally:
        if proc is not None:
            try:
                stop(proc)
            except Exception:  # noqa: BLE001
                pass

    result["passed"] = bool(ok)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    # Persist the evidence before writing it to the human-facing console so a
    # terminal encoding problem can never erase the machine-readable report.
    if args.report:
        report = Path(args.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(rendered, encoding="utf-8")
    print(rendered)
    shutil.rmtree(home, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
