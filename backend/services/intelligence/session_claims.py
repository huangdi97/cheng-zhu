"""Session Claims (R2 Stage E): what the candidate said aloud this session.

The v1.x idea "the user said it, keep later answers consistent with it" is
retired. A statement made live without a source is recorded as

    session_status = SESSION_STATED, provenance = NO_EVIDENCE

and may only drive:
  - a private consistency warning with a same-session correction entry,
  - prompt constraints that FORBID expanding it (no new metric / role /
    architecture detail to "round out" the earlier statement),
  - a Review item where the user can confirm / deny / add a source.

 INVARIANT:
  - Never promoted to a long-term Claim here; only Review can create one.
  - Never used as factual evidence for later answers.
  - SESSION_CORRECTED statements are never used again in this session.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

from core.logger import get_logger
from services.intelligence.semantics import ProvenanceStatus, SessionStatus

_log = get_logger("intelligence.session_claims")

# First-person experience statements in the candidate's actual speech.
_STATEMENT = re.compile(
    r"(?:我|我们|本人)(?:当时|之前|后来|实际|在[^，,。]{0,12})?"
    r"(?:用了|用过|使用了|使用过|做过|做了|负责|负责过|主导|上线了|部署了|搭建了|实现了|落地了|引入了)"
    r"[^，,。！!？?；;]{2,60}",
)
_SENTENCE_SPLIT = re.compile(r"[。！!？?；;\n]")
_TERMS = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]*(?:\s+[A-Z][A-Za-z0-9+#.\-]*)*|[一-鿿]{2,6}")
_STOP_TERMS = {"我们", "当时", "之前", "后来", "实际", "使用", "负责", "主导", "上线", "部署", "搭建", "实现", "落地", "引入", "用了", "做过", "生产"}

ACTIONS = {
    "slip": "这是口误",
    "continue_no_expand": "继续，但不要扩展细节",
    "later": "稍后确认",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _claim_id(session_id: str, normalized: str) -> str:
    return "sc-" + hashlib.sha1(f"{session_id}|{normalized}".encode("utf-8")).hexdigest()[:14]


def extract_statements(text: str) -> list[str]:
    out: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(text or ""):
        for match in _STATEMENT.finditer(sentence):
            statement = match.group(0).strip()
            if statement and statement not in out:
                out.append(statement)
    return out


def key_terms(text: str) -> list[str]:
    terms = []
    for raw in _TERMS.findall(text or ""):
        term = raw.strip()
        if len(term) < 2 or term in _STOP_TERMS:
            continue
        terms.append(term.lower())
    return terms


def coverage(statement: str, pack) -> ProvenanceStatus:
    """Does the frozen pack hold a source for every distinctive term?"""
    corpus = " ".join(
        [pack.profile_text]
        + [str(c.get("text", "")) for c in pack.claims if c.get("user_assertion_status") != "USER_DENIED"]
        + [str(e.get("text", "")) for e in pack.evidence_refs]
    ).lower()
    ascii_terms = [t for t in key_terms(statement) if re.match(r"[a-z]", t)]
    terms = ascii_terms or key_terms(statement)
    if not terms:
        return ProvenanceStatus.NO_EVIDENCE
    if all(term in corpus for term in terms):
        return ProvenanceStatus.DIRECT_EVIDENCE
    return ProvenanceStatus.NO_EVIDENCE


def warning_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "session_claim_warning",
        "id": row["id"],
        "qa_id": row.get("qa_id", ""),
        "text": row["text"],
        "message": f"你刚才提到“{row['text']}”。当前 Interview Pack 没有材料支持这一陈述。",
        "actions": [{"id": key, "label": label} for key, label in ACTIONS.items()],
        "private": True,
    }


def record_candidate_speech(session_id: str, pack, text: str, *, qa_id: str = "") -> list[dict[str, Any]]:
    """Record first-person statements; return warnings for unsourced ones."""
    from services.storage import intelligence as storage

    warnings: list[dict[str, Any]] = []
    for statement in extract_statements(text):
        normalized = _normalize(statement)
        claim_id = _claim_id(session_id, normalized)
        existing = storage.get_session_claim(claim_id)
        if existing and existing.get("session_status") == SessionStatus.SESSION_CORRECTED.value:
            continue
        prov = coverage(statement, pack)
        row = {
            "id": claim_id,
            "session_id": session_id,
            "pack_id": getattr(pack, "id", "") or "",
            "text": statement,
            "normalized": normalized,
            "session_status": SessionStatus.SESSION_STATED.value,
            "provenance_status": prov.value,
            "review_state": (existing or {}).get("review_state", "PENDING"),
            "qa_id": qa_id,
        }
        storage.upsert_session_claim(row)
        if prov == ProvenanceStatus.NO_EVIDENCE and not existing:
            warnings.append(warning_payload(row))
    return warnings


def resolve(claim_id: str, action: str) -> Optional[dict[str, Any]]:
    """Same-session correction entry (private overlay buttons)."""
    from services.storage import intelligence as storage

    row = storage.get_session_claim(claim_id)
    if row is None or action not in ACTIONS:
        return None
    if action == "slip":
        row["session_status"] = SessionStatus.SESSION_CORRECTED.value
        row["review_state"] = "CORRECTED"
    elif action == "continue_no_expand":
        row["review_state"] = "HOLD_NO_EXPAND"
    else:
        row["review_state"] = "PENDING"
    storage.upsert_session_claim(row)
    return row


def session_status_for(session_id: str, question: str) -> SessionStatus:
    """Was the subject of this question stated / corrected this session?"""
    from services.storage import intelligence as storage

    q_terms = set(key_terms(question))
    if not q_terms:
        return SessionStatus.NOT_STATED
    status = SessionStatus.NOT_STATED
    for row in storage.list_session_claims(session_id):
        if not q_terms & set(key_terms(row.get("text", ""))):
            continue
        if row.get("session_status") == SessionStatus.SESSION_CORRECTED.value:
            return SessionStatus.SESSION_CORRECTED
        status = SessionStatus.SESSION_STATED
    return status


def prompt_constraints(session_id: str) -> str:
    """Constraints for the answer prompt. Unsourced statements are listed so
    the model does NOT build on them; corrected ones must not be reused."""
    from services.storage import intelligence as storage

    stated, corrected = [], []
    for row in storage.list_session_claims(session_id):
        if row.get("session_status") == SessionStatus.SESSION_CORRECTED.value:
            corrected.append(row["text"])
        elif row.get("provenance_status") == ProvenanceStatus.NO_EVIDENCE.value:
            stated.append(row["text"])
    lines = []
    if stated:
        lines.append(
            "[本场口述但暂无来源的陈述] 不要把它们当作事实依据，不要扩展细节、不要补充指标/角色/架构来圆前文："
            + "；".join(f"「{t}」" for t in stated[-5:])
        )
    if corrected:
        lines.append("[候选人已标记为口误] 禁止再使用：" + "；".join(f"「{t}」" for t in corrected[-5:]))
    return "\n".join(lines)


def review_items(session_id: str) -> list[dict[str, Any]]:
    from services.storage import intelligence as storage

    return [
        {
            "id": row["id"],
            "text": row["text"],
            "session_status": row["session_status"],
            "provenance_status": row["provenance_status"],
            "review_state": row["review_state"],
            "qa_id": row.get("qa_id", ""),
        }
        for row in storage.list_session_claims(session_id)
    ]


def confirm_in_review(claim_id: str, *, candidate_id: str, decision: str) -> Optional[dict[str, Any]]:
    """Review is the only place a session statement can become long-term.

    decision:
      confirm -> long-term claim, provenance NO_EVIDENCE (unless it was
                 covered), user_assertion USER_CONFIRMED. Confirmation is
                 not evidence; the axes stay separate.
      deny    -> long-term claim with USER_DENIED so it can never be used.
      forget  -> nothing is remembered.
    """
    from services.storage import intelligence as storage

    row = storage.get_session_claim(claim_id)
    if row is None:
        return None
    if decision == "forget":
        row["review_state"] = "FORGOTTEN"
        storage.upsert_session_claim(row)
        return {"id": claim_id, "long_term_claim_id": ""}
    if decision not in {"confirm", "deny"}:
        return None
    long_id = "claim-" + claim_id[3:]
    storage.save_claims(
        candidate_id,
        [
            {
                "id": long_id,
                "type": "fact",
                "text": row["text"],
                "source": "session_statement",
                "truth_status": "UNKNOWN",
                "confidence": 0.3,
                "metadata": {"session_id": row["session_id"], "session_claim_id": claim_id},
            }
        ],
    )
    storage.update_claim_axes(
        long_id,
        provenance_status=row.get("provenance_status", "NO_EVIDENCE"),
        user_assertion_status="USER_CONFIRMED" if decision == "confirm" else "USER_DENIED",
    )
    row["review_state"] = "CONFIRMED" if decision == "confirm" else "DENIED"
    storage.upsert_session_claim(row)
    return {"id": claim_id, "long_term_claim_id": long_id}
