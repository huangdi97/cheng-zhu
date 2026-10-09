#!/usr/bin/env python3
"""Phase J/K/P — frozen pack, truth/provenance, open threads, derived state,
manual-ask frozen retrieval and expression-profile freeze (local evidence).

Runs against an isolated temp DB via the real service layer. Sections:

  J1  SESSION_PACK_IMMUTABILITY: after start, mutate Space Goal / Material /
      Quick Note / Participant / Expression / Open Thread and prove the frozen
      pack payload is byte-identical and keeps frozen goal, open threads,
      counterparty, expression, playbook, processing route.
  J2  Truth/provenance negatives: AI-extracted != AGREED; COMMITTED needs
      owner+source+review; Deadline needs source; ambiguous times blocked;
      supersession keeps old Decision as SUPERSEDED; quick note / transcript
      stay non-evidence.
  J3  Open Thread lifecycle + 500+ projection + no phantom threads after
      deleting the source session.
  J4  Conversation State is a derived read model; derived views/write-back
      drafts never create new Decision/Commitment/OpenThread.
  K1  Manual Ask authority order + frozen source replacement (10x -> 50x) +
      distinctive token exactness (v2/v3, Q4/Q3, dates).
  P1  Expression profile freeze + delivery cue changes only structure/length/
      delivery, never facts.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[4] / "backend"
sys.path.insert(0, str(BACKEND))

import core.config as config_module  # noqa: E402
from services.product import conversations, materials, quick_notes  # noqa: E402
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


def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _make_material(title: str, text: str) -> str:
    material = materials.create_material(title=title, text=text, background=True)
    version_id = material.get("active_version_id") or ""
    if version_id:
        materials.process_version(version_id, text=text)
    return material["id"]


def _voice(prefs: dict) -> None:
    intel_store.save_voice_profile("local", json.dumps({"explicit_preferences": prefs}, ensure_ascii=False), 1, True)


def run(data_dir: Path) -> dict:
    _isolate(data_dir)
    product_store.init_db()
    intel_store.init_db()
    out: dict = {}

    # ---------------- J1: Session Pack immutability ----------------
    space = conversations.create_space("PackImm", "PROJECT_SYNC")
    goal = conversations.create_goal(space["id"], "迁移上线", "无回滚")
    participant = conversations.add_participant(
        space["id"], display_name="王工", role="CTO",
        explicit_priority="migration stability", explicit_concern="rollback risk",
        decision_authority="architecture approval", relationship_context="customer technical lead",
    )
    mat_id = _make_material("Q4 报告", "Q4 数据规模为 10x，延迟降低 40%。")
    conversations.update_space(space["id"], {"selected_source_ids": [mat_id]})
    note = quick_notes.create_note(content="客户明确说下周评审", title="客户备注")
    conversations.update_space(space["id"], {"selected_quick_note_ids": [note["id"]]})
    _voice({"conclusion_first": True, "shape": "bullet", "target_seconds": 30, "banned_phrases": ["总而言之"]})

    session = conversations.create_session(space["id"], title="J1", capture_mode="NOTES_ONLY",
                                           processing_mode="LOCAL", consent_ack=True)
    conversations.start_session(session["id"])
    before = conversations._frozen_pack_payload(conversations.require_session(session["id"]))
    before_digest = _digest(before)

    # Mutate every mutable input after ACTIVE.
    conversations.update_goal(goal["id"], {"outcome_definition": "CHANGED outcome"})
    conversations.add_participant(space["id"], display_name="李工", role="PM")
    conversations.update_participant(participant["id"], {"explicit_concern": "CHANGED concern"})
    _make_material("Q4 报告 v2", "Q4 数据规模为 50x，延迟降低 60%。")
    conversations.update_space(space["id"], {"selected_source_ids": [mat_id, "ghost_material_v2"]})
    quick_notes.update_note(note["id"], {"content": "CHANGED note"})
    _voice({"conclusion_first": False, "shape": "narrative", "target_seconds": 60, "banned_phrases": []})
    thread_item = conversations.add_item(session["id"], item_type="OpenQuestion", title="谁负责回滚？",
                                         source_refs=[{"kind": "USER_NOTE", "excerpt": "需要明确"}])
    conversations.review_item(thread_item["id"], "CONFIRM")
    tr = conversations.space_detail(space["id"])["threads"][0]
    conversations.resolve_open_thread(tr["id"])

    after = conversations._frozen_pack_payload(conversations.require_session(session["id"]))
    after_digest = _digest(after)
    brief = after.get("session_brief") or {}
    j1 = {
        "digest_before": before_digest,
        "digest_after": after_digest,
        "immutable": before_digest == after_digest,
        "frozen_goal_still": [g["id"] for g in (brief.get("goals") or [])] == [goal["id"]],
        "frozen_expression_still": after.get("expression_profile") == {
            "conclusion_first": True, "shape": "bullet", "target_seconds": 30, "banned_phrases": ["总而言之"]},
        "frozen_playbook_profile": (after.get("profile_playbook") or {}).get("profile") == "PROJECT_SYNC",
        "frozen_processing_mode": (after.get("processing_runtime") or {}).get("mode") == "LOCAL",
        "frozen_participants_still_1": len(after.get("participants") or []) == 1,
    }
    out["J1_session_pack_immutability"] = j1

    # ---------------- J2: Truth / provenance negatives ----------------
    j2 = {}
    ai_item = conversations.add_item(session["id"], item_type="Decision", title="AI 提取的决策",
                                     source_refs=[{"kind": "TRANSCRIPT", "excerpt": "我们决定 X"}])
    j2["ai_extracted_not_agreed"] = ai_item["state"] == "PROPOSED" and ai_item["review_status"] == "AI_EXTRACTED"
    try:
        conversations.add_item(session["id"], item_type="Commitment", title="无 owner 承诺",
                               state="COMMITTED", source_refs=[{"kind": "USER_NOTE", "excerpt": "s"}])
        j2["commitment_requires_owner_source_review"] = False
    except ValueError:
        j2["commitment_requires_owner_source_review"] = True
    try:
        conversations.add_item(session["id"], item_type="Deadline", title="周五前完成", state="COMMITTED")
        j2["deadline_requires_source"] = False
    except ValueError:
        j2["deadline_requires_source"] = True
    ambiguous = []
    for text in ("周五前完成", "下周给结论", "月底前上线", "明天答复"):
        item = conversations.add_item(session["id"], item_type="Deadline", title=text,
                                      source_refs=[{"kind": "USER_NOTE", "excerpt": "原话"}])
        blocked = False
        try:
            conversations.review_item(item["id"], "CONFIRM")
        except ValueError as exc:
            blocked = "歧义" in str(exc)
        ambiguous.append({"original_text": text, "blocked_from_reviewed_truth": blocked})
    j2["ambiguous_deadlines_blocked"] = ambiguous

    # Supersession: old Decision must remain SUPERSEDED, never deleted.
    old = conversations.add_item(session["id"], item_type="Decision", title="采用方案 A",
                                 source_refs=[{"kind": "USER_NOTE", "excerpt": "决定 A"}])
    conversations.review_item(old["id"], "CONFIRM")
    new = conversations.add_item(session["id"], item_type="Decision", title="采用方案 B",
                                 source_refs=[{"kind": "USER_NOTE", "excerpt": "决定 B"}])
    conversations.review_item(new["id"], "SUPERSEDE", {"supersedes_id": old["id"]})
    old_now = conversations.require_item(old["id"])
    new_now = conversations.require_item(new["id"])
    j2["supersession_keeps_old_as_superseded"] = (
        old_now["state"] == "SUPERSEDED" and new_now["state"] == "AGREED"
        and new_now.get("supersedes_id") == old["id"]
    )

    # Quick note / transcript stay non-evidence in Manual Ask.
    ask_note = conversations.ask(session["id"], "客户备注")
    j2["quick_note_authority"] = any(r.get("authority") == "USER_NOTE_NOT_EVIDENCE" for r in ask_note.get("matches", []))
    store = product_store
    store.insert("conversation_transcript_segment", {
        "id": "cts_j2_1", "space_id": space["id"], "session_id": session["id"],
        "channel": "PRIMARY_AUDIO", "text": "我们先看看数据规模再定方案", "created_at": store.now(),
    })
    before_items = int(store.scalar("SELECT COUNT(*) FROM conversation_item"))
    ask_tr = conversations.ask(session["id"], "数据规模")
    j2["transcript_observation_not_truth"] = (
        bool(ask_tr.get("grounded"))
        and int(store.scalar("SELECT COUNT(*) FROM conversation_item")) == before_items
    )
    out["J2_truth_provenance_negatives"] = j2

    # ---------------- J3: Open Thread lifecycle + 500+ ----------------
    j3 = {}
    t = conversations.add_item(session["id"], item_type="OpenQuestion", title="待确认问题",
                               source_refs=[{"kind": "TRANSCRIPT", "excerpt": "待确认"}])
    j3["ai_extracted_not_persistent"] = conversations.space_detail(space["id"])["threads"] == []
    conversations.review_item(t["id"], "CONFIRM")
    j3["confirm_opens_thread"] = any(x["status"] == "OPEN" and x["kind"] == "OpenQuestion"
                                     for x in conversations.space_detail(space["id"])["threads"])
    thr = next(x for x in conversations.space_detail(space["id"])["threads"] if x["kind"] == "OpenQuestion")
    conversations.resolve_open_thread(thr["id"])
    j3["resolve_closes_thread"] = conversations.space_detail(space["id"])["threads"] == []
    obj = conversations.add_item(session["id"], item_type="Objection", title="回滚风险",
                                 source_refs=[{"kind": "USER_NOTE", "excerpt": "明确 objection"}])
    conversations.review_item(obj["id"], "CONFIRM")
    j3["objection_opens_thread"] = any(x["status"] == "OPEN" for x in conversations.space_detail(space["id"])["threads"])
    conversations.review_item(obj["id"], "REJECT")
    j3["reject_closes_thread"] = all(x["status"] != "OPEN" for x in conversations.space_detail(space["id"])["threads"])

    # 500+ historical threads: bulk-confirm OpenQuestions in one session.
    bulk_session = conversations.create_session(space["id"], title="Bulk", capture_mode="NOTES_ONLY",
                                                processing_mode="LOCAL", consent_ack=True)
    conversations.start_session(bulk_session["id"])
    bulk_ids = []
    for i in range(520):
        it = conversations.add_item(bulk_session["id"], item_type="OpenQuestion",
                                    title=f"bulk-thread-{i}", source_refs=[{"kind": "TRANSCRIPT", "excerpt": "x"}])
        conversations.review_item(it["id"], "CONFIRM")
        bulk_ids.append(it["id"])
    detail = conversations.space_detail(space["id"])
    open_threads = [x for x in detail["threads"] if x["status"] == "OPEN"]
    j3["bulk_520_confirmed"] = len(bulk_ids) == 520
    j3["open_thread_projection_not_truncated"] = len(open_threads) >= 500
    j3["prepare_still_lists_all_open"] = len(conversations.prepare_space(space["id"])["open_threads"]) >= 500

    # Delete source session with confirmed truth -> no phantom OPEN thread.
    conversations.end_session(bulk_session["id"])
    before_delete_open = len([x for x in conversations.space_detail(space["id"])["threads"] if x["status"] == "OPEN"])
    del_result = conversations.delete_session(bulk_session["id"], confirmed_policy="TOMBSTONE")
    after_delete = conversations.space_detail(space["id"])["threads"]
    phantom = [x for x in after_delete if x["status"] == "OPEN" and x["session_id"] == bulk_session["id"]]
    j3["delete_session_no_phantom_thread"] = phantom == []
    j3["delete_tombstoned"] = bool(del_result.get("tombstone") or del_result.get("deleted"))
    j3["open_threads_before_delete"] = before_delete_open
    j3["open_threads_after_delete"] = len([x for x in after_delete if x["status"] == "OPEN"])
    out["J3_open_thread_lifecycle"] = j3

    # ---------------- J4: Conversation State is derived ----------------
    j4 = {}
    st = conversations.conversation_state(session["id"])
    j4["state_has_phase"] = bool(st.get("phase"))
    before_items4 = int(store.scalar("SELECT COUNT(*) FROM conversation_item"))
    before_threads4 = int(store.scalar("SELECT COUNT(*) FROM conversation_open_thread"))
    j4["state_has_topic_speaking_audience"] = all(k in st for k in ("current_topic", "user_speaking", "audience_context", "items", "open_threads", "last_guidance_id"))
    cont = conversations.continue_summary(session["id"])
    conv_state_again = conversations.conversation_state(session["id"])
    try:
        conversations.derived_writeback_draft(session["id"], "CREATE_TASK_DRAFT")
    except ValueError:
        pass  # may require ENDED or specific state; drafts must never be truth either way
    after_items4 = int(store.scalar("SELECT COUNT(*) FROM conversation_item"))
    after_threads4 = int(store.scalar("SELECT COUNT(*) FROM conversation_open_thread"))
    j4["derived_views_create_no_truth"] = (
        after_items4 == before_items4 and after_threads4 == before_threads4
        and conv_state_again == st
    )
    j4["continue_summary_sections"] = sorted(cont.keys())
    out["J4_conversation_state_derived_only"] = j4

    # ---------------- K1: Manual Ask authority + frozen retrieval ----------------
    k1 = {}
    auth_space = conversations.create_space("AskAuth", "PROJECT_SYNC")
    auth_sess = conversations.create_session(auth_space["id"], capture_mode="NOTES_ONLY",
                                             processing_mode="LOCAL", consent_ack=True)
    conversations.start_session(auth_sess["id"])
    dec = conversations.add_item(auth_sess["id"], item_type="Decision", title="采用方案 B",
                                 source_refs=[{"kind": "USER_NOTE", "excerpt": "决定 B"}])
    conversations.review_item(dec["id"], "CONFIRM")
    m1 = _make_material("方案 B 文档", "方案 B 的完整设计文档")
    conversations.update_space(auth_space["id"], {"selected_source_ids": [m1]})
    n1 = quick_notes.create_note(content="方案 B 备忘", title="备忘")
    conversations.update_space(auth_space["id"], {"selected_quick_note_ids": [n1["id"]]})
    r = conversations.ask(auth_sess["id"], "方案 B")
    authorities = [x["authority"] for x in r.get("matches", [])]
    k1["authority_order"] = authorities
    k1["confirmed_truth_ranks_first"] = bool(authorities and authorities[0] == "CONFIRMED_TRUTH")

    # Frozen source replacement: v1 10x frozen; v2 50x arrives after start.
    repl_space = conversations.create_space("SourceRepl", "PROJECT_SYNC")
    mv1 = _make_material("数据说明", "Q4 数据规模为 10x，延迟降低 40%。")
    conversations.update_space(repl_space["id"], {"selected_source_ids": [mv1]})
    repl_sess = conversations.create_session(repl_space["id"], capture_mode="NOTES_ONLY",
                                             processing_mode="LOCAL", consent_ack=True)
    conversations.start_session(repl_sess["id"])
    _make_material("数据说明 v2", "Q4 数据规模为 50x，延迟降低 60%。")
    conversations.update_space(repl_space["id"], {"selected_source_ids": [mv1, "ghost_v2"]})
    r10 = conversations.ask(repl_sess["id"], "10x")
    r50 = conversations.ask(repl_sess["id"], "50x")
    k1["ask_10x_hits_frozen_v1"] = any("10x" in x.get("excerpt", "") for x in r10.get("matches", []))
    k1["ask_50x_not_falsely_grounded_in_v1"] = not any("10x" in x.get("excerpt", "") for x in r50.get("matches", []))
    k1["ask_50x_results"] = [x.get("excerpt", "")[:80] for x in r50.get("matches", [])]

    # Distinctive token exactness.
    tok_space = conversations.create_space("Tokens", "PROJECT_SYNC")
    tok_sess = conversations.create_session(tok_space["id"], capture_mode="NOTES_ONLY",
                                            processing_mode="LOCAL", consent_ack=True)
    conversations.start_session(tok_sess["id"])
    for title in ("v2 兼容层方案", "v3 兼容层方案", "Q4 数据规模 10x", "Q3 数据规模 8x", "2026-10-09 上线", "2026-10-08 上线"):
        it = conversations.add_item(tok_sess["id"], item_type="Status", title=title,
                                    source_refs=[{"kind": "USER_NOTE", "excerpt": "t"}])
        conversations.review_item(it["id"], "CONFIRM")
    def _hit(question: str, needle: str) -> bool:
        rr = conversations.ask(tok_sess["id"], question)
        return any(needle in x.get("title", "") for x in rr.get("matches", []))
    k1["token_v2_not_v3"] = _hit("v2 兼容层", "v2 兼容层") and not _hit("v3 兼容层", "v2 兼容层")
    k1["token_10x_not_50x"] = _hit("10x 数据规模", "10x") and not _hit("50x 数据规模", "10x")
    k1["token_q4_not_q3"] = _hit("Q4 数据规模", "Q4 数据规模") and not _hit("Q3 数据规模", "Q4 数据规模")
    k1["token_date_exact"] = _hit("2026-10-09 上线", "2026-10-09") and not _hit("2026-10-08 上线", "2026-10-09")
    out["K1_manual_ask_frozen_retrieval"] = k1

    # ---------------- P1: Expression profile freeze ----------------
    p1 = {}
    exp_space = conversations.create_space("ExpFreeze", "PRESENTATION_QA")
    exp_sess = conversations.create_session(exp_space["id"], capture_mode="NOTES_ONLY",
                                            processing_mode="LOCAL", consent_ack=True)
    _voice({"conclusion_first": True, "shape": "bullet", "target_seconds": 30})
    conversations.start_session(exp_sess["id"])
    frozen_expr = conversations._frozen_pack_payload(conversations.require_session(exp_sess["id"])).get("expression_profile")
    _voice({"conclusion_first": False, "shape": "narrative", "target_seconds": 90})
    still = conversations._frozen_pack_payload(conversations.require_session(exp_sess["id"])).get("expression_profile")
    p1["frozen_expression_kept"] = frozen_expr == {"conclusion_first": True, "shape": "bullet", "target_seconds": 30} and still == frozen_expr
    cue = conversations.evaluate_guidance(exp_sess["id"], {"delivery_focus": "conclusion first", "source_refs": []})
    cue_text = cue["guidance"]["text"]
    p1["cue_uses_frozen_style"] = ("先给结论" in cue_text and "要点展开" in cue_text and "30 秒" in cue_text)
    p1["cue_changes_structure_only"] = not any(f in cue_text for f in ("10x", "40%", "方案"))
    p1["cue_text"] = cue_text[:300]
    out["P1_expression_profile_freeze"] = p1

    return out


def main() -> int:
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tmp_phase_j")
    report = run(data_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
