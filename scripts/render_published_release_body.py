#!/usr/bin/env python3
"""Render authoritative public GitHub Release body without mutating release-note assets.

The immutable/versioned RELEASE_NOTES file remains the historical release-note
artifact. This helper creates only the GitHub Release *display body* by
prepending a generated publication-status block. It is idempotent: if an older
generated block is already present, only that block is replaced and the
underlying notes/body remain otherwise unchanged.
"""
from __future__ import annotations

import argparse
from pathlib import Path


BEGIN = "<!-- CHENGZHU_PUBLISHED_STATUS_BEGIN -->"
END = "<!-- CHENGZHU_PUBLISHED_STATUS_END -->"


def _strip_existing_status(text: str) -> str:
    start = text.find(BEGIN)
    if start < 0:
        return text
    end = text.find(END, start + len(BEGIN))
    if end < 0:
        raise ValueError("published-status begin marker exists without end marker")
    suffix = text[end + len(END):]
    # The generated block owns at most the blank lines immediately following
    # its end marker. Preserve the original notes/body content byte-for-byte
    # apart from newline normalization performed by text IO.
    return text[:start] + suffix.lstrip("\r\n")


def render(
    original: str,
    *,
    tag: str,
    source_sha: str,
    channel: str,
    stable_latest: str = "",
) -> str:
    tag = str(tag or "").strip()
    source_sha = str(source_sha or "").strip()
    channel = str(channel or "").strip().upper()
    stable_latest = str(stable_latest or "").strip()

    if not tag.startswith("v"):
        raise ValueError("tag must start with v")
    if len(source_sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in source_sha):
        raise ValueError("source_sha must be a 40-character git SHA")
    if channel not in {"PRERELEASE", "STABLE"}:
        raise ValueError("channel must be PRERELEASE or STABLE")
    if channel == "PRERELEASE" and not stable_latest:
        raise ValueError("stable_latest is required for prerelease display truth")

    underlying = _strip_existing_status(original)
    lines = [
        BEGIN,
        "> **Published status — authoritative current Release metadata**",
        ">",
        f"> Published: **TRUE** · Channel: **{channel}**",
        f"> Tag/source: `{tag}` → `{source_sha}`",
    ]
    if channel == "PRERELEASE":
        lines.append(f"> Stable Latest remains: **{stable_latest}**")
        lines.append("> This prerelease does **not** imply Stable v2, real-user validation, or PMF.")
    else:
        lines.append("> This status block records publication metadata only; product-value/PMF claims remain separate.")
    lines.extend([
        ">",
        "> The release notes below were authored before final publication and may contain",
        "> candidate/future-tense wording. This generated status block supersedes only",
        "> that publication-state wording. Release-note assets, binaries, tag and target",
        "> commit are unchanged.",
        END,
        "",
        underlying.rstrip("\r\n"),
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--channel", required=True, choices=("PRERELEASE", "STABLE"))
    parser.add_argument("--stable-latest", default="")
    args = parser.parse_args()

    source = Path(args.input)
    output = Path(args.output)
    if not source.is_file():
        parser.error(f"input does not exist: {source}")
    if source.resolve() == output.resolve():
        parser.error("output must not overwrite the input release notes/body")

    original = source.read_text(encoding="utf-8")
    try:
        rendered = render(
            original,
            tag=args.tag,
            source_sha=args.source_sha,
            channel=args.channel,
            stable_latest=args.stable_latest,
        )
    except ValueError as exc:
        parser.error(str(exc))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8", newline="\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
