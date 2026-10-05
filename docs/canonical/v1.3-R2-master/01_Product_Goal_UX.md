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
