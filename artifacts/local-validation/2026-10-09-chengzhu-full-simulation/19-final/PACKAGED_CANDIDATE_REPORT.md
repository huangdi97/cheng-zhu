# PACKAGED CANDIDATE REPORT

- 构建源: 当前 main 分支 HEAD（非 beta.2 tag）`af709e5183ddd33071e27ee13680e93448f2e683`
- 构建命令（按 docs/RELEASE.md + desktop/package.json + CI）:
  1. `python scripts/build_sidecar.py`（clean venv + PyInstaller）→ `build/sidecar/chengzhu-backend/chengzhu-backend.exe`
  2. `python scripts/packaged_smoke.py --exe build/sidecar/... --frontend-dist frontend/dist --report …` → PASS
  3. `cd desktop && npm run dist:win`（electron-builder ns installer + portable zip）→ PASS
- 构建时间戳: 2026-10-09 21:01-21:04（修复后重建）；清单 `16-packaged/candidate-manifest.txt`

## Artifacts（SHA256 / size）
| 文件 | SHA256 | Size |
| --- | --- | --- |
| `dist/desktop/Chengzhu-Setup-x64.exe` | `4EE6302E3BD3652908249333F980D290568F5AD443F66228EA955C1FC9C2EDEC` | 193.21 MB |
| `dist/desktop/Chengzhu-Portable-x64.zip` | `CE92FB99AF7E05C7F6F96F4BC14A5143880C89D1E059B8CF74CCADF90C8527F8` | 256.55 MB |
| `build/sidecar/chengzhu-backend/chengzhu-backend.exe` | `5F56D2AC2087164BF412781E967B920A9C47C136886BF3781ECBEFCFA898EFD7` | 16.61 MB |

## 验证结果
- `packaged_smoke.py`: fresh first run 7.7s、cold start 5.55s、WS 事件、fast-cue-first、Conversation space/session/preflight/pack 冻结、decision reviewed、ask/search/continue grounded、restart 后 pack 持久化、schema v7、diagnostics healthy、license bundled —— **passed**。
- Conversation 打包 Web 证据: 6 张截图（Home/Space/Prepare/Live/Sessions/History）全部 `UNOBSTRUCTED_BY_MODAL`，pack digest/session ACTIVE/history 保留 —— **PASS**。
- 真机 Electron 窗口证据: 46 张真实 BrowserWindow 截图（onboarding→Home→Goal→Prepare→Live→Reflection→Conversation 流程）—— **PASS**（在修复 BUG-01 后）。
- 桌面 Runtime: 窗口「成竹」、sidecar 监听端口、userData layout 建立、正常关闭 0 残留 —— **PASS**。

## 过程中发现并修复的打包缺陷（重要）
- **BUG-01 (P1)**: 打包候选（与已发布 beta.2 相同配置）启动即崩溃——`overlayLayout.js` 未列入 `build.files`。修复后打包应用可正常启动；新增 `desktop/buildFilesCoverage.test.js` 回归门禁。
- 环境备注: electron-builder 首次构建需下载 NSIS 工具链；本机 git 走本地代理 `127.0.0.1:10808`，为构建设置了 `HTTPS_PROXY/HTTP_PROXY`（仅本次构建进程）。

## 判定
```
LOCAL_PACKAGED_CANDIDATE = READY_FOR_DOGFOOD
（NOT: READY_FOR_STABLE_RELEASE；真实用户证据仍 PENDING）
```
- 未自动发布 GitHub Release（遵守契约）。
- Clean-install replay: packaged smoke + 窗口证据 harness 均以全新 userData 完成 first-run、onboarding、Interview、Conversation、restart 持久化 —— 证明非 dev server only。
