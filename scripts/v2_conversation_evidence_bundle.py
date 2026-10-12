#!/usr/bin/env python3
"""Build a reproducible local Chengzhu v2 Stable evidence bundle.

The bundle recomputes the human-label aggregate and Stable readiness directly
from raw label JSONL + pilot manifest + frozen policy in one process.  It records
SHA256 digests for every input and evaluator tool so an auditor can reproduce
which local bytes produced the conclusion.

This is consistency/provenance evidence only. Hashes do not prove reviewer
identity, participant consent, AUTHORIZED_REAL_USE, real-user value, Stable
release status, or PMF.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


BUNDLE_CONTRACT_VERSION = "v2.0-R1-stable-evidence-bundle-1"
ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
HUMAN_TOOL = SCRIPT_DIR / "v2_conversation_human_eval.py"
STABLE_TOOL = SCRIPT_DIR / "v2_conversation_stable_readiness.py"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_digest(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "name": path.name,
        "sha256": _sha256_bytes(raw),
        "bytes": len(raw),
    }


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _object_digest(value: Any) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load evaluator tool: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_bundle(
    label_paths: list[Path],
    pilot_manifest_path: Path,
    policy_path: Path,
) -> dict[str, Any]:
    if not label_paths:
        raise ValueError("at least one raw label JSONL is required")
    all_inputs = [*label_paths, pilot_manifest_path, policy_path]
    missing = [str(path) for path in all_inputs if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing evidence input(s): " + ", ".join(missing))

    human_eval = _load_module("chengzhu_v2_human_eval_bundle", HUMAN_TOOL)
    stable_eval = _load_module("chengzhu_v2_stable_readiness_bundle", STABLE_TOOL)

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for path in label_paths:
        rows.extend(human_eval.load_rows(path, seen=seen))

    human_report = human_eval.aggregate(rows)
    pilot_manifest = _load_json_object(pilot_manifest_path)
    policy = _load_json_object(policy_path)
    stable_report = stable_eval.evaluate(human_report, pilot_manifest, policy)

    label_digests = sorted(
        (_file_digest(path) for path in label_paths),
        key=lambda item: (item["sha256"], item["name"]),
    )
    payload: dict[str, Any] = {
        "bundle_contract_version": BUNDLE_CONTRACT_VERSION,
        "evidence_type": "CHENGZHU_V2_STABLE_EVIDENCE_BUNDLE",
        "inputs": {
            "raw_labels": label_digests,
            "pilot_manifest": _file_digest(pilot_manifest_path),
            "policy": {
                **_file_digest(policy_path),
                "policy_version": policy.get("policy_version"),
            },
        },
        "toolchain": {
            "human_eval": {
                **_file_digest(HUMAN_TOOL),
                "report_contract_version": human_report.get("report_contract_version"),
            },
            "stable_readiness": _file_digest(STABLE_TOOL),
            "bundle_builder": _file_digest(Path(__file__).resolve()),
        },
        "human_report_sha256": _object_digest(human_report),
        "stable_report_sha256": _object_digest(stable_report),
        "human_report": human_report,
        "stable_report": stable_report,
        "claims": {
            "INPUT_BYTES_HASHED": True,
            "EVALUATOR_BYTES_HASHED": True,
            "REPRODUCIBLE_LOCAL_CALCULATION": True,
            "REVIEWER_IDENTITY_VERIFIED": False,
            "AUTHORIZED_REAL_USE_SYSTEM_VERIFIED": False,
            "V2_STABLE_RELEASE": False,
            "PMF_PROVEN": False,
        },
        "interpretation": (
            "This bundle proves which local input bytes, frozen policy and evaluator bytes produced "
            "the embedded reports. It does not authenticate human identity or consent, and a passing "
            "Stable evidence gate still permits only a separate release review."
        ),
    }
    payload["bundle_sha256"] = _object_digest(payload)
    return payload


def markdown(bundle: dict[str, Any]) -> str:
    stable = bundle.get("stable_report") or {}
    inputs = bundle.get("inputs") or {}
    cohort = stable.get("pilot_cohort") or {}
    lines = [
        "# Chengzhu v2 Stable Evidence Bundle",
        "",
        f"- Bundle contract: **{bundle.get('bundle_contract_version')}**",
        f"- Bundle SHA256: `{bundle.get('bundle_sha256')}`",
        f"- Stable evidence status: **{stable.get('status') or 'UNKNOWN'}**",
        f"- Policy: **{stable.get('policy_version') or 'unknown'}**",
        f"- Authorized manifest Sessions: **{cohort.get('authorized_sessions', 0)}**",
        f"- Human-labeled Sessions: **{cohort.get('human_labeled_sessions', 0)}**",
        "- V2_STABLE_RELEASE: **FALSE**",
        "- PMF_PROVEN: **FALSE**",
        "",
        "## Input digests",
        "",
        "| Input | SHA256 | Bytes |",
        "| --- | --- | ---: |",
    ]
    for index, item in enumerate(inputs.get("raw_labels") or [], start=1):
        lines.append(
            f"| raw-label-{index}: {item.get('name')} | `{item.get('sha256')}` | {item.get('bytes')} |"
        )
    for key in ("pilot_manifest", "policy"):
        item = inputs.get(key) or {}
        lines.append(
            f"| {key}: {item.get('name')} | `{item.get('sha256')}` | {item.get('bytes')} |"
        )
    lines += [
        "",
        "## Derived report digests",
        "",
        f"- human_report_sha256: `{bundle.get('human_report_sha256')}`",
        f"- stable_report_sha256: `{bundle.get('stable_report_sha256')}`",
        "",
        "> This is a local reproducibility/provenance bundle. SHA256 does not prove reviewer identity, participant consent, real-user value, Stable release status, or PMF.",
        "",
    ]
    return "\n".join(lines)


def _validate_output_paths(inputs: list[Path], outputs: list[Path]) -> None:
    resolved_inputs = {path.resolve() for path in inputs}
    resolved_outputs = [path.resolve() for path in outputs]
    if len(resolved_outputs) != len(set(resolved_outputs)):
        raise ValueError("bundle outputs must be distinct")
    if any(path in resolved_inputs for path in resolved_outputs):
        raise ValueError("bundle outputs must not overwrite evidence inputs or policy")
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise FileExistsError(
            "bundle output already exists; choose a new path to preserve prior evidence: "
            + ", ".join(existing)
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--labels",
        nargs="+",
        required=True,
        help="one or more raw human-labeled JSONL files",
    )
    parser.add_argument("--pilot-manifest", required=True)
    parser.add_argument(
        "--policy",
        default="docs/evals/V2_CONVERSATION_STABLE_PROMOTION_POLICY.json",
    )
    parser.add_argument("--out", required=True, help="new JSON bundle path; existing files are refused")
    parser.add_argument("--markdown-out", default="", help="optional new Markdown summary path")
    args = parser.parse_args()

    label_paths = [Path(value) for value in args.labels]
    pilot_path = Path(args.pilot_manifest)
    policy_path = Path(args.policy)
    output_paths = [Path(args.out)]
    if args.markdown_out:
        output_paths.append(Path(args.markdown_out))
    _validate_output_paths([*label_paths, pilot_path, policy_path], output_paths)

    bundle = build_bundle(label_paths, pilot_path, policy_path)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.markdown_out:
        md = Path(args.markdown_out)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(markdown(bundle), encoding="utf-8")

    print(json.dumps({
        "bundle_contract_version": bundle["bundle_contract_version"],
        "bundle_sha256": bundle["bundle_sha256"],
        "stable_status": bundle["stable_report"]["status"],
        "out": str(out),
        "real_user_identity_verified": False,
        "v2_stable_release": False,
        "pmf_proven": False,
    }, ensure_ascii=False, indent=2))
    return 0 if bundle["stable_report"]["status"] != "NO_GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
