#!/usr/bin/env python
"""Re-verify the closure-branch claims independently of the closure report.

This harness exists because a PASS document is not evidence. It re-derives the
load-bearing facts from the repository, the built artifacts and GitHub, and
writes a machine-readable re-verification record.

Every check reports the value it actually observed. Nothing is inferred, and a
check that cannot run is reported as an error rather than as a pass.

Usage:
    python scripts/v2_local_reverify_closure.py \
        --worktree . \
        --out artifacts/runtime-evidence/2026-10-11-v2-local-full-closure/reverification.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Expected values taken from the closure report. The harness fails when the
# repository disagrees with them, which is the whole point of re-deriving.
EXPECTED_BASE_SHA = "c581c0d764cf6dd4f59a254957b90dd7eb409f45"
EXPECTED_BETA2_TAG = "cac605edf413ec248babf02ea9f73da708d156f8"
EXPECTED_ARTIFACTS = {
    "dist/desktop/Chengzhu-Setup-x64.exe": (
        "d9c86fb0d4718faef213ee980d3c6390d050de99ff759f4f9bb90166aa0793bb"
    ),
    "dist/desktop/Chengzhu-Portable-x64.zip": (
        "ae86074bd6042fdac9c32cd1f99a134404f4b3ae32d8c88e6c146836da41e762"
    ),
    "dist/desktop/win-unpacked/resources/backend/chengzhu-backend.exe": (
        "22ed600ae95137745fea7222b9eee1e4e4ddcdcb9edbe317c61d48e6f9959907"
    ),
}
EXPECTED_PACKAGED_CAPTURES = 46
EXPECTED_CONVERSATION_CAPTURES = 6
EXPECTED_TESTS_COLLECTED = 1337
EXPECTED_VITEST_FILES = 59
EXPECTED_VITEST_TESTS = 428
EXPECTED_DESKTOP_TESTS = 38

# A bracketed IPv6 entry in NO_PROXY makes httpx 0.28.x raise InvalidURL while
# building the default client. That is a property of this machine's proxy
# environment, not of the product, so the harness records it explicitly instead
# of letting it look like a code defect.
BRACKETED_IPV6_IN_NO_PROXY = "[::1]"


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", default=".")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    root = Path(args.worktree).resolve()
    checks: list[dict] = []
    started = time.time()

    def record(name: str, passed: bool, observed, expected=None, note: str = "") -> None:
        entry = {"check": name, "pass": bool(passed), "observed": observed}
        if expected is not None:
            entry["expected"] = expected
        if note:
            entry["note"] = note
        checks.append(entry)

    # ---- source truth -------------------------------------------------
    code, head = run(["git", "rev-parse", "HEAD"], root)
    head = head.strip()
    record("worktree_head_is_sha", code == 0 and bool(re.fullmatch(r"[0-9a-f]{40}", head)), head)

    code, remote = run(["git", "rev-parse", "origin/main"], root)
    remote = remote.strip()
    record("origin_main_matches_expected_base", remote == EXPECTED_BASE_SHA, remote, EXPECTED_BASE_SHA)

    code, base = run(["git", "merge-base", "origin/main", "HEAD"], root)
    record("branch_is_based_on_expected_base", base.strip() == EXPECTED_BASE_SHA, base.strip(), EXPECTED_BASE_SHA)

    code, tag = run(["git", "rev-parse", f"{EXPECTED_BETA2_TAG}^{{commit}}"], root)
    record("beta2_tag_present_locally", code == 0, tag.strip() or "missing")

    # beta.2 must be strictly behind the branch head: the branch adds work.
    code, behind = run(["git", "rev-list", "--count", f"{EXPECTED_BETA2_TAG}..HEAD"], root)
    try:
        behind_n = int(behind.strip())
    except ValueError:
        behind_n = -1
    record("branch_is_ahead_of_beta2", behind_n > 0, behind_n, ">0")

    code, dirty = run(["git", "status", "--porcelain", "--untracked-files=no"], root)
    record("no_uncommitted_tracked_changes", dirty.strip() == "", dirty.strip() or "(clean)")

    # ---- packaged artifacts -------------------------------------------
    for rel, expected in EXPECTED_ARTIFACTS.items():
        path = root / rel
        if not path.is_file():
            record(f"artifact_sha256::{Path(rel).name}", False, "missing", expected)
            continue
        actual = sha256_file(path)
        record(
            f"artifact_sha256::{Path(rel).name}",
            actual == expected,
            actual,
            expected,
            note=f"{path.stat().st_size} bytes",
        )

    # The packaged asar must carry the modules the entry point requires.
    asar = root / "dist/desktop/win-unpacked/resources/app.asar"
    if asar.is_file():
        blob = asar.read_bytes()
        for module in ("overlayLayout.js", "conversationReminders.js"):
            record(
                f"asar_contains::{module}",
                module.encode("utf-8") in blob,
                module.encode("utf-8") in blob,
                True,
            )
    else:
        record("asar_present", False, "missing", "dist/desktop/win-unpacked/resources/app.asar")

    # ---- packaged evidence --------------------------------------------
    release_ev = root / "artifacts/release-evidence/v2.0.0-beta.2"
    packaged = list(release_ev.glob("*.png")) if release_ev.is_dir() else []
    record(
        "packaged_guid_capture_count",
        len(packaged) == EXPECTED_PACKAGED_CAPTURES,
        len(packaged),
        EXPECTED_PACKAGED_CAPTURES,
    )
    convo_dir = release_ev / "conversation-beta"
    convo = list(convo_dir.glob("*.png")) if convo_dir.is_dir() else []
    record(
        "packaged_conversation_capture_count",
        len(convo) == EXPECTED_CONVERSATION_CAPTURES,
        len(convo),
        EXPECTED_CONVERSATION_CAPTURES,
    )

    clean = root / "artifacts/runtime-evidence/2026-10-11-v2-local-full-closure/clean-install/results.json"
    if clean.is_file():
        data = json.loads(clean.read_text(encoding="utf-8"))
        c = data.get("checks", {})
        record("clean_install_passed", data.get("passed") is True, data.get("passed"), True)
        record("clean_install_no_python_on_path", c.get("python_on_path") is False, c.get("python_on_path"), False)
        record("clean_install_no_node_on_path", c.get("node_on_path") is False, c.get("node_on_path"), False)
        record("clean_install_no_repo_checkout", c.get("repo_checkout_present") is False, c.get("repo_checkout_present"), False)
        record("clean_install_sha256_all_match", c.get("sha256_all_match") is True, c.get("sha256_all_match"), True)
        record("clean_install_uninstall_removes_dir", c.get("install_dir_removed_by_uninstall") is True, c.get("install_dir_removed_by_uninstall"), True)
        record("clean_install_keeps_user_data", c.get("user_data_kept_after_uninstall") is True, c.get("user_data_kept_after_uninstall"), True)
        record("clean_install_portable_launches", bool(c.get("portable_backend_ready_seconds")), c.get("portable_backend_ready_seconds"))
    else:
        record("clean_install_results_present", False, "missing")

    # ---- suite shape (counts only; suites are run separately) ----------
    code, out = run([sys.executable, "-m", "pytest", "--collect-only", "-q"], root / "backend")
    m = re.search(r"(\d+)\s+tests?\s+collected", out)
    collected = int(m.group(1)) if m else -1
    record("backend_tests_collected", collected == EXPECTED_TESTS_COLLECTED, collected, EXPECTED_TESTS_COLLECTED)

    # ---- environment caveat -------------------------------------------
    no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    bracketed = BRACKETED_IPV6_IN_NO_PROXY in no_proxy
    record(
        "no_proxy_has_bracketed_ipv6",
        True,
        bracketed,
        note=(
            "httpx 0.28.x raises InvalidURL for a bracketed IPv6 no_proxy entry; "
            "this is a machine proxy setting, not a product defect. "
            "Run `python -m pytest` with that entry removed for a clean local suite."
        ),
    )

    passed = sum(1 for c in checks if c["pass"])
    failed = [c["check"] for c in checks if not c["pass"]]
    payload = {
        "evidence_type": "V2_LOCAL_CLOSURE_REVERIFICATION",
        "worktree": str(root),
        "head": head,
        "expected_base_sha": EXPECTED_BASE_SHA,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "duration_seconds": round(time.time() - started, 2),
        "checks_total": len(checks),
        "checks_passed": passed,
        "checks_failed": len(failed),
        "failed_checks": failed,
        "checks": checks,
        "passed": not failed,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"checks {passed}/{len(checks)} passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
    print(f"wrote {out_path}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
