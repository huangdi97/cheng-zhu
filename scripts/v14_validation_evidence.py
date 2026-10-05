#!/usr/bin/env python3
"""Generate deterministic v1.4 engineering-evidence artifacts.

Runs only against isolated temporary SQLite stores. The output is synthetic
engineering evidence, never real-user or PMF evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import core.config as config_module  # noqa: E402
from services.product import data_export, dogfood, validation  # noqa: E402
from services.storage import intelligence as intel_storage  # noqa: E402
from services.storage import job_tracker, prep_space, product, review  # noqa: E402


def _configure(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    product.DB_PATH = str(root / "product.db")
    intel_storage.DB_PATH = str(root / "intelligence.db")
    prep_space.DB_PATH = str(root / "prep.db")
    review.DB_PATH = str(root / "review.db")
    job_tracker.DB_PATH = str(root / "job_tracker.db")
    product._READY_PATHS.clear()  # noqa: SLF001
    product._COLUMNS_CACHE.clear()  # noqa: SLF001

    config_module._save_config = lambda cfg: True  # type: ignore[assignment]  # noqa: ARG005, SLF001
    config_module._config = config_module._raw_config().model_copy(deep=True)  # noqa: SLF001
    config_module._effective = None  # noqa: SLF001

    import services.product.data_export as data_export_module
    import services.storage.paths as storage_paths

    storage_paths.exports_dir = lambda: str(root)  # type: ignore[assignment]
    data_export_module.exports_dir = lambda: str(root)  # type: ignore[assignment]

    intel_storage.init_db()
    prep_space.init_db()
    review.init_db()
    job_tracker.init_db()
    product.init_db()
    config_module.clear_session_overlay()


def _run_week() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="chengzhu-v14-week-") as td:
        _configure(Path(td))
        original_now = product.now
        try:
            week = dogfood.run_week(lambda clock: setattr(product, "now", clock))
            return {
                "dogfood": week,
                "validation": validation.report(),
                "integrity": data_export.integrity(),
            }
        finally:
            product.now = original_now
            config_module.clear_session_overlay()


def _run_sessions(count: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"chengzhu-v14-{count}-") as td:
        _configure(Path(td))
        original_now = product.now
        try:
            run = dogfood.run_sessions(count, lambda clock: setattr(product, "now", clock))
            return {
                "dogfood": run,
                "validation": validation.report(),
                "integrity": data_export.integrity(),
            }
        finally:
            product.now = original_now
            config_module.clear_session_overlay()


def _markdown(payload: dict[str, Any]) -> str:
    week = payload["seven_day"]
    thirty = payload["thirty_session"]
    hundred = payload["hundred_session"]
    v = week["validation"]
    lines = [
        "# Chengzhu v1.4 Engineering Validation Evidence",
        "",
        "> Evidence type: SYNTHETIC_DOGFOOD. This is deterministic engineering evidence, not real-user evidence and not PMF proof.",
        "",
        "## Gate summary",
        "",
        f"- 7-day continuity: {'PASS' if week['dogfood']['passed'] else 'FAIL'}",
        f"- 30-session continuity: {'PASS' if thirty['dogfood']['passed'] else 'FAIL'}",
        f"- 7-day integrity: {'PASS' if week['integrity']['ok'] else 'FAIL'}",
        f"- 30-session integrity: {'PASS' if thirty['integrity']['ok'] else 'FAIL'}",
        f"- 100-session continuity: {'PASS' if hundred['dogfood']['passed'] else 'FAIL'}",
        f"- 100-session integrity: {'PASS' if hundred['integrity']['ok'] else 'FAIL'}",
        f"- real_user_validation: {v['real_user_validation']}",
        "",
        "## Seven-day continuity checks",
        "",
    ]
    lines += [f"- {'PASS' if ok else 'FAIL'}: {key}" for key, ok in week["dogfood"]["checks"].items()]
    lines += ["", "## Thirty-session continuity checks", ""]
    lines += [f"- {'PASS' if ok else 'FAIL'}: {key}" for key, ok in thirty["dogfood"]["checks"].items()]
    lines += ["", "## Hundred-session reliability checks", ""]
    lines += [f"- {'PASS' if ok else 'FAIL'}: {key}" for key, ok in hundred["dogfood"]["checks"].items()]
    for title, key in [
        ("A · Goal reuse", "A_goal_reuse"),
        ("B · Reflection → Prepare", "B_reflection_to_prepare"),
        ("C · Fast Cue usefulness signals", "C_fast_cue_usefulness"),
        ("D · Practice transfer", "D_practice_transfer"),
        ("E · Fact Inbox burden", "E_fact_inbox_burden"),
        ("F · Quick Notes / Pin value", "F_quick_notes_and_pins"),
    ]:
        lines += ["", f"## {title}", "", "    " + json.dumps(v[key], ensure_ascii=False)]
    lines += [
        "",
        "## Product friction audit",
        "",
        "    " + json.dumps(v["friction_audit"], ensure_ascii=False),
    ]
    lines += [
        "",
        "## Honest conclusion",
        "",
        "- PRODUCT_VALIDATION_INFRA_COMPLETE: supported by the local event store, six-question report, continuity dogfood and integrity checks.",
        "- REAL_USER_EVIDENCE_PENDING: still true.",
        "- PMF PROVEN: must not be claimed from this artifact.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=str(ROOT / "artifacts" / "validation"))
    args = parser.parse_args()
    out = Path(args.out_dir)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    payload = {
        "evidence_type": "SYNTHETIC_DOGFOOD",
        "real_user_evidence": "REAL_USER_EVIDENCE_PENDING",
        "seven_day": _run_week(),
        "thirty_session": _run_sessions(30),
        "hundred_session": _run_sessions(100),
    }
    (out / "v1.4-engineering-evidence.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "V1_4_ENGINEERING_VALIDATION.md").write_text(_markdown(payload), encoding="utf-8")

    ok = (
        payload["seven_day"]["dogfood"]["passed"]
        and payload["thirty_session"]["dogfood"]["passed"]
        and payload["hundred_session"]["dogfood"]["passed"]
        and payload["seven_day"]["integrity"]["ok"]
        and payload["thirty_session"]["integrity"]["ok"]
        and payload["hundred_session"]["integrity"]["ok"]
    )
    print(json.dumps({
        "ok": ok,
        "evidence_type": payload["evidence_type"],
        "seven_day": payload["seven_day"]["dogfood"]["passed"],
        "thirty_session": payload["thirty_session"]["dogfood"]["passed"],
        "hundred_session": payload["hundred_session"]["dogfood"]["passed"],
        "real_user_evidence": payload["real_user_evidence"],
        "out_dir": str(out),
    }, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
