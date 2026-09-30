"""Render the latency benchmark JSON into markdown tables for the forensics report.

    python scripts/render_latency_report.py [reports/perf/latency_bench.json]

Prints markdown to stdout; the report embeds it verbatim so every number in
the report comes from the committed JSON.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODE_LABEL = {
    "baseline": "baseline (v1.x path)",
    "r2_prev": "r2_prev (f04f217, old frontend)",
    "local": "**final · Local CPU profile**",
    "streaming_sim": "**final · Streaming profile (SIMULATED provider)**",
}


def ms(v):
    return "—" if v is None else f"{v / 1000:.2f} s"


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reports" / "perf" / "latency_bench.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    summary, stages, load = data["summary"], data["stages"], data.get("load", {})
    out = [f"Generated {data['generated_at']} · {data['machine']['stt']} · {data['machine']['cpu_threads']} CPU threads", ""]
    out += ["### Headline (TTFUG_user = first useful cue on screen − ground-truth speech end)", "",
            "| Mode | n | TTFUG_user p50 | p95 | QBD p50 | p95 | TTFUG_internal p50 | question ok | no question | cue before deep |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for mode, s in summary.items():
        out.append(
            f"| {MODE_LABEL.get(mode, mode)} | {s['n']} | {ms(s['ttfug_user_ms']['p50'])} | {ms(s['ttfug_user_ms']['p95'])} | "
            f"{ms(s['qbd_ms']['p50'])} | {ms(s['qbd_ms']['p95'])} | {ms(s['ttfug_internal_ms']['p50'])} | "
            f"{s['question_ok_rate']:.3f} | {len(s['errors'])} | {s['cue_before_deep_rate']:.2f} |"
        )
    out += ["", "### Safety rates", "",
            "| Mode | premature end | premature cue | question replaced | provisional cues (same / corrected / replaced) | cards rendered >1× | false trigger on silence |",
            "|---|---|---|---|---|---|---|"]
    for mode, s in summary.items():
        rel = s["provisional_relations"]
        out.append(
            f"| {MODE_LABEL.get(mode, mode)} | {s['premature_end_rate']:.3f} | {s['premature_cue_rate']:.3f} | {s['question_replacement_rate']:.3f} | "
            f"{s['provisional_emitted']} ({rel['same']} / {rel['corrected']} / {rel['replaced']}) | {s['multi_render_cards']} | {s['false_trigger_on_silence']} |"
        )
    out += ["", "### Forensic time points (median ms after ground-truth speech end E)", "",
            "| Point | " + " | ".join(MODE_LABEL.get(m, m) for m in stages) + " |",
            "|---|" + "---|" * len(stages)]
    names = list(next(iter(stages.values())).keys())
    for name in names:
        cells = []
        for mode in stages:
            v = stages[mode][name]
            cells.append("—" if v["p50_ms_after_E"] is None else f"{v['p50_ms_after_E']} (n={v['n']})")
        out.append(f"| {name} | " + " | ".join(cells) + " |")
    out += ["", "### Machine load during each mode (calibration = one fixed zh-short decode; ~0.8 s when the CPU is quiet)", "",
            "| Mode | repeat | CPU before | calib. before | CPU after | calib. after |", "|---|---|---|---|---|---|"]
    for mode, reps in load.items():
        for rep in reps:
            b, a = rep.get("before", {}), rep.get("after", {})
            out.append(f"| {mode} | {rep['repeat']} | {b.get('system_cpu_percent')}% | {b.get('calibration_decode_ms')} ms | "
                       f"{a.get('system_cpu_percent')}% | {a.get('calibration_decode_ms')} ms |")
    out += ["", "### Errors (no question submitted)", ""]
    for mode, s in summary.items():
        out.append(f"- {mode}: {', '.join(s['errors']) or 'none'}")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
