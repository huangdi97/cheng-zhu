# 成竹 Chengzhu v2.0.0-beta.2

## 这是什么版本

v2.0.0-beta.2 是 **Personal Conversation Intelligence** 的第二个 Windows Beta 发布候选，直接从 2026-10-08 最新 main 构建。

它不会取代当前稳定版 v1.4.2。GitHub Release 必须保持：

```text
prerelease = true
latest = false
```

因此：

- v1.4.2 继续作为 Stable / GitHub Latest；
- v2.0.0-beta.2 是 Conversation Beta 的最新可安装候选；
- Beta 通过工程与发布门禁，不等于 stable v2；
- Beta 也不等于真实用户价值或 PMF 已验证。

---

## 相比 beta.1 候选的主要变化

### 1. 六类 Conversation Profile 已有 frozen Playbook

Project Sync / Design Review / Presentation-QA / 1:1 / Client Call / Negotiation 不再只是 label 或默认模式不同。

每个 Profile 的 Playbook 会冻结：

- success conditions；
- priority truth types；
- Prepare prompts；
- Guidance boundaries；
- closing objective。

并贯穿：

```text
Template Picker
→ Prepare
→ Session Pack
→ Live
→ Continue
```

Session 开始后模板再变化，也不会静默改写本场。

### 2. Expression Plan 已成为可审计 runtime read model

每一条 shown / SILENT Guidance 都可以解释：

- action；
- guidance kind；
- target participant；
- text；
- source refs；
- warnings；
- render mode；
- suppression reasons。

Expression Plan 是从已持久化 Guidance 派生出的只读解释层，不是第二套 truth store。

### 3. Conversation Screen Context 已从 MANUAL 扩展到 explicit-start AUTO

MANUAL：

- 用户每次主动抓取一次；
- raw screenshot 不落库；
- 只保存 observation text + image hash + model/route provenance；
- observation = OBSERVED_NOT_CONFIRMED。

AUTO：

- policy 允许 AUTO 不代表自动启动；
- 进入 Live 后必须二次显式启动；
- 显示 ACTIVE / OFF THE RECORD / AUTO STOPPED；
- 支持 pause / resume / stop；
- duplicate-frame suppression；
- rate limit；
- bounded error fail-stop；
- Session end/delete/Space erase 强制停止；
- LOCAL processing 下 remote vision fail-closed；
- frozen vision fingerprint 变化时拒绝静默切换。

### 4. Conversation Share Privacy 已有真实桌面 runtime

`PRIVATE_OVERLAY` 不再只是 policy 字段。

开始 Session 前必须：

1. 由 Electron bridge 启用 content protection；
2. 回读实际 BrowserWindow content-protection flags；
3. 把验证 proof 交给 backend；
4. proof 不成立则 fail-closed。

Live 会持续显示实际保护状态；Session 结束后恢复会话前全局默认。

该能力只是 **best-effort window content protection**，不能解释为：

- 安全隔离；
- 屏幕共享绝对不可见；
- “不可检测”；
- anti-proctoring / stealth。

### 5. Conversation Human Coach 已进入 session-scoped runtime

只有本场 frozen policy = `HUMAN_ALLOWED` 且记录 participant transparency plan 时才允许显式创建。

Human Coach：

- 必须绑定一个明确 Conversation Session；
- link/token 一次性展示、TTL-bound、可 revoke；
- 默认 local-only，不自动公开暴露；
- 权限按字段授权 transcript / AI Guidance / frozen Session Context；
- Conversation helper 不读取 Interview Resume/JD；
- policy 在每次 cue 前重新读取；
- Session end/delete/Space erase 自动 revoke；
- advice 进入 `conversation_guidance_event(kind=HUMAN_COACH)` 审计；
- source 标记 `is_evidence=false`；
- 不进入 Conversation Item truth / memory / extraction；
- 不允许 remote keyboard / mouse control；
- 不承诺 stealth / anti-proctoring / bypass。

### 6. Conversation truth / continuity 进一步收口

当前 main 已包含：

- reviewed longitudinal Open Threads；
- derived Conversation State；
- atomic Decision supersession；
- schema v6 temporal provenance / Deadline disambiguation；
- schema v7 Screen Context provenance；
- frozen Ready-source Manual Ask；
- source visibility / suggestion budget / SILENT；
- global grounded Conversation search；
- current Session / Space categorized local export；
- local reviewed Follow-up / Task / Issue / Decision Log drafts；
- human-label evaluation tooling。

### 7. Packaged 与 runtime truth 更严格

Beta release gate 已要求：

- full backend/frontend/desktop test suite；
- Playwright functional；
- visual regression；
- real-backend smoke；
- Windows packaged smoke；
- Conversation packaged UI evidence；
- independent packaged screenshots；
- unobstructed-surface assertion；
- clean installer replay；
- installed-layout smoke；
- SHA256；
- draft Release download-back；
- downloaded installer replay；
- exact source/tag provenance。

---

## Conversation Beta 主循环

```text
Conversation Home
→ Space
→ Next Focus
→ Prepare
→ Preflight
→ Frozen Session Pack
→ Participate
→ Continue
→ same Space
```

核心差异仍然不是“会议纪要”或“实时卡片”，而是：

```text
Contribution Opportunity
+ Provenance-aware Continuity
+ Stakeholder-aware Expression
+ Silence / Interruption Control
+ Review-first Truth Promotion
```

---

## Privacy / truth boundary

Preflight 与 Session Pack 会冻结：

- Capture / Processing；
- STT / inference / retention / write-back data path；
- participant consent status（用户报告）；
- participant transparency plan（用户报告）；
- selected sources / Quick Notes；
- Screen Context policy；
- AI / Human Assistance；
- Share Privacy；
- connector permissions；
- Expression Profile；
- resolved runtime proof。

原则：

```text
UI policy
must match
actual runtime path
```

如果无法证明一致，fail-closed。

---

## 仍然明确未完成 / 不宣称

beta.2 不伪装以下能力已经真实完成：

- Calendar / Docs / Mail / project tracker 外部 connector；
- actual external email/task/issue/decision-log execution；
- participant automatic chat notice / watermark；
- Organization / shared team truth registry；
- code signing；
- macOS signing/notarization；
- stable v2 release；
- real-user value / PMF。

当前 reviewed DraftAction 的 `APPROVED` 只表示**本地草稿经过用户审核**，不代表外部系统已经执行。

---

## 真实用户边界

仍然：

```text
REAL_CONVERSATION_USER_EVIDENCE_PENDING = TRUE
PMF_PROVEN = FALSE
```

工程 evidence 可以证明：

- 可安装；
- 可重放；
- provenance / privacy / continuity 约束成立；
- packaged runtime 与源码一致；
- human-label tooling 可用。

它不能证明：

- Opportunity Precision 已满足真实使用；
- Interruption Regret 足够低；
- Useful Silence 已被真人验证；
- cognitive load 已下降；
- real cross-session value 已成立；
- PMF 成立。

第一批真实 dogfood / user study 仍优先：

- Project Sync；
- Design Review。

---

## Release channel

```text
Stable Latest = v1.4.2
Beta Candidate = v2.0.0-beta.2
Stable v2 = NOT CLAIMED
```

beta.2 必须发布为 GitHub **Prerelease**，不得成为 Stable Latest。

## License

MIT。第三方组件保留各自许可证，详见 `THIRD_PARTY_NOTICES.md`。
