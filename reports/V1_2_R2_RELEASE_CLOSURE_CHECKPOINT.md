# v1.2-R2 Release Closure — Checkpoint

Date: 2026-09-30

| Item | State |
|---|---|
| HEAD | `main` = `2608879` (tag `v1.2.2`); report commit follows on a docs PR |
| Release | v1.2.2 **Latest** — https://github.com/huangdi97/cheng-zhu/releases/tag/v1.2.2 |
| PRs | #1, #2, #3 merged; all CI green on each head and on `main` (`36713331944`) |
| Completed gates | PR CI · main CI · license closure (MIT, PyMuPDF REPLACED, provenance SELF_AUTHORED_CONFIRMED) · tag · GitHub Release (installer, portable, SHA256SUMS, LICENSE, THIRD_PARTY_NOTICES, notes) · download-back by URL + SHA256 · fresh en-US Windows VM install/launch/onboarding/freeze/Live/restart/uninstall/portable (release-verify `36716495128`) · screenshots from the downloaded build |
| Latency | pooled clean-runner: Local CPU 1.58 s / 3.00 s (p95 at the Gate A boundary), Streaming (simulated) 0.56 s / 2.08 s (Gate A met) |
| Open gate | **Clean Windows 11 install with no Python / Node (Windows Sandbox)** for v1.2.2 — the host's Windows Sandbox app crashes on start since a Store update (WindowsSandboxRemoteSession `CLASS_E_CLASSNOTAVAILABLE`); needs a reboot. Maintainer chose to run it later. |

## Next exact command (after a reboot)

From `E:\AI\面试助手` in PowerShell, with the three assets downloaded from the v1.2.2 release into a folder
(`Chengzhu-Setup-x64.exe`, `Chengzhu-Portable-x64.zip`, `SHA256SUMS.txt`):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\sandbox\run-clean-install.ps1 -ReleaseDir "$env:TEMP\chengzhu-v1.2.2-download-back" -OutDir artifacts\release-evidence\v1.2.2-download-back\sandbox-win11
```

It opens Windows Sandbox (Windows 11, no Python, no Node, no repo), runs
`scripts/sandbox/verify-clean-install.ps1` inside it and writes `results.json`, `verify.log` and
screenshots to the output folder; exit code 0 = every required check passed. Then update the verdict in
`reports/CHENGZHU_V1_2_R2_FINAL_REALITY_REPORT.md` (expected: RELEASE_READY_WITH_EXTERNAL_BLOCKERS).
