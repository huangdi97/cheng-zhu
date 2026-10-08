# 成竹 Chengzhu v2.0.0-beta.1

## 这是什么版本

v2.0.0-beta.1 是 **Personal Conversation Intelligence** 的首个公开 Windows Beta 候选。

它不会取代当前稳定版 v1.4.2。GitHub Release 必须发布为：

```text
prerelease = true
latest = false
```

因此：

- v1.4.2 继续作为 Stable / GitHub Latest；
- v2.0.0-beta.1 作为可下载、可审计、可回滚的 Conversation Beta；
- Beta 发布本身不等于真实用户价值已验证。

---

## v2 的产品变化

成竹从 Interview-first 单一工作流扩展为一个 Core 下的双 Profile：

```text
Interview
Conversation
```

Conversation Profile 的主循环是：

```text
Conversation Home
→ Space
→ Next Focus
→ Prepare
→ Preflight
→ Frozen Session Pack
→ Participate
→ Continue
→ Next Focus
→ same Space
```

首发验证楔子：

- Project Sync；
- Design Review。

共享 runtime 模板：

- Presentation / Q&A；
- 1:1；
- Client Call；
- Negotiation。

模板能运行不等于其专属行为已经完成真实用户验证。

---

## Conversation Beta 已有能力

### Personal Continuity

- Conversation Space；
- Goal；
- Session；
- History；
- reviewed Decision / Commitment / Task / Deadline / Open Question / Risk / Objection；
- longitudinal Open Threads；
- derived Conversation State；
- supersession；
- provenance tombstones。

### Frozen Session Pack

每场开始时冻结：

- Goal；
- Ready material version；
- skipped / unready source；
- Quick Notes；
- confirmed Conversation Items；
- reviewed Open Threads；
- participants / explicit Counterparty State；
- Expression Profile；
- Session Policy；
- retention；
- capture / processing / assistance；
- resolved data path；
- Prepare brief；
- digest。

会中不会因 Space、资料或表达偏好后来改变而静默改写本场上下文。

### Live Guidance

真实 TRANSCRIPT 可以驱动：

- Direct Question → Answer Cue；
- Critical Risk；
- reviewed/frozen Recall；
- Ready-source Contribution Opportunity；
- profile-allowed Talking Point / Question；
- Delivery；
- SILENT。

Arbiter 支持：

- 一个 primary Guidance；
- Direct Question 抢占 stale proactive card；
- SELF_MIC 不自动打断；
- source visibility；
- duplicate suppression；
- suggestion budget；
- social / stale risk；
- explicit stakeholder context；
- newest SILENT 不允许被轮询“复活”为旧卡。

### Provenance-aware Manual Ask

检索优先级：

```text
confirmed truth
> frozen Ready source
> frozen Quick Note
> current-session transcript
```

结果明确区分：

- CONFIRMED_TRUTH；
- PERSONAL_EVIDENCE；
- REFERENCE_SOURCE；
- USER_NOTE_NOT_EVIDENCE；
- OBSERVED_NOT_CONFIRMED。

数字、版本号、比例等判别 token 使用精度保护，避免“50x”靠“data scale”泛词误命中冻结的“10x”。

### Counterparty / Expression

可长期保存的只有明确、可追溯的信息：

- role；
- explicit priority；
- explicit concern；
- stated position；
- decision authority；
- relationship context；
- source；
- confidence。

不把 emotion / personality / hidden intent / secret bottom line 事实化。

### Privacy / Preflight

Preflight 会显示并冻结：

- Capture Mode；
- Processing Mode；
- transcript retention；
- participant consent status（用户报告）；
- participant transparency plan（用户报告）；
- sources / Quick Notes；
- connector permissions；
- Screen Context；
- AI / Human Assistance；
- Share Privacy；
- external write-back；
- resolved data path。

Local policy 与真实 runtime 不一致时 fail-closed。

### Conversation-owned Manual Screen Context

schema v7 支持手动 Screen Context：

- 每次由用户显式触发；
- raw screenshot 不进入 product.db；
- 仅保留 observation text + image/model-route provenance；
- observation 是 OBSERVED_NOT_CONFIRMED；
- LOCAL processing 下 remote vision route fail-closed；
- vision fingerprint 在本场变化时拒绝静默切换。

### Continue / Review-first Write-back

Continue 包含：

- What changed；
- Pins；
- reviewed truth；
- Review Queue；
- Next Focus；
- Follow-up Draft；
- Task Draft；
- Issue Draft；
- Decision Log Draft。

`APPROVED` 只代表本地草稿已由用户审核，不代表外部系统已经执行。

### Search / Export / Evaluation

- grounded global Conversation search；
- Ctrl+K 查 Decision / Commitment / Open Question；
- current Session 分类化 local export；
- privacy-bounded human-label tooling；
- observed telemetry proxy 与 human-label metrics 分离；
- human labels / source annotations 不允许被 seed/export 静默覆盖。

---

## Windows Beta 工程证据

发布 gate 继续要求：

- backend full suite；
- frontend typecheck / unit / build；
- desktop tests；
- functional Playwright；
- visual regression；
- real-backend smoke；
- Windows packaged smoke；
- Conversation packaged UI evidence；
- independent Conversation screenshot evidence；
- clean installer replay；
- installed-layout smoke；
- SHA256；
- draft Release download-back；
- downloaded installer replay；
- exact source/tag provenance。

Beta 使用与 stable 相同的 release provenance 不变量：

```text
green main CI SHA
==
release checkout SHA
==
binary source SHA
==
public tag SHA
```

---

## 当前仍明确不宣称完成

v2.0.0-beta.1 不伪装以下能力已完成：

- Conversation AUTO Screen Context；
- Conversation Human Coach；
- Conversation Private Overlay；
- Calendar / Docs / Mail / project-tracker connector runtime；
- actual external email/task/issue/decision-log execution；
- participant auto chat notice / watermark；
- organization/shared team truth registry。

---

## 真实用户边界

当前仍然：

```text
REAL_CONVERSATION_USER_EVIDENCE_PENDING = TRUE
PMF_PROVEN = FALSE
```

Beta 可以证明：

- 可安装；
- 可重放；
- packaged runtime 与源码设计一致；
- privacy/provenance/continuity 工程边界可验证；
- 本地 dogfood 与人工标注工具可用。

Beta 不能证明：

- Opportunity Precision 已满足真实使用；
- Interruption Regret 足够低；
- Useful Silence 已验证；
- real cross-session value 已验证；
- cognitive load 已下降；
- PMF 成立。

第一批真实使用仍应优先 Project Sync / Design Review。

---

## Release channel

v2.0.0-beta.1 必须发布为 GitHub **Prerelease**，且不得成为 Stable Latest。

当前 Stable：

```text
v1.4.2
```

当前 Beta：

```text
v2.0.0-beta.1
```

## License

MIT。第三方组件保留各自许可证，详见 `THIRD_PARTY_NOTICES.md`。
