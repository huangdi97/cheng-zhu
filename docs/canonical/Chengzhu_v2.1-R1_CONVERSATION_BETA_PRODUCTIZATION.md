# 成竹 Chengzhu v2.1-R1
## Conversation Beta Productization｜Packaged Evidence / Dogfood / Human Labels
**日期**：2026-10-07  
**状态**：CANONICAL BETA PRODUCTIZATION  
**继承**：v2.0-R1 Personal Conversation Intelligence；不重定义 v2.0 truth model / Session Pack / Guidance Arbiter  
**稳定发布基线**：v1.4.2 Interview  
**当前目标**：把已存在的 Conversation runtime 从“源码/CI 可运行”推进到“可打包重放、可本地 dogfood、可积累人工评测样本”的 Beta Candidate。

---

# 0. 状态边界

v2.1 新增的状态层：

```text
V2_DESIGN_COMPLETE = TRUE
V2_RUNTIME_AVAILABLE = TRUE
V21_BETA_PRODUCTIZATION = IN_PROGRESS
V21_PACKAGED_CONVERSATION_EVIDENCE = PENDING_UNTIL_GATE
V2_PRODUCTIZED_RELEASE = FALSE
REAL_CONVERSATION_USER_EVIDENCE_PENDING = TRUE
PMF_PROVEN = FALSE
```

任何 PR CI、packaged smoke、synthetic dogfood、截图、点击率都不能把最后两项改为 TRUE。

---

# 1. 为什么需要 v2.1

v2.0 已经完成：

- Profile-aware Conversation runtime；
- Space continuity；
- Prepare / Preflight / Frozen Session Pack；
- Live Guidance + SILENT；
- source-aware Manual Ask；
- Counterparty / Expression；
- Conversation-owned transcript；
- Continue / Decisions / Open Threads；
- reviewed local write-back drafts；
- privacy fail-closed；
- retention / export / deletion provenance。

剩余问题已经不是“对象没设计”，而是：

1. packaged Windows 路径是否真的跑同一套 Conversation；
2. Beta dogfood 是否能记录“提示有用/错/打断/太晚”等人工标签；
3. 是否能记录“本该提示但没提示”；
4. 是否能区分 telemetry proxy 与 human-labeled evidence；
5. 是否有可下载、可审计、可重复的 CI / packaged evidence；
6. 是否能在不宣称 PMF 的前提下进入小规模真实使用。

---

# 2. v2.1 三条主线

## A. Packaged Truth

必须证明打包后的 sidecar / frontend，而不是 source dev server：

```text
Space
→ Preflight
→ Start
→ Guidance
→ Human Label
→ End
→ Session Outcome Label
→ Evaluation Export
→ Restart
→ Persistence
```

同时 packaged UI evidence 必须出现：

- Conversation Home；
- Space；
- Prepare；
- Preflight；
- Live；
- frozen Session Pulse；
- Guidance；
- dogfood label；
- Continue；
- Conversation History；
- 390px Prepare。

BrowserWindow 是首选证据。Hosted Windows runner 无交互桌面时允许 packaged-sidecar + packaged-frontend Chromium fallback，但 manifest 必须明确说明 BrowserWindow 被环境阻断，不得冒充 Electron evidence。

---

# 3. Dogfood Human Label Ledger

## 3.1 为什么不能只看 PIN / Dismiss / Used

这些是交互 telemetry：

- PINNED；
- DISMISSED；
- USED；
- EXPANDED。

它们不能回答：

- 内容是否正确；
- 来源是否正确；
- 是否打断；
- 是否太早/太晚；
- 本该提醒却没提醒；
- Continue 是否真的帮助下一次准备。

因此 v2.1 使用独立 `conversation_feedback_event` ledger。

## 3.2 Guidance Quality labels

允许：

- USEFUL；
- NOT_USEFUL；
- WRONG；
- SOURCE_WRONG；
- INTERRUPTING；
- TOO_EARLY；
- TOO_LATE；
- ALREADY_KNEW。

同一 Guidance 可有多个 label，例如：

```text
USEFUL + TOO_LATE
```

这是合法的，不应被压缩成一个单选满意度。

## 3.3 Missed Moment labels

允许：

- SHOULD_HAVE_RECALLED；
- SHOULD_HAVE_WARNED_RISK；
- SHOULD_HAVE_ASKED；
- SHOULD_HAVE_SURFACED_SOURCE；
- OTHER。

Missed Moment 是后续计算 recall/regret 的必要负样本来源。

## 3.4 Session Outcome labels

允许：

- CONTINUE_HELPED_NEXT_PREP；
- CONTINUE_PARTLY_HELPED；
- CONTINUE_DID_NOT_HELP；
- WOULD_REUSE_SPACE；
- WOULD_NOT_REUSE_SPACE。

Session Outcome 只能在 Session ENDED 后记录。

---

# 4. Feedback 不得改变 Conversation Truth

`conversation_feedback_event`：

- 不改变 Decision；
- 不改变 Commitment；
- 不改变 Open Thread；
- 不自动改变 Guidance model/policy；
- 不把 dogfood 反馈提升成长期个人事实；
- 不作为 Counterparty truth；
- 不自动发往服务器。

Feedback 是 evaluation evidence，不是 product truth。

---

# 5. Feedback Provenance

每条 Guidance feedback 冻结：

- guidance_id；
- guidance kind；
- expression action；
- reason；
- shown text；
- current user_action；
- source refs；
- local timestamp。

每条 Missed Moment 冻结：

- session_id；
- current topic；
- profile；
- assistance mode；
- source refs（如用户提供）；
- local timestamp。

每条 Session Outcome 冻结：

- profile；
- capture / processing / assistance mode；
- session status；
- local timestamp。

---

# 6. Retention / Delete / Privacy

默认：

```text
feedback storage = LOCAL_PRODUCT_DB
remote feedback telemetry = OFF
```

Guidance retention 删除 Guidance 时：

- feedback event 保留；
- guidance_id 变为 null；
- frozen feedback context / source refs 仍可用于评测。

原因：否则“删 30 天 Guidance”会把长期 dogfood label 一起静默抹掉。

但：

- 删除 Session → feedback cascade 删除；
- 删除 Space → feedback cascade 删除。

用户删除权优先于评测完整性。

Retention Preview 必须写清：

```text
dogfood_feedback = KEEP_UNTIL_SESSION_OR_SPACE_DELETE
```

---

# 7. Evaluation Export

新增本地：

```text
CONVERSATION_BETA_EVALUATION_EXPORT
contract = v2.1-R1
```

必须包含：

- scope；
- evidence boundary；
- feedback event counts；
- label counts；
- raw local feedback events。

必须明确：

```text
human_labels = true
remote_telemetry = false
synthetic_or_dogfood_labels_are_not_pmf = true
```

---

# 8. Diagnostics

Diagnostics 分三层：

## Observed proxies
- source attribution coverage；
- adoption；
- dismissal；
- suppression；
- duplicate suppression；
- review queue；
- approved draft rate。

## Explicit human-label ledger
- guidance labels；
- useful；
- wrong/source wrong；
- interrupting；
- missed moments；
- session outcomes。

## Still requires labeled study
- Recall Precision；
- Opportunity Precision；
- Interruption Regret；
- Useful Silence；
- real cross-session value；
- real cognitive load。

即使 human labels 已存在，单纯的 count 也不自动等于这些指标。

---

# 9. Source CI Evidence Gate

每个 v2.1 PR 必须生成：

```text
artifacts/validation/v2.1-conversation-beta/
  v2.1-conversation-beta-engineering.json
  V2_1_CONVERSATION_BETA_ENGINEERING.md
```

Evidence type：

```text
SYNTHETIC_CONVERSATION_BETA_ENGINEERING
```

至少证明：

- schema v6；
- Preflight clear；
- Session Pack frozen；
- Guidance shown；
- guidance labels；
- missed moment；
- session outcome；
- local-only evaluation export；
- retention keeps feedback；
- feedback detaches safely after Guidance deletion；
- diagnostics human-label boundary；
- real-user evidence pending；
- PMF false。

---

# 10. Packaged Sidecar Smoke Gate

`scripts/packaged_smoke.py` 必须在真实构建的 sidecar 上验证：

1. Conversation Space；
2. Notes-only Local Session；
3. Preflight；
4. Start；
5. Guidance；
6. Guidance human label；
7. Missed Moment；
8. End；
9. Session Outcome；
10. evaluation export；
11. product.db schema；
12. sidecar restart；
13. feedback persists；
14. Conversation History persists；
15. install dir remains clean。

---

# 11. Packaged UI Evidence Gate

BrowserWindow 路径至少增加：

- Conversation Home；
- Conversation Space；
- Prepare；
- Preflight；
- Live Guidance；
- local human label；
- Continue；
- History；
- 390px Prepare。

当前最低总 capture gate：

```text
real BrowserWindow >= 45 captures
fallback packaged Chromium >= 38 captures
```

这些数字是当前 artifact gate，不是未来产品 UI 固定页数。

---

# 12. Beta Onboarding

第一次使用 Conversation Beta 建议：

1. Project Sync / Design Review；
2. 1–3 个明确来源；
3. Notes Only；
4. Local；
5. Balanced；
6. 一场低风险真实对话；
7. 会中只在确实有感受时打人工 label；
8. 会后确认 Decision / Commitment / Open Thread；
9. 下一场观察 continuity。

不要为了“收数据”要求用户每条 Guidance 都标注。

---

# 13. Dogfood Study 最低协议

真实 dogfood 每场至少允许记录：

- shown Guidance；
- useful / wrong / interrupting / too late；
- Missed Moments；
- Continue helpfulness；
- reuse same Space intent。

计算 Precision/Regret 前还需要：

- 明确采样规则；
- 至少一部分完整 Session 被人工回看；
- missed intervention 的负样本；
- 来源正确性标注；
- 定义哪些场景应该 SILENT。

不能只抽样用户点击过的 Guidance，否则会有 selection bias。

---

# 14. Beta Candidate Gate

PR 合并前：

- backend full suite；
- frontend typecheck/unit/build；
- Playwright；
- visual；
- real-backend smoke；
- Windows packaged smoke；
- schema/migration；
- v2.1 evidence artifact；
- Interview regression 全绿。

合并后：

- main CI 绿；
- packaged runtime UI evidence 可重放；
- Conversation evidence manifest 存在。

只有此时允许：

```text
V21_BETA_ENGINEERING_COMPLETE = TRUE
V21_PACKAGED_BETA_CANDIDATE = TRUE
```

仍不允许：

```text
V2_PRODUCTIZED_RELEASE = TRUE
REAL_USER_VALIDATED = TRUE
PMF_PROVEN = TRUE
```

---

# 15. Stable v2 Release Gate

稳定 v2 发布仍需：

- exact main SHA；
- installer / portable；
- Conversation packaged runtime UI evidence；
- clean installer replay；
- installed-layout smoke；
- download-back；
- SHA256；
- tag/source provenance；
- public README screenshot truth；
- no critical Conversation blocker。

即使完成 stable v2 release：

```text
REAL_USER_VALIDATED
PMF_PROVEN
```

仍由真实研究决定。

---

# 16. 当前不进入 v2.1 的能力

继续保持 blocked / fail-closed：

- Conversation Screen Context；
- Conversation Human Coach；
- Conversation Private Overlay；
- Calendar / Docs / Mail / project tracker connectors；
- actual external write-back；
- organization/shared registry。

v2.1 不用这些能力来换取“看起来更完整”。

---

# 17. v2.1 完成定义

本阶段代码完成需要同时满足：

- schema v6 feedback ledger；
- domain/API/contracts；
- Live Guidance human labels；
- Missed Moment UI；
- Session Outcome UI；
- diagnostics / export / retention / delete semantics；
- backend tests；
- browser E2E；
- deterministic evidence script + CI artifact；
- packaged sidecar Conversation smoke；
- packaged BrowserWindow/fallback Conversation UI evidence；
- DEVELOPMENT / RELEASE / README truth 同步；
- PR CI 全绿。

这叫：

> **Conversation Beta Productization Engineering Complete**

不叫：

> “真实用户价值已证明”。
