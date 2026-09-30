# 成竹 Chengzhu v1.2.0

## What is Chengzhu / 成竹是什么

成竹是一个本地优先的技术面试准备、练习与实时辅助桌面应用：从你的简历和目标岗位出发，冻结一份本场 InterviewPack，上场时先给出简短可说的 Fast Cue，再流式给出完整回答；个人经历只来自你确认过的来源，不被模型改写。

Chengzhu is a local-first desktop app for technical-interview preparation, rehearsal and live assistance. It starts from your resume and a job goal, freezes an InterviewPack for the session, shows a short speakable Fast Cue first and the full answer after it, and never lets the model invent personal facts.

## Key features

- **InterviewPack**: job goal → prepare → freeze; Live reads only the frozen pack (no "latest job" reads), restart-safe.
- **Fast Cue before Deep answer**: a deterministic cue renders as soon as the question is recognized; the deep answer streams after it.
- **Facts with provenance**: source / user confirmation / said-in-session are separate; unsourced personal claims get a private warning, never silent reinforcement.
- **Stream Truth Guard**: first-person claims are checked while streaming; knowledge content streams normally.
- **Review 2.0**, **Story Builder**, **Voice preferences**, **reviewed Skill Cards**, **Human Coach (practice, local network)**, **first-run onboarding + diagnostics**.
- **Share Privacy** is OFF by default, per session, and always visible in the tray.

## System requirements

- Windows 10 / 11, 64-bit. 8 GB RAM recommended (local speech recognition).
- About 700 MB disk for the app; local Whisper models download on first use (~150 MB for `base`).
- No Python, Node or other runtime needed.

## Install

1. Download `Chengzhu-Setup-x64.exe` and `SHA256SUMS.txt` from this release.
2. Optional: verify: `Get-FileHash .\Chengzhu-Setup-x64.exe -Algorithm SHA256` must match the line in `SHA256SUMS.txt`.
3. Run the installer (per-user, no admin rights; you can choose the folder).

**Unsigned Windows build:** the installer is not code-signed yet, so Windows SmartScreen shows "Windows protected your PC". Click **More info → Run anyway** only if the SHA256 matches this release.

## Portable

Unzip `Chengzhu-Portable-x64.zip` anywhere and run `Chengzhu.exe`. Portable and installed builds share the same user data folder.

## Your data (local-first)

Everything is stored under `%APPDATA%\Chengzhu` (config, database, logs). The install folder is never written to. Uninstalling keeps your data; delete that folder to remove it.

## BYOK (bring your own key)

A model is optional for onboarding, preparation and review. For AI answers, add your own OpenAI-compatible provider key in Settings. Keys stay on your machine and are sent only to the provider you configure. Speech recognition runs locally (Whisper) or through your own Doubao / generic ASR credentials.

## Latency profiles (measured, see `reports/CHENGZHU_V1_2_R2_LATENCY_FORENSICS.md`)

TTFUG_user = time from the interviewer finishing the question to the first useful cue **on screen**.

{{LATENCY_TABLE}}

Numbers depend heavily on your CPU and what else is running. The local profile needs no network. The streaming profile needs your own streaming ASR key, and its figures are simulated from a model of that provider, not measured against the live service.

## Human Coach scope

Human Coach connects a helper over your local network (LAN) for practice sessions. It is independent of AI settings, uses revocable tokens and is off for formal interviews by default. A public relay is not included.

## macOS

Not available in this release (needs Apple hardware and a developer account for signing and notarization).

## Known limitations

{{KNOWN_LIMITATIONS}}

## License

MIT (`LICENSE.txt`). Third-party components keep their own licenses (`THIRD_PARTY_NOTICES.md`); the Windows build contains no copyleft components.

Use Chengzhu to prepare, rehearse and review honestly. Follow the rules of any interview you take part in.
