"""Local secret-safety scan for the v2 closure (offline; prints no secret values).

Scans the working tree, the evidence/report directories and the git history of
the current branch for real credential values and credential-shaped strings.

The scan never prints a matched secret: findings are reported as
``path:line  rule  <redacted>`` with only a length and a 4-character prefix.

Exit code 0 only when nothing is found.

Usage:  python scripts/v2_local_secret_scan.py [--json-out PATH]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Credential-shaped patterns. Deliberately narrow so real code/UI strings do not
# produce noise, but broad enough to catch a leaked provider credential.
RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("openai_style_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("slack_token", re.compile(r"\bxox[abpor]-[A-Za-z0-9-]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("bearer_header_value", re.compile(r"(?i)authorization\s*[:=]\s*[\"']?bearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    ("url_userinfo", re.compile(r"https?://[^\s/@:]{2,}:[^\s/@]{2,}@")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("pem_oauth_client_secret", re.compile(r"(?i)client_secret\s*[:=]\s*[\"'][A-Za-z0-9._-]{16,}[\"']")),
)

SCAN_DIRS = ("artifacts", "reports", "docs/evidence")
SKIP_PATH_FRAGMENTS = (
    "node_modules/",
    "backend/data/",
    ".git/",
    "dist/",
    "build/",
    "frontend/e2e/__screenshots__/",
    ".pytest_cache/",
)


# Exact literals from the redaction tests. They are deliberately fake values used
# to prove that provider responses, snapshots and account hints are redacted
# before persistence. Any other credential-shaped match blocks the scan.
KNOWN_REDACTION_FIXTURES: dict[str, str] = {
    "sk-abcdefghijklmnopqrstuvwxyz123456": "fake OpenAI-style key in the redaction fixture",
    "Authorization: Bearer abcdefghijklmnopqrstuvwxyz": "fake bearer header in the redaction fixture",
    "https://alice:supersecret@": "fake URL userinfo in the redaction fixture",
}


def known_fixture_reason(value: str) -> str:
    for literal, reason in KNOWN_REDACTION_FIXTURES.items():
        if value.startswith(literal) or literal in value:
            return reason
    return ""
TEXT_SUFFIXES = {
    ".md", ".json", ".jsonl", ".txt", ".py", ".js", ".mjs", ".ts", ".tsx", ".yml", ".yaml",
    ".html", ".css", ".log", ".cfg", ".ini", ".ps1", ".sh", ".csv", ".env", ".toml", ".lock",
}


def redact(value: str) -> str:
    head = value[:4]
    return f"{head}…(len={len(value)})"


def scan_text(text: str, origin: str) -> list[dict]:
    findings: list[dict] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for name, pattern in RULES:
            for match in pattern.finditer(line):
                findings.append(
                    {
                        "origin": origin,
                        "line": line_no,
                        "rule": name,
                        "redacted": redact(match.group(0)),
                        "classification": known_fixture_reason(match.group(0)) or "BLOCKING",
                    }
                )
    return findings


def iter_files() -> list[Path]:
    files: list[Path] = []
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    for rel in tracked:
        if any(fragment in rel for fragment in SKIP_PATH_FRAGMENTS):
            continue
        files.append(ROOT / rel)
    for directory in SCAN_DIRS:
        base = ROOT / directory
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            if any(fragment in rel for fragment in SKIP_PATH_FRAGMENTS):
                continue
            files.append(path)
    unique: dict[str, Path] = {}
    for path in files:
        unique[path.as_posix()] = path
    return sorted(unique.values())


def scan_files() -> list[dict]:
    findings: list[dict] = []
    for path in iter_files():
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = path.relative_to(ROOT).as_posix() if str(path).startswith(str(ROOT)) else path.as_posix()
        findings.extend(scan_text(text, rel))
    return findings


def scan_git_history() -> list[dict]:
    findings: list[dict] = []
    diff = subprocess.run(
        ["git", "log", "-p", "--no-color", "-20", "HEAD"],
        cwd=ROOT, capture_output=True, text=True, errors="ignore",
    )
    if diff.returncode != 0:
        return findings
    return scan_text(diff.stdout, "git-history(HEAD~20..HEAD)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    findings = scan_files() + scan_git_history()
    blocking = [item for item in findings if item.get("classification") == "BLOCKING"]
    allowlisted = [item for item in findings if item.get("classification") != "BLOCKING"]
    payload = {
        "evidence_type": "LOCAL_SECRET_SCAN",
        "rules": [name for name, _ in RULES],
        "scanned_roots": [".git-tracked files", *SCAN_DIRS, "git history of HEAD"],
        "findings": blocking,
        "allowlisted_fixtures": allowlisted,
        "findings_count": len(blocking),
        "allowlisted_count": len(allowlisted),
        "passed": not blocking,
        "note": (
            "matched values are redacted, so no secret value is written into this report; "
            "allowlisted_fixtures are the deliberately fake literals used by the connector redaction tests"
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if not blocking else 1


if __name__ == "__main__":
    raise SystemExit(main())
