# Chengzhu v2.0-R1 Design → Runtime Closure Matrix

> 日期：2026-10-07  
> 分支：`feat/chengzhu-v2-conversation-design-closure`  
> PR：#19  
> Canonical：`Chengzhu_v2.0-R1_PERSONAL_CONVERSATION_INTELLIGENCE.md`  
> 目标：证明“设计完成”对应真实 runtime / UI / tests / evidence，而不是只有文档、字段、数据库表或 mock。

---

## 0. 状态语义

本矩阵严格区分：

```text
DESIGN_COMPLETE
CONTRACT_COMPLETE
RUNTIME_AVAILABLE
ENGINEERING_EVIDENCE
PRODUCTIZED_RELEASE
REAL_USER_VALIDATED
```

当前允许声明：

```text
V2_DESIGN_COMPLETE = TRUE
V2_CONTRACT_COMPLETE = TRUE
V2_RUNTIME_AVAILABLE = TRUE
V2_PRODUCTIZED_RELEASE = FALSE
REAL_CONVERSATION_USER_EVIDENCE_PENDING = TRUE
PMF_PROVEN = FALSE
```

`RUNTIME_AVAILABLE` 只说明存在真实 route / persistence / UI / runtime path；不等于 Windows v2 stable release，也不等于真实用户价值已经验证。

---

# 1. 产品主循环

| 设计对象 | Runtime / UI | 关键证据 | 当前状态 |
| --- | --- | --- | --- |
| Profile Switcher | Interview / Conversation 双 Profile shell | `frontend/src/App.tsx` + v2 Playwright | RUNTIME_AVAILABLE |
| Conversation Home | Next Session / Next Focus / owed / reviewed open questions / recent change | `home_summary()` + Conversation Home E2E | RUNTIME_AVAILABLE |
| Conversation Space | Overview / Prepare / Sessions / Decisions | `ConversationSpacePage.tsx` | RUNTIME_AVAILABLE |
| Prepare | Brief / Agenda / expected questions / sources / Quick Notes / reviewed continuity | `prepare_space()` | RUNTIME_AVAILABLE |
| Preflight | policy + resolved data path + Pack Preview + blockers/warnings | `preflight()` + E2E | RUNTIME_AVAILABLE |
| Participate | Guidance-first Live + transcript + Session Pulse + Manual Ask | `ConversationLivePage.tsx` | RUNTIME_AVAILABLE |
| Continue | What changed / Pins / Review Queue / Next Focus / DraftAction | `continue_summary()` | RUNTIME_AVAILABLE |
| History | Conversation-only history，不回 Interview History | `ConversationHistoryPage.tsx` | RUNTIME_AVAILABLE |

冻结主循环：

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

没有新增 Project Sync / Design Review / 1:1 / Client Call 等一级导航；它们仍是 Space template。

---

# 2. Goal / Space / Session 生命周期

| 能力 | 真值实现 | 规则 |
| --- | --- | --- |
| Conversation Goal | `conversation_goal` + create/update | ACTIVE / RESOLVED |
| 自动带入 Goal | Session 创建时默认捕获 ACTIVE Goal ids | 已开始 Session 不被后续 Goal 变化重写 |
| 人工排期 | UPCOMING Session 支持 `scheduled_at` | 不伪装 Calendar connector |
| Space archive | ACTIVE / ARCHIVED | 不删除历史 provenance |
| Space complete erase | 显式 confirm 后 cascade erase | 和 Session tombstone 语义明确区分 |
| Session delete | reviewed truth 需要 TOMBSTONE | 删除后 tombstone 不再参与 Recall |
| Retention | transcript / guidance / draft 分类预览与删除 | confirmed items / Packs / tombstones 不被 retention 静默删 |

---

# 3. Frozen Session Pack

Session 开始时冻结的不是“一个 prompt”，而是可审计输入快照。

真实 Pack 包含：

- Space identity；
- Goal ids；
- Ready material version；
- skipped/unready source；
- Quick Notes；
- confirmed Conversation Items；
- reviewed Open Threads；
- participants / explicit Counterparty State；
- Expression Profile；
- Session Policy；
- capture / processing / assistance mode；
- consent acknowledgement；
- retention policy；
- resolved processing runtime / data path；
- Prepare session brief；
- digest。

已证明的时间一致性：

1. material 在 Session 开始后被 replacement，不改变旧 Session 的 frozen version；
2. Space goal / source 变化不重写已开始 Session；
3. reviewed Open Thread 在 Session 开始后被 resolve，也不重写本场 Pack；
4. Live `Session Pulse` 读取 frozen context，而不是重新读取 mutable Space truth。

---

# 4. Truth / Provenance Model

一等 Conversation Item：

```text
Decision
Commitment
Task
Deadline
Risk
Assumption
OpenQuestion
Proposal
Objection
Metric
Status
```

状态：

```text
PROPOSED
AGREED
COMMITTED
DONE
SUPERSEDED
UNKNOWN
```

审核：

```text
AI_EXTRACTED
USER_CONFIRMED
USER_EDITED
USER_REJECTED
SOURCE_CONFIRMED
```

硬门禁已经进入 runtime + tests：

| 规则 | 实现状态 |
| --- | --- |
| transcript segment 只是 source，不是真值 | ENFORCED |
| AI transcript extraction 默认 PROPOSED + AI_EXTRACTED | ENFORCED |
| Decision → AGREED 需要 provenance + review | ENFORCED |
| Commitment / Task → COMMITTED 需要 owner + provenance + review | ENFORCED |
| 未知 owner 不自动写成 me | ENFORCED |
| Deadline 必须带 source | ENFORCED |
| Decision supersession 是 NEW → OLD，旧 Decision 保留为 SUPERSEDED | ENFORCED |
| Quick Note 可检索但不自动升级成 evidence | ENFORCED |
| 删除 reviewed truth 的 Session 先保留 tombstone | ENFORCED |
| tombstone 不继续作为未来 Recall memory | ENFORCED |

---

# 5. Longitudinal Open Threads

`conversation_open_thread` 不再是“有表无语义”。

当前规则：

```text
AI_EXTRACTED OpenQuestion / Risk / Objection
→ 不进入长期 Thread

USER_CONFIRMED / USER_EDITED / SOURCE_CONFIRMED
+ unresolved
→ 投影为 OPEN longitudinal thread

RESOLVE / REJECT / DONE / SUPERSEDED / UNKNOWN
→ 不再作为 OPEN continuity
```

Thread 是 read-model projection，不替代 Conversation Item truth。

额外边界：

- thread 带回原 Conversation Item 与 source refs；
- Prepare / Overview 使用 reviewed Open Threads；
- 新 Session Pack 显式冻结 reviewed Open Threads；
- Live Session Pulse 显示 frozen Open Threads；
- Session 开始后 Thread 被 resolve，不改写已经开始的 Pack；
- 删除来源 Session 时移除派生 Thread projection，避免 phantom continuity；
- tombstone 保留删除 provenance，但不会留下可行动的幽灵 Thread。

---

# 6. Manual Ask / Context Retrieval

Manual Ask 的来源排序：

```text
confirmed cross-session state
> frozen Ready source version
> frozen Quick Note
> current-session transcript
```

每个结果显式带 authority：

- `CONFIRMED_TRUTH`
- `PERSONAL_EVIDENCE`
- `REFERENCE_SOURCE`
- `USER_NOTE_NOT_EVIDENCE`
- `OBSERVED_NOT_CONFIRMED`

已收口：

- started Session 只查询 frozen material version；
- material replacement 不静默刷新本场；
- 数字 / 版本 / 比例等 distinctive token 不允许靠泛词重合伪 grounded；
- AI Assistance = FORBIDDEN 时 Manual Ask 无旁路；
- current transcript 可作为观察上下文，但不自动升级为 confirmed truth。

Manual Ask 是 baseline capability，不作为产品核心差异声明。

---

# 7. Live Guidance / Expression

当前真实优先级：

```text
Direct Question / Answer Cue
> Critical Risk
> reviewed/frozen Recall or Contribution Opportunity
> profile-allowed Talking Point / Question
> Delivery
> SILENT
```

已实现并测试：

- PRIMARY_AUDIO direct-question detection；
- Quiet 模式仍允许 Direct Question；
- SELF_MIC 不自动弹 proactive Guidance；
- frozen confirmed truth → Recall；
- frozen Ready source → Contribution Opportunity；
- Quick Note / current transcript 不自动抬成 proactive factual suggestion；
- user speaking → SILENT；
- duplicate suppression；
- suggestion budget；
- source visibility；
- social-risk suppression；
- Direct Question 取消尚未处理的 stale proactive card；
- Profile-specific Guidance allowlist；
- Stakeholder-aware Expression 只使用 explicit role / priority / concern / authority / relationship context；
- Delivery cue 使用 Expression Profile；
- 任意时刻一个 primary Guidance。

高级手工 Guidance 注入被降级为 dogfood / verification surface，不作为普通用户主路径。

---

# 8. Transcript → Review Queue

真实转写不会直接制造长期组织事实。

```text
final transcript
→ conservative explicit-language extraction
→ PROPOSED + AI_EXTRACTED
→ Continue Review Queue
→ user confirm/edit/reject
→ only then long-term truth / continuity
```

当前 deterministic beta 可提取显式：

- OpenQuestion；
- Decision candidate；
- Commitment candidate；
- Deadline candidate；
- Risk candidate。

这只是工程可验证的 review-first extraction，不宣称 model extraction recall/precision 已被真实用户验证。

---

# 9. Counterparty / Stakeholder State

允许持久化：

- role；
- explicit priority；
- explicit concern；
- stated position；
- decision authority；
- relationship context；
- source refs；
- confidence。

UI 明确显示：

```text
Known / Explicit
Inferred / Temporary
Unknown
```

禁止事实化：

- emotion；
- sentiment；
- personality；
- hidden intent；
- “他其实想……”；
- “他不信任你……”；
- negotiation hidden bottom line。

Counterparty State 可人工新增、修正；frozen into Session Pack。

---

# 10. Privacy / Consent / Transparency

Session Policy 已进入真实 runtime，不只是文档：

- capture mode；
- processing mode；
- transcript retention；
- AI assistance；
- Human assistance；
- screen context；
- share privacy；
- external write-back；
- participant consent status（user report）；
- participant transparency plan（user report）；
- connector permissions。

透明性严格区分：

```text
user says current use is allowed
!=
user reports participants consented
!=
user plans to notify participants
!=
system verified consent
!=
system automatically notified participants
```

当前没有 Conversation chat-notice / watermark runtime，因此不会伪装已经通知其他参与者。

固定 OFF：

- speaker biometric identity；
- emotion/sentiment profiling；
- hidden-intent claims。

---

# 11. Resolved Data Path

Preflight 与 frozen Session Pulse 都显示分段数据路径，而不是一个模糊“Local”：

```text
Capture
STT
Inference
Retention
Write-back
Audio retention
Transcript retention
```

当前 Conversation deterministic runtime：

```text
Inference = LOCAL_DETERMINISTIC
Retention = LOCAL_PRODUCT_DB
Write-back = LOCAL_REVIEWED_DRAFT_ONLY / DISABLED
Audio retention = OFF
```

Local processing 对可能进入 remote STT 的配置 fail-closed；Capture start 会重新校验，防止 Preflight 后配置变化绕过 policy。

---

# 12. Continue / Reviewed Write-back

Continue 不是 summary-only 页面。

当前具有：

- What changed；
- Pins；
- reviewed Decision；
- Commitment；
- Open Question；
- Review Queue；
- Next Focus；
- Follow-up Draft；
- Task Draft；
- Issue Draft；
- Decision Log Draft。

DraftAction 状态：

```text
DRAFT
→ APPROVED / DISMISSED
```

`APPROVED` 只表示用户审核了本地草稿：

```text
APPROVED
!= email sent
!= external task created
!= issue created
!= decision log written
```

真正 connector execution 尚未接线，不能伪装完成。

---

# 13. Profile Maturity

| Profile | Shared runtime | Launch wedge | Specialized behavior validated | Stable v2 release | Real-user validated |
| --- | --- | --- | --- | --- | --- |
| Project Sync | YES | YES | NO | NO | NO |
| Design Review | YES | YES | NO | NO | NO |
| Presentation / Q&A | YES | NO | NO | NO | NO |
| 1:1 | YES | NO | NO | NO | NO |
| Client Call | YES | NO | NO | NO | NO |
| Negotiation | YES | NO | NO | NO | NO |

`runtime available != specialized behavior validated`。

在没有真实用户前，不因为共享 runtime 能跑就把六种模板都标成“已验证产品”。

---

# 14. 当前明确 blocked / future-runtime 项

以下不是“忘了实现”，而是当前证据边界要求不能假装已生效：

| 能力 | 当前状态 | 为什么不伪装 |
| --- | --- | --- |
| Conversation Screen Context | BLOCKED | Interview screenshot path 不能无条件复用到第三方会话 |
| Conversation Human Coach | BLOCKED | 需要独立 policy / disclosure / runtime evidence |
| Conversation Private Overlay / Share Privacy | BLOCKED | 需要 presenter-visible control 与 Conversation namespace |
| Calendar / Mail / Docs / project tracker connector | NOT WIRED | external dependency；不能用 placeholder 伪装 |
| External task/email/issue write-back execution | NOT WIRED | 当前只有 reviewed local drafts |
| 自动 participant chat notice / watermark | NOT WIRED | 当前只记录 user transparency plan |
| Organization / shared team truth registry | FUTURE | 必须在个人 v2 真实验证后再做 |

---

# 15. Evaluation Boundary

可由本地工程事实直接测量：

- source attribution coverage；
- guidance shown / used / dismissed / suppressed；
- duplicate suppression；
- suggestion budget；
- review queue；
- draft approval；
- latency / recovery；
- export/delete integrity；
- Pack immutability；
- provenance/tombstone integrity。

必须真人标注：

- Recall Precision；
- Direct Question Detection quality；
- Opportunity Precision；
- Interruption Regret；
- Useful Silence Rate；
- Decision/Commitment State Precision；
- real Continue write-back accuracy；
- real cross-session value；
- cognitive load；
- willingness to reuse same Space。

禁止：

```text
synthetic success → PMF
adoption → precision
test coverage → user value
```

---

# 16. Competitive Boundary

2026 竞品已经把以下能力商品化：

- transcript / summary；
- in-meeting Q&A；
- catch-up；
- action items；
- botless capture；
- real-time coaching；
- agenda / pacing；
- task/doc creation；
- cross-session context。

因此 Chengzhu 不把这些单点能力本身定义成 moat。

冻结差异：

```text
Contribution Opportunity
+ Provenance-aware Continuity
+ Stakeholder-aware Expression
+ Silence / Interruption Control
+ Review-first Truth Promotion
```

详见：

- `docs/research/Chengzhu_v2.0_Conversation_Competitive_Research_2026-10-06.md`

---

# 17. CI / Release Truth

PR #19 的 CI 必须同时通过：

- backend；
- frontend；
- desktop；
- Playwright；
- visual；
- packaged smoke；
- shared Interview regressions；
- ci-gate。

在 PR gate 全绿前：

```text
PR_CI_GATE = PENDING
ENGINEERING_CLOSURE_CANDIDATE = TRUE
```

即使 PR 全绿，也仍然：

```text
V2_PRODUCTIZED_RELEASE = FALSE
```

直到完成独立 Windows Conversation Beta packaged runtime evidence、clean-install replay、artifact hash、download-back 与 release provenance。

---

# 18. 本 PR 的闭环定义

PR #19 可以被称为 **v2 Design/Runtime Closure**，仅当：

- canonical 与 runtime truth 一致；
- 本矩阵每个 `RUNTIME_AVAILABLE` 项都有代码/测试证据；
- 不存在“表存在但没有生命周期语义”的一等对象；
- AI candidate 与 reviewed continuity 明确分层；
- mutable Space 与 frozen Session Pack 明确分层；
- external/unwired 能力 fail-closed；
- README 不夸大 release / validation；
- CI 全绿。

这之后的下一阶段是 **Conversation Beta productization / dogfood / real-user evidence**，不是继续靠文档把成熟度写高。
