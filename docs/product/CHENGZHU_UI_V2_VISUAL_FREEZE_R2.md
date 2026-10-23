# Chengzhu UI v2 Visual Freeze R2

Date: 2026-10-22
Status: final acceptance contract (supersedes R1's open items; R1 principles unchanged)

R1 (`CHENGZHU_UI_V2_VISUAL_FREEZE_R1.md`) fixed the visual direction: two worlds
(Studio / Live Cockpit), Goal over modules, evidence over scores, quiet
intelligence. R2 does not re-open that direction. It records what the direction
became once it was actually run, measured, and frozen:

- the first-run surface was cut from eleven setup steps to three questions;
- Preflight is the only place that decides "can I start?", and it is
  blocker-first in both layout and copy;
- every Studio surface now passes a measurable acceptance harness at five
  viewports;
- the screenshot contract is pixel-exact (no diff budget) and covers the setup
  surfaces that were still unfrozen when #157 shipped.

## 1. Final visual principles

Carried forward from R1 without change:

- content hierarchy before container hierarchy; sections and hairlines before cards;
- one primary attention object per viewport;
- 90% neutral, 10% brand/semantic accent;
- shadows only on overlays, dialogs, popovers and the floating Live surface;
- pills only for status/tags;
- no bamboo/watercolor decoration, no gradient hero, no module dashboard;
- no readiness percentage, no offer probability, no stealth narrative.

Refinements made in R2 because the measurements exposed them:

| Area | R1 said | R2 froze | Why |
| --- | --- | --- | --- |
| Primary buttons | "pills for status, not every button" | `.btn-primary` / `.btn-danger` radius `8px` | the shared class was `9999px`; every Studio CTA was a pill |
| Elevation | "shadow only for floating layers" | `.btn-primary`, `.sig-tile`, `.header-gradient` carry no shadow | elevation was leaking into ordinary Studio chrome |
| Dark-mode foreground | implicit | `--c-on-accent` token per theme | white-on-light-accent failed 4.5:1 in dark themes |
| Typography | "5–6 stable levels" | measured: ≤ 6 distinct text sizes per Studio surface (shell excluded) | several surfaces carried 7–8 sizes, mostly 10/11px duplicates |
| Corner radius | "8–12px, dialogs may be larger" | Studio panels `≤ 12px`; dialogs and Live chrome may use `16px` | `rounded-2xl` had spread into Studio panels |
| Motion | not specified | `prefers-reduced-motion: reduce` stops all animation and transition | motion was decoration-only and ignored the OS setting |
| Palette warmth | "warm neutral canvas", "green only as brand/state" | neutral tokens keep `hue 45–125°` whenever chroma `> 0.006`; accent stays `hue 125–160°` (bamboo) | the neutrals themselves were teal-tinted (text `H166`, borders `H161`, accent `H169`), so the product read green-cyan even with 1% accent coverage |

R2 palette (workbench light; the named third-party themes are untouched):

| role | token | value | hue / chroma |
| --- | --- | --- | --- |
| canvas | `--c-bg-primary` | `#F8F6F0` | 91° / 0.008 |
| raised | `--c-bg-secondary` | `#FFFFFF` | — |
| sunken | `--c-bg-tertiary` | `#F2EEE5` | 87° / 0.013 |
| hover | `--c-bg-hover` | `#E7E0D3` | 83° / 0.019 |
| ink | `--c-text-primary` | `#221E16` | 84° / 0.016 |
| secondary ink | `--c-text-secondary` | `#5F594C` | 86° / 0.022 |
| muted ink | `--c-text-muted` | `#706A5C` | 88° / 0.023 |
| hairline | `--c-outline-variant` | `#DED7CA` | 83° / 0.019 |
| brand | `--c-accent-blue` | `#3F6A42` | 146° / 0.080 |

Contrast after the change: body 15.4:1, secondary 6.4:1, muted 5.0:1, brand text
on its container 7.9:1, white on brand 6.3:1.

## 2. First-run contract

First run answers three questions and nothing else.

1. **理解** — what Chengzhu is, why everything hangs off one Goal, where data lives.
2. **创建目标** — company, role, JD; round and time sit behind "下一轮信息（可选）".
3. **就绪** — the prepare → practice → on-stage → review loop, one honest machine
   status line, and the way in.

Rules this contract enforces:

- no model/STT/microphone/loopback tests, no data-directory dump, no privacy
  radio group, no resume upload, no guided practice gate inside first run;
- environment work moved to Settings and to blocker-first Preflight, where it is
  checked at the moment it matters;
- machine status is reported with icon + text ("就绪" / "未就绪") and never gates
  entry;
- an optional three-minute guided practice stays available behind a secondary
  text action, not as a required step;
- finishing the flow lands on the Goal that was just created.

## 3. Create Goal contract

Create Goal answers "tell Chengzhu what my next interview is", not "create a
database object".

- first layer: 公司, 岗位, JD, one primary button;
- 轮次 and 时间 behind progressive disclosure;
- no advanced AI parameters, no material toggles, no practice configuration;
- validation is inline (`请填写目标岗位；公司可以暂时留空` → toast), never a silent dead button;
- labels are real `<label>` elements, so every field has an accessible name;
- at 1280×720 the dialog fits the viewport and the primary button is in the first view.

## 4. Preflight contract

Preflight answers one question: *can I start this session, and if not, what is
blocking me?*

**Ready**

- the first view states `可以开始` (semibold, status colour) next to the Goal title;
- `开始上场` is enabled and inside the first viewport at 1280×720;
- the page then shows this session's inputs, this machine's device status and the
  session-only overrides.

**Blocked**

- the first block after the summary is the blocker list: what is wrong, why it
  matters, how to fix it;
- there is no ready-count, no percentage, no per-device status duplication under
  the active blocker;
- `开始上场` is disabled and reads `先处理阻塞项`;
- the primary action stays visible at 1280×720.

**Session-only overrides**

- overrides are labelled `本场覆盖`, default to `未修改本场默认值`, and never write back
  to the Goal or global settings.

## 5. Live state contract

The Live surface is a graphite instrument, not a Studio dark theme.

### Compact

- the status line stays one row (`≤ 56px` measured at 1440×900) and carries
  listening state plus Goal context;
- no guidance is shown when there is nothing worth saying.

### Cue

- first layer only: current question, one-line direction, at most **three**
  speakable bullets, provenance per bullet, feedback affordance, expand;
- the cap is enforced twice: in the view model (`CUE_CAP = 3`) and at render time;
- measured height budget at 1440×900: `≤ 340px`, so the user can look and keep
  talking within three seconds.

### Deep

- opt-in only (`展开完整回答`), never open by default;
- carries the streamed answer; the cue stays above it.

### Artifact

- artifact means a second work surface for the *task* (coding, system design,
  product case, written problem, calculation, structured whiteboard);
- it is not a code editor by definition, and no surface may assume code;
- status of this round: **NOT_APPLICABLE**. No artifact surface exists yet —
  `git grep -i artifact -- frontend/src` returns nothing at this commit — so there
  is no code-editor-bound UI to generalise. The contract above is the gate any
  future artifact surface must pass before it ships: a non-code artifact must
  render without code chrome.

### Transcript

- secondary by default and collapsed; opening it is an explicit user action.

## 6. Measured acceptance

The executable form of this document is `frontend/scripts/ui-v2-hva.mjs`
(`npm run hva`). It renders the built product against deterministic API + socket
fixtures, drives the real states, and fails the run when a rule breaks.

Rules it asserts on every reviewed surface, at 390×844 / 768×1024 / 1280×720 /
1440×900 / 1920×1080:

-no document-level horizontal scroll;
-primary CTA inside the first viewport at 1280×720;
-dialogs fully inside the viewport at 1280×720;
-`≤ 6` distinct text sizes per Studio surface (app shell excluded);
-radii above 12px only on dialogs, overlays or status pills;
-shadows only on dialogs, popovers, overlays (selection rings are not elevation);
-no decorative card nesting (interactive option cards inside a section are allowed);
-visible text keeps `≥ 4.5:1` contrast (`≥ 3:1` for large text);
-no blank or error-only render (ink coverage), brand-green pixel budget `< 6%`;
-heading order, accessible names on every interactive control, reduced-motion respected;
-`axe` reports no serious or critical `wcag2a`/`wcag2aa` violation;
-every keyboard stop shows a focus indicator, and a modal moves focus inside, keeps
  Tab inside and closes on Escape;
-neutral warmth: every neutral token with chroma above `0.006` must sit in the warm
band (`hue 45–125°`), and the accent must stay bamboo (`hue 125–160°`) — this is the
check that a green-pixel budget cannot make;
-product invariants: primary nav is 首页/求职目标/练习/历史/我的成竹, Goal Prepare keeps
its next-interview-first order, cue ≤ 3 bullets, transcript collapsed, no
offer-probability / readiness-percentage / stealth copy anywhere;
-truth boundaries stay individually readable: My Chengzhu must still render
`有直接证据` / `你已确认` / `暂无证据` separately, and Library must still separate
`项目资料` / `知识库` / `速记` / `题库`, so no surface can collapse them into one
generic "verified" label.

Latest run: 18 states × 5 viewports = 90 renders, 0 measured failures.
Evidence, the measured JSON and a contact sheet are written under
`.runtime/ui-v2-hva/` (never committed).


This is a required CI job (`hva`, wired into `ci-gate`), not a local script: the
contact sheet and the JSON are uploaded as artifacts for human sign-off. Adding a
surface to `STATES` therefore adds it to the gate in the same commit.
## 7. Strict baseline set

`frontend/e2e/visual.spec.mjs` freezes these surfaces with `toHaveScreenshot`
and no diff budget:

Action Home · Goals · Goal Room overview · Goal Room prepare · Practice setup ·
Reflection · History · My Chengzhu (overview, resume, facts, stories, projects,
skills, voice) · Library (materials, knowledge, banks, notes) · Settings general ·
Conversation home · Conversation spaces · Live cockpit · **First run understand** ·
**First run create goal** · **Create Goal dialog** · **Preflight ready** ·
**Preflight blocked**.

`playwright.config.mjs` sets `maxDiffPixelRatio: 0` **and** `threshold: 0.05`.
Both matter: with the ratio at 0 but the colour threshold left at Playwright's
default 0.2, a whole-palette re-tint (a few RGB units on every text node and
hairline) counted as "no change", so the CI baseline generator rewrote nothing and
the committed baselines silently stayed on the old palette. 0.05 still absorbs
sub-pixel antialiasing but registers a real colour shift.

## 8. Known intentional exceptions

Each exception is a decision, not an oversight, and the harness knows about it.

1. **Live cockpit nests its turn card and speaker chip.** The cockpit is a single
   floating instrument; inside it, the current turn, the speaker chip and the
   draft block are one object with internal boundaries, not decorative cards.
2. **Dialogs may use a 16px radius.** Onboarding, Create Goal, Preflight and the
   command palette are overlays; the 8–12px rule is a Studio rule.
3. **Selection rings count as state, not elevation.** Tailwind `ring-1` renders as
   a zero-blur, zero-offset box-shadow; the harness classifies those separately.
4. **Query notes keep 10px micro labels.** Goal Prepare uses 10px for tertiary
   labels inside a dense dossier; it stays inside the six-tier budget.
5. **The Live control bar keeps its gradient and shadow.** It is the floating edge
   of an overlay, not a Studio section.

## 9. Accessibility notes

- every theme defines `--c-on-accent`, so accent buttons keep readable contrast in
  light, dark, high-contrast, nord, editorial and solarized themes;
- status is never colour-only: device state, blockers and evidence boundaries
  always pair an icon with text;
- dialogs trap focus, restore it on close, and close on `Escape`;
- `prefers-reduced-motion: reduce` disables animation and transitions globally;
- labels are associated (`<label>`/`aria-label`), so form controls in Create Goal,
  Practice setup and Preflight have accessible names.

## 10. Final HVA status

Measured acceptance: **PASS** (harness, 18 surfaces × 5 viewports).
Human acceptance: **pending owner sign-off** on the contact sheet produced by
`npm run hva:sheet` (`.runtime/ui-v2-hva/index.html`).

The tooling that produced this document has no eyes. It can prove the rules above
hold, and it can hand over a curated screenshot set; it cannot claim that a screen
"looks right". That final judgement stays with the product owner, and this
document is the list of what to look at.
