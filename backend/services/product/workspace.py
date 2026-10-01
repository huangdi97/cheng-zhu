"""Goal workspace: the v1.2 Job Workspace composed for one Goal's own JD.

Reuses the deterministic Intelligence pieces (alignment, gap map, attack
surface, question graph, stories). Computed from the Goal's JD — never from
the "latest job" — so one Goal's gaps never leak into another.
"""
from __future__ import annotations

from typing import Any

from core.logger import get_logger

_log = get_logger("product.workspace")

STORY_CATEGORIES = ("Ownership", "Conflict", "Failure", "Leadership", "Ambiguity", "Collaboration",
                    "Difficult Problem", "Influence", "Trade-off", "Learning")
STORY_CATEGORY_LABELS = {
    "Ownership": "Ownership 担当", "Conflict": "冲突处理", "Failure": "失败与反思", "Leadership": "领导力",
    "Ambiguity": "模糊情境决策", "Collaboration": "协作", "Difficult Problem": "解决困难问题",
    "Influence": "影响他人", "Trade-off": "取舍", "Learning": "学习成长",
}
_CATEGORY_ALIASES = {
    "ownership": "Ownership", "担当": "Ownership", "负责": "Ownership",
    "conflict": "Conflict", "冲突": "Conflict", "分歧": "Conflict",
    "failure": "Failure", "失败": "Failure", "反思": "Failure",
    "leadership": "Leadership", "领导": "Leadership", "带团队": "Leadership",
    "ambiguity": "Ambiguity", "模糊": "Ambiguity", "不确定": "Ambiguity",
    "collaboration": "Collaboration", "协作": "Collaboration", "团队协作": "Collaboration", "合作": "Collaboration",
    "difficult problem": "Difficult Problem", "困难": "Difficult Problem", "难题": "Difficult Problem",
    "解决困难问题": "Difficult Problem",
    "influence": "Influence", "影响": "Influence", "推动": "Influence", "说服": "Influence",
    "trade-off": "Trade-off", "取舍": "Trade-off", "权衡": "Trade-off",
    "learning": "Learning", "学习": "Learning", "成长": "Learning",
}


def story_category(tag: str) -> str:
    text = (tag or "").strip().lower()
    for alias, category in _CATEGORY_ALIASES.items():
        if alias in text:
            return category
    return ""


def story_coverage(stories: list[dict[str, Any]]) -> dict[str, Any]:
    covered: dict[str, list[str]] = {c: [] for c in STORY_CATEGORIES}
    for story in stories:
        tags = story.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        cats = {story_category(str(t)) for t in [*tags, story.get("category", ""), story.get("title", "")]}
        for cat in cats:
            if cat:
                covered[cat].append(str(story.get("id", "")))
    missing = [c for c, ids in covered.items() if not ids]
    return {
        "categories": [{"key": c, "label": STORY_CATEGORY_LABELS[c], "story_ids": covered[c]} for c in STORY_CATEGORIES],
        "missing": [{"key": c, "label": STORY_CATEGORY_LABELS[c]} for c in missing],
    }


def goal_workspace(goal: dict[str, Any]) -> dict[str, Any]:
    """Gap Map / Attack Surface / Question Graph / Stories for this Goal."""
    jd = str(goal.get("jd") or "")
    empty = {"gap_map": [], "attack_surface": [], "question_graph": [], "stories": {"items": [], "prompts": []},
             "job": {}, "has_jd": bool(jd.strip())}
    try:
        from services.intelligence import job_workspace as jw
        from services.intelligence.job_representation import build_job_representation, compute_alignment

        claims = jw.active_claims()
        stories = jw.stored_stories()
        if not jd.strip():
            empty["attack_surface"] = jw.build_attack_surface(claims, [])
            empty["question_graph"] = jw.build_question_graph(empty["attack_surface"], [])
            empty["stories"] = jw.build_stories(stories, [], claims)
            return empty
        job = build_job_representation(jd, company=str(goal.get("company") or ""), role=str(goal.get("role") or ""))
        alignment = compute_alignment(
            job,
            jw.alignment_resume_text(""),
            claim_texts=[str(c.get("text", "")) for c in claims],
            claim_ids=[str(c.get("id", "")) for c in claims],
        )
        payload = job.payload() if hasattr(job, "payload") else dict(getattr(job, "__dict__", {}))
        ws = jw.compose_workspace(payload, alignment, claims, stories, jw.learning_signals())
        ws["job"] = {k: payload.get(k) for k in ("title", "company", "must_have", "technologies", "competencies")}
        ws["alignment"] = alignment
        ws["has_jd"] = True
        return ws
    except Exception as exc:  # noqa: BLE001 — Prepare must not break on intelligence errors
        _log.warning("goal workspace degraded for %s: %s", goal.get("id"), exc)
        return empty


def stories_list() -> list[dict[str, Any]]:
    try:
        from services.intelligence import job_workspace as jw

        out = []
        for story in jw.stored_stories():
            import json

            try:
                tags = json.loads(story.get("tags_json") or "[]")
            except (TypeError, ValueError):
                tags = []
            out.append({**story, "tags": tags})
        return out
    except Exception as exc:  # noqa: BLE001
        _log.warning("stories unavailable: %s", exc)
        return []
