"""Progress Trends (canonical §12) — per Goal / rubric dimension / delivery metric.

Reads rubric observations and delivery metrics of recent sessions and
describes direction in words ("结论时间 22s → 11s", "ownership 问题仍重复").
No percentile, no offer probability, no composite score.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Optional

from services.product.rubrics import DIMENSIONS
from services.storage import product as store

WINDOW = 5


def _sessions_levels(goal_id: Optional[str], window: int) -> "OrderedDict[str, dict[str, list[int]]]":
    where, params = ("goal_id = ?", (goal_id,)) if goal_id else ("", ())
    rows = store.select("rubric_observation", where, params, "created_at ASC")
    sessions: "OrderedDict[str, dict[str, list[int]]]" = OrderedDict()
    for row in rows:
        sessions.setdefault(row["session_ref"], {}).setdefault(row["dimension"], []).append(int(row["level"]))
    keys = list(sessions)[-window:]
    return OrderedDict((k, sessions[k]) for k in keys)


def _ttc_by_session(goal_id: Optional[str], window: int) -> list[tuple[str, float]]:
    sql = ("SELECT ps.id AS sid, pt.delivery_json AS delivery_json FROM practice_turn pt JOIN practice_session ps "
           "ON ps.id = pt.practice_id WHERE ps.status = 'DONE'")
    params: tuple[Any, ...] = ()
    if goal_id:
        sql += " AND ps.goal_id = ?"
        params = (goal_id,)
    sql += " ORDER BY ps.started_at ASC, pt.seq ASC"
    per: "OrderedDict[str, list[float]]" = OrderedDict()
    for row in store.rows(sql, params):
        ttc = ((row.get("delivery") or {}).get("metrics") or {}).get("time_to_conclusion_s")
        if ttc is not None:
            per.setdefault(row["sid"], []).append(float(ttc))
    out = [(sid, sum(v) / len(v)) for sid, v in per.items() if v]
    return out[-window:]


def trends(goal_id: Optional[str] = None, window: int = WINDOW) -> dict[str, Any]:
    sessions = _sessions_levels(goal_id, window)
    dims: list[dict[str, Any]] = []
    for dim, label in DIMENSIONS.items():
        series = [round(sum(v[dim]) / len(v[dim]), 2) for v in sessions.values() if v.get(dim)]
        if len(series) < 2:
            if series:
                dims.append({"dimension": dim, "label": label, "series": series, "direction": "INSUFFICIENT",
                             "text": f"{label}：只有 1 场数据"})
            continue
        first, last = series[0], series[-1]
        low_count = sum(1 for x in series if x <= 2)
        if last - first >= 0.5:
            direction, text = "IMPROVING", f"{label}更稳定（{first:.1f} → {last:.1f} 级）"
        elif first - last >= 0.5:
            direction, text = "DECLINING", f"{label}有回落（{first:.1f} → {last:.1f} 级）"
        elif low_count >= max(2, len(series) - 1):
            direction, text = "REPEATING", f"{label}问题仍在重复（最近 {len(series)} 场有 {low_count} 场偏弱）"
        else:
            direction, text = "STABLE", f"{label}基本持平"
        dims.append({"dimension": dim, "label": label, "series": series, "direction": direction, "text": text})

    ttc = _ttc_by_session(goal_id, window)
    delivery = None
    if len(ttc) >= 2:
        a, b = ttc[0][1], ttc[-1][1]
        delivery = {"metric": "time_to_conclusion_s", "series": [round(v, 1) for _, v in ttc],
                    "text": f"结论时间 {a:.0f}s → {b:.0f}s",
                    "direction": "IMPROVING" if b < a - 2 else "DECLINING" if b > a + 2 else "STABLE"}
    order = {"REPEATING": 0, "DECLINING": 1, "IMPROVING": 2, "STABLE": 3, "INSUFFICIENT": 4}
    dims.sort(key=lambda d: order[d["direction"]])
    return {"goal_id": goal_id, "sessions": len(sessions), "window": window, "dimensions": dims,
            "delivery": delivery,
            "note": "按场次的维度等级（1–4）和本地表达指标，不是总分、百分位或录用概率。"}
