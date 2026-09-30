# Troubleshooting

Most errors are explained in the app itself (first-run guide, Settings → 常用 → 运行状态). This page lists the common ones.

| Symptom | Cause | Fix |
|---|---|---|
| "端口 18080 被占用" at start | Another program uses the port | The app tries 18080–18099 automatically; if all are busy, close the other program. |
| "找不到内置后端程序" | Incomplete install | Reinstall from the Release page. |
| Model test: "API Key 无效或已过期" | 401 from the provider | Settings → 模型: re-enter the key. |
| "额度不足或触发限流" | 429 / quota | Check the provider balance, retry later. |
| "连接服务商超时" / "无法连接服务商" | Network / proxy / wrong Base URL | Check network and the Base URL. |
| "本地识别模型下载失败" | Whisper model download blocked | Retry on a working network, or switch STT to a cloud engine in Settings → 语音. |
| No microphone / no system audio | Device missing or not allowed | Plug in a device; allow microphone access in Windows privacy settings; system audio uses the current speaker output (loopback). |
| Fast Cue says "先说边界" for something you did | The InterviewPack has no source for it | 我的成竹 → 事实与来源: add a source or confirm it, then re-freeze the pack. |
| Live uses the wrong job | The session pack is from another Job Goal | 求职 → 岗位目标 → 冻结并用于本场 (creates a new revision). |
| Warning "你刚才提到…没有材料支持" | You said something the pack cannot source | Choose 这是口误 / 继续但不要扩展细节 / 稍后确认; confirm or deny it in 复盘. |

## Where things are

- Data: `%APPDATA%\Chengzhu\data` (SQLite files: `intelligence.db`, `review.db`, `prep.db`, …)
- Config: `%APPDATA%\Chengzhu\config\config.json`
- Logs: `%APPDATA%\Chengzhu\logs`
- Model cache: `%APPDATA%\Chengzhu\cache`

Backups: copy the whole `%APPDATA%\Chengzhu` folder while the app is closed. Uninstalling keeps this folder.

## Share Privacy

Share Privacy uses the operating system's standard window content protection to reduce accidental exposure in supported screen-share / recording paths. Capture tools behave differently; it is not a security or "undetectable" guarantee.
