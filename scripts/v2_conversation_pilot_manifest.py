#!/usr/bin/env python3
"""Build a local Conversation v2 pilot-cohort manifest from product.db.

The builder reduces clerical errors; it does not verify identity, consent,
authorization, real-world use, or incident status.

Default output is deliberately a DRAFT that stable-readiness will reject.
A final AUTHORIZED_REAL_CONVERSATION_PILOT manifest requires:
- explicit --finalize;
- every required --attest value supplied by the operator;
- explicit --critical-incidents;
- only ended PROJECT_SYNC / DESIGN_REVIEW sessions selected from product.db.

No transcript text, participant names, Space titles, or other content is copied
into the manifest. user_ref is a local pseudonymous cohort key, not identity
proof.
"""
from __future__ import annotations

import argparse
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
        required = {"conversation_session", "conversation_space"}
        if not required <= tables:
            raise ValueError("product.db 缺少 Conversation schema")

        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            "SELECT s.id, s.space_id, s.template, s.status, s.started_at, s.ended_at "
            "FROM conversation_session s "
            f"WHERE s.id IN ({placeholders})",
            tuple(ids),
        ).fetchall()
        return {str(row["id"]): dict(row) for row in rows}
    finally:
        conn.close()


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
        if session_id in by_session:
            raise ValueError(f"重复 session_id: {session_id}")
        by_session[session_id] = user_ref

    rows = _session_rows(db, by_session)
    missing = sorted(set(by_session) - set(rows))
    if missing:
        raise ValueError(f"product.db 中不存在 Session: {', '.join(missing)}")

    selected: list[dict[str, Any]] = []
    for session_id, user_ref in by_session.items():
        row = rows[session_id]
        profile = str(row.get("template") or "").upper()
        if profile not in REQUIRED_PROFILES:
            raise ValueError(
                f"{session_id}: profile={profile or '<empty>'} 不属于 Stable launch cohort"
            )
        if str(row.get("status") or "").upper() != "ENDED":
            raise ValueError(f"{session_id}: 只有 ENDED Session 可进入 pilot cohort")
        started_at = _finite_timestamp(row.get("started_at"), "started_at", session_id)
        ended_at = _finite_timestamp(row.get("ended_at"), "ended_at", session_id)
        if ended_at < started_at:
            raise ValueError(f"{session_id}: ended_at 早于 started_at")
        selected.append({
            "session_id": session_id,
            "space_id": str(row.get("space_id") or ""),
            "profile": profile,
            "user_ref": user_ref,
            "started_at": started_at,
            "ended_at": ended_at,
        })

    if any(not row["space_id"] for row in selected):
        raise ValueError("存在缺少 space_id 的 Session")

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
            "local pseudonyms, not identity proof. Authorization/real-use/"
            "incident attestations are operator declarations, not system verification."
        ),
    }

    summary: dict[str, Any] = {
        "mode": "FINAL" if finalize else "DRAFT",
        "sessions": len(selected),
        "profiles": {},
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
            "cross_session_spaces": sum(1 for count in spaces.values() if count >= 2),
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
            "it does not verify real-user identity, authorization, consent, or PMF."
        ),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
