# Chengzhu v1.2-R2 — Soak

Simulated with `scripts/soak_sim.py` (raw: `reports/perf/soak.json`): the real answer worker with a fake provider, ~1 question per minute, one frozen InterviewPack, an unsourced candidate statement once an hour, a provider failure every 25th turn, and a coach create/revoke cycle every 45 turns.

| Session | Turns | RSS start → end | Prompt chars (1st h → last h) | Pack stable | State topic stack | DB size | Provider failures injected / recovered | Coach sessions left active | Result |
|---|---|---|---|---|---|---|---|---|---|
| 2 h | 120 | 108.7 → 135.8 MB (import warm-up) | 451 → 494 | yes | 12 | 0.8 MB | 4, all recovered | 0 | PASS |
| 3 h | 180 | 128.6 → 129.3 MB | 451 → 485 | yes | 12 | 1.1 MB | 7, all recovered | 0 | PASS |
| 5 h | 300 | 129.3 → 130.1 MB | 451 → 490 | yes | 12 | 1.8 MB | 12, all recovered | 0 | PASS |

Checks: no context pollution (last-hour prompt ≤ 1.5× first hour), same pack id and content hash every turn, bounded interview state and session history (qa history capped at 80), bounded latency history (500), no leaked coach sessions. DB grows ~0.35 MB/hour (turn traces + telemetry).

## Not simulated → BLOCKED-EXTERNAL

- Real multi-hour interview with real audio devices and people
- Audio device switching mid-session, sleep/wake, real network loss
