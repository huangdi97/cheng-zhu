#!/usr/bin/env python3
"""Build a local Conversation v2 pilot-cohort manifest from product.db.

The builder reduces clerical errors; it does not verify identity, consent,
authorization, real-world use, or incident status.

Default output is deliberately a DRAFT that stable-readiness will reject.
A final AUTHORIZED_REAL_CONVERSATION_PILOT manifest requires:
- explicit --finalize;
- every required --attest value supplied by the operator;
- explicit --critical-incidents;
- only ended PROJECT_SYNC / DESIGN_REVIEW sessions selected from product.db;
- each selected Session has consent acknowledgement and a matching Frozen Session Pack;
- every selected Session in one Conversation Space binds to the same pseudonymous user_ref.

No transcript text, participant names, Space titles, or other content is copied
into the manifest. user_ref is a local pseudonymous cohort key, not identity
proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CONTRACT_VERSION = "v2.0-R1-pilot-cohort-2"
FINAL_EVIDENCE_TYPE = "AUTHORIZED_REAL_CONVERSATION_PILOT"
DRAFT_EVIDENCE_TYPE = "DRAFT_AUTHORIZED_REAL_CONVERSATION_PILOT"
REQUIRED_PROFILES = ("PROJECT_SYNC", "DESIGN_REVIEW")
CROSS_SESSION_SPACE_MIN_SESSIONS = 3
CROSS_SESSION_SPACE_USER_BINDING = "SINGLE_PSEUDONYMOUS_USER_REF"
REQUIRED_ATTESTATIONS = (
    "AUTHORIZED_REAL_USE",
    "NO_SYNTHETIC_ROWS_IN_HUMAN_EVAL",
    "RAW_LABELS_KEPT_LOCAL",
    "NO_CRITICAL_PRIVACY_INCIDENT",
    "NO_KNOWN_DATA_LOSS",
)
_USER_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


def _finite_timestamp(value: Any, field: str, session_id: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{session_id}: {field} 缺失")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{session_id}: {field} 无效")
    return number


def _iso_utc(timestamp: float) -> str:
    return (
        datetime.fromtimestamp(timestamp, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _canonical_json_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validated_session_fact(row: dict[str, Any], session_id: str) -> dict[str, Any]:
    pack_id = str(row.get("pack_id") or "").strip()
    frozen_pack_id = str(row.get("frozen_pack_id") or "").strip()
    stored_digest = str(row.get("frozen_pack_digest") or "").strip()
    payload_text = str(row.get("frozen_pack_payload_json") or "")

    if not pack_id or frozen_pack_id != pack_id:
        raise ValueError(f"{session_id}: 缺少可验证的 Frozen Session Pack")
    if not stored_digest or not payload_text:
        raise ValueError(f"{session_id}: Frozen Session Pack payload/digest 缺失")
    try:
        payload = json.loads(payload_text)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"{session_id}: Frozen Session Pack payload 不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{session_id}: Frozen Session Pack payload 结构无效")

    calculated_digest = _canonical_json_sha256(payload)
    if calculated_digest != stored_digest:
        raise ValueError(f"{session_id}: Frozen Session Pack payload digest mismatch")

    frozen_space = payload.get("space") if isinstance(payload.get("space"), dict) else {}
    frozen_policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}

    row_space_id = str(row.get("space_id") or "")
    row_profile = str(row.get("template") or "").upper()
    row_capture = str(row.get("capture_mode") or "").upper()
    row_processing = str(row.get("processing_mode") or "").upper()
    row_assistance = str(row.get("assistance_mode") or "").upper()
    row_consent = bool(row.get("consent_ack"))

    frozen_space_id = str(frozen_space.get("id") or "")
    frozen_profile = str(frozen_space.get("profile") or "").upper()
    frozen_capture = str(frozen_policy.get("capture_mode") or "").upper()
    frozen_processing = str(frozen_policy.get("processing_mode") or "").upper()
    frozen_assistance = str(frozen_policy.get("assistance_mode") or "").upper()
    frozen_consent = bool(frozen_policy.get("consent_ack"))

    mismatches: list[str] = []
    if frozen_space_id != row_space_id:
        mismatches.append("space_id")
    if frozen_profile != row_profile:
        mismatches.append("profile")
    if frozen_capture != row_capture:
        mismatches.append("capture_mode")
    if frozen_processing != row_processing:
        mismatches.append("processing_mode")
    if frozen_assistance != row_assistance:
        mismatches.append("assistance_mode")
    if frozen_consent != row_consent:
        mismatches.append("consent_ack")
    if mismatches:
        raise ValueError(
            f"{session_id}: Session row 与 Frozen Session Pack 不一致: "
            + ", ".join(mismatches)
        )

    return {
        "session_id": session_id,
        "space_id": row_space_id,
        "profile": frozen_profile,
        "status": str(row.get("status") or "").upper(),
        "started_at": row.get("started_at"),
        "ended_at": row.get("ended_at"),
        "consent_ack_recorded": row_consent,
        "capture_mode": row_capture,
        "processing_mode": row_processing,
        "assistance_mode": row_assistance,
        "pack_id": pack_id,
        "frozen_pack_id": frozen_pack_id,
        "frozen_pack_digest": stored_digest,
        "frozen_pack_payload_digest_verified": True,
    }


def parse_assignment(value: str) -> tuple[str, str]:
    text = str(value or "").strip()
    if "=" not in text:
        raise ValueError("--session 必须使用 SESSION_ID=USER_REF")
    session_id, user_ref = (part.strip() for part in text.split("=", 1))
    if not session_id:
        raise ValueError("--session 缺少 session_id")
    if not _USER_REF.fullmatch(user_ref):
        raise ValueError(
            "user_ref 必须是 1-80 位本地匿名 token，仅允许字母/数字/._-；"
            "不要填写姓名、邮箱或空格"
        )
    return session_id, user_ref


def _session_rows(db: Path, session_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    if not db.is_file():
        raise FileNotFoundError(db)
    ids = list(session_ids)
    if not ids:
        raise ValueError("至少选择一个 Session")
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        required = {
            "conversation_session",
            "conversation_space",
            "conversation_session_pack",
        }
        if not required <= tables:
            raise ValueError("product.db 缺少 Conversation schema")

        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            "SELECT s.id, s.space_id, s.template, s.status, s.started_at, s.ended_at, "
            "s.capture_mode, s.processing_mode, s.assistance_mode, "
            "s.consent_ack, s.pack_id, p.id AS frozen_pack_id, "
            "p.digest AS frozen_pack_digest, p.payload_json AS frozen_pack_payload_json "
            "FROM conversation_session s "
            "LEFT JOIN conversation_session_pack p "
            "ON p.id = s.pack_id AND p.session_id = s.id AND p.space_id = s.space_id "
            f"WHERE s.id IN ({placeholders})",
            tuple(ids),
        ).fetchall()
        return {str(row["id"]): dict(row) for row in rows}
    finally:
        conn.close()


def validated_session_facts(
    db: Path,
    session_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    ids = [str(value or "").strip() for value in session_ids]
    rows = _session_rows(db, ids)
    missing = sorted(set(ids) - set(rows))
    if missing:
        raise ValueError(f"product.db 中不存在 Session: {', '.join(missing)}")
    return {
        session_id: validated_session_fact(rows[session_id], session_id)
        for session_id in ids
    }


def build_manifest(
    db: Path,
    assignments: Iterable[tuple[str, str]],
    *,
    finalize: bool = False,
    attestations: Iterable[str] = (),
    critical_incidents: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pairs = list(assignments)
    if not pairs:
        raise ValueError("至少提供一个 --session SESSION_ID=USER_REF")

    by_session: dict[str, str] = {}
    for session_id, user_ref in pairs:
        session_id = str(session_id or "").strip()
        user_ref = str(user_ref or "").strip()
        if not session_id:
            raise ValueError("session_id 不能为空")
        if not _USER_REF.fullmatch(user_ref):
            raise ValueError(
                "user_ref 必须是 1-80 位本地匿名 token，仅允许字母/数字/._-；"
                "不要填写姓名、邮箱或空格"
            )
        if session_id in by_session:
            raise ValueError(f"重复 session_id: {session_id}")
        by_session[session_id] = user_ref

    facts = validated_session_facts(db, by_session)

    selected: list[dict[str, Any]] = []
    for session_id, user_ref in by_session.items():
        fact = facts[session_id]
        profile = str(fact.get("profile") or "").upper()
        if profile not in REQUIRED_PROFILES:
            raise ValueError(
                f"{session_id}: frozen profile={profile or '<empty>'} 不属于 Stable launch cohort"
            )
        if str(fact.get("status") or "").upper() != "ENDED":
            raise ValueError(f"{session_id}: 只有 ENDED Session 可进入 pilot cohort")
        if not bool(fact.get("consent_ack_recorded")):
            raise ValueError(f"{session_id}: 缺少 Session consent acknowledgement")
        started_at = _finite_timestamp(fact.get("started_at"), "started_at", session_id)
        ended_at = _finite_timestamp(fact.get("ended_at"), "ended_at", session_id)
        if ended_at < started_at:
            raise ValueError(f"{session_id}: ended_at 早于 started_at")
        selected.append({
            "session_id": session_id,
            "space_id": str(fact.get("space_id") or ""),
            "profile": profile,
            "user_ref": user_ref,
            "started_at": started_at,
            "ended_at": ended_at,
        })

    if any(not row["space_id"] for row in selected):
        raise ValueError("存在缺少 space_id 的 Session")

    space_user_refs: dict[str, set[str]] = {}
    for row in selected:
        space_user_refs.setdefault(row["space_id"], set()).add(
            row["user_ref"].casefold()
        )
    mixed_user_spaces = sorted(
        space_id for space_id, refs in space_user_refs.items()
        if len(refs) > 1
    )
    if mixed_user_spaces:
        raise ValueError(
            "同一 Conversation Space 的 pilot Sessions 必须绑定同一个 user_ref；"
            "存在混合用户 Space: " + ", ".join(mixed_user_spaces)
        )

    selected.sort(key=lambda row: (row["started_at"], row["session_id"]))
    supplied_attestations = [str(value or "").strip() for value in attestations]
    if len(supplied_attestations) != len(set(supplied_attestations)):
        raise ValueError("attestation 不能重复")
    unknown = sorted(set(supplied_attestations) - set(REQUIRED_ATTESTATIONS))
    if unknown:
        raise ValueError(f"未知 attestation: {', '.join(unknown)}")

    if critical_incidents is not None:
        if isinstance(critical_incidents, bool) or critical_incidents < 0:
            raise ValueError("critical_incidents 必须是 >= 0 的整数")

    if finalize:
        missing_attestations = [
            value for value in REQUIRED_ATTESTATIONS
            if value not in supplied_attestations
        ]
        if missing_attestations:
            raise ValueError(
                "finalize 缺少显式 attestation: "
                + ", ".join(missing_attestations)
            )
        if critical_incidents is None:
            raise ValueError("finalize 必须显式提供 --critical-incidents")
    elif supplied_attestations or critical_incidents is not None:
        raise ValueError(
            "DRAFT 模式不写 attestation / incident 结论；"
            "若要声明，请同时显式使用 --finalize"
        )

    profiles: dict[str, dict[str, list[dict[str, str]]]] = {
        profile: {"sessions": []} for profile in REQUIRED_PROFILES
    }
    for row in selected:
        profiles[row["profile"]]["sessions"].append({
            "session_id": row["session_id"],
            "space_id": row["space_id"],
            "user_ref": row["user_ref"],
        })

    manifest = {
        "contract_version": CONTRACT_VERSION,
        "evidence_type": FINAL_EVIDENCE_TYPE if finalize else DRAFT_EVIDENCE_TYPE,
        "period": {
            "started_at": _iso_utc(min(row["started_at"] for row in selected)),
            "ended_at": _iso_utc(max(row["ended_at"] for row in selected)),
        },
        "profiles": profiles,
        "critical_incidents": critical_incidents if finalize else None,
        "attestations": supplied_attestations if finalize else [],
        "notes": (
            "Generated from local product.db Session identifiers only. "
            "user_ref values were supplied explicitly by the operator and are "
            "local pseudonyms, not identity proof. Every selected Space is bound "
            "to exactly one pseudonymous user_ref for longitudinal evidence. "
            "Authorization/real-use/"
            "incident attestations are operator declarations, not system verification."
        ),
    }

    summary: dict[str, Any] = {
        "mode": "FINAL" if finalize else "DRAFT",
        "sessions": len(selected),
        "profiles": {},
        "cross_session_space_min_sessions": CROSS_SESSION_SPACE_MIN_SESSIONS,
        "cross_session_space_user_binding": CROSS_SESSION_SPACE_USER_BINDING,
        "real_user_identity_system_verified": False,
        "authorization_system_verified": False,
        "pmf_proven": False,
    }
    for profile in REQUIRED_PROFILES:
        rows_for_profile = [row for row in selected if row["profile"] == profile]
        spaces: dict[str, int] = {}
        users: set[str] = set()
        for row in rows_for_profile:
            users.add(row["user_ref"].casefold())
            spaces[row["space_id"]] = spaces.get(row["space_id"], 0) + 1
        summary["profiles"][profile] = {
            "sessions": len(rows_for_profile),
            "distinct_pseudonymous_users": len(users),
            "cross_session_spaces": sum(
                1 for count in spaces.values()
                if count >= CROSS_SESSION_SPACE_MIN_SESSIONS
            ),
        }
    return manifest, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="path to local product.db")
    parser.add_argument(
        "--session",
        action="append",
        default=[],
        metavar="SESSION_ID=USER_REF",
        help=(
            "explicitly select one ended launch-profile Session and assign a "
            "stable local pseudonymous user_ref; repeat for every Session"
        ),
    )
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--finalize",
        action="store_true",
        help="emit evaluator-eligible evidence_type only with all explicit attestations",
    )
    parser.add_argument(
        "--attest",
        action="append",
        default=[],
        choices=REQUIRED_ATTESTATIONS,
        help="explicit operator attestation; all required values are mandatory for --finalize",
    )
    parser.add_argument("--critical-incidents", type=int, default=None)
    args = parser.parse_args()

    db = Path(args.db)
    out = Path(args.out)
    if db.resolve() == out.resolve():
        parser.error("--out must not overwrite product.db")
    if out.exists():
        parser.error("--out already exists; choose a new path to preserve prior evidence")

    try:
        assignments = [parse_assignment(value) for value in args.session]
        manifest, summary = build_manifest(
            db,
            assignments,
            finalize=args.finalize,
            attestations=args.attest,
            critical_incidents=args.critical_incidents,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(json.dumps({
        "out": str(out),
        **summary,
        "stable_readiness_eligible_manifest_type": args.finalize,
        "interpretation": (
            "This builder validates local Session membership and structure only; "
            "it does not verify real-user identity, real-world authorization, participant consent, or PMF."
        ),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
