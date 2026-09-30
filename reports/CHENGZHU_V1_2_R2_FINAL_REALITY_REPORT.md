# Chengzhu v1.2-R2 — Final Reality Report

Date: 2026-09-30 · Release closure goal: latency · license · release · download-back · clean install.
Status vocabulary per the release-closure goal §29. Nothing below uses "PASS" in place of an evidence level.

## Verdict

**NOT_READY — one gate open: the clean Windows 11 install without Python / Node (Windows Sandbox) of the published v1.2.2.**

Per §29 "clean install not done" is NOT_READY, and a fresh Windows VM whose image ships the `py`
launcher does not fully substitute for it. Everything else in §2 is met for **v1.2.2** (Latest):
PR and `main` CI green; license closure (MIT, PyMuPDF replaced, no copyleft component, provenance
confirmed by the maintainer); tag + GitHub Release with installer, portable, SHA256SUMS, LICENSE,
THIRD_PARTY_NOTICES and notes; download-back by URL with verified SHA256; on a fresh en-US Windows VM
the downloaded installer installs, launches without Python/Node on PATH, onboards, persists the frozen
InterviewPack across restart, shows the Fast Cue before the deep answer, leaves the install dir untouched
and uninstalls cleanly; screenshots from the downloaded build.

The Windows Sandbox on this machine crashes since a Store update (needs a reboot); the maintainer chose
to run that last step later with the command in `V1_2_R2_RELEASE_CLOSURE_CHECKPOINT.md`. When it passes,
the status becomes **RELEASE_READY_WITH_EXTERNAL_BLOCKERS** (external items below).

Latency is acceptable under the Stage G profile split, stated as measured: Streaming profile meets
Gate A; the Local CPU profile meets Gate A at the median and sits exactly on the 3.0 s p95 limit.

This closure found and fixed a release-blocking bug that local and Chinese-locale checks could not see:
**v1.2.0 exited at first launch on non-Chinese Windows locales** — caught only by the download-back run
on an English-locale VM, fixed in v1.2.1; v1.2.0's release page now points to v1.2.2.

## Git

| Item | Value |
|---|---|
| Final `main` HEAD | `2608879` (merge of #3) — local `main` == `origin/main` |
| Tags | `v1.2.0` → `fa82c61` · `v1.2.1` → `bab58dc` · **`v1.2.2` → `2608879`** (annotated) |
| Releases | **v1.2.2 (Latest)**: https://github.com/huangdi97/cheng-zhu/releases/tag/v1.2.2 · v1.2.1 · v1.2.0 (notice at the top: use a later version on non-Chinese Windows) |
| PRs | [#1](https://github.com/huangdi97/cheng-zhu/pull/1) v1.2-R2 → v1.2.0 · [#2](https://github.com/huangdi97/cheng-zhu/pull/2) v1.2.1 locale fix + download-back verification · [#3](https://github.com/huangdi97/cheng-zhu/pull/3) v1.2.2 — all merged with merge commits, no force, no bypassed check |
| Worktree | clean |

## CI

| Run | What | Result |
|---|---|---|
| `36693099939` + Release `36693100061` | PR #1 head `3960410` (CI + full Windows installer build) | success |
| `36694082059` | `main` after #1 (`fa82c61`) | success |
| `36701112663` + Release `36701112625` | PR #2 head `36d0bfc` | success |
| `36702134989` | `main` after #2 (`bab58dc`) | success |
| PR #3 head `56d5307` (CI + Windows release build + release-verify) | | success |
| `36713331944` | **`main` after #3 (`2608879`)** | **success** |
| Release `36694796398` / `36702670593` / `36713904706` | tag builds v1.2.0 / v1.2.1 / v1.2.2 (tests, license gate, sidecar, packaged smoke, installer + portable, installed-layout smoke, publish) | success / success / success |

History kept, not rewritten: `313f442` failed · `88a63ba` failed · `f04f217` success (`36664430658`) · `f577a16` failed (ruff B017 in a new test) · `5e237b3` failed (stricter license gate flagged wheels not installed on the Linux runner; gate fixed to verify them in the Windows job) · every later PR head green.

## Performance (`reports/CHENGZHU_V1_2_R2_LATENCY_FORENSICS.md`)

Pooled over 3 clean `windows-latest` runs (4 vCPU), 34-clip corpus, product defaults; TTFUG_user = first useful cue **on screen** − ground-truth speech end.

| Metric | Local CPU profile (measured) | Streaming profile (SIMULATED provider) | f04f217 (as rendered) |
|---|---|---|---|
| TTFUG_user p50 / p95 | **1.58 s / 3.00 s** (per run p95 2.50 / 2.96 / 3.12 s) | **0.56 s / 2.08 s** | 5.61 s / 6.89 s |
| QBD p50 / p95 | 2.44 s / 3.70 s | 1.98 s / 2.44 s | 4.26 s / 5.54 s |
| TTFUG_internal p50 (cue − question confirmed) | −0.80 s (cue shown before confirmation, then confirmed on the same card) | −1.42 s | 1.35 s |
| TTFA / TTD p50 (fake provider) | 1.88 s / 2.02 s after confirmation (includes the 1.2 s late-constraint grace) | same | same |
| premature end / premature cue / replaced | 0 / 2.0 % / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Cue before deep answer | 100 % | 100 % | 100 % |

Gates: **Gate A** — Streaming profile MET; Local CPU p50 met, p95 **at the 3.0 s boundary** (BORDERLINE, met on 2 of 3 runs). **Gate B** — not met (Local); Streaming p50 met, p95 2.08 s not met. Profiles are split and stated in the release notes (Stage G). The earlier single-run claim (Local 1.30 s / 2.54 s) is withdrawn in the report and in the v1.2.2 notes.

## License

| Item | Status |
|---|---|
| Root license | MIT — README / package metadata / About / installer license page |
| PyMuPDF (AGPL-3.0) | **REPLACED** by pypdfium2 (BSD-3 / Apache-2.0) — `PYMUPDF_USAGE_AUDIT.md`, `PYMUPDF_LICENSE_DECISION.md`; PDF regression corpus 26 tests |
| THIRD_PARTY_NOTICES | regenerated; gate **fails** on installed non-permissive or known-copyleft dependencies (verified with every wheel installed in the Windows release job); shipped build has no copyleft component |
| Legacy `interview-assistant` provenance | **SELF_AUTHORED_CONFIRMED** by the maintainer (2026-09-30) — `LEGACY_CODE_PROVENANCE_AUDIT.md` |

## Packaging (v1.2.2 assets)

| Asset | Size | SHA256 |
|---|---|---|
| `Chengzhu-Setup-x64.exe` (per-user NSIS, unsigned) | 202,475,988 B (193.1 MiB) | `ca6448d01fa12863c99b7a47cb5b3de4a2b1ba736d4d081ec99c88c3612ee799` |
| `Chengzhu-Portable-x64.zip` | 268,623,613 B (256.2 MiB) | `4e3011873ac03d26336cfeb59ac0191eb81ce857ee102f20b7ae448612ff5638` |
| `SHA256SUMS.txt` (LF), `LICENSE.txt`, `THIRD_PARTY_NOTICES.md`, `RELEASE_NOTES_v1.2.2.md` | 181 / 1,087 / 35,819 / 6,779 B | — |

| Gate | Result | Evidence |
|---|---|---|
| **Download-back** | **done** — all six assets downloaded by their public release URLs into a fresh temp directory (not the build folder); `sha256sum -c SHA256SUMS.txt` OK for installer and portable | this report; `artifacts/release-evidence/v1.2.2-download-back/manifest.json` |
| **Fresh Windows VM (en-US)** | **every product check passed**: SHA256 · silent install 24 s · LICENSE + notices bundled · backend ready 3.4 s (first launch, fresh profile) · Share Privacy OFF · onboarding · resume upload · job goal · frozen InterviewPack · Live ask: `guidance_fast` before `answer_chunk`, `answer_done` · restart 2.1 s with pack / onboarding / resume persisted · install dir untouched · uninstall removes the app and keeps `%APPDATA%\Chengzhu` · portable launches in 2.7 s on the same data | release-verify `36716495128`; `clean-vm-en-us/` (results.json, verify.log, installer / first-launch / live / restart / portable screenshots). Node absent from PATH; **the image ships the `py` launcher in `C:\Windows`, so "no Python on the machine" is not provable there** |
| **Clean Windows 11, no Python / Node (Windows Sandbox)** | **open** — the same verification ran in Windows Sandbox against the pre-release f04f217 build (all product checks passed except the in-sandbox fake provider, since fixed); for the published v1.2.2 the host's Windows Sandbox app crashes on start after a Store update (`CLASS_E_CLASSNOTAVAILABLE`) and needs a reboot. The maintainer chose to run it later | `reports/V1_2_R2_RELEASE_CLOSURE_CHECKPOINT.md` (exact command) |
| Screenshots from the downloaded build | installer (fresh VM) · first launch · onboarding · home · facts · prepare · freeze · preflight · live Fast Cue · review · settings · About 版本 1.2.2; overlay **not captured** | `artifacts/release-evidence/v1.2.2-download-back/` |
| Exe file metadata | reports Electron's version, not 1.2.2 (`signAndEditExecutable: false`); About, sidecar `--version` and the installer show 1.2.2 | cosmetic, recorded |

## Product (real status)

| Capability | Level | Evidence |
|---|---|---|
| InterviewPack freeze + Live reads only the frozen pack | AUTHORITATIVE | frozen pack id + content hashes in the download-back manifest; restart persistence on the fresh VM |
| Fast Cue before Deep | AUTHORITATIVE | fresh-VM Live ask: `guidance_fast` before `answer_chunk`; benchmark 100 % |
| Adaptive end of turn + provisional cue + reconcile | INTEGRATED, CI-PROVEN (corpus) | latency forensics; 30+ unit tests |
| English / Chinese question detection fixes | CI-PROVEN | `test_asr_english_questions.py` |
| First launch on non-Chinese Windows | REAL-PROVEN on a fresh en-US VM | release-verify; packaged smoke fresh first run on the en-US runner |
| Onboarding, facts & sources, job goal, preflight, review, settings/About 版本 | REAL-PROVEN from the downloaded build | `artifacts/release-evidence/v1.2.2-download-back/` |
| Overlay Cue Mode | INTEGRATED | shared view model tests; **screenshot not captured** (window renders blank under automation) |
| Human Coach LAN, Share Privacy OFF by default | PRODUCT-COMPLETE (unchanged) | earlier R2 evidence; Share Privacy default checked on the fresh VM |

## Tests (final code, local unless noted)

Backend 994 passed, ruff clean · Eval 2.0 20/20 mandatory, held-out v2 exact 0.833 (unchanged) · Frontend tsc + build clean, vitest 390/391 locally (pre-existing JobTracker test flaked once under heavy CPU load; passes alone and in CI; separate task suggested) · Desktop 23/23 · CI: all jobs green on every PR head and on `main`.

## External / open

| Item | Status |
|---|---|
| Clean Windows 11 install without Python / Node (Windows Sandbox) of v1.2.2 | **open (local)** — run after a reboot; checkpoint has the command |
| Code signing certificate (SmartScreen warning; release notes explain it) | BLOCKED-EXTERNAL |
| macOS build + notarization | BLOCKED-EXTERNAL |
| Real paid-provider evaluation (quality, TTFA/TTD) and a measured streaming-ASR profile | BLOCKED-EXTERNAL (maintainer chose not to spend the Doubao key; streaming profile is simulated) |
| Public Human Coach relay | BLOCKED-EXTERNAL (LAN only) |
| Real multi-hour human interview audio | BLOCKED-EXTERNAL (corpus is synthetic SAPI speech + mixed noise) |
| Overlay screenshot | not captured (renders blank under automation); view model covered by tests |
| Flaky frontend test (JobTracker pending-save rail) under heavy CPU load | pre-existing; separate task suggested |
| Stray file `D:\Code\Git\tmp_sums.txt` (181 B copy of a checksum list) created by a shell one-liner during download-back | blocked from deletion by a safety check — maintainer to delete |
