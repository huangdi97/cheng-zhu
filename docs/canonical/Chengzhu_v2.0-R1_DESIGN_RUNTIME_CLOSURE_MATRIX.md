# Chengzhu v2.0-R1 Design → Runtime Closure Matrix

> 日期：2026-10-08  
> v2 closure：PR #19（已合并）  
> post-merge semantics：已进入 main  
> final pure-repo audit：`feat/chengzhu-v2-final-design-audit`  
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
V2_BETA_PACKAGED_ENGINEERING_EVIDENCE = TRUE
V2_BETA_PRERELEASE_PUBLISHED = TRUE
V2_PRODUCTIZED_RELEASE = FALSE
REAL_CONVERSATION_USER_EVIDENCE_PENDING = TRUE
PMF_PROVEN = FALSE
```

`RUNTIME_AVAILABLE` 只说明存在真实 route / persistence / UI / runtime path。当前主线已经具备 Windows packaged Conversation Beta engineering evidence 与独立 screenshot evidence，并且 `v2.0.0-beta.2` 已于 2026-10-09 公开发布为 GitHub Prerelease；tag/source SHA = `cac605edf413ec248babf02ea9f73da708d156f8`，Stable Latest 仍为 v1.4.2。这仍不等于 stable v2，也不等于真实用户价值已经验证。

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
- selected immutable connector snapshots（用户显式选入时）；
- exact connector grants / provider / connection ids（Session 请求 read capability 时）；
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
| Deadline / 带时间 Commitment 保存 original text / normalized datetime / timezone / ambiguity | ENFORCED · schema v6 |
| 模糊 Deadline 在时间消歧前不得进入 reviewed long-term truth | ENFORCED |
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
- tombstone 保留删除 provenance，但不会留下可行动的幽灵 Thread；
- Space Overview 可直接 Resolve reviewed Open Thread；
- thread-level Resolve 不自己改 truth，而是沿 `CONVERSATION_ITEM` provenance 调用原 Item 的 reviewed resolve transition。
- Thread projection lookup 按源 Session 的完整记录检索，不再使用 Space 最新 500 条的截断窗口；Session 删除基于一次性 provenance 映射移除派生 Thread（长期 Space 超过 500 条的回归测试见 `test_long_lived_space_open_thread_lookup_survives_over_500_other_threads`）。

---

# 6. Manual Ask / Context Retrieval

Manual Ask 的来源排序：

```text
confirmed cross-session state
> frozen Ready source version
> frozen connector snapshot（REFERENCE_SOURCE）
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

全局 Conversation Search 同样遵守 grounded boundary：

- Ctrl+K 可找 Decision / Commitment / Open Question；
- 搜索结果必须带 Space / Session / time / review state / source kind；
- 不提供无来源“AI 搜索答案”；
- current Session 支持分类化 local JSON export，不声称同步到外部系统。

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

Expression Planner runtime boundary：

```text
Conversation State
+ frozen Expression Profile
+ explicit audience context
+ provenance / policy / Profile lane
→ Guidance(kind / expression_action / text / source / reason)
```

Expression Plan 已成为 Guidance 的 service-boundary 派生 read model：SHOWN 与 SILENT 都返回 `action / kind / target / source / warnings / render_as / suppression`；target 只来自 explicit frozen participant selection，清空选择会清除旧 target。它不建立第二套持久化 truth table；长期审计仍以 Guidance event + frozen Session Pack 为准。

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

PR #61 引入 reviewed two-step external execution boundary：

```text
APPROVED DraftAction
→ 选择 exact CONNECTED account
→ 创建 Execution Request
→ 第二次显式 Execute
→ provider result
→ SUCCEEDED / FAILED / BLOCKED audit
```

这只表示**执行边界已实现**。默认仍无真实 provider/account；没有 adapter + credential + exact capability 时无法产生 SUCCEEDED。

---

# 12.5 Profile-specific Playbook Runtime

六个 Conversation Profile 不再只区别于名称、default mode 与 Guidance allowlist。

每个 Profile 现在都有冻结的 `Profile Playbook`：

- success conditions；
- priority truth types；
- Prepare prompts；
- closing objective；
- explicit boundaries。

Runtime 闭环：

```text
Template Picker
→ Prepare Playbook
→ Frozen Session Pack
→ Live Session Pulse
→ Continue Reviewed Outcome Evidence
```

Continue 只统计各 Profile priority truth type 中**经过 review 的真实输出**，并显式声明：

```text
reviewed output evidence
!= meeting-quality score
!= success score
!= real-user validation
```

当前 Playbook：

- Project Sync：Status / Commitment / Task / Risk / OpenQuestion / Deadline / Decision；
- Design Review：Decision / Proposal / Objection / Risk / Assumption / OpenQuestion / Metric；
- Presentation / Q&A：Metric / Status / Decision / OpenQuestion / Commitment；
- 1:1：Commitment / OpenQuestion / Status / Risk / Decision；
- Client Call：OpenQuestion / Commitment / Risk / Decision / Status / Metric；
- Negotiation：Proposal / Objection / Decision / Commitment / Risk / OpenQuestion。

这关闭了“模板只是共享 runtime 名字不同”的纯仓库设计缺口，但仍不等于 profile-specific real-user behavior validated。

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
| Conversation Manual Screen Context | RUNTIME_AVAILABLE | 独立 Conversation namespace；单次用户触发；raw image 不持久化；提取文本为 OBSERVED_NOT_CONFIRMED；vision route/fingerprint 冻结并受 processing policy 约束 |
| Conversation AUTO Screen Context | RUNTIME_AVAILABLE | policy 允许 ≠ 自动启动；Live 二次显式 start；ACTIVE/OFF THE RECORD 可见；consent/transparency user-report gate；同帧去重/限频/连续错误 fail-stop；raw image 不持久化；frozen vision route；Session/Space lifecycle 强制 stop |
| Conversation Human Coach | RUNTIME_AVAILABLE | Conversation-specific session kind/target + frozen HUMAN_ALLOWED policy + transparency gate + per-field permissions + helper-side session scoping + Interview Resume/JD isolation + advice-only audit + lifecycle revoke；beta.2 public prerelease / real-session evidence 仍是独立发布/用户证据门禁 |
| Conversation Private Overlay / Share Privacy | RUNTIME_AVAILABLE_DESKTOP | 复用 Electron `setContentProtection`，但由 Conversation Session Policy 显式请求；Start 前临时启用并验证 runtime proof，Pack 冻结 verified state，Live 显示 ACTIVE/UNKNOWN，End 后恢复会话前全局默认；Web fallback fail-closed；best-effort only，不声称安全/隐身/不可检测 |
| Connector capability contract / registry | RUNTIME_AVAILABLE · NO PROVIDER BY DEFAULT | capability registry 默认空且 fail-closed；只回答 capability truth |
| Local scheduled Conversation reminder | RUNTIME_AVAILABLE_DESKTOP | 只读取 Chengzhu 内手工排期的 UPCOMING Session；用户显式 opt-in；默认提前 10 分钟；通知不泄露 Session/Space 标题；点击进入对应 Space Prepare；不等于 Calendar connector |
| External Integration Boundary | RUNTIME_AVAILABLE | PR #61 已合入 main：schema v9、opaque credential ref、CONNECTED account、Space-scoped immutable snapshot、canonical hash、per-capability cursor、exact grant、retention/export、Execution Request / audit、UNKNOWN_OUTCOME reconciliation |
| GitHub project tracker / issue provider | RUNTIME_AVAILABLE_OPT_IN · REAL ACCOUNT EVIDENCE PENDING | 首个真实 REST adapter：project.read + issue.create；默认不注册，需 CHENGZHU_GITHUB_CONNECTOR_ENABLE=1；token 仅经 env credential reference 解析；没有真实账户连接/外部 action evidence 前不得宣称 GITHUB_ACCOUNT_CONNECTED |
| Calendar / Mail / Docs / Microsoft / MCP provider | NOT CONFIGURED | catalog/contract 已定义；没有真实 adapter/auth/account/runtime evidence 就不能宣称可用 |
| External task/email/issue write-back execution boundary | RUNTIME_AVAILABLE | reviewed Draft → exact account → Execution Request → second Execute → provider result；UNKNOWN_OUTCOME 只能经 provider-side reconciliation；GitHub issue.create 已有 opt-in real adapter，其他 provider 仍 fail-closed |
| Real external action evidence | NOT AVAILABLE | 只有 provider 真连接并返回 SUCCEEDED 后才能形成；mock/FakeAdapter 只证明边界逻辑 |
| 自动 participant chat notice / watermark | NOT WIRED | 当前只记录 user transparency plan |
| Organization / shared team truth registry | FUTURE | 必须在个人 v2 真实验证后再做 |

---

# 14.5 Derived Conversation State

Conversation State 已有真实 runtime read model，但不是独立可写数据库真值：

- Session status → PREPARE / PARTICIPATE / CONTINUE；
- session state → current topic / user speaking / audience context / last guidance；
- current Session Items；
- reviewed longitudinal Open Threads。

Live Session Pulse 可读取该状态。

规则：

```text
derived state view
!= Conversation Item truth
!= Open Thread truth
!= new persistence authority
```

这避免 Expression Planner / UI / diagnostics 各自维护一套可漂移状态。

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
- connector snapshot Space isolation / canonical hash / Pack freeze；
- per-capability incremental sync cursor isolation；
- execution idempotency / single-call concurrency / UNKNOWN_OUTCOME reconciliation；
- value-level secret redaction / secret-safe export；
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

Settings > Diagnostics 现已把 Conversation 子系统拆成：

- database；
- capture；
- Session Pack / Context；
- retrieval；
- state engine；
- Guidance Arbiter；
- export/delete integrity；
- processing policy；
- speaker/diarization boundary；
- external connector / screen / coach / write-back execution。

普通 UI 只显示“可用 / 受限 / 需要处理”；raw JSON 二级展开。

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

代码闭环 checkpoint：

```text
CODE_CLOSURE_HEAD = 873e92f98e357f49358fd6b04a4c440ec43f6750
CODE_CLOSURE_CI_RUN = 37571903716
CODE_CLOSURE_CI_GATE = PASS
```

该 run 已通过：

- backend；
- frontend；
- desktop；
- Playwright functional；
- visual；
- e2e-smoke；
- packaged-smoke；
- ci-gate。

任何后续文档/证据提交都会形成新的 PR HEAD，因此 **最终 merge 仍必须以实际最终 HEAD 的 CI 全绿为准**，不能拿旧 checkpoint 给新 HEAD 背书。

PR #19 已合并到 main。post-merge 对象闭环由 PR #24 承接；PR #24 只包含 Open Thread Resolve / derived Conversation State / Expression Plan truth-boundary 及其测试/文档增量。它必须以自己的 final-head CI 作为合并证据。

PR #19 之后，main 已继续补齐：

- Conversation Beta packaged smoke；
- Windows packaged Conversation UI evidence；
- 独立 Conversation screenshot evidence；
- clean-install / installed-layout release gate；
- human-label evaluation tooling；
- schema v7 Manual Screen Context；
- long-lived Open Thread provenance correctness。

因此当前发布层允许升级为：

```text
V2_BETA_PACKAGED_ENGINEERING_EVIDENCE = TRUE
V2_BETA_PRERELEASE_CANDIDATE = TRUE
V2_PRODUCTIZED_RELEASE = FALSE
REAL_CONVERSATION_USER_EVIDENCE_PENDING = TRUE
PMF_PROVEN = FALSE
```

`v2.0.0-beta.2` 已通过 public prerelease 发布门禁并以 GitHub `prerelease=true` 发布；tag/source SHA 精确等于 `cac605edf413ec248babf02ea9f73da708d156f8`，Stable Latest 仍为 v1.4.2。允许写 `V2_BETA_PRERELEASE_PUBLISHED = TRUE`。Stable v2 仍保留独立门禁。

Public prerelease provenance：`docs/releases/V2_0_0_BETA_2_PUBLICATION_PROVENANCE.md`。

---

# 17.5 Final Pure-repo Audit

PR #19 合并后的最终仓库审计只关闭**不依赖外部系统、Windows 新打包证据或真实用户**的剩余 canonical gap：

- grounded global Item search；
- Ctrl+K find Decision / Commitment / Open Question；
- current Session categorized local export；
- ad-hoc 统一为 Space-backed continuity truth，不再设计第二套 standalone truth；
- schema v6 temporal provenance + Deadline ambiguity review gate；
- subsystem-level Conversation Diagnostics；
- privacy-first local scheduled Conversation reminder（非 Calendar discovery）；
- stale Reality Report / historical Goal truth sync。

以下仍保持 external/productization gate，不得为了“全做完”伪实现：

- real Google / Microsoft / MCP adapter + account authorization；
- GitHub real-account authorization / real repository replay / real external Issue evidence（adapter code 已存在，真实账户证据仍是 external gate）；
- external Calendar/meeting discovery；
- Human Coach real-session evidence；
- real external action evidence（边界/runtime 可在 repo 内实现；provider success 必须来自真实 adapter/account）；
- participant auto chat notice / watermark；
- Windows v2 stable packaged release；
- real-user validation。

# 17.8 Post-beta.2 Stable Promotion Gate

beta.2 之后不再用 synthetic/packaged evidence 单独推动 stable 状态。

新增机器可执行产品证据门禁：

- `docs/evals/V2_CONVERSATION_STABLE_PROMOTION_POLICY.json`
- `scripts/v2_conversation_stable_readiness.py`
- `docs/evals/v2_conversation_real_pilot_manifest.template.json`
- `docs/canonical/Chengzhu_v2.0-R1_STABLE_PROMOTION_GATE.md`

它要求 Project Sync / Design Review 的真实 pilot floor、human-label metric sample floor 与质量阈值、授权/隐私/数据丢失 attestations。

PASS 只允许：

```text
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = TRUE
```

明确不允许自动升级：

```text
V2_STABLE_RELEASE = TRUE
PMF_PROVEN = TRUE
```

stable packaged/release/security/public-truth review 仍是独立门禁。

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

这之后的下一阶段已经从“是否有 packaged evidence”推进为 **Conversation Beta public prerelease / dogfood / real-user evidence**。packaged evidence 与 human-eval tooling 已进入 main；剩余成熟度只能由公开 prerelease provenance、真实 dogfood 和真实用户研究继续推进，不能继续靠文档把状态写高。
