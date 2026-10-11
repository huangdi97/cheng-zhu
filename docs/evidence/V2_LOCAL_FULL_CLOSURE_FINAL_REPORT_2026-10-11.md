# Chengzhu v2 Local Full Closure Final Report

**Generated**: 2026-10-11 (Asia/Shanghai)
**Companion document**: [`V2_LOCAL_FULL_CLOSURE_2026-10-11.md`](V2_LOCAL_FULL_CLOSURE_2026-10-11.md) — the 27-section local truth report produced by this closure.

## Provenance of this report

This report is a **re-verification pass**, not a restatement. The closure report was treated as a claim
to be tested, and the load-bearing facts were re-derived from the repository, the built artifacts and
GitHub. Where a number appears below it is either (a) re-observed in this pass, or (b) explicitly
marked as inherited. Machine-readable output:
`artifacts/runtime-evidence/2026-10-11-v2-local-full-closure/reverification.json`
(23/23 checks pass, produced by `scripts/v2_local_reverify_closure.py`).

```
Base SHA:   c581c0d764cf6dd4f59a254957b90dd7eb409f45   (origin/main — exactly the expected baseline)
Branch:     chore/v2-local-full-closure-2026-10-11
PR:         #70  https://github.com/huangdi97/cheng-zhu/pull/70   (OPEN, MERGEABLE)
Head:       6f932bcc778c59f1a90d03123b080c83cb927b31   (branch head at the time of writing)
CI:         run 38114705146 "CI"      => success      @ 6f932bc
            run 38114705148 "Release" => success      @ 6f932bc  (windows job: build + packaged smoke + clean install)
Candidate:  c07830429ba27340e938a656b0fc1c89ade39bd6   (first commit with both workflows green)
```

Nine of nine required CI checks are `pass` at the head: `backend`, `frontend`, `desktop`,
`e2e-playwright`, `e2e-visual`, `e2e-smoke`, `packaged-smoke`, `windows`, `ci-gate`. Earlier `Release`
runs on this branch were red until the tzdata defect was fixed, so a real defect was found and fixed
rather than the gate being waived. The `Release` workflow ran the full packaging path (sidecar,
installer, portable, packaged smoke, clean install) as a build-only job and **created no tag or GitHub
Release**, which is correct: this repository publishes only from a green `main`.

On SHA discipline: documentation cannot certify the SHA that contains it without a re-commit loop, so
the head above is a moving target by one docs commit. What matters is that the workflows are green on
the head itself, and that the code-bearing candidate `c078304` was independently green as well.

---

## 1. Engineering

**PASS**

| Gate | Observed in this pass |
| --- | --- |
| backend suite | **1337 passed, 0 failed** in 278.10 s (re-observed; see §1a for the one machine setting that had to be neutralised first) |
| frontend unit | **428 passed / 59 files** (re-observed, exit 0) |
| frontend typecheck | `npx tsc -b --noEmit` exit 0 (re-observed) |
| frontend build | `npm run build` exit 0 (re-observed) |
| desktop unit | **38 passed / 0 fail** (re-observed) |
| backend lint | `ruff check .` — All checks passed |
| release version consistency | `{"ok": true, "version": "2.0.0-beta.2", "release_channel": "PRERELEASE"}` |
| license / third-party notices | `generate_third_party_notices.py --check` exit 0 |
| secret scan | `passed: true`, 0 blocking findings, 25 allowlisted fake fixtures |
| migration matrix | `passed: true`, additive across fresh/v1/v2/v4/v7/v8/v9, idempotent reopen |
| independent re-verification | `scripts/v2_local_reverify_closure.py` — **23/23 checks pass**, exit 0 |

### 1a. The one non-green local signal, root-caused

A bare local `python -m pytest -q` first gave **1 failed, 1336 passed**: `tests/test_review_analysis.py::test_get_active_llm_client` raising `httpx.InvalidURL: Invalid port: ':1]'`.

Root cause, isolated by running httpx against each candidate variable:

| `no_proxy` value | `httpx.Client()` |
| --- | --- |
| all proxy vars cleared | PASS |
| `all_proxy` only | PASS |
| **`[::1]` present** | **FAIL — `InvalidURL: Invalid port: ':1]'`** |
| `::1` (bare) | PASS |

httpx 0.28.x builds its client mounts by parsing every comma-separated `no_proxy` entry as a
`URLPattern`; a bracketed IPv6 literal raises. This machine's user-level `NO_PROXY` ends with `[::1]`
and already contains the bare `::1`, which is the form that works.

Two Windows-specific details had to be handled, and both are worth recording:

1. httpx reads `no_proxy` case-insensitively, and on Windows a variable set in one case is visible in
   the other — so stripping only `NO_PROXY` leaves `no_proxy` still carrying the entry.
2. Assigning to an existing `os.environ` key on Windows does **not** reliably propagate the new value
   to child processes. An assignment-only fix therefore looks successful (the parent's own
   `httpx.Client()` constructs) while the pytest child still fails. The key must be removed and re-added.

With both handled, the unmodified suite reports **1337 passed, 0 failed**.

This is a **machine proxy setting, not a product defect**: no repository code and no test contract is
at fault, and CI (clean proxy environment) is green. Because `get_client_for_model` builds its client
with `trust_env=True`, the same setting also affects a real local run of the product; that robustness
observation is recorded rather than silently patched, since narrowing `trust_env` is a product decision
about corporate proxy support. `scripts/run_backend_suite_clean_proxy.py` documents the setting and
runs the unmodified suite in a sanitised environment.

---

## 2. Conversation runtime

**PASS**

- Real packaged-sidecar loop (`scripts/packaged_smoke.py`, exit 0): `/api/instance` nonce echo,
  schema `9 == 9`, frontend served, Fast Cue emitted before the first deep token, Session Pack frozen
  and persisted, and after a **real process restart** the pack, history and reviewed truth survived.
- Frozen-pack behaviour is asserted against the real contract, not a mock: mid-session material edits
  do not leak into an active session, and space goal / participant / playbook / expression are frozen.
- Guidance arbiter, guidance sources, truth model, supersession, longitudinal open threads and profile
  isolation each have named tests inside the 1337-test suite.
- Conversation UI evidence: **46** packaged BrowserWindow captures plus **6** Conversation-only
  packaged captures (counts re-observed in this pass).

---

## 3. Interview regression

**PASS**

Interview is exercised by the backend suite, the 65-case Playwright run and the packaged captures
(`01-onboarding` … `29-history`), i.e. Interview and Conversation coexist in one packaged build. The
Conversation connector runtime does not alter Interview provider semantics, and the boundary is
asserted in both directions
(`test_conversation_capture_refuses_to_steal_live_interview_audio`,
`test_interview_start_refuses_to_preempt_active_conversation_capture`).

---

## 4. Windows packaged product

**PASS**

| Item | Observed |
| --- | --- |
| installer | `dist/desktop/Chengzhu-Setup-x64.exe` — sha256 `d9c86fb0d4718faef213ee980d3c6390d050de99ff759f4f9bb90166aa0793bb` (**re-computed in this pass**) |
| portable | `dist/desktop/Chengzhu-Portable-x64.zip` — sha256 `ae86074bd6042fdac9c32cd1f99a134404f4b3ae32d8c88e6c146836da41e762` (**re-computed**) |
| sidecar | `chengzhu-backend.exe` — sha256 `22ed600ae95137745fea7222b9eee1e4e4ddcdcb9edbe317c61d48e6f9959907` (**re-computed**) |
| build date | 2026-10-11 06:30–06:33 — current closure build, **not** a reused beta.2 artifact (the pre-existing `dist/` in the original checkout is the superseded 2026-10-09 build and is *not* presented as closure evidence) |
| defect #1 regression | built `app.asar` contains `overlayLayout.js` and `conversationReminders.js` (**verified by reading the built archive**) |
| signing | unsigned — no signing identity on this machine; reported, not hidden |

**Clean-install replay PASS**: re-read from `clean-install/results.json`, `passed: true`, with
`python_on_path false`, `node_on_path false`, `repo_checkout_present false`, both artifacts
**SHA256-matched**, first launch backend ready 7.1 s, `share_privacy` default `OFF`, pack frozen,
Fast Cue before deep, restart ready 3.2 s with pack/onboarding/resume persisted, install dir
unchanged after use, uninstall removes the install dir while keeping user data, portable launches in
3.3 s seeing the same user data. The earlier failing run is retained as counter-evidence.

---

## 5. Real Account Connectors

| Provider | Status | Basis |
| --- | --- | --- |
| **GitHub** | **PASS_REAL_ACCOUNT** | `github-replay.json`, 48/48 assertions, against private throwaway repo `huangdi97/chengzhu-connector-replay-2026-10-11`; real account `huangdi97` (token scopes re-confirmed this pass: `gist, read:org, repo, workflow, write:packages`). Flag-off run proves `adapter_available: false` and zero connections. |
| Google Calendar | **BLOCKED_ACCOUNT** | No Google credential on this machine (env probe in this pass found none). Code/contract/fail-closed verified by tests. |
| Google Drive | **BLOCKED_ACCOUNT** | Same; no credential exists. |
| Gmail | **BLOCKED_ACCOUNT** + **BLOCKED_EXTERNAL** | No credential; sending to real users additionally needs Google OAuth sensitive-scope verification / consent publication. |
| Microsoft To Do | **BLOCKED_ACCOUNT** | No Microsoft credential exists. |

Test-repository hygiene: the private replay repo still exists with its **2 seed issues**, and the
issue created by the reviewed write flow was deleted — verified in this pass. Deleting the repo itself
needs the `delete_repo` scope, which the current token does not have.

---

## 6. External execution

**PASS for every path reachable on this machine.**

| Path | Status |
| --- | --- |
| GitHub Issue | **Executed for real**: reviewed `CREATE_ISSUE_DRAFT` → `APPROVE` → explicit target → second execute → `SUCCEEDED`; exactly one issue at the provider with the exact reviewed title, and the audited idempotency key present in the created artifact. A second execute returned `SUCCEEDED` without a second issue. |
| Gmail Send | **BLOCKED_ACCOUNT** (+ `BLOCKED_EXTERNAL` for OAuth publication) — reviewed draft path implemented and tested; no real send performed or claimed. |
| Microsoft To Do Task | **BLOCKED_ACCOUNT** — reviewed task draft path implemented and tested; no real task created or claimed. |
| Decision Log | **BLOCKED_EXTERNAL_PROVIDER** — only the local reviewed draft/approve/audit/export path is exercised. No external execution is claimed. |

`UNKNOWN_OUTCOME` is verified by fault injection only (`connection interruption after request`,
`unknown outcome`, `retry blocked`, explicit reconciliation required) — never by manufacturing a real
duplicate side effect. `UNKNOWN_OUTCOME != FAILED`, and retry of a definitive-but-unsafe failure is
refused unless the provider declared `retry_safe`.

---

## 7. Privacy

| Area | Status |
| --- | --- |
| Local Processing | **PASS** — LOCAL refuses a remote STT path at preflight *and* at capture start (fail closed); CLOUD shows the remote path explicitly in the UI; OFF yields no TRANSCRIPT and `AI_FORBIDDEN`. Capture/STT/inference/retention/write-back are frozen in the Session Pack. |
| Screen | **PASS** — MANUAL stores observation text + image hash + vision provider/model and **no raw image**; AUTO requires an explicit second start (a Session start never silently starts it), has duplicate-frame suppression, rate limit, OFF THE RECORD, and force-stop on end session / delete session / delete Space. LOCAL + remote vision fails closed. |
| Overlay | **PASS** — web without the Electron bridge fails closed; backend refuses PRIVATE_OVERLAY start without a verified desktop runtime proof; Electron path activates, verifies, restores baseline. Wording limited to *best-effort content protection on supported capture paths*; no undetectable/anti-proctoring claim is made. |
| Human Coach | **PASS** — `HUMAN_ALLOWED` with a participant-transparency plan, one-time hashed link with TTL, per-item permissions (transcript / AI Guidance / frozen Session Context), advice is `HUMAN_COACH` with `is_evidence = false`, Interview resume/JD unreachable, links revoke on end session / delete session / erase Space. |
| Transparency | **PASS** — all five TRANSCRIPT states distinguished; `NOT_RECORDED` warns; the system never claims it notified anyone or obtained consent. |
| Secret Safety | **PASS** — secret scan green across tracked files, artifacts, docs and git history; credentials stay opaque env references (`PROCESS_ENV_ONLY`) and are absent from `product.db`, exports and audit rows. |

---

## 8. Artifacts

```
Installer:  dist/desktop/Chengzhu-Setup-x64.exe
            sha256 d9c86fb0d4718faef213ee980d3c6390d050de99ff759f4f9bb90166aa0793bb   (203,371,880 bytes)
Portable:   dist/desktop/Chengzhu-Portable-x64.zip
            sha256 ae86074bd6042fdac9c32cd1f99a134404f4b3ae32d8c88e6c146836da41e762   (270,147,648 bytes)
Sidecar:    chengzhu-backend.exe
            sha256 22ed600ae95137745fea7222b9eee1e4e4ddcdcb9edbe317c61d48e6f9959907
Checksums:  dist/desktop/SHA256SUMS.txt  (contents match the recomputed hashes)
Screenshots: artifacts/release-evidence/v2.0.0-beta.2/            46 packaged captures
             artifacts/release-evidence/v2.0.0-beta.2/conversation-beta/   6 captures
             artifacts/runtime-evidence/2026-10-11-v2-local-full-closure/clean-install/*.png
Logs:       artifacts/runtime-evidence/2026-10-11-v2-local-full-closure/backend-suite-clean-proxy.log
Evidence:   .../reverification.json · audio.json · github-replay.json · migration-matrix.json
            .../secret-scan.json · diagnostics.json · stable-readiness.{json,md} · human-report-empty.json
            reports/packaged_smoke.json · clean-install/results.json
```

Artifacts are **staged and upload-ready** in the closure worktree. They are build outputs of the
closure branch, and are not published.

---

## 9. Remaining blockers

1. **`BLOCKED_ACCOUNT`** — Google Calendar real-account replay. Needs an access token for a test
   account in `$env:CHENGZHU_GOOGLE_CALENDAR_TOKEN`, then
   `CHENGZHU_GOOGLE_CALENDAR_CONNECTOR_ENABLE=1` and the same 6-step connector sequence used for
   GitHub (catalog → connection → verify → sync → select → freeze → ask). Expected verification:
   one-page read probe succeeds, `account_hint` set, immutable snapshot revisions with visible drift
   for rescheduled/cancelled events, all-day and status events rejected.
2. **`BLOCKED_ACCOUNT`** — Google Drive / Docs. Same shape with
   `CHENGZHU_GOOGLE_DRIVE_CONNECTOR_ENABLE=1` and an explicit folder target.
3. **`BLOCKED_ACCOUNT`** — Gmail send-only. Needs an OAuth test app/account with exactly
   `openid`, `email`, `gmail.send`.
4. **`BLOCKED_EXTERNAL`** — Gmail sending to real recipients additionally requires Google OAuth
   sensitive-scope verification / consent-screen publication. Platform approval, not code.
5. **`BLOCKED_ACCOUNT`** — Microsoft To Do real-account replay, scope `Tasks.ReadWrite` only.
6. **`BLOCKED_EXTERNAL`** — MCP provider: no real adapter/auth/account runtime exists upstream. Only
   catalog fail-closed, unregistered-capability blocking and Preflight/diagnostics truth can be
   verified locally; no fake MCP connector was implemented.
7. **`BLOCKED_EXTERNAL`** — External Decision Log provider: no real provider exists upstream, so only
   the local reviewed draft/approve/audit/export path is exercised.
8. **`BLOCKED_HUMAN_EVIDENCE`** — real-user evidence. The stable gate was executed and returns
   **NO_GO, 29/37 checks failed, `V2_STABLE_RELEASE: FALSE`, `PMF_PROVEN: FALSE`**, driven entirely by
   sample size (0 users / 0 sessions / 0 labels against floors of 5 users, 20 sessions, 3 cross-session
   Spaces and 15–30 labels per metric). Tooling actively rejects placeholder labels.
9. **`BLOCKED_HUMAN_EVIDENCE`** — real device switching, sleep-wake and real participants
   (`soak_sim` marks these `BLOCKED-EXTERNAL`), plus a real multi-hour Interview / Project Sync /
   Design Review session with a human speaker.
10. **`BLOCKED_EXTERNAL_PERMISSION`** — download-back verification of a published release. No GitHub
    Release or tag was created: this repository publishes only from a green `main` via
    `.github/workflows/publish-current-version-on-green-main.yml`, and PR #70 is not merged. The
    `Release` workflow has already exercised the whole packaging path on this exact SHA (sidecar,
    installer, portable, packaged smoke, clean install) and is green, so the installers are staged
    with checksums and a ready-to-run replay; only merge → publish → download-back remains, and that
    requires repository authority this machine does not hold.
11. **`BLOCKED_EXTERNAL_PERMISSION`** — deleting the throwaway replay repo
    `huangdi97/chengzhu-connector-replay-2026-10-11`: the token has `repo` but not `delete_repo`.

Not a blocker, recorded for honesty: the closure branch carries a known **environment** caveat (§1a).
It makes a bare `pytest` run on this machine report one false red until the redundant `[::1]` entry is
removed from the user-level `NO_PROXY`. With it handled, the unmodified suite is fully green.

---

## 10. Release recommendation

**BETA_RC / BETA_RELEASE_READY** for a `v2.0.0-beta.3` prerelease — **never stable**.

Engineering gates, the packaged Windows product, the clean-install replay, the migration matrix and a
real-account GitHub replay all pass, and the packaged Windows product is *better* than published
beta.2 because the launch defect found here was fixed. Stable promotion is not eligible:
`BLOCKED_HUMAN_EVIDENCE` is unmet and the gate itself returns `NO_GO` / `PMF_PROVEN = FALSE`.

No beta.3 version bump was performed: it would invalidate the currently green exact-SHA CI + Release +
clean-install evidence, and the repository's own policy routes publication through a green `main`. It
should be cut deliberately as a separate pass after PR #70 merges.

---

## 11. Next actions that CANNOT be completed locally

1. Provide Google / Microsoft test-account tokens for a real-account replay (unblocks §9 items 1–5).
2. Complete Google OAuth sensitive-scope verification / consent publication to send real Gmail.
3. Merge PR #70 into `main`, then let the publisher workflow cut `v2.0.0-beta.3` from that exact SHA.
4. Run the published-asset download-back verification once a Release exists.
5. Grant `delete_repo` (or delete via the GitHub UI) to remove the throwaway replay repository.
6. Run an authorized real-use pilot and have humans label real sessions — this is the only input that
   can move the stable gate, and it cannot be synthesized.

---

## Final status

```text
LOCAL_FULL_CLOSURE     = PASS
LOCAL_ENGINEERING_GAP  = 0
LOCAL_RUNTIME_GAP      = 0
LOCAL_PACKAGING_GAP    = 0
LOCAL_EVIDENCE_GAP     = 0

EXTERNAL_BLOCKERS = [
  BLOCKED_ACCOUNT            (Google Calendar, Google Drive, Gmail, Microsoft To Do credentials)
  BLOCKED_EXTERNAL           (Google OAuth sensitive-scope verification; MCP provider; Decision Log provider)
  BLOCKED_EXTERNAL_PERMISSION(merge/publish for download-back; delete_repo)
  BLOCKED_HUMAN_EVIDENCE     (real users, real labels, real device switching, real multi-hour sessions)
]
HUMAN_EVIDENCE_PENDING = TRUE

STABLE_READY = FALSE
RECOMMENDED_NEXT_RELEASE = v2.0.0-beta.3 (prerelease), staged from PR #70 (candidate c078304)
```
