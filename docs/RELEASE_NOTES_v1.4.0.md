# 成竹 Chengzhu v1.4.0

## Product Validation Hardening

v1.4.0 does not replace the v1.3 Goal-centered Interview OS and does not add a new top-level product. It hardens the loop that v1.3 introduced:

```text
Goal → Next Focus → Prepare → Practice → Preflight → Live → Reflection → Next Focus
```

The purpose of this release is to make that loop measurable, durable and auditable without turning local analytics into surveillance or automated evidence into a PMF claim.

## What v1.4 hardens

### A · Goal reuse

Local product events now support measuring whether a Goal is reopened and reused across preparation, practice and sessions. This is a continuity signal, not an engagement score.

### B · Reflection → Prepare

Reflection actions can write back into the current Goal's Next Focus. Engineering tests prove the write-back path and controlled dogfood verifies that reopening the Goal sees the updated next action.

### C · Fast Cue usefulness

v1.4 distinguishes:

- cue rendered
- cue expanded
- Deep Answer opened
- user feedback
- candidate speech after cue where the applicable local mode permits analysis

A rendered cue is not treated as proof that the cue was useful.

### D · Practice transfer

Practice observations can be linked to later observations of the same rubric dimension. Synthetic / mock-to-mock evidence is explicitly labelled and is never described as real-interview transfer.

### E · Fact Inbox burden

The local validation report exposes:

- backlog size
- resolution rate
- dismissal rate
- age / reopen signals where available

The hardening rule is to reduce automatic Fact Inbox generation or batch similar items if the product becomes maintenance work for the user.

### F · Quick Notes / Pin Moment value

Local-only events capture whether Quick Notes are selected into a Pack and whether user-created Pins lead to Reflection actions or Next Focus.

The intent is to measure whether these features help the user continue the same Goal, not whether they can produce more telemetry.

## Longitudinal engineering evidence

The repository includes deterministic isolated-data dogfood for:

- 7-day continuity
- 30-session continuity
- 100-session reliability

These runs use disposable SQLite stores and are classified as:

```text
SYNTHETIC_DOGFOOD
```

They are engineering evidence only.

## Product-readable validation UI

Settings → Diagnostics exposes the six validation questions directly instead of only printing a raw JSON blob.

Goal Room exposes explainable within-Goal trends such as:

- technical depth
- ownership clarity
- delivery timing

It does not display:

- hire probability
- candidate percentile
- unsupported readiness score

## Reliability and data integrity

v1.4 keeps the v1.2/v1.3 verified core frozen while hardening:

- migration compatibility
- product-store primary-key integrity
- export / delete integrity
- restart-safe Goal continuity
- material replacement semantics
- local ProductEvent privacy
- packaged Windows smoke
- clean-install replay
- runtime UI evidence

## Privacy

Product validation is local-first.

Events must not contain:

- full resume text
- raw audio
- API keys
- full transcript
- full evidence documents

Remote telemetry remains opt-in.

## Honest validation status

v1.4 can prove engineering closure when all CI / packaged / continuity gates are green.

It does **not** prove product-market fit.

Until real participants and real longitudinal usage are available, the release retains:

```text
REAL_USER_EVIDENCE_PENDING
```

and must never claim:

```text
PMF PROVEN
REAL INTERVIEW TRANSFER PROVEN
```

from synthetic or automated evidence.

## Future Personal Conversation Intelligence

The future Conversation Profile remains a canonical design boundary, not a v1.4 product surface.

The current product is still Interview-first. v1.4 does not add Meeting / Presentation / 1:1 as top-level navigation.

## Windows artifacts

The release pipeline publishes:

- `Chengzhu-Setup-x64.exe`
- `Chengzhu-Portable-x64.zip`
- `SHA256SUMS.txt`
- `LICENSE.txt`
- `THIRD_PARTY_NOTICES.md`

The installer remains unsigned unless an external code-signing certificate is provided.

## External validation still pending

- real-user recruitment
- real multi-session longitudinal usage
- real paid provider matrix
- Windows code signing
- macOS signing / notarization
- public Human Coach relay
- real long-duration human sessions

## License

MIT. Third-party components retain their own licenses; see `THIRD_PARTY_NOTICES.md`.
