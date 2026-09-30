# Chengzhu v1.2-R2 — Latency Forensics & Closure

Date: 2026-09-30 · Scope: Stages A–H of the release-closure goal.
Raw data: `reports/perf/latency_bench_ci.json` (clean runner) + `latency_bench_ci_runner.json`.
Harness: `scripts/bench_latency.py` · corpus: `backend/evals/latency_corpus/` (`scripts/latency_corpus.py`) · tables: `scripts/render_latency_report.py` · CI: `.github/workflows/latency-bench.yml`.

## 1. What changed in the measurement (and why the old number was optimistic)

The previous report (`CHENGZHU_V1_2_R2_PERFORMANCE.md`, TTFUG_user p50 3.62 s) measured the **server emit** of the Fast Cue with a raw faster-whisper call. Forensics against the real product found three things that made the user-visible number worse than reported:

| Finding | Effect | Fixed |
|---|---|---|
| The frontend only rendered a Fast Cue once `answer_start` created the QA card, and `answer_start` comes after the 1.2 s late-constraint grace + worker pre-processing | the cue the user **saw** was ≥ 1.35 s after the emit that was being measured | cue now renders on arrival (`guidance_fast` carries its question; `guidance_fast_retract` removes an unconfirmed one) |
| The product STT is `STTEngine.transcribe` (beam 3, VAD filter, initial prompt, **auto language detection**), not a beam-1 raw decode | auto detection is a second encoder pass: +0.5 s per decode on CPU | sticky language (pins after two confident agreeing detections, re-checks every 4th decode, unpins and re-decodes when a pinned decode hears nothing) |
| At every VAD flush the streaming preview called `finish()`: join the thread + one more full preview decode **on the capture thread** before the segment was even queued | +0.8–2.5 s before the authoritative decode could start | `stop()` at flush; no re-decode without new audio; adaptive preview throttle on a busy CPU |

The new harness uses the product components end to end (see §3), all time points on one monotonic simulated clock, and **ground-truth** speech end E from the clean synthesized speech.

## 2. Two product bugs the controlled corpus found

1. **English questions were rejected in the default `smart` mode** — every English question without a Chinese cue word was classified as "这段内容不像完整问题" and never answered (`test_asr_english_questions.py`).
2. **Chinese questions with 哪里/哪个/多少/会不会/是不是… ending in "。"** (Whisper often drops "？") were rejected the same way.

Both were in the shipping f04f217 build and are independent of latency.

## 3. Pipeline after the closure (Stages C–E)

```
audio ─▶ VAD (preroll 0.24 s) ─┬─▶ streaming preview (local Whisper / Doubao) ─▶ LiveTurnTracker
                               │        partial text + covered samples / provider endpoint
                               │
        trailing silence ≥0.30 s ─▶ speculative final decode (local Whisper only)
                               │        = end-covering "partial" + reused as the final
                               │
        EndOfTurnDetector: CONTINUE / LIKELY_END / CONFIRMED_END
          inputs: silence, partial coverage + stability, punctuation, question
          terminal phrases, semantic completeness, dangling connectors, open
          conditions, follow-up relation, the speaker's own pause pattern,
          provider endpoint; min 0.55 s (comma pauses), hard timeout 1.2 s
                               │
     CONFIRMED_END / flush ─▶ provisional Fast Cue (stable end-covering partial,
                               or a complete authoritative final) ─▶ UI now
                               │
     authoritative final ─▶ merge / group windows ─▶ confirm on the SAME card:
                               same (no re-render) · corrected · replaced · retracted
                               │
                        deep answer (after the 1.2 s late-constraint grace)
```

Predictive start (Stage D): the existing read-only prefetch (`services/intelligence/predictive.py`: question-type/domain hypothesis + KB retrieval from the first meaningful partial) is unchanged; job requirements, evidence and pack context are in-memory pack reads (2–3 ms, measured) and need no prefetch. Nothing on the provisional path commits interview state, Session Claims, the resolved question, final guidance or a deep answer.

## 4. Results

Primary measurement: clean GitHub `windows-latest` runner (AMD EPYC, 4 vCPU, CPU 15–20 % before each mode; run `36689804321` on commit `edc47e5`). 33 corpus fixtures (+1 silence clip); the final Local profile ran 3 repeats (n = 99).

Generated 2026-09-30 08:43:59 · faster-whisper base int8 CPU (product STTEngine) · 4 CPU threads

### Headline (TTFUG_user = first useful cue on screen − ground-truth speech end)

| Mode | n | TTFUG_user p50 | p95 | QBD p50 | p95 | TTFUG_internal p50 | question ok | no question | cue before deep |
|---|---|---|---|---|---|---|---|---|---|
| baseline (v1.x path) | 32 | 7.05 s | 7.55 s | 5.70 s | 6.20 s | 1.35 s | 0.750 | 1 | 1.00 |
| r2_prev (f04f217, old frontend) | 32 | 5.27 s | 5.93 s | 3.92 s | 4.58 s | 1.35 s | 0.750 | 1 | 1.00 |
| **final · Local CPU profile** | 99 | 1.30 s | 2.54 s | 2.22 s | 2.98 s | -0.82 s | 0.788 | 0 | 1.00 |
| **final · Streaming profile (SIMULATED provider)** | 33 | 0.56 s | 2.00 s | 1.98 s | 2.12 s | -1.42 s | 0.758 | 0 | 1.00 |

### Safety rates

| Mode | premature end | premature cue | question replaced | provisional cues (same / corrected / replaced) | cards rendered >1× | false trigger on silence |
|---|---|---|---|---|---|---|
| baseline (v1.x path) | 0.000 | 0.000 | 0.000 | 0 (0 / 0 / 0) | 0 | 0 |
| r2_prev (f04f217, old frontend) | 0.000 | 0.000 | 0.000 | 0 (0 / 0 / 0) | 0 | 0 |
| **final · Local CPU profile** | 0.000 | 0.000 | 0.010 | 99 (83 / 9 / 1) | 10 | 0 |
| **final · Streaming profile (SIMULATED provider)** | 0.000 | 0.000 | 0.000 | 33 (21 / 10 / 0) | 10 | 0 |

### Forensic time points (median ms after ground-truth speech end E)

| Point | baseline (v1.x path) | r2_prev (f04f217, old frontend) | **final · Local CPU profile** | **final · Streaming profile (SIMULATED provider)** |
|---|---|---|---|---|
| partial_first | -1740 (n=32) | -1756 (n=32) | -1920 (n=99) | -2310 (n=33) |
| partial_stable | — | — | 1080 (n=47) | 540 (n=27) |
| speech_end_estimate | -20 (n=32) | -20 (n=32) | -20 (n=99) | -20 (n=33) |
| vad_end | 1180 (n=32) | 1180 (n=32) | 1180 (n=99) | 560 (n=33) |
| asr_final | 3150 (n=32) | 3011 (n=32) | 1404 (n=99) | 1160 (n=33) |
| question_candidate | 5160 (n=32) | 3380 (n=32) | 1760 (n=99) | 1520 (n=33) |
| question_confirmed | 5700 (n=32) | 3920 (n=32) | 2220 (n=99) | 1980 (n=33) |
| guidance_fast_created | — | 3920 (n=32) | 1200 (n=99) | 560 (n=33) |
| guidance_fast_broadcast | — | 3922 (n=32) | 1302 (n=99) | 562 (n=33) |
| guidance_fast_rendered | 7053 (n=32) | 5270 (n=32) | 1302 (n=99) | 562 (n=33) |
| deep_first_token | 7580 (n=32) | 5800 (n=32) | 4100 (n=99) | 3860 (n=33) |
| deep_done | 7720 (n=32) | 5940 (n=32) | 4240 (n=99) | 4000 (n=33) |

### Machine load during each mode (calibration = one fixed zh-short decode; ~0.8 s when the CPU is quiet)

| Mode | repeat | CPU before | calib. before | CPU after | calib. after |
|---|---|---|---|---|---|
| baseline | 0 | 17.1% | 1265 ms | 14.8% | 748 ms |
| r2_prev | 0 | 18.3% | 1272 ms | 17.2% | 747 ms |
| local | 0 | 16.8% | 1335 ms | 15.9% | 763 ms |
| local | 1 | 19.9% | 1338 ms | 17.4% | 742 ms |
| local | 2 | 18.1% | 1277 ms | 15.2% | 743 ms |
| streaming_sim | 0 | 18.6% | 1306 ms | 16.2% | 1275 ms |

### Errors (no question submitted)

- baseline: en-long
- r2_prev: en-long
- local: none
- streaming_sim: none

`en-long` in baseline / r2_prev: the old path's cue arrived after the harness tail on this 11 s question (not a crash); every mode recognizes it once the cue path is fast enough.


### Latency gates

| Gate | Target | Local CPU profile (measured) | Streaming profile (simulated) |
|---|---|---|---|
| **Gate A** | TTFUG_user p50 ≤ 2.0 s, p95 ≤ 3.0 s | **MET** — 1.30 s / 2.54 s | **MET** — 0.56 s / 2.00 s |
| premature_end_rate ≤ 3 % | | 0.000 | 0.000 |
| premature_cue_rate ≤ 3 % | | 0.000 | 0.000 |
| question_replacement_rate ≤ 5 % | | 0.010 | 0.000 |
| **Gate B** | TTFUG_user p50 ≤ 1.2 s, p95 ≤ 2.0 s | **not met** (1.30 s / 2.54 s) | **MET** (0.56 s / 2.00 s, p95 at the limit) |

`LATENCY_GATE_A = MET` (both profiles). Gate B is split by profile as Stage G requires: the Streaming
profile meets it in simulation; the Local CPU profile (Whisper `base` on 4 CPU cores) does not, and the
release notes say so. Before the closure the same harness measured the shipped f04f217 path at
5.27 s / 5.93 s (as rendered) and the v1.x path at 7.05 s / 7.55 s.

No cue is shown for half a question: premature end / premature cue are 0 in both profiles; a
provisional cue is re-rendered at most once, on the same card (`corrected`), in 9–10 % of turns;
one local turn in 99 was `replaced`.


## 5. Where the remaining time goes

Local CPU profile (median after E, from the forensic table):

| Stage | Time |
|---|---|
| wait for 0.30 s of trailing silence (speculative trigger) | 0.30 s |
| speculative final decode (product engine, beam 3, sticky language) + any in-flight preview decode it waits for | ≈ 1.0 s |
| provisional cue compute + render | ≈ 3 ms |
| **first useful cue on screen** | **1.30 s** |
| authoritative final available (reused decode) | 1.40 s |
| question confirmed (merge + group windows) | 2.22 s — confirms the cue already on screen |
| deep answer first token (fake provider, after the 1.2 s late-constraint grace) | 4.10 s |

The remaining local cost is the CPU Whisper decode itself. Reaching Gate B locally needs faster
recognition — a GPU, a smaller/distilled model, or a true streaming ASR — not more waiting-time
tuning. The p95 tail is long questions (en-long: 7 s of audio) and one wasted speculative decode on a
comma pause (zh-coding).

Streaming profile: the provider endpoint (end_window 320 ms + 250 ms modeled lag) confirms the turn
at 0.56 s; the provisional cue renders immediately; the provider final (modeled 600 ms) confirms it
at the same card.

Developer machine (not the headline): with a Docker VM and other applications running, the same
fixed calibration decode took 0.8–5.4 s instead of ~0.75 s; Local-profile latency scales with that
factor. Earlier runs on that machine (before the harness matched the product VAD preroll) are not
reported.


## 6. Cue quality regression (Stage H)

| Suite | Result |
|---|---|
| Eval 2.0 `python -m evals.r2_eval --check` | mandatory **20/20**; dev route exact 1.0; seven-turn 1.0; unsupported claim blocked 1.0; held-out v2 exact **0.833** (unchanged from before the closure) |
| Question text correct (corpus, keyword match) | same in every mode (misses are Whisper-base recognition errors: 单线成, 漫茶巡, 分裤分表, "tree offs") — the latency work does not change what is recognized |
| Premature partial question / corrected final | `test_end_of_turn.py::test_premature_partial_is_reconciled_on_the_same_card`, `…two_part_turn…`, `…comma_pause…`; provisional relations in the corpus runs above |
| Truth boundary / follow-up / topic reset / Job A/B / Session Claim | backend suite (990 tests) green, including the existing fixtures for each |

## 7. Honest limits

- The corpus is Windows SAPI speech (+ mixed noise / keyboard / echo). Real human speech — accents, disfluency, room acoustics — is not in it; real multi-hour audio remains **BLOCKED-EXTERNAL**.
- The Streaming profile is **simulated**: partials are real Whisper text of the audio so far, delivered with a modeled provider lag (250 ms), endpoint (Doubao end_window 320 ms + lag) and final (600 ms). The maintainer chose not to spend a paid Doubao key on the benchmark; a measured streaming-provider profile is **BLOCKED-EXTERNAL**.
- The deep answer times use the fake provider (TTFA 0.53 s after dispatch); real-provider TTFA/TTD are **BLOCKED-EXTERNAL**.
- Local CPU numbers depend heavily on the CPU and its load (see §5); the headline is the clean 4-vCPU runner.
