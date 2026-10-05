# 成竹 Chengzhu v1.3-R2
## Goal-centered Interview Operating System｜Verified Interview Core × Goal-centered Experience × Personal Conversation Intelligence Future Profile
### 产品 · AI 系统 · 实时工程 · 数据 · UI/UX · 桌面端 · 评测 · 隐私 · 商业化统一全量设计母版

**版本**：v1.3-R2  
**日期**：2026-10-01  
**状态**：CANONICAL MASTER CANDIDATE  
**中文品牌**：成竹  
**英文品牌**：Chengzhu  
**品牌来源**：胸有成竹  
**英文品牌句**：Ready before you speak.  
**中文品牌句**：胸有成竹，从容上场。  
**许可证决策**：MIT（仓库代码）；第三方资产遵循各自许可证。  
**核心产品原则**：Goal-centered；Interview-first；Resume-first, not Resume-bound；Evidence before assertion；Cue before essay；Complexity behind the interface.  

> **v1.3 的核心不是继续增加模块，而是把 v1.2-R2 已经很深的系统能力压缩成一个普通求职者自然理解、自然使用、能够重复循环的产品。**

---

# 0. 文档地位、继承关系与 v1.3 修订原则

本文件完整继承 v1.2-R2 中已经冻结的技术和治理原则，包括 MIT、Provenance 与 Truth 分离、InterviewPack 真冻结、Context Compiler 唯一上下文 authority、用户感知 TTFUG、Fast Cue、Stream Guard、AI/Human/Share Privacy 三轴 Policy、Session Statement、Cross-session Learning、Windows 可安装发行与 GitHub Release Gate。

v1.3-R2 不推翻这些底层能力，而是补上此前最明显的一层缺口：**产品体验模型**。

本版同时补齐此前最新母版中的一个重要缺口：**将 v1.1-R1 已经详细设计、但在 v1.3-R1 中仅保留路线图标题的 Personal Conversation Intelligence / Meeting Future Profile 完整纳入当前 Canonical**。这只是设计与接口层的完整继承，**不把完整 Meeting UI 提前进入 v1.3 的工程交付范围**。

v1.2-R2 已经解决“系统应该怎样正确地理解候选人、岗位、事实、会话和上下文”；v1.3-R2 进一步解决：

> **普通用户为什么打开成竹？他现在正在追哪个岗位？下一步应该做什么？正式面试时屏幕上应该只出现什么？面试结束后如何自然进入下一轮准备？**

因此本版把 UI 与产品对象从“模块中心”改成“目标中心”。

正式冲突优先级：

1. 当前真实 runtime / DB / release artifact / repository / CI evidence；
2. 本 v1.3-R2；
3. v1.2-R2 技术与治理定义；
4. v1.1-R1；
5. v1.0-R1 与旧 DESIGN.md / PRODUCT.md 仅作为 provenance。

本版继续坚持：

- Chengzhu 当前仍然是 **Interview-first**；
- 不在本版产品化完整 Meeting；
- 不大爆炸重写；
- 不迁 Tauri；
- 不为了“架构高级”强制 Neo4j / PostgreSQL / pgvector / 微服务；
- 不把后端模块数量直接映射成导航项；
- 不用虚假的准备度、通过率、面试成功率制造确定性；
- 不把用户在 Live 中需要理解的东西变成工程术语。

本版新增一句产品层原则：

> **The system can be complex; the user's next action cannot be.**

---

# 1. v1.3-R2 的核心升级

v1.3-R2 冻结十六项产品体验与长期架构决策：

1. **Goal 成为求职主对象**：一个 Goal = 一家公司 × 一个岗位 × 一个长期求职上下文；Prepare、Practice、Sessions、Debriefs、Offer 都围绕 Goal 聚合。
2. **顶层导航继续收敛**：不再把“准备、上场、复盘”都当一级功能中心；Live 是动作/模式，Review 是 Session 结果。
3. **Studio / Live Cockpit 是两种状态，不是两个页面模块**：用户从 Goal 或全局 Go Live 经过 Preflight 自动切换。
4. **首页从 Dashboard 变成 Action Home**：只回答“下一场是什么、现在最值得做什么、哪里存在 blocker”。
5. **Goal Room 成为产品高频中心**：Overview / Prepare / Interviews / Offer，一切围绕某一岗位。
6. **Fact Inbox 代替 Evidence Graph 数据库感 UI**：底层仍是图，用户看到的是“需要你确认的 4 件事”。
7. **Material Taxonomy 正式分层**：Resume、JD、Project Material、Knowledge Base、Quick Notes、Question Banks、Skills/Stories 不再混成“文件”。
8. **Quick Notes 正式进入 InterviewPack**：它是用户写给自己看的现场材料，不是 Evidence，也不是可检索 KB。
9. **Command Palette / Contextual Actions 成为复杂功能的收纳层**：减少每张卡片铺满按钮。
10. **Guided First Practice 成为 Onboarding 最后一步**：第一次使用不以“设置完成”为结束，而以真实跑通一轮音频→问题→Cue→Overlay→Review 为结束。
11. **Practice 进一步产品化**：支持 round、persona、demeanor、difficulty、question bank、dynamic follow-up；未来可做 panel/multi-persona。
12. **Practice / Review 将 Content Coach 与 Delivery Coach 分离**：事实/技术深度与表达节奏不混成单一分数。
13. **Live 新增轻量 Nudge / Open Thread**：只在高置信、无新问题时提示“还能补什么/可能被追问什么”，不抢占 Fast Cue。
14. **Closing Mode 成为正式 Interview Mode**：当面试官问“你有什么问题想问我”时，基于本场真实对话生成有上下文的问题，而不是 generic 模板。
15. **Pin Moment / User Judgment 优先**：用户可一键标记“这题很重要/我答崩了/对方说了关键信息”，Review 优先处理用户主动标记的时刻。
16. **完整保留 Personal Conversation Intelligence Future Profile**：Interview 仍是当前第一垂直，但 Person / Goal / Session / Conversation State / Counterparty State / Expression Planner、七类会中 Guidance、Contribution Opportunity、Decision/Commitment 数据模型和平台集成路线正式纳入本 Canonical，避免长期方向被后续版本意外丢失。

这十六项不是增加十六个导航按钮，而是减少用户在系统中的认知跳转，并让当前 Interview Core 与未来 Conversation Profile 共享同一长期架构。

---

# 2. 2026-10-01 当前 GitHub 真实状态与 v1.3 起点

仓库：`huangdi97/cheng-zhu`

本文再次核验时：

- 默认分支：`main`；
- `main` HEAD：`a660f86255babc07b9749749ca5178be433bd601`；
- PR #1–#4 已合并；
- 当前公开 Latest Release：`v1.2.2`；
- Release 已包含 Windows installer、portable、SHA256、MIT LICENSE、THIRD_PARTY_NOTICES 与 release notes；
- v1.2.2 已解决非中文 Windows 首启与本地 CPU Whisper preview/final 资源竞争问题；
- 当前 v1.2.x 已形成可安装、可运行、可回归的 Verified Interview Core，v1.3 不需要重做该内核。

当前公开工程事实只代表本文生成时的 GitHub 快照。后续实现状态继续以新的 runtime / Git / CI / release artifact 为准，不得为了匹配本文而 reset 到旧 SHA。

v1.3-R2 的工程策略因此正式改为：

- **冻结 v1.2-R2/v1.2.2 已经验证的实时核心行为**；
- v1.3 主要推进 Goal-centered IA、Goal Room、Quick Notes、Command Palette、Practice/Reflection 产品化与 Live 表层体验；
- Future Conversation Profile 只完成 Canonical、共享数据模型、接口边界与未来 Gate，不进入当前一级导航和 release scope；
- 任何 UI / Product 改造不得破坏已关闭的 InterviewPack、Provenance、Context Authority、Fast Cue、Stream Guard、Policy 与 release gate。

---
# 3. 深度市场研究：真正值得借鉴的不是“功能表”，而是产品组织方式

本轮重点研究 FinalRound AI、AskCc、GhostInterview、Yoodli、Hedy、Granola，以及 Linear / Raycast 这类成熟桌面工作流产品。研究结论不用于照抄视觉，而用于回答一个问题：

> **当一个产品底层能力越来越多，怎样让用户仍然只看到一个清楚的下一步？**

## 3.1 FinalRound AI：Goal Room + Loop + Studio/Cockpit

FinalRound 最新桌面产品最值得借鉴的不是实时 Copilot 本身，而是 Goal：一个 Goal 对应一家公司和一个岗位，Resume、Prep、Practice、Live Session、Debrief 都归属于这个 Goal。[S1][S2]

其 Goal Room 的 Overview 不是大盘，而是 Next Focus、What We Know、Recent Sessions、Next Interview；Prep 承载材料和练习，Sessions 承载历史。[S1]

另一个关键点是 Studio / Cockpit：主窗口是平静的准备/回顾状态，只有开始 Session 后才进入小型浮动 Live 状态，中间有短 Preflight。[S2][S3]

**吸收：**

- Goal 成为 Chengzhu 求职主对象；
- Go Live 是动作，不是一级导航；
- Preflight 是 Studio→Live 的正式边界；
- 首页和 Goal Overview 优先给 Next Focus，而不是准备度百分比。

## 3.2 AskCc：技能档案不是抽取结果，而是审核生命周期

AskCc 的优势在于把 Resume/JD/个人知识、技能档案和现场使用连接成一条明显链路。其公开功能强调“共享面试档案”和项目技能档案，重点不是模型能抽取，而是用户能在面试前把自己的项目事实整理成稳定资产，再用于现场。[S4]

**吸收：**

- Skill Card 不能只是 AI 自动抽取结果；
- “需要确认”比“事实数据库”更适合作为 UI；
- 团队成果、个人职责、指标、trade-off 都要有用户审核步骤；
- Approved Personal Context 才能进入 InterviewPack。

## 3.3 GhostInterview：材料分类、Quick Notes、Reference Fragment、Debrief、Duo

GhostInterview 明确区分 Resume、JD、Quick Notes、Knowledge Base：Resume 代表经历，JD 代表目标岗位，Quick Notes 是用户自己现场阅读的短笔记，Knowledge Base 是 Ask AI 可检索资料。[S5]

其 Knowledge Base 有 Processing / Ready / Failed 生命周期，而且 Interview Record 能展开当时提供给模型的 reference fragments。[S5]

GhostInterview 还把 Quick Notes 做成桌面面试中的独立面板，并提供快捷键展开/收起。[S8]

Interview Debrief 的一个重要原则是：分析用户真正说出的内容，而不是把 AI 建议当作候选人表现证据；同时反馈聚焦下一次准备，而不是为每题制造技术评分。[S7]

Duo 证明 Human Helper 的浏览器协作、细粒度分享和 AI/Human source label 是真实产品需求，但 Chengzhu 继续采用更严格的 Human Assistance Policy。[S6]

**吸收：**

- Material Taxonomy；
- Quick Notes；
- Processing state；
- Review 中显示 Context/Reference fragments；
- Candidate actual speech 与 AI suggestion 永久分离；
- Human Coach 只作为独立 Guidance Source。

## 3.4 Yoodli：Practice 才是可以主动设计的训练场

Yoodli 的 Practice 支持 interview roleplay、动态 follow-up、自定义 question bank、interviewer demeanor，并允许构建 persona / multi-persona roleplay。[S9][S10]

这意味着成竹无需把所有复杂 coaching 都塞进真实 Live。Practice 是最适合：

- 人格化面试官；
- 压力模式；
- panel interview；
- delivery feedback；
- 高强度追问；
- Human Coach；
- Cue adoption 分析

的场景。

**吸收：** Practice 从“Mock 页面”升级成独立训练系统，但仍挂在 Goal 上。

## 3.5 Hedy：主动 Suggestion / Blind Spot / Talking Point

Hedy 的差异是“建议在你发问之前出现”，并将 Suggestion、Blind Spot、Talking Point 作为不同类型的会中提示，同时跨 Session 继承上下文。[S11][S12]

Chengzhu 不应照搬成会议助手，但可以在 Interview 内引入非常克制的 Nudge：

- “还能补一句 reliability”；
- “可能继续追问一致性”；
- “别忘了问清前三个月目标”。

Nudge 只在 Fast Cue 之后、没有新问题、置信度足够时出现，不抢占核心回答。

## 3.6 Granola：用户的判断是第一等信号

Granola 的 AI-enhanced notes 将用户自己写下的 raw notes 与 transcript 一起作为生成输入，并允许用户追溯增强内容来自哪里。[S13]

这给成竹一个重要启发：不要假设 AI 能判断每个“重要时刻”。用户应该有一个极轻的 `Pin Moment`：

- 这题很重要；
- 我答崩了；
- 对方透露了关键信息；
- 这段要放进下次准备。

Review 优先处理用户主动 Pin 的时刻。

## 3.7 Linear / Raycast：复杂产品不等于按钮越来越多

Linear 使用 contextual command menu，让动作跟随当前选择；Raycast 允许用户直接搜索 Settings 和命令，而不是记住每个选项藏在哪里。[S14][S15]

**吸收：**

- `Ctrl+K` / Command Palette；
- 右键/`...` Contextual Actions；
- Settings Search；
- 边缘功能进入命令层，不永久占界面。

## 3.8 综合产品结论

市场上的成熟形态大致可以分为：

```text
Goal / Workflow Layer        FinalRound
Personal Context Layer       AskCc
Technical Live Layer         GhostInterview
Practice / Coaching Layer    Yoodli
Proactive Intelligence       Hedy
Human Judgment Layer         Granola
Desktop Interaction Layer    Linear / Raycast
```

Chengzhu 的目标不是把七套 UI 拼在一起，而是形成自己的统一闭环：

```text
Goal
↓
Know Me
↓
Prepare What Matters
↓
Practice Under Pressure
↓
Freeze InterviewPack
↓
Cue-first Live
↓
Reflect on What I Actually Said
↓
Next Focus
↓
same Goal
```

---

# 4. 产品定义：Goal-centered Interview Operating System

成竹当前定义升级为：

> **成竹 Chengzhu 是一个 Goal-centered Interview Intelligence 产品：以“我要拿下某个具体岗位”为长期工作对象，从真实个人资料建立可追溯的候选人上下文，在准备、演练、正式面试和复盘之间保持同一条状态链，并在 Live 中以最短可扫读 Cue 帮助用户表达真实的自己。**

“Interview Operating System” 是产品组织比喻，不表示它是操作系统软件。它强调：

- 不围绕聊天框组织；
- 不围绕一堆 AI 功能组织；
- 不围绕某一个 Session 组织；
- 而是围绕用户正在推进的 Job Goal 组织所有材料、准备、Live 和学习。

底层仍然是 v1.2-R2 的：

```text
Candidate Representation
+ Provenance / Assertion Policy
+ InterviewPack
+ Interview State
+ Context Compiler
+ Answer Planner
+ Fast Cue
+ Deep Answer
+ Controlled Memory
```

但用户不应该需要理解这些术语才能使用产品。

---

# 5. 产品闭环 3.0：Goal → Next Focus → Practice → Preflight → Live → Reflection

用户的自然闭环固定为：

```text
Create / Select Goal
        ↓
Next Focus
        ↓
Prepare
        ↓
Practice
        ↓
Preflight
        ↓
Live
        ↓
Reflection
        ↓
Next Focus
        ↓
Same Goal / Next Round
```

其中：

- **Next Focus** 是所有复杂分析的产品出口；
- **Prepare** 不是一个孤立一级模块，而是当前 Goal 下的工作区；
- **Practice** 可以跨 Goal，但最好从 Goal 启动；
- **Preflight** 是正式冻结 InterviewPack 的边界；
- **Live** 是状态；
- **Reflection** 是 Session 完成后的结果；
- **History** 是跨 Goal 浏览历史 Session 的入口，但不是学习闭环的终点。

这个闭环的设计要求：每一步只给用户一个主要下一动作。

---

# 6. 用户角色与核心 Jobs-to-be-Done

## 6.1 Candidate

用户真正的 Jobs-to-be-Done 不是“我要使用 Context Compiler”，而是：

- 明天要面这家公司，我今晚最该准备什么？
- 这个项目面试官最可能从哪里继续挖？
- 我知道答案，但现场一紧张组织不出来怎么办？
- 这个问题我能讲知识，但我到底有没有真实做过？
- 我刚才是不是说错了一个事实？
- 这场面完，下一场我最应该改什么？

## 6.2 Practice Coach / Friend

Human Coach 的首要场景是：

- Mock；
- Pair practice；
- Career coach；
- 明确允许第三方辅助的 Session。

不把“真实正式面试中的隐蔽真人外援”作为默认产品定位。

## 6.3 Future Roles

未来可能有：

- Mentor；
- Interview Trainer；
- Team Coach；
- School Career Center。

v1.3 不增加组织管理产品。

---

# 7. 产品能力全景 3.0：用户对象与系统能力分层

## 7.1 用户真正看到的七个对象

```text
Home
Goals
Me
Practice
Library
History
Settings
```

Live 通过全局 `Go Live` 进入，不作为常驻一级导航。

## 7.2 Goal 内部对象

```text
Goal
├── Overview
├── Prepare
├── Interviews
└── Offer
```

## 7.3 Me 内部对象

```text
Me
├── Overview
├── Resume
├── Projects
├── Fact Inbox
├── Stories
├── Skills
└── Expression
```

## 7.4 Library 内部对象

```text
Library
├── Project Materials
├── Knowledge Bases
├── Quick Notes
└── Question Banks
```

## 7.5 系统底层能力保持隐藏

```text
Candidate Representation
Provenance Graph
Interview State
Context Compiler
Retrieval
Answer Planner
Truth / Assertion Guard
Memory
Telemetry
```

它们属于系统，不属于导航。

---

# 7A. 五个核心产品对象：Person × Goal × Pack × Session × Reflection

为了避免模块继续膨胀，v1.3 用五个稳定对象统一整个产品。

## Person

“我是谁、我实际做过什么、我怎样表达”。

包含 Resume、Projects、Claims、Sources、Stories、Skills、Expression Profile。

## Goal

“我要拿下哪个岗位”。

一个 Goal = Company + Role + JD + interview plan + job-specific material selection + sessions + offer state。

## InterviewPack

“这一场真正带进去什么”。

它是 Goal + Person 在某一轮 Session 的冻结物，不是 UI 中让用户管理版本号的技术对象。

## Session

“一次真实或模拟面试发生了什么”。

包括 Practice / Live / Phone / In-person capture 等 Session Kind。

## Reflection

“这场之后应该改变什么”。

Reflection 产生 Next Focus、Knowledge Gap、Fact Inbox item、Story Opportunity、Practice Recommendation。

五个对象之间的稳定关系：

```text
Person ─────────────┐
                    ├─> InterviewPack ─> Session ─> Reflection
Goal ───────────────┘                         │
   ▲                                         │
   └────────────── Next Focus ───────────────┘
```

---

# 7B. Goal Room：产品高频中心

Goal Room 是 Chengzhu 最重要的 Studio 页面。

Header：

```text
MindRank · AIDD Agent Engineer
技术二面 · 10/02 14:00

[概览] [准备] [面试] [Offer]                  [开始演练] [上场]
```

## Overview

默认只展示四类内容：

1. Next Focus；
2. What We Know；
3. Next Interview；
4. Recent Sessions。

Wireframe：

```text
┌───────────────────────────────────────────────────────────┐
│ MindRank · AIDD Agent Engineer             [演练] [上场] │
├───────────────────────────────────────────────────────────┤
│ 下一步                                                    │
│                                                           │
│ Redis Cluster 是当前最高优先事实边界                      │
│ 你能解释 Redis，但没有生产 Cluster 经历来源。             │
│                                                           │
│ [准备这个问题]                                            │
├─────────────────────────┬─────────────────────────────────┤
│ 已经建立                │ 下一场                          │
│                         │                                 │
│ ✓ RAG architecture      │ 技术二面                        │
│ ✓ Agent orchestration   │ 10/02 · 14:00                  │
│ ! scale reasoning       │                                 │
│ ! ownership story       │ [Preflight]                     │
├─────────────────────────┴─────────────────────────────────┤
│ 最近面试                                                  │
│ 技术一面 · 28min · 8 turns · “System Design depth”       │
└───────────────────────────────────────────────────────────┘
```

禁止默认出现：

- 准备度 87%；
- Offer probability；
- “你超过 92% 候选人”；
- 没有方法学依据的综合分。

---

# 7C. Material Taxonomy：文件不是同一种东西

v1.3 正式把材料按用途分类，而不是全部扔进“知识库”。

| Material | 用户语义 | 系统用途 | 是否能证明个人经历 |
|---|---|---|---|
| Resume | 我的正式经历摘要 | Candidate seed | 可以作为来源之一 |
| Project Material | 项目 README / 设计文档 / 产物 | Candidate / Evidence / Knowledge | 需要显式用途 |
| JD | 目标岗位 | Goal context | 否 |
| Knowledge Base | 技术参考 | Retrieval | 默认否 |
| Quick Notes | 我自己现场想看的短笔记 | Direct display / Pack | 否 |
| Question Bank | 练习题来源 | Practice | 否 |
| Skill Card | 用户审核后的项目能力资产 | Candidate / Live | 可关联来源 |
| Story | 用户确认的真实行为故事 | Behavioral | 可关联来源 |

上传 Project Material 时必须让用户选择：

```text
这个文件主要用于：
● 项目事实与来源
○ 技术参考
○ 两者都是
```

Knowledge Base 默认不能作为“我做过”的证据。

---

# 7D. Quick Notes：用户写给自己的现场短记忆

Quick Notes 是 v1.3 正式新增的一等产品资产。

它不是：

- Evidence；
- Knowledge Base；
- Memory；
- AI 生成答案。

它是用户自己写、自己负责、自己现场看的短笔记。

例：

```text
MindRank Quick Notes

Redis
- session state
- TTL
- 没用过 Cluster

RAG
- hybrid retrieval
- rerank
- eval

想问
- Agent production scale
- team size
```

能力：

- Goal-specific；
- Global reusable；
- pin；
- reorder；
- keyboard open/collapse；
- InterviewPack 选择；
- Live 只读为主；
- Review 可建议“把这个加入 Quick Notes”，但不自动写入。

---

# 7E. Command Palette 与 Contextual Actions

全局：

```text
Ctrl + K
```

命令按当前上下文排序。

Home：

- 创建 Goal；
- 打开下一场；
- 开始演练；
- Go Live。

Goal：

- 继续准备；
- 新建 Quick Note；
- 开始 Practice；
- Preflight；
- 添加材料。

Live：

- 展开/收起 Overlay；
- 打开 Quick Notes；
- 截图；
- Pin Moment；
- 标记刚才为口误；
- 重答最新问题；
- 切换 Compact / Focus。

Contextual menu：

```text
Redis session state     有直接来源     ⋯
```

`⋯`：

- 查看来源；
- 编辑；
- 用户确认；
- 添加来源；
- 用它练一道题；
- 加入 Quick Notes；
- 删除 Draft。

Settings 支持全文搜索，不要求用户记住选项在哪个 section。

---

# 7F. Guided First Practice：Onboarding 的完成标准

第一次启动流程不以“API Key 保存成功”为结束，而以跑完一个 5 分钟 Guided Practice 为结束。

流程：

```text
Welcome
↓
Local data explanation
↓
Model / STT
↓
Microphone test
↓
System audio test
↓
Import Resume
↓
Create / Skip Goal
↓
Guided First Practice
```

Guided First Practice：

1. 播放一条测试 interviewer question；
2. 检查系统音频；
3. 显示 ASR partial；
4. 出现 Fast Cue；
5. 用户打开一次 Overlay；
6. 用户试一次 Quick Notes；
7. 用户试一次截图；
8. 用户说一段回答；
9. 结束后显示 Demo Reflection。

最后状态：

> **“你的成竹已经可以进行一次完整 Session。”**

如果某一步失败，给具体修复入口，而不是通用“初始化失败”。

---

# 7G. Practice 3.0：Persona × Round × Difficulty × Question Bank

Practice Setup：

```text
目标
MindRank · AIDD Agent Engineer

轮次
● 技术一面
○ 项目深挖
○ System Design
○ Hiring Manager
○ HR

面试官风格
● 中性
○ 友好
○ 强追问
○ 怀疑型
○ 快节奏

难度
○ 热身
● 标准
○ 压力

题目来源
✓ Goal Question Graph
✓ Recent Weakness
✓ My Question Bank
```

Practice 的 AI interviewer 可以比 Live 更“主动”，包括：

- 追问；
- 质疑；
- 打断模拟；
- 改变约束；
- 要求量化；
- 要求 ownership；
- 结束时反问。

v1.3-R2 可先做单 Persona；Multi-persona / Panel Interview 进入 v1.3.x / v1.4。

---

# 7H. Content Coach × Delivery Coach

Practice 与 Review 的反馈拆成两层。

## Content Coach

关注：

- 事实边界；
- 是否回答问题；
- 技术深度；
- 结构；
- trade-off；
- ownership；
- missing evidence；
- follow-up resilience。

## Delivery Coach

关注：

- 结论出现时间；
- 回答长度；
- 语速；
- 停顿；
- 重复；
- 口头填充；
- 是否过度背稿。

不合并成一个“83 分”。

更好的反馈是：

> “技术内容完整，但前三个回答的结论平均在 17 秒后才出现。下一轮训练先做 15 秒结论式回答。”

Live 中 Delivery analytics 默认关闭；Practice 本地分析优先。

---

# 7I. Pin Moment：让用户判断什么最重要

Live / Practice 全局动作：

```text
Ctrl + P  Pin Moment
```

可选标签：

- 重要；
- 我答崩了；
- 对方透露关键信息；
- 下一场要准备；
- 事实需要确认。

系统保存：

- timestamp；
- current question；
- current turn；
- short surrounding transcript；
- optional user note。

Review 第一屏优先展示用户 Pin 的内容。

---

# 7J. Nudge / Open Thread：主动但克制

Nudge 是 Fast Cue 之后的弱提示，不是另一个答案。

类型：

```text
Missing Dimension
Likely Follow-up
Fact Boundary
Ask-back Opportunity
```

例：

```text
还可以补一句
Reliability / failover
```

```text
可能继续追问
数据一致性
```

触发条件：

- 当前没有新问题；
- 置信度高；
- 用户没有关闭 proactive guidance；
- 不打断用户正在说话；
- 1 个时刻最多显示 1 条。

用户可关闭 Nudge，而不关闭 Fast Cue。

---

# 7K. Closing Mode：把“你有什么想问我”变成真正的上下文能力

当 Question Understanding 判断进入 interview closing / candidate questions 阶段：

自动切换 Closing Mode。

输入：

- Job Goal；
- Company context；
- 这一场 interviewer 透露的信息；
- 已讨论问题；
- 用户 Quick Notes 中“想问”；
- 未解决 open threads。

输出优先三类：

1. 追问刚才真实出现的信息；
2. 了解前三个月 success criteria；
3. 了解团队真实工作方式/技术挑战。

例：

```text
刚才您提到团队正在把 Agent 从内部工具推到 production，
当前最难的是 eval、infra 还是业务侧 adoption？
```

禁止默认给一组 generic：

- 公司文化怎样？
- 日常工作是什么？

除非当前上下文确实没有更具体的信息。

---

# 7L. Language Layering

正式拆四层：

```text
UI Language
Interview Language
Answer Language
Coding Language
```

再加：

```text
Technical Term Policy
```

例如：中国技术面试常见设置：

```text
UI        中文
Interview 自动检测 / 中文
Answer    跟随面试
Coding    Python
术语      保留英文
```

不要让一个 `language=zh` 同时控制 ASR、UI、LLM 和 code。

---

# 8. 核心架构：Candidate × InterviewPack × State × Context × Planner

R2 核心不再只写：

```text
Candidate Representation
× Interview State
× Context Compiler
× Answer Planner
```

而正式升级为：

```text
Candidate Representation
        │
        ├── Claims
        ├── Provenance
        ├── User Assertions
        ├── Skills
        ├── Stories
        └── Voice
        │
        ▼
Job Goal / Company / JD
        │
        ▼
Build InterviewPack
        │
        ▼
Freeze
        │
        ├─────────────┐
        │             │
        ▼             ▼
Interview State   Session Events
        │             │
        └──────┬──────┘
               ▼
       Context Compiler
               │
        ┌──────┴──────┐
        ▼             ▼
   Fast Context   Deep Context
        │             │
        ▼             ▼
 Guidance      World Reasoning
 Generator      + Answer Planner
        │             │
        └──────┬──────┘
               ▼
        Stream Truth Guard
               │
               ▼
         Live Guidance
```

整个链路受三类硬边界约束：

```text
Provenance Boundary
Assertion Boundary
Session Assistance Policy
```

R2 不把 Human Coach 混在核心事实层；Human Coach 只是另一条 Guidance Source。

---

# 9. Candidate Representation 2.0

Candidate Representation 不只是解析简历，而是长期维护用户真实职业世界的结构化表示。

建议实体：

```text
Candidate
├── Education
├── Experience
├── Project
├── Skill
├── Claim
├── Provenance / Source
├── Story
├── Voice Profile
└── Version
```

每条 Claim 不能只是一段字符串，应逐步具备：

```text
subject
predicate/action
object
role
scope
project_id
metric
value
unit
time_range
source_ids
provenance_status
user_assertion_status
created_at
updated_at
```

示例：

```text
subject = Candidate
predicate = use
object = Redis
role = contributor
scope = session_state
project = WenNian
provenance_status = DIRECT_EVIDENCE
user_assertion_status = UNREVIEWED
source = resume_v4
```

“使用 Redis”不能自动推出“使用 Redis Cluster”；“参与”不能自动推出“主导”。

---

# 10. Claim Lifecycle 2.0：Provenance ≠ Truth

R1 的 VERIFIED / SUPPORTED / INFERRED / UNKNOWN / CONTRADICTED 把多种语义混在了一条“真值轴”上。R2 正式拆成三个独立维度。

## 10.1 Provenance Status

描述“当前系统拥有的来源如何覆盖这个陈述”，不是描述现实世界绝对真伪。

```text
DIRECT_EVIDENCE
SUPPORTING_EVIDENCE
NO_EVIDENCE
CONFLICTING_EVIDENCE
```

### DIRECT_EVIDENCE

来源直接覆盖该具体陈述。

例如：Resume 明确写“Redis 用于 session state”。

### SUPPORTING_EVIDENCE

来源支持核心事实，但不是逐字覆盖完整范围。

### NO_EVIDENCE

当前没有可用来源覆盖。

### CONFLICTING_EVIDENCE

不同来源对同一陈述出现实质冲突。

## 10.2 User Assertion Status

描述用户本人是否明确确认。

```text
UNREVIEWED
USER_CONFIRMED
USER_DENIED
```

`USER_CONFIRMED` 只意味着：

> 用户明确表示这件事真实。

它**不等于**系统拥有独立证据。

因此完全允许：

```text
Provenance = NO_EVIDENCE
UserAssertion = USER_CONFIRMED
```

UI 应显示：

> “用户已确认；当前没有独立来源覆盖。”

而不是 VERIFIED。

## 10.3 Session Status

```text
NOT_STATED
SESSION_STATED
SESSION_CORRECTED
```

只描述用户当前 Session 里有没有说过。

它不改变长期 Provenance，也不自动改变 User Assertion。

## 10.4 Assertion Policy

新增独立决策：

```text
ALLOW_PERSONAL_ASSERTION
ALLOW_WITH_QUALIFIER
REQUIRE_BOUNDARY
KNOWLEDGE_ONLY
BLOCK_ASSERTION
```

由：

```text
Provenance
× User Assertion
× Session Status
× Truth Requirement
× Current Session Policy
```

共同决定。

## 10.5 典型例子

### “我用了 Redis”

如果 Resume 有直接来源：

```text
DIRECT_EVIDENCE
USER_CONFIRMED（可有可无）
```

可以自然表达。

### “我用了 Redis Cluster”

如果只有 Redis：

```text
NO_EVIDENCE
UNREVIEWED
```

不能因为字符串重叠推断。

### “我负责整个系统”

如果来源只写“参与”：

必须把 role scope 视为不同 Claim，不能自动升级 ownership。

## 10.6 UI 语言

普通用户界面避免显示“Truth verified”。

改为：

- 有直接证据；
- 有支持材料；
- 暂无证据；
- 来源冲突；
- 用户已确认；
- 用户已否认；
- 本场曾口述；
- 本场已纠正。

---

# 11. Evidence / Provenance Graph 2.0

Evidence Graph 在 R2 中更准确地称为 **Provenance Graph**：它管理来源关系，而不是宣称自己拥有现实真相。

核心关系：

```text
Claim ──directly_supported_by──> Evidence
Claim ──supported_by───────────> Evidence
Claim ──conflicted_by──────────> Evidence
Claim ──derived_from───────────> Source
Claim ──belongs_to─────────────> Project / Experience
Story ──contains───────────────> Claim
SessionStatement ──refers_to───> Claim
```

Evidence 类型：

- Resume excerpt；
- 用户手工确认；
- Project README / Design Doc；
- GitHub artifact；
- 用户导入的工作材料；
- Review-confirmed transcript；
- external public record；
- user note。

Knowledge Base 文档默认是知识来源，不自动成为个人经历 Evidence。

文件上传时允许用户标记：

```text
Knowledge Reference
Evidence Source
Both
```

即使标为 Evidence Source，也只能说明“该文档包含支持材料”，不能跳过 Claim scope 匹配。

R2 的核心原则：

> **证据图回答“系统为什么认为这句话可以/不可以作为个人事实表达”，而不是替用户做现实世界审判。**

---

# 12. “我的成竹”必须成为个人事实与来源管理产品

Claim / Provenance 如果只存在 SQLite 表和后台 API，就不是产品能力。

正式增加：

## 我的成竹 → 事实与来源

用户看到的是：

- 事实陈述；
- 所属项目/经历；
- Provenance Status；
- User Assertion Status；
- 来源；
- 冲突；
- 是否在当前/历史 Session 被口述；
- 哪些回答曾使用；
- 最近修改。

示例：

```text
有直接证据
我在 WenNian 中使用 Redis 管理 session state

来源：
Resume v4
Project README

用户确认：已确认
```

另一个：

```text
暂无证据
我在生产中使用 Redis Cluster

用户确认：已确认
说明：当前没有独立资料覆盖这一陈述。
```

用户操作：

- 确认；
- 否认；
- 修改；
- 补来源；
- 合并重复；
- 删除错误 Draft；
- 查看被哪些 InterviewPack 使用；
- 查看 Session Statement 历史。

任何 AI 抽取出的新个人 Claim 默认：

```text
UNREVIEWED
```

不能自动变成 USER_CONFIRMED，更不能因为模型“很确定”而变成 DIRECT_EVIDENCE。

---

# 13. Job Representation 2.0

每个目标岗位形成独立 Job：

```text
Company
Role
Level
Responsibilities
Must-have
Nice-to-have
Technologies
Competencies
Interview Signals
Company Context
```

Candidate × Job Alignment 状态：

- STRONG_MATCH；
- PARTIAL_MATCH；
- KNOWLEDGE_MATCH；
- GAP；
- UNKNOWN。

避免伪精确“87% 匹配度”。

用户更需要：

> 哪三件事我有证据？哪两件事我会但没做过？哪一件必须今晚补？

---

# 14. Job Workspace

当前已实现 Gap Map、Attack Surface、Question Graph、Stories prompt，应提升为正式 Prepare 核心页面。

## Gap Map

来源：

- JD Alignment；
- Review knowledge_weakness；
- repeated_topic；
- 用户手工标记；
- 未来官方题库/面经趋势。

## Attack Surface

优先：

- 带指标的 Claim；
- 与 JD 强相关的 Claim；
- 容易被验证真假的 Claim；
- 技术决策和 trade-off；
- 简历一句话但背后深度很大的 Claim。

## Question Graph

不是题目列表，而是树：

```text
项目经历
└── 为什么这样设计？
    ├── 为什么不用替代方案？
    ├── 如何评估？
    └── 如果规模扩大 100 倍？
```

Gap 类：

```text
Knowledge
└── Experience Boundary
    └── Open Design
```

---

# 15. Question Understanding 2.0：三轴 + 唯一路由函数

R2 保留三轴，但增加一个非常重要的约束：

> **整个系统只能存在一个正式 Answer Routing Function。**

不能 `question_understanding.py` 一套路由、`answer_planner.py` 一套、eval 又一套兼容别名。

## 15.1 Dialogue Act

描述“这句话在对话中做什么”：

- NEW_QUESTION；
- FOLLOW_UP；
- CLARIFICATION；
- CHALLENGE；
- INTERRUPTION；
- META；
- TRANSITION。

## 15.2 Content Type

描述“问题在问什么”：

- INTRODUCTION；
- EXPERIENCE；
- PROJECT_DEEP_DIVE；
- KNOWLEDGE；
- CODING；
- SYSTEM_DESIGN；
- OOD；
- BEHAVIORAL；
- PRODUCT；
- CASE；
- DATA_ML；
- HYPOTHETICAL；
- RECRUITER；
- NEGOTIATION；
- COMPANY_ROLE_FIT。

## 15.3 Truth Requirement

描述“回答是否需要个人事实”：

- PERSONAL_FACT_REQUIRED；
- PERSONAL_FACT_RELEVANT；
- KNOWLEDGE_ONLY；
- HYPOTHETICAL_ALLOWED；
- SCREEN_CONTEXT_REQUIRED。

## 15.4 唯一 Routing Function

建议纯函数：

```text
route_answer(
  dialogue_act,
  content_type,
  truth_requirement,
  provenance_state,
  user_assertion_state,
  current_policy
) -> ResponseMode
```

Response Mode：

- EXPERIENCE；
- EXPERIENCE_KNOWLEDGE；
- EXPERIENCE_BOUNDARY_KNOWLEDGE；
- KNOWLEDGE；
- HYPOTHETICAL；
- OPEN_DESIGN；
- CODING；
- SYSTEM_DESIGN；
- OOD；
- BEHAVIORAL；
- PRODUCT_CASE；
- NEGOTIATION。

## 15.5 示例

> “那如果流量扩大 100 倍呢？”

```text
dialogue_act = FOLLOW_UP
content_type = HYPOTHETICAL / SYSTEM_DESIGN
truth_requirement = HYPOTHETICAL_ALLOWED
```

> “你实际在生产用过 Redis Cluster 吗？”

```text
dialogue_act = FOLLOW_UP
content_type = EXPERIENCE
truth_requirement = PERSONAL_FACT_REQUIRED
```

如果只有 Redis Evidence，则 route 应进入：

```text
EXPERIENCE_BOUNDARY_KNOWLEDGE
```

## 15.6 Eval 必须区分 exact 与 compatible

过去“expected OPEN_DESIGN，actual SYSTEM_DESIGN 也算 route pass”的宽松做法可以保留为 semantic-compatible 指标，但不能再计入 exact route accuracy。

最终报告必须同时给：

```text
exact_route_accuracy
semantic_compatible_accuracy
```

不能用后一项冒充前一项。

---

# 16. Interview State 2.0

状态必须持续理解：

```text
active_topic
active_project
previous_topic
question_chain
open_threads
resolved_question
candidate_claims_spoken
interviewer_focus
screen_problem
current_job
turn_version
```

核心要求：

- topic reset；
- interruption；
- follow-up resolution；
- crash restore；
- bounded memory；
- 不让 stale context 污染新问题。

面试官状态仍然只能作为 planner hint，不是事实。

Interviewer State 输出应更保守：

```text
high / medium / low
+ evidence trail
```

而不是向用户展示“真实性 82%”这种伪精确数字。

---

# 17. InterviewPack：真正的冻结运行对象

R1 的 `Interview Pack Snapshot` 方向正确，但“保存一堆 version ID”仍然不足以保证 Live 不漂移。

R2 正式把它定义成：

> **InterviewPack = 开始一场 Interview 时真正冻结并成为 Live Context 根对象的不可变运行包。**

## 17.1 InterviewPack 内容

```text
InterviewPack
├── id / session_id / revision
├── candidate_context
├── claims
├── provenance_refs
├── skill_cards
├── stories
├── job
├── job_alignment
├── company_context
├── selected_kb
├── voice_profile
├── AI policy
├── Human assistance policy
├── Share privacy policy
├── Screen context policy
├── model_profile
├── answer_preferences
├── source_versions
├── content_hashes
└── created_at
```

它不只是 metadata，而是能真正重建本场上下文的 frozen package。

## 17.2 Live 禁止读取全局 latest 状态

Pack 冻结后，Live 主链禁止重新调用：

```text
latest_job_id()
latest_resume()
latest_candidate()
latest_skill_card()
latest_story()
```

ContextCompiler 本场只允许读取：

```text
Frozen InterviewPack
+ Current Question
+ Current Session Events
+ Current Screen Context
+ Allowed World Knowledge
```

## 17.3 更新当前场

如果用户中途明确点击：

> 更新本场资料

不能静默修改原 Pack。

创建：

```text
InterviewPackRevision 2
```

保存旧 revision，Review 能查看某一轮到底基于哪版 Pack。

## 17.4 第一验收用例：A/B 岗位污染

```text
Job A = AI Agent Engineer
Job B = Data Engineer

1. Prepare A
2. Freeze Pack A
3. 后续分析 B
4. 回 A 开始 Live
5. 问题进入 ContextCompiler
6. Assert：B 的 JD、技术要求、Gap 不得出现
```

这是 R2 Snapshot 的最重要 regression fixture。

## 17.5 为什么这是产品能力

冻结不是为了工程洁癖，而是为了用户知道：

> “这场面试的成竹到底基于哪一版我的资料和哪一个岗位。”

Review、Debug、Truth Boundary、Cross-session 都依赖这个可追溯性。

---

# 18. Context Compiler 2.0：从 Integrated 到 Authoritative

当前生产路径已经调用 ContextCompiler，但 R2 的目标不是“调用了”，而是：

> **最终送给模型的用户上下文只能由 ContextCompiler 决定。**

## 18.1 正式 Provider

- InterviewPackCandidateProvider；
- InterviewPackEvidenceProvider；
- InterviewPackSkillCardProvider；
- InterviewPackStoryProvider；
- SessionMemoryProvider；
- LongTermMemoryProvider；
- JobProvider；
- KBProvider；
- ScreenProvider；
- WorldKnowledgePermissionProvider。

## 18.2 Authority Rule

Compiler 成功时：

- legacy Resume 不再重复注入；
- legacy KB hits 不再重复注入；
- legacy Memo 不再重复注入；
- legacy JD 不再重复注入；
- legacy global latest Job 不再重新读取。

Compiler 失败时才能明确 fallback：

```text
compiler_fallback = true
```

并进入 telemetry。

## 18.3 Fragment Identity

每个 fragment：

```text
fragment_id
source_type
source_id
content_hash
score
selected
reason
contradiction_risk
token_estimate
```

最终 prompt 同一逻辑 fragment 最多出现一次。

## 18.4 自动 Gate

至少自动检测：

```text
same Resume excerpt <= 1
same KB hit <= 1
same Skill Card fact <= 1
same JD requirement <= 1
```

同时比较迁移前后：

```text
tokens_before
tokens_after
duplicate_before
duplicate_after
```

目标不是 token 越少越好，而是：

> **去重后仍保持最小充分上下文。**

## 18.5 Review Provenance

每轮必须保存 selected context，Review 可以展开：

> “这一题当时到底给模型看了什么？”

这比“RAG 命中了几个 chunk”更有产品价值。

---

# 19. Retrieval 2.0

当前 KB 使用 SQLite FTS5 + CJK bigram + deadline watchdog，这一实现适合本地桌面，不需要为了“RAG 看起来高级”强制换 Chroma / pgvector。

继续保留：

- lexical / FTS；
- entity exact；
- active-topic；
- job alignment；
- evidence strength；
- recency；
- contradiction risk；
- redundancy penalty。

后续增量：

- optional local embedding；
- dense semantic score；
- local reranker；
- benchmark 后再选择 sqlite-vec / hnsw / 其他本地实现。

原则：**先证明 dense retrieval 能提升命中，再引入依赖。**

---

# 20. 真正 Fast Path：Cue before Essay

R2 对 Fast Path 的定义进一步收紧：

> **Fast Path 不是“模型先输出几个 token”，而是在 Deep Answer 之前独立产出一份用户已经可以据此开始说话的结构化 Cue。**

链路：

```text
Partial ASR
  ↓
Question Hypothesis
  ↓
Speculative Context Prefetch
  ↓
Speech-end Estimate / Stable Question
  ↓
Question Understanding
  ↓
Context Compiler FAST
  ↓
Assertion Constraint
  ↓
Guidance Generator
  ↓
WS: guidance_fast
  ↓
Overlay + Main UI

同时：
Deep Context → Planner → Deep Answer Stream
```

Fast Cue 至少包括：

```text
resolved_question
one_line_direction
3–5 core cues
personal evidence anchors（若有）
knowledge source labels（若有）
cautions
response mode
```

用户看到 Fast Cue 时，Deep Answer 可以还没完成。

## 20.1 Cue 不能是 Planner 标签

下面这些不是 Cue：

```text
结论
机制
边界
验证
```

真正 Cue 必须是内容：

```text
• RAG 更适合频繁更新的知识
• 来源可追溯
• WenNian 可以讲“不需要每次重训”
• 当前没有 fine-tuning 线上训练证据
```

## 20.2 Cue Source

R2 明确四类：

```text
PERSONAL_EVIDENCE
KB_KNOWLEDGE
WORLD_KNOWLEDGE
HUMAN_COACH
```

这些来源必须分开显示和审计。

---

# 21. Predictive Start：不等 1.2 秒 silence 才从零开始

当前 VAD 默认 1.2 秒 silence 是用户感知延迟的重要来源，因此 R2 引入更完整的 speculative pipeline。

## 21.1 Question Hypothesis

partial ASR 期间只形成可撤销对象：

```text
QuestionHypothesis
├── partial_text
├── likely_dialogue_act
├── likely_content_type
├── active_topic_candidate
├── entity candidates
├── confidence
└── created_at
```

## 21.2 partial 阶段允许提前做

- KB prefetch；
- Provenance search；
- current project candidate；
- current Job context prefetch；
- World Knowledge readiness；
- Screen context readiness；
- planner mode hypothesis。

## 21.3 partial 阶段不允许做

- 写 permanent Interview State；
- 创建长期 Claim；
- 把不稳定问题当 final；
- 显示未经稳定问题确认的个人事实 Cue；
- 提交最终 answer。

## 21.4 Stable 后 reconcile

Q1 到来：

- reuse valid prefetch；
- cancel stale retrieval；
- resolve topic reset；
- commit question；
- 立即产 Fast Cue。

R2 的技术目标不是机械把 VAD 从 1.2 改成 0.3，而是用：

```text
partial ASR
+ end-of-turn signal
+ punctuation / lexical cue
+ adaptive VAD
+ rollback
```

共同降低真实等待。

---

# 22. Guidance Generator 2.0：Evidence / Knowledge 分源

Guidance Generator 必须知道“这个 Cue 是从哪里来的”。

## 22.1 Level 0：Deterministic / local

适合：

- Personal Evidence anchor；
- Experience boundary；
- risk；
- InterviewPack 中已知 architecture fact；
- Job-specific current focus。

目标：毫秒级。

对知识题，如果本地上下文没有知识内容，L0 不能凭空创造技术结论。

## 22.2 Level 1：Tiny / Fast Model

适合：

- KNOWLEDGE；
- SYSTEM_DESIGN；
- CODING；
- HYPOTHETICAL；
- 把已选 Evidence / KB / World Knowledge 改写成 3–5 点短 Cue。

限制：

- 60–100 tokens；
- 禁止新增 personal fact；
- Personal Evidence 与 World Knowledge 明确分源；
- 必须经过 Cue Assertion Check；
- tiny provider 失败时 L0 仍可显示风险/证据，Deep Path 继续。

## 22.3 Knowledge Point 来源

R2 不再写模糊的“selected knowledge point”。必须明确来源：

```text
KB_KNOWLEDGE
WORLD_KNOWLEDGE
```

KB 是用户准备资料；World Knowledge 是模型的一般知识。

两者都不能自动变成：

> “我实际做过”。

## 22.4 Human Coach

Human Coach Cue 作为第四来源：

```text
source = HUMAN_COACH
```

它永远不是 Evidence，也不自动改变 Candidate Claim。

---

# 23. TTFUG 2.0：真正按用户感知计时

TTFUG = Time To First Usable Guidance。

R2 正式定义五个时间点：

```text
E  = estimated interviewer speech end
Q0 = first meaningful partial
Q1 = stable / resolved question
G0 = first usable Cue visible
A0 = first Deep Answer token visible
D0 = Deep Answer complete
```

指标：

```text
QBD = Q1 - E

TTFUG_user
= G0 - E

TTFUG_predictive
= G0 - Q0

TTFUG_internal
= G0 - Q1

TTFA
= A0 - Q1

TTD
= D0 - Q1
```

其中主用户指标必须是：

```text
TTFUG_user
```
因为用户真正感受到的是：

> “面试官已经说完多久，我屏幕上才出现第一条能用的提示？”

不能再用：

> “ASR final 之后模型很快。”

掩盖前面的 1.2 秒 silence wait。

## 23.1 初始 Release SLO

在 controlled prerecorded benchmark 中，建议目标：

```text
QBD p50 <= 500ms
QBD p95 <= 900ms

TTFUG_user p50 <= 1.2s
TTFUG_user p95 <= 2.0s
```

这是初始工程 SLO，不是市场承诺；若真实设备不满足，报告真实数字，不修改指标定义。

## 23.2 Telemetry 分段

至少记录：

- partial start；
- estimated speech end；
- stable question；
- prefetch hit；
- compiler start/end；
- L0 cue；
- L1 cue；
- WS send；
- UI render；
- first Deep token；
- Deep complete。

---

# 24. Assertion Boundary 2.0：Pre-Constraint × Stream Guard × Post Audit

R2 将原 Truth Boundary 更准确地理解为：

> **Assertion Boundary：模型什么时候可以把一句话表达成“我做过/我负责/我上线了”。**

## 24.1 第一层：Pre-generation Constraint

Planner 在生成前得到明确 contract：

- 哪些个人 Claim 可直接说；
- 哪些只能 qualifier；
- 哪些必须 boundary；
- 哪些只能讲知识；
- 哪些只能 hypothetical；
- 哪些 metrics / role / project scope 禁止出现。

## 24.2 第二层：Stream-safe Claim Guard

不能把整段答案全部生成完再审，否则 Live 失去实时性。

建议：

```text
token stream
→ current sentence / claim buffer
→ personal-claim detector
→ low risk: release
→ high risk: assertion check
→ release / rewrite / boundary
```

高风险信号：

- 第一人称经历；
- 精确 metric；
- ownership；
- production deployment；
- concrete project；
- leadership；
- “我负责…”；
- “我们上线了…”；
- “我在生产用了…”。

Knowledge / System Design 正常 token 保持流式；只有突然出现的新 personal assertion 局部缓冲。

## 24.3 第三层：Post-generation Audit

完整答案最终再审：

- unsupported personal assertion；
- unexpected metric；
- subject substitution；
- role inflation；
- contradiction；
- internal prompt leakage。

## 24.4 Session Statement 的处理

`SESSION_STATED` 只能：

- 触发 consistency warning；
- 触发“是否口误”提示；
- 进入 Review 待确认。

不能：

- 自动成为 Evidence；
- 自动成为 User Confirmed；
- 自动允许后续模型扩写更多细节。

如果用户说：

> “我们后来用了 Redis Cluster。”

而 Pack 没有来源，系统应提示：

> “你刚才提到了 Redis Cluster，但当前资料没有来源覆盖。如果这是口误可以立即纠正；如果确实发生过，建议会后确认并补来源。”

---

# 25. Answer Planner 2.0

Planner 的职责不是“写答案”，而是：

- 决定 Response Mode；
- 决定 answer structure；
- 决定事实空间；
- 决定深度；
- 决定 Fast Cue 类型；
- 决定 Deep Answer 是否需要；
- 决定 Screenshot / KB / Story / World Knowledge 是否需要。

建议 Response Modes：

- EXPERIENCE；
- EXPERIENCE_KNOWLEDGE；
- EXPERIENCE_BOUNDARY_KNOWLEDGE；
- KNOWLEDGE；
- HYPOTHETICAL；
- OPEN_DESIGN；
- CODING；
- SYSTEM_DESIGN；
- OOD；
- BEHAVIORAL；
- PRODUCT_CASE；
- NEGOTIATION。

---

# 26. Skill Card：必须从 Prep 资产变成 Live 资产

当前 Skill Builder 已经能围绕项目问：

- 背景；
- 角色；
- 技术决策；
- 指标；
- trade-off；
- 踩坑；
- 可能追问。

但 v1.2 必须补齐：

```text
Skill Builder Q&A
      ↓
Draft Skill Card
      ↓
用户审核
      ↓
Claim extraction
      ↓
Evidence mapping
      ↓
Candidate Graph
      ↓
SkillCardProvider
      ↓
Live Context Compiler
```

Skill Card 不能只存在 PrepSpace JSON 里。

---

# 27. Story Bank 2.0

Behavioral Interview 不能靠 AI 临场虚构 STAR。

新增 Story Builder：

```text
缺少 ownership story
      ↓
系统发起问答
      ↓
Situation
Challenge
Action
Result
Reflection
      ↓
抽取 Claims
      ↓
用户确认
      ↓
Story Bank
```

每条 Story：

- 标题；
- competencies；
- STAR/SCARR 结构；
- linked claims；
- evidence；
- truth status；
- 适用问题；
- 最近使用场次。

---

# 28. Personal Voice 2.0

Voice Profile 不等于声音克隆。

它描述：

- 先结论还是先背景；
- 口语短句/长句；
- 技术词是否保留英文；
- 回答目标时长；
- bullet vs narrative；
- 常见表达；
- 用户不喜欢的 AI 套话。

必须可见、可编辑、可关闭。

建议 UI：

```text
我的表达
✓ 先结论后解释
✓ 中文为主，技术词保留英文
✓ 单题 45–90 秒
✓ 少用“首先、其次、最后”
○ 更正式
○ 更口语
```

任何 Voice rewrite 都不能改变事实边界。

---

# 29. Prepare：从一级页面收回 Job Goal Workspace

R2 继续保留 Prepare 能力，但不再把“准备”作为必须的一级导航中心。

Prepare 的正式语义是：

> **某一个具体 Job Goal 的准备工作区。**

入口可以来自：

- 首页“继续准备”；
- 求职 → 某岗位 → 准备；
- Review → “加入下次准备”；
- Gap → “开始准备”。

Prepare 必须回答：

> **我下一场面这个岗位，现在最该准备什么？**

核心内容：

- Job Brief；
- Next Focus；
- Gap Map；
- Attack Surface；
- Question Graph；
- Skill Cards；
- Stories；
- Knowledge Sources；
- Pack Preview；
- Preflight blockers。

不再维护第二套独立于 Job 的 Prepare 对象语义。

---

# 30. Mock / Rehearse 2.0

当前 Mock 已经会：

- Gap-driven question insertion；
- recent weakness priority；
- response analysis；
- dynamic follow-up questions；
- 自动写 Review。

下一步：让 AI interviewer 真正沿 Question Graph 走，而不是“模板 Gap 问题 + follow-up list”。

Mock interviewer 输入：

```text
Job
Candidate attack surface
Question Graph
Weakness memory
Current mock state
Candidate last answer
```

输出：

- 下一问；
- 为什么追问；
- probing intent；
- stop/continue branch。

但任何“用户经历”都只能来自用户回答/已确认材料。

---

# 31. Coding / System Design / OOD 专项体验

成竹底层 Planner 已有结构，但 UI 还需要专项化。

## Coding

Fast Cue：

- 题意一句话；
- 核心算法；
- 复杂度；
- 1–2 edge cases。

Deep：

- clarification；
- approach；
- code；
- complexity；
- tests；
- follow-up optimization。

## System Design

Fast Cue：

- requirements；
- architecture skeleton；
- biggest trade-off；
- first deep-dive target。

Deep：

- FR/NFR；
- capacity；
- API；
- data；
- architecture；
- scaling；
- reliability；
- security；
- observability；
- cost；
- evolution。

## OOD

Fast Cue：

- core objects；
- responsibilities；
- relationships；
- pattern / extension point。

Deep：

- class boundaries；
- interfaces；
- invariants；
- design pattern；
- testability；
- extension trade-offs。

---

# 32. Screenshot / Screen Context

Screen Context 不应是孤立的“看图 AI”。

统一进入 Context Compiler：

```text
spoken question
+
screen prompt / code / diagram
+
Candidate / Job / State
+
Knowledge / Evidence
```

Screen Context 支持：

- 全屏/配置区域；
- 框选区域；
- 多截图序列；
- code/image/diagram problem type；
- vision verify；
- source provenance。

未来 Auto-capture 必须是显式可控 per-session setting。

---

# 33. Knowledge Base 2.0

知识库必须把“知识”和“个人事实证据”区分。

每个文件上传时选择用途：

```text
Knowledge Reference
Evidence Source
Both
```

支持：

- md / txt / log / docx / pdf；
- FTS5；
- optional local embeddings；
- source preview；
- section/page provenance；
- recent hits；
- answer/review 中查看实际提供给模型的 fragments。

这点应借鉴 GhostInterview：Review 中能展开当时提供给 AI 的 reference fragments。

---

# 34. Review / Debrief 2.0

一场面试后，Review 不只回答“表现如何”，而是重建这场发生了什么。

每个 Turn 显示：

- interviewer question raw；
- resolved question；
- candidate actual speech；
- Fast Cue；
- Deep Answer；
- Human Coach Cue；
- selected evidence；
- selected KB fragments；
- route / plan；
- truth warnings；
- latency；
- user correction。

全场：

- strong points；
- weak points；
- repeated topics；
- communication patterns；
- knowledge gaps；
- fact boundary risks；
- Story opportunities；
- next actions。

AI 建议与用户实际说的话必须分开，不能拿 AI 文本当用户表现证据。

---

# 35. Cross-session Learning 2.0

当前已经证明：Review weakness → next Workspace / Mock。

v1.2 补齐：

```text
Review
↓
Controlled Memory
↓
LongTermMemoryProvider
↓
Next Live Context Compiler
```

可自动写回：

- knowledge_weakness；
- repeated_topic；
- communication_profile。

不可自动写回：

- “用户做过 X”；
- 新指标；
- 新项目职责；
- interviewer 对用户能力的猜测。

这些必须走用户确认。

---

# 36. Session Assistance Policy 2.0：AI / Human / Share Privacy 三轴分离

R2 不再把所有现场能力塞进一个 policy。

正式拆为三个互相独立的维度。

## 36.1 AI Assistance Policy

每场 Session：

```text
AI_FORBIDDEN
AI_LIMITED
AI_ALLOWED
AI_EXPECTED
```

### AI_FORBIDDEN

- Prepare / Mock / Review 可用；
- Live AI Guidance server-side hard block；
- 不能只在前端隐藏按钮。

### AI_LIMITED

- transcript 可用；
- 手动 Ask / Screenshot 按规则可用；
- Auto-answer 默认关闭。

### AI_ALLOWED

- 完整 realtime guidance。

### AI_EXPECTED

- 完整 guidance；
- 可允许更主动 Cue。

全局 config 只保存默认值，真正生效值属于 InterviewSession / InterviewPack。

## 36.2 Human Assistance Policy

新增：

```text
HUMAN_FORBIDDEN
HUMAN_PRACTICE_ONLY
HUMAN_ALLOWED
```

默认：

```text
HUMAN_PRACTICE_ONLY
```

含义：

- Mock / Practice 可以使用 Human Coach；
- 正式 Live 不因为 AI_ALLOWED 自动获得 Human Coach；
- 只有用户明确确认场景允许外部人工辅助时才启用 HUMAN_ALLOWED。

## 36.3 Share Privacy

```text
OFF
PRIVATE_OVERLAY
```

默认：

```text
OFF
```

Share Privacy 与 AI / Human policy 独立。

它的目的：

> 减少 Chengzhu 私人资料在受支持的屏幕共享和录制路径中意外暴露。

不是：

> 绕过第三方监控或保证不可检测。

## 36.4 Screen Context Policy

建议每场：

```text
OFF
MANUAL
AUTO
```

AUTO 只有在用户明确开启时才可自动采集，并且必须记录 session event。

## 36.5 Policy 优先级

```text
Hard Policy
>
Session Setting
>
Global Default
```

Share Privacy 不能绕过 AI_FORBIDDEN；Human Coach 也不能绕过 HUMAN_FORBIDDEN。

---

# 37. Human Coach：从“秘密外援”改为受控协作 Guidance Source

Human Coach 保留，因为它在 Mock、Career Coaching、Pair Interview 和明确允许的 assisted interview 中有真实价值；但它不再被定义为“任何真实面试都可隐蔽接入的助手”。

## 37.1 默认产品定位

优先支持：

- Mock；
- Practice；
- Career Coach 远程训练；
- Pair Interview；
- 明确允许外部辅助的面试场景。

正式 Live 默认受 `HUMAN_PRACTICE_ONLY` 限制。

## 37.2 权限模型

默认无共享。

用户逐项授权：

- Current Question；
- Transcript；
- AI Cue；
- Resume；
- JD；
- Screen；
- Screenshot；
- selected KB reference。

权限必须 server-side enforce，不能只是前端隐藏。

## 37.3 Guidance Source

Human Coach 输出：

```text
source = HUMAN_COACH
```

与 AI 分开显示：

```text
AI Cue
• ...

个人来源
• ...

Coach
• ...
```

Human suggestion：

```text
≠ Evidence
≠ User Confirmed
≠ Direct Evidence
```

如果 Coach 给出新的个人事实，只能作为建议，必须由用户确认。

## 37.4 MVP 技术范围

Candidate 端：

- create coach session；
- invite token；
- revoke；
- TTL；
- QR；
- granular permission。

Helper Web：

- current question；
- transcript；
- AI cue（授权时）；
- Resume/JD（授权时）；
- text suggestion；
- hold-to-speak voice suggestion。

不做：

- remote keyboard；
- remote mouse；
- remote file access。

## 37.5 Local-first 与公网边界

LAN / local helper 应完整可用。

公网远程 Coach 如果缺 relay/domain/部署基础设施：

```text
BLOCKED-EXTERNAL
```

保留：

```text
COACH_PUBLIC_BASE_URL
```

但不能假装仓库天然拥有公网服务。

---

# 38. Live 主链路 2.0：Frozen Pack → Predictive Cue → Deep

R2 正式生产链：

```text
Audio / Manual / Screen
        ↓
Streaming ASR
        ↓
Q0: Meaningful Partial
        ↓
Question Hypothesis
        ↓
Speculative Context Prefetch
        ↓
E: Estimated Speech End
        ↓
Q1: Stable Question
        ↓
Dialogue Act × Content Type × Truth Requirement
        ↓
Follow-up Resolver
        ↓
Interview State
        ↓
Frozen InterviewPack
        ↓
Context Compiler FAST
        ↓
Assertion Constraint
        ↓
Guidance Generator
        ↓
G0: guidance_fast
        ↓
Main UI + Overlay
        │
        ├────→ Context Compiler DEEP
        ├────→ World Reasoning
        ├────→ Answer Planner
        ├────→ Deep Answer Stream
        └────→ Stream Assertion Guard
        ↓
Candidate Actual Speech
        ↓
Session Statements / Turn Commit
        ↓
Review
        ↓
Controlled Memory / User Confirmation
```

整个 Live Session 不能重新选择“全局最新 Job”。

InterviewPack 是本场 Context 的 root authority；Current Session Events 只能增量追加，不得偷偷替换冻结资料。

---

# 39. UI/UX 总原则 3.0：把系统复杂度藏起来

v1.3 的 UI 不再追求“把每个模块都展示出来”，而追求：

> **对象稳定、下一动作清楚、Live 极简、复杂能力随上下文出现。**

十二条原则：

1. Goal 优先于功能模块；
2. 用户动作优先于系统状态；
3. Studio 信息完整，Live 信息克制；
4. Cue 优先，Essay 后置；
5. Next Focus 优先于评分；
6. Fact Inbox 优先于 Evidence database；
7. Material role 必须清楚；
8. 边缘动作进入 Command Palette / Context menu；
9. 同一对象不要在多个一级入口重复；
10. 每个页面最多一个主 CTA；
11. 状态只在一个地方展示，不让 loading 信号四处闪；
12. 所有自动化都必须允许用户知道“它做了什么、基于什么”。

---

# 40. 两种产品状态：Studio 与 Live Cockpit

## Studio

普通主窗口，用于：

- Goal；
- Prepare；
- Practice；
- Me；
- Library；
- History；
- Settings；
- Reflection。

Studio 是“慢思考、可编辑、可追溯”的空间。

## Live Cockpit

只有进入 Session 后出现。

Live 不显示复杂导航，主界面只保留：

```text
Question
Fast Cue
Source / Warning
```

Deep Answer、Transcript、Screen、References、Coach、Quick Notes 都是第二层。

用户不用点击“切换到 Cockpit”，而是从 Preflight 自动进入；结束 Session 自动回 Studio。

---

# 41. UI 视觉系统 3.0：Professional Workbench, not AI Dashboard

视觉目标：

- 专业桌面工作台；
- 安静；
- 高信息可读性；
- 不炫技；
- 不赛博；
- 不做“作弊神器”视觉；
- 不用大面积渐变制造 AI 感。

## 41.1 色彩

Light：

- Canvas `#F6F7F6`
- Surface `#FFFFFF`
- Surface Alt `#F0F3F1`
- Bamboo `#2F6B57`
- Ink Blue `#3F6475`
- Text `#1B2420`
- Secondary `#58625D`

正文级状态色：

- Direct Evidence `#256A4B`
- Supporting `#317566`
- Inferred `#86551F`
- No Evidence `#636A66`
- Risk `#AD4545`

状态永远配 icon + label，不只靠颜色。

## 41.2 Typography

- 中文：系统 UI Sans；
- 英文：Inter / system sans；
- Code：JetBrains Mono；
- Live Cue：15–16px 起；
- Overlay：12–24px 可调；
- 大标题少，减少 Dashboard 化。

## 41.3 Density

Studio：中等信息密度。

Live：高可扫读密度，但单屏元素更少。

Card 只在真正存在分组意义时使用；不要把每条信息都包成 Card。

## 41.4 Action Design

默认显示：

- 主动作；
- 一个次动作；
- 其余进入 `⋯`。

这样避免每行出现 5–7 个按钮。

---

# 42. 信息架构 v1.3：Goal-centered

正式一级导航：

```text
首页
求职目标
我的成竹
练习
资料库
历史
设置
```

右上固定：

```text
[上场]
```

可选全局：

```text
Search / Ctrl+K
```

说明：

- **上场** 是动作，不是一级导航；
- **准备** 属于 Goal；
- **复盘** 属于 Session / History / Goal；
- **岗位 / Job Tracker** 统一为“求职目标”；
- **Knowledge / Quick Notes / Question Bank** 统一进入资料库，但按角色分区；
- “我的成竹”只管理 Person，不承载 Job。

---

# 43. 首页：Action Home，不做指标 Dashboard

首页只回答三件事：

1. 下一场是什么？
2. 当前最值得做什么？
3. 有没有 blocker？

Wireframe：

```text
┌──────────────────────────────────────────────────────────┐
│ 成竹                         Ctrl+K               [上场] │
├─────────────┬────────────────────────────────────────────┤
│ 首页        │ 下一场                                     │
│ 求职目标    │ MindRank · 技术二面 · 明天 14:00           │
│ 我的成竹    │ [继续准备] [开始演练] [Preflight]           │
│ 练习        ├────────────────────────────────────────────┤
│ 资料库      │ Next Focus                                 │
│ 历史        │ Redis Cluster：有知识，无生产经历来源       │
│ 设置        │ [准备这个问题]                             │
│             ├────────────────────────────────────────────┤
│             │ 需要你处理                                 │
│             │ 3 个事实待确认 · 1 个 Story 缺口           │
│             ├────────────────────────────────────────────┤
│             │ 最近 Session                               │
│             │ MindRank 技术一面 · System Design depth    │
└─────────────┴────────────────────────────────────────────┘
```

不默认放：

- 大量图表；
- 准备度百分比；
- “AI 分析指数”；
- 无行动意义的累计数字。

---

# 44. 我的成竹：从“数据管理”升级为 Person Workspace

Tabs：

```text
概览 | 简历 | 项目 | 待确认 | Stories | Skills | 我的表达
```

`待确认` 是 Fact Inbox，不默认显示底层 Graph 术语。
## Fact Inbox

例：

```text
需要你确认 · 4

WenNian
“我负责完整 RAG 架构设计”

材料目前能证明：参与设计
不能证明：主导全部架构

你实际情况是？
[我主导] [我参与] [修改表述]
```

确认之后才进入稳定 Personal Context。

高级用户可在 detail drawer 查看：

- source excerpt；
- provenance status；
- assertion status；
- session history；
- linked Story；
- linked Skill。

---

# 45. Stories UI：从卡片收藏升级为真实故事资产

Stories 页面按能力标签浏览：

```text
Ownership
Conflict
Failure
Leadership
Ambiguity
Collaboration
Difficult Problem
```

缺失状态比空白页更重要：

```text
你还没有“失败与反思”故事

很多 Hiring Manager 会追问失败、复盘和改变。
[开始 5 分钟 Story Builder]
```

Story detail：

- Situation；
- Challenge；
- Action；
- Result；
- Reflection；
- linked sources；
- related questions；
- last used session；
- `Practice this story`。

---

# 46. 求职目标 UI：Goal 是唯一岗位中心

列表页面不是 Job Tracker 看板优先，而是 Goal list：

```text
Active
MindRank · AIDD Agent Engineer       技术二面 · 明天
德睿智药 · AI Product               待安排
康龙化成 · AI 应用实施              已完成
```

每个 Goal 进入 Goal Room：

```text
概览 | 准备 | 面试 | Offer
```

Applications status 可以是 Goal metadata，不需要先让产品变成 ATS。

Goal detail 中 Resume/JD/Materials 都明确来源；不让用户在另一个“岗位”页面重复维护一份。

---

# 47. Goal Prepare Workspace

Prepare 页面不是“题库瀑布流”，而是行动顺序。

```text
Next Focus
Gap Map
Attack Surface
Question Graph
Skills / Stories
Materials
InterviewPack Preview
```

默认首屏：

```text
Next Focus
──────────
1. Redis Cluster：事实边界
2. System Design：scale reasoning
3. Ownership Story：待补
```

点一个 Focus，进入单任务页面，避免同时展示全部图谱。

Question Graph 默认折叠，只展开当前 Focus 的分支。

---

# 48. Practice UI 3.0

Practice 分两步：Setup → Session。

## Setup

```text
Practice · MindRank

轮次        技术一面
面试官风格  强追问
难度        标准
题目来源    Goal + 最近弱点

[开始]
```

高级设置折叠：

- Question Bank；
- Language；
- Coding Language；
- Duration；
- Human Coach；
- Delivery analysis。

## Session

主界面保持对话感，不在用户回答前显示参考答案。

回答结束后只给极短反馈：

```text
✓ trade-off 清楚
! ownership 不够具体

下一问：那你个人真正负责了哪部分？
```

完整 Content / Delivery feedback 在 Session 后显示。

---

# 49. Live Preflight 3.0：告诉用户“这一场到底带进去什么”

Preflight 不显示工程版本号为主，而显示可理解来源。

```text
上场前检查

Goal
MindRank · AIDD Agent Engineer

个人上下文
郝磊-简历.pdf                   [来自 我的成竹]
3 个 Skill Cards                [Goal 默认]
2 个 Stories                    [Goal 默认]

Knowledge
AIDD Notes                      [Goal 默认]
RAG Notes                       [本场覆盖]

Quick Notes
MindRank 二面                   [本场]

回答
中文 · 技术词保留英文           [我的表达]
Python                          [Goal 默认]

AI Assistance
Allowed                         [本场设置]

Human Coach
Practice only / Off             [系统默认]

Share Privacy
Off                             [本场设置]

音频
✓ 麦克风
✓ 系统音频
✓ STT

[冻结并开始]
```

技术上的 Candidate v7 / Pack hash 可放在 Diagnostics，不应成为普通用户主要信息。

---

# 50. Live Main UI 3.0：三层首屏

首屏固定三层：

```text
1. Question
2. Cue
3. Source / Warning
```

Wireframe：

```text
● Cue ready

为什么不用 fine-tuning？
────────────────────────────
• 知识更新频繁，RAG 不需要重新训练
• 检索来源可追溯
• 结合 WenNian 的文档更新讲
────────────────────────────
你的经历
✓ WenNian：RAG + Agent

注意
! 没有 fine-tuning 生产经历

[展开完整回答]
```

系统状态只有一处：

```text
Listening
Question detected
Preparing
Cue ready
Answering
Reconnecting
```

不要同时出现 ASR / retrieval / LLM / compiler 四套 loading。

---

# 51. Overlay 3.0：Dock × Interaction × Size

Overlay 不是永久大浮窗。

用户设置三个维度：

```text
Dock
Top / Left / Right / Free

Interaction
Passive / Interactive

Size
Compact / Standard / Focus
```

## Idle Compact

```text
● Listening · MindRank
```

## Cue arrives

```text
┌──────────────────────────────┐
│ 为什么不用 fine-tuning？    │
│                              │
│ • 更新快                     │
│ • 可追溯                     │
│ • WenNian 可讲               │
│                              │
│ ! 无生产 fine-tune 经历      │
└──────────────────────────────┘
```

## Focus

用于：

- Full answer；
- Coding；
- System Design；
- OOD；
- References。

问题结束后自动回 Compact，可由用户关闭自动收起。

Main UI 与 Overlay 必须共用同一 GuidanceViewModel。

---

# 52. Share Privacy UI

继续遵守 v1.2-R2：默认 OFF，定义为私人内容保护，不承诺不可检测。

设置文案：

```text
屏幕共享保护
[ OFF ]

减少 Chengzhu 私人窗口在受支持的屏幕共享/录制路径中
意外出现。不同系统与捕获方式可能不同，这不是安全保证。
```

Preflight 必须显示本场实际值。

---

# 53. Human Coach UI：Practice-first

Human Coach 默认出现在 Practice Setup，而不是 Live 首页主入口。

Practice：

```text
Human Coach
[邀请]
```

正式 Live：

只有 Human Assistance Policy 允许时才显示。

Candidate 侧来源分离：

```text
AI
• ...

Coach
• ...
```

Coach Suggestion 永远不是 Evidence。

---

# 54. Reflection UI 3.0：先给下一步，再给完整分析

默认 Summary：

```text
这场之后

下一步
System Design scale reasoning
[开始练习]

做得好的
RAG trade-off 讲得具体
“你的真实原话……”

需要改进
多次使用“我们”，个人职责不清
“你的真实原话……”

待确认事实
Redis Cluster
[确认] [口误]

值得建立的 Story
线上事故恢复
[创建 Story]

[查看完整逐轮分析]
```

完整 Timeline 才展示：

- raw question；
- resolved question；
- candidate actual speech；
- Fast Cue；
- Deep Answer；
- Coach Cue；
- selected context；
- reference fragment；
- assertion event；
- latency。

Reflection 输出直接回 Goal 的 Next Focus。

---

# 55. Settings 3.0：可搜索、默认值与本场覆盖分离

分组：

```text
General
Models
Speech & Audio
Language
Live & Overlay
Privacy
Knowledge
Shortcuts
Data & Export
Diagnostics
```

支持：

```text
Ctrl+F 搜设置
Ctrl+, 打开设置
```

每个可被 Session 覆盖的设置标记：

```text
Account default
Goal default
This session
```

避免用户不知道修改会影响本场、后续还是全局。

---

# 56. Empty / Loading / Processing / Error State 3.0

状态设计必须按对象语义，而不是通用 Spinner。

## Material

```text
Processing
Ready
Failed
Replacing
```

替换文件时：上一版保持可用，直到新版 Ready；不要让当前 Goal 突然失去材料。

## Fast Cue

- Preparing；
- Cue unavailable, deep answer continues；
- Provider fallback；
- Offline knowledge only。

## Goal

- No JD；
- No Resume；
- No upcoming interview；
- Archived。

## Human Coach

- waiting；
- connected；
- reconnecting；
- permission changed；
- revoked。

所有 Error 都必须有下一步动作。

---

# 57. Accessibility、Keyboard 与 Desktop Interaction

必须支持：

- 全键盘导航；
- Focus ring；
- ARIA；
- Screen reader；
- Reduced motion；
- Font scaling；
- High contrast；
- Light/Dark；
- 390px；
- 小 Overlay；
- 关键动作不依赖 hover。

核心快捷键建议：

```text
Ctrl+K       Command Palette
Ctrl+,       Settings
Ctrl+P       Pin Moment（Session 中）
Ctrl+N       Quick Notes（Session 中）
Ctrl+B       Show/Hide Overlay（沿用现有习惯时）
Esc          Close transient UI
```

快捷键以真实仓库冲突审计为准，不能硬覆盖现有用户绑定。

---

# 58. Data Model 2.1

R2 重点新增 / 强化：

```text
candidate
candidate_version
experience
project
skill
claim
claim_provenance
source
story
voice_profile
job_profile
alignment
job_goal
prep_workspace
question_graph
interview_session
interview_pack
interview_pack_revision
session_statement
interview_turn
context_selection
guidance_event
coach_session
coach_message
memory_item
model_profile
```

## 58.1 claim

建议：

```text
id
subject
predicate
object
role
scope
project_id
metric
value
unit
time_range
provenance_status
user_assertion_status
created_at
updated_at
```

## 58.2 interview_pack

不是只存 version ID；至少保存可重建冻结上下文的 materialized payload 或内容引用 + content hash。

```text
id
session_id
revision
payload_json
content_hash
created_at
```

其中 payload 内含：

- candidate context；
- claims；
- sources；
- Job；
- Skill Cards；
- Stories；
- KB selection；
- Voice；
- policies；
- model profile。

## 58.3 context_selection

每轮记录：

- fragment_id；
- provider；
- source_id；
- content_hash；
- score；
- selected / dropped；
- reason；
- contradiction risk；
- token estimate。

## 58.4 session_statement

```text
id
session_id
turn_id
text
normalized_claim_ref
status = SESSION_STATED | SESSION_CORRECTED
created_at
resolved_at
```

Session Statement 不直接写入长期 Claim。

---

# 59. Privacy / Local-first 2.1

默认：

- Resume 本地；
- SQLite 本地；
- API key 本地；
- 原始音频默认不长期保存；
- 只向 provider 发送当前最小充分上下文；
- Session 可删除；
- Intelligence 数据可导出；
- Human Coach 默认不共享；
- Share Privacy 默认 OFF；
- speech adoption analytics 在正式 Live 默认 OFF；
- 用户可以查看 InterviewPack；
- 用户可以查看哪些 fragment 被发送给模型。

## 59.1 Cue Adoption / Speech Analytics

Practice / Mock：

- 可默认本地分析 cue coverage；
- speaking pace；
- filler；
- answer duration；
- correction。

正式 Live：

```text
speech_adoption_analytics = OFF
```

必须用户 opt-in 才开启。

这些指标只用于产品改进和个人复盘，不做：

- “通过率预测”；
- “面试官检测”；
- covert surveillance。

## 59.2 Human Coach

Coach 分享逐项授权；session end 自动 revoke。

## 59.3 Pack 与 Export

用户导出时必须能选择：

- 是否包含 transcript；
- 是否包含 AI Guidance；
- 是否包含 Coach messages；
- 是否包含 provenance excerpts。

API Key 永远不进入 export。

---

# 60. Policy 与产品边界

Policy 必须成为 runtime contract，不只是 Settings 文案。

## AI Policy

- AI_FORBIDDEN：server-side block；
- AI_LIMITED：manual only / constrained；
- AI_ALLOWED：normal guidance；
- AI_EXPECTED：可主动 cue。

## Human Assistance

- HUMAN_FORBIDDEN；
- HUMAN_PRACTICE_ONLY；
- HUMAN_ALLOWED。

## Share Privacy

- OFF；
- PRIVATE_OVERLAY。

它只控制窗口 capture protection，不改变 AI/Human policy。

## 明确禁止

- 伪造用户经历；
- 自动扩写未经来源/用户确认的 personal claim；
- 把 Human Coach suggestion 变成事实；
- 把 World Knowledge 变成经历；
- 绕过第三方安全/监控/反作弊机制；
- 承诺“绝对不可检测”；
- 因为 Session Statement 而继续虚构更多支撑细节；
- 偷偷上传原始音频。

---

# 61. Observability 2.1

每轮至少记录结构化事件：

```text
Q0 meaningful partial
E speech-end estimate
Q1 stable question
question hypothesis
resolved question
dialogue act
content type
truth requirement
active topic
InterviewPack id / revision
context candidates
context selected / dropped
response mode
assertion policy
L0 cue time
L1 cue time
G0 UI-visible cue
deep first token
deep complete
assertion rewrite
provider fallback
coach cue
candidate correction
session statement
```

必须能区分：

```text
TTFUG_user
TTFUG_internal
TTFA
TTD
```

不要再用一个 `first_useful_guidance` 字段同时代表多件事。

敏感文本依然做最小化、截断、hash / ID 优先。

---

# 62. Eval Harness 2.1：Strict / Held-out / Production 分层

R2 不允许“10 个 fixture route_accuracy 1.0”代表产品完成。

## 62.1 Deterministic Eval

测试：

- 三轴 question understanding；
- exact routing；
- provenance state；
- assertion policy；
- Session Statement；
- InterviewPack；
- Job A/B contamination；
- Context dedupe；
- policy；
- memory write-back；
- coach permission。

## 62.2 Dev Fixtures 与 Held-out 分开

必须有：

```text
dev fixtures
held-out fixtures
```

Agent 不得对 held-out 逐题硬编码。

## 62.3 Model-dependent Eval

使用 BYOK / opt-in provider：

- answer correctness；
- personal assertion precision；
- unsupported personal assertion rate；
- cue usefulness；
- knowledge correctness；
- coding / system design；
- latency；
- token / cost。

无 key：

```text
BLOCKED-EXTERNAL
```

而不是 PASS。

## 62.4 Production E2E

必须覆盖：

- 中文；
- 英文；
- 中英混合；
- partial ASR；
- ASR 错词；
- interruption；
- topic reset；
- screenshot；
- Session Statement；
- provider fallback；
- network jitter；
- Fast Cue timeout；
- Pack revision；
- AI/Human policy。

---

# 63. R2 必须新增的 Eval 场景

至少：

1. Resume 有 Redis，无 Redis Cluster；
2. 用户确认“确实用过 Redis Cluster”，但无独立来源；
3. 用户现场说“后来用了 Redis Cluster”；
4. 系统记录 SESSION_STATED，但不扩大细节；
5. 用户当场点击“这是口误”；
6. 下一场不得继承错误 statement；
7. Knowledge 问题中模型突然输出“我之前生产做过”；
8. Follow-up：“为什么不用那个？”；
9. RAG topic 明确切换 OS；
10. Job A Pack freeze 后分析 Job B，再回 A Live；
11. B 的 JD 绝不能出现在 A prompt；
12. Compiler active 时 Resume fragment 不重复；
13. KB fragment 不重复；
14. Share Privacy OFF 不改变 AI Guidance；
15. AI_FORBIDDEN hard block；
16. HUMAN_PRACTICE_ONLY 在正式 Live 禁用 Coach；
17. Coach 给出与 Provenance 冲突的 suggestion；
18. Screen 上有代码，spoken question 只说“这里有什么问题？”；
19. 中文 slow speaker；
20. English fast speaker；
21. 中英混合；
22. ASR typo；
23. provider fallback；
24. tiny Cue provider failure；
25. Deep failure但 Fast Cue 已显示；
26. Pack rev 1 后用户更新资料，Live 不漂；
27. 创建 rev 2 后只有后续 turn 切换；
28. Review 基于 candidate speech，不拿 AI answer 当用户表现。

---

# 64. Quality Metrics 2.1

## Live

- QBD；
- TTFUG_user；
- TTFUG_internal；
- TTFA；
- Cue render success；
- Fast Cue fallback rate；
- Context duplicate rate；
- assertion rewrite rate；
- provider fallback rate。

## Candidate / Provenance

- direct-evidence claim coverage；
- user-confirmed/no-evidence count；
- unresolved conflict count；
- high-risk role/metric claims；
- Story coverage。

## Learning

- repeated weakness closure；
- Review → Prepare transfer；
- Review → Mock transfer；
- Review → Live Pack transfer。

## Cue Adoption

Practice / Mock 可以测：

- candidate speech 对 Cue semantic coverage；
- Cue expand rate；
- ignored rate；
- correction rate。

正式 Live 默认不持续做 adoption analytics，除非用户 opt-in。

## 禁止指标

不输出：

- “拿 Offer 概率”；
- “面试官喜欢程度 82%”；
- “真实性评分 93%”；
- 无可验证基础的综合准备度百分比。

---

# 65. Performance / Cost / Unit Economics

R2 性能必须按整个用户链测，不只测 LLM。

一次 Live Turn 分解：

```text
Audio / partial
+ speech-end detection
+ question stabilization
+ prefetch
+ ContextCompiler FAST
+ L0/L1 Cue
+ UI render
+ ContextCompiler DEEP
+ Deep provider
+ Stream Guard
```

模型 Profile 记录：

- provider；
- model；
- fast latency；
- deep latency；
- knowledge quality；
- assertion precision；
- token cost；
- vision support；
- reasoning support。

商业成本按一小时拆：

```text
ASR
+ Fast Cue calls
+ Deep Answer calls
+ Vision
+ Review
+ optional Coach relay
+ storage / sync
```

BYOK 模式下，Chengzhu 的软件价值来自：

- Candidate / Provenance；
- InterviewPack；
- Context Compiler；
- Live UX；
- Review；
- local-first；
- workflow；

而不是 token resale。

---

# 66. MIT License 与商业化方向

用户已经正式决定：

> **Chengzhu 软件代码从 v1.2-R2 起采用 MIT License。**

## 66.1 License

根 `LICENSE` 使用标准 MIT License。

同时新增：

```text
THIRD_PARTY_NOTICES.md
```

第三方依赖、字体、图标、模型、数据、素材继续遵守各自许可证，不能因为主项目改 MIT 就重新授权别人的内容。

Git 历史中的旧 CC BY-NC 不需要改写历史；从当前版本开始新的仓库根许可证和 Release 采用 MIT。

## 66.2 开源不等于不能商业化

MIT 允许：

- 使用；
- 修改；
- 分发；
- sublicense；
- 商业使用。

因此 Chengzhu 后续可以同时：

- 保持核心项目公开；
- 提供 BYOK Pro；
- 提供托管 AI；
- 提供 Cloud Sync；
- 提供团队/教练服务；
- 提供商业支持。

## 66.3 建议产品层

### Free / Local

- Resume；
- Job；
- Candidate；
- Facts / Sources；
- 基础 Prepare；
- 有限 Practice；
- 本地 Review。

### Pro BYOK

- Full Live；
- Fast Cue；
- Overlay；
- Screenshot；
- Cross-session；
- advanced Review；
- Share Privacy；
- Practice Human Coach。

### Optional Managed AI

面向不愿管理 API Key 的用户：

- managed provider；
- 清楚显示 usage / cost；
- 不改变 Local-first 数据原则。

## 66.4 商业发布前必须完成

- MIT LICENSE；
- THIRD_PARTY_NOTICES；
- package artifact license inclusion；
- third-party dependency license scan；
- pricing unit economics；
- privacy policy / terms（真正收费前）。

---

# 67. 技术债务与拆分

当前：

- `backend/api/assist/pipeline.py` 约 2416 行；
- `backend/api/assist/answer_worker.py` 约 1813 行。

需要逐步拆，而不是大重写。

建议域：

```text
assist/audio_pipeline.py
assist/question_pipeline.py
assist/context_assembly.py
assist/generation_runner.py
assist/truth_stream_guard.py
assist/commit_pipeline.py
assist/ws_events.py
```

每次迁移保持行为 fixture 与 regression gate。

目标不是为了 300 行而切碎，而是让：

- 状态；
- 输入；
- 输出；
- fallback；
- test seam

更清楚。

---

# 68. CI / Release / Packaging Gate

v1.2-R2 的“可发布”必须包括源码门禁、Windows 安装包和 GitHub Release 回验。

## 68.1 G0 Canonical Truth

- v1.2-R2 canonical 入 repo；
- README / DESIGN / PRODUCT / CHANGELOG 一致；
- repo 不再错误指向 v1.0；
- MIT 表述一致。

## 68.2 G1 Repo Integrity

- no force push；
- worktree clean；
- PR → main；
- CI all green。

## 68.3 G2 Provenance / Assertion Semantics

- Provenance / User Assertion / Session 三轴真实落库；
- UI 文案不冒充 reality verification；
- Redis / Redis Cluster scope fixture pass。

## 68.4 G3 InterviewPack

- Frozen Pack 是 Live root；
- `latest_job_id()` 不再进入 Live；
- A/B Job contamination fixture pass；
- Pack revision 可追溯。

## 68.5 G4 Context Authority

- Compiler active 时 legacy duplicate context = 0；
- selected context 保存；
- fallback tested。

## 68.6 G5 True Fast Cue

- `guidance_fast` 独立存在；
- 比 Deep 更早到达 UI；
- Cue 是内容，不是结构标签；
- Main + Overlay 共用 GuidanceViewModel。

## 68.7 G6 TTFUG / Predictive Start

- E/Q0/Q1/G0/A0 telemetry；
- QBD / TTFUG_user 正确计算；
- controlled benchmark；
- 不再把 first token 当 TTFUG。

## 68.8 G7 Stream Assertion

- high-risk claim 局部 guard；
- Knowledge 保持低延迟流；
- session statement 不扩大细节。

## 68.9 G8 Skill / Story / Voice / Memory to Live

- Skill Card 进入 Pack；
- Story Provider；
- Voice 可见可编辑；
- Controlled Memory 能影响下一场 Pack。

## 68.10 G9 Policy / Privacy

- AI policy server-side；
- Human policy 独立；
- Share Privacy 默认 OFF；
- content protection 可切；
- 不承诺 undetectable。

## 68.11 G10 Human Coach MVP

- Practice / Mock local/LAN；
- permission server-side；
- AI/Coach source 分开；
-公网 relay 可 BLOCKED-EXTERNAL。

## 68.12 G11 UI / Accessibility

- 新 IA；
- Facts UI；
- Preflight；
- Live Cue；
- Review 2.0；
- AA color；
- keyboard；
- 390px；
- dark/light；
- visual regression。

## 68.13 G12 Eval

- strict exact route；
- held-out；
- production E2E；
- fake provider；
- real BYOK 无 key则 external。

## 68.14 G13 Long Session

- simulated 2h / 3h / 5h；
- real hardware 若不可用则 external。

## 68.15 G14 Desktop Packaging

最终 Windows 用户不能需要 Python / Node。

### Backend sidecar

使用 PyInstaller 等成熟方案打成：

```text
resources/backend/chengzhu-backend.exe
```

### Frontend

预构建 `frontend/dist`，打入 Electron。

### Release artifacts

至少：

```text
Chengzhu-Setup-x64.exe
Chengzhu-Portable-x64.zip
SHA256SUMS.txt
LICENSE
THIRD_PARTY_NOTICES.md
```

## 68.16 G15 User Data Path

Packaged Windows：

```text
%APPDATA%\Chengzhu\
  data\
  config\
  logs\
  cache\
  exports\
```

更新不能覆盖用户 DB。

## 68.17 G16 First-run Onboarding

必须支持：

- Welcome；
- Local data notice；
- Model / API Key test；
- STT；
- microphone；
- system audio；
- Share Privacy default；
- Resume；
- first Job。

无 API Key 仍可进入本地功能。

## 68.18 G17 GitHub Release Workflow

新增 release workflow：

- tests；
- backend sidecar；
- frontend build；
- Electron package；
- packaged smoke；
- checksum；
- GitHub Release asset。

## 68.19 G18 Download-back Verification

真正的最后一步：

1. 从 GitHub Release 下载刚生成的 installer；
2. 在 clean Windows 环境安装；
3. 不依赖 Python / Node；
4. 启动；
5. 迁移；
6. fake-provider E2E；
7. 重启与数据持久化；
8. 只有通过后才允许 `RELEASE_READY`。

## 68.20 最终状态

只允许：

- RELEASE_READY；
- RELEASE_READY_WITH_EXTERNAL_BLOCKERS；
- NOT_READY。

---

# 69. 版本路线 v1.3

## v1.3-R2 — Goal-centered Product Experience + Future Profile Canonical Retention

目标：不推翻 v1.2-R2 Verified Live Core，把其能力真正收敛成成熟桌面产品体验。

当前重点：

- Goal Room；
- Goal-centered IA；
- Quick Notes；
- Command Palette；
- Guided First Practice；
- Practice Persona / Round / Difficulty；
- Content × Delivery feedback；
- Pin Moment；
- Nudge；
- Closing Mode；
- Material lifecycle；
- Language layering；
- Compact/Docked Overlay；
- Reflection → Next Focus。

## v1.3.x — Practice Depth

- Panel Interview / Multi-persona；
- richer question banks；
- role-specific rubrics；
- user progress trends；
- optional local delivery analytics。

## v1.4 — Product-Market Validation Hardening

进入 v1.4 前必须证明：

- Goal 被用户持续复用；
- Reflection 确实改变下一轮 Prepare；
- Fast Cue 被真正使用而不是机械照读；
- Practice 对真实 Session 有迁移价值；
- Fact Inbox 不成为维护负担；
- Quick Notes / Pin Moment 是高价值小功能而非噪声。

## v2.0 — Personal Conversation Intelligence / Conversation Profile（条件触发）

只有 Interview 主产品完成 PMF 验证后再启动第二垂直，不提前扩大顶层导航。

建议第一验证场景优先选择：**项目周会 / 技术设计评审**。它们与现有 Person、Project、Evidence、Decision、Commitment、Screen Context 和 Fast Cue 复用度最高，也最适合验证“回答问题之外，是否能识别值得说的话”。完整 Future Profile 见下一章。

---


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

# 70. 当前明确不做

v1.3-R2 当前 release scope 不做：

- 自研基础大模型；
- Agent swarm；
- Neo4j 强迁移；
- PostgreSQL 云化重构；
- pgvector 强依赖；
- Tauri 重写；
- ATS；
- 自动投递；
- 社区；
- 简历模板市场；
- 完整 Meeting UI；
- Sales Copilot；
- remote keyboard/mouse；
- 第三方安全机制绕过；
- anti-proctoring bypass；
- “20 层不可检测”军备竞赛；
- “100% interviewer 看不到”承诺；
- 把候选人现场没证据的口述自动写成长期事实；
- 把 World Knowledge 冒充经历；
- 为了密集功能增加重复页面；
- 在 Live 主链没闭环前继续堆更多新模块。

---

# 71. 当前实现状态重新判定（R2 视角）

截至本文再次核验的 feature snapshot：

| 能力 | 当前判定 | R2 目标 |
|---|---|---|
| Candidate Representation | INTEGRATED | PRODUCT-COMPLETE |
| Provenance / Claim UI | IMPLEMENTED / 不完整 | PRODUCT-COMPLETE |
| Job Representation | INTEGRATED | Pack-scoped |
| Gap / Attack / Question Graph | INTEGRATED | PRODUCT-COMPLETE |
| ContextCompiler | INTEGRATED | AUTHORITATIVE |
| Fast Cue | PARTIAL | guidance_fast 真独立 |
| Overlay | INTEGRATED full-answer | Cue-first |
| Truth / Assertion Guard | PARTIAL | stream-safe |
| InterviewPack | 设计/部分 | frozen runtime root |
| Session Statement | 设计/部分 | safe consistency warning |
| Review → Prepare/Mock | INTEGRATED | Review → Next Live |
| Voice | IMPLEMENTED | 用户可见可编辑 |
| Story | PARTIAL | Builder + Provider |
| AI Policy | INTEGRATED | per-session hard gate |
| Share Privacy | IMPLEMENTED | explicit OFF-by-default |
| Human Coach | 设计 | Practice MVP |
| Packaging | source-run capable | GitHub download-ready |
| License | 当前仓库旧 CC BY-NC | MIT |

最重要的三个现实缺口仍然是：

1. `latest_job_id()` 型 runtime drift；
2. 1.2 秒 VAD + 错误 TTFUG 语义；
3. Compiled Context + Legacy Context 双注入。

R2 必须优先解决，而不是先做更多新页面。

---

# 72. 关键验收样例：Redis 七轮 + Pack/Session Statement

R2 的核心 benchmark 不再只看 route，还要同时验证 Pack、Provenance、Assertion 与 Context。

## 72.1 准备材料

Candidate Pack：

```text
WenNian
- RAG + Agent
- Redis 用于 session state
- QPS 30k（若有来源）
```

没有：

```text
Redis Cluster production usage
```

## 72.2 七轮

Q1：介绍一下这个项目。

- PERSONAL_FACT_REQUIRED；
- EXPERIENCE。

Q2：为什么用 RAG？

- PERSONAL_FACT_RELEVANT；
- EXPERIENCE_KNOWLEDGE。

Q3：为什么不用 fine-tuning？

- EXPERIENCE_KNOWLEDGE；
- 不允许声称自己做过线上 fine-tuning，除非 Pack 有来源。

Q4：如果数据量扩大 100 倍呢？

- FOLLOW_UP；
- HYPOTHETICAL / SYSTEM_DESIGN；
- 允许开放设计。

Q5：Redis 会有什么问题？

- KNOWLEDGE；
- World Knowledge 正常回答。

Q6：你实际在生产跑过 Redis Cluster 吗？

如果 Pack 只有 Redis：

```text
Provenance = NO_EVIDENCE
ResponseMode = EXPERIENCE_BOUNDARY_KNOWLEDGE
```

正确表达：

> “当前这个项目里我有依据的是 Redis session state；现有资料不能支持我说自己在生产跑过 Redis Cluster。Cluster 的设计和迁移我可以继续解释。”

Q7：如果没跑过，怎么迁？

- OPEN_DESIGN；
- 正常设计；
- 不把 hypothetical 说成过去经历。

## 72.3 Session Statement 分支

如果 Q6 后候选人自己说：

> “其实后来用了 Redis Cluster。”

系统：

```text
SESSION_STATED
Provenance = NO_EVIDENCE
```

提示：

> “你刚才补充了 Redis Cluster，但当前 Pack 没有来源覆盖。若这是口误可立即纠正；若真实发生过，建议会后确认。”

后续模型不得自动生成：

> “我们当时用了 3 主 3 从、哨兵、Cluster Bus...”

除非用户继续亲口提供且合法保留为 Session Statement，或 Pack 有资料。

## 72.4 Job A/B 污染测试

冻结 Job A Pack 后分析 Job B；再次进入 A：

```text
assert "Job B" not in final context
assert B.must_have not in selected fragments
```

这是 R2 必须持续跑的 regression benchmark。

---

# 73. 最终产品哲学 3.0

第一代实时面试工具解决：

> 这题答案是什么？

v1.2-R2 的成竹进一步解决：

> 哪些属于我的真实事实？当前上下文应该怎么编译？怎样在正确边界里给出可扫读 Guidance？

v1.3 再往前一步：

> **对于这个我真正想拿下的岗位，下一步最值得做什么？正式上场时，我只需要看到什么？结束后，下一轮应该自然改变什么？**

因此 Chengzhu 不应该让用户感觉自己在操作：

- RAG；
- Evidence Graph；
- Context Compiler；
- Memory；
- 21 类 Question Type；
- 多模型路由。

这些复杂性应该被产品压缩成：

```text
Next Focus
→ Practice
→ Preflight
→ Cue
→ Reflection
→ Next Focus
```

长期护城河仍然是复杂系统能力，但产品价值来自：

> **复杂能力在正确时刻变成一个简单动作。**

---

# 74. v1.3-R2 最终 Canonical Definition

## 当前产品定义

> **成竹 Chengzhu 是一个 Goal-centered Interview Intelligence 产品。它从用户真实资料建立可追溯的 Personal Context，以具体 Job Goal 为长期工作对象，把 Prepare、Practice、Frozen InterviewPack、Cue-first Live、Reflection 和 Cross-session Learning 连成一条状态链；在实时面试中只把最需要的 Question、Cue、Source 和 Warning 放到用户眼前，并让每一场真实发生的内容自然成为下一轮的 Next Focus。**

## 核心对象

```text
Person
Goal
InterviewPack
Session
Reflection
```

## 底层原则

```text
Resume-first, not Resume-bound
Provenance is not truth
Session-stated is not verified
One context authority
Cue before essay
Goal before module
Next action before dashboard
```

## 当前边界

- Interview-first；
- Human Coach practice-first；
- Share Privacy 默认 OFF；
- 不做不可检测承诺；
- 不做万能会议助手；
- 不做 ATS；
- 不做社区；
- 不做 Agent swarm；
- 不用虚假准备度/通过率作为核心 UI。

## 长期平台方向

只有 Interview 完成真实产品验证后，才把底层 Person / Conversation / Expression 能力扩展到 Meeting、Presentation、Negotiation 等高价值对话。


## 74.1 当前与长期两层定义

当前产品定义：**Goal-centered Interview Operating System**。

长期平台定义：**Personal Conversation Intelligence Core + Conversation Profiles**。

二者不是两套架构：Interview 是第一 Profile；Future Conversation 继承 Person / Goal / Pack / Session / Reflection、Provenance、Context Compiler、Memory、Fast Cue 与 Policy，并进一步引入 Counterparty State、Expression Planner、Decision/Commitment 和 Contribution Opportunity。

因此从本版开始，任何新的 v1.x 核心设计都应同时回答一个问题：

> **它是否解决当前 Interview 问题，同时避免把底层锁死成只能服务 Interview？**

但“可泛化”不能成为提前产品化 Meeting 的理由。

---

# 75. 外部研究来源（复核日期：2026-09-30）

> Future Conversation Profile 章节的原始内部设计依据主要来自 v1.1-R1 第 56–71 节；本版按 v1.2-R2/v1.3-R2 的 Provenance、Pack、Policy 与 Goal-centered 术语做了显式融合，而不是把旧章节静默覆盖。

以下资料用于产品与 UX 研究，不代表 Chengzhu 复制其实现或接受其全部产品定位。

- **[S1] FinalRound AI — Inside the goal room**  
  https://docs.finalroundai.com/docs/goals/goal-workspace
- **[S2] FinalRound AI — Studio vs Cockpit**  
  https://docs.finalroundai.com/docs/core-concepts/studio-vs-cockpit
- **[S3] FinalRound AI — Launching a session / Preflight**  
  https://docs.finalroundai.com/docs/live-copilot/launching-a-session
- **[S4] AskCc — 产品功能 / 共享面试档案 / 技能档案**  
  https://askcc.com.cn/features
- **[S5] GhostInterview — Knowledge Bases / Quick Notes material taxonomy**  
  https://ghostinterview.co/docs/user-guide/knowledge-base
- **[S6] GhostInterview — Duo**  
  https://ghostinterview.co/docs/user-guide/duo
- **[S7] GhostInterview — Interview Debrief**  
  https://ghostinterview.co/docs/user-guide/interview-debrief
- **[S8] GhostInterview — Changelog / Quick Notes**  
  https://ghostinterview.co/changelog
- **[S9] Yoodli — Practice with Yoodli**  
  https://support.yoodli.ai/en/articles/9550465-practice-with-yoodli
- **[S10] Yoodli — Customizing Practice / Question Banks / Personas**  
  https://support.yoodli.ai/en/articles/9628260-customizing-practice
- **[S11] Hedy — Features / proactive suggestions**  
  https://www.hedy.ai/features/
- **[S12] Hedy — Job seeker interview tool**  
  https://hedy.ai/job-seeker-ai-interview-tool/
- **[S13] Granola — AI-enhanced notes**  
  https://help.granola.ai/article/ai-enhanced-notes
- **[S14] Raycast — Settings / Settings Search**  
  https://manual.raycast.com/settings
- **[S15] Linear — Contextual command menu**  
  https://linear.app/changelog/2019-10-07-contextual-command-menu

研究使用原则：

- 借产品模式，不抄界面；
- 借用户路径，不复制品牌；
- 借成熟交互，不放弃 Chengzhu 的 Provenance / Truth / Goal Memory 差异；
- 任何竞品宣称都不能替代 Chengzhu 自己的实测。

---

# 附录 A：从 v1.1-R1 继承且继续有效的原则

- Interview-first；
- Resume-first, not Resume-bound；
- Open-world reasoning；
- no big-bang rewrite；
- versioned migration；
- additive rollout + feature flags；
- deterministic grounding 不降低；
- inference 不等于 fact；
- Meeting 只保留未来接口；
- Local-first；
- Gate 不为赶进度降低；
- runtime / DB / CI / current repo 高于文档自述。

# 附录 B：建议工程收口顺序

R2 的工程顺序必须按依赖关系推进，而不是按“哪个页面好写”推进。

## P0：先修系统语义

1. MIT License；
2. Provenance / User Assertion / Session 三轴；
3. Session Statement 安全语义；
4. InterviewPack 真冻结；
5. Live 移除 `latest_*`；
6. ContextCompiler authoritative；
7. 唯一 routing function。

## P0：再打穿实时主链

8. partial ASR hypothesis；
9. speech-end / QBD；
10. 真 `guidance_fast`；
11. Overlay cue-first；
12. stream assertion guard；
13. TTFUG_user telemetry。

## P1：用户资产进 Live

14. Facts / Sources UI；
15. Skill Card → Pack；
16. Story → Pack；
17. Voice → Pack；
18. Controlled Memory → Next Pack。

## P1：产品化

19. 新 IA；
20. Preflight；
21. Review 2.0；
22. Human Coach Practice MVP；
23. WCAG；
24. Onboarding / Diagnostics。

## P0 Release

25. packaged backend；
26. Electron installer / portable；
27. release workflow；
28. packaged smoke；
29. GitHub Release；
30. download-back clean install verification。

任何后续新模块都不能排在上述 Release Core 之前。

# 附录 C：一句话判断当前项目（R2）

当前成竹已经不是“缺少核心模块”的阶段，而是进入：

> **强 Intelligence Core 已经存在，但必须把这些能力压缩成一条稳定、低延迟、可解释、可验证、用户能真正感知的 Live 主链。**

---

# 附录 D：最近一轮设计评审吸收矩阵

| 评审意见 | R2 处理 |
|---|---|
| Share Privacy 技术上与 Stealth 使用相似 capture protection | 保留能力，改为 OFF-by-default 私人窗口保护，不承诺不可检测 |
| Human Coach 真实 Live 风险过高 | 新增 Human Assistance Policy；默认 Practice only |
| AI Policy 用户自己选择不构成全部约束 | AI / Human / Privacy 三轴分离，server-side enforce |
| License 为 CC BY-NC 不利于软件长期商业策略 | 用户决定改 MIT；第三方另做 Notices |
| `latest_job_id()` 会污染 Live | InterviewPack 成为唯一 frozen Job 来源 |
| VAD 1.2 秒被指标定义掩盖 | 增加 E/Q0/Q1/G0 时钟与 TTFUG_user |
| VERIFIED 容易被误解成现实真伪验证 | 拆 Provenance / User Assertion / Session |
| Session Claim 会把口误越圆越大 | 只能 consistency warning，不自动当 Evidence |
| 三轴题型没有唯一 routing | 新增统一 route_answer() 决策表 |
| L0 知识题 Cue 来源不清 | PERSONAL / KB / WORLD / COACH 四类 Cue Source |
| Stream Guard 整段 buffer 会变伪流式 | sentence/claim-level 局部 guard |
| Snapshot 只存 version ID 仍会漂 | 生成真正 immutable InterviewPack payload |
| ContextCompiler 接了但 legacy 仍重复注入 | AUTHORITATIVE Gate + fragment dedupe |
| Cue adoption 需要持续分析口述，隐私风险 | Practice 默认可测；Live 默认 OFF、local opt-in |
| 顶层 Prepare 与 Job Prep 重复 | Prepare 收回 Job Goal Workspace |
| 状态色对比度不足 | 更新正文状态色 + automated contrast gate |
| 首次安装、音频、错误恢复不足 | Onboarding / Audio diagnostics / Packaging 进入 Release Gate |
| “功能 PASS”容易过度乐观 | 统一八级实现状态体系 |

本矩阵用于说明 R2 不是附加评论，而是已经将评审意见融入正式定义、数据模型、UI、Gate 和 Release 标准。

# 附录 E：v1.3 产品体验新增验收矩阵

| 能力 | 设计完成条件 | 产品完成条件 |
|---|---|---|
| Goal Room | IA / wireframe 明确 | Goal 中 Prep / Sessions / Next Focus 真串起来 |
| Quick Notes | Material role 定义 | 可选入 Pack、Live 快捷展开、Review 手工回写 |
| Command Palette | 命令模型明确 | Ctrl+K 按上下文展示可执行动作 |
| Guided First Practice | 流程明确 | 新用户能跑完 audio→cue→overlay→review |
| Practice Persona | round/demeanor/difficulty 定义 | 下一问受 persona/answer/graph 共同影响 |
| Content/Delivery Coach | 指标分层 | 不再用一个综合分掩盖不同问题 |
| Pin Moment | 事件结构明确 | Review 第一屏可优先呈现 |
| Nudge | trigger/priority 定义 | 不抢 Fast Cue、不打断用户说话 |
| Closing Mode | route 定义 | 可用本场真实内容生成 ask-back questions |
| Material Lifecycle | Processing/Ready/Failed | 替换处理中旧版继续可用 |
| Language Layering | 五层配置定义 | UI/ASR/Answer/Code/Term policy 可独立 |
| Compact Overlay | Dock/Interaction/Size | idle 缩小、cue 到达展开、可回 compact |
| Reflection → Next Focus | write-back contract | 下一次 Goal Overview 真更新 |

---


# 附录 G：Personal Conversation Intelligence 继承矩阵

| v1.1 长期设计 | v1.3-R2 当前归属 | 当前是否实现 | 未来 Profile |
|---|---|---:|---|
| Person Representation | Candidate/Person Core | 部分 | 共用 |
| Goal / Session Representation | Goal + InterviewPack | Interview 已实现 | 泛化 |
| Conversation State | Interview State | Interview 已实现 | 扩展 |
| Counterparty State | Interviewer State 雏形 | 部分 | 扩展 |
| Expression Planner | Answer Planner | Interview 已实现 | 泛化 |
| Recall | Long-term Memory / Review context | 基础存在 | Future UI |
| Talking Point | Nudge 雏形 | 部分 | Future |
| Answer Cue | Fast Cue | 已实现 | 共用 |
| Question | Closing Mode / Nudge 雏形 | v1.3 设计 | Future |
| Risk / Contradiction | Provenance / Stream Guard | Interview 已实现部分 | 扩展 |
| Delivery | Delivery Coach | v1.3 设计 | 共用 |
| Contribution Opportunity | 无完整 runtime | 未实现 | v2.0 研究核心 |
| Decision / Commitment / Task | 无完整会议模型 | 未实现 | v2.0 |
| Before / During / After | Prepare / Live / Reflection | Interview 已有同构 | 泛化 |
| Desktop Sidecar | Electron + Audio + Overlay | 已实现基础 | 共用 |
| Connector / MCP | 未进入 release scope | 未实现 | Future |

本矩阵用于防止后续母版再次只保留“v2.0 Meeting”一句话，而丢掉已经形成的长期架构和产品定义。

---
# 附录 F：v1.3 设计收敛检查

任何新增功能在进入开发前先回答：

1. 它属于 Person、Goal、Pack、Session 还是 Reflection？
2. 用户在什么时刻需要它？
3. 它应该是页面、上下文动作、Command，还是系统后台能力？
4. 它是否已经有别的入口？
5. 它是否会让 Live 第一屏多一个永久元素？
6. 它是否能转化成 Next Focus / Cue / Reflection 中的一个可执行结果？
