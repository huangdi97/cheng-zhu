# Chengzhu v1.2-R2 — Performance

Measured 2026-09-30 on the development machine (Windows 11, CPU only). Raw data: `reports/perf/ttfug_bench.json`, `reports/perf/soak.json`, `.tmp`-free and reproducible with `scripts/bench_ttfug.py` / `scripts/soak_sim.py`.

## Metric definitions (unchanged from the canonical)

- E = last voiced 20 ms frame of the recording (speech end)
- Q1 = question group confirmed and submitted
- G0 = first Fast Cue emitted by the server (UI render is covered by e2e, not added here)
- A0 = first deep token, D0 = deep answer complete
- **QBD = Q1 − E**, **TTFUG_user = G0 − E** (primary), TTFUG_internal = G0 − Q1, TTFA = A0 − Q1

The first model token is never counted as TTFUG.

## Controlled prerecorded benchmark

Setup: 9 prerecorded questions (Windows SAPI offline voices; zh normal / request / 700 ms internal pause / 1.4 s long pause / slow / fast, en normal / slow, zh-en mixed) × 3 repeats × 2 modes. Real components on a sample-accurate timeline: product-default VAD (`silence_duration` 1.2 s), local faster-whisper `base` int8 on CPU (wall time), real ASR state machine (merge gap 2.0 s, confirm 0.45 s, late-constraint grace 1.2 s), real Fast Cue code. Product defaults from `AppConfig()`, not a developer's config.

- **baseline**: `assist_eot_fast_flush=false`, `intelligence_early_cue=false` (the v1.x path)
- **r2**: both on (R2 defaults)

| | QBD p50 | QBD p95 | TTFUG_user p50 | TTFUG_user p95 | STT p50 | Cue compute p50 | Question text correct |
|---|---|---|---|---|---|---|---|
| baseline | 5040 ms | 5660 ms | 6244 ms | 6863 ms | 1380 ms | 2 ms | 0.667 |
| **r2** | **3620 ms** | 5680 ms | **3622 ms** | **5682 ms** | 1595 ms | 2 ms | 0.667 |
| Release SLO | ≤ 500 | ≤ 900 | ≤ 1200 | ≤ 2000 | | | |

These are from the final committed code (end-of-turn gap 0.35 s that ongoing speech still extends). An earlier run of the same benchmark with an unsafe immediate flush (since reverted: it could cut off a speaker who kept talking) gave r2 p50 3505 ms; the difference to the committed number is the 0.35 s safety gap plus machine variance in STT time (1.4–2.4 s across runs).

**Result: SLO NOT MET on this hardware.** R2 removes ~2.6 s at p50 (the 2.0 s merge gap and the 1.2 s late-constraint grace no longer sit in front of the first cue) without changing question assembly (same correctness in both modes; misses are Whisper-base recognition errors on synthetic speech, e.g. "B+树" → "比加速").

### Where the remaining ~3.6 s goes (r2, per case median)

| Stage | Time |
|---|---|
| VAD end-of-speech wait (`silence_duration`) | 1200 ms |
| Batch STT on CPU (Whisper base) | ~1800–2000 ms |
| End-of-turn gap (complete question) | 350 ms |
| Question group confirm window | ~450 ms |
| Fast Cue compute (understanding + pack compile + L0) | ~3 ms |

### Per-case notes

- `zh-long-pause` (1.4 s pause mid-sentence): VAD splits the utterance and the first half ("我们先聊聊缓存") is submitted as the question in **both** modes. This is an existing product limitation of a fixed silence threshold; adaptive end-of-turn inside the VAD needs streaming partial text and is not implemented yet.
- `mixed`: STT garbles "Kafka … 吗" → "Calf … 嘛", the end-of-turn cue does not fire and the 2 s merge gap applies (5.0 s).
- Cue compute is ~3 ms: the deterministic L0 path is not the bottleneck.

### What it would take to meet the SLO

1. Streaming ASR final signal (Doubao streaming or local streaming Whisper on a GPU) so STT is not a post-silence batch step — removes ~1.8 s.
2. Adaptive VAD end-of-turn using the streaming partial (e.g. 0.45 s silence when the partial already reads as a complete question, with rollback) — removes ~0.75 s.
3. Shorter confirm window for high-confidence complete questions.

None of these were tuned into the benchmark; the numbers above are what the shipped defaults do on this machine.

## Live path stage timings (from the running system)

| Stage | Measured |
|---|---|
| Context compile (pack providers + dedupe) | p50 2–3 ms (worker logs, soak) |
| TTFUG_internal (worker path, fake provider, packaged sidecar) | 156 ms |
| TTFA (fake provider streaming at 30 ms/chunk) | 531 ms |
| TTD (fake provider) | 672 ms |
| Packaged sidecar cold start | 2.6 s; restart 1.5–2.5 s |

Real-provider TTFA / TTD depend on the provider and key: **BLOCKED-EXTERNAL** (no provider key used for evaluation).

## Soak (simulated)

See `CHENGZHU_V1_2_R2_SOAK.md`.
