# RUNTIME EVIDENCE INDEX

证据根: `artifacts/local-validation/2026-10-09-chengzhu-full-simulation/`

| 阶段 | 路径 |
| --- | --- |
| 环境清单 | `00-environment/ENVIRONMENT.md`, `git-status-initial.txt`, `tool-versions.txt`, `audio-devices.txt`, `initial-working-tree.diff` |
| 静态门禁 | `01-source-gates/STATIC_GATES_SUMMARY.md` |
| Backend 全量 | `02-backend/full-pytest.log.txt`（修复前 9 failed）、`full-pytest-pass2.log.txt`（1222）、`full-pytest-final.log.txt`（1223） |
| Intelligence | `02-backend/intelligence-strict-eval.log.txt`（exact 1.0 / r2_eval 20/20） |
| Product DB / Migration / Restart | `02-backend/phase_f_report.log.txt` + `phase_f_db_migration_persistence.py` + `db-snapshots/phase-f*` |
| E2E 功能 | `05-e2e/playwright-functional.log.txt`（55+1 flaky+3 skip） |
| Visual | `06-visual/visual-first-run.log.txt`, `visual-final-run.log.txt`, `screenshot-evidence.log.txt`; 基线 `frontend/e2e/__screenshots__/visual.spec.mjs/*-win32.png`; 截图 `screenshots/*.png`（60 张）+ `screenshots/screenshots-manifest.json` |
| 六 Profile 模拟 | `08-conversation/phase_i_report.full.json` + `phase_i_profiles_simulation.py`（14 场） |
| 冻结 Pack/Truth/Thread/State/Ask/表达 | `08-conversation/phase_j_k_p_report.full.json` + `phase_j_k_p_frozen_truth_state.py` |
| Scenario A/B | `08-conversation/phase_aa_report.full.json` + `phase_aa_scenarios.py` |
| Conversation+Connectors -vv | `08-conversation/conversations-connectors-vv.log.txt`（125 passed） |
| 音频设备 | `09-audio/device-enumeration.json` |
| Screen/Coach/隐私等 | 见 `conversations-connectors-vv.log.txt` 与 `phase_o_report.full.json` |
| 故障注入/Stress | `15-failure-injection/phase_o_report.full.json` + `phase_o_failure_stress.py`（F1–F7 + 100 sessions/600 items/300 threads/1000 segs） |
| Soak | `17-soak/soak-sim-3h.json` + `soak-sim-3h.log.txt` + `conversation_soak_report.full.json` + `conversation_soak.py` |
| 桌面真机 Runtime | `04-desktop/runtime-live.txt`, `runtime-fixed.txt`, `packaged-window-fixed.png`, `packaged-window-evidence-fixed.log.txt` |
| 发布窗口证据（46 captures + manifest） | `artifacts/release-evidence/v2.0.0-beta.2/`（截图 + manifest.json） |
| 打包 Web 证据（6 captures） | `artifacts/release-evidence/v2.0.0-beta.2/conversation-beta/` |
| Packaged candidate 清单 | `16-packaged/candidate-manifest.txt`, `dist-win.log.txt`, `dist-win-fixed.log.txt`, `build-sidecar.log.txt`, `packaged-smoke.json`, `capture-v20-evidence.log.txt` |
| Human Eval 工具链 | `18-human-eval-tooling/`（seed.jsonl、eval-empty.json、eval-synthetic-pass.json、readiness-empty.json、readiness-synthetic-pass.json、pilot-*.json、labels-*.jsonl） |
| 最终报告 | `19-final/*.md` + `MANIFEST.md` |
| DB 快照（合成） | `db-snapshots/phase-f*`, `phase-i`, `phase-j-k-p`, `phase-o`, `phase-aa`, `soak-conversation` |
