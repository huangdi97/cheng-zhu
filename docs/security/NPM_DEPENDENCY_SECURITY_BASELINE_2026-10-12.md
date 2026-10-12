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

The current production graph was clean.

Tailwind `3.4.19` remains the v3 LTS line, while npm's automatic remediation proposes a Tailwind 4 major upgrade. Chengzhu does not perform that migration merely to reduce an audit counter; it requires a separate UI/build migration and visual-regression decision.

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

The most severe observed transitive finding was `tar` critical. npm identified the electron-builder v26.15+ line as the remediation path.

Electron itself had no high/critical advisory in the measured npm audit.

## Selected upgrades

This branch uses npm itself to regenerate the lockfiles for:

```text
frontend:
  vite 6.4.3 → 6.4.4

desktop:
  electron-builder 25.1.8 → 26.16.1
```

Reasons:

- Vite 6.4.4 is a patch within the existing 6.4 line and closes the October 2026 dev-server advisories affecting 6.4.3.
- electron-builder 26.16.1 stays on the stable v26 line and contains the post-26.15 security fixes for the builder-util-runtime / app-builder-lib generation while avoiding the larger v27 migration.
- Chengzhu's Windows release target is x64 NSIS + zip; it does not build AppImage and does not integrate `electron-updater` / `autoUpdater`.
- Windows x64 packaged smoke remains mandatory because target applicability does not replace real packaging validation.

The normal scope-aware CI audit on the committed upgraded lockfiles confirmed the desktop graph dropping from `12 high + 1 critical` to `8 moderate`, with `high=0`, `critical=0`, and no Electron-runtime blocking advisory. The frontend production graph remains at `0` vulnerabilities; the remaining frontend `2 moderate + 6 high` findings are confined to the documented Tailwind 3 dev/build graph.

## Release truth boundary

These dependency changes are **not** part of the already-published `v2.0.0-beta.4`.

```text
v2.0.0-beta.4 tag/source remains:
0e1d89ad381a93c1dcd9725418d9cbd5b3c71fcc
```

If this hardening is later distributed to users, it requires a new version/tag and the normal exact-SHA Windows release cycle. Do not rewrite beta.4 provenance to include it.

This security work does not change:

```text
V2_STABLE_RELEASE = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```
