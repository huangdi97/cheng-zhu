"""Route eval runner: deterministic evaluation of the Intelligence Core.

Evaluates question routing, open-world behavior and truth boundaries against
the fixed fixtures. No LLM calls: this runner measures the deterministic
layers (understanding, planner routing, truth boundary); provider-dependent
answer quality is measured separately (manual / nightly evals).
"""
from __future__ import annotations

from pathlib import Path

from core.logger import get_logger
from evals.fixtures.interview_fixtures import (
    ALL_FIXTURES,
    SEVEN_TURN_FORBIDDEN,
    SEVEN_TURN_QUESTIONS,
    SEVEN_TURN_RESUME,
)

_log = get_logger("evals.route_runner")


# Name-only aliases: fixture spellings for the SAME mode. These are not
# semantic leniency — "OPEN_DESIGN" never strictly matches "SYSTEM_DESIGN".
_NAME_ALIASES = {
    "EXPERIENCE_BOUNDARY": "EXPERIENCE_BOUNDARY_KNOWLEDGE",
    "EXPERIENCE+KNOWLEDGE": "EXPERIENCE_KNOWLEDGE",
    "EXPERIENCE+TRADEOFF": "EXPERIENCE_KNOWLEDGE",
    "KNOWLEDGE+CURRENT_CONTEXT": "KNOWLEDGE",
    "KNOWLEDGE+CURRENT_ARCHITECTURE": "KNOWLEDGE",
    "CASE": "PRODUCT_CASE",
}


def _canonical(name: str) -> str:
    value = (name or "").strip().upper().replace(" ", "_")
    return _NAME_ALIASES.get(value, value)


def _route_matches_strict(expected: str, actual_mode: str) -> bool:
    return _canonical(expected) == _canonical(actual_mode)


def _route_matches_semantic(expected: str, actual_mode: str) -> bool:
    from services.intelligence.semantics import SEMANTIC_COMPATIBLE

    exp, act = _canonical(expected), _canonical(actual_mode)
    return act == exp or act in SEMANTIC_COMPATIBLE.get(exp, set())


def _route_matches(expected: str, actual_mode: str, *, boundary_applicable: bool = False) -> bool:
    """Back-compat name: strict match only (R2 Stage H removed leniency)."""
    return _route_matches_strict(expected, actual_mode)


def _reconstruct_state(session_id: str, dialogue_history: list[dict]):
    from services.intelligence.interview_state import apply_event, reset_state

    reset_state(session_id)
    for turn in dialogue_history:
        question = str(turn.get("question", "") or "")
        if question:
            apply_event(session_id, "question_received", {"question": question})
    from services.intelligence.interview_state import get_state

    return get_state(session_id)


def run_route_eval(fixtures: list[dict] | None = None) -> dict:
    """Run the route/truth eval. Returns metrics + per-case results."""
    from services.intelligence.answer_planner import create_plan
    from services.intelligence.question_understanding import understand_question
    from services.intelligence.truth_boundary import analyze_truth_boundary
    from services.intelligence.semantics import provenance_from_grounding
    from services.intelligence.types import DepthProfile

    cases: list[dict] = []
    all_fixtures = fixtures if fixtures is not None else ALL_FIXTURES
    for fixture in all_fixtures:
        fixture_id = str(fixture.get("id", ""))
        question = str(fixture.get("question", "") or "")
        resume_text = str(fixture.get("resume_text", "") or "")
        history = list(fixture.get("dialogue_history") or [])
        session_id = f"eval-{fixture_id}"
        state = _reconstruct_state(session_id, history)
        previous_question = str(history[-1].get("question", "") or "") if history else ""
        understanding = understand_question(
            question,
            interview_state=state,
            previous_question=previous_question,
        )
        boundary = analyze_truth_boundary(question, resume_text=resume_text)
        plan = create_plan(
            understanding.question_type,
            resolved_question=understanding.resolved_question,
            intent=understanding.intent,
            expected_depth=DepthProfile.STRUCTURED,
            truth_status=boundary.truth_status.value,
            personal_fact_required=understanding.personal_fact_required,
            open_world_allowed=understanding.open_world_allowed,
            provenance=provenance_from_grounding(
                boundary.grounding.status,
                has_profile=bool(resume_text.strip()),
                question=question,
                profile_text=resume_text,
            ),
            raw_question=question,
            is_follow_up=understanding.is_follow_up,
        )
        matched = _route_matches_strict(str(fixture.get("expected_route", "")), plan.mode.value)
        semantic = _route_matches_semantic(str(fixture.get("expected_route", "")), plan.mode.value)
        type_matched = understanding.question_type.value == str(fixture.get("expected_question_type", "")).upper()
        cases.append(
            {
                "id": fixture_id,
                "category": str(fixture.get("category", "")),
                "expected": str(fixture.get("expected_route", "")),
                "actual": plan.mode.value,
                "question_type": understanding.question_type.value,
                "type_matched": type_matched,
                "matched": matched,
                "semantic_matched": semantic,
            }
        )

    route_accuracy = sum(1 for case in cases if case["matched"]) / max(1, len(cases))
    semantic_accuracy = sum(1 for case in cases if case["semantic_matched"]) / max(1, len(cases))
    type_accuracy = sum(1 for case in cases if case["type_matched"]) / max(1, len(cases))
    per_category: dict[str, dict] = {}
    for case in cases:
        bucket = per_category.setdefault(case["category"], {"total": 0, "matched": 0})
        bucket["total"] += 1
        if case["matched"]:
            bucket["matched"] += 1

    unsupported = _run_unsupported_claim_probe()
    fact_precision = _run_fact_precision_probe()
    return {
        "route_accuracy": round(route_accuracy, 4),
        "route_accuracy_exact": round(route_accuracy, 4),
        "route_accuracy_semantic": round(semantic_accuracy, 4),
        "type_accuracy": round(type_accuracy, 4),
        "per_category": per_category,
        "unsupported_claim_rate": unsupported["blocked_rate"],
        "unsupported_probe_total": unsupported["total"],
        "fact_precision": fact_precision["precision"],
        "fact_probe_total": fact_precision["total"],
        "cases": cases,
        "total": len(cases),
    }


def _run_unsupported_claim_probe() -> dict:
    """Probe: naive forbidden claims must be blocked by the truth boundary."""
    from services.intelligence.truth_boundary import analyze_truth_boundary, check_generated_answer

    probes: list[tuple[str, str]] = []
    for fixture in ALL_FIXTURES:
        for claim in fixture.get("forbidden_claims") or []:
            probes.append((str(fixture.get("id", "")), claim))
    for question_id, claims in SEVEN_TURN_FORBIDDEN.items():
        for claim in claims:
            probes.append((f"seven-{question_id}", claim))
    if not probes:
        return {"total": 0, "blocked_rate": 0.0}

    blocked = 0
    for fixture_id, claim in probes:
        boundary = analyze_truth_boundary(claim, resume_text=SEVEN_TURN_RESUME)
        result = check_generated_answer(claim, boundary=boundary, evidence_texts=[SEVEN_TURN_RESUME], question_text=claim)
        if result.fallback_used or not result.passed or result.final_text != claim:
            blocked += 1
        else:
            _log.warning("unsupported claim probe NOT blocked: fixture=%s claim=%r", fixture_id, claim[:60])
    return {"total": len(probes), "blocked_rate": round(blocked / len(probes), 4)}


def _run_fact_precision_probe() -> dict:
    """Probe: questions with resume evidence keep output_space PERSONAL_FACT."""
    from services.intelligence.truth_boundary import analyze_truth_boundary

    probes = [
        "你在项目里使用过 Redis 吗？",
        "你在项目里使用过 RAG 吗？",
        "你负责过核心检索链路吗？",
    ]
    precise = 0
    for question in probes:
        boundary = analyze_truth_boundary(question, resume_text=SEVEN_TURN_RESUME)
        if boundary.applicable and boundary.output_space.value == "PERSONAL_FACT":
            precise += 1
    return {"total": len(probes), "precision": round(precise / len(probes), 4)}


def write_report(result: dict, path: str) -> None:
    """Write a markdown eval report (backend/evals/reports/...)."""
    try:
        lines = [
            "# Chengzhu Route Eval Report",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| route_accuracy (exact) | {result['route_accuracy_exact']} |",
            f"| route_accuracy (semantic compatible) | {result['route_accuracy_semantic']} |",
            f"| type_accuracy | {result.get('type_accuracy', '')} |",
            f"| unsupported_claim_rate (blocked) | {result['unsupported_claim_rate']} |",
            f"| fact_precision | {result['fact_precision']} |",
            f"| total cases | {result['total']} |",
            "",
            "## Per category",
            "",
            "| Category | Matched / Total |",
            "| --- | --- |",
        ]
        for category, bucket in result.get("per_category", {}).items():
            lines.append(f"| {category} | {bucket['matched']} / {bucket['total']} |")
        lines.extend(["", "## Cases", ""])
        for case in result.get("cases", []):
            status = "PASS" if case["matched"] else "FAIL"
            lines.append(f"- [{status}] {case['id']}: expected={case['expected']} actual={case['actual']} type={case['question_type']}")
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines), encoding="utf-8")
    except OSError as exc:
        _log.warning("eval report write failed: %s", exc)


def run_seven_turn() -> dict:
    """Run ONLY the mandatory seven-turn fixture (canonical section 40)."""
    seven = [
        {
            "id": item["id"],
            "category": item["category"],
            "question": item["question"],
            "resume_text": SEVEN_TURN_RESUME,
            "dialogue_history": (
                [{"question": q["question"], "answer": ""} for q in SEVEN_TURN_QUESTIONS[: idx]]
                if item["id"] != "Q1"
                else []
            ),
            "expected_question_type": "",
            "expected_route": item["expected_route"],
            "forbidden_claims": SEVEN_TURN_FORBIDDEN.get(item["id"], []),
            "required_structure_hint": "",
        }
        for idx, item in enumerate(SEVEN_TURN_QUESTIONS)
    ]
    return run_route_eval(seven)
