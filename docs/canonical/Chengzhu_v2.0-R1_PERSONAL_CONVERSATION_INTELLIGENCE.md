# 成竹 Chengzhu v2.0-R1
## Personal Conversation Intelligence｜Interview Profile × Conversation Profile × Provenance-aware Expression

**版本**：v2.0-R1  
**日期**：2026-10-06  
**状态**：CANONICAL DESIGN COMPLETE / CONVERSATION BETA RUNTIME AVAILABLE / STABLE v2 RELEASE NOT CLAIMED  
**基线**：v1.4.2 Windows reproducible Interview release + merged Conversation runtime PR #18 + v2 closure PR #19  
**产品定义**：Personal Conversation Intelligence  
**首发验证楔子**：项目周会 / 技术设计评审  
**核心原则**：Help me know **what is worth saying, why, to whom, and whether I should stay silent.**

> v2.0 的目标不是把成竹改造成“AI 会议纪要”，而是把已经验证的 Interview Core 泛化为一个个人对话智能系统：基于用户自己的事实、资料、历史、目标和当前会话，在真正需要的时刻帮助用户回忆、判断、组织和表达属于自己的内容。

---

# 0. 版本地位与继承关系

真实事实优先级继续保持：

1. 当前 repository / runtime / CI / release artifact；
2. 本 v2.0-R1；
3. v1.4.x validation/release truth；
4. v1.3-R2 Goal-centered Interview OS；
5. v1.2-R2 Verified Interview Core；
6. 更早文档仅作 provenance。

v2.0 **冻结而不重写**：

- Provenance / User Assertion / Session Statement；
- Frozen Session/Interview Pack 思想；
- Context Compiler authority；
- Fast Cue before Deep；
- Stream Truth Guard；
- local-first；
- Share Privacy default OFF；
- Windows desktop sidecar / audio / ASR / overlay 基础；
- Person / Goal / Session / Reflection 的连续性；
- Interview Profile 已发布产品能力。

v2.0 新增的不是“Meeting 功能包”，而是第二个正式 Profile 家族：

```text
Chengzhu Core
├── Interview Profile          ← v1.x 已发布
└── Conversation Profile       ← v2.x 新设计
    ├── Project Sync
    ├── Design Review
    ├── Presentation / Q&A
    ├── 1:1
    ├── Client Call
    └── Negotiation
```

六种场景是 **Profile Template**，不是六套导航、六套数据模型或六套应用。

---

# 1. 为什么现在进入 v2 设计

v1.4.2 已经把 Interview 的工程闭环、Windows packaged runtime、release provenance 和公开产品真相收口。当前仍无真实用户，因此：

```text
REAL_USER_EVIDENCE_PENDING = TRUE
PMF_PROVEN = FALSE
```

这意味着不能把 v2 写成“市场验证后的扩张”，但可以把长期设计完整做完，并通过内部 dogfood / synthetic evidence 验证工程可行性。

本版明确区分：

- **DESIGN_COMPLETE**：产品、对象、AI、UI、隐私、评测、迁移定义完整；
- **CONTRACT_COMPLETE**：共享类型与边界可执行；
- **RUNTIME_AVAILABLE**：真实 route / UI / API / persistence / test 路径存在；
- **PRODUCTIZED_RELEASE**：完成 packaged runtime、release artifact、download-back 与公开发布门禁；
- **REAL_USER_VALIDATED**：需要真实参与者，当前不得宣称。

截至 2026-10-06 的真实状态：

```text
V2_DESIGN_COMPLETE = TRUE
V2_CONTRACT_COMPLETE = TRUE
V2_RUNTIME_AVAILABLE = TRUE
V2_PRODUCTIZED_RELEASE = FALSE
REAL_CONVERSATION_USER_EVIDENCE_PENDING = TRUE
PMF_PROVEN = FALSE
```

Conversation runtime 已由 PR #18 落地；PR #19 负责 canonical/runtime closure。Project Sync / Design Review 是 launch wedge。其余模板可运行于 shared runtime，但 profile-specific behavior 尚未分别证明。

---

# 2. 市场判断：差异不在“会后摘要”

2026 年主流产品已经覆盖：

- botless/system-audio capture；
- transcript / summary / action items；
- “catch me up”与会中问答；
- calendar brief；
- cross-session memory；
- 实时 suggestions/coaching；
- agenda / pacing / task execution；
- task/CRM/project integrations；
- MCP/agent access。

当前官方产品事实进一步显示：Otter Live Assist 已进入实时 glanceable coaching；Teams Facilitator 已把 agenda / timer / decisions / open questions / tasks 推进到会中；Granola 强调 botless、本机捕获与 private-by-default；Zoom / Gemini 已把 in-meeting Q&A、notes/action items 做成基础能力。

因此“更好的纪要”或“有实时提示卡”都不是足够的产品楔子。

完整研究见：

- [2026-10-06 Conversation Competitive Research](../research/Chengzhu_v2.0_Conversation_Competitive_Research_2026-10-06.md)

Chengzhu v2 的核心差异冻结为：

## 2.1 Contribution Opportunity

系统持续判断：

> **当前讨论里，我有没有一条真正相关、尚未被提出、来源可靠、对当前目标有价值的信息值得说？**

它不是 RAG 命中就弹提示，而是经过：

```text
relevance
+ novelty
+ provenance_strength
+ role_relevance
+ goal_relevance
+ urgency
+ decision_impact
- interruption_cost
- already_mentioned
- uncertainty
- social_risk
- stale_context_risk
```

并由 Live Guidance Arbiter 决定：显示、延后、抑制或保持沉默。

## 2.2 Provenance-aware Conversation Continuity

Meeting transcript 不是事实本身。成竹长期保存的是可追溯状态：

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

系统必须区分：

```text
有人提出
≠
团队同意
≠
某人承诺
≠
已经完成
```

## 2.3 Stakeholder-aware Expression

同一个事实针对 CTO、直属经理、客户、合作团队可以改变结构、长度、重点，但不能改变事实。

## 2.4 Silence is a first-class action

v2 的 Expression Planner 必须允许：

```text
SILENT
```

“此刻不要说”与“此刻应该说什么”同等重要。

---

# 3. v2 稳定产品对象

v2 在 v1 的 Person × Goal × Pack × Session × Reflection 上扩展，而不是重做。

```text
Person
  │
  ├── Interview Goal
  │
  └── Conversation Space
         ├── Conversation Goal
         ├── Participants / Counterparty State
         ├── Session Pack
         ├── Conversation Session
         │      ├── Topics / Open Threads
         │      ├── Guidance Events
         │      └── Conversation Items
         └── Continue / Next Focus
```

### Person
用户长期事实世界、项目、角色、技能、表达偏好与来源。

### Conversation Space
一个可持续多场会话的上下文容器，例如：

- PDIG Android Architecture；
- Acme 客户；
- 与直属经理的 1:1；
- Q4 Roadmap Review。

它不是聊天文件夹，而是长期 Conversation continuity 边界。

### Conversation Goal
一场或一系列会话希望达成的结果，例如“决定 conflict merge strategy”。

### Session Pack
这一场允许进入实时推理的冻结上下文。只包含用户明确授权的来源。

### Conversation Session
一次真实会话的发生记录。

### Conversation Item
Decision / Commitment / Task 等结构化状态。

### Continue
会后不是“总结页”，而是：什么改变了、谁承诺了什么、什么还没解决、下一次从哪里继续。

---

# 4. Profile 与场景模板

## 4.1 Project Sync（首发楔子）

目标：状态同步、blocker、owner、deadline、跨场延续。

高权重 Guidance：

- Recall
- Question
- Contribution Opportunity
- Risk
- Commit Next Step

## 4.2 Design Review（首发楔子）

目标：清晰呈现 trade-off、记录 objection、形成可追溯 decision。

高权重 Guidance：

- Talking Point
- Risk / Contradiction
- Question
- Contribution Opportunity
- Recall

## 4.3 Presentation / Q&A

目标：结构、时间、Q&A、受众适配。

高权重 Guidance：

- Delivery
- Answer Cue
- Recall
- Question

## 4.4 1:1

目标：关系连续性、承诺、反馈与敏感表达。

高权重 Guidance：

- Recall
- Question
- Talking Point
- Commitment continuity

禁止：情绪诊断、人格推断、隐藏心理状态。

## 4.5 Client Call

目标：客户目标、明确 concern、风险、承诺与 next checkpoint。

高权重 Guidance：

- Recall
- Answer Cue
- Question
- Risk
- Contribution Opportunity

## 4.6 Negotiation

目标：约束、proposal、objection、明确条件、避免事实/承诺越界。

高权重 Guidance：

- Risk
- Recall
- Question
- Talking Point

禁止：欺骗、操纵性心理画像、秘密推断对方“底价/真实情绪”。

---

# 5. v2 IA：Profile Switcher，而不是导航爆炸

全局 Shell 保留品牌、Person、Library、History、Settings。

左上新增 Profile Switcher：

```text
成竹
[ 面试 ▾ ]
```

Interview 激活时继续显示 v1 IA：

```text
首页
求职目标
练习
我的成竹
资料库
历史
设置
```

Conversation 激活时：

```text
首页
对话空间
我的成竹
资料库
历史
设置
```

右上全局动作：

```text
[开始]
```

根据当前 Profile 自动进入对应 Preflight。

不增加：

- Meeting；
- 1:1；
- Design Review；
- Client Call；
- Negotiation

作为一级导航。它们只是创建 Conversation Space / Session 时选择的模板。

---

# 6. Conversation 主循环

```text
Space
→ Next Focus
→ Prepare
→ Session Pack
→ Preflight
→ Participate
→ Continue
→ Next Focus
→ same Space
```

v1 Interview：

```text
Goal → Prepare → Practice → Live → Reflection
```

v2 Conversation：

```text
Space → Prepare → Participate → Continue
```

二者共享：

- Context Compiler；
- provenance；
- audio/ASR；
- screen context；
- Fast Cue；
- Quick Notes；
- Pin；
- Expression Profile；
- local analytics；
- export/delete；
- desktop sidecar。

---

# 7. Conversation Home

首页只回答四件事：

1. 下一场是什么？
2. 我欠谁什么？
3. 还有什么没有决定/回答？
4. 现在最值得准备什么？

建议第一屏：

```text
Next Conversation
Next Focus
Owed by Me
Waiting / Open Questions
Recent Change
```

禁止：

- meeting productivity score；
- engagement percentile；
- sentiment gauge；
- influence score；
- “领导力 87%”。

---

# 8. Conversation Room

Header：

```text
PDIG · Android Architecture
技术设计评审 · 明天 15:00

[概览] [准备] [会话] [决策]

                         [准备下一场] [开始]
```

## 概览

- Next Focus；
- Next Session；
- Open Commitments；
- Open Questions；
- Recent Decisions；
- relevant participants；
- last session delta。

## 准备

- Session Goal；
- Agenda；
- Brief；
- previous unresolved items；
- relevant decisions；
- relevant sources；
- Quick Notes；
- expected questions；
- precomputed contribution candidates；
- Session Pack Preview。

## 会话

所有真实 Session 与 Continue。

## 决策

以时间和 supersession 链显示：

- Proposed；
- Agreed；
- Superseded；
- source；
- who said/confirmed；
- related objection；
- follow-up。

---

# 9. Before / During / After

## Before — Prepare

成竹生成的是 **Brief**，不是长报告：

- 上次发生了什么；
- 未完成 Commitment；
- open questions；
- relevant decisions；
- agenda；
- participants / roles（仅已知）；
- 用户希望达成什么；
- Quick Notes；
- 推荐带入的来源。

## During — Participate

第一视觉层只允许当前最高价值 Guidance：

```text
Current Topic
↓
One Guidance
↓
Source / Confidence / Warning
```

其余 transcript、notes、history、references 后置。

## After — Continue

第一屏：

- What changed；
- Decisions；
- Commitments；
- Open Questions；
- Pins；
- Follow-up；
- Next Focus。

全文 transcript / summary 是第二层。

---

# 10. 七类 Guidance

1. **RECALL** — 从过去可靠来源调出当前相关信息。
2. **TALKING_POINT** — 有值得补充的事实/观点。
3. **ANSWER_CUE** — 直接问题的 glanceable 回答提示。
4. **QUESTION** — 当前重要未解决问题。
5. **RISK** — 冲突、事实边界、承诺风险。
6. **DELIVERY** — 表达结构/节奏提示。
7. **CONTRIBUTION_OPPORTUNITY** — “值得在这个时机开口”的高价值机会。

每一类都必须经过统一 Guidance Arbiter，Live 不得同时堆七张卡。

---

# 11. Assistance Modes

### Quiet
仅 direct question / critical risk / manual ask。

### Balanced（默认）
Direct question + 高价值 Recall / Opportunity / Question。

### Active
更积极的 Talking Point 与 Open Question，但仍受 suggestion budget 和打断成本控制。

### Presentation
结构、时间、Q&A、audience framing 优先。

### 1:1
关系连续性、承诺、follow-up、敏感表达优先。

Mode 改变优先级，不改变事实边界、权限或 provenance。

---

# 12. Expression Planner

Expression Planner 是 Answer Planner 的父概念。

允许动作：

```text
SILENT
ANSWER
RECALL
ADD_TALKING_POINT
ASK_QUESTION
FLAG_RISK
CLARIFY
SUMMARIZE
COMMIT_NEXT_STEP
```

输入：

- Conversation Goal；
- Current Topic；
- explicit audience role；
- explicit concerns；
- decision authority（已知/明确）；
- relationship context；
- Conversation State；
- selected evidence；
- user expression profile；
- policy；
- latency / interruption budget。

输出：

- 是否说；
- 对谁说；
- 说什么类型；
- 多长；
- 用什么来源；
- 哪些风险；
- render as cue / caution / question / silence。

底线：

> **调整表达，不改写事实。**

---

# 13. Counterparty State

只允许保存可观察或明确输入：

- role；
- explicit priority；
- explicit concern；
- stated position；
- decision authority（如明确）；
- relationship context；
- source；
- confidence。

UI 分层：

```text
Known / Explicit
Inferred / Temporary
Unknown
```

禁止把：

- “他不高兴”；
- “他想压价”；
- “他不信任你”；
- “他是某种人格”

作为确定长期事实。

Inference 默认 session-scoped，有 TTL，不自动写入长期 Memory。

---

# 14. Conversation Item Truth Model

一等实体：

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

共享状态：

```text
PROPOSED
AGREED
COMMITTED
DONE
SUPERSEDED
UNKNOWN
```

并增加 review/provenance 层：

```text
AI_EXTRACTED
USER_CONFIRMED
USER_EDITED
USER_REJECTED
SOURCE_CONFIRMED
```

规则：

- transcript segment 是 source，不是 truth；
- AI summary 不能作为唯一 source；
- Decision 的 AGREED 必须有明确证据或用户确认；
- Commitment 必须有 owner；
- Deadline 必须带来源；
- 冲突的新 Decision 通过 SUPERSEDED 连接旧 Decision，不直接删除；
- item 的 owner、speaker、due、state 均可独立不确定。

---

# 15. Live Guidance Arbitration

实时顺序不是固定“多卡并排”，而是动态 arbitration。

硬优先级：

```text
Direct Question / Answer Cue
> Critical Risk
> High-confidence Recall
> High-value Contribution Opportunity
> Open Question
> Delivery
```

抑制规则：

- 用户正在连续说话 → 默认不弹主动建议；
- 新 direct question → 取消旧 Opportunity；
- 最近已表达同义内容 → suppress；
- 低 provenance 的个人事实 → 不主动提示；
- source visibility 不允许 → 不进入候选集；
- stale context → 降权或取消；
- Balanced 模式受 suggestion budget；
- social risk 高 → 倾向 SILENT。

任何时刻最多一个 primary Guidance。

---

# 16. Privacy / Consent 作为产品面

Conversation 比 Interview 涉及更多第三方数据，Preflight 必须明确：

- Capture Mode；
- Transcript retention；
- Processing Mode：Local / Cloud / Off；
- participants consent status（用户报告）；
- participant transparency plan（用户报告：口头告知 / chat 告知 / 已告知 / 不适用）；
- selected sources；
- connector permissions；
- screen context；
- AI Assistance Policy；
- Human Assistance Policy；
- Share Privacy；
- external write-back policy。

默认：

```text
Local-first
No auto-share
No auto-send
No auto-create external task
No biometric identity
No emotion/sentiment profiling
No hidden-intent claims
```

Botless / sidecar 的透明性必须单独处理：参与者同意状态与“如何告知参与者”不是同一个字段。当前成竹不会自动发送 chat notice 或 watermark，因此只能记录用户的 transparency plan / report，不能声称系统已经通知他人。

此外 Preflight 必须展示 **resolved runtime data path**。Capture locality、STT locality、inference locality、retention locality 与 write-back locality 不得混为一个“Local”标签。若用户选择的 policy 与真实 runtime path 不一致，必须 fail-closed；Capture start 还要二次校验，防止 Preflight 后配置变化。

当前未接线的 Conversation Screen Context、Human Coach、Private Overlay / Share Privacy 与 external connector permission 必须显式阻断，不能把 policy 选择伪装成已生效能力。

外部 action 先进入 Review Queue，再由用户确认。

---

# 17. Integration Strategy

## Phase 1 — Desktop Sidecar

优先复用：

- system audio；
- mic；
- ASR；
- overlay；
- screenshot/screen context；
- shortcuts。

平台无关支持 Zoom / Teams / Meet / 腾讯会议 / 飞书等。

## Phase 2 — Read-only Context Connectors

Calendar / docs / mail / project tracker 仅作为 Prepare/Continue source。

连接器不成为 truth authority。

## Phase 3 — Reviewed Write-back

支持：

- create task draft；
- follow-up draft；
- issue draft；
- decision log draft。

默认必须用户确认，不允许“模型自己认为同意了”就写入组织系统。

## Phase 4 — Organization（Future）

只有个人 v2 被真实验证后再考虑 team decision registry / shared commitments / org permissions。

---

# 18. Evaluation

v2 不以“摘要准确率”作为核心。

核心指标：

- Recall Precision；
- Source Attribution Accuracy；
- Direct Question Detection；
- Decision/Commitment State Precision；
- Opportunity Precision；
- Interruption Regret；
- Duplicate Suggestion Rate；
- Guidance Adoption；
- Useful Silence Rate；
- Continue Write-back Accuracy；
- cross-session continuity；
- deletion/export integrity；
- latency / recovery。

评测必须区分两层：

**本地可直接观测 proxy**：
- source attribution coverage；
- guidance adoption / dismissal；
- suppression；
- duplicate suppression；
- review queue；
- approved draft rate；
- latency / recovery；
- deletion / export integrity。

**必须真人标注**：
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

adoption 不得偷换成 precision，synthetic success 不得偷换成 real-user value。

原则：

> **对于主动提示，Precision > Recall。少弹一个，比错弹一个更好。**

---

# 19. 无真实用户时的证据边界

允许：

```text
V2_DESIGN_COMPLETE
V2_CONTRACT_COMPLETE
V2_RUNTIME_AVAILABLE
SYNTHETIC_ENGINEERING_PROVEN
INTERNAL_DOGFOOD_EVIDENCE
```

只有经过 packaged/release gate 后才允许：

```text
V2_PRODUCTIZED_RELEASE
```

禁止在真实用户证据前声称：

```text
V2_PMF_PROVEN
REAL_MEETING_VALUE_PROVEN
REAL_CONVERSATION_TRANSFER_PROVEN
REAL_USER_COGNITIVE_LOAD_PROVEN
```

---

# 20. 设计完成定义

v2.0-R1 设计完成必须同时存在：

- research / competitive synthesis；
- product definition；
- object model；
- data / provenance model；
- Conversation State；
- Counterparty State；
- Expression Planner；
- Opportunity Engine；
- Guidance Arbiter；
- all profile templates；
- IA；
- Before / During / After；
- Studio / Preflight / Live / Continue UI；
- privacy/consent；
- connectors/write-back；
- eval；
- rollout；
- implementation master goal；
- executable contract types；
- no false implementation / release / validation claim。

对应实现总目标：

- [v2.0-R1 Implementation & Rollout Master Goal](Chengzhu_v2.0-R1_IMPLEMENTATION_MASTER_GOAL.md)

本版已经从“允许进入 implementation”推进为“设计完整 + Beta runtime 已存在”。下一状态升级必须依赖 PR/CI、packaged runtime、release provenance 或真实用户证据，不能仅靠文档声明。
