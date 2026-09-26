"""Eval rubric thresholds (canonical Stage R). Pure data."""
from __future__ import annotations

ROUTE_RUBRIC = {
    "name": "route_eval",
    "description": "Question routing accuracy across all fixture categories",
    "metrics": ["route_accuracy", "type_accuracy"],
    "thresholds": {"route_accuracy_min": 0.9, "type_accuracy_min": 0.8},
}

TRUTH_RUBRIC = {
    "name": "truth_boundary",
    "description": "Unsupported personal claims blocked; resume evidence stays PERSONAL_FACT",
    "metrics": ["unsupported_claim_rate", "fact_precision"],
    "thresholds": {"unsupported_claim_rate_max": 0.05, "fact_precision_min": 0.9},
}

CONTEXT_RUBRIC = {
    "name": "context_compiler",
    "description": "Minimal sufficient context: precision within budget, no stale-topic pollution",
    "metrics": ["context_precision", "context_recall", "topic_leakage"],
    "thresholds": {"context_precision_min": 0.8, "topic_leakage_max": 0.1},
}

ALL_RUBRICS = [ROUTE_RUBRIC, TRUTH_RUBRIC, CONTEXT_RUBRIC]
