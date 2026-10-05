"""Next Focus engine (canonical §7) — 1–3 explainable items per Goal.

Ranking is deterministic and every item carries ``reason`` + ``source``.
There is no composite readiness score. Order of precedence:

  1. USER items (set explicitly from Reflection, a Pin, or the Goal Room)
  2. Practice / session weaknesses (rubric observations, weighted by role)
  3. Fact boundaries on job-relevant claims (Fact Inbox high-risk items)
  4. Goal requirement gaps (JD × evidence)
  5. Story gaps for competencies the role cares about

Practice reads ``practice_defaults`` so the next practice starts on the top
item instead of a generic setup.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from core.logger import get_logger
from services.product import events
from services.product.rubrics import DIMENSIONS, priority_gaps
from services.storage import product as store

_log = get_logger("product.next_focus")

MAX_ITEMS = 3

# Finding / focus types (shared with Reflection finding kinds).
TYPES: dict[str, dict[str, Any]] = {
    "KNOWLEDGE_GAP": {"label": "知识缺口", "round": "TECHNICAL", "actions": ["learn", "add_source", "practice"]},
    "OWNERSHIP": {"label": "Ownership 表达", "round": "PROJECT_DEEP_DIVE", "actions": ["practice", "create_story"]},
    "STORY_GAP": {"label": "Story 缺口", "round": "BEHAVIORAL", "actions": ["story_builder", "practice"]},
    "FACT_BOUNDARY": {"label": "事实边界", "round": "PROJECT_DEEP_DIVE", "actions": ["confirm_fact", "add_source", "practice"]},
    "SYSTEM_DESIGN": {"label": "系统设计", "round": "SYSTEM_DESIGN", "actions": ["practice", "learn"]},
    "DELIVERY": {"label": "表达节奏", "round": "BEHAVIORAL", "actions": ["practice"]},
    "FOLLOWUP_RESILIENCE": {"label": "追问韧性", "round": "TECHNICAL", "actions": ["practice"]},
    "CODING": {"label": "编码", "round": "TECHNICAL", "actions": ["practice", "learn"]},
    "CLOSING_QUESTION": {"label": "收尾提问", "round": "HIRING_MANAGER", "actions": ["add_quick_note", "practice"]},
    "USER_PIN": {"label": "你标记的时刻", "round": "", "actions": ["practice"]},
    "RUBRIC": {"label": "能力维度", "round": "", "actions": ["practice"]},
}

ACTION_LABELS = {
    "learn": "学知识", "add_source": "补来源", "practice": "练这个问题", "create_story": "整理 Story",
    "story_builder": "开始 5 分钟 Story Builder", "confirm_fact": "确认事实", "add_quick_note": "记一条速记",
}

# rubric dimension -> focus type
_DIMENSION_TYPE = {
    "ownership": "OWNERSHIP", "followup_resilience": "FOLLOWUP_RESILIENCE", "communication": "DELIVERY",
    "trade_off": "SYSTEM_DESIGN", "depth": "KNOWLEDGE_GAP", "technical_correctness": "KNOWLEDGE_GAP",
    "evidence_discipline": "FACT_BOUNDARY", "impact": "OWNERSHIP",
}
_DEMEANOR_FOR_TYPE = {"FOLLOWUP_RESILIENCE": "STRONG_FOLLOWUP", "DELIVERY": "FAST_PACED",
                      "FACT_BOUNDARY": "SKEPTICAL", "OWNERSHIP": "SKEPTICAL"}

_PRIORITY = {"USER": 100, "REFLECTION": 90, "PRACTICE": 80, "FACT": 70, "GAP": 60, "STORY": 50}


def topic_key(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())[:60]


def _item(type_: str, title: str, reason: str, source_kind: str, source_ref: str = "",
          priority: Optional[int] = None, extra_actions: Optional[list[str]] = None) -> dict[str, Any]:
    spec = TYPES.get(type_, TYPES["RUBRIC"])
    actions = list(dict.fromkeys([*(extra_actions or []), *spec["actions"]]))
    return {"type": type_, "title": title[:80], "topic_key": topic_key(f"{type_}:{title}"), "reason": reason[:240],
            "source_kind": source_kind, "source_ref": str(source_ref)[:120],
            "actions": [{"key": a, "label": ACTION_LABELS.get(a, a)} for a in actions],
            "priority": priority if priority is not None else _PRIORITY.get(source_kind, 40)}


# ---------------------------------------------------------------------------
# Candidate generators (each degrades to [])
# ---------------------------------------------------------------------------


def _practice_candidates(goal: dict[str, Any]) -> list[dict[str, Any]]:
    rows = store.select("rubric_observation", "goal_id = ?", (goal["id"],), "created_at DESC", 80)
    if not rows:
        return []
    sessions: list[str] = []
    for row in rows:
        if row["session_ref"] not in sessions:
            sessions.append(row["session_ref"])
    recent = set(sessions[:3])
    levels: dict[str, list[int]] = {}
    for row in rows:
        if row["session_ref"] in recent:
            levels.setdefault(row["dimension"], []).append(int(row["level"]))
    avg = {k: sum(v) / len(v) for k, v in levels.items() if v}
    out = []
    for gap in priority_gaps(goal.get("role_family") or "SWE", avg)[:2]:
        type_ = _DIMENSION_TYPE.get(gap["dimension"], "RUBRIC")
        level = float(gap["level"])
        if level < 1.5:
            observation = "多次明显缺失"
        elif level < 2.5:
            observation = "经常不够完整"
        elif level < 3.5:
            observation = "还不够稳定"
        else:
            observation = "已经比较稳定，但仍值得保持"
        role_note = "这个岗位会重点追问这一项。" if int(gap["weight"]) >= 15 else "继续补齐会让回答更稳。"
        out.append(_item(
            type_, DIMENSIONS[gap["dimension"]],
            f"最近 {len(recent)} 场练习里，「{gap['label']}」{observation}；{role_note}",
            "PRACTICE", gap["dimension"],
            priority=_PRIORITY["PRACTICE"] + min(9, int(gap["rank_value"] / 10)),
        ))
    return out


def _fact_candidates(goal: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        from services.product.fact_inbox import inbox_items

        items = [i for i in inbox_items(limit=50) if i.get("risk") == "HIGH"]
    except Exception as exc:  # noqa: BLE001
        _log.debug("fact inbox unavailable: %s", exc)
        return []
    if not items:
        return []
    first = items[0]
    return [_item("FACT_BOUNDARY", f"{len(items)} 个高风险事实待确认",
                  f"例如「{first['text'][:40]}」：材料目前只支持「{first['supported_label']}」。面试中被追问前先确认边界。",
                  "FACT", first["id"])]


def _gap_candidates(goal: dict[str, Any], workspace: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps = (workspace or {}).get("gap_map") or []
    out = []
    for gap in gaps[:2]:
        if gap.get("priority") == "low":
            continue
        status = gap.get("status")
        topic = str(gap.get("topic") or "")
        if status == "KNOWLEDGE_MATCH":
            reason = f"岗位要求「{topic}」；你可以讲通用知识，但材料里没有你做过的来源。"
        elif status in ("REVIEW_WEAKNESS", "REPEATED_TOPIC"):
            reason = f"「{topic}」在之前的复盘里暴露为薄弱点。"
        else:
            reason = f"岗位要求「{topic}」，但你的材料里还没有对应证据。"
        type_ = "SYSTEM_DESIGN" if re.search(r"(架构|设计|系统|高可用|分布式|design)", topic, re.I) else "KNOWLEDGE_GAP"
        out.append(_item(type_, topic, reason, "GAP", topic))
    return out


def _story_candidates(goal: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        from services.product.workspace import story_coverage, stories_list

        missing = story_coverage(stories_list())["missing"]
    except Exception as exc:  # noqa: BLE001 — story coverage is an enrichment, not a gate
        _log.debug("story coverage unavailable for next focus: %s", exc)
        return []
    preferred = ("Ownership", "Failure", "Conflict", "Difficult Problem")
    ranked = sorted(missing, key=lambda m: preferred.index(m["key"]) if m["key"] in preferred else 9)
    if not ranked:
        return []
    m = ranked[0]
    return [_item("STORY_GAP", f"缺少「{m['label']}」故事", f"你还没有「{m['label']}」类的真实故事；行为面常问。",
                  "STORY", m["key"])]


def candidates(goal: dict[str, Any], workspace: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    return [*_practice_candidates(goal), *_fact_candidates(goal), *_gap_candidates(goal, workspace),
            *_story_candidates(goal)]


# ---------------------------------------------------------------------------
# Persisted Next Focus
# ---------------------------------------------------------------------------


def active_items(goal_id: str) -> list[dict[str, Any]]:
    return store.select("next_focus", "goal_id = ? AND status = 'ACTIVE'", (goal_id,),
                        "priority DESC, updated_at DESC", MAX_ITEMS)


def recompute(goal_id: str, workspace: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """Refresh DERIVED items; USER items are kept and always rank first."""
    from services.product.goals import require_goal

    goal = require_goal(goal_id)
    if workspace is None and goal.get("jd"):
        from services.product.workspace import goal_workspace

        workspace = goal_workspace(goal)
    before_top = (active_items(goal_id) or [{}])[0].get("topic_key")
    users = store.select("next_focus", "goal_id = ? AND status = 'ACTIVE' AND origin = 'USER'", (goal_id,),
                         "priority DESC, updated_at DESC")
    derived_slots = max(0, MAX_ITEMS - len(users))
    seen = {u["topic_key"] for u in users}
    chosen: list[dict[str, Any]] = []
    for cand in sorted(candidates(goal, workspace), key=lambda c: -c["priority"]):
        if cand["topic_key"] in seen or len(chosen) >= derived_slots:
            continue
        seen.add(cand["topic_key"])
        chosen.append(cand)
    now = store.now()
    with store.connect() as conn:
        existing = {r["topic_key"]: r for r in (store.decode_row(x) for x in conn.execute(
            "SELECT * FROM next_focus WHERE goal_id = ? AND status = 'ACTIVE' AND origin = 'DERIVED'",
            (goal_id,)).fetchall()) if r}
        keep: set[str] = set()
        for cand in chosen:
            row = existing.get(cand["topic_key"])
            if row:
                store.update("next_focus", row["id"], {**cand, "updated_at": now}, conn=conn)
                keep.add(row["id"])
            else:
                new = {"id": store.new_id("nf_"), "goal_id": goal_id, **cand, "status": "ACTIVE",
                       "origin": "DERIVED", "created_at": now, "updated_at": now}
                store.insert("next_focus", new, conn=conn)
                keep.add(new["id"])
        for row in existing.values():
            if row["id"] not in keep:
                conn.execute("UPDATE next_focus SET status = 'SUPERSEDED', updated_at = ? WHERE id = ?", (now, row["id"]))
    items = active_items(goal_id)
    _set_goal_pointer(goal_id, items, before_top)
    return items


def _set_goal_pointer(goal_id: str, items: list[dict[str, Any]], before_top: Optional[str]) -> None:
    top = items[0] if items else None
    store.update("goal", goal_id, {"next_focus_id": top["id"] if top else ""})
    if top and top["topic_key"] != before_top:
        events.record("next_focus_changed", goal_id=goal_id, type=top["type"], origin=top["origin"])


def set_user_focus(
    goal_id: str,
    type_: str,
    title: str,
    reason: str,
    *,
    source_kind: str = "USER",
    source_ref: str = "",
) -> dict[str, Any]:
    """Explicit user choice (Reflection 'Set as Next Focus', a Pin, Goal Room)."""
    from services.product.goals import require_goal

    require_goal(goal_id)
    if type_ not in TYPES:
        raise ValueError(f"未知 Next Focus 类型：{type_}")
    before_top = (active_items(goal_id) or [{}])[0].get("topic_key")
    cand = _item(type_, title, reason, source_kind, source_ref, priority=_PRIORITY["USER"])
    now = store.now()
    with store.connect() as conn:
        # newest explicit choice wins: older USER items step down but stay
        conn.execute("UPDATE next_focus SET priority = priority - 1 WHERE goal_id = ? AND origin = 'USER' "
                     "AND status = 'ACTIVE'", (goal_id,))
        conn.execute("UPDATE next_focus SET status = 'SUPERSEDED', updated_at = ? WHERE goal_id = ? "
                     "AND status = 'ACTIVE' AND topic_key = ?", (now, goal_id, cand["topic_key"]))
        row = {"id": store.new_id("nf_"), "goal_id": goal_id, **cand, "status": "ACTIVE", "origin": "USER",
               "created_at": now, "updated_at": now}
        store.insert("next_focus", row, conn=conn)
        # keep at most MAX_ITEMS active: drop the lowest derived first
        active = conn.execute("SELECT id, origin FROM next_focus WHERE goal_id = ? AND status = 'ACTIVE' "
                              "ORDER BY priority DESC, updated_at DESC", (goal_id,)).fetchall()
        for extra in active[MAX_ITEMS:]:
            conn.execute("UPDATE next_focus SET status = 'SUPERSEDED', updated_at = ? WHERE id = ?", (now, extra[0]))
    items = active_items(goal_id)
    _set_goal_pointer(goal_id, items, before_top)
    return row


def complete(focus_id: str) -> Optional[dict[str, Any]]:
    row = store.get("next_focus", focus_id)
    if row is None:
        return None
    store.update("next_focus", focus_id, {"status": "DONE", "updated_at": store.now()})
    events.record("next_focus_completed", goal_id=row["goal_id"], type=row["type"])
    recompute(row["goal_id"])
    return store.get("next_focus", focus_id)


def dismiss(focus_id: str) -> Optional[dict[str, Any]]:
    row = store.get("next_focus", focus_id)
    if row is None:
        return None
    store.update("next_focus", focus_id, {"status": "DISMISSED", "updated_at": store.now()})
    recompute(row["goal_id"])
    return store.get("next_focus", focus_id)


def practice_defaults(goal_id: str) -> dict[str, Any]:
    """Practice setup defaults driven by the Goal's top Next Focus item."""
    items = active_items(goal_id)
    if not items:
        return {"round": "", "focus": None, "demeanor": "NEUTRAL", "difficulty": "STANDARD",
                "sources": ["GOAL_GRAPH", "RECENT_WEAKNESS", "ROLE_BANK"]}
    top = items[0]
    spec = TYPES.get(top["type"], TYPES["RUBRIC"])
    round_name = spec["round"]
    if top["type"] == "RUBRIC" or not round_name:
        round_name = "PROJECT_DEEP_DIVE" if top["source_ref"] in ("ownership", "impact") else "TECHNICAL"
    return {
        "round": round_name,
        "focus": {"id": top["id"], "type": top["type"], "title": top["title"], "reason": top["reason"]},
        "demeanor": _DEMEANOR_FOR_TYPE.get(top["type"], "NEUTRAL"),
        "difficulty": "STANDARD",
        "sources": ["RECENT_WEAKNESS", "GOAL_GRAPH", "MY_BANK", "ROLE_BANK"],
    }
