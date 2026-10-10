# Chengzhu v2.0-R1 — Design / Runtime Reality Report

> **Updated:** 2026-10-10
>
> **Status:** DESIGN_COMPLETE / CONTRACT_COMPLETE / CONVERSATION_BETA_RUNTIME_AVAILABLE / BETA_2_PRERELEASE_PUBLISHED
>
> **Stable v2 packaged release:** NOT CLAIMED
>
> **Real-user value / PMF:** NOT CLAIMED

This report supersedes the original PR #17 design-stage wording that said Conversation runtime did not exist. The historical design work remains valid input, but that implementation-status statement is no longer true.

## 1. Current repository baseline

```text
stable public release:
v1.4.2 Interview

public Conversation prerelease:
v2.0.0-beta.2 @ cac605edf413ec248babf02ea9f73da708d156f8

Conversation runtime:
merged PR #18

design/runtime closure:
merged PR #19

current pure-repo closure baseline:
main @ 383978fa480aac35d214dce3fa4e9fa5ebb17118

current baseline CI:
GitHub Actions run 37901753321 = PASS

public beta line:
v2.0.0-beta.2 @ cac605edf413ec248babf02ea9f73da708d156f8

post-beta.2 main additions:
connector capability registry + stable promotion evidence gate + privacy-safe local Conversation reminders
```

The authoritative current sources are:

- `docs/canonical/Chengzhu_v2.0-R1_PERSONAL_CONVERSATION_INTELLIGENCE.md`
- `docs/canonical/Chengzhu_v2.0-R1_IMPLEMENTATION_MASTER_GOAL.md`
- `docs/canonical/Chengzhu_v2.0-R1_DESIGN_RUNTIME_CLOSURE_MATRIX.md`

The older `docs/goals/CHENGZHU_V2_0_IMPLEMENTATION_MASTER_GOAL.md` is retained as implementation-history provenance, not as a list of currently unimplemented stages.

## 2. What exists as real runtime

Conversation Profile now has real:

- Profile switcher and opt-in onboarding;
- Conversation Home;
- Space / Goal / Session lifecycle;
- Prepare and auditable Preflight;
- frozen Session Pack with digest;
- real capture ownership and transcript path;
- deterministic transcript candidate extraction;
- review-first Decision / Commitment / Deadline truth promotion;
- reviewed longitudinal Open Threads;
- source-aware Manual Ask over frozen sources / Quick Notes / current transcript;
- cross-session Recall;
- Contribution Opportunity / Answer Cue / Risk / Talking Point / Question / Delivery;
- profile-aware Guidance Arbiter and SILENT;
- explicit Counterparty State and stakeholder-aware Expression;
- Continue / Pins / Next Focus;
- reviewed local Follow-up / Task / Issue / Decision Log drafts;
- Conversation-native History;
- retention / delete / export / tombstones;
- grounded global Decision / Commitment / Open Question search;
- current Session export;
- Conversation subsystem diagnostics;
- additive schema v6 temporal provenance for Deadline / Commitment review;
- additive schema v7 Manual Screen Context observations with raw-image non-persistence and frozen vision-route provenance.

Therefore these old statements are **false** and must not be repeated:

```text
V2_RUNTIME_COMPLETE = FALSE because no routes/UI/DB exist
future_profile.py is only a hypothetical placeholder
Conversation has no persistence/runtime UI
```

## 3. Truth and privacy boundaries that remain enforced

```text
AI_EXTRACTED != confirmed truth
Quick Note != evidence
transcript != agreement
APPROVED local draft != external execution
capture local != STT local
user consent report != system-verified consent
transparency plan != automatic participant notification
runtime available != stable packaged release
synthetic green != real-user value
```

Current capability / fail-closed boundaries:

- Conversation Manual Screen Context = AVAILABLE when the frozen vision route satisfies processing policy;
- Conversation AUTO Screen Context = AVAILABLE with Live explicit-start / off-the-record / fail-stop semantics;
- Conversation Share Privacy / PRIVATE_OVERLAY = DESKTOP RUNTIME AVAILABLE, verify-at-start with Electron content-protection proof, Live-visible, session-scoped restoration, best-effort only;
- Conversation Human Coach = RUNTIME AVAILABLE in the beta.2 source line; session-scoped, policy/transparency gated, advice-only and non-evidence; real-session value is still unvalidated;
- Calendar / Mail / Docs / project-tracker connectors;
- actual external email/task/issue/decision-log execution;
- automatic participant chat notice / watermark;
- organization/shared truth registry.

These are external or separately governed runtime gates, not features to fake with placeholders.

## 4. Final pure-repo closure now present on main

The final audit closes canonical items that were still implementable without external dependencies, Windows new stable-release evidence, or real users:

- global grounded Conversation Item search;
- Ctrl+K find Decision / Commitment / Open Question;
- current Session categorized local export;
- ad-hoc semantics aligned to one Space-backed truth model;
- time/date provenance: original text + normalized datetime + timezone + ambiguity;
- ambiguous Deadline cannot enter reviewed long-term truth until explicitly resolved;
- subsystem-level Conversation Diagnostics with user-facing 可用 / 受限 / 需要处理 states;
- Manual + explicit-start AUTO Screen Context with session-scoped observation truth, frozen vision fingerprint, retention/export integration and no raw screenshot persistence;
- desktop Conversation Share Privacy with verify-at-start runtime proof and baseline restoration;
- session-scoped Conversation Human Coach with policy/transparency gates and non-evidence boundary;
- fail-closed connector capability registry with frozen grants;
- machine-readable stable promotion evidence evaluator;
- opt-in privacy-safe local reminders for Chengzhu-internal scheduled Sessions;
- stale public-truth documents aligned with current runtime.

## 5. What may be claimed after final audit CI is green

```text
V2_DESIGN_COMPLETE = TRUE
V2_CONTRACT_COMPLETE = TRUE
V2_RUNTIME_AVAILABLE = TRUE
V2_BETA_PRERELEASE_PUBLISHED = TRUE
BETA_TAG = v2.0.0-beta.2
BETA_SOURCE_SHA = cac605edf413ec248babf02ea9f73da708d156f8
PURE_REPO_DESIGN_RUNTIME_GAPS = CLOSED
CURRENT_MAIN_CLOSURE_HEAD = 383978fa480aac35d214dce3fa4e9fa5ebb17118
CURRENT_MAIN_CI_RUN = 37901753321
CURRENT_MAIN_CI_GATE = PASS
INTERVIEW_STABLE_RELEASE_BASELINE = v1.4.2
```

## 6. What still may NOT be claimed

```text
V2_PRODUCTIZED_RELEASE = TRUE
REAL_CONVERSATION_VALUE_PROVEN = TRUE
REAL_USER_VALIDATED = TRUE
PMF_PROVEN = TRUE
ALL_EXTERNAL_CONNECTORS_AVAILABLE = TRUE
```

A stable v2 productized release still requires the independent stable-review path: real pilot + human-label gate first, then current Windows packaged evidence, clean-install replay, artifacts/hashes/download-back/provenance, public-truth review and no critical runtime blocker. beta.2 engineering evidence alone cannot promote stable.

Real-user validation still requires real Project Sync / Design Review sessions and human-labeled evaluation for Recall Precision, Opportunity Precision, Interruption Regret, Useful Silence, cross-session value and cognitive load.

## 7. Final reality rule

Repository state is authoritative over historical planning prose.

When a future agent continues this project, it must first verify current `main`, canonical closure matrix, latest CI, beta/stable release channels and product-evidence gates. Historical PRs and implementation branches are provenance only; they must not be treated as the current work queue.

At the 2026-10-10 truth-sync baseline, the next legitimate maturity work is **external provider integration or real-user evidence**, not another synthetic declaration that Conversation design/runtime is incomplete.
