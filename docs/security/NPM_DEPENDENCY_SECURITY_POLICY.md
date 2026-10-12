# npm Dependency Security Policy

## Purpose

Chengzhu must not translate the single number printed by `npm ci` into a packaged-runtime security claim.

The repository has three materially different JavaScript dependency surfaces:

```text
frontend production graph
Electron runtime
dev / test / build toolchain
```

They are audited together for visibility, but they do not have the same release semantics.

## Automatic blocking policy

CI creates:

```text
artifacts/npm-audit/frontend-production.json
artifacts/npm-audit/frontend-full.json
artifacts/npm-audit/desktop-full.json
artifacts/npm-audit/SUMMARY.md
```

The aggregate CI gate fails automatically when:

1. the frontend **production** graph contains any `high` or `critical` advisory; or
2. npm attributes a `high` or `critical` advisory directly to the `electron` package.

Electron is declared under `devDependencies` because electron-builder consumes it during packaging, but the Electron runtime binary is shipped to Windows users. It therefore receives a runtime-sensitive exception instead of being hidden by `--omit=dev`.

## Findings that are reported, not automatically called packaged-runtime vulnerabilities

The full frontend and desktop audit graphs are retained even when they do not block the build.

Examples include:

- Vite / Vitest / Playwright / jsdom test and development tooling;
- electron-builder and its packaging helpers;
- target-specific packaging code that is not used by Chengzhu's Windows targets.

These findings still require review. REPORT does **not** mean IGNORE. It means the release decision must answer:

```text
Is the vulnerable package shipped?
Is the vulnerable code path reachable?
Does Chengzhu use the affected target/provider/feature?
Can the issue affect build provenance even if users never execute the package?
Is there a non-breaking patched version?
```

## Current target truth

The desktop release configuration builds:

```text
Windows x64 NSIS installer
Windows x64 portable zip
```

It does not configure an AppImage target.

The repository currently contains no `electron-updater` or `autoUpdater` application integration. This is an applicability fact, not a permanent exemption: CI still retains the desktop full-audit report because dependencies and release architecture can change.

## Vite boundary

Vite is a frontend dev/build dependency. The installed Windows application serves the already-built `frontend/dist`; it does not start a Vite development server.

Therefore a Vite dev-server advisory is not automatically evidence of a vulnerability in the published Windows runtime. It can still matter to developers/CI and should be patched when a compatible release is available.

## Prohibited shortcuts

Do not:

- run `npm audit fix --force` blindly;
- upgrade electron-builder across a major boundary solely to make the audit count smaller;
- suppress an advisory without recording why its path is unreachable;
- claim `0 runtime vulnerabilities` merely because `npm audit --omit=dev` is clean;
- claim a published release is vulnerable solely from the aggregate `npm ci` count.

## Release truth

Dependency audit is one input to release/security review. It does not change:

```text
V2_STABLE_RELEASE
REAL_USER_VALIDATED
PMF_PROVEN
```

and it does not rewrite already-published tag/source provenance.

A dependency fix that changes shipped runtime or release-build integrity must go through the normal exact-SHA CI/package/release process before it can be attributed to a downloadable version.
