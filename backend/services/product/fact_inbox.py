"""Fact Inbox (canonical §6) — the product face of provenance.

Provenance, user assertion and session axes stay exactly as in the v1.2
core (services.intelligence.semantics). The inbox only *selects* unreviewed
claims worth the user's attention and offers one-click resolutions that go
through the same storage calls as the Facts API:

  - confirming never raises provenance; only adding a source does
  - "我参与" rewrites lead verbs to participation verbs, so the claim the
    live system may use is no stronger than what the user stands behind

Burden guard (canonical §6, v1.4 §21): local metrics per claim (first seen,
opened, resolved, dismissed, reopened) and a policy that shrinks the inbox
to HIGH-risk items + one batch card when backlog grows or dismissals are
frequent — instead of adding notifications.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from core.logger import get_logger
from services.product import events
from services.storage import product as store

_log = get_logger("product.fact_inbox")

_STATE_KEY = "fact_inbox_state"
_LEAD = re.compile(r"(负责|主导|牵头|独立完成|从零搭建|从0到1|一手|全权|带领)")
_PARTICIPATE = re.compile(r"(参与|协助|配合|支持|跟进)")
_METRIC = re.compile(r"\d+(?:\.\d+)?\s*(?:%|倍|万|千|亿|ms|QPS|qps|x|X|人|天)")
_LEAD_TO_PART = (("独立完成", "参与完成"), ("全权负责", "参与"), ("负责", "参与"), ("主导", "参与"),
                 ("牵头", "参与"), ("带领", "参与"), ("从零搭建", "参与搭建"))
PROVENANCE_SUPPORT_LABEL = {
    "DIRECT_EVIDENCE": "材料直接支持",
    "SUPPORTING_EVIDENCE": "材料部分支持",
    "NO_EVIDENCE": "材料中没有来源",
    "CONFLICTING_EVIDENCE": "材料与之冲突",
}
ACTIONS = ("LEAD", "PARTICIPATE", "CONFIRM", "DENY", "EDIT", "ADD_SOURCE", "MERGE", "DELETE_DRAFT",
           "PRACTICE", "QUICK_NOTE", "DISMISS", "OPEN")
BACKLOG_LIMIT = 15
DISMISS_RATE_LIMIT = 0.4


class FactInboxError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Local per-claim state (burden metrics)
# ---------------------------------------------------------------------------


def _load_state() -> dict[str, dict[str, Any]]:
    raw = store.meta_get(_STATE_KEY)
    try:
        data = json.loads(raw) if raw else {}
    except (TypeError, json.JSONDecodeError):
        data = {}
    return data if isinstance(data, dict) else {}


def _save_state(state: dict[str, dict[str, Any]]) -> None:
    store.meta_set(_STATE_KEY, json.dumps(state, ensure_ascii=False))


def _intel():
    from services.storage import intelligence as intel_storage

    return intel_storage


def _claims() -> list[dict[str, Any]]:
    try:
        intel = _intel()
        candidate_id = intel.active_candidate_id()
        return intel.list_claims(candidate_id) if candidate_id else []
    except Exception as exc:  # noqa: BLE001
        _log.warning("claims unavailable: %s", exc)
        return []


def _evidence_text(claim_id: str) -> str:
    try:
        intel = _intel()
        ids = set(intel.claim_evidence_ids(claim_id))
        if not ids:
            return ""
        rows = intel.list_evidence(intel.active_candidate_id(), limit=2000)
        return "\n".join(str(r.get("text") or "") for r in rows if r.get("id") in ids)
    except Exception:  # noqa: BLE001
        return ""


def _structured(claim: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(claim.get("structured_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        data = {}
    return data if isinstance(data, dict) else {}


def assess(claim: dict[str, Any]) -> dict[str, Any]:
    """Risk + what the material actually supports, for one claim."""
    text = str(claim.get("text") or "")
    prov = str(claim.get("provenance_status") or "NO_EVIDENCE")
    evidence = _evidence_text(str(claim.get("id")))
    lead = bool(_LEAD.search(text))
    metric = bool(_METRIC.search(text))
    supported = PROVENANCE_SUPPORT_LABEL.get(prov, prov)
    if lead and evidence and not _LEAD.search(evidence) and _PARTICIPATE.search(evidence):
        supported = "参与（材料里没有主导的说法）"
    if prov == "CONFLICTING_EVIDENCE":
        risk = "HIGH"
    elif lead and prov != "DIRECT_EVIDENCE":
        risk = "HIGH"
    elif lead and supported.startswith("参与"):
        risk = "HIGH"
    elif metric and prov != "DIRECT_EVIDENCE":
        risk = "HIGH"
    elif prov == "NO_EVIDENCE":
        risk = "MEDIUM"
    else:
        risk = "LOW"
    return {"risk": risk, "supported_label": supported, "lead_language": lead, "has_metric": metric}


def _card(claim: dict[str, Any]) -> dict[str, Any]:
    structured = _structured(claim)
    a = assess(claim)
    return {
        "id": claim["id"],
        "text": claim.get("text", ""),
        "project": structured.get("project") or structured.get("project_name") or claim.get("source", ""),
        "source": claim.get("source", ""),
        "provenance_status": claim.get("provenance_status") or "NO_EVIDENCE",
        "user_assertion_status": claim.get("user_assertion_status") or "UNREVIEWED",
        **a,
        "primary_actions": ["LEAD", "PARTICIPATE", "EDIT", "VIEW_SOURCE"] if a["lead_language"]
        else ["CONFIRM", "DENY", "EDIT", "VIEW_SOURCE"],
        "more_actions": ["ADD_SOURCE", "MERGE", "DELETE_DRAFT", "PRACTICE", "QUICK_NOTE", "DISMISS"],
    }


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[一-鿿]{2}|[A-Za-z][A-Za-z0-9+#.\-]+", (text or "").lower()))


def merge_suggestions(cards: list[dict[str, Any]]) -> list[list[str]]:
    groups: list[list[str]] = []
    used: set[str] = set()
    for i, a in enumerate(cards):
        if a["id"] in used:
            continue
        ta = _tokens(a["text"])
        group = [a["id"]]
        for b in cards[i + 1:]:
            if b["id"] in used:
                continue
            tb = _tokens(b["text"])
            if ta and tb and len(ta & tb) / max(1, min(len(ta), len(tb))) >= 0.7:
                group.append(b["id"])
                used.add(b["id"])
        if len(group) > 1:
            used.add(a["id"])
            groups.append(group)
    return groups


def policy(state: Optional[dict[str, dict[str, Any]]] = None) -> dict[str, Any]:
    state = state if state is not None else _load_state()
    m = _metrics_from_state(state)
    reasons = []
    if m["backlog_size"] > BACKLOG_LIMIT:
        reasons.append("BACKLOG_GROWING")
    if m["handled"] >= 5 and m["dismiss_rate"] > DISMISS_RATE_LIMIT:
        reasons.append("HIGH_DISMISS_RATE")
    return {"mode": "HIGH_ONLY" if reasons else "STANDARD", "reasons": reasons}


def inbox_items(limit: int = 30, mode: str = "") -> list[dict[str, Any]]:
    """Unreviewed claims that need the user, risk-ordered, honoring dismissals."""
    state = _load_state()
    cards: list[dict[str, Any]] = []
    now = store.now()
    changed = False
    for claim in _claims():
        if str(claim.get("type") or "fact") != "fact":
            continue
        cid = str(claim["id"])
        entry = state.get(cid, {})
        if str(claim.get("user_assertion_status") or "UNREVIEWED") != "UNREVIEWED":
            continue
        if entry.get("status") == "DISMISSED":
            continue
        if entry.get("status") == "RESOLVED":
            # came back unreviewed (e.g. resume re-import): count as reopened
            entry.update({"status": "OPEN", "reopened": int(entry.get("reopened", 0)) + 1})
            events.record("fact_reopened")
            changed = True
        card = _card(claim)
        if card["risk"] == "LOW" and card["provenance_status"] == "DIRECT_EVIDENCE":
            continue
        if "first_seen" not in entry:
            entry.update({"first_seen": now, "status": "OPEN", "risk": card["risk"]})
            events.record("fact_inbox_created", risk=card["risk"])
            changed = True
        state[cid] = entry
        cards.append(card)
    if changed:
        _save_state(state)
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    cards.sort(key=lambda c: order.get(c["risk"], 3))
    mode = mode or policy(state)["mode"]
    if mode == "HIGH_ONLY":
        cards = [c for c in cards if c["risk"] == "HIGH"]
    return cards[:limit]


def inbox(limit: int = 30) -> dict[str, Any]:
    all_items = inbox_items(limit=500, mode="STANDARD")  # registers new items first
    pol = policy()
    items = [c for c in all_items if c["risk"] == "HIGH"][:limit] if pol["mode"] == "HIGH_ONLY" else all_items[:limit]
    batched = [c for c in all_items if c["risk"] != "HIGH"] if pol["mode"] == "HIGH_ONLY" else \
        [c for c in items if c["risk"] == "LOW"]
    individual = [c for c in items if c not in batched]
    return {
        "count": len(individual) + (1 if batched else 0),
        "items": individual,
        "batch": {"count": len(batched), "ids": [c["id"] for c in batched]} if batched else None,
        "merge_suggestions": merge_suggestions(individual),
        "policy": pol,
    }


def mark_opened() -> None:
    state = _load_state()
    now = store.now()
    for entry in state.values():
        if entry.get("status") == "OPEN" and "opened_at" not in entry:
            entry["opened_at"] = now
    _save_state(state)
    events.record("fact_inbox_opened", backlog=sum(1 for e in state.values() if e.get("status") == "OPEN"))


def _mark(claim_id: str, status: str) -> None:
    state = _load_state()
    entry = state.setdefault(claim_id, {"first_seen": store.now()})
    entry["status"] = status
    entry[f"{status.lower()}_at"] = store.now()
    _save_state(state)
    if status == "RESOLVED":
        events.record("fact_resolved", seconds=int(entry["resolved_at"] - float(entry.get("first_seen", entry["resolved_at"]))))
    elif status == "DISMISSED":
        events.record("fact_dismissed")


def _find_claim(claim_id: str) -> dict[str, Any]:
    for claim in _claims():
        if str(claim["id"]) == claim_id:
            return claim
    raise FactInboxError("事实不存在")


def to_participation(text: str) -> str:
    out = text
    for strong, weak in _LEAD_TO_PART:
        out = out.replace(strong, weak)
    return out


def resolve(claim_id: str, action: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Apply one inbox action through the same storage paths as the Facts API."""
    payload = payload or {}
    if action not in ACTIONS:
        raise FactInboxError(f"未知操作：{action}")
    intel = _intel()
    claim = _find_claim(claim_id)
    result: dict[str, Any] = {"id": claim_id, "action": action}
    if action in ("LEAD", "PARTICIPATE", "CONFIRM"):
        structured = {**_structured(claim), "ownership": {"LEAD": "LEAD", "PARTICIPATE": "PARTICIPATE"}.get(action, "")}
        if action == "PARTICIPATE":
            _save_text(claim, to_participation(str(claim.get("text") or "")))
        intel.update_claim_axes(claim_id, provenance_status=None, user_assertion_status="USER_CONFIRMED",
                                structured=structured, source_ids=None)
        _mark(claim_id, "RESOLVED")
    elif action == "DENY":
        intel.update_claim_axes(claim_id, provenance_status=None, user_assertion_status="USER_DENIED",
                                structured=None, source_ids=None)
        _mark(claim_id, "RESOLVED")
    elif action == "EDIT":
        text = str(payload.get("text") or "").strip()
        if not text:
            raise FactInboxError("修改后的内容不能为空")
        _save_text(claim, text)
        intel.update_claim_axes(claim_id, provenance_status=None, user_assertion_status="USER_CONFIRMED",
                                structured=None, source_ids=None)
        _mark(claim_id, "RESOLVED")
    elif action == "ADD_SOURCE":
        source_ids = [str(s) for s in payload.get("source_ids") or [] if s]
        source_text = str(payload.get("source_text") or "").strip()
        if source_text:
            evidence_id = f"ev_user_{store.new_id()}"
            intel.save_evidence_batch(intel.active_candidate_id(), [{
                "id": evidence_id, "source": "user_added", "text": source_text[:2000], "kind": "user_source",
            }], [])
            source_ids.append(evidence_id)
        if not source_ids:
            raise FactInboxError("请提供来源")
        intel.update_claim_axes(claim_id, provenance_status="SUPPORTING_EVIDENCE", user_assertion_status=None,
                                structured=None, source_ids=source_ids)
        intel.save_evidence_batch(intel.active_candidate_id(), [], [(claim_id, s) for s in source_ids])
        result["source_ids"] = source_ids
    elif action == "MERGE":
        others = [str(i) for i in payload.get("merge_ids") or [] if str(i) != claim_id]
        if not others:
            raise FactInboxError("请选择要合并的事实")
        links = []
        for other in others:
            links += [(claim_id, sid) for sid in intel.claim_evidence_ids(other)]
            intel.delete_claim(other)
            _mark(other, "RESOLVED")
        if links:
            intel.save_evidence_batch(intel.active_candidate_id(), [], links)
        result["merged"] = others
    elif action == "DELETE_DRAFT":
        if str(claim.get("user_assertion_status") or "UNREVIEWED") != "UNREVIEWED":
            raise FactInboxError("只有未确认的草稿可以删除")
        intel.delete_claim(claim_id)
        _mark(claim_id, "RESOLVED")
    elif action == "DISMISS":
        _mark(claim_id, "DISMISSED")
    elif action == "PRACTICE":
        goal_id = str(payload.get("goal_id") or "")
        if not goal_id:
            raise FactInboxError("请选择要练习的求职目标")
        from services.product.next_focus import set_user_focus

        result["next_focus"] = set_user_focus(goal_id, "FACT_BOUNDARY", str(claim.get("text") or "")[:60],
                                              "你选择练习这条事实的边界表达。", source_kind="FACT", source_ref=claim_id)
    elif action == "QUICK_NOTE":
        from services.product.quick_notes import create_note

        result["quick_note"] = create_note(
            str(payload.get("content") or claim.get("text") or ""), title="事实边界",
            scope="GOAL" if payload.get("goal_id") else "GLOBAL", goal_id=payload.get("goal_id") or None,
        )
    return result


def _save_text(claim: dict[str, Any], text: str) -> None:
    intel = _intel()
    intel.save_claims(claim["candidate_id"], [{
        "id": claim["id"], "type": claim.get("type", "fact"), "text": text, "source": claim.get("source", ""),
        "truth_status": claim.get("truth_status", "UNKNOWN"), "confidence": claim.get("confidence", 0.5),
        "provenance_status": claim.get("provenance_status") or "NO_EVIDENCE",
    }])


def batch_resolve(claim_ids: list[str], action: str) -> dict[str, Any]:
    if action not in ("CONFIRM", "DENY", "DISMISS"):
        raise FactInboxError("批量操作只支持 确认 / 否认 / 暂不处理")
    done, failed = [], []
    for cid in claim_ids:
        try:
            resolve(cid, action)
            done.append(cid)
        except FactInboxError:
            failed.append(cid)
    return {"done": done, "failed": failed}


def _metrics_from_state(state: dict[str, dict[str, Any]]) -> dict[str, Any]:
    resolved = [e for e in state.values() if e.get("status") == "RESOLVED"]
    dismissed = [e for e in state.values() if e.get("status") == "DISMISSED"]
    open_items = [e for e in state.values() if e.get("status") == "OPEN"]
    durations = sorted(float(e["resolved_at"]) - float(e.get("first_seen", e["resolved_at"])) for e in resolved
                       if "resolved_at" in e)
    median = durations[len(durations) // 2] if durations else None
    now = store.now()
    ages = [now - float(e.get("first_seen", now)) for e in open_items]
    handled = len(resolved) + len(dismissed)
    return {
        "inbox_created": len(state),
        "opened": sum(1 for e in state.values() if "opened_at" in e),
        "resolved": len(resolved),
        "dismissed": len(dismissed),
        "handled": handled,
        "backlog_size": len(open_items),
        "resolution_rate": round(len(resolved) / len(state), 3) if state else None,
        "dismiss_rate": round(len(dismissed) / handled, 3) if handled else 0.0,
        "median_time_to_resolve_s": round(median, 1) if median is not None else None,
        "oldest_backlog_age_s": round(max(ages), 1) if ages else None,
        "reopened": sum(int(e.get("reopened", 0)) for e in state.values()),
    }


def metrics() -> dict[str, Any]:
    state = _load_state()
    return {**_metrics_from_state(state), "policy": policy(state)}
