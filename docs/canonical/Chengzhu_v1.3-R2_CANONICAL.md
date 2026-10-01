# 成竹 Chengzhu v1.3-R2 — Canonical

**Goal-centered Interview Operating System** · Verified Interview Core × Goal-centered Experience × Personal Conversation Intelligence Future Profile

Status: **current Canonical** (2026-10-01). Supersedes the v1.2-R2 Canonical for product experience;
[v1.2-R2](Chengzhu_v1.2-R2_CANONICAL.md) remains the **FROZEN VERIFIED CORE** for every live-intelligence
semantic (provenance axes, session claims, frozen InterviewPack, Context Compiler authority, Fast Cue before
Deep, Stream Truth Guard, policy modes, share privacy contract).

Priority when sources disagree: **running code / runtime / data / CI > this document > v1.2-R2 > older docs (provenance only).**

Provenance: assembled from `成竹_Chengzhu_v1.3_to_v1.4_全量产品实现_设计闭环_总Goal_2026-10-01.md`, which carries
the complete v1.3 / v1.3.x / v1.4 product design. The separately named v1.3-R2 Canonical file was not
available in the workspace; if it is supplied later and conflicts, the newer file wins and this file is updated.

---

## 1. Principles

- **Freeze the verified core; rebuild the product experience around it.** No rewrite of Context Compiler,
  InterviewPack, provenance or session policy. No framework migration (stays Electron / React / FastAPI / SQLite).
- **The system can be complex; the user's next action cannot be.** Every screen has one primary action.
- The user is advancing a concrete job **Goal**, not operating a set of AI modules.
- Evidence before assertion · Cue before essay · Frozen pack before live (all inherited from v1.2-R2).
- No pseudo-precision: no readiness %, offer probability, percentile, "AI index", or single composite score.
- Local-first: analytics and delivery metrics stay on the device unless the user exports or opts in.
- Human Coach is a practice partner first, never a covert helper. No anti-proctoring, no detection
  evasion, no "undetectable" claims.

## 2. Product loop

```text
Person → Goal → Prepare → Practice → InterviewPack → Preflight → Live → Reflection → Next Focus ─┐
   ▲                                                                                             │
   └──────────────────────────────────── next round ◀────────────────────────────────────────────┘
```

## 3. Information architecture

Top-level navigation: **首页 · 求职目标 · 我的成竹 · 练习 · 资料库 · 历史 · 设置**.
**[上场]** is a global action in the header, not a destination: Go Live → Preflight → Live Cockpit.

Removed as top-level: 准备 (inside a Goal), 复盘 (History / Goal / Session), 上场 (global action).

Routes (hash routes, old `appMode` values are adapted, never hard-cut):

| Route | Surface |
|---|---|
| `/home` | Action Home |
| `/goals`, `/goals/:id`, `/goals/:id/prepare`, `/goals/:id/interviews`, `/goals/:id/offer` | Goal list and Goal Room |
| `/me` | Person Workspace (我的成竹) |
| `/practice` | Practice setup / session |
| `/library` | Project Materials · Knowledge Bases · Quick Notes · Question Banks |
| `/history` | Real Interviews · Practice Sessions · Reflections |
| `/settings` | Settings 3.0 |
| `/live/:sessionId` | Live Cockpit (entered only through Preflight) |

Legacy mode map: `home→/home`, `job-tracker→/goals`, `prep→/practice`, `assist→/live`, `review|knowledge→/history`,
`resume-opt→/me`.

## 4. Objects

Existing and reused: Candidate (Person), Claim, Evidence, Story, Skill, InterviewPack, Session, Review.

New (additive migration, separate `product.db`, never altering v1.2 tables):

| Object | Purpose |
|---|---|
| Goal | Long-lived job target (schema §5). Absorbs the legacy prep space; not a UI alias of it. |
| GoalMaterial | Material selected into a Goal. |
| GoalInterview | A scheduled or past interview round of a Goal; links to a Session. |
| GoalOffer | Offer status / comp / deadline / notes. Not an ATS. |
| QuickNote | First-class short note (§9). |
| QuestionBank / QuestionBankItem | Question sources with origin (§11). |
| PracticeProfile / PracticeSessionConfig | Practice setup (§10). |
| PinMoment | User-marked live/practice moment (§13). |
| NudgeEvent | Proactive guidance shown / dismissed / used (§14). |
| ClosingModeEvent | Closing-mode suggestions shown in a session (§15). |
| ReflectionAction | A user action taken on a Reflection finding (§17). |
| NextFocus | 1–3 prioritised items per Goal (§7). |
| MaterialLifecycle | PROCESSING / READY / FAILED / REPLACING per material version (§8). |
| DeliveryMetrics | Local delivery analytics per answer (§12). |
| ProgressTrend | Derived per Goal / skill / rubric dimension (§12). |
| ProductEvent | Local product analytics event (§19). |

## 5. Goal

```text
Goal { id, company, role, jd, status, stage, next_interview_at, interview_round, goal_notes,
       selected_resume_id, selected_material_ids, selected_kb_ids, selected_quick_note_ids,
       active_question_bank_ids, next_focus_id, offer_state, created_at, updated_at }
```

- `status`: ACTIVE / PAUSED / COMPLETED / ARCHIVED. `stage` (applied, screening, round N, offer, …) is metadata.
- Legacy prep spaces migrate into Goals (one Goal per prep space, link kept as `legacy_prep_space_id`);
  the prep space keeps owning skill cards and generated questions until each surface moves to Goal APIs.
- The InterviewPack freezes from a Goal: resume, READY materials, selected KB, selected Quick Notes, active banks.

## 6. Surfaces

**Action Home** answers only: what is next, what is most worth doing now, is anything blocking.
First screen: Next Interview · Next Focus · Needs Attention · Recent Session. System status (model, KB count,
resume, CPU) lives in Diagnostics / Settings. Empty: "创建第一个求职目标". Goal without session: "继续准备".

**Goal Room** — header with company · role · round · time, tabs 概览 / 准备 / 面试 / Offer, actions [开始练习] [上场].
Overview: Next Focus, What We Know, Next Interview, Recent Sessions. Prepare: Next Focus, Gap Map, Attack Surface,
Question Graph, Skills/Stories, Materials, InterviewPack Preview. Interviews: upcoming, past, practice, reflections.
Offer: status, comp, deadline, notes.

**我的成竹 (Person Workspace)** — tabs 概览 / 简历 / 项目 / 待确认 / Stories / Skills / 我的表达. No "Evidence Graph manager".

**Fact Inbox (待确认)** — product face of provenance. Card: project, claim, what the material supports, actions
[我主导] [我参与] [修改] [查看来源]; plus deny, add source, merge, delete draft, practice, add Quick Note.
Burden guard metrics: inbox_created, inbox_opened, resolved, dismissed, time_to_resolve, backlog_size, reopened.

**Stories 3.0** — categories Ownership, Conflict, Failure, Leadership, Ambiguity, Collaboration, Difficult Problem,
Influence, Trade-off, Learning. Fields S/C/A/R/Reflection + sources, skills, last_used_session. Gaps prompt a
5-minute Story Builder. Stories never invent events.

**Library** — Project Materials · Knowledge Bases · Quick Notes · Question Banks. Resume belongs to Me, JD to Goal.
A project material declares its role on upload: 项目事实与来源 / 技术参考 / 两者. A Knowledge Base is never
personal evidence by default.

## 7. Next Focus

Inputs: Goal requirements, fact boundaries, practice weaknesses, real-session reflection, Question Graph, story
gaps, skill gaps, user pins. Output: **1–3 items**, each `{type, reason, source, action, priority}`. Deterministic
ranking with explicit reasons; no composite readiness score. A user-selected item always outranks a derived one.
Practice defaults its focus to the Goal's top Next Focus item.

## 8. Material lifecycle

`PROCESSING → READY | FAILED`; replacing a READY file creates a new version in `REPLACING` while the old READY
version stays active until the new one is READY. Pack freeze selects READY versions only. FAILED shows reason,
retry, replace — never a generic spinner.

## 9. Quick Notes

`QuickNote { id, scope: GLOBAL|GOAL, goal_id?, title, content, pinned, sort_order, created_at, updated_at }`.
Create / edit / delete / reorder / pin / global or goal-scoped / select into InterviewPack / keyboard open /
read-only in Live by default / Reflection may *suggest* a note, never auto-writes.

**Truth boundary:** Quick Note ≠ Evidence ≠ Knowledge Base ≠ User-Confirmed Claim ≠ Memory. Writing
"我做过 Redis Cluster" in a note never marks a claim confirmed. In the pack, notes are a separate section labelled
as user notes; the compiler never cites them as evidence.

## 10. Practice 3.0

Setup: Goal, Round (Technical, Project Deep Dive, System Design, Hiring Manager, HR, Behavioral, Product/Case),
Persona, Demeanor (Neutral, Friendly, Skeptical, Strong Follow-up, Fast-paced), Difficulty (Warmup, Standard,
Pressure), Question Sources (Goal Question Graph, Recent Weakness, My Question Bank, Role Bank), Language,
Human Coach.

**Adaptive interviewer** — the next question depends on Goal, round, persona, demeanor, difficulty, current answer,
Question Graph, recent weakness and open threads. Moves: follow-up, challenge, constraint change, ownership probe,
quantify, clarify, contradiction probe, closing question. It is never a fixed-order playlist.

**Panel** — 2–3 personas (e.g. Tech Lead, Hiring Manager, Product Partner), each with role, priority, demeanor,
question domain, follow-up style. State: current speaker, next speaker, shared topic, persona-specific concern.
One speaker per turn; a moderator decides turn-taking.

**Human Coach** stays; default entry is Practice Setup. In formal Live it appears only under `HUMAN_ALLOWED`.
Sources stay separated: AI / PERSONAL / KB / WORLD / COACH. Coach input is never evidence.

## 11. Question banks and rubrics

`QuestionBank { name, scope, role, company?, source_type }`, item `{ text, category, difficulty, origin,
source_url?, created_at }`, origin ∈ CURATED / IMPORTED / GENERATED / PREVIOUS_SESSION / USER_ADDED.
A generated question is never labelled "XX 公司真实面经" without a source.

Rubrics for Software Engineer, AI/ML Engineer, AI Product Manager, Data/ML, General Product. Dimensions:
Technical correctness, Depth, Trade-off, Ownership, Impact, Communication, Evidence discipline, Follow-up
resilience; per-role weights are public and explainable. Never a hiring probability.

## 12. Coaching

**Content Coach** — dimensions did_answer_question, truth_boundary, technical_depth, structure, trade_off, ownership,
evidence, followup_resilience. Each finding = `{finding, evidence_from_actual_speech, action}` quoting the
candidate's real speech; an AI answer is never quoted as the user's performance.

**Delivery Coach** — time_to_conclusion, answer_duration, speech_rate, pause, repetition, filler, overlong_answer,
possible_script_reading. Output is actionable sentences, never "Delivery score = 83". Practice: local analytics
default ON. Live: default OFF, opt-in. Raw audio is never uploaded by default.

**Progress Trends** — per Goal / skill / rubric dimension over recent sessions ("结论时间 22s → 11s"). No percentile,
no offer probability, no pseudo-scientific score.

## 13. Pin Moment

`Ctrl+P` in Live and Practice. Tags IMPORTANT, BAD_ANSWER, COUNTERPARTY_INFO, PREP_NEXT, FACT_CHECK, CUSTOM.
Saved: timestamp, session_id, turn_id, question, surrounding transcript, user note. Reflection shows
"你标记的时刻" first, before any generated summary. A pin can be promoted to Next Focus only by explicit user action.

## 14. Nudge / Open Thread

Kinds MISSING_DIMENSION, LIKELY_FOLLOWUP, FACT_BOUNDARY, ASK_BACK_OPPORTUNITY. Trigger requires: no new question,
candidate not speaking, confidence ≥ threshold, proactive guidance enabled, one nudge at a time. Priority
**Fast Cue > Warning > Nudge**; a nudge never pre-empts a cue. Suppression: cooldown, duplicate, already-mentioned,
speech-active, new-question cancellation. Events: shown, dismissed, used, disabled.

## 15. Closing Mode

Question understanding recognises INTERVIEW_CLOSING and CANDIDATE_QUESTION. Inputs: Goal, company context, the
actual transcript, interviewer disclosures, Quick Notes tagged "想问", open threads. Output order: contextual
follow-up, success criteria, team / technical challenge, unresolved thread. Generic questions ("公司文化怎么样？")
only when no context exists.

## 16. Language layering

Five independent settings: UI Language, Interview Language (ASR), Answer Language (`FOLLOW_INTERVIEW` or fixed),
Coding Language, Technical Term Policy (`KEEP_ENGLISH` / `TRANSLATE` / `BILINGUAL`). One setting never drives another.

## 17. Live

**Preflight 3.0** lists Goal, Resume, Skill Cards, Stories, Knowledge, Quick Notes, Language, Model, Audio, STT,
AI Assistance, Human Assistance, Share Privacy, Screen Context — each with its origin: 我的成竹 / Goal 默认 /
本场覆盖 / 系统默认. Hashes and versions are not primary UI.

**Live Cockpit 3.0** — first layer: Question · Fast Cue · Source/Warning. Second layer: Deep Answer, Transcript,
Screen, References, Coach, Quick Notes, History. One status line only: Listening / Question detected / Preparing /
Cue ready / Answering / Reconnecting. Session end returns to Reflection.

**Overlay 3.0** — Dock (Top/Left/Right/Free) × Interaction (Passive/Interactive) × Size (Compact/Standard/Focus).
Idle compact "● Listening · {company}", expands on cue, returns to compact when idle. Main UI and overlay share one
`GuidanceViewModel`.

**Share Privacy** keeps the R2 contract: default OFF; copy says it reduces accidental exposure on supported
share/record paths and is not a security or undetectability guarantee. No stealth branding.

## 18. Reflection 3.0

First screen: Next Step, What went well, What to improve, Fact checks, Story opportunities, Pinned moments.
Turn timeline is the second layer. Every finding links back to actual speech, question and source.
Actions — Practice this, Set as Next Focus, Confirm fact, Mark as mistake, Add source, Create Story, Add Quick Note,
Don't remember — all perform real write-back (ReflectionAction → NextFocus / Claim / Story / QuickNote).

History unifies Real Interviews, Practice Sessions and Reflections, filterable by Goal, date, type, round. A
Goal shows the same session rows (no copy).

## 19. Settings, states, accessibility, visual system

Settings groups: General, Models, Speech & Audio, Language, Live & Overlay, Privacy, Knowledge, Shortcuts,
Data & Export, Diagnostics; searchable; each value shows Global Default / Goal Default / This Session Override.

Empty / processing / error states are object-specific, and every error offers a next step (Fast Cue: Preparing,
Cue unavailable — Deep continues, Provider fallback, Offline only; Coach: Disconnected, Expired, Revoked).

Accessibility: keyboard-only, visible focus, ARIA, screen reader, reduced motion, font scaling, high contrast,
light/dark, 390 px, high DPI, no hover-only actions. Shortcuts: Ctrl+K Command Palette, Ctrl+, Settings,
Ctrl+P Pin Moment (others unchanged).

**Command Palette** (Ctrl+K) ranks commands by context (Home, Goal, Live, Me) and executes them — it is not a search
demo. Cards show Primary CTA + Secondary CTA + ⋯ (contextual actions).

Visual system: Professional Workbench, not an AI dashboard — quiet, legible, no large gradients, not everything in
a card, one primary CTA per screen, status = icon + text, WCAG AA.

## 20. Onboarding — Guided First Practice

Onboarding ends with a real run: test interviewer audio → system audio → ASR partial → question → Fast Cue →
overlay → Quick Notes → optional screenshot → user answer → demo reflection → "你的成竹已经可以进行一次完整 Session。"
Each failure links its fix. Without audio hardware the run uses a prerecorded fixture and records `BLOCKED_HARDWARE`.

## 21. v1.4 Product-Market Validation Hardening

v1.4 proves the loop, it does not add modules. Six questions:
A Goal reuse · B Reflection changes next Prepare · C Fast Cue actually used · D Practice transfers to later sessions ·
E Fact Inbox burden · F Quick Notes / Pin value.

**ProductEvent** (local store, remote telemetry opt-in only): goal_created, goal_opened, goal_reopened,
next_focus_opened, next_focus_completed, practice_started, practice_completed, preflight_started, live_started,
live_completed, fast_cue_rendered, fast_cue_expanded, deep_opened, reflection_opened, reflection_action,
next_focus_changed, fact_inbox_opened, fact_resolved, fact_dismissed, quick_note_opened, quick_note_used_in_pack,
pin_created, pin_used_in_reflection, nudge_shown, nudge_dismissed, nudge_actioned.
Never recorded: resume, raw transcript, API keys, raw audio, evidence full text. Events carry IDs, counts,
durations, booleans and hashed categories.

Cue usefulness is measured by proxies (expanded, deep opened, speaking after cue, helpful/dismiss/regenerate) and a
single post-session question ("这场 Fast Cue 有帮助吗？有 / 一般 / 没有"), split into Usefulness, Accuracy,
Personal Fact Safety, Latency, Readability, Over-specificity — never one AI score.

Practice transfer links practice weakness → Next Focus → later session → same rubric observation, before/after.
Mock-to-Mock transfer is engineering evidence, never presented as real-interview transfer.

Fact Inbox hardening: when backlog grows or dismiss rate is high, generate less, merge similar claims, batch review,
inbox only high-risk items. Quick Notes / Pin low usage → fix access latency, placement, keyboard, selection
clarity, not more features.

Status words for real-user evidence: `REAL_USER_VALIDATION_PENDING`, `PRODUCT_VALIDATION_INFRA_COMPLETE`,
`REAL_USER_EVIDENCE_PENDING`. "PMF proven" is never written from automated tests.

## 22. Future Profile — Personal Conversation Intelligence

Not productized in v1.x: no Meeting UI, no Meeting top-level nav. Interview is the first proven profile;
Conversation is the future second profile. Abstraction boundaries to keep open:

| Interview term | Future general term |
|---|---|
| Candidate | Person |
| Job Goal | Goal |
| Interview State | Conversation State |
| Interviewer State | Counterparty State |
| Answer Planner | Expression Planner |
| InterviewPack | Session Pack family |

Contracts retained at the type/interface level: `ConversationProfile`, `ConversationGoal`, `ConversationState`,
`CounterpartyState`, `ExpressionIntent`, `GuidanceKind` = RECALL / TALKING_POINT / ANSWER_CUE / QUESTION / RISK /
DELIVERY / CONTRIBUTION_OPPORTUNITY. Future conversation data types: Decision, Commitment, Task, Deadline, Risk,
Assumption, OpenQuestion, Proposal, Objection, Metric, Status with state PROPOSED / AGREED / COMMITTED / DONE /
SUPERSEDED / UNKNOWN. No DB tables are added for them until a shared need exists. New v1.3 product layers
(Goal, Quick Notes, Pins, Next Focus, events) avoid hard-coding `job` in shared interfaces.

## 23. Forbidden

Rewriting the v1.2-R2 core; Tauri; Neo4j / PostgreSQL / pgvector; redoing Context Compiler or InterviewPack;
removing provenance / truth / session policy for looks; UI work that slows Fast Cue; deleting tests or editing
snapshots to hide regressions; presenting simulated benchmarks as real-user proof; Meeting in v1.3 nav;
Human Coach as covert help; anti-proctoring / detection evasion; "100% undetectable".
