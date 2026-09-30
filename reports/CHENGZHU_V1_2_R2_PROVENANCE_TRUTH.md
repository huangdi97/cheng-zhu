# Chengzhu v1.2-R2 — Provenance / Truth

## What changed

| Before (R1) | After (R2) |
|---|---|
| One `TruthStatus` (VERIFIED/SUPPORTED/INFERRED/UNKNOWN/CONTRADICTED), VERIFIED shown as "真" | Three axes: Provenance, User Assertion, Session (`services/intelligence/semantics.py`) |
| User click "verify" = VERIFIED | User confirm sets `USER_CONFIRMED`; provenance only changes when a source is linked |
| Session statements kept "for consistency" | `SESSION_STATED` + `NO_EVIDENCE` → private warning, no-expansion constraint, Review only |
| Whole-answer post check (experience) / nothing (knowledge) | Sentence-level Stream Truth Guard on every live route + full post-audit |

## Migration v2 backfill (tested: `test_migration_v2_backfills_axes_from_legacy_status`)

| Legacy | Provenance | User assertion |
|---|---|---|
| SUPPORTED (resume action line) | DIRECT_EVIDENCE | UNREVIEWED |
| INFERRED (熟悉/了解) | SUPPORTING_EVIDENCE | UNREVIEWED |
| VERIFIED + linked evidence | DIRECT_EVIDENCE | USER_CONFIRMED |
| VERIFIED without evidence | NO_EVIDENCE | USER_CONFIRMED |
| CONTRADICTED | CONFLICTING_EVIDENCE | UNREVIEWED |
| UNKNOWN | NO_EVIDENCE | UNREVIEWED |

## Assertion policy table (tested: `test_assertion_policy_table`, 9 rows)

See canonical §3.2. Key rows: user confirmation without a source only yields `ALLOW_WITH_QUALIFIER` (no new metrics / roles / scale; enforced by the stream guard); `SESSION_STATED` alone stays `REQUIRE_BOUNDARY`; denial or slip → `BLOCK_ASSERTION`.

## Session claims (tested)

- "我们后来用了 Redis Cluster" with a pack that only sources Redis → one private warning with 这是口误 / 继续但不要扩展细节 / 稍后确认.
- Slip → `SESSION_CORRECTED`; the prompt says 禁止再使用; re-saying it does not resurrect it.
- Next session inherits nothing.
- Review confirm → long-term claim `USER_CONFIRMED` + `NO_EVIDENCE` (axes stay separate); deny → `USER_DENIED`, never enters a pack.
- Resume rebuild carries verdicts by normalized text.

## Stream Truth Guard (tested)

- Knowledge answer streams immediately; "我之前在生产环境用过 Redis Cluster 做分片" is rewritten mid-stream to a boundary phrasing; "如果我来设计…" and "我没有用过 Kafka" pass untouched.
- Experience route with no source: the claim sentence becomes "我没有直接做过 {subject} 的项目…" (no substituted subject leaks).
- `ALLOW_WITH_QUALIFIER`: numbers absent from sources are rewritten.

## Found and fixed during R2

- English yes/no experience check (`did you use X`) contained a literal backspace instead of `\b`, so "Did you use gRPC in production?" was treated as sourced. Fixed; `claim_coverage` now also strips verbs inside phrases ("use Kafka" → "Kafka").

## UI

我的成竹 → 事实与来源 shows provenance and user confirmation as two labelled chips (icon + text, AA colors), with 查看来源 / 修改 / 补来源 / 用户确认 / 用户否认 / 在哪些场次使用 / 删除草稿. The word "验证/真相" is not used.
