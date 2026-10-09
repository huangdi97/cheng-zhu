# BUGS FOUND AND FIXED

## BUG-01 (P1) — Packaged Windows app crashes at startup: overlayLayout.js missing from asar
- severity: P1（核心循环损坏：打包应用不可启动）
- reproduction: 构建 dist:win 后直接运行 `win-unpacked/Chengzhu.exe`（隔离 CHENGZHU_HOME）。主进程抛 `Error: Cannot find module './overlayLayout'`，Electron 弹出标题 “Error” 的异常对话框；backend sidecar 从未启动（无 userData layout、无监听端口）。
- expected: 窗口正常打开「成竹」、sidecar 启动。
- actual: 窗口标题 “Error”、无后端。
- root cause: `desktop/main.js` 顶层 `require('./overlayLayout')`（第 121 行），但 `desktop/package.json` `build.files` 列表未包含 `overlayLayout.js` → electron-builder 未打入 asar。
- scope: **同样影响已发布的 v2.0.0-beta.2 打包包**（其 main.js 同样 require overlayLayout；发布管线窗口证据失败时回退 web 证据，掩盖了该缺陷）。
- fix: `desktop/package.json` build.files 增加 `"overlayLayout.js"`。
- affected files: `desktop/package.json`、新增 `desktop/buildFilesCoverage.test.js`（回归门禁：扫描 main-process 本地 require vs build.files）。
- targeted test: `node --test desktop/buildFilesCoverage.test.js`（修复前会失败，修复后通过）。
- full regression: desktop 36/36；后端全量 1223/1223；重建 dist:win 后真机启动验证：窗口「成竹」、sidecar 监听端口、layout 建立、关闭 0 残留；发布管线窗口证据 harness 46 张截图 PASS。
- evidence: `16-packaged/dist-win-fixed.log.txt`、`04-desktop/runtime-fixed.txt`、`04-desktop/packaged-window-evidence-fixed.log.txt`、`artifacts/release-evidence/v2.0.0-beta.2/`（46 captures）。

## BUG-02 (P2) — Live Delivery cue 使用当前全局表达而非冻结 Session Pack 表达
- severity: P2（状态契约违规：Session 中改全局表达会改变本场 delivery cue）
- reproduction: 设置表达 v1 → start_session（pack 冻结 v1）→ 改全局表达 v2 → `evaluate_guidance(delivery_focus)` 输出 v2 风格（“沿用表达结构 narrative；控制在约 90 秒”）。
- expected: 当前 Session 使用冻结的 expression profile（“先给结论；用 2–3 个要点展开；控制在约 30 秒”）。
- actual: 使用修改后的 v2。
- root cause: `_delivery_cue()` 直接读 `_expression_profile()`（活配置），未优先读 frozen pack 的 `expression_profile`；canonical 契约（frozen Expression Profile → Guidance）被违反。
- fix: `_delivery_cue()` 优先使用 `_frozen_pack_payload(session).expression_profile`，无 pack 时才回退活配置。
- affected files: `backend/services/product/conversations.py`；新增回归测试 `test_delivery_cue_uses_frozen_expression_profile_after_global_change`。
- targeted test: 1 passed；conversations 全套件 119 passed；后端全量 1223 passed。
- evidence: `08-conversation/phase_j_k_p_report.full.json`（P1_expression_profile_freeze 全 True）、`02-backend/full-pytest-final.log.txt`。

## BUG-03 (测试基建) — 测试套件依赖开发者本机 STT 凭据（9 个 conversation 测试在 CI 外失败）
- severity: 环境隔离缺陷（修复前 9 failed / 1213 passed）
- reproduction: 本机 `backend/config.json` 配置 doubao STT；`pytest tests/test_product_conversations.py` 中 9 个 TRANSCRIPT+LOCAL 场景因 v2 隐私 fail-closed 预检被阻断（CI 无 config.json 故通过）。
- expected: 任何机器上测试行为一致。
- actual: 依赖开发者机器配置。
- root cause: `tests/conftest.py::product_env` 将磁盘 `config.json`（含远程 STT）复制进测试环境。
- fix: fixture 在内存 config 副本上强制 local-only STT（whisper、清空 doubao 凭据、candidate_remote_stt_enabled=False）；显式测试远程 STT 的用例仍自行 monkeypatch。
- affected files: `backend/tests/conftest.py`。
- targeted test: 原 9 个失败用例 9/9 通过。
- full regression: 后端全量 1222→1223 passed。
- evidence: `02-backend/full-pytest.log.txt`（修复前 9 failed）、`full-pytest-pass2.log.txt`、`full-pytest-final.log.txt`。

## BUG-04 (P3, 观察记录) — Playwright E2E 一处时序 flake
- severity: P3（不阻塞）
- reproduction: `v20-conversation-profile.spec.mjs` “Prepare → Preflight → Live → Guidance → Continue” 首次运行 `getByText('target cp-1')` 5s 超时，retry #1 通过（exit 0）。
- expected: 稳定通过。
- actual: 首次渲染时序偶发（异步 guidance 卡首帧）。
- root cause: 页面首帧异步渲染慢于默认 5s 断言窗口；未复现于 retry。
- fix: 未修（记录）；CI 配置 retries:1 可吸收此类时序。
- evidence: `05-e2e/playwright-functional.log.txt`（含 trace/screenshot/video 附件记录）。
