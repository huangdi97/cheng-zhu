# Chengzhu npm Dependency Security Baseline — 2026-10-12

## Scope

This baseline separates security findings by execution surface instead of treating the aggregate number printed by `npm ci` as a packaged-runtime claim.

Audited surfaces:

```text
frontend production graph
frontend full dev/build graph
desktop full graph
Electron shipped runtime exception
Windows release target applicability
```

## Pre-upgrade measured baseline

PR #81 / CI #897 produced the first scope-aware audit artifact from the exact repository lockfiles.

```text
frontend production:
  total = 0
  high = 0
  critical = 0

frontend full:
  moderate = 2
  high = 6
  critical = 0

desktop full:
  high = 12
  critical = 1

Electron package high/critical:
  0
```

Therefore the previous aggregate npm counts did **not** mean that the published Windows application had six or thirteen runtime high-severity vulnerabilities.

### Frontend full-graph findings

The high/moderate findings were development/build dependencies, led by the Tailwind 3 toolchain:

```text
braces
chokidar
fast-glob
micromatch
source-map-js
tailwindcss
postcss-nested
postcss-selector-parser
```

The production frontend graph was clean.

Tailwind `3.4.19` remains the v3 line used by Chengzhu, while npm's automatic remediation proposes a Tailwind 4 major upgrade. Chengzhu does not perform that migration merely to reduce an audit counter; it requires a separate UI/build migration and visual-regression decision.

### Desktop full-graph findings

The desktop full audit attributed the high/critical chain to electron-builder tooling, including:

```text
electron-builder
app-builder-lib
builder-util
builder-util-runtime
@electron/rebuild
tar
node-gyp
cacache
make-fetch-happen
electron-publish
```

The most severe observed transitive finding was `tar` critical. npm identified the maintained electron-builder v26 line as the remediation path.

Electron itself had no high/critical advisory in the measured npm audit.

## Current hardening state

The post-beta.4 hardening is intentionally split so lockfiles generated against different dependency roots are not merged over one another.

### Desktop — already on main

Current main contains:

```text
electron-builder 25.1.8 → 26.17.0
```

That upgrade was resolved and committed directly on top of the current main dependency graph. Scope-aware CI reported the desktop full graph dropping from `12 high + 1 critical` to no high/critical findings; remaining findings are non-blocking moderate build-tool findings. Electron runtime high/critical remains zero.

### Frontend — this replacement PR

This branch carries only:

```text
vite 6.4.3 → 6.4.4
```

The exact `frontend/package-lock.json` is the npm-resolved lockfile produced during the original security-upgrade work. Vite 6.4.4 stays within the existing 6.4 line and closes the October 2026 dev-server advisories affecting 6.4.3.

The frontend production graph remains the release-relevant runtime gate and must stay at zero high/critical findings. Remaining Tailwind 3 dev/build findings are tracked separately and do not get silently reclassified as packaged-runtime vulnerabilities.

## Why PR #82 is superseded

PR #82 originally contained both:

```text
vite 6.4.4
electron-builder 26.16.1
```

While it was under validation, main independently advanced desktop to the newer `electron-builder 26.17.0`. PR #82 therefore became structurally stale and diverged on `desktop/package-lock.json`.

Merging it directly would risk downgrading the already-hardened Desktop dependency graph. The safe replacement is:

```text
current main (electron-builder 26.17.0)
+ frontend Vite 6.4.4 exact npm lock
+ regenerated notices from both current graphs
```

No desktop dependency or lockfile is changed by the replacement PR.

## Third-party notice truth

`THIRD_PARTY_NOTICES.md` is regenerated logically from the two exact lockfile surfaces:

- Frontend npm section: upgraded Vite 6.4.4 lock;
- Desktop npm section: current main electron-builder 26.17.0 lock;
- Backend/Python section: unchanged current main truth.

The license gate remains mandatory. Security upgrades do not bypass dependency-license review.

## Release truth boundary

These dependency changes are **not** part of the already-published `v2.0.0-beta.4`.

```text
v2.0.0-beta.4 tag/source =
0e1d89ad381a93c1dcd9725418d9cbd5b3c71fcc
```

Current post-beta.4 main already contains Desktop hardening, while this replacement PR adds the frontend Vite patch. If these hardening changes are distributed to users, they require a new version/tag and the normal exact-SHA Windows release cycle. Do not rewrite beta.4 provenance to include them.

This security work does not change:

```text
V2_STABLE_RELEASE = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```
