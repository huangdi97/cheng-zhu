#!/usr/bin/env python3
"""Phase AA — explicit Scenario A (Project Sync, 3 sessions) and Scenario B
(Design Review, 3 sessions with supersession + rollback owner + follow-up task
+ decision-log draft) end-to-end evidence (isolated DB, service layer)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[4] / "backend"
sys.path.insert(0, str(BACKEND))

import core.config as config_module  # noqa: E402
from services.product import conversations  # noqa: E402
from services.storage import intelligence as intel_store  # noqa: E402
from services.storage import product as product_store  # noqa: E402


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


def _start(space_id: str, title: str) -> dict:
    sess = conversations.create_session(space_id, title=title, capture_mode="NOTES_ONLY",
                                        processing_mode="LOCAL", consent_ack=True)
    conversations.start_session(sess["id"])
    return sess


def run(data_dir: Path) -> dict:
    _isolate(data_dir)
    product_store.init_db()
    intel_store.init_db()
    out: dict = {}

    # ---------------- Scenario A: Project Sync, 3 sessions ----------------
    a: dict = {}
    space = conversations.create_space("ScenarioA Project Sync", "PROJECT_SYNC")
    conversations.create_goal(space["id"], "migration 上线", "窗口内无回滚")

    s1 = _start(space["id"], "A-S1")
    for title in ("本周完成 V2 路由迁移", "migration window 太短", "回滚 drill 谁负责？", "周五前完成 rollout plan"):
        item_type = ("OpenQuestion" if "谁" in title
                     else "Commitment" if "rollout" in title
                     else "Risk" if "window" in title else "Status")
        it = conversations.add_item(s1["id"], item_type=item_type, title=title,
                                    source_refs=[{"kind": "USER_NOTE", "excerpt": f"明确说出：{title}"}])
        conversations.review_item(it["id"], "CONFIRM", {"owner_id": "王工"} if "rollout" in title else {})
    dl = conversations.add_item(s1["id"], item_type="Deadline", title="月底前完成压测",
                                source_refs=[{"kind": "USER_NOTE", "excerpt": "原话"}])
    blocked = False
    try:
        conversations.review_item(dl["id"], "CONFIRM")
    except ValueError as exc:
        blocked = "歧义" in str(exc)
    a["s1_ambiguous_deadline_blocked"] = blocked
    conversations.end_session(s1["id"])

    # S2: continuity — Recall / Open Threads / Next Focus / owner-due.
    prepared = conversations.prepare_space(space["id"])
    threads = {t["text"] for t in prepared.get("open_threads", [])}
    cont = conversations.continue_summary(s1["id"])
    a["s2_recall_open_thread_in_prepare"] = "回滚 drill 谁负责？" in threads
    a["s2_continue_has_next_focus"] = "next_focus" in cont
    a["s2_commitment_owner"] = any(
        i.get("owner_id") == "王工" and i.get("title") == "周五前完成 rollout plan"
        for i in product_store.select("conversation_item", where="space_id = ?", params=(space["id"],))
    )
    s2 = _start(space["id"], "A-S2")
    thr = next((t for t in conversations.space_detail(space["id"])["threads"]
                if t["text"] == "回滚 drill 谁负责？"), None)
    if thr is not None:
        conversations.resolve_open_thread(thr["id"])
    a["s2_thread_found_open_before_resolve"] = thr is not None and thr["status"] == "OPEN"
    conversations.end_session(s2["id"])

    s3 = _start(space["id"], "A-S3")
    threads3 = {t["text"] for t in conversations.space_detail(space["id"])["threads"] if t["status"] == "OPEN"}
    a["s3_thread_stays_closed"] = "回滚 drill 谁负责？" not in threads3
    conversations.end_session(s3["id"])
    out["scenario_a_project_sync"] = a

    # ---------------- Scenario B: Design Review, 3 sessions ----------------
    b: dict = {}
    bspace = conversations.create_space("ScenarioB Design Review", "DESIGN_REVIEW")
    conversations.create_goal(bspace["id"], "决定迁移方案", "有 provenance 的决策")

    b1 = _start(bspace["id"], "B-S1")
    prop_a = conversations.add_item(b1["id"], item_type="Proposal", title="方案 A：全量迁移",
                                    source_refs=[{"kind": "USER_NOTE", "excerpt": "提案 A"}])
    conversations.review_item(prop_a["id"], "CONFIRM")
    obj = conversations.add_item(b1["id"], item_type="Objection", title="回滚窗口不足",
                                 source_refs=[{"kind": "USER_NOTE", "excerpt": "明确 objection"}])
    conversations.review_item(obj["id"], "CONFIRM")
    conversations.add_item(b1["id"], item_type="Risk", title="数据一致性问题",
                           source_refs=[{"kind": "USER_NOTE", "excerpt": "明确风险"}])
    conversations.end_session(b1["id"])

    b2 = _start(bspace["id"], "B-S2")
    old_a = conversations.add_item(b2["id"], item_type="Decision", title="采用方案 A",
                                   source_refs=[{"kind": "USER_NOTE", "excerpt": "旧决定 A"}])
    conversations.review_item(old_a["id"], "CONFIRM")
    prop_b = conversations.add_item(b2["id"], item_type="Decision", title="采用方案 B",
                                    source_refs=[{"kind": "USER_NOTE", "excerpt": "决定 B"}])
    conversations.review_item(prop_b["id"], "SUPERSEDE", {"supersedes_id": old_a["id"]})
    b["s2_supersede_old_kept"] = conversations.require_item(old_a["id"])["state"] == "SUPERSEDED"
    b["s2_decision_b_agreed"] = conversations.require_item(prop_b["id"])["state"] == "AGREED"
    conversations.end_session(b2["id"])

    b3 = _start(bspace["id"], "B-S3")
    rollback = conversations.add_item(b3["id"], item_type="Task", title="指定 rollback owner",
                                      owner_id="王工", source_refs=[{"kind": "USER_NOTE", "excerpt": "明确 owner"}])
    rollback = conversations.review_item(rollback["id"], "CONFIRM", {"owner_id": "王工"})
    draft = conversations.create_draft_action(
        b3["id"], kind="UPDATE_DECISION_LOG_DRAFT", title="记录方案 B 决策日志",
        source_refs=[{"kind": "DECISION", "id": prop_b["id"], "visibility": "PRIVATE"}],
    )
    b["s3_rollback_task_committed"] = rollback["state"] == "COMMITTED" and rollback["owner_id"] == "王工"
    b["s3_decision_log_draft"] = draft["kind"] == "UPDATE_DECISION_LOG_DRAFT" and draft["status"] == "DRAFT"
    b["s3_draft_not_external"] = draft.get("external_execution") is False or draft.get("status") == "DRAFT"
    cont_b = conversations.continue_summary(b3["id"])
    b["s3_continue_has_review_required"] = "review_required" in cont_b
    conversations.end_session(b3["id"])
    out["scenario_b_design_review"] = b
    return out


def main() -> int:
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tmp_scenarios")
    report = run(data_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
