# 成竹 Chengzhu v1.3.0

## Goal-centered Interview OS

v1.3.0 keeps the verified v1.2 Interview Core and rebuilds the product experience around one continuously improving **Job Goal**.

> The system can be complex; the user's next action cannot be.

The core loop is now:

```text
Goal → Next Focus → Prepare → Practice → Preflight → Live → Reflection → Next Focus
```

## Major product changes

### Goal-centered information architecture

The primary desktop navigation is now:

```text
首页
求职目标
我的成竹
练习
资料库
历史
设置

                         [上场]
```

`上场` is a global action, not another module tab. Prepare lives inside a Goal; Reflection is linked back to the Goal and Session.

### Goal Room + Next Focus

Each company × role target has a durable Goal Room with:

- Overview
- Prepare
- Interviews
- Offer metadata
- Next Focus
- Gap Map
- Attack Surface
- Question Graph
- Skills / Stories
- InterviewPack preview

Reflection actions can write back into the Goal so the next opening of Chengzhu continues from what actually happened.

### My Chengzhu / Fact Inbox

Personal facts remain governed by provenance and assertion policy, but the UI now exposes this as reviewable work instead of an Evidence Graph console:

- confirm / deny / revise
- inspect source
- attach supporting source
- create Story / Skill
- practice a weak point

Knowledge Base material is still not treated as personal-experience evidence by default.

### Material taxonomy + lifecycle

The library distinguishes:

- Project Materials
- Knowledge Bases
- Quick Notes
- Question Banks

Project material explicitly records whether it supports personal facts, technical reference, or both.

Material lifecycle is explicit:

```text
PROCESSING / READY / FAILED / REPLACING
```

During replacement, the previous ready version remains usable until the new one is ready.

### Quick Notes

Quick Notes are now first-class Goal/global assets:

- pinnable and reorderable
- selectable into an InterviewPack
- quickly accessible in Live
- intentionally separate from Evidence, Knowledge Base, Memory, and confirmed Claims

### Command Palette

`Ctrl+K` opens contextual commands for the current screen, including Goal, Practice, Live, Quick Notes, Overlay and fact-review actions.

### Guided First Practice

Fresh install no longer ends after configuration. The onboarding path creates a first Goal and runs a real guided Practice turn:

```text
test question
→ Practice session
→ Fast Cue
→ user's own answer
→ Content feedback
→ Delivery feedback
→ completion
```

Hardware/provider fallbacks are explicitly labelled and never presented as real runtime evidence.

### Practice 3.0

Practice now supports:

- interview round
- interviewer persona
- demeanor
- difficulty
- Goal Question Graph / weakness / question-bank sources
- adaptive follow-ups
- ownership probes
- challenge / clarification moves
- 2–3 person panel practice with controlled turn-taking
- role-specific rubrics
- progress trends

Content Coach and Delivery Coach are separate; there is no synthetic combined “hire score”.

### Live Cockpit 3.0

The default Live hierarchy is intentionally small:

1. Question
2. Fast Cue
3. Source / Warning

Deep answer is secondary.

One status line represents the current runtime state instead of exposing separate ASR / retrieval / compiler / LLM loaders.

### Pin Moment

`Ctrl+P` lets the user mark an important moment during a session:

- Important
- Bad answer
- Counterparty information
- Prepare next time
- Fact check
- Custom

Pins are prioritized in Reflection and can become Next Focus.

### Nudge / Open Thread

After a Fast Cue and only when no new question or candidate speech is active, Chengzhu may surface one restrained proactive nudge:

- Missing Dimension
- Likely Follow-up
- Fact Boundary
- Ask-back Opportunity

Nudges have cooldown, duplicate suppression and speech/new-question cancellation.

### Closing Mode

When the interviewer asks whether the candidate has questions, Chengzhu uses:

- Goal context
- company context
- this session
- interviewer disclosures
- Quick Notes
- open threads

to suggest contextual questions before generic question lists.

### Language layers

UI, interview, answer, coding, and technical-term language are independent settings.

### Overlay 3.0

Overlay behavior is now described by three independent dimensions:

- Dock: Top / Left / Right / Free
- Interaction: Passive / Interactive
- Size: Compact / Standard / Focus

The main UI and overlay use the same GuidanceViewModel.

### Reflection 3.0

Reflection is action-first:

- Next Step
- What went well
- What to improve
- Fact checks
- Story opportunities
- Pinned moments
- detailed turn timeline as a second layer

Actions include Practice this, Set as Next Focus, Confirm fact, Mark as mistake, Add source, Create Story, Add Quick Note and Don't remember.

### Product-readable progress + validation

Goal Room shows explainable within-Goal trends, never an offer probability or candidate percentile.

Diagnostics exposes six local validation questions for v1.4 hardening:

A. Is the Goal reused?
B. Does Reflection change the next Prepare action?
C. Is Fast Cue actually useful?
D. Does Practice transfer to later sessions?
E. Does Fact Inbox become maintenance burden?
F. Do Quick Notes and Pin Moment create value?

These metrics are local-first. Synthetic dogfood and automated tests are engineering evidence only.

## Verified core retained

v1.3.0 does **not** replace the v1.2-R2 core:

- frozen InterviewPack
- Context Compiler authority
- provenance / assertion / session semantics
- Stream Truth Guard
- Fast Cue before Deep
- restart-safe pack persistence
- Review / Story / Skill / Voice
- Human Coach policy boundary
- Share Privacy default OFF
- Windows installer / portable packaging
- MIT root license

## Future Personal Conversation Intelligence

The canonical design retains a future Conversation Profile on the same core:

```text
Interview Profile        ← current product
Conversation Profile     ← future second profile
```

Future-compatible concepts include Recall, Talking Point, Answer Cue, Question, Risk, Delivery and Contribution Opportunity, plus Decision / Commitment / Task / OpenQuestion semantics.

v1.3.0 does **not** expose a Meeting top-level product or claim that v2.0 is implemented.

## Validation status

v1.3/v1.4 engineering includes:

- full backend / frontend / desktop test suites
- functional Playwright
- accessibility checks
- Linux visual regression
- migration compatibility
- packaged sidecar smoke
- packaged Windows UI evidence
- 7-day synthetic continuity
- 30-session synthetic continuity
- 100-session synthetic reliability
- local product-event validation report

Real-user product validation remains:

```text
REAL_USER_EVIDENCE_PENDING
```

Automated or synthetic evidence must not be interpreted as PMF proof.

## Windows

Artifacts:

- `Chengzhu-Setup-x64.exe`
- `Chengzhu-Portable-x64.zip`
- `SHA256SUMS.txt`
- `LICENSE.txt`
- `THIRD_PARTY_NOTICES.md`

The build is currently unsigned, so Windows SmartScreen may warn on first launch. Verify the SHA256 before running.

## Known external blockers

Not claimed as completed in this release:

- Windows code signing
- macOS signing / notarization
- public Human Coach relay
- multi-hour real-user sessions
- real-user product validation
- validation against every paid model / ASR provider

## License

MIT. Third-party components retain their own licenses; see `THIRD_PARTY_NOTICES.md`.
