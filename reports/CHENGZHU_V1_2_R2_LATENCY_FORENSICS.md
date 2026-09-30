# Chengzhu v1.2-R2 — Latency Forensics & Closure

Date: 2026-09-30 · Scope: Stages A–H of the release-closure goal.
Raw data: `reports/perf/latency_ci/` (3 clean-runner runs + pooled summary).
Harness: `scripts/bench_latency.py` · corpus: `backend/evals/latency_corpus/` (`scripts/latency_corpus.py`) · tables: `scripts/render_latency_report.py` · CI: `.github/workflows/latency-bench.yml`.

## 1. What changed in the measurement (and why the old number was optimistic)

The previous report (`CHENGZHU_V1_2_R2_PERFORMANCE.md`, TTFUG_user p50 3.62 s) measured the **server emit** of the Fast Cue with a raw faster-whisper call. Forensics against the real product found three things that made the user-visible number worse than reported:

| Finding | Effect | Fixed |
|---|---|---|
| The frontend only rendered a Fast Cue once `answer_start` created the QA card, and `answer_start` comes after the 1.2 s late-constraint grace + worker pre-processing | the cue the user **saw** was ≥ 1.35 s after the emit that was being measured | cue now renders on arrival (`guidance_fast` carries its question; `guidance_fast_retract` removes an unconfirmed one) |
| The product STT is `STTEngine.transcribe` (beam 3, VAD filter, initial prompt, **auto language detection**), not a beam-1 raw decode | auto detection is a second encoder pass: +0.5 s per decode on CPU | sticky language (pins after two confident agreeing detections, re-checks every 4th decode, unpins and re-decodes when a pinned decode hears nothing) |
| At every VAD flush the streaming preview called `finish()`: join the thread + one more full preview decode **on the capture thread** before the segment was even queued | +0.8–2.5 s before the authoritative decode could start | `stop()` at flush; no re-decode without new audio; adaptive preview throttle on a busy CPU |

The new harness uses the product components end to end (see §3), all time points on one monotonic simulated clock, and **ground-truth** speech end E from the clean synthesized speech.

## 2. Product bugs found during the closure (all fixed)

1. **English questions were rejected in the default `smart` mode** — every English question without a Chinese cue word was classified "这段内容不像完整问题" and never answered (`test_asr_english_questions.py`). In the shipping f04f217 build.
2. **Chinese questions with 哪里/哪个/多少/会不会/是不是… ending in "。"** (Whisper often drops "？") were rejected the same way. In f04f217.
3. **Sticky language could drop a question**: with `zh` pinned, an English question decoded to an empty string → re-decode with detection when a pinned decode hears nothing / only weakly.
4. **…or echo the Whisper initial prompt** ("请优先识别技术术语英文原词…") with good confidence → prompt echo is treated as a language mismatch (v1.2.2).
5. **v1.2.0 exited at first launch on non-Chinese Windows locales** ("成竹后端已退出 (code 3)", `UnicodeEncodeError` on a cp1252 stdout — the frozen sidecar ignores `PYTHONIOENCODING`). Found by the download-back verification on a fresh en-US VM; fixed in v1.2.1; the packaged smoke now does a fresh first run on the en-US runner.

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

Final code = the v1.2.2 live path (commit `15e6407`). Three independent clean GitHub `windows-latest`
runs (4 vCPU each, product defaults, 34-clip corpus; the final Local profile ran 3 repeats per run, so
n = 297). Runs land on two CPU types; the slower one dominates the p95. Raw data:
`reports/perf/latency_ci/run-*.json`, pooled summary `reports/perf/latency_ci/pooled.json`.

### Pooled over 3 runs

| Mode | n | TTFUG_user p50 | p95 | per-run p95 | QBD p50 | TTFA p50 | premature end | premature cue | replaced | question ok | cue before deep |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline (v1.x path) | 99 | 7.25 s | 8.27 s | 8.43 s / 8.17 s / 7.63 s | 5.90 s | 1.88 s | 0.000 | 0.000 | 0.000 | 0.758 | 1.00 |
| r2_prev (f04f217, as rendered) | 99 | 5.61 s | 6.89 s | 6.89 s / 7.31 s / 5.69 s | 4.26 s | 1.88 s | 0.000 | 0.000 | 0.000 | 0.737 | 1.00 |
| **final · Local CPU profile** | 297 | 1.58 s | 3.00 s | 2.96 s / 3.12 s / 2.50 s | 2.44 s | 1.88 s | 0.000 | 0.020 | 0.000 | 0.788 | 1.00 |
| **final · Streaming profile (SIMULATED)** | 99 | 0.56 s | 2.08 s | 2.06 s / 2.06 s / 2.00 s | 1.98 s | 1.88 s | 0.000 | 0.000 | 0.000 | 0.758 | 1.00 |

| Run | runner CPU | calibration decode (ms) | Local p50 / p95 | Streaming p50 / p95 |
|---|---|---|---|---|
| 36709255474 | AMD64 Family 25 Model 1 Stepping 1, AuthenticAMD (4 vCPU) | [1687, 1911, 1689] | 1.74 s / 2.96 s | 0.56 s / 2.06 s |
| 36709258083 | AMD64 Family 25 Model 1 Stepping 1, AuthenticAMD (4 vCPU) | [1698, 1681, 1663] | 1.74 s / 3.12 s | 0.56 s / 2.06 s |
| 36709263343 | AMD64 Family 25 Model 17 Stepping 1, AuthenticAMD (4 vCPU) | [1248, 1278, 1553] | 1.26 s / 2.50 s | 0.56 s / 2.00 s |

**Correction.** An earlier draft of this report (and the v1.2.0 / v1.2.1 release notes) quoted a single run
(`36689804321`: Local 1.30 s / 2.54 s) that happened to land on the faster runner CPU. Re-running the same
code on more runners gave Local p95 2.90–3.08 s. The numbers above are pooled; single runs are not quoted.

### Forensic time points of one final run (`36709255474`, slower runner CPU; median ms after ground-truth speech end E)

| Point | baseline (v1.x path) | r2_prev (f04f217, old frontend) | **final · Local CPU profile** | **final · Streaming profile (SIMULATED provider)** |
|---|---|---|---|---|
| partial_first | -1686 (n=32) | -1701 (n=31) | -1530 (n=99) | -2210 (n=33) |
| partial_stable | — | — | 1120 (n=4) | 540 (n=27) |
| speech_end_estimate | -20 (n=33) | -20 (n=33) | -20 (n=99) | -20 (n=33) |
| vad_end | 1180 (n=33) | 1180 (n=33) | 1180 (n=99) | 560 (n=33) |
| asr_final | 3684 (n=33) | 3701 (n=33) | 1780 (n=99) | 1160 (n=33) |
| question_candidate | 5700 (n=33) | 4060 (n=33) | 2160 (n=99) | 1520 (n=33) |
| question_confirmed | 6200 (n=33) | 4520 (n=33) | 2620 (n=99) | 1980 (n=33) |
| guidance_fast_created | — | 4520 (n=33) | 1740 (n=99) | 560 (n=33) |
| guidance_fast_broadcast | — | 4522 (n=33) | 1742 (n=99) | 562 (n=33) |
| guidance_fast_rendered | 7553 (n=33) | 5870 (n=33) | 1742 (n=99) | 562 (n=33) |
| deep_first_token | 8080 (n=33) | 6400 (n=33) | 4500 (n=99) | 3860 (n=33) |
| deep_done | 8220 (n=33) | 6540 (n=33) | 4640 (n=99) | 4000 (n=33) |

### Machine load during each mode (calibration = one fixed zh-short decode; ~0.8 s when the CPU is quiet)

| Mode | repeat | CPU before | calib. before | CPU after | calib. after |
|---|---|---|---|---|---|
| baseline | 0 | 15.2% | 1665 ms | 13.7% | 989 ms |
| r2_prev | 0 | 16.4% | 1683 ms | 13.3% | 976 ms |
| local | 0 | 17.9% | 1687 ms | 39.8% | 1337 ms |
| local | 1 | 43.2% | 1911 ms | 14.1% | 977 ms |
| local | 2 | 17.4% | 1689 ms | 13.3% | 965 ms |
| streaming_sim | 0 | 16.4% | 1678 ms | 14.3% | 1696 ms |

### Errors (no question submitted)

- baseline: none
- r2_prev: none
- local: none
- streaming_sim: none


### Latency gates

| Gate | Target | Local CPU profile (measured, pooled) | Streaming profile (simulated, pooled) |
|---|---|---|---|
| **Gate A** | TTFUG_user p50 ≤ 2.0 s, p95 ≤ 3.0 s | p50 **1.58 s** met; p95 **3.00 s — at the boundary** (per run 2.50 / 2.96 / 3.12 s) | **MET** — 0.56 s / 2.08 s |
| premature_end_rate ≤ 3 % | | 0.000 | 0.000 |
| premature_cue_rate ≤ 3 % | | 0.020 | 0.000 |
| question_replacement_rate ≤ 5 % | | 0.000 | 0.000 |
| **Gate B** | TTFUG_user p50 ≤ 1.2 s, p95 ≤ 2.0 s | not met | p50 met; p95 **2.08 s — not met** |

`LATENCY_GATE_A = MET` for the Streaming profile (simulated provider). For the Local CPU profile the
median meets Gate A with margin and the 95th percentile sits exactly on the 3.0 s limit on a 4-vCPU
cloud CPU (met on 2 of 3 runs): **BORDERLINE**, not claimed as met. As Stage G requires, the profiles are
reported separately and the release notes state the local figure as measured. Before the closure the
same harness measured the shipped f04f217 path at 5.61 s / 6.89 s (as rendered) and the v1.x path at
7.25 s / 8.27 s.

Safety holds in both profiles: no premature end, premature cue ≤ 2 %, no question replaced, the cue
is before the deep answer in every turn, no false trigger on the silence clip, no question lost.

## 5. Where the remaining time goes

Local CPU profile, run `36709255474` (slower runner CPU), medians after E:

| Stage | Time after E |
|---|---|
| speculative final starts after 0.30 s of trailing silence (+ any preview decode still running) | ≥ 0.30 s |
| speculative final decode done (product engine, beam 3, sticky language) = authoritative text | 1.78 s |
| provisional cue computed and on screen (≈ 3 ms compute) | **1.74 s** |
| question confirmed by the merge + group windows (confirms the cue already on screen) | 2.62 s |
| deep answer first token (fake provider, after the 1.2 s late-constraint grace) | 4.50 s |

The remaining local cost is the CPU Whisper decode itself (≈ 1.0–1.5 s on these CPUs, up to 2.7 s for
a 7 s question). The p95 tail is long questions (en-long, zh-long) and noisy clips (echo, keyboard)
whose trailing noise delays the end of speech. Reaching Gate B locally — or a p95 with margin under
3.0 s on a 4-core CPU — needs faster recognition (GPU, a smaller/distilled model or a true streaming
ASR), not more waiting-time tuning. Decoding without timestamps was measured (40 % faster) and rejected:
it changed recognized text (en-behavioral came back as prompt text).

Streaming profile: the provider endpoint (end_window 320 ms + 250 ms modeled lag) confirms the turn at
0.56 s and the provisional cue renders immediately; the p95 (≈ 2.1 s) is turns where the partial did
not yet read as a complete question, which then wait for the provider final + windows.

Developer machine (not the headline): with a Docker VM and other applications running, the fixed
calibration decode took 0.8–5.4 s instead of ~0.75 s; Local-profile latency scales with that factor.

## 6. Cue quality regression (Stage H)

| Suite | Result |
|---|---|
| Eval 2.0 `python -m evals.r2_eval --check` | mandatory **20/20**; dev route exact 1.0; seven-turn 1.0; unsupported claim blocked 1.0; held-out v2 exact **0.833** (unchanged from before the closure) |
| Question text correct (corpus, keyword match) | same in every mode (misses are Whisper-base recognition errors: 单线成, 漫茶巡, 分裤分表, "tree offs") — the latency work does not change what is recognized |
| Premature partial question / corrected final | `test_end_of_turn.py::test_premature_partial_is_reconciled_on_the_same_card`, `…two_part_turn…`, `…comma_pause…`; provisional relations in the corpus runs above |
| Truth boundary / follow-up / topic reset / Job A/B / Session Claim | backend suite (994 tests) green, including the existing fixtures for each |

## 7. Honest limits

- The corpus is Windows SAPI speech (+ mixed noise / keyboard / echo). Real human speech — accents, disfluency, room acoustics — is not in it; real multi-hour audio remains **BLOCKED-EXTERNAL**.
- The Streaming profile is **simulated**: partials are real Whisper text of the audio so far, delivered with a modeled provider lag (250 ms), endpoint (Doubao end_window 320 ms + lag) and final (600 ms). The maintainer chose not to spend a paid Doubao key on the benchmark; a measured streaming-provider profile is **BLOCKED-EXTERNAL**.
- The deep answer times use the fake provider (TTFA 0.53 s after dispatch); real-provider TTFA/TTD are **BLOCKED-EXTERNAL**.
- Local CPU numbers depend heavily on the CPU and its load (see §5); the headline is the clean 4-vCPU runner.
