# Chengzhu UI v2 Visual Freeze R1

Date: 2026-10-19  
Status: implementation baseline

## North Star

> Quiet intelligence, at the moment it matters.

成竹的前台不是“AI 功能 Dashboard”。用户面对的是一个正在推进的 Goal；AI 只在当前任务需要时出现。

## Two visual worlds

### Studio

Used for Home, Goals, Goal Room, Prep, Practice setup, History and Reflection.

- warm neutral canvas;
- restrained bamboo accent;
- content hierarchy before containers;
- sections and hairlines before cards;
- one primary attention object per viewport;
- Goal over modules;
- evidence over scores.

### Live Cockpit

Used during a real interview.

- graphite translucent overlay independent from Studio theme;
- current turn first;
- compact by default;
- at most three cue bullets in the first layer;
- Deep is opt-in;
- transcript/history/supporting controls are secondary;
- no live performance score.

## Primary interview navigation

The persistent interview rail is:

1. Home
2. Goals
3. Practice
4. History
5. Me

Go Live is an action, not a navigation destination.

Library remains a capability and contextual destination, but it is not a primary front-door item.

## Home

Home answers only:

1. What is my current/next interview Goal?
2. What should I do now?

Do not restore:

- system status cards;
- module grids;
- readiness percentages;
- radar charts;
- model/provider status as ordinary content.

## Goal Room

The Goal header owns the current company/role context.

Primary action:

- Enter interview

Secondary action:

- Practice

Goal-level views remain compatible with current routes, but the visual hierarchy is:

- Overview
- Prep
- Sessions
- secondary lifecycle surfaces such as Offer

Overview prioritizes:

- next focus;
- recent sessions;
- next interview;
- goal context.

Progress trends are progressive disclosure, not an above-the-fold dashboard.

## Prep

Prep is a dossier/workspace, not a card gallery.

Main column:

- next focus;
- JD gaps;
- attack surface;
- likely questions.

Context rail:

- skills/stories;
- selected materials;
- quick notes;
- frozen session inputs.

## Live states

### Compact

Only session/listening state + Goal context.

Automatically return to Compact after approximately 12 seconds without new guidance.

### Cue

First layer:

- current question;
- judgment / short cue;
- maximum three speakable bullets;
- provenance;
- expand action.

### Deep

Only after explicit expansion.

May include:

- expanded answer;
- evidence;
- alternative framing;
- possible follow-up;
- risk.

### Artifact

Only when the task needs a second work surface (coding, system design, written problem, product case, calculations, structured whiteboard work).

Artifact is not synonymous with code.

## Reflection

Reflection is evidence-first.

First screen prioritizes:

- the grounded review focus;
- what worked;
- what was exposed;
- the single recommended next action.

Scores and dimension analytics may exist as secondary evidence, but must never become the hero or imply offer probability.

If evidence is insufficient, say so instead of inventing precision.

## Visual rules

- 90% neutral, 10% brand/semantic color.
- No bamboo/watercolor decorative backgrounds in ordinary product screens.
- Avoid nested cards.
- Ordinary Studio surfaces should prefer 8–12px radii.
- Pills are for status/tags, not every button.
- Shadows are reserved for overlays, popovers and dialogs.
- Icons are monochrome by default.
- Green is a state/brand accent, not a page background.

## Explicit anti-patterns

Do not reintroduce:

- Home module dashboard;
- permanent Transcript + Answer + Metrics three-column Live layout as the default;
- live numeric performance scoring;
- readiness percentage hero;
- radar-chart hero;
- long STAR scripts as the default Cue;
- multiple colored icon tiles as navigation;
- “stealth / undetectable” as Chengzhu's brand narrative.

## Current implementation mapping

This visual freeze is implemented primarily in:

- `frontend/src/App.tsx`
- `frontend/src/components/os/HomePage.tsx`
- `frontend/src/components/os/GoalRoom.tsx`
- `frontend/src/components/os/GoalPrepare.tsx`
- `frontend/src/components/os/GoalsPage.tsx`
- `frontend/src/components/os/PracticePage.tsx`
- `frontend/src/components/os/ReflectionPage.tsx`
- `frontend/src/components/os/NextFocusList.tsx`
- `frontend/src/components/os/SessionList.tsx`
- `frontend/src/components/os/ui.tsx`
- `frontend/src/components/InterviewOverlay.tsx`
- `frontend/src/index.css`

Legacy UI components may remain for compatibility, but they are not the design source of truth.

## Acceptance checks

### Home 5-second test

A user can identify the next/current Goal and the next action within five seconds.

### Live 1-second test

A glance reveals the cue's main judgment.

### Live 3-second test

Within three seconds the user has enough structure to continue speaking without reading a paragraph.

### Evidence test

Claims about the user remain distinguishable from inference, notes and generic advice.

### Silence test

When there is nothing useful to say, the interface is allowed to stay quiet.

### Brand test

Removing the logo must not make the UI indistinguishable from a generic AI SaaS dashboard.
