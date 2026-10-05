# Chengzhu v1.3 Runtime UI Audit

> Audit basis: GitHub Actions Release run `37281817505`, artifact `chengzhu-v1.3-runtime-ui-evidence`.
>
> Captured at: 2026-10-05T08:24:48Z.
>
> This report distinguishes what the hosted Windows runner really proved from what it could not prove. It does not promote headless packaged-frontend evidence into Electron BrowserWindow evidence.

## 1. Evidence level

The artifact manifest records:

```text
evidence_type =
PACKAGED_FRONTEND_DIST_VIA_PACKAGED_SIDECAR_HEADLESS_CHROMIUM

browserwindow_evidence =
BLOCKED_HOSTED_WINDOWS_RUNNER_NO_INTERACTIVE_DESKTOP
```

The capture used:

- the packaged backend executable under `win-unpacked/resources/backend/chengzhu-backend.exe`;
- the packaged frontend under `win-unpacked/resources/frontend-dist`;
- an isolated product data directory;
- a local fake OpenAI-compatible provider for deterministic Cue/Deep evidence.

Therefore the evidence proves the **packaged product resources + packaged sidecar + real product APIs + real v1.3 frontend routes**. It does **not** prove native Electron window chrome, OS-level overlay placement, or Windows display-compositor behavior on the hosted runner.

Those BrowserWindow-only claims remain separately covered by Electron unit/integration code and require an interactive Windows desktop for true visual evidence.

## 2. Captured product surface

The artifact contains 36 PNG files covering the following product states:

### Onboarding / first value

- first-run onboarding;
- first Goal creation;
- Guided First Practice question;
- real Fast Cue through packaged sidecar + deterministic provider;
- explicit Overlay-unavailable state outside Electron BrowserWindow;
- Quick Note during first practice;
- Guided Reflection;
- onboarding completion.

### Goal-centered Studio

- Action Home;
- Goal list;
- Goal Room overview;
- Goal Prepare;
- Goal Interviews;
- Goal Offer;
- Person / Resume;
- Fact Inbox;
- Stories;
- Material lifecycle;
- Quick Notes;
- Question Banks;
- Practice 3.0;
- Panel Practice;
- Reflection;
- History;
- Command Palette.

### Live

- Preflight 3.0;
- Live idle;
- Fast Cue before Deep;
- Deep as a second layer;
- Pin Moment;
- Live Quick Notes;
- Closing Mode.

### Settings / product hardening

- Live / Overlay settings;
- v1.4 six-question validation UI;
- dark theme;
- 390px Goal Prepare.

## 3. Visual review

All captured states were visually inspected as a set rather than accepting artifact existence as UI approval.

### What is now working

1. **The product reads as one workbench, not a pile of unrelated modules.**
   The seven-item navigation rail, global Go Live action, Goal Room internal tabs and shared surface language are consistent.

2. **Action Home has the correct hierarchy.**
   The next interview / current Goal and the next useful action dominate. System implementation detail is not the hero content.

3. **Goal Room is the strongest Studio surface.**
   Overview / Prepare / Interviews / Offer reads as one durable company × role workspace. Prepare carries the densest information but stays scan-friendly.

4. **Practice 3.0 is visibly a setup workflow, not a generic form.**
   Goal, round, persona/panel, demeanor, difficulty, question sources, language and local delivery analysis are grouped coherently.

5. **Live follows the intended Cue-first hierarchy.**
   Fast Cue is visible before Deep and keeps source/risk information near the glanceable answer layer. Deep remains opt-in.

6. **Reflection is action-first.**
   It reads as “what changes next?” rather than a long AI report.

7. **v1.4 validation is product-readable.**
   The six questions are shown as six separate product signals. There is no synthetic aggregate hire score or PMF badge.

8. **390px is a real supported layout.**
   Goal Prepare remains usable without horizontal overflow; the narrow layout is not merely a shrunken desktop canvas.

9. **Light and dark themes share the same product identity.**
   Bamboo / ink tones remain restrained and do not drift into a cyberpunk or “cheating tool” aesthetic.

### Remaining visual limitations

These are not release-blocking defects:

- Some intentionally empty surfaces (Offer, early History, empty Stories/Library states) are visually sparse. This is preferable to fake data or decorative dashboards; the next action must remain explicit.
- Desktop views are deliberately quieter and more spacious than mobile. Further global density changes would risk reducing scanability and should be driven by real-user evidence, not aesthetic pressure.
- The hosted-runner artifact cannot prove native overlay placement, multi-monitor geometry or OS window interaction.

## 4. Design acceptance

| Area | Runtime result |
|---|---|
| Goal-centered IA | PASS |
| Action Home | PASS |
| Goal Room | PASS |
| Fact Inbox | PASS |
| Material taxonomy/lifecycle | PASS |
| Quick Notes | PASS |
| Question Banks | PASS |
| Command Palette | PASS |
| Guided First Practice | PASS — packaged resources / sidecar; native Overlay step honestly blocked |
| Practice 3.0 | PASS |
| Panel Practice | PASS |
| Content vs Delivery | PASS |
| Preflight | PASS |
| Live Cue-first hierarchy | PASS |
| Pin Moment | PASS |
| Closing Mode | PASS |
| Reflection | PASS |
| History | PASS |
| Settings 3.0 | PASS |
| v1.4 validation UI | PASS |
| Light/Dark | PASS |
| 390px | PASS |
| Native Electron BrowserWindow visual proof | BLOCKED_HOSTED_WINDOWS_RUNNER_NO_INTERACTIVE_DESKTOP |
| Native overlay geometry / multi-monitor visual proof | BLOCKED_HOSTED_WINDOWS_RUNNER_NO_INTERACTIVE_DESKTOP |

## 5. Decision

```text
V1_3_RUNTIME_UI =
ACCEPTANCE_CANDIDATE
```

No broad visual rewrite is warranted before v1.3 release. Remaining changes should be limited to defects found by CI/runtime evidence and release-truth synchronization.

The product still needs the final branch CI gate, merge/main CI, tag/release and download-back before `V1_3_PRODUCT_COMPLETE` can be claimed.
