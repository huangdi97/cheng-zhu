"""Go Live → Preflight 3.0 → Live → Reflection (canonical §17).

Preflight lists every input of the coming session with its origin
(我的成竹 / Goal 默认 / 本场覆盖 / 系统默认). Start freezes the Goal into an
InterviewPack through the v1.2 core (build_pack_payload + freeze_pack) and
adds the v1.3 sections: selected Quick Notes (``user_notes``, never
evidence) and READY Goal materials (``goal_materials``). Session overrides
are installed as the config session overlay — never saved as global
defaults — and removed at the end.
"""
from __future__ import annotations

from typing import Any, Optional

from core.logger import get_logger
from services.product import events, settings_layers
from services.storage import product as store

_log = get_logger("product.live")

MATERIAL_EXCERPT_CHARS = 1500


class LiveError(ValueError):
    pass


def _current_session_id() -> str:
    from core.session import session_id as current_session_id

    return str(current_session_id() or "default")


def _resume_text(goal: dict[str, Any]) -> tuple[str, str]:
    """(text, origin) — the Goal's selected resume, else the active one in 我的成竹."""
    rid = goal.get("selected_resume_id")
    if rid:
        try:
            from services.storage import resume_history

            entry = resume_history.get_entry_detail(int(rid))
            text = str(entry.get("summary") or "") if entry.get("summary_is_full") else ""
            if text:
                return text, "GOAL"
        except Exception as exc:  # noqa: BLE001
            _log.debug("goal resume unavailable: %s", exc)
    from core.config import persisted_config

    return str(getattr(persisted_config(), "resume_text", "") or ""), "PERSON"


def preflight(goal_id: str, session_overrides: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    from services.product.goals import require_goal
    from services.product.materials import materials_for_pack
    from services.product.quick_notes import notes_for_pack
    from services.product.workspace import stories_list

    goal = require_goal(goal_id)
    resolved = settings_layers.resolve(goal_id)
    for key, value in (session_overrides or {}).items():
        if key in resolved:
            settings_layers._validate(key, value)  # noqa: SLF001 — same validation as a stored override
            resolved[key] = {**resolved[key], "value": value, "origin": "SESSION",
                             "origin_label": settings_layers.ORIGIN_LABELS["SESSION"]}
    resume, resume_origin = _resume_text(goal)
    mats = materials_for_pack(goal)
    notes = notes_for_pack({**goal, "id": goal["id"]})
    cards = _skill_card_count(goal)
    stories = stories_list()

    def item(key: str, label: str, value: Any, origin: str, ok: bool = True, hint: str = "") -> dict[str, Any]:
        return {"key": key, "label": label, "value": value, "origin": origin,
                "origin_label": settings_layers.ORIGIN_LABELS[origin], "ok": ok, "hint": hint}

    def layered(key: str, label: str) -> dict[str, Any]:
        r = resolved[key]
        return item(key, label, r["value"], r["origin"])

    from core.config import get_config

    cfg = get_config()
    model_index = int(resolved["active_model"]["value"])
    model_cfg = cfg.models[model_index] if 0 <= model_index < len(cfg.models) else None
    model_name = str(
        getattr(model_cfg, "name", "")
        or getattr(model_cfg, "model", "")
        or f"模型 {model_index + 1}"
    )
    technical_term_labels = {
        "AUTO": "自动",
        "KEEP_ENGLISH": "保留英文",
        "TRANSLATE": "译为回答语言",
        "BILINGUAL": "中英并列",
    }
    stt_labels = {
        "whisper": "本地 Whisper",
        "doubao": "豆包语音识别",
        "generic": "通用 STT",
    }
    items = [
        item("goal", "求职目标", goal["title"], "GOAL"),
        item("resume", "简历", "已选择" if resume else "未导入", resume_origin, bool(resume),
             "" if resume else "在「我的成竹 · 简历」导入"),
        item("skill_cards", "技能卡", cards, "GOAL"),
        item("stories", "故事", len(stories), "PERSON"),
        item("knowledge", "知识库", "开启" if resolved["kb_enabled"]["value"] else "关闭", resolved["kb_enabled"]["origin"]),
        item("materials", "项目资料", f"{len(mats['included'])} 份就绪", "GOAL", not mats["skipped"],
             f"{len(mats['skipped'])} 份未就绪，不会进入本场" if mats["skipped"] else ""),
        item("quick_notes", "速记", len(notes), "GOAL"),
        layered("answer_language", "回答语言"),
        layered("whisper_language", "面试语言"),
        layered("language", "编程语言"),
        item(
            "technical_term_policy",
            "技术术语",
            technical_term_labels.get(str(resolved["technical_term_policy"]["value"]),
                                      str(resolved["technical_term_policy"]["value"])),
            resolved["technical_term_policy"]["origin"],
        ),
        item("active_model", "回答模型", model_name, resolved["active_model"]["origin"]),
        item(
            "stt",
            "语音识别",
            stt_labels.get(str(getattr(cfg, "stt_provider", "whisper")),
                           str(getattr(cfg, "stt_provider", "whisper"))),
            "GLOBAL",
        ),
        item("audio", "音频", "开播前检测", "SYSTEM"),
        layered("ai_policy_mode", "AI 辅助"),
        layered("human_assistance_policy", "真人辅助"),
        layered("share_privacy_mode", "共享隐私"),
        item("screen_context", "屏幕上下文", "按需", "SYSTEM"),
    ]
    blockers = [i for i in items if not i["ok"] and i["key"] in ("resume",)]
    events.record("preflight_started", goal_id=goal_id)
    return {"goal": {"id": goal["id"], "title": goal["title"]}, "items": items, "blockers": blockers,
            "share_privacy_note": "减少成竹私人内容在受支持的屏幕共享/录屏路径中意外出现，不是安全或不可检测保证。"}


def _skill_card_count(goal: dict[str, Any]) -> int:
    space_id = goal.get("legacy_prep_space_id")
    if not space_id:
        return 0
    try:
        from services.storage import prep_space

        return len((prep_space.get_space(int(space_id)) or {}).get("skill_cards") or [])
    except Exception as exc:  # noqa: BLE001 — skill cards are optional context
        _log.debug("prep space skill cards unavailable: %s", exc)
        return 0


def start(goal_id: str, session_overrides: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    from services.intelligence import interview_pack
    from services.intelligence.job_representation import build_job_representation, save_job
    from services.product.goals import link_session, require_goal
    from services.product.materials import materials_for_pack
    from services.product.quick_notes import notes_for_pack

    goal = require_goal(goal_id)
    session_id = _current_session_id()
    settings_layers.clear_override("SESSION", session_id)
    for key, value in (session_overrides or {}).items():
        settings_layers.set_override("SESSION", session_id, key, value)
    overlay = settings_layers.apply_session(goal_id, session_id)
    # position / JD of this Goal apply to this session only (never persisted)
    from core.config import get_config, session_overlay, set_session_overlay

    set_session_overlay({**session_overlay(), "position": goal["role"] or "通用岗位",
                         "jd_text": goal["jd"] or "", "assist_answer_align_jd_enabled": True})
    cfg = get_config()
    resume, _ = _resume_text(goal)
    job_id = ""
    if goal["jd"]:
        job = build_job_representation(goal["jd"], company=goal["company"], title=goal["title"], role=goal["role"])
        job_id = save_job(job, job_id=f"job-goal-{goal['id']}")
    payload = interview_pack.build_pack_payload(
        session_id=session_id, cfg=cfg, job_id=job_id, prep_space_id=goal.get("legacy_prep_space_id"),
        answer_preferences={"notes": str(getattr(cfg, "interview_notes", "") or ""),
                            "answer_language": cfg.answer_language,
                            "technical_term_policy": getattr(cfg, "technical_term_policy", "AUTO")},
        profile_text_override=resume,
    )
    mats = materials_for_pack(goal)
    payload["goal_id"] = goal["id"]
    payload["user_notes"] = notes_for_pack(goal, record_usage=True)
    payload["goal_materials"] = [{k: m[k] for k in ("material_id", "version_id", "version", "title", "kind", "usage",
                                                    "content_hash", "is_personal_evidence")}
                                 | {"excerpt": m["text"][:MATERIAL_EXCERPT_CHARS]} for m in mats["included"]]
    payload["goal_materials_skipped"] = mats["skipped"]
    pack = interview_pack.freeze_pack(payload, reason="goal_go_live")
    link = link_session(goal["id"], "REAL", live_session_id=session_id, round_name=goal.get("interview_round") or "",
                        goal_interview_id=_upcoming_interview_id(goal["id"]))
    events.record("live_started", goal_id=goal["id"], session_id=session_id, notes=len(payload["user_notes"]),
                  materials=len(payload["goal_materials"]))
    return {"session_id": session_id, "goal_id": goal["id"], "pack": pack.summary(), "overlay_keys": sorted(overlay),
            "link_id": link["id"]}


def _upcoming_interview_id(goal_id: str) -> str:
    rows = store.select("goal_interview", "goal_id = ? AND status = 'UPCOMING'", (goal_id,),
                        "COALESCE(scheduled_at, 9e18) ASC", 1)
    return rows[0]["id"] if rows else ""


def end(session_id: str = "", review_session_id: Optional[int] = None) -> dict[str, Any]:
    """Close the Live session: attach its review row, clear the overlay."""
    session_id = session_id or _current_session_id()
    link_rows = store.select("goal_session_link", "live_session_id = ?", (session_id,), "created_at DESC", 1)
    settings_layers.end_session()
    if not link_rows:
        return {"session_id": session_id, "goal_id": None, "review_session_id": review_session_id}
    link = link_rows[0]
    if review_session_id is None:
        review_session_id = _find_review_for(float(link["created_at"]))
    if review_session_id is not None:
        store.update("goal_session_link", link["id"], {"review_session_id": int(review_session_id)})
        if link.get("goal_interview_id"):
            try:
                from services.product.goals import update_interview

                update_interview(link["goal_interview_id"], {"status": "DONE"})
            except Exception as exc:  # noqa: BLE001
                _log.warning("marking goal interview %s DONE after live failed: %s",
                             link["goal_interview_id"], exc)
        try:
            from services.product.question_banks import remember_session_questions
            from services.storage import review as review_storage

            detail = review_storage.get_session_detail(int(review_session_id)) or {}
            remember_session_questions(link["goal_id"], [t.get("question_text", "") for t in detail.get("turns", [])])
        except Exception as exc:  # noqa: BLE001
            _log.debug("remember live questions failed: %s", exc)
    events.record("live_completed", goal_id=link["goal_id"], session_id=session_id,
                  has_review=review_session_id is not None)
    return {"session_id": session_id, "goal_id": link["goal_id"], "review_session_id": review_session_id,
            "reflection_ref": {"session_kind": "REVIEW", "session_ref": str(review_session_id)}
            if review_session_id is not None else None}


def _find_review_for(started_after: float) -> Optional[int]:
    try:
        from services.storage import review as review_storage

        items = review_storage.list_sessions(page=1, page_size=20).get("items") or []
    except Exception as exc:  # noqa: BLE001 — the review store is optional here
        _log.debug("review sessions unavailable while linking a live session: %s", exc)
        return None
    candidates = [i for i in items if str(i.get("source") or "") in ("assist", "written_exam")
                  and float(i.get("started_at") or 0) >= started_after - 5]
    if not candidates:
        return None
    return int(min(candidates, key=lambda i: float(i["started_at"]))["id"])
