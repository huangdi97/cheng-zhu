# Chengzhu v1.3-R2 → v1.4 Final Design Convergence Matrix

> Purpose: map the canonical v1.3-R2 product-experience acceptance items and the v1.4 engineering Definition of Done to the current implementation and verification surfaces.
> This is an implementation truth table, not a PMF claim.

Evidence labels: IMPLEMENTED / INTEGRATED / CI-PROVEN / PACKAGED-PROVEN / REAL-USER-PENDING.

## 0. Baseline

- v1.2-R2 Verified Interview Core: frozen and authoritative.
- v1.3 Goal-centered Interview OS: implemented and publicly released.
- v1.4 Product Validation Hardening: implemented and publicly released.
- v1.4.1 Live → Reflection closure: merged, full Windows release/download-back passed, and v1.4.1 is publicly released.
- Personal Conversation Intelligence: canonical future profile, deliberately not productized in v1.4.

Top-level IA stays: 首页 / 求职目标 / 我的成竹 / 练习 / 资料库 / 历史 / 设置, with 上场 as a global action.

## 1. v1.3-R2 Appendix E acceptance matrix

| Capability | Canonical product condition | Implementation / evidence | Status |
| --- | --- | --- | --- |
| Goal Room | Prep / Sessions / Next Focus are one Goal flow | `frontend/src/components/os/GoalRoom.tsx`, `GoalPrepare.tsx`, `SessionList.tsx`, `backend/services/product/goals.py`, `next_focus.py`; `frontend/e2e/v13-product-loop.spec.mjs`, `job-workspace.spec.mjs` | PRODUCT_COMPLETE / CI-PROVEN / PACKAGED-PROVEN |
| Quick Notes | selectable into Pack, available in Live, manual Reflection write-back | `backend/services/product/quick_notes.py`, `QuickNotesDrawer.tsx`, `LiveCompanions.tsx`, `ReflectionPage.tsx` | PRODUCT_COMPLETE / CI-PROVEN |
| Command Palette | Ctrl+K shows executable context actions | `CommandPalette.tsx`, `actions.ts`, `App.tsx`, `docs/screenshots/command-palette.png` | PRODUCT_COMPLETE / CI-PROVEN / PACKAGED-PROVEN |
| Guided First Practice | first user can run audio → cue → overlay → review | `OnboardingWizard.tsx`, `GuidedFirstPractice.tsx`, Practice backend, Electron overlay. Flow includes first Goal, test audio/fallback, Fast Cue, own answer, Content/Delivery feedback, optional Compact Overlay/Quick Note/screenshot, demo Reflection | PRODUCT_COMPLETE / CI-PROVEN |
| Practice Persona | next question reacts to persona / answer / graph | `backend/services/product/practice.py`, `rubrics.py`, `PracticePage.tsx`; panel turn-taking included | PRODUCT_COMPLETE / CI-PROVEN |
| Content / Delivery Coach | no single score hides separate problems | Practice backend + UI; distinct content findings and delivery metrics | PRODUCT_COMPLETE / CI-PROVEN |
| Pin Moment | Review first screen can prioritize user Pins | `pins.py`, `PinDialog.tsx`, `ReflectionPage.tsx`; Pin → Reflection → explicit Next Focus path exercised | PRODUCT_COMPLETE / CI-PROVEN |
| Nudge | does not steal Fast Cue or interrupt user speech | `nudges.py`, `LiveCompanions.tsx`; cooldown, duplicate/speech/new-question suppression | PRODUCT_COMPLETE / CI-PROVEN / REAL-USER-USEFULNESS-PENDING |
| Closing Mode | uses actual session context for ask-back questions | `closing.py`, `LiveCompanions.tsx`; Goal + session + disclosures + Quick Notes + open threads | PRODUCT_COMPLETE / CI-PROVEN |
| Material Lifecycle | Processing / Ready / Failed / Replacing; old READY remains usable while replacement processes | `backend/services/product/materials.py`, `LibraryPage.tsx`, product API | PRODUCT_COMPLETE / CI-PROVEN |
| Language Layering | UI / ASR / Answer / Code / Term policy independent | `settings_layers.py`, `SettingsPage.tsx`, `live.py`; v1.4 removes raw enum values from Preflight | PRODUCT_COMPLETE / CI-PROVEN |
| Compact Overlay 3.0 | Dock / Interaction / Size; idle compact, cue expands, can return compact | `InterviewOverlay.tsx`, `OverlayPrefs.tsx`, `overlayLayoutStore.ts`, desktop overlay code | PRODUCT_COMPLETE / CI-PROVEN; native interactive multi-monitor proof remains environment-limited |
| Reflection → Next Focus | next Goal Overview really changes | `reflection.py`, `next_focus.py`, `ReflectionPage.tsx`, `GoalRoom.tsx`; v1.4.1 closes formal Live stop → live/end → Reflection | PRODUCT_COMPLETE / CI-PROVEN |

## 2. Other v1.3 product surfaces now integrated

Action Home; Goal list; Goal Room Overview/Prepare/Interviews/Offer; Person Workspace; Fact Inbox; Stories 3.0; Skills; Expression Profile; material taxonomy; Question Banks; role-specific rubrics; Panel/Multi-persona Practice; Goal progress trends; Preflight 3.0; Cue-first Live Cockpit; Human Coach Practice-first; Share Privacy default OFF; History; Settings 3.0; Data Export/Delete; Light/Dark; 390px; keyboard/accessibility.

Public runtime screenshots live in `docs/screenshots/` and are promoted only from current Goal-centered runtime evidence. Legacy module-first screenshot generators are not allowed to overwrite public media.

## 3. Frozen Verified Core non-regression

Still authoritative: Candidate/Person factual boundary; Provenance; User Assertion; Session Statement; frozen InterviewPack; Context Compiler authority; Question Understanding/Routing; Follow-up resolution; Fast Cue before Deep; Stream Truth Guard; Session Claim boundary; Human Assistance Policy; Share Privacy; Windows backend sidecar.

## 4. v1.4-R1 Definition of Done

| Gate | Implementation / evidence | Status |
| --- | --- | --- |
| A–F validation locally inspectable | `events.py`, `validation.py`, `SettingsPage.tsx` | ENGINEERING-PROVEN; real-user pending where applicable |
| Reflection → Next Focus authoritative | same path as v1.3 row above | PASS |
| friction audit | `reports/CHENGZHU_V1_4_FRICTION_AUDIT.md`; v1.4.1 closes discovered Live→Reflection defect | ENGINEERING-COMPLETE |
| 7-day / 30-session / 100-session continuity | `dogfood.py`, `scripts/v14_validation_evidence.py` | CI-PROVEN as SYNTHETIC_DOGFOOD |
| 3-hour-equivalent soak | controlled engineering soak; explicitly excludes real human fatigue/device/network/provider behavior | ENGINEERING-PROVEN / REAL-LONG-SESSION-PENDING |
| migration + export/delete integrity | `product_migrations.py`, `data_export.py`, Reflection/Settings product UI | CI-PROVEN |
| no Verified Core regression | Cue before Deep, frozen Pack, compiler/truth boundaries remain gated | CI-PROVEN |
| full CI | backend / frontend / desktop / Playwright / visual / e2e / packaged smoke / gate | REQUIRED GREEN |
| Windows package | Setup EXE + Portable ZIP | PACKAGED-PROVEN |
| clean-install replay | release workflow on fresh Windows hosted runner | PACKAGED-PROVEN |
| version consistency + SHA256 + GitHub Release | frontend/desktop/locks/backend APP_VERSION/tag/release assets | RELEASE-PROVEN |

## 5. Product-validation truth boundary

Strongest valid claims:

- V1_4_ENGINEERING_COMPLETE
- PRODUCT_VALIDATION_INFRA_COMPLETE
- RELEASE_READY_WITH_EXTERNAL_BLOCKERS
- REAL_USER_EVIDENCE_PENDING

Not allowed without real participants:

- PMF_PROVEN
- REAL_INTERVIEW_TRANSFER_PROVEN
- V1_4_REAL_VALIDATION_COMPLETE

## 6. Personal Conversation Intelligence boundary

Full future design remains canonical in `docs/canonical/v1.3-R2-master/05_Personal_Conversation_Intelligence.md` and Appendix G.

Retained future concepts: Person Representation, Conversation Goal/State, Counterparty State, Expression Planner, Recall, Talking Point, Answer Cue, Question, Risk/Contradiction, Delivery, Contribution Opportunity, Decision/Commitment/Task/OpenQuestion, Before/During/After, Desktop Sidecar, future Connector/MCP.

Current v1.4 intentionally does not add Meeting / Presentation / 1:1 top-level product UI. This is scope control, not a missing v1.3/v1.4 requirement.

## 7. Final convergence verdict

- v1.2-R2 Verified Interview Core: FROZEN / AUTHORITATIVE.
- v1.3-R2 Goal-centered Interview OS: IMPLEMENTED / RELEASED.
- v1.4-R1 Validation Hardening: IMPLEMENTED / RELEASED.
- v1.4.1 Live→Reflection closure: RELEASED / DOWNLOAD-BACK-PROVEN.
- v1.4.2 Final Design Convergence: current release candidate; packages the post-v1.4.1 product-craft/public-surface closure already present on main.
- Personal Conversation Intelligence: CANONICAL / FUTURE PROFILE.

Remaining non-design evidence: real-user longitudinal Goal reuse; perceived Fact Inbox burden; real-interview transfer; real paid-provider quality/latency/cost; interactive multi-monitor overlay proof; code signing; macOS signing/notarization; public Human Coach relay; real multi-hour sessions.

Future work rule: do not add permanent product surfaces merely to increase feature count. New Interview features must belong clearly to Person/Goal/Pack/Session/Reflection, improve a real next action, avoid duplicate entry points, preserve Cue-first Live hierarchy and provenance/truth boundaries, and be justified by evidence.
