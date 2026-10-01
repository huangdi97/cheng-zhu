"""Role-specific rubrics (canonical §11).

A rubric is a set of dimensions with public per-role weights and level
descriptors (1–4). It is never collapsed into a hiring probability or a
single composite score: observations stay per dimension and the weights are
only used to order which dimension to work on next.
"""
from __future__ import annotations

from typing import Any

DIMENSIONS: dict[str, str] = {
    "technical_correctness": "技术正确性",
    "depth": "深度",
    "trade_off": "取舍",
    "ownership": "Ownership",
    "impact": "影响 / 结果",
    "communication": "表达",
    "evidence_discipline": "证据纪律",
    "followup_resilience": "追问韧性",
}

LEVELS: dict[int, str] = {
    1: "未体现",
    2: "有提及，缺细节",
    3: "清楚，有具体细节",
    4: "清楚、具体，并主动说明边界与取舍",
}

ROLE_LABELS: dict[str, str] = {
    "SWE": "Software Engineer",
    "AI_ML": "AI / ML Engineer",
    "AI_PM": "AI Product Manager",
    "DATA_ML": "Data / ML",
    "PRODUCT": "General Product",
}

# Public weights (sum to 100 per role). Used only to rank what to improve.
ROLE_WEIGHTS: dict[str, dict[str, int]] = {
    "SWE": {"technical_correctness": 20, "depth": 18, "trade_off": 15, "ownership": 12, "impact": 10,
            "communication": 10, "evidence_discipline": 7, "followup_resilience": 8},
    "AI_ML": {"technical_correctness": 18, "depth": 18, "trade_off": 16, "ownership": 10, "impact": 10,
              "communication": 8, "evidence_discipline": 12, "followup_resilience": 8},
    "AI_PM": {"technical_correctness": 8, "depth": 10, "trade_off": 18, "ownership": 14, "impact": 18,
              "communication": 16, "evidence_discipline": 8, "followup_resilience": 8},
    "DATA_ML": {"technical_correctness": 18, "depth": 15, "trade_off": 12, "ownership": 10, "impact": 15,
                "communication": 10, "evidence_discipline": 12, "followup_resilience": 8},
    "PRODUCT": {"technical_correctness": 5, "depth": 10, "trade_off": 18, "ownership": 15, "impact": 20,
                "communication": 18, "evidence_discipline": 6, "followup_resilience": 8},
}

# Content-coach signal -> rubric dimension
SIGNAL_TO_DIMENSION: dict[str, str] = {
    "did_answer_question": "technical_correctness",
    "technical_depth": "depth",
    "trade_off": "trade_off",
    "ownership": "ownership",
    "evidence": "impact",
    "structure": "communication",
    "truth_boundary": "evidence_discipline",
    "followup_resilience": "followup_resilience",
}


def rubric_for(role_family: str) -> dict[str, Any]:
    family = role_family if role_family in ROLE_WEIGHTS else "SWE"
    weights = ROLE_WEIGHTS[family]
    return {
        "role_family": family,
        "label": ROLE_LABELS[family],
        "levels": LEVELS,
        "dimensions": [
            {"key": key, "label": DIMENSIONS[key], "weight": weights[key]}
            for key in sorted(weights, key=lambda k: -weights[k])
        ],
        "note": "权重公开，仅用于决定下一步先练什么；不输出总分或录用概率。",
    }


def all_rubrics() -> list[dict[str, Any]]:
    return [rubric_for(f) for f in ROLE_WEIGHTS]


def priority_gaps(role_family: str, levels: dict[str, float]) -> list[dict[str, Any]]:
    """Dimensions ordered by weighted shortfall from level 4 (no total score)."""
    weights = ROLE_WEIGHTS.get(role_family, ROLE_WEIGHTS["SWE"])
    gaps = []
    for key, level in levels.items():
        if key not in weights:
            continue
        shortfall = max(0.0, 4.0 - float(level))
        if shortfall <= 0.5:
            continue
        gaps.append({"dimension": key, "label": DIMENSIONS[key], "level": round(float(level), 1),
                     "weight": weights[key], "rank_value": round(shortfall * weights[key], 1)})
    return sorted(gaps, key=lambda g: -g["rank_value"])
