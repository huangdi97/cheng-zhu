#!/usr/bin/env python3
"""Phase I — six Conversation Profile full-loop simulation (local evidence).

For every profile (PROJECT_SYNC / DESIGN_REVIEW / PRESENTATION_QA / ONE_ON_ONE /
CLIENT_CALL / NEGOTIATION):

  Create Space -> Goal -> Participant -> Prepare -> Preflight -> Start -> Live
  (profile semantics + guidance lanes) -> Continue -> second Session continuity.

Project Sync and Design Review run 3 sessions each with explicit cross-session
open-thread closure probes. All runs are service-layer only, against an
isolated temp DB; no network, no real users. Output: JSON report (printed);
assertion failures abort loudly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[4] / "backend"
sys.path.insert(0, str(BACKEND))

import core.config as config_module  # noqa: E402
from services.product import conversations  # noqa: E402
from services.storage import product as product_store  # noqa: E402
from services.storage import intelligence as intel_store  # noqa: E402

PROFILES = ["PROJECT_SYNC", "DESIGN_REVIEW", "PRESENTATION_QA", "ONE_ON_ONE", "CLIENT_CALL", "NEGOTIATION"]

PROFILE_LANES = {
    "PROJECT_SYNC": {"RECALL", "QUESTION", "RISK", "CONTRIBUTION_OPPORTUNITY"},
    "DESIGN_REVIEW": {"RECALL", "TALKING_POINT", "QUESTION", "RISK", "CONTRIBUTION_OPPORTUNITY"},
    "PRESENTATION_QA": {"ANSWER_CUE", "RECALL", "QUESTION", "DELIVERY"},
    "ONE_ON_ONE": {"RECALL", "QUESTION", "TALKING_POINT"},
    "CLIENT_CALL": {"RECALL", "ANSWER_CUE", "QUESTION", "RISK", "CONTRIBUTION_OPPORTUNITY"},
    "NEGOTIATION": {"RECALL", "TALKING_POINT", "QUESTION", "RISK"},
}

THREAD_ITEM_TYPES = {"OpenQuestion", "Risk", "Objection"}
NO_INFER_KEYS = ("emotion", "personality", "hidden", "intent", "motivation", "bottom_line", "sentiment")


def _isolate(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    product_store.DB_PATH = str(data_dir / "product.db")
    intel_store.DB_PATH = str(data_dir / "intelligence.db")
    for cache in ("_READY_PATHS", "_COLUMNS_CACHE"):
        if hasattr(product_store, cache):
            getattr(product_store, cache).clear()
    config_module._save_config = lambda cfg: True
    config_module._config = config_module._raw_config().model_copy(deep=True)
    config_module._config.stt_provider = "whisper"
    config_module._config.doubao_stt_api_key = ""
    config_module._config.doubao_stt_access_token = ""
    config_module._config.candidate_stt_provider = "whisper"
    config_module._config.candidate_remote_stt_enabled = False
    config_module._effective = None


def _dump_no_infer(d: dict, skip_keys: set[str], prefix: str = "") -> list[str]:
    hits: list[str] = []
    for k, v in (d or {}).items():
        if k in skip_keys:
            continue
        if any(tag in k.lower() for tag in NO_INFER_KEYS):
            hits.append(f"{prefix}{k}")
        if isinstance(v, dict):
            hits += _dump_no_infer(v, skip_keys, f"{prefix}{k}.")
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    hits += _dump_no_infer(item, skip_keys, f"{prefix}{k}[{i}].")
    return hits


def _session_flow(
    space: dict,
    goal_id: str,
    session_no: int,
    semantics: list[tuple[str, str, str]],
    guidance: list[dict],
) -> dict:
    session = conversations.create_session(
        space["id"], title=f"{space['profile']} S{session_no}", goal_ids=[goal_id],
        capture_mode="NOTES_ONLY", processing_mode="LOCAL", consent_ack=True,
    )
    prepared = conversations.prepare_space(space["id"])
    pre = conversations.preflight(session["id"])
    started = conversations.start_session(session["id"])
    pack = started["pack"]["payload"]
    policy = conversations._normalize_session_policy(session.get("policy"))
    items = []
    for item_type, title, action in semantics:
        item = conversations.add_item(
            session["id"], item_type=item_type, title=title,
            source_refs=[{"kind": "USER_NOTE", "excerpt": f"明确说出：{title}"}],
        )
        if action:
            patch = {"owner_id": "王工"} if item_type in {"Commitment", "Task"} else {}
            try:
                item = conversations.review_item(item["id"], action, patch)
            except ValueError as exc:
                item = {"id": item["id"], "title": title, "type": item_type, "review_blocked": str(exc)}
        items.append(item)
    guidance_results = []
    for body in guidance:
        guidance_results.append(conversations.evaluate_guidance(session["id"], body))
    cont = conversations.continue_summary(session["id"])
    ended = conversations.end_session(session["id"])
    brief_goals = (pack.get("session_brief") or {}).get("goals") or []
    return {
        "session_id": session["id"],
        "prepare_ok": "open_threads" in prepared,
        "preflight_blockers": [b["key"] for b in pre["blockers"]],
        "pack_frozen_goal": any(g.get("id") == goal_id for g in brief_goals) or goal_id in (pack.get("goal_ids") or []),
        "pack_has_playbook": bool(pack.get("profile_playbook")),
        "pack_has_expression_profile": "expression_profile" in pack,
        "policy_guarantees": {
            k: policy.get(k) for k in ("speaker_biometric_identity", "emotion_sentiment_profiling", "hidden_intent_claims")
        },
        "items": items,
        "guidance": guidance_results,
        "continue_sections": sorted(cont.keys()),
        "ended_status": ended.get("session", {}).get("status"),
    }

def run(data_dir: Path) -> dict:
    _isolate(data_dir)
    product_store.init_db()
    intel_store.init_db()
    report: dict = {"profiles": {}, "global_checks": {}}

    for profile in PROFILES:
        space = conversations.create_space(f"{profile} Space", profile)
        goal = conversations.create_goal(space["id"], f"{profile} Goal", "明确 outcome")
        conversations.add_participant(
            space["id"], display_name="王工", role="CTO", organization="客户",
            explicit_priority="migration stability", explicit_concern="rollback risk",
            decision_authority="architecture approval", relationship_context="customer technical lead",
        )

        if profile == "PROJECT_SYNC":
            semantics = [
                ("Status", "本周已完成 V2 路由迁移", "CONFIRM"),
                ("Risk", "migration window 太短", "CONFIRM"),
                ("OpenQuestion", "回滚 drill 谁来负责？", "CONFIRM"),
                ("Commitment", "周五前完成 rollout plan", "CONFIRM"),
                ("Deadline", "月底前完成压测", "CONFIRM"),  # ambiguous -> must stay blocked
            ]
            guidance_cases = [
                {"candidate_text": "回滚 drill 还未安排负责人", "source_refs": [{"kind": "DECISION", "visibility": "PRIVATE"}],
                 "relevance": 1, "novelty": 1, "provenance_strength": 1},
                {"user_speaking": True, "candidate_text": "我再补充一下细节", "source_refs": []},
            ]
        elif profile == "DESIGN_REVIEW":
            semantics = [
                ("Proposal", "方案 A：全量迁移", "CONFIRM"),
                ("Objection", "回滚窗口不足", "CONFIRM"),
                ("Risk", "数据一致性问题", "CONFIRM"),
                ("Assumption", "下游已支持新协议", "CONFIRM"),
            ]
            guidance_cases = [
                {"talking_point": "把证据与 trade-off 放同一屏", "source_refs": [{"kind": "DECISION", "visibility": "PRIVATE"}]},
                {"candidate_text": "回滚 drill 还未安排负责人", "source_refs": [{"kind": "DECISION", "visibility": "PRIVATE"}],
                 "relevance": 1, "novelty": 1, "provenance_strength": 1},
            ]
        elif profile == "PRESENTATION_QA":
            semantics = [
                ("Metric", "Q4 延迟降低 40%", "CONFIRM"),
                ("Status", "已灰度 30% 流量", "CONFIRM"),
                ("OpenQuestion", "回滚触发条件是什么？", "CONFIRM"),
                ("Commitment", "会后提供压测报告", "CONFIRM"),
            ]
            guidance_cases = [
                {"direct_question": "为什么之前选择 v2？", "answer_cue": "先给结论再补证据。",
                 "source_refs": [{"kind": "DECISION", "visibility": "PRIVATE"}]},
                {"delivery_focus": "conclusion first", "source_refs": [],
                 "audience_role": "CTO", "audience_priority": "migration stability",
                 "audience_concern": "rollback risk", "decision_authority": "architecture approval"},
                {"talking_point": "不该出现的 lane", "source_refs": [{"kind": "DECISION", "visibility": "PRIVATE"}]},
            ]
        elif profile == "ONE_ON_ONE":
            semantics = [
                ("Commitment", "本周内给出评估", "CONFIRM"),
                ("OpenQuestion", "你担心的 blocker 是什么？", "CONFIRM"),
                ("Status", "招聘流程已同步", "CONFIRM"),
                ("Risk", "依赖尚未对齐", "CONFIRM"),
            ]
            guidance_cases = [
                {"talking_point": "明确对方 concern 的回应", "source_refs": [{"kind": "DECISION", "visibility": "PRIVATE"}]},
                {"delivery_focus": "conclusion first", "source_refs": []},
                {"critical_risk": "对方明确告知合规风险", "source_refs": [{"kind": "DECISION", "visibility": "PRIVATE"}]},
            ]
        elif profile == "CLIENT_CALL":
            semantics = [
                ("OpenQuestion", "客户明确问：迁移时长多久？", "CONFIRM"),
                ("Commitment", "我们承诺周五前答复", "CONFIRM"),
                ("Risk", "客户明确提到合规风险", "CONFIRM"),
                ("Decision", "采用按库分批迁移", "CONFIRM"),
            ]
            guidance_cases = [
                {"direct_question": "迁移会影响我的服务吗？", "answer_cue": "先回答影响范围。",
                 "source_refs": [{"kind": "DECISION", "visibility": "PRIVATE"}]},
                {"candidate_text": "主动补充一个客户未问的新事实", "source_refs": [{"kind": "DECISION", "visibility": "PRIVATE"}],
                 "relevance": 1, "novelty": 1, "provenance_strength": 1},
            ]
        else:  # NEGOTIATION
            semantics = [
                ("Proposal", "我方提出 3 个月授权期", "CONFIRM"),
                ("Objection", "对方明确拒绝该期限", "CONFIRM"),
                ("Risk", "上线窗口冲突", "CONFIRM"),
                ("Decision", "暂不签长期协议", "CONFIRM"),
            ]
            guidance_cases = [
                {"candidate_text": "主动提示某个新事实", "source_refs": [{"kind": "DECISION", "visibility": "PRIVATE"}],
                 "relevance": 1, "novelty": 1, "provenance_strength": 1, "social_risk": 2.0},
                {"direct_question": "你们最低能接受什么期限？", "source_refs": [{"kind": "DECISION", "visibility": "PRIVATE"}]},
            ]

        sessions_count = 3 if profile in {"PROJECT_SYNC", "DESIGN_REVIEW"} else 2
        sessions = []
        for no in range(1, sessions_count + 1):
            sessions.append(_session_flow(space, goal["id"], no, semantics, guidance_cases))

        # Continuity probes for Project Sync / Design Review.
        cont_checks: dict = {}
        if profile in {"PROJECT_SYNC", "DESIGN_REVIEW"}:
            # Thread-capable item confirmed in session 1 must project into the
            # next prepare as an OPEN thread with the same text.
            s1_confirmed_thread_items = [
                i for i in sessions[0]["items"]
                if i.get("type") in THREAD_ITEM_TYPES and i.get("review_status") == "USER_CONFIRMED"
            ]
            first_text = (s1_confirmed_thread_items[0].get("title") or "") if s1_confirmed_thread_items else ""
            probe_after_s1 = {
                t["text"] for t in conversations.prepare_space(space["id"])["open_threads"]
            }
            cont_checks["session1_thread_projects_to_next_prepare"] = first_text in probe_after_s1
            # Resolve it by id; that exact thread must never show as OPEN again,
            # even though later sessions may create a *different* thread row
            # with the same text (correct longitudinal behaviour).
            thread = next(
                (t for t in conversations.space_detail(space["id"])["threads"] if t.get("text") == first_text), None
            )
            if thread is not None:
                resolved = conversations.resolve_open_thread(thread["id"])
                cont_checks["resolved_status"] = resolved.get("status")
                cont_checks["resolved_thread_closed_for_next_prepare"] = not any(
                    t["id"] == thread["id"] and t["status"] == "OPEN"
                    for t in conversations.space_detail(space["id"])["threads"]
                )
            else:
                cont_checks["resolved_status"] = "NOT_FOUND"
                cont_checks["resolved_thread_closed_for_next_prepare"] = False
            cont_checks["thread_text_probed"] = first_text
        else:
            cont_checks["second_session_prepare_ok"] = "open_threads" in conversations.prepare_space(space["id"])

        # No emotion / personality / hidden-intent on persisted data surfaces
        # (policy keys excluded: they are the explicit OFF guarantees).
        detail = conversations.space_detail(space["id"])
        skip = {"policy"}
        no_infer = {"check": f"{profile}: no emotion/personality/hidden-intent",
                    "pass": not _dump_no_infer(detail, skip),
                    "inferred_keys_found": _dump_no_infer(detail, skip)}

        # Lane bookkeeping.
        suppressed = [
            {"kind": g["event"]["kind"], "reason": g["event"]["reason"]}
            for flow in sessions for g in flow["guidance"]
            if g.get("suppressed") and g.get("event") and g["event"].get("status") == "SUPPRESSED"
        ]
        shown_kinds = {
            g["guidance"]["kind"] for flow in sessions for g in flow["guidance"]
            if g.get("guidance") and g["guidance"].get("status") == "SHOWN"
        }
        lane_checks = {
            "profile": profile,
            "allowed_lanes": sorted(PROFILE_LANES[profile]),
            "suppressed_events": suppressed,
            "shown_kinds": sorted(shown_kinds),
        }

        report["profiles"][profile] = {
            "space": space["id"], "sessions": sessions,
            "continuity": cont_checks, "no_infer": no_infer, "lane_checks": lane_checks,
        }

    # Global invariants.
    for profile, data in report["profiles"].items():
        for shown in data["lane_checks"]["shown_kinds"]:
            if shown in {"ANSWER_CUE", "RISK"}:
                continue  # documented global overrides (Direct Question / Critical Risk)
            assert shown in PROFILE_LANES[profile], f"{profile} leaked lane {shown}"
        for flow in data["sessions"]:
            assert flow["policy_guarantees"]["emotion_sentiment_profiling"] == "OFF"
            assert flow["policy_guarantees"]["hidden_intent_claims"] == "OFF"
            assert flow["policy_guarantees"]["speaker_biometric_identity"] == "OFF"
            assert flow["preflight_blockers"] == [], (profile, flow["preflight_blockers"])
            assert flow["pack_frozen_goal"] and flow["pack_has_playbook"] and flow["pack_has_expression_profile"]

    neg_suppressed = [g["suppressed"] for flow in report["profiles"]["NEGOTIATION"]["sessions"] for g in flow["guidance"] if g.get("suppressed")]
    assert "SOCIAL_RISK" in neg_suppressed, neg_suppressed
    pres_suppressed = [g["suppressed"] for flow in report["profiles"]["PRESENTATION_QA"]["sessions"] for g in flow["guidance"] if g.get("suppressed")]
    assert "PROFILE_GUIDANCE_NOT_ALLOWED" in pres_suppressed, pres_suppressed
    o3 = report["profiles"]["ONE_ON_ONE"]
    shown = [g["guidance"]["kind"] for flow in o3["sessions"] for g in flow["guidance"] if g.get("guidance") and g["guidance"]["status"] == "SHOWN"]
    assert "RISK" in shown and "TALKING_POINT" in shown, shown
    sync_items = [i for flow in report["profiles"]["PROJECT_SYNC"]["sessions"] for i in flow["items"]]
    blocked_deadlines = [i for i in sync_items if i.get("review_blocked") and "歧义" in i.get("review_blocked", "")]
    assert blocked_deadlines, "ambiguous deadline must be blocked from reviewed truth"

    report["global_checks"] = {
        "negotiation_social_risk_silent": True,
        "presentation_lane_isolation": True,
        "one_on_one_critical_risk_global_override": True,
        "policy_guarantees_off": True,
        "ambiguous_deadline_blocked": True,
        "profiles_simulated": len(PROFILES),
        "sessions_total": sum(len(p["sessions"]) for p in report["profiles"].values()),
    }
    return report


def main() -> int:
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tmp_phase_i")
    report = run(data_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
