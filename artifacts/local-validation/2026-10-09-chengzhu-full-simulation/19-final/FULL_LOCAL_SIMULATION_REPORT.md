# Chengzhu v2 × v1 — FULL LOCAL SIMULATION REPORT

- 执行日期: 2026-10-09（契约基线）
- 分支: `test/chengzhu-v2-local-full-simulation-2026-10-09`
- 测试源 SHA（分支 HEAD）: `af709e5183ddd33071e27ee13680e93448f2e683`
- 远端 main SHA（执行时 fetch）: `383978fa480aac35d214dce3fa4e9fa5ebb17118`（`feat(v2): close final pure-repo Conversation product gap`）
- 结论: **LOCAL_FULL_SIMULATION = GO**（P0=0，P1=0；全部 §55 必需门禁 PASS）

## Source Truth
- 起始核验：本地 `git fetch origin --prune` 后 `origin/main = 383978fa…`，与交接信息一致。
- 从 `origin/main` 创建测试分支（未直接修改 main；无 force push/reset/rebase）。
- v1.3 本地脏工作树（7 个已跟踪修改 + 3 个新截图）已完整记录、stash 保护、结束还原并校验（见 Git 章节）。
- 版本事实：Stable Latest = v1.4.2（tag `ce72eb40…`）；Conversation Prerelease = v2.0.0-beta.2（tag `cac605ed…`）；当前 main 高于 beta.2。三者在报告中从未混同。

## Tests
- Backend: `pytest -q --tb=short` **1223 passed / 0 failed / 0 skipped**（302s）。含 Interview Core、Intelligence、Product DB、migrations、Conversation、capture、screen、coach、connectors、reminders、release/stable gates、export/delete、retention、provenance。
- Intelligence 严格评测: `route_accuracy_exact=1.0`（≥0.9）、`seven_turn_exact=1.0`（≥0.85）、`unsupported_claim_rate=1.0`（≥0.95）；`python -m evals.r2_eval --check` 20/20 mandatory PASS（heldout 4 项为已知 informational 项；`model_eval` 无 `CHENGZHU_EVAL_API_KEY` → BLOCKED_EXTERNAL）。
- Frontend: `tsc -b --noEmit` PASS；`npm test` 59 files / 428 tests PASS；`npm run build` PASS。
- Desktop: `node --test *.test.js` **36 passed**（含新增 build.files 覆盖回归测试）。
- E2E (Playwright functional): **55 passed / 1 flaky-retry-pass / 3 designed skips**（real-chain 需真后端，设计内跳过），exit 0。
- Visual: `@visual` 3/3 PASS（新增 win32 基线，经规则核验：DOM 断言通过、非空白、与 linux 基线像素相关 0.73–0.78）；另生成 **60 张截图证据**（light/dark × desktop/390px，全部无 modal 遮挡）。
- 打包 Smoke: `packaged_smoke.py` PASS（fresh first run、cold start、WS 事件、fast-cue-first、Conversation pack 冻结/restart 持久化、schema v7、license）。
- Soak: `soak_sim.py --hours 3` PASS（180 轮、RSS 106→133MB、无上下文污染、pack 稳定、无 coach 泄漏）；Conversation 本地 soak PASS（30 sessions、120 guidance、90 segments、reminders 稳定、restart 后 30/30 存活、0 未处理错误）。

## Interview（v1 全量回归）
- **INTERVIEW_REGRESSION = PASS**：backend 全量套件（Interview Core/Practice/Live/Reflection/History/Settings/Diagnostics/Share Privacy/Human Coach 路径）+ a11y/critical-paths/v13-product-loop E2E 全绿；Conversation schema migration（v1→v7）与 capture ownership 未污染 Interview。

## Conversation
- 六 Profile（Project Sync/Design Review/Presentation Q&A/1:1/Client Call/Negotiation）: **14 场**模拟全绿（Project Sync 与 Design Review 各 3 场跨会话 continuity；其余各 2 场）。无 emotion profiling / personality / hidden-intent（policy 三开关强制 OFF 已断言）。
- Session Pack 不可变: **PASS**（ACTIVE 后改 Goal/Material/Note/Participant/Expression/Thread/Connector，pack digest 前后一致）。
- Truth/Provenance 负向: AI-extracted≠AGREED、无 owner+source+review≠COMMITTED、无来源 Deadline=REJECT、四种模糊时间（周五/下周/月底/明天）全部阻断、Supersession 保留旧 Decision=SUPERSEDED、Quick Note/Transcript 不升 truth。
- Open Thread: AI_EXTRACTED 不持久 → CONFIRM→OPEN → RESOLVED/REJECT 关闭；520+300 条线程投影不截断；删除源 Session 无 phantom。
- Conversation State: derived read model，修改/派生视图不产生新 truth。
- Manual Ask: 权威序 CONFIRMED_TRUTH>PERSONAL_EVIDENCE>REFERENCE_SOURCE>USER_NOTE_NOT_EVIDENCE>OBSERVED_NOT_CONFIRMED；frozen source replacement（10x→50x）不伪 grounded；v2/v3、10x/50x、Q4/Q3、日期精确匹配。
- Live Guidance: Direct Question→ANSWER_CUE（QUIET 也可）、SELF_MIC 不打断、Recall/Opportunity、Quick Note 不自动 proactive、user speaking→SILENT、duplicate/stale/social-risk 抑制、critical risk 抢占；Profile lane 隔离（Presentation 无 TALKING_POINT、1:1 无 DELIVERY；仅全局 override 合法）。
- Audio/STT: 设备枚举（EDIFIER 麦克风/摄像头/loopback）；capture owner 隔离；双向互斥（Conversation↔Interview 互抢拒绝）；final ASR drain（stop 后最后一句可落盘）；self-mic degraded 状态。
- Privacy: LOCAL+remote-possible → Preflight BLOCK + Capture start 二次 BLOCK；OFF → transcript 不可用 + AI FORBIDDEN；config drift fail-closed；UI 从不静默走 remote。
- Screen Context: MANUAL（仅文本/哈希持久化，raw image 不落盘，OBSERVED_NOT_CONFIRMED）；AUTO（必须显式启动、dedupe、3 错 fail-stop、session end/space delete force stop）。
- Share Privacy: 无 Electron proof → start 拒绝；web fail-closed；桌面端验证见真机 Runtime。
- Human Coach: 默认最小权限（transcript/ai_cue OFF、session_context ON、LAN OFF）契约匹配；cue 审计 `is_evidence=false`/HUMAN_COACH；End/Delete revoke；过期 token 拒绝。
- Connectors: 空 registry fail-closed；未知/写 capability 拒绝（WRITE_REQUIRES_EXPLICIT_EXECUTION_FLOW）；synthetic provider 精确 grant 冻结在 Pack。
- DraftActions: DRAFT→APPROVE/DISMISS；APPROVED 后 `external_execution=false`。
- Reminders: 未来排程会话 opt-in 列表稳定（3/3/3/3/3），restart 持久化；点击只进对应 Space Prepare；不泄露标题/转写/参与者；无 calendar 声明。
- Export/Delete/Retention: export 11 类目显式分离；Delete Session→tombstone；Delete Space 需显式确认；MINIMUM/STANDARD 保留 confirmed truth/Pack/tombstones。
- Search/Diagnostics: 结果带 Space/Session/time/review/source；无 unsourced AI 答案；Diagnostics 与 runtime 一致（本地工程项，不声称 PMF）。

## Windows Desktop Runtime（真机）
- 发现并修复 **P1**：打包应用启动即崩溃（Electron “Error” 对话框）——`main.js` 顶层 `require('./overlayLayout')` 但 `desktop/package.json build.files` 漏列 `overlayLayout.js`。**该缺陷同样存在于已发布 v2.0.0-beta.2 打包包**（其发布窗口证据走了 web fallback 被掩盖）。
- 修复后验证：窗口标题「成竹」、backend sidecar 监听 18080、userData layout 建立、关闭后 0 残留进程；发布管线窗口证据 harness **46 张真实 BrowserWindow 截图 PASS**。

## Packaged Candidate
- 基于当前 main（非 beta.2）本地构建 installer + portable；SHA256/size/source SHA/build timestamp 见 `16-packaged/candidate-manifest.txt`。
- 判定: **LOCAL_PACKAGED_CANDIDATE = READY_FOR_DOGFOOD**（不是 READY_FOR_STABLE_RELEASE）。

## Bugs（详见 BUGS_FOUND_AND_FIXED.md）
- P1×1（打包启动崩溃）— 已修 + 回归测试 + 真机验证
- P2×1（Delivery cue 用活表达而非冻结 Pack 表达）— 已修 + 回归测试 + 全量回归
- 测试基建×1（conftest 环境泄漏开发者 STT 凭据）— 已修，backed by 全量回归
- P3 观察：E2E 一处时序 flake（retry 通过），记录未修。

## Blocked External（精确原因）
- 真实 LLM provider 质量评测：无 `CHENGZHU_EVAL_API_KEY`。
- 真人语音/真实会议/真实用户 pilot：本机无真人参与者与授权（Human Eval 工具链已验证其正确拒绝路径）。
- GitHub Releases API 核验（Latest/Prerelease 资产）：未认证凭据；本地已用 git tags 核验 v1.4.2/v2.0.0-beta.2 存在且 SHA 匹配。
- Soak 中 audio switching / sleep-wake / real network loss：按脚本声明 BLOCKED_EXTERNAL。
- 真人视觉验收（human_visual_acceptance）：按打包证据契约显式 false。

## Final Verdict
```
LOCAL_FULL_SIMULATION = GO
ENGINEERING_RUNTIME_CONFIDENCE = HIGH
REAL_USER_EVIDENCE_PENDING = TRUE
（未声明 V2_STABLE_RELEASE / REAL_USER_VALIDATED / PMF_PROVEN / PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW）
```
