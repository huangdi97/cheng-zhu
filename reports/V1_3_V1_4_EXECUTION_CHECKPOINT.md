# Chengzhu v1.3 → v1.4 Execution Checkpoint

> Current truth only. Older checkpoint content that said “no PR / no CI / six Playwright failures / screenshots not started” is obsolete.

## Git

```text
repository  huangdi97/cheng-zhu
main        48d06ffcdc5769332cba48e04577e6d787ad4f2d
v1.3 PR     #5 MERGED
v1.4 branch feat/chengzhu-v1.4-validation-hardening
v1.4 PR     #9 OPEN
```

## v1.3 merge proof

```text
PR #5 head              a680ef764bfc59f48595a998ceed0f6e37294ed1
PR CI                   37285890890 SUCCESS
PR Release preflight    37285890873 SUCCESS
merge commit            48d06ffcdc5769332cba48e04577e6d787ad4f2d
main CI                  37287635769 SUCCESS
```

The public Releases page must still be checked separately. Code merged to main is not equivalent to a published GitHub Release.

## v1.3 implemented product surface

- Goal-centered IA
- Action Home
- Goal Room / Prepare / Interviews / Offer
- Next Focus
- Person Workspace / Fact Inbox
- Stories / Skills / Expression
- Material taxonomy + lifecycle
- Quick Notes
- Question Banks
- Command Palette
- Guided First Practice
- Practice 3.0 / Adaptive Follow-up / Panel
- Role Rubrics / Progress Trends
- Content Coach / Delivery Coach
- Preflight 3.0
- Live Cue-first UI
- Pin / Nudge / Closing
- Overlay 3.0
- Reflection write-back
- History
- Settings 3.0
- Data export/delete
- Accessibility / Light-Dark / 390px
- Personal Conversation Intelligence future contracts retained, not productized

## Runtime UI evidence

See:

```text
reports/CHENGZHU_V1_3_RUNTIME_UI_AUDIT.md
```

Packaged-resource + packaged-sidecar evidence covers the v1.3 Studio/Practice/Live/Reflection UI. Hosted Windows cannot honestly prove native BrowserWindow compositor / overlay multi-monitor geometry because there is no interactive desktop; this remains an environment limitation rather than being labelled PASS.

## Latest core/eval evidence

Latest successful v1.3 PR CI:

- backend: 1062 passed / 3 skipped
- mandatory eval: 20/20
- strict route exact: 1.0
- seven-turn exact: 1.0
- unsupported personal-claim block rate: 1.0
- held-out v2 exact: 0.8333
- real-provider eval: BLOCKED_EXTERNAL (no provider credential)
- frontend / desktop / Playwright / visual / packaged-smoke / e2e-smoke / ci-gate: SUCCESS

## v1.4 scope

v1.4 is validation hardening, not another feature expansion.

Six questions:

1. Goal reuse
2. Reflection → Prepare
3. Fast Cue usefulness
4. Practice transfer
5. Fact Inbox burden
6. Quick Notes / Pin value

Synthetic / controlled evidence may prove engineering paths only.

Always retain:

```text
REAL_USER_EVIDENCE_PENDING
PMF_PROVEN = false
```

until real participant evidence exists.

## v1.4 synthetic continuity

The CI evidence generator exercises isolated disposable SQLite stores and requires:

- 7-day continuity
- 30-session continuity
- 100-session continuity
- export/delete integrity
- no cross-Goal contamination
- Reflection → Next Focus
- Fast Cue usage signals
- mock/synthetic Practice transfer labelling

Current v1.4 hardening additionally exercises:

- Fact Inbox opened + resolved
- Reflection → Quick Note
- Pin → Next Focus through explicit user action

## Current exact next gate

PR #9 must go green with the new E/F write-back assertions.

After PR #9 CI:

```text
green
→ merge #9
→ main CI
→ final v1.4 engineering report
```

Separately, public v1.3 Release/tag remains a release-operation gate if the Releases page still only shows v1.2.2.

## External evidence that automation cannot fabricate

- real-user longitudinal Goal reuse
- perceived Fact Inbox burden
- real interview transfer
- real provider quality / latency / cost
- interactive Windows multi-monitor Overlay visual proof
- code signing
- macOS signing/notarization
- public Human Coach relay
- true long-duration human session evidence

Do not convert these to PASS merely because synthetic tests are green.
