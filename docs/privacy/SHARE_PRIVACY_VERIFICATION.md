# What the privacy claims actually verify

This records what was **measured on this machine** about 共享隐私, network egress,
local exposure and policy enforcement — including what could not be verified here.
It exists so the next person does not re-derive it, and so nobody mistakes a
best-effort mitigation for a guarantee.

## 1. 共享隐私 (PRIVATE_OVERLAY)

`desktop/sharePrivacy.js` asks Windows to exclude the app's windows from supported
capture paths via Electron's `setContentProtection`. Two modes only:
`OFF` (default) and `PRIVATE_OVERLAY`.

Verified on the packaged Windows build, over CDP against the real windows:

| State | main window | private overlay | verdict |
| --- | --- | --- | --- |
| OFF | unprotected | unprotected | `runtime_verified: true` |
| ON, overlay hidden | protected | protected | `true` |
| **ON, overlay on screen** (main hidden) | hidden → excluded from verdict | protected | `true` |
| ON, overlay first then toggled ON | hidden → excluded | protected | `true` |

**Defect found and fixed here.** The runtime verdict used to include hidden
windows. Windows clears a hidden window's display affinity, so
`isContentProtected()` reads `false` the moment the main window hides — which is
exactly the Live layout (main window hidden on purpose, private overlay on screen).
Result: `runtime_verified: false` and `protected: false` in the one state where
protection matters, so the tray tooltip read `共享隐私：关` while the overlay was
actually protected.

`readWindowProtection` now returns `null` for a window that exists but is not
visible, so hidden windows leave the verdict, while a visible unprotected window
still fails it (covered by `share privacy verdict ignores windows that are not on
screen` in `desktop/r2Desktop.test.js`).

**Not verified, and cannot be verified here.** Whether Windows really excludes the
window from a given capture path. A GDI desktop capture in this environment returns
neither the app nor a black rectangle for the window rect, so the harness cannot
distinguish "excluded" from "no interactive desktop". Treat the exclusion as
best-effort: capture paths differ per OS, per tool and per version, and content
protection does not defeat hardware capture cards, some remote-desktop stacks, or a
phone pointed at the screen. The product copy says this and must keep saying it.

## 2. What leaves the machine

- **No update check.** `desktop/package.json` builds with `--publish never`; there
  is no `electron-updater`/`autoUpdater` anywhere in the desktop process. The app
  never phones home on its own.
- **One listener, loopback only.** `backend/sidecar.py` binds `--host 127.0.0.1`
  (default). The runtime evidence bridge binds `127.0.0.1` and authenticates with a
  nonce + token.
- **The only outbound traffic is what the user configures**: the model API bases
  present in the source are the provider defaults (OpenAI, DeepSeek, Google,
  Volcengine Ark) plus optional Google Calendar/Drive/Meet integration endpoints.
  When AI is enabled, resume/JD/transcript content necessarily goes to that
  provider — that is the product, and it should be stated as such, not hidden.
- **Analytics are local.** `track()` posts to the app's own backend
  (`/api/product/events`); nothing is shipped to a third-party endpoint.
- **Human Coach is opt-in and token-guarded.** `api/coach/router.py` starts a second
  listener on `0.0.0.0:18180` *only while a coach session is active*, serving only
  the helper page and token-guarded endpoints (`x-coach-token`), and stops it when
  idle. This is the one interface reachable from the LAN, by design, and it is now
  stated in Settings → 隐私与策略 (`COACH_LAN_COPY`): the port, the token, that it
  closes with the session, and that everything else stays on loopback.

## 3. Local data at rest

Verified by reading the packaged profile: `product.db`, `resume_history.db`,
`intelligence.db` and friends are **plaintext SQLite** — the seeded Goal
(`MindRank · AIDD Agent Engineer`) is readable with a text search of the file.

That is a deliberate local-first trade-off, but it means the real protection for
this data is the OS account boundary plus disk encryption (BitLocker/FileVault).
Settings → 隐私与策略 now says exactly that, next to the 共享隐私 control
(`LOCAL_DATA_COPY` in `frontend/src/lib/privacyCopy.ts`), and a unit test keeps the
sentence from being trimmed away.

## 3a. Resume uploads at rest (Windows)

Inspecting the storage layer changed the recommendation: the parsed text in
`resume_history.db` is the smaller half. The **uploaded document itself** is written
verbatim to `resume_uploads/<uuid>.<ext>` — the exact PDF/DOCX the user handed over.

`backend/services/privacy/at_rest.py` now protects those bytes with DPAPI
(`CryptProtectData`, scoped by a per-purpose entropy), so the file on disk is
`CZHDPAPI1\n` + a blob that only the same Windows user on the same machine can
unwrap. Measured on this machine:

| Check | Result |
| --- | --- |
| file starts with the marker | yes |
| plaintext bytes still present in the file | no |
| `_read_entry_bytes()` returns the original document | yes |
| tampered blob | `AtRestError`, not silent garbage |
| wrong purpose | `AtRestError` |

What it does not do, and the code says so in `status()`:

- **The resume text columns are protected too** (`resume_entries.resume_summary`,
  `preview`), measured by scanning the database and its WAL for a marker string: it
  does not appear, and the UI still renders the text. The other stores (Goal fields,
  transcripts, knowledge base) stay plaintext — the knowledge base needs FTS, so
  encrypting it is a search problem, not a crypto one.
- **It does not stop a process running as the same user** — that process can call
  `CryptUnprotectData` too. It closes the "profile copied to another machine or into a
  synced folder" case, not a compromised account.
- **Non-Windows platforms get no protection.** `protect()` returns `None`, writes
  stay plaintext, and `status()` reports `scheme: none` rather than pretending.
  macOS has the right home for a key (Keychain) but no cipher in the standard
  library, and this environment cannot reach PyPI to add `cryptography`, so the macOS
  path stays unimplemented rather than hand-rolled.

Reads stay backward compatible: anything without the marker is returned untouched, so
an existing plaintext directory keeps working and is protected from the next write.

## 4. Policy enforcement

`AI_FORBIDDEN` / `HUMAN_*` policies are enforced in backend policy code and covered
by the strict eval that CI runs (`python -m evals.r2_eval --check`, mandatory case
`11 AI_FORBIDDEN`). Running it locally returns `failed_mandatory: []`.

## 5. What this document does not claim

- It is not a security audit, a threat model or a penetration test.
- It does not claim the overlay is undetectable, or that a determined interviewer,
  proctoring tool or hardware capture cannot see it.
- It does not cover macOS (ScreenCaptureKit path) — untested here.

## 3b. 本机暴露自检

`GET /api/privacy/exposure` (Settings → 隐私与策略 → 本机暴露自检) reports the
filesystem as it is: how many uploaded originals are protected, how many resume rows
carry the marker, the database files and their sizes, and the disk-encryption state
(BitLocker on Windows, FileVault on macOS).

It is a report, not a promise. `disk_encryption.protected: null` means "could not
determine" — it is never counted as a pass, and it is never reported as a gap either.
`verdict` flips to `exposed` only when something is measurably plaintext or the
platform has no at-rest implementation at all.
