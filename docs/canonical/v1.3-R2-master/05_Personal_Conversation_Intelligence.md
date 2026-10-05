# 69A. Future Profile — Personal Conversation Intelligence

> **本章完整继承 v1.1-R1 第 56–71 节的长期方向，并按 v1.2-R2/v1.3-R2 已冻结的 Provenance、InterviewPack、Policy、Goal-centered UX 术语重新整理。**
>
> 本章的地位是 **Canonical Future Profile**：它规定未来怎么扩，但不把完整 Meeting 产品提前列入 v1.3-R2 的工程 Done Definition。

## 69A.1 为什么它是自然扩展，而不是另一个产品幻想

Interview 已经逼迫 Chengzhu 解决一组极难、同时又高度可泛化的问题：

- 实时听懂连续语音；
- 判断当前真正的问题/意图；
- 维护长会话状态；
- 从大量个人资料中只挑此刻有用的上下文；
- 区分个人事实、用户确认、知识与现场推理；
- 在很短时间内给可扫读 Cue；
- 决定回答多长、以什么结构回答；
- 记录用户真正说了什么，而不是把 AI 建议当作用户行为；
- 会后把真正值得保留的信息写回长期 Memory。

会议、汇报、答辩、1:1、客户电话与谈判需要的是同一类能力，只是从：

```text
“别人问我什么，我怎么答？”
```

进一步扩展为：

```text
“现在发生了什么？”
“这和我过去的事实、决策、承诺有什么关系？”
“此刻我是否值得开口？”
“应该回答、补充、追问、提醒，还是保持沉默？”
“面对这个对象，应如何表达同一个事实？”
```

因此长期产品不是另造一个 AI Meeting Notes，而是把当前 Interview Core 泛化为：

> **Personal Conversation Intelligence：基于用户自己的资料、历史、目标和当前会话，在真正需要的时刻，帮助用户回忆、判断、组织和表达属于自己的内容。**

## 69A.2 长期产品结构：一个 Core，多种 Conversation Profile

未来建议产品结构：

```text
Chengzhu Core
│
├── Interview Profile        ← 当前 v1.x 第一垂直
│
└── Conversation Profile     ← 条件触发的第二垂直
    ├── Meeting
    ├── Presentation / Q&A
    ├── 1:1
    ├── Design Review
    ├── Client Call
    └── Negotiation
```

不是做六套应用，而是共享同一套：

- Person Representation；
- Goal / Session Representation；
- Provenance / Assertion Boundary；
- Context Compiler；
- Conversation State；
- Memory；
- Voice / Expression Profile；
- Fast Cue / Overlay；
- Audio / ASR；
- Screen Context；
- Review / Reflection；
- Policy / Privacy。

Profile 只负责定义：场景目标、允许的 Guidance 类型、优先级、UI 表层、数据实体和评测标准。

## 69A.3 Interview → Conversation 的正式泛化映射

| Interview | Future Conversation | 说明 |
|---|---|---|
| Candidate Representation | Person Representation | 从“求职候选人”扩展为用户长期职业/项目事实世界 |
| Job Goal | Conversation Goal | 从岗位目标扩展为会议、项目、决策或关系目标 |
| InterviewPack | ConversationPack / SessionPack | 某次会话允许带入的冻结上下文 |
| Interview State | Conversation State | 当前话题、开放问题、决策、承诺、冲突、pending action |
| Interviewer State | Counterparty State | 角色、显式优先级、已表达 concern、决策权限；禁止读心 |
| Answer Planner | Expression Planner | 不只回答，还决定是否说、怎么说、说给谁 |
| Review / Debrief | Reflection / Continue | 会后把 Decision、Commitment、Task、OpenQuestion 延续下去 |
| Job-specific Quick Notes | Session Quick Notes | 用户自己准备的会中短记忆 |
| Nudge | Talking Point / Opportunity | Interview 中轻量提示未来泛化为真正表达机会识别 |

这种映射意味着 v1.3 的 Goal-centered 对象模型并不是只为面试服务，它已经是未来第二垂直的稳定地基。

## 69A.4 Person Representation：不再只有“候选人”视角

未来 Person 结构可以扩展为：

```text
Person
├── Identity / Role
├── Projects
├── Experience
├── Skills / Knowledge
├── Decisions
├── Commitments
├── Preferences
├── Communication Style
├── Relationships
├── Claims / Assertions
└── Provenance / Sources
```

Interview Profile 只读取与求职相关的 Person slice。

Conversation Profile 需要额外关心：

- 当前角色；
- 所属项目；
- 过去决定；
- 尚未完成的承诺；
- 关系上下文；
- 沟通偏好；
- 哪些信息允许在当前会话可见。

仍然坚持 v1.2-R2 语义：

> **Provenance 只能证明“系统持有什么来源”，不能替用户宣布现实世界绝对真伪。**

## 69A.5 Conversation Goal / Session Representation

Interview 里的 Goal = Company + Role。

未来 Conversation Goal 可以是：

```text
Goal
├── conversation_type
├── project / account
├── agenda
├── desired_outcomes
├── expected_decisions
├── constraints
├── related_people
├── related_materials
├── open_questions
└── success_criteria
```

示例：技术设计评审 Goal：

```text
目标：决定 Android offline sync v2 是否进入 implementation
希望结果：明确方案、owner、deadline
必须澄清：冲突合并策略、迁移成本、rollback
相关资料：ADR-024、上次 benchmark、线上 crash report
```

## 69A.6 ConversationPack：未来会话的冻结上下文根

沿用 InterviewPack 的核心原则：**开始会话后，不允许 runtime 偷偷读取“最新全局状态”替换本场上下文。**

未来 ConversationPack 建议包含：

```text
ConversationPack
├── person_context
├── conversation_goal
├── project_context
├── related_decisions
├── related_commitments
├── selected_materials
├── quick_notes
├── counterparty_known_context
├── expression_profile
├── policy
├── privacy
└── content_hashes / source_versions
```

会中新增事实以 Session Event 形式追加；需要修改 Pack 时创建 revision，而不是原地漂移。

## 69A.7 Conversation State：从问题链扩展到共同讨论状态

未来 Conversation State 至少维护：

```text
current_topic
previous_topic
topic_stack
speaker_focus
open_questions
claims
proposals
decisions
commitments
unresolved_conflicts
objections
pending_actions
next_decision_needed
```

关键不是“生成更长摘要”，而是支持实时判断：

- 当前话题是否已经切换；
- 某个问题是否一直没有被回答；
- 某个 proposal 是否已被同意；
- 某个 commitment 是谁做出的；
- 当前是否存在值得提醒的历史冲突。

## 69A.8 Counterparty State：只记录可观察信息，不做心理推断

Meeting/1:1/客户场景中，系统可以维护：

- participant role；
- known priorities；
- explicit concerns；
- current stated position；
- decision authority；
- relationship context；
- confidence / uncertainty。

禁止把：

- “他不高兴”；
- “他想压价”；
- “他不信任你”；

这类模型推断直接写成事实。

UI 必须区分：

```text
Known / Explicit
Inferred / Low confidence
Unknown
```

## 69A.9 Expression Planner：Answer Planner 的通用父概念

Expression Planner 不只是“怎么回答”。

它的核心决策空间是：

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

输入建议：

```text
Conversation Goal
Current Topic
Audience / Counterparty Role
Relationship Context
Decision Authority
Selected Evidence
Conversation State
Opportunity Candidates
User Expression Profile
Policy
```

输出至少决定：

- 现在是否应该说；
- 是回答、补充、追问还是保持沉默；
- 应该说给谁听；
- 要多长；
- 应用哪些来源；
- 是否存在事实/承诺风险；
- 展示一个 Cue、Caution 还是完整建议。

底线不变：

> **调整表达，不改写事实。**

## 69A.10 Future Meeting / Conversation 的七类 Live Guidance

### A. Recall

帮助用户从自己的历史中调出当前真正相关的信息。

例：

> 上周你已经承诺 10 月 3 日完成接口联调。

必须带来源；如果只是模型推断，则显示不确定性。

### B. Talking Point

当前讨论中，用户有一个尚未被提到、但值得补充的事实或观点。

例：

> 可以补充：上一轮真实用户测试已经覆盖这个失败路径。

### C. Answer Cue

有人直接向用户提问时，沿用 Interview 的 Cue-first 设计：

- 3–5 点；
- 可扫读；
- 来源清晰；
- Deep 解释后置。

### D. Question

识别当前尚未解决、但值得用户追问的问题。

例：

> 上线日期讨论过了，但最终验收 owner 还没确定。

### E. Risk / Contradiction

当前讨论与过去可追溯信息可能冲突。

例：

> 当前说法可能与 9 月 20 日评审中的 Android-first 决策不一致。

系统必须：

- 给来源；
- 给不确定性；
- 不直接断言别人“说错了”；
- 区分历史条目是否已经被 SUPERSEDED。

### F. Delivery

只在价值明确时提醒表达层问题：

- 先结论；
- 回答过长；
- 语速过快；
- 重复；
- 缺具体数字；
- 缺 next step。

不把 filler word 计数做成产品中心。

### G. Contribution Opportunity

这是 Conversation Profile 最值得形成差异化的能力。

系统判断：

> **当前讨论里，我有没有一条真正相关、尚未被提出、而且我有可靠来源的信息值得说？**

例：

别人说：

> “我们好像从来没做过这种 benchmark。”

而用户资料中存在去年的 benchmark。

成竹只给轻提示：

> **你有相关信息：2025 Q4 Benchmark，可补充。**

它不是自动替用户抢话，而是让用户看见“值得贡献的时机”。

## 69A.11 Contribution Opportunity Detection

不能把每条相关检索结果都弹出来，否则产品会成为新的干扰源。

建议保留 v1.1 的基础评分思想，并按当前 Provenance 语义扩展：

```text
Opportunity Score =
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

只有超过 profile-specific threshold 才允许提示。

特别规则：

- 直接提问始终高于主动 Opportunity；
- 新问题到来时立即压制旧 Opportunity；
- 用户正在连续表达时默认不弹；
- 已经说过的同义内容不重复；
- 低 provenance 的个人事实不得作为主动 Talking Point；
- 社交风险高时宁可沉默。

## 69A.12 Conversation Assistance Modes

未来 Conversation Profile 建议支持：

### Quiet

只处理直接提问、明确风险和用户主动 Ask。

适合：高风险会议、正式汇报。

### Balanced（默认）

直接问题 + 高价值 Recall / Opportunity / Question。

### Active

允许更多 Talking Point、Open Question 与 Nudge。

### Presentation

演讲结构、时间、Q&A 和 audience question 优先。

### 1:1

关系连续性、承诺、follow-up 和敏感表达优先。

这些模式只是 Guidance priority，不改变事实边界或权限策略。

## 69A.13 Stakeholder-aware Expression

同一事实面对不同角色应改变结构，而不是改变事实。

例：“项目预计延期两周”。

```text
对 CTO
依赖 / 架构原因 / 技术风险 / rollback

对直属老板
影响 / 日期 / mitigation / decision needed

对客户
结果影响 / 新预期 / 承诺 / next checkpoint

对合作团队
接口变化 / 依赖 / owner / integration plan
```

Expression Planner 必须读取：

- audience role；
- explicit concern；
- conversation goal；
- decision authority；
- relationship context；
- user expression profile。

不得读取或生成“对方真实心理状态”作为确定输入。

## 69A.14 Conversation 数据与 Provenance 模型

未来 Meeting 比 Interview 更需要 provenance，因为它会涉及真实组织决策和承诺。

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

每个实体至少带：

```text
id
conversation_id
speaker / owner
source
source_excerpt
timestamp
confidence
provenance_status
visibility
created_at
updated_at
```

状态特别需要区分：

```text
PROPOSED
AGREED
COMMITTED
DONE
SUPERSEDED
UNKNOWN
```

核心规则：

- “有人提出”不能自动升级为“团队决定”；
- “看起来大家没反对”不能自动升级为 AGREED；
- Commitment 必须有 owner；
- Deadline 必须能追溯来源；
- 新 Decision 与旧 Decision 冲突时，旧条目应标 SUPERSEDED，而不是直接删除；
- AI 摘要不是原始来源。

## 69A.15 Before / During / After 三阶段体验

### Before — Prepare

成竹自动准备：

- 上次相关 Conversation 发生了什么；
- 仍未完成的 Commitment / Task；
- 当前 agenda；
- 与自己相关的项目状态；
- 可能被问到什么；
- 自己希望达成什么；
- Quick Notes；
- 哪些历史 Decision 可能与本次相关。

### During — Assist

优先级建议：

```text
Direct question
→ Answer Cue

High-confidence relevant memory
→ Recall

Conflict with tracked history
→ Caution

High-value missing contribution
→ Talking Point / Contribution Opportunity

Important unresolved item
→ Question
```

默认保持极简、私有、低打扰。

### After — Continue

会后不是只生成纪要，而是生成可继续工作的结构：

- 新 Decision；
- 新 Commitment；
- Task；
- Deadline；
- Risk；
- OpenQuestion；
- 用户自己的 follow-up；
- Reflection；
- 下一场 Conversation 的 Prepare input。

任何长期写回仍受 Provenance / User Confirmation / Policy 控制。

## 69A.16 Future UI：Conversation Profile 不是复制 Interview 页面

### Studio：Conversation Room

建议 future IA 只在 v2.0 激活后出现，不提前占用 v1.3 顶层导航。

Conversation Room 示例：

```text
PDIG · Android Architecture Review
明天 15:00 · 6 人

[概览] [准备] [Sessions] [Decisions]

Next Focus
• 决定 conflict merge strategy
• 上次遗留：migration owner 未确认

Open Commitments
• 我：补 benchmark · 10/02
• Backend：确认 schema compatibility · 未定

[Prepare] [Start Session]
```

### Preflight

```text
本次目标
Agenda
参与者 / 角色（已知）
相关项目资料
历史 Decisions
Open Commitments
Quick Notes
Guidance Mode: Balanced
AI Policy
Human Assistance
Share Privacy
Screen Context
```

### Live Conversation Cockpit

默认不铺满七种提示，只显示当前最高价值的一类：

```text
● Listening

当前话题
Android offline migration

Recall
上周你承诺今天补 benchmark。
来源：Design Review · 09/24
```

或：

```text
Talking Point
你有相关信息：Q4 benchmark 已覆盖 10x data scale。

[展开来源] [Pin] [忽略]
```

或：

```text
Question
上线日期确定了，但 migration owner 还没有明确。
```

用户始终可以：

- Pin；
- snooze；
- dismiss；
- 展开来源；
- 降低主动程度。

### After / Continue

```text
这场之后

Decisions
• Android offline sync v2 进入 implementation

Commitments
• 我：10/03 补 migration benchmark

Open Questions
• rollback owner 未确认

Next Focus
• 下次同步先确认 rollback owner
```

## 69A.17 Meeting 不是“纪要产品”

Transcript / Summary 可以存在，但它们是：

- Conversation Memory 输入；
- Review/Continue 的来源；
- Decision/Commitment extraction 的证据。

不把“自动会议纪要”作为 Chengzhu 的战略差异。

真正主价值发生在：

> **During Conversation。**

也就是：在正确时刻帮用户知道什么值得说、为什么值得说、有没有来源、怎么表达，以及什么时候最好不要打断。

## 69A.18 平台集成路线

### Phase 1：平台无关 Desktop Sidecar

优先复用 Chengzhu 已有桌面能力：

- 系统音频；
- 麦克风；
- ASR；
- Overlay；
- Screenshot / Screen Context；
- Shortcuts。

优点：

- 腾讯会议 / Teams / Zoom / Google Meet / 飞书等统一；
- 不等待每个平台实时 API；
- 复用 Interview 已验证的低延迟链路。

### Phase 2：官方 Connector / MCP / Calendar

当用户授权时读取：

- Calendar event；
- agenda；
- related docs；
- project source；
- approved notes；
- action tracker。

作用是 Prepare 和 Continue，不把连接器变成事实 authority。

### Phase 3：组织工作流（Future）

只有个人 Conversation Profile 被验证后再考虑：

- team decision registry；
- shared commitments；
- org permissions；
- CRM / issue tracker / project system write-back。

不在 v2.0 第一版一次做全。

## 69A.19 Privacy / Permissions / Visibility

Conversation Profile 比 Interview 更容易涉及第三方和组织数据，因此必须默认更严格：

- Local-first；
- 每场明确输入源；
- 录音/转写遵循用户所在场景和适用规则；
- 不默认上传原始音频；
- 参与者身份不确定时不强行识别；
- Counterparty inference 不变成长期事实；
- 组织来源需要 visibility / permission；
- 用户可删除 Conversation 与派生 Memory；
- Export 必须区分 transcript、AI guidance、personal notes、Decision/Commitment 数据；
- API key 永远不进入 export。

Human Coach 仍只是一个独立 `HUMAN_COACH` Guidance Source，不等于 Conversation Profile 本身。

## 69A.20 Personal Conversation Intelligence 的未来 Evaluation

不能只测“摘要准确率”。真正的评测维度应包括：

### Recall Precision

提示的历史信息是否真的与当前话题相关、来源是否正确。

### Opportunity Precision

主动提示中，有多少是真正值得用户开口的；重点控制 false positive。

### Interruption Cost

系统是否在用户/他人正在表达时制造不必要干扰。

### Decision State Accuracy

PROPOSED / AGREED / COMMITTED / DONE / SUPERSEDED 是否被正确区分。

### Commitment Attribution

owner、deadline、source 是否正确。

### Contradiction Quality

是否能识别真实冲突，同时避免把新旧版本正常演进误报成矛盾。

### Expression Usefulness

针对角色的表达建议是否保留原事实、是否真正更适合当前 audience。

### Longitudinal Continuity

上一场 Decision / Commitment 能否在下一场正确被 Recall，而不是被旧摘要污染。

### Silence Quality

最重要的指标之一：**该沉默时能不能沉默。**

## 69A.21 Conversation Profile 的激活 Gate

完整 Meeting/Conversation 产品只有在以下条件成立后才进入正式开发：

1. Interview Goal 被真实用户持续复用；
2. Reflection → Next Focus 能实际改变下一场准备；
3. Fast Cue 被用户真正采用，而不是机械照读；
4. Fact Inbox / Provenance 不成为维护负担；
5. v1.3 Goal-centered IA 已稳定；
6. v1.x Core 的 Context/Policy/Memory/Pack 不需要为 Meeting 大改；
7. 能找到一个足够窄、频率高的第二垂直进行验证。

建议第一验证垂直：

```text
项目周会 / 技术设计评审
```

理由：

- 项目事实可追溯；
- Decision / Commitment 高价值；
- 与当前技术用户画像高度重合；
- 可以直接复用 Screen/Docs/Quick Notes/Context Compiler；
- Contribution Opportunity 的价值容易观察。

## 69A.22 Conversation Profile 第一版 MVP

第一版不要做万能会议助手。

只做：

### Before

- 上次发生什么；
- 未完成 Commitment；
- 本次 Goal；
- Quick Notes。

### During

- Recall；
- Answer Cue；
- Talking Point；
- Question；
- Risk / Contradiction。

Contribution Opportunity 先在高阈值下灰度。

### After

- Decision；
- Commitment；
- Task；
- OpenQuestion；
- Next Focus。

暂不做：

- 复杂组织管理；
- CRM；
- 自动替用户发言；
- 多组织权限中台；
- 销售全流程 Copilot；
- remote control；
- 情绪/心理状态推断。

## 69A.23 Interview 与 Conversation 的共享护城河

长期真正的护城河不是“多了一个 Meeting Tab”，而是：

```text
Person Context
×
Provenance
×
Longitudinal Memory
×
Conversation State
×
Context Compiler
×
Expression Planner
×
Cue-first Realtime UX
×
Contribution Opportunity
```

Interview 提供高压、高价值、强真实性约束的第一验证场景。

Conversation Profile 则把同一内核扩展到更高频的职业交流。

因此长期产品定义应保持：

> **Chengzhu helps you know what is worth saying, when to say it, and how to say it without losing the truth of what is actually yours.**

中文：

> **成竹理解你的资料、历史、目标和当前对话，在真正需要的时刻，帮助你想起该想起的、说出值得说的，并始终守住属于你的事实边界。**

## 69A.24 当前版本边界再次确认

尽管本章已经完整定义 Future Profile，v1.3-R2 当前 release scope 仍是 Interview。

当前不新增：

- Meeting 一级导航；
- Meeting Room production UI；
- Calendar/Teams/Zoom/Meet connector；
- 组织 Decision Registry；
- Sales Copilot；
- 自动会议纪要商业化主线。

v1.3 当前应该先把：

```text
Goal Room
Quick Notes
Practice
Live
Reflection
```

真正做成熟。

Future Profile 的价值是：**最新 Canonical 不再丢失长期方向，同时所有 v1.3 设计选择都能检查是否会阻塞未来泛化。**

---
