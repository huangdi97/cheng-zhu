# 成竹 Chengzhu v1.2-R2 — Canonical

Status: **FROZEN VERIFIED CORE** (2026-10-01). Product experience is now defined by the [v1.3-R2 Canonical](Chengzhu_v1.3-R2_CANONICAL.md); every live-intelligence semantic below stays authoritative and must not regress.
Historical status: source of truth for product semantics (supersedes v1.2-R1 / v1.1-R1 / v1.0-R1 where they conflict).
Priority when sources disagree: running code → repository → DB → release artifact → test/CI evidence → this document → older design docs (provenance only).

## 1. Principles

- Interview-first · Personal-Context-native · Resume-first, not Resume-bound
- Evidence before assertion · Cue before essay · Frozen pack before live
- One context authority
- **Provenance is not truth** · **Session-stated is not verified** · **Human advice is not evidence** · **Share privacy is not undetectability**

## 2. Corrections to R1

| R1 concept | R2 rule | Where it lives |
|---|---|---|
| Single `TruthStatus`, `VERIFIED` shown as "true" | Three independent axes: Provenance / User Assertion / Session. UI never says "verified = true". | `services/intelligence/semantics.py`, migration v2 |
| "User said it, keep later answers consistent" | `SESSION_STATED` without evidence only drives a private warning, a no-expansion prompt constraint and a Review item. Never promoted except in Review. | `services/intelligence/session_claims.py` |
| Interview Pack = list of version ids | Immutable snapshot of actual content (candidate, claims, evidence, skill cards, stories, job, KB selection, voice, policies, model profile, hashes). Updates create a revision. | `services/intelligence/interview_pack.py`, table `interview_pack` |
| Live reads latest job | Live resolves only the session's frozen pack; an unfrozen session gets the configured resume and **no job**. `latest_job_id()` is Prepare-side only. | `answer_worker._resolve_live_pack`, test `test_job_a_pack_is_not_contaminated_by_later_job_b` |
| TTFUG = first model token | TTFUG_user = G0 − E (speech end). First model token is TTFA. | `services/intelligence/latency_clock.py` |
| Human coach tied to AI policy | `HUMAN_FORBIDDEN / HUMAN_PRACTICE_ONLY (default) / HUMAN_ALLOWED`, independent of AI policy. | `services/intelligence/policy.py`, `services/coach.py` |
| Share privacy on by default | `OFF` (default) / `PRIVATE_OVERLAY`. Copy says it is not a security or undetectability guarantee. | `desktop/sharePrivacy.js`, config `share_privacy_mode` |
| 准备 as a top-level nav | Nav: 首页 / 我的成竹 / 求职 / 演练 / 上场 / 复盘 / 设置. Prepare is part of each Job Goal. | `App.tsx`, `components/hubs/Hubs.tsx` |
| License CC BY-NC 4.0 | MIT for the current tree; third-party components keep their licenses. | `LICENSE`, `THIRD_PARTY_NOTICES.md` |
| Compiler added on top of legacy prompt | Compiler is the only context authority; the system prompt stops injecting resume / KB / memo / JD when it succeeds. `compiler_fallback=true` only on explicit failure. | `context_compiler.compile_live_context`, `prompts.build_system_prompt(context_authoritative=True)` |
| Cue = "AI" | Source taxonomy `PERSONAL_EVIDENCE / KB_KNOWLEDGE / WORLD_KNOWLEDGE / HUMAN_COACH`. | `services/intelligence/fast_cue.py` |
| Status colors | `#256A4B / #317566 / #86551F / #636A66 / #AD4545` on light themes, per-theme AA variants on dark; icon + text always. | `index.css`, `lib/statusContrast.test.ts` |

## 3. Semantics

### 3.1 Axes

- **ProvenanceStatus**: `DIRECT_EVIDENCE`, `SUPPORTING_EVIDENCE`, `NO_EVIDENCE`, `CONFLICTING_EVIDENCE` — whether held sources cover the statement.
- **UserAssertionStatus**: `UNREVIEWED`, `USER_CONFIRMED`, `USER_DENIED` — the user's own verdict.
- **SessionStatus**: `NOT_STATED`, `SESSION_STATED`, `SESSION_CORRECTED` — said aloud in this session.

Resume rebuilds carry user verdicts forward by normalized text; Review-confirmed facts survive a rebuild.

### 3.2 Assertion policy (`decide_assertion_policy`)

1. `AI_FORBIDDEN`, `USER_DENIED` or `SESSION_CORRECTED` → `BLOCK_ASSERTION`
2. Truth requirement not personal (knowledge / hypothetical / screen) → `KNOWLEDGE_ONLY`
3. `CONFLICTING_EVIDENCE` → `REQUIRE_BOUNDARY`
4. `DIRECT_EVIDENCE` → `ALLOW_PERSONAL_ASSERTION`
5. `SUPPORTING_EVIDENCE` or (`NO_EVIDENCE` + `USER_CONFIRMED`) → `ALLOW_WITH_QUALIFIER` (no new metrics / roles / scale)
6. `NO_EVIDENCE` + `PERSONAL_FACT_RELEVANT` → `KNOWLEDGE_ONLY`; otherwise `REQUIRE_BOUNDARY`

### 3.3 Question understanding and routing

`derive_axes` → (DialogueAct, ContentType, TruthRequirement). `route_answer(...)` is the **only** question → ResponseMode table (`answer_planner` has no private table). Modes: EXPERIENCE, EXPERIENCE_KNOWLEDGE, EXPERIENCE_BOUNDARY_KNOWLEDGE, KNOWLEDGE, HYPOTHETICAL, OPEN_DESIGN, CODING, SYSTEM_DESIGN, OOD, BEHAVIORAL, PRODUCT_CASE, NEGOTIATION. Eval reports exact and semantic-compatible accuracy separately.

## 4. Live path

```
partial ASR ─► Q0 + predictive KB prefetch (read-only)
VAD flush ─► E estimate ─► STT ─► end-of-turn cue flush ─► question group confirmed (Q1)
   ─► early L0 Fast Cue (G0) ─► late-constraint grace ─► answer worker
   ─► frozen InterviewPack ─► compile_live_context (dedupe, fragment identity)
   ─► guidance_fast (re-emitted if resolved) ─► deep stream through StreamTruthGuard (A0)
   ─► post-audit ─► answer_done + latency + turn_trace (D0)
candidate speech ─► session_claims ─► private warning (slip / continue-no-expand / later)
```

- Stream Truth Guard buffers only a first-person span until its sentence ends; knowledge prose streams unchanged.
- Fast Cue L0 is deterministic; L1 (optional fast model) is claim-checked and falls back to L0.

## 5. Policies (frozen per session)

- AI: `AI_FORBIDDEN` (server-side live block) / `AI_LIMITED` (no auto-answer) / `AI_ALLOWED` / `AI_EXPECTED`
- Human: `HUMAN_FORBIDDEN` / `HUMAN_PRACTICE_ONLY` (default) / `HUMAN_ALLOWED`
- Share privacy: `OFF` (default) / `PRIVATE_OVERLAY`
- Live speech-adoption analytics: off by default, local only, never "cheating detection" or "pass probability"

## 6. Memory

Automatic: `knowledge_weakness`, `repeated_topic`, `communication_profile`. Never automatic: new personal experience, metric, ownership, project role, coach suggestion, interviewer inference. Controlled memory is frozen into the next pack.

## 7. Desktop

- Windows installer `Chengzhu-Setup-x64.exe` and `Chengzhu-Portable-x64.zip`; backend is a PyInstaller sidecar — no system Python/Node.
- All user data under `%APPDATA%\Chengzhu\{data,config,logs,cache,exports}` via `CHENGZHU_HOME`; the install dir is never written.
- Sidecar binds 127.0.0.1; LAN coaching uses a separate listener that serves only `/coach` routes.

## 8. Status vocabulary

`IMPLEMENTED · INTEGRATED · AUTHORITATIVE · PRODUCT-COMPLETE · CI-PROVEN · REAL-PROVEN · BLOCKED-EXTERNAL · FUTURE` — see `reports/CHENGZHU_V1_2_R2_FINAL_REALITY_REPORT.md` for the per-capability status. A single "PASS" never stands in for these.
