# 成竹 Chengzhu v2.0-R1
## Personal Conversation Intelligence｜Implementation & Rollout Master Goal
**日期**：2026-10-06  
**状态**：CANONICAL IMPLEMENTATION GOAL  
**工作分支**：`feat/chengzhu-v2-conversation-design-closure`  
**当前 PR**：#19（承接已合入的 Conversation runtime PR #18）  
**最高设计依据**：`Chengzhu_v2.0-R1_PERSONAL_CONVERSATION_INTELLIGENCE.md`

---

# 0. 总目标

把 Chengzhu 从已发布的 Interview-first 产品，扩展成一个仍以个人为中心的：

> **Personal Conversation Intelligence**

并做到：

```text
不是：
meeting recorder
meeting summary app
generic chatbot in a meeting
sales-only coach
team workspace clone

而是：
用户自己的长期事实 / 项目 / 关系 / 决策 / 承诺 / 目标
        ↓
冻结进每一场允许使用的 Session Pack
        ↓
结合当前话题 / 明确 stakeholder / policy
        ↓
判断“现在是否值得说、说什么、对谁说、是否应该沉默”
        ↓
会后把真实变化带到下一场
```

---

# 1. 状态模型：永远不要再混淆这四层

## 1.1 DESIGN_COMPLETE
产品、对象、交互、AI、privacy、eval、rollout 已定义。

## 1.2 RUNTIME_AVAILABLE
仓库里存在真实 route / UI / API / persistence / test 路径，可以运行。

## 1.3 BETA_PRERELEASE
经过 packaged runtime evidence、installer / portable、download-back 与 release provenance gate，以 GitHub Prerelease 公开，可供真实 dogfood；不得成为 Stable Latest。

## 1.4 PRODUCTIZED_RELEASE
经过稳定版 packaged release、runtime evidence、download-back、release provenance gate，对公众作为 stable 产品发布。

## 1.5 REAL_USER_VALIDATED
真实用户在真实对话中证明：
- Recall 有用；
- Opportunity precision 足够高；
- 不必要打断足够少；
- continuity 真正减少认知负担；
- 不只是 synthetic / mock / dogfood。

当前禁止把这四层互相替代。

---

# 2. 当前真实基线

## 2.1 Interview Profile

```text
DESIGN_COMPLETE = TRUE
RUNTIME_AVAILABLE = TRUE
PRODUCTIZED_RELEASE = TRUE
REAL_USER_VALIDATED = FALSE
```

Interview v1.4.x 已有正式 Windows packaged release 与 release provenance evidence，但没有真实用户价值/PMF 结论。

## 2.2 Conversation Profile

PR #18 已建立真实 Conversation runtime：

- opt-in Conversation Beta；
- Profile Switcher；
- Conversation Home；
- Spaces；
- Prepare；
- Preflight；
- Live；
- Continue；
- Decisions；
- History；
- Project Sync / Design Review / Presentation-QA / 1:1 / Client Call / Negotiation 模板；
- source-aware Manual Ask；
- cross-session Recall；
- Contribution Opportunity；
- deterministic SILENT / suppression；
- Conversation-owned TRANSCRIPT capture；
- additive persistence；
- export / retention / delete provenance；
- local DraftActions；
- synthetic/runtime/E2E gates。

PR #19 负责 canonical closure，不得重新定义成第三套产品。

当前目标状态：

```text
V2_DESIGN_COMPLETE = TRUE
V2_CONTRACT_COMPLETE = TRUE
V2_RUNTIME_AVAILABLE = TRUE
V2_BETA_PACKAGED_ENGINEERING_EVIDENCE = TRUE
V2_BETA_PRERELEASE_CANDIDATE = TRUE
V2_PRODUCTIZED_RELEASE = FALSE
REAL_CONVERSATION_USER_EVIDENCE_PENDING = TRUE
PMF_PROVEN = FALSE
```

---

# 3. 产品楔子与模板等级

## 3.1 Launch wedge

优先验证：

1. Project Sync；
2. Design Review。

原因：
- 用户自己的历史事实 / decision / commitment continuity 价值最容易观察；
- provenance 与 owner / due / supersession 有明确语义；
- 比销售 coaching 更少依赖组织 CRM；
- 比 1:1 / negotiation 更少触碰隐藏心理推断；
- 更适合内部 dogfood。

## 3.2 Shared-runtime templates

以下模板允许使用同一 Conversation runtime：

- Presentation / Q&A；
- 1:1；
- Client Call；
- Negotiation。

但：

```text
runtime available
!=
profile-specific behavior validated
!=
stable productized release
```

每个模板只有在专属 E2E / policy / real-session evaluation 完成后，才能提高状态等级。

---

## 3.3 Profile Playbook Gate

所有 Profile 在 shared runtime 之上必须拥有真实、冻结、可测试的 Playbook，而不是只修改 label / default mode / Guidance allowlist。

每个 Playbook 至少定义：

- success conditions；
- priority truth types；
- Prepare prompts；
- closing objective；
- boundaries。

必须贯穿：

```text
Template Picker
→ Prepare
→ Frozen Session Pack
→ Live Session Pulse
→ Continue Reviewed Outcome Evidence
```

Continue 只统计 review 后的 priority truth outputs；禁止生成：

- meeting quality score；
- success percentage；
- pseudo-readiness；
- 未经真实会话证据支持的“该模板已验证”。

`runtime specialization exists != specialized behavior validated`。


# 4. 必须存在的用户主循环

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

任何新增页面必须服务这条 loop，禁止重新退化成：

```text
Transcript
Summary
Meeting list
AI chat
```

几个互相割裂的模块。

---

# 5. 全局 IA Gate

Conversation Profile 激活时一级导航只允许：

```text
首页
对话空间
我的成竹
资料库
历史
设置
```

全局：

```text
[开始]
```

行为：
- 当前位于某个 Space → 进入该 Space Prepare；
- 其他 Conversation 页面 → 创建 Space / Preflight 路径；
- 不允许跳回 Interview Go Live。

禁止增加：
- Project Sync；
- Design Review；
- Client Call；
- Negotiation；
- 1:1

作为独立一级导航。

---

# 6. Conversation Home Gate

第一屏只回答：

- 下一场；
- Next Focus；
- 我欠的；
- Waiting / Open Questions；
- Recent Change。

禁止：
- productivity score；
- influence score；
- sentiment；
- pseudo-readiness；
- 伪精确百分比。

---

# 7. Conversation Space Gate

必须具有：

## Overview
- Next Focus；
- Next Session；
- Open Commitments；
- Open Questions；
- Recent Decisions；
- relevant participants；
- Last Session Delta。

## Prepare
- Session Goal；
- Agenda；
- Brief；
- unresolved items；
- relevant decisions；
- sources；
- Quick Notes；
- expected questions；
- contribution candidates；
- Session Pack Preview。

## Sessions
- 每一场真实 Session；
- Continue；
- source / review 状态；
- 不回退到 Interview History。

## Decisions
- Proposed / Agreed / Superseded；
- provenance；
- speaker / confirmer；
- objection；
- follow-up；
- supersession chain。

---

# 8. Session Pack Gate

开始一场前必须冻结：

- Space identity；
- Goal ids；
- selected Ready sources；
- skipped/unready sources；
- Quick Notes；
- confirmed Conversation Items；
- participants；
- **我的表达 / Expression Profile**；
- Session Policy；
- capture mode；
- processing mode；
- assistance mode；
- consent acknowledgement；
- retention policy；
- **resolved processing runtime / data path**。

Pack 必须有 digest。

原则：

> 后续资料变化、表达偏好变化、全局配置变化不得静默改写已经开始的这一场。

---

# 9. Truth / Provenance Gate

一等实体：

- Decision；
- Commitment；
- Task；
- Deadline；
- Risk；
- Assumption；
- OpenQuestion；
- Proposal；
- Objection；
- Metric；
- Status。

状态：

- PROPOSED；
- AGREED；
- COMMITTED；
- DONE；
- SUPERSEDED；
- UNKNOWN。

审核：

- AI_EXTRACTED；
- USER_CONFIRMED；
- USER_EDITED；
- USER_REJECTED；
- SOURCE_CONFIRMED。

硬规则：

1. transcript segment 只是 source；
2. summary 不能自己成为 truth authority；
3. Decision → AGREED 需要 provenance + 明确 review；
4. Commitment / Task → COMMITTED 需要 owner + provenance + review；
5. Deadline 必须有来源；
6. Superseded 保留旧事实，不做破坏性覆盖；
7. owner / speaker / due / state 可以分别 unknown；
8. Quick Note 不能自动升级成 evidence；
9. 删除已确认事项所属 Session 时保留 provenance tombstone。

---

# 10. Counterparty / Stakeholder Gate

允许长期保存：

- role；
- explicit priority；
- explicit concern；
- stated position；
- decision authority；
- relationship context；
- source；
- confidence。

UI 明确分：

```text
Known / Explicit
Inferred / Temporary
Unknown
```

禁止把：
- emotion；
- personality；
- hidden intent；
- secret bottom line；
- “他不信任你”；
- “他想压价”

当作长期确定事实。

临时 inference：
- session-scoped；
- TTL；
- 不自动进入长期 Memory。

---

Conversation State 同样是派生 read model：phase / topic / user-speaking / audience context / current items / reviewed open threads / last guidance 从已有真值对象组合，不新增独立可写状态表。

# 11. Expression Planner Gate

输入至少覆盖：

- goal；
- current topic；
- explicit audience role；
- explicit concern；
- decision authority；
- relationship context；
- selected evidence；
- shared Expression Profile；
- session policy；
- interruption / suggestion budget。

允许动作：

- SILENT；
- ANSWER；
- RECALL；
- ADD_TALKING_POINT；
- ASK_QUESTION；
- FLAG_RISK；
- CLARIFY；
- SUMMARIZE；
- COMMIT_NEXT_STEP。

底线：

> 修改表达结构，不修改事实。

---

Runtime closure：Expression Plan 是 Guidance 的派生展示层，不单独建立第二套持久化 truth。长期审计以 Guidance 的 kind / expression_action / source_refs / reason / user_action 与 frozen Session Pack 为准；DELIVERY 读取共享 Expression Profile 与 explicit audience context 生成结构提示。

# 12. Guidance Arbiter Gate

硬优先级：

```text
Direct Question
> Critical Risk
> High-confidence Recall
> High-value Contribution Opportunity
> Open Question
> Delivery
```

必须实现：

- 一次最多一个 primary Guidance；
- direct question 取消旧 proactive opportunity；
- critical risk 可以抢占普通机会；
- 用户连续说话默认 suppress proactive；
- source visibility 不允许 → 不进入 Guidance；
- 无 provenance 的个人事实 → 不主动提示；
- duplicate / semantic repeat → suppress；
- stale context → suppress / downgrade；
- social risk 高 → SILENT；
- Balanced / Active 有 suggestion budget；
- transcript-driven Recall 也必须服从 visibility + budget；
- Quiet 只允许 direct question / critical risk / manual ask。

---

# 13. Privacy / Consent Gate

Preflight 是产品面，不是免责文字。

必须显示并冻结：

- Capture Mode；
- Processing Mode；
- transcript retention；
- participant consent status（用户报告）；
- participant transparency plan（用户报告）；
- selected sources；
- connector permissions；
- screen context；
- AI Assistance Policy；
- Human Assistance Policy；
- Share Privacy；
- external write-back。

默认：

```text
Local-first
No auto-share
No auto-send
No auto-create external task
No biometric identity
No emotion/sentiment profiling
No hidden-intent claims
No claim that participants were automatically notified
```

## 13.1 Runtime truth

尤其禁止：

```text
UI says LOCAL
but STT can silently use remote provider
```

因此必须解析：

```text
capture locality
STT locality
inference locality
retention locality
write-back locality
```

如果 policy 与真实 runtime path 不一致：
- fail closed；
- 不静默降级；
- 不只显示 warning。

Capture start 必须二次校验，防止 Preflight 后配置改变。

---

# 14. 当前明确 Blocked 的能力

以下能力在真实 runtime 未接线前必须阻止开始或标明 unavailable：

## Conversation Screen Context
MANUAL 已实现为 Conversation-owned capability：每次由用户主动抓取，原图不落库，保存的只是 observation text + image/model-route provenance；LOCAL processing 下 remote vision fail-closed，冻结 vision fingerprint 在会中变化时拒绝继续抓取。AUTO 仍未接线，不能直接假设 Interview screenshot pipeline 可以安全复用。

## Conversation Human Coach
不能把 Interview practice/live Coach 权限直接映射到 Conversation。

## Conversation Private Overlay / Share Privacy
现有 overlay 仍是 Interview Live 语义；没有 Conversation 独立证明前，`PRIVATE_OVERLAY` 不得伪装为有效。

## External connectors
Calendar / mail / project tracker read path 未接线时，非空 connector permission 必须阻断或保持 unavailable。

## Actual external write-back
当前：
- local draft；
- review；
- approve local draft。

不等于：
- email 已发送；
- task 已创建；
- issue 已写入；
- decision log 已同步。

---

# 15. Integration Rollout

## Phase A — Personal local runtime
当前主线。

目标：
- Space continuity；
- local capture；
- provenance；
- Guidance；
- Continue；
- export/delete；
- synthetic/runtime validation。

## Phase B — Read-only connectors
仅在 connector 真实存在时进入：
- Calendar；
- Docs；
- Mail；
- project tracker。

规则：
- connector 只是 source；
- 不提升 truth authority；
- permission 要进入 Session Pack；
- source visibility 可阻止 Guidance。

## Phase C — Reviewed write-back
支持：
- follow-up draft；
- task draft；
- issue draft；
- decision-log draft。

必须：

```text
Draft
→ explicit user review
→ explicit target
→ explicit execute
→ connector result / failure
→ audit trail
```

## Phase D — Organization
只有个人 v2 真实验证后再设计：
- shared decision registry；
- team commitments；
- org permissions；
- shared policy；
- enterprise governance。

禁止在个人价值未验证前先做团队平台。

---

# 16. Evaluation Gate

## 16.1 本地可观测 proxy

允许计算：
- source attribution coverage；
- guidance adoption rate；
- guidance dismissal rate；
- suppression rate；
- duplicate suppression count；
- review queue size；
- approved draft rate；
- latency；
- recovery；
- deletion/export integrity。

它们只能叫：
> observed runtime proxy

## 16.2 必须真人标注

- Recall Precision；
- Source Attribution Accuracy；
- Direct Question Detection；
- Decision/Commitment State Precision；
- Opportunity Precision；
- Interruption Regret；
- Useful Silence Rate；
- Continue Write-back Accuracy；
- real cross-session value；
- real cognitive load。

禁止：
- 用 adoption 代替 precision；
- 用 synthetic success 代替 real-user value；
- 用 test coverage 代替 PMF。

---

# 17. CI / Release Gate

## PR Gate

必须：
- backend lint；
- backend compile；
- backend tests；
- frontend typecheck/build/tests；
- desktop；
- Playwright；
- visual；
- shared Interview regressions。

任何红项：
- 不写 ENGINEERING_COMPLETE；
- 不更新稳定 release；
- 不绕过已有 gate。

## Conversation Beta Runtime Candidate Gate

PR 合并后至少要有：
- clean source checkout；
- Windows desktop startup；
- Conversation opt-in；
- Home；
- Space；
- Prepare；
- Preflight；
- Live；
- Continue；
- History；
- 390px；
- capture start/pause/resume/stop；
- source-aware Manual Ask；
- SILENT；
- provenance review；
- export/delete；
- privacy fail-closed evidence。

## Public Conversation Beta Prerelease Gate

`v2.0.0-beta.1` 只允许在以下条件同时成立时发布：

- exact green main SHA；
- Windows installer + portable；
- Conversation packaged runtime UI evidence；
- independent Conversation screenshot evidence；
- clean installer replay；
- installed-layout smoke；
- SHA256；
- GitHub draft download-back；
- downloaded installer replay；
- tag/source provenance；
- `prerelease=true`；
- `latest=false`；
- GitHub Stable Latest 仍不是该 Beta tag。

只有公开 prerelease 实际完成后，才允许：

```text
V2_BETA_PRERELEASE_PUBLISHED = TRUE
```

仍不允许：

```text
V2_PRODUCTIZED_RELEASE = TRUE
REAL_USER_VALIDATED = TRUE
PMF_PROVEN = TRUE
```

## Stable v2 Productized Release Gate

在宣称 `V2_PRODUCTIZED_RELEASE=TRUE` 前还需要：
- packaged Windows runtime evidence；
- clean install replay；
- installer/portable artifacts；
- SHA256；
- download-back verification；
- release provenance；
- README/public screenshot truth；
- no current critical runtime blocker。

---

# 18. Real-user Gate

真实用户不存在时：

允许：
- synthetic dry run；
- deterministic tests；
- local dogfood；
- mock E2E；
- packaged runtime evidence。

不允许：
- “用户喜欢”；
- “降低 30% 认知负担”；
- “提升会议质量”；
- “Opportunity precision 已验证”；
- “PMF 成立”。

第一批真实用户建议只验证 Project Sync / Design Review。

最低需要采集：
- 每条 shown Guidance 是否 useful；
- 每条 dismissed / ignored 的原因；
- 哪些本应提示但没提示；
- 哪些提示打断了表达；
- Recall 是否准确；
- source 是否正确；
- 会后 Continue 是否减少下一次准备时间；
- 用户是否愿意连续使用同一个 Space。

---

# 19. 当前完成定义

逐项设计→runtime 对照与证据索引见：

- [v2.0-R1 Design → Runtime Closure Matrix](Chengzhu_v2.0-R1_DESIGN_RUNTIME_CLOSURE_MATRIX.md)


本次 v2.0-R1 closure 只有在以下条件同时成立时才算“设计与当前仓库可做部分做完”：

- canonical 已同步真实实现；
- competitive research 有当前外部证据；
- implementation master goal 存在；
- executable contract 不再说 runtime 不存在；
- Profile 的 `productized` 与 `runtime_available` 分开；
- Room / Prepare / Preflight / Live / Continue / History 对齐；
- Session Pack 冻结 expression + policy + resolved data path；
- Truth Model 硬规则有测试；
- Decision supersession 方向与历史保留是原子的；
- AI-extracted candidate 不进入长期 Home / History / Next Focus continuity；
- reviewed OpenQuestion / Risk / Objection 才能投影为 longitudinal Open Thread，并可显式 resolve；
- Conversation Goal lifecycle 与 Session frozen membership 有测试；
- Guidance Arbiter priority / silence / visibility / budget 有测试；
- Counterparty 不做隐藏心理事实化；
- participant consent / transparency 只记录用户报告，不伪装系统已验证/已通知；
- Local processing fail-closed；
- Manual Screen Context 可用且 AUTO screen / coach / private overlay / connectors 明确 blocked；
- diagnostics 分 observed proxy 与 human-label metrics，并暴露 Pack / retrieval / state / arbiter / export-delete 等子系统健康；
- 全局 Conversation Search 返回 grounded Item + Space / Session / time / source；
- Ctrl+K Find Decision / Commitment / Open Question 与 current Session export 为真实 runtime；
- Deadline / temporal Commitment 使用 schema v6 time semantics，模糊时间 review-first；
- ad-hoc 只使用 Space-backed continuity，不制造 standalone 第二真相；
- README / canonical / Reality Report 不再写“v2 runtime 尚不存在”；
- PR #19 最终 CI 全绿。

---

# 20. 当前下一阶段

PR #19 后，以下已经进入 main，不再列为未来项：

- Windows packaged Conversation Beta evidence；
- independent Conversation screenshot evidence；
- local human-evaluation tooling；
- Manual Screen Context；
- Conversation search/export；
- long-lived Open Thread correctness。

当前下一阶段按顺序是：

1. 发布 `v2.0.0-beta.1` GitHub Prerelease，保持 v1.4.2 为 Stable Latest；
2. 用该可下载安装包进行 local dogfood；
3. 真实 Project Sync / Design Review 小规模使用；
4. 收集 human-labeled Guidance / missed-moment / continuity evidence；
5. 根据真实证据再决定是否继续投入：
   - AUTO Screen Context；
   - Human Coach；
   - Private Overlay；
   - Calendar / Docs / Mail / project-tracker connectors；
   - actual external write-back；
   - Presentation / 1:1 / Client Call / Negotiation 专属行为优化。

后四类不是“源码里再补几个字段就能完成”的缺口，而是需要真实 runtime、外部权限或真实用户证据才能合法升级状态。
