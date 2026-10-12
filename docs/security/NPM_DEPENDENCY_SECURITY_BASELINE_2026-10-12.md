# Chengzhu npm Dependency Security Baseline — 2026-10-12

## Purpose

This baseline records dependency-security truth by execution surface. It must not turn the aggregate number printed by `npm ci` into a claim about the packaged Windows runtime.

Audited surfaces:

```text
frontend production graph
frontend full dev/build graph
desktop full graph
Electron shipped runtime exception
Windows x64 packaged release path
```

## Measured current-main baseline before the Vite patch

Exact main SHA:

```text
a9b5650ce5a276ad91307631b8135f454b8c6935
```

CI #911 / dependency-security completed successfully and reported:

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
  moderate = 8
  high = 0
  critical = 0

Electron runtime high/critical = 0
desktop build/toolchain high/critical = 0
```

The desktop result reflects main's `electron-builder 26.17.0` upgrade. It must not be replaced by the stale `26.16.1` value from superseded PR #82.

## Vite patch

Current main still declares:

```text
vite = ^6.4.3
lockfile resolved vite = 6.4.3
```

Vite's October 2026 advisories list `<=6.4.3` as affected for the 6.x line and `6.4.4` as the patched 6.x release for the applicable dev-server issues.

This branch therefore performs the narrow patch:

```text
vite 6.4.3 → 6.4.4
```

The package-lock content is copied from the npm-resolved lock generated on PR #82. No integrity hash is hand-written.

Vite is a dev/build dependency. Chengzhu's packaged Windows application serves the prebuilt frontend and does not run a Vite development server. Patching it still reduces developer/CI exposure and removes the known 6.4.3 dev-server advisory surface without requiring a framework major upgrade.

## Electron-builder truth

Current main uses:

```text
electron-builder = 26.17.0
```

This is retained. The cleanup PR must never downgrade it to the `26.16.1` value present on stale PR #82.

Main CI #911 already reports:

```text
desktop full high = 0
desktop full critical = 0
Electron runtime high/critical = 0
```

Remaining desktop findings are moderate and remain visible in the full audit artifact.

## Frontend dev/build residual findings

The Vite patch does not imply the entire frontend full graph becomes clean. The current baseline still includes findings in the Tailwind 3 dev/build toolchain. Those remain reported and should be handled by a separate, visually verified build-system migration rather than by blind `npm audit fix --force`.

Automatic release blocking continues to be based on:

- frontend production high/critical;
- advisories attributed directly to shipped Electron runtime;
- the normal build/test/package/release gates.

Full dev/build findings remain visible evidence and require applicability review.

## Release boundary

The already-published public Beta remains immutable:

```text
v2.0.0-beta.4
source/tag SHA = 0e1d89ad381a93c1dcd9725418d9cbd5b3c71fcc
```

Neither the electron-builder 26.17.0 hardening nor this Vite 6.4.4 patch exists in beta.4 binaries.

If these post-beta.4 security changes are distributed, they require a new version/tag and the complete exact-SHA Windows release cycle.

This security work does not change:

```text
V2_STABLE_RELEASE = FALSE
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```
