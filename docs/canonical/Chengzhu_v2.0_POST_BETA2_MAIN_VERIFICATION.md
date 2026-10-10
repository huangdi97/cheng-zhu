# Chengzhu v2.0 — Post-beta.2 Main Verification
## Current main after beta.2 publication

**Date:** 2026-10-10  
**Verification branch:** `chore/v2-post-beta2-main-verification`  
**Base main SHA:** `383978fa480aac35d214dce3fa4e9fa5ebb17118`

---

## 1. Why this verification exists

The public prerelease `v2.0.0-beta.2` is pinned to:

```text
cac605edf413ec248babf02ea9f73da708d156f8
```

Current `main` has continued past that prerelease and now includes post-beta.2 work, including:

- fail-closed connector capability registry and frozen connector grants;
- machine-readable stable promotion evidence gate;
- privacy-safe local upcoming Conversation reminders;
- reminder persistence / Electron bridge / restart behavior;
- public-truth documentation for those capabilities.

Those changes are real repository state, but they are newer than beta.2.

Therefore:

```text
beta.2 release evidence
!=
current main evidence
```

A new full-current-main verification is required before treating the post-beta.2 main line as an engineering-evidenced checkpoint.

---

## 2. Current product truth

Allowed before this verification completes:

```text
V2_DESIGN_COMPLETE = TRUE
V2_CONTRACT_COMPLETE = TRUE
V2_RUNTIME_AVAILABLE = TRUE
V2_BETA_PRERELEASE_PUBLISHED = TRUE
```

Not inferred from beta.2:

```text
POST_BETA2_MAIN_CI_VERIFIED = TRUE
POST_BETA2_MAIN_PACKAGED_VERIFIED = TRUE
V2_STABLE_RELEASE = TRUE
REAL_USER_VALIDATED = TRUE
PMF_PROVEN = TRUE
```

---

## 3. Full gate required on this branch

This branch must reuse the repository's normal PR gate, including:

- backend lint / compile / test;
- frontend typecheck / unit / build;
- desktop tests;
- Playwright functional;
- visual gate;
- real backend e2e smoke;
- Windows packaged smoke;
- aggregate `ci-gate`.

A partial green result is not sufficient.

---

## 4. Scope of the audit

This is intentionally not a new product-feature branch.

The current pure-repo v2 closure already covers:

- Conversation Home / Spaces / Prepare / Preflight / Live / Continue / History;
- frozen Session Pack;
- provenance-aware truth and temporal provenance;
- reviewed longitudinal Open Threads;
- derived Conversation State;
- source-aware Manual Ask and global grounded search;
- Guidance Arbiter / Expression Plan;
- Counterparty State;
- six frozen Profile Playbooks;
- MANUAL + explicit-start AUTO Conversation Screen Context;
- verified desktop Conversation Share Privacy;
- Conversation Human Coach;
- local reviewed DraftActions;
- connector capability contract/registry;
- stable-promotion evidence evaluator;
- privacy-safe local scheduled Conversation reminders.

Remaining items that require non-repository evidence or a real external provider are not to be faked in this branch:

- Calendar / Mail / Docs / project-tracker provider implementation;
- actual external task/email/issue/decision-log execution;
- automatic participant chat notice / watermark;
- real Project Sync / Design Review pilot evidence;
- human-labeled quality thresholds;
- stable v2 packaged/release decision;
- real-user validation / PMF.

---

## 5. Acceptance

This verification is successful only when the **actual final PR HEAD** passes the full gate.

After PASS, the allowed claim becomes:

```text
POST_BETA2_MAIN_CI_VERIFIED = TRUE
```

This still does not claim a new public binary release.

A future `beta.3` or stable release needs a separately pinned release SHA and release provenance.

---

## 6. Next maturity step after engineering PASS

Once current main is green, the engineering/design path is no longer the limiting factor.

The next product gate is:

```text
authorized real-use pilot
→ human labels
→ stable-promotion evaluator
→ stable release review
```

Project Sync and Design Review remain the first profiles for that evidence.

