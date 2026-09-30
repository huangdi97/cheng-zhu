# 成竹 Chengzhu v1.0-R1
## 产品 · 算法 · AI 系统 · 实时工程 · UX · 数据 · 评测 · 商业化统一全量设计母版

**版本**：v1.0-R1  
**日期**：2026-09-25  
**状态**：CANONICAL MASTER  
**中文品牌**：成竹  
**英文品牌**：Chengzhu  
**品牌来源**：胸有成竹  
**英文品牌句**：Ready before you speak.  
**中文品牌句**：胸有成竹，从容上场。  
**核心产品原则**：Resume-first, not Resume-bound.

---

# 0. 本文档的地位

本文件用于统一成竹后续的产品、算法、AI 编排、后端、桌面端、前端、数据结构、评测、测试、隐私、安全、商业化与版本路线。它不是一次功能脑暴，也不是把现有代码推倒重做的“理想架构图”。

从本版本开始，成竹不再被定义为“实时语音转文字 + LLM 回答 + 悬浮窗”，而被定义为：

> **一个从简历启动、但不受简历限制的开放世界实时面试智能体。**

它需要同时理解：

- 候选人是谁、真正做过什么；
- 当前岗位与公司需要什么；
- 面试当前聊到了哪里；
- 面试官这一问真正想验证什么；
- 哪些内容属于用户事实、哪些属于通用知识、哪些属于现场推理；
- 此刻最适合给用户的是答案、结构、证据、提醒、边界，还是追问意图。

最终核心不是 Question → Answer，而是：

```text
Candidate
+ Job
+ Company
+ Interview History
+ Current Question
+ Screen / Code Context
+ Personal Evidence
+ Domain / World Knowledge
+ Reasoning
        ↓
Interview Intelligence
        ↓
Response Strategy
        ↓
Live Guidance
```

---

# 1. 2026-09-25 当前仓库基线

仓库：`huangdi97/cheng-zhu`  
默认分支：`main`  
当前公开基线提交：`6dfa47520246a35350cfb5090a5abbc22a84739d`  
提交信息：`Initial public release: Cheng Zhu`

该提交的 GitHub CI 已成功通过。当前仓库并不是空白 MVP，而是已经具有较完整的本地优先实时面试工作台。

## 1.1 当前工程规模

仓库当前约 424 个 tracked blob/file，其中：

- backend：约 185 个文件；
- frontend：约 182 个文件；
- desktop：约 14 个文件；
- docs：约 21 个文件；
- test/spec/playwright 相关文件约 147 个。

这些数字用于表明当前系统已经进入“继承式演进”阶段，而不是“从零搭一个 demo”。

## 1.2 当前技术栈

现状：

- 桌面端：Electron；
- 前端：React 18 + TypeScript + Vite + Tailwind + Zustand；
- 后端：Python 3.11 + FastAPI；
- 实时：WebSocket；
- 本地数据：SQLite；
- 音频：系统音频/loopback + 麦克风双通道；
- STT：远端 STT + Whisper fallback；
- LLM：多 provider、多模型、并行与降级；
- 测试：pytest、Vitest、Playwright、Node test；
- CI：backend/frontend/desktop/E2E/visual regression/e2e-smoke 聚合 gate。

## 1.3 已实现能力

现有代码已经具备：

- 面试官线路与候选人麦克风双通道采集；
- VAD、流式 ASR、partial/final 处理；
- ASR 问题合并、问题块分组与 interrupt；
- 多模型回答调度、健康状态与 fallback；
- 简历、JD、Notes、Rolling Memo 注入；
- 回答深度与回答 grounding；
- 简历历史；
- 面试 PrepSpace；
- Skill Builder；
- Mock / Practice；
- 本地知识库 RAG；
- md/txt/docx/pdf 文档加载；
- OCR/Vision 辅助；
- 截图解题；
- 多会话；
- 面试复盘；
- 候选人实际口述采集；
- ASR 纠错；
- 知识点沉淀；
- Job Tracker / Offer Compare；
- 中英回答；
- 面试官问题翻译；
- TTS；
- 快捷键；
- Overlay；
- UI 主题、可访问性和视觉回归；
- Windows 本地启动。

## 1.4 当前已经存在、必须复用的“新架构雏形”

以下文件不能被当作旧代码随意删除，它们已经包含成竹 v1.0 所需要的部分能力：

- `backend/services/answer_grounding.py`
  - 已经实现“个人经历不能由 LLM 随意决定”的确定性 grounding；
  - 是未来 Truth Boundary 的直接基础。

- `backend/services/answer_depth.py`
  - 是未来 Answer Planner 的一部分。

- `backend/services/copilot_strategy.py`
  - 是未来回答策略层的现有雏形。

- `backend/services/question_turn_parser.py`
  - 是 Question Understanding / Follow-up Resolver 的现有基础。

- `backend/services/memory.py`
  - 是 Interview State / Working Memory 的现有基础。

- `backend/services/kb/*`
  - 保留作为 Personal Extended Context / Document Retrieval Provider。

- `backend/services/resume.py`
  - 保留作为 Candidate Bootstrap 输入。

- `backend/services/skill_builder.py`
  - 不再作为“回答边界”，但可转成 Candidate Representation 的 enrichment 工具。

- `backend/api/assist/pipeline.py`
  - 是实时链路核心，不允许一次性重写；
  - 新 Intelligence Core 应逐步接入。

- `backend/api/assist/answer_worker.py`
  - 是模型调用和流式回答主路径之一；
  - 后续逐步由 Answer Plan + Compiled Context 驱动。

## 1.5 当前必须修正的品牌写法

历史仓库里存在 `成竹 Cheng Zhu` / `Cheng Zhu`。

从 v1.0-R1 开始统一：

- 中文：`成竹`
- 英文：`Chengzhu`
- 全大写视觉：`CHENGZHU`

不再使用 `Cheng Zhu` 作为正式英文品牌。

---

# 2. 为什么需要从“实时助手”升级为 Interview Intelligence

第一代 AI 面试助手基本已经完成以下范式：

```text
Audio
↓
ASR
↓
Question
↓
Prompt + Resume
↓
LLM
↓
Answer
```

这个能力已经高度商品化。

真正还没有被解决好的问题是：

1. 简历被当成答案边界，导致简历外问题表现僵硬；
2. 个人事实与通用知识混在一起，容易把“知道”说成“做过”；
3. 对“为什么？然后呢？如果再扩大呢？”这类追问理解不足；
4. 上下文越积越多，旧主题污染新问题；
5. 每题都生成长答案，用户根本来不及看；
6. 回答像统一模板，不像候选人本人；
7. 没有真正理解 interviewer intent；
8. 面试前、面试中、面试后没有形成持久学习闭环；
9. “隐形/不可检测”容易成为短期军备竞赛，而不是长期产品资产。

成竹 v1.0 的战略楔子因此不是“更隐蔽”，而是：

> **个人事实一致性 + 开放世界推理 + 实时状态理解 + 最小充分上下文 + 合适的回答策略。**

---

# 3. 品牌定义

## 3.1 品牌

**成竹 Chengzhu**

成竹来自“胸有成竹”。

不是说 AI 临时替用户找一个答案，而是：

> 在真正开口之前，已经形成理解、判断和准备。

## 3.2 品牌语言

主品牌句：

> **胸有成竹，从容上场。**

英文：

> **Ready before you speak.**

产品差异：

> **理解你，也理解这一问。**

实时体验：

> **每一个追问，都接得住。**

## 3.3 品牌禁区

不要把以下词作为核心品牌心智：

- undetectable
- invisible cheating
- bypass
- anti-proctoring
- stealth as the main promise

产品可以保护用户隐私、提供不干扰面试的 UI，但不得把规避规则与反作弊作为能力卖点。

---

# 4. 正式产品定义

> **成竹 Chengzhu 是一个以简历为起点、具备开放世界知识与推理能力、持续理解实时面试上下文，并严格区分个人事实、知识判断和假设推理的 Personal Interview Intelligence。**

英文：

> **Chengzhu is a resume-bootstrapped, open-world, evidence-grounded, real-time interview intelligence system.**

关键词：

- Resume-bootstrapped
- Not Resume-bound
- Open-world
- Evidence-grounded
- Context-aware
- Reasoning-native
- Real-time
- Local-first
- Longitudinal

---

# 5. 第一原则：简历是 Seed，不是 Prison

简历负责告诉系统：

> 用户做过什么。

它不能决定：

> 用户只能回答什么。

必须严格区分三类输出。

## 5.1 Personal Fact

用户真实做过的事情。

例如：

> “我在这个项目里使用了 Redis 做 session state。”

必须有用户材料、代码、文档、用户确认或其他可信证据支撑。

## 5.2 Knowledge / Judgment

用户没有声称做过，但可以基于知识进行解释、分析和判断。

例如：

> “从架构上看，如果 Redis 成为热点，可以考虑……”

无需简历里出现。

## 5.3 Hypothetical / Design

纯粹开放推演。

例如：

> “如果把这个系统扩到百万 DAU，我会先测瓶颈，再考虑分片、异步化、缓存策略和降级……”

不能自动改写成：

> “我们当时就是这么做的。”

这就是成竹 v1.0 的 Truth Boundary。

---

# 6. 五层信息世界

## L1 Resume Facts

简历显式事实：

- 教育；
- 公司；
- 项目；
- 角色；
- 技术；
- 成果；
- 指标；
- 时间。

## L2 Personal Extended Context

简历之外但属于用户的真实材料：

- GitHub；
- README；
- 项目设计文档；
- 代码；
- Portfolio；
- 个人网站；
- 论文；
- 历史面试；
- 用户补充；
- 用户确认的回答；
- 知识笔记。

## L3 Live Interview Context

当前面试：

- 当前 utterance；
- 前几轮问题；
- 候选人刚才的回答；
- 当前主题；
- 当前代码；
- 当前截图；
- 已建立的假设；
- 是否追问/打断；
- 当前 open thread。

## L4 Domain / World Knowledge

与候选人是否写进简历无关：

- 算法；
- 数据库；
- AI；
- LLM；
- Agent；
- 生物医药；
- 产品；
- 管理；
- 公司公开资料；
- 行业知识。

## L5 Novel Reasoning

没有现成答案的问题：

- system design；
- case；
- hypothetical；
- “如果重做”；
- “如果流量扩大 100 倍”；
- “如果你来负责这个业务”。

---

# 7. 成竹 Intelligence Core

v1.0 的核心不是多 Agent 数量，而是八个可解释模块。

```text
Candidate Representation
        +
Evidence Graph / Truth Boundary
        +
Job Representation
        +
Interview State
        +
Question Understanding
        +
Context Compiler
        +
Answer Planner
        +
Open-world Reasoning
```

第二层：

```text
Interviewer State
Personal Voice
Cross-session Learning
Model Router
```

---

# 8. Candidate Representation

Candidate Representation 是“系统当前如何表示这个候选人”，不是训练一个新的 LLM。

它由结构化数据库、逻辑图、文本证据和向量/词法索引共同组成。

## 8.1 核心实体

```text
Candidate
├── Identity
├── Education
├── Experience
├── Project
├── Skill
├── Domain
├── Achievement
├── Decision
├── Challenge
├── Failure
├── Tradeoff
├── Story
├── CommunicationProfile
└── Evidence
```

## 8.2 Experience Expansion Graph

简历一条：

> “构建基于 RAG + Agent 的智能问答系统。”

自动展开成可追问维度：

```text
why
problem
users
role
architecture
data
retrieval
rerank
evaluation
latency
cost
agent orchestration
memory
failure
tradeoff
deployment
observability
scale
if-redo
```

注意：

> 自动生成的是“问题节点”和“待补信息”，不是自动生成个人事实。

---

# 9. Evidence Graph 与 Truth Boundary

## 9.1 Claim 状态

每个个人事实 Claim 必须具有状态：

- VERIFIED
- SUPPORTED
- INFERRED
- UNKNOWN
- CONTRADICTED

## 9.2 证据来源

Evidence 可以来自：

- resume；
- user-confirmed；
- project document；
- GitHub code；
- README；
- interview transcript；
- imported note；
- external profile。

## 9.3 生成规则

Personal Fact 模式：

- VERIFIED / SUPPORTED：允许第一人称事实表达；
- INFERRED：不得升级成“我做过”；
- UNKNOWN：必须设边界；
- CONTRADICTED：不得直接生成确定性声称。

## 9.4 与当前 `answer_grounding.py` 的关系

现有 deterministic grounding 保留并增强。

迁移目标：

```text
answer_grounding.py
        ↓ compatibility facade
services/intelligence/truth_boundary.py
```

不允许在新架构落地过程中暂时移除原有安全约束。

---

# 10. Job Representation

每个目标岗位建立：

```text
Job
├── company
├── title
├── level
├── jd
├── responsibilities
├── must-have
├── nice-to-have
├── technologies
├── competencies
├── likely interview dimensions
├── company context
└── candidate alignment
```

不要只生成一个“匹配度 93%”。

使用可解释状态：

- STRONG_MATCH
- PARTIAL_MATCH
- KNOWLEDGE_MATCH
- GAP
- UNKNOWN

---

# 11. Interview State

Interview State 表示：

> 这场面试现在进行到了哪里。

建议状态：

```yaml
phase: technical_deep_dive
topic_stack:
  - agent_architecture
  - rag
current_topic: rag
question_type: follow_up
intent: architecture_tradeoff
candidate_claims:
  - hybrid_retrieval_used
open_threads:
  - why_not_finetuning
risk_flags:
  - redis_depth_uncertain
language: zh-CN
expected_depth: mid_senior
```

Interview State 必须是增量更新，而不是每轮重新总结整场。

---

# 12. Interviewer State

Interviewer State 是概率性推断，不是事实。

示例：

```yaml
possible_focus:
  engineering_depth: 0.82
  authenticity: 0.71
  product_thinking: 0.43
possible_concerns:
  rag_evaluation: 0.76
  production_depth: 0.58
```

它主要服务 Answer Planner。

UI 默认不展示“面试官认为你不行”之类确定性句子。

可展示：

> “当前追问可能在验证：工程深度 / 真实性。”

---

# 13. Question Understanding 与 Follow-up Resolver

## 13.1 Question Type

至少支持：

- SELF_INTRODUCTION
- EXPERIENCE
- PROJECT_DEEP_DIVE
- BEHAVIORAL
- KNOWLEDGE
- CODING
- SYSTEM_DESIGN
- OOD
- DEBUGGING
- HYPOTHETICAL
- CASE
- PRODUCT
- BUSINESS
- ROLE_FIT
- COMPANY
- CAREER
- SALARY
- NEGOTIATION
- FOLLOW_UP
- CLARIFICATION
- META

## 13.2 Follow-up Resolver

输入：

> “为什么不用那个？”

输出应解析为：

> “为什么该项目选择 RAG 而没有选择 fine-tuning？”

必须利用：

- 最近问题；
- 当前 topic；
- open thread；
- 候选人最近 claim；
- 语义指代。

现有 `question_turn_parser.py` 应逐步升级，而不是另造一个重复 parser。

---

# 14. Context Compiler

这是成竹 v1.0 最关键技术内核之一。

定义：

> 根据当前问题，从所有可能上下文中编译出“最小充分上下文包”。

输入：

```text
Resolved Question
Candidate Representation
Evidence Graph
Job Representation
Interview State
Interviewer State
Personal KB
Recent Dialogue
Screen Context
World Knowledge
```

输出：

```text
CompiledContext
```

## 14.1 为什么不是“把资料全塞进去”

实时面试要求：

- 低延迟；
- 高相关；
- 低冲突；
- 低 token；
- 低旧主题污染。

因此目标不是 max context，而是 minimum sufficient context。

## 14.2 Context Candidate Score

第一阶段采用可解释规则 + reranker：

```text
score(c) =
  w1 * semantic_relevance
+ w2 * lexical_entity_match
+ w3 * evidence_strength
+ w4 * interview_recency
+ w5 * topic_continuity
+ w6 * job_alignment
+ w7 * candidate_importance
- w8 * contradiction_risk
- w9 * redundancy
- w10 * stale_topic_penalty
```

权重后续可基于 eval 学习，但 v1.0 必须可配置、可观测。

## 14.3 Retrieval Provider

Context Compiler 不绑定一个检索器。

它从 provider 拉 candidate：

```text
Resume Provider
Candidate Graph Provider
Evidence Provider
Recent Dialogue Provider
Session Memory Provider
KB Provider
Job Provider
Screen Provider
World Knowledge Provider
```

---

# 15. Hybrid Retrieval

不能只使用向量。

```text
Query
├── exact/entity match
├── BM25 / lexical
├── dense semantic
├── graph traversal
├── recency
└── active-topic boost
        ↓
fusion
        ↓
reranker
        ↓
Context Compiler
```

当前本地优先阶段仍以 SQLite 为中心。

不因为“知识图谱”三个字强行引入 Neo4j。

可采用：

- SQLite；
- FTS5；
- JSON；
- 逻辑 edge table；
- 现有 KB；
- 可选 embedding index。

---

# 16. Answer Planner

Answer Planner 不直接写最终自然语言，它先决定：

1. 这是什么题；
2. 面试官可能在验证什么；
3. 是否需要个人事实；
4. 是否允许 open-world；
5. 有哪些 evidence；
6. 哪些内容禁止声称；
7. 回答需要什么结构；
8. 深度到哪里；
9. 先显示 cue 还是完整答案；
10. 下一步可能被追问什么。

输出：

```json
{
  "mode": "EXPERIENCE_KNOWLEDGE",
  "intent": ["architecture_tradeoff"],
  "must_use_claim_ids": ["..."],
  "forbidden_claims": ["..."],
  "structure": ["结论", "项目事实", "技术原因", "trade-off"],
  "depth": "medium",
  "surface": "cue_first"
}
```

现有 `answer_depth.py`、`copilot_strategy.py` 要迁移/吸收进入这一层。

---

# 17. Response Modes

## EXPERIENCE

讲真实项目。

结构：

- 结论；
- 场景；
- 我的职责；
- 关键动作；
- 为什么这样做；
- 结果；
- 反思。

## EXPERIENCE + KNOWLEDGE

先讲自己的项目，再讲技术原理和取舍。

## KNOWLEDGE

直接回答知识，不强套简历。

## HYPOTHETICAL

使用“如果让我设计/如果规模变化”表达。

## OPEN_DESIGN

```text
Clarify
Requirements
Architecture
Data
Scale
Reliability
Security
Observability
Cost
Trade-offs
Evolution
```

## BEHAVIORAL

优先从真实 Story Bank 检索。

没有真实故事，不编事件。

## EXPERIENCE_BOUNDARY + KNOWLEDGE

典型：

> “你实际用过 Kubernetes 吗？”

没有证据时：

```text
事实边界
↓
相关经验
↓
对该技术的理解
↓
如果落地会怎么做
```

---

# 18. Open-world Reasoning

成竹必须原生支持简历外问题。

例如：

- “Transformer 为什么需要 positional encoding？”
- “Redis 和 Memcached 怎么选？”
- “设计一个短视频系统。”
- “如果流量增长 100 倍怎么办？”
- “如果让你给药企设计 multi-agent 平台？”

Question Router 必须允许：

```text
Personal Evidence = none
World Knowledge = yes
Reasoning = yes
```

然后正常回答。

严禁把“没有简历证据”误判成“不能回答”。

---

# 19. 双路径实时生成：Fast Path + Deep Path

实时使用不能等完整长答案。

## Fast Path

目标：

> 先给“能用的第一屏”。

输出：

- 一句话结论；
- 3–5 个关键词；
- 回答骨架。

目标 TTFUG：尽量 < 1.5 秒。

## Deep Path

并行继续：

- evidence；
- trade-off；
- 详细推理；
- full answer；
- follow-up prediction；
- caution。

UI progressive disclosure。

---

# 20. Live Guidance Surface

不是所有问题都展示完整答案。

支持：

- QUICK CUE
- STRUCTURE
- EVIDENCE
- FULL ANSWER
- INTENT
- TRADEOFF
- CAUTION
- FOLLOW-UP

默认第一屏：

```text
当前问题
为什么不用 fine-tuning？

核心思路
• 数据持续更新
• 可追溯
• 成本与迭代速度

我的证据
WenNian · RAG 决策

[展开]
```

目标：

> 用户扫一眼就能继续说，而不是低头照稿念。

---

# 21. 实时主链路

```text
System Audio / Microphone
        ↓
Audio Capture
        ↓
VAD
        ↓
Streaming ASR
        ↓
Stable Utterance
        ↓
Question / Follow-up Resolution
        ↓
Question Understanding
        ↓
Interview State Update
        ↓
Context Compiler
        ↓
Answer Planner
        ↓
Model Router
        ↓
Truth / Contradiction Check
        ↓
Streaming Guidance
        ↓
Candidate Speech
        ↓
Session Memory / Review
```

并行：

```text
Screen / Region Capture
        ↓
Vision / OCR
        ↓
Screen Context
        ↓
Context Compiler
```

---

# 22. 音频与 ASR

现有双通道能力继续保留：

- interviewer/system audio；
- candidate microphone。

重点升级：

1. partial 与 final 清晰分层；
2. utterance boundary；
3. question group；
4. late constraint；
5. interrupt；
6. topic reset；
7. 候选人真实回答与 assistant guidance 严格分开。

ASR 纠错不得改变语义。

所有 corrected transcript 应保留：

- raw；
- corrected；
- correction metadata。

---

# 23. Memory Architecture

三级 Memory。

## Working Memory

当前几分钟。

高精度、可回溯。

## Session Memory

整场面试。

保存：

- topic；
- question tree；
- claims；
- open threads；
- key constraints。

## Long-term Candidate Memory

跨面试。

只写入：

- 已确认个人事实；
- 用户确认的表达偏好；
- 多次重复暴露的知识薄弱点；
- 用户确认的复盘结论。

禁止把一次 LLM 的 interviewer inference 永久写成事实。

---

# 24. Personal Voice

目标：

> 答案越来越像这个人，而不是越来越像“AI 面试模板”。

Voice Profile 包括：

- 首句习惯；
- 句子长度；
- 技术表达密度；
- 是否先结论；
- 是否喜欢举例；
- 是否习惯口语；
- 中文/英文；
- seniority；
- 禁用模板短语。

Voice Profile 的学习必须由真实候选人口述优先，而不是 assistant 自己生成的答案。

---

# 25. Prepare

围绕 Job Workspace 组织。

一场目标岗位包括：

- JD；
- 公司；
- Candidate × Job Alignment；
- 简历攻击面；
- Gap Map；
- Question Graph；
- Story Bank；
- Quick Mock；
- Deep Mock。

不要把“题库”做成产品中心。

---

# 26. Mock Interview

Mock 不是随机抽题。

根据：

```text
Candidate Representation
+ Job Representation
+ Gap Map
+ Previous Performance
```

动态决定下一问。

Interview Agent 需要：

- 深挖；
- 质疑；
- 要数字；
- 要 trade-off；
- 改变假设；
- 打断；
- 连续追问；
- 检验真实性。

形成 Question Tree，而不是 Question List。

---

# 27. Coding Interview

输出顺序：

```text
Problem Understanding
Clarifying Questions
Approach
Complexity
Code
Edge Cases
How to Explain
```

屏幕识别属于 context provider，不另起一套孤立逻辑。

---

# 28. System Design

专门模式：

```text
Clarify
Functional Requirements
Non-functional Requirements
Capacity
API
Data Model
High-level Architecture
Deep Dive
Scale
Reliability
Security
Observability
Cost
Trade-offs
Evolution
```

根据岗位级别裁剪。

---

# 29. Behavioral Interview

建立真实 Story Bank：

```text
Story
├── situation
├── challenge
├── action
├── result
├── reflection
├── competency tags
└── evidence
```

没有真实故事：

> 提供找故事的方向，不生成虚构经历。

---

# 30. Post-interview Debrief

每场结束生成：

- Timeline；
- Question Tree；
- 能力展示；
- Missing Signals；
- Weak Answers；
- Fact Risk；
- Knowledge Gap；
- Communication issues；
- 下一轮重点。

最重要的是：

> Review 结果必须能选择性回写 Candidate Representation / Skill Gap。

---

# 31. Cross-session Learning

长期形成：

```text
过去 6 场：
RAG evaluation 被追问 4 次；
Redis production depth 被追问 3 次；
System design 回答偏长；
行为题经常缺少量化结果。
```

下一场准备自动优先这些部分。

---

# 32. 数据结构建议

v1.0 保持 SQLite，不迁 PostgreSQL/Neo4j。

新增版本化 Intelligence Storage。

核心表：

```text
candidate_profile
experience
project
claim
evidence
claim_evidence
skill
story
job_profile
job_requirement
candidate_job_alignment
interview_session
interview_turn
interview_state_snapshot
guidance_event
memory_item
voice_profile
```

每张表必须具有 schema version / created_at / updated_at。

所有 migration 必须：

- 可重复；
- 可测试；
- 可回滚或至少可恢复；
- 不破坏现有用户数据。

---

# 33. 当前代码到目标架构的映射

## 33.1 不重写 `pipeline.py`

目标：

逐阶段接入：

```text
pipeline
  ↓
QuestionUnderstanding
  ↓
InterviewStateService
  ↓
ContextCompiler
  ↓
AnswerPlanner
  ↓
answer_worker
```

早期通过 feature flag。

## 33.2 `answer_grounding.py`

演进成：

> Truth Boundary compatibility facade。

## 33.3 `question_turn_parser.py`

演进成：

> Question Understanding + Follow-up Resolver 的一部分。

## 33.4 `memory.py`

演进成：

> Working / Session Memory provider。

## 33.5 `copilot_strategy.py` + `answer_depth.py`

演进成：

> Answer Planner。

## 33.6 `kb`

继续服务：

> Personal Extended Context。

不把 KB 当成候选人全部事实。

## 33.7 `skill_builder.py`

从“技能卡即边界”改为：

> Candidate enrichment + Gap discovery。

---

# 34. 推荐代码域

新增：

```text
backend/services/intelligence/
├── __init__.py
├── types.py
├── candidate_representation.py
├── evidence_graph.py
├── truth_boundary.py
├── job_representation.py
├── interview_state.py
├── interviewer_state.py
├── question_understanding.py
├── followup_resolver.py
├── context_compiler.py
├── retrieval.py
├── answer_planner.py
├── world_reasoning.py
├── voice_profile.py
├── memory_policy.py
└── telemetry.py
```

新增 storage：

```text
backend/services/storage/intelligence.py
backend/services/storage/intelligence_migrations.py
```

不要把现有模块全量搬文件后再修逻辑。

优先用 facade / adapter 渐进迁移。

---

# 35. 模型编排

第一阶段不训练自己的大模型。

不同任务不同模型：

- ASR：专用语音模型；
- question classification：fast model；
- follow-up resolution：fast/medium；
- context rerank：reranker/fast model；
- knowledge answer：general model；
- system design：reasoning model；
- behavioral：general strong model；
- vision：multimodal model；
- review：latency-insensitive strong model。

现有多模型配置与健康检查继续复用。

---

# 36. Provider Reliability

所有 provider 统一支持：

- timeout；
- retry；
- fallback；
- circuit breaker；
- health score；
- request id；
- latency；
- token/cost；
- failure reason。

不要因为引入 Intelligence Core 退化现有 fallback。

---

# 37. Latency SLO

核心指标不是“全文完成时间”。

定义：

## TTFUG

Time to First Useful Guidance。

目标：

- ASR partial 更新：尽量 < 300 ms 感知；
- boundary：< 300 ms；
- Context Compiler P50：< 300 ms；
- 第一屏 useful cue：P50 < 1.5 s，P95 持续优化；
- 深度答案允许异步继续流式。

---

# 38. Observability

每个 guidance 记录：

```text
question_raw
question_resolved
question_type
route
active_topic
context_candidates
selected_context
context_scores
evidence_ids
answer_plan
model/provider
ttfug
total_latency
truth_flags
contradiction_flags
user_expand_action
```

提供 replay。

如果无法 replay，就无法系统性优化“为什么这题不好用”。

---

# 39. Eval Harness

必须建立固定 fixtures。

类别：

- resume factual；
- resume-outside knowledge；
- project deep dive；
- follow-up；
- ambiguous follow-up；
- topic reset；
- behavioral；
- coding；
- system design；
- hypothetical；
- company；
- boundary；
- contradiction；
- Chinese；
- English；
- mixed language；
- long session。

每个 fixture：

```text
candidate
job
dialogue_history
question
expected_route
required_facts
forbidden_claims
expected_structure
rubric
```

---

# 40. 必须通过的七轮连续测试

```text
Q1 介绍一下你的项目。
Q2 为什么选 RAG？
Q3 为什么不用 fine-tuning？
Q4 如果数据量扩大 100 倍呢？
Q5 那 Redis 会有什么问题？
Q6 你实际用过 Redis Cluster 吗？
Q7 没用过的话，你会怎么迁？
```

正确路由：

- Q1 EXPERIENCE；
- Q2 EXPERIENCE + KNOWLEDGE；
- Q3 EXPERIENCE + TRADEOFF；
- Q4 HYPOTHETICAL；
- Q5 KNOWLEDGE + CURRENT ARCHITECTURE；
- Q6 TRUTH BOUNDARY；
- Q7 OPEN DESIGN。

如果七题都只是 Resume RAG，则架构失败。

---

# 41. Topic Reset Benchmark

必须测试：

```text
问题 A
→ 追问 A1
→ 限制变化 A2
→ 明确转到新问题 B
→ B 的回答不得被 A 的旧细节污染
```

建立：

- active topic；
- topic stack；
- stale topic penalty；
- explicit reset；
- implicit reset。

---

# 42. Long Session Reliability

必须覆盖：

- 2h；
- 3h；
- 5h soak。

观察：

- memory；
- thread；
- queue；
- WebSocket；
- state growth；
- ASR drift；
- context pollution；
- latency degradation；
- provider fallback；
- audio device switching；
- sleep/wake；
- session recovery。

---

# 43. 前端信息架构

在保留现有 React/Material-style 视觉基础上逐渐收敛成：

```text
首页
我的成竹
岗位
演练
上场
复盘
设置
```

Job Tracker 可作为求职管理能力保留，但不要压过 Interview Intelligence 主流程。

## 首页

核心：

- 下一场面试；
- 当前目标岗位；
- Resume readiness；
- Gap；
- [准备] [演练] [上场]。

## 我的成竹

包括：

- 简历；
- 经历；
- 项目；
- Stories；
- Skills；
- Evidence；
- Voice Profile。

## 上场

默认只显示：

- 当前问题；
- 核心思路；
- 我的证据；
- 展开按钮。

---

# 44. UI 迁移原则

- 不进行“为了新设计而全站重做”；
- 保留现有主题系统；
- 保留可访问性改进；
- 保留 visual regression；
- 新 IA 逐页面迁移；
- 每次改变必须更新 Playwright snapshot；
- Live 页优先信息密度与 glanceability，不追求花哨。

---

# 45. Desktop 策略

v1.0 继续 Electron。

**明确不迁 Tauri。**

理由：

- 当前 Electron 已实现窗口、overlay、快捷键、截图、系统集成；
- 迁移不会提升核心 Interview Intelligence；
- 会增加大量平台风险。

未来只有在明确证据证明：

- 内存；
- 包体；
- 平台能力；
- 安全；
- 启动时间

成为瓶颈时再评估。

---

# 46. Privacy / Local-first

默认：

- 简历本地；
- 本地 DB；
- API key 本地；
- 原始音频不长期保存；
- 尽量只向模型 provider 发送当前必要上下文；
- session 可删除；
- 数据可导出；
- 用户能看到云端处理范围。

后续可做：

- local ASR；
- local embeddings；
- optional local LLM。

---

# 47. Interview Policy Awareness

每场支持策略：

- AI_FORBIDDEN
- AI_LIMITED
- AI_ALLOWED
- AI_EXPECTED

当用户明确标记 AI_FORBIDDEN：

- 成竹保留 Prepare / Mock / Review；
- Live guidance 默认关闭。

不开发反监考、规避检测等能力。

---

# 48. 安全边界

不得：

- 伪造用户工作经历；
- 伪造成果指标；
- 把 inference 写成 verified；
- 自动修改用户证据；
- 把一次 interviewer inference 永久记忆；
- 默认上传原始音频；
- 偷偷更改用户 provider key；
- 降低测试 Gate 来“通过”。

---

# 49. 商业化

建议从求职的阶段性需求出发。

可能方案：

- Free：简历解析 + 少量 Mock + 少量 live；
- Sprint：7/14/30 天求职冲刺；
- Interview Pack：实时分钟；
- Pro：持续使用；
- Student：学生版本。

长期可扩：

- Interview；
- Recruiter Call；
- Salary Negotiation；
- Offer Discussion；
- Networking。

但 v1.0 不提前做 Meeting/Sales。

---

# 50. 北极星指标

不是：

> 生成答案数量。

而是：

> **Useful Interview Moments Assisted**

辅助指标：

- TTFUG；
- Guidance adoption；
- Follow-up continuity；
- Fact precision；
- Unsupported personal claim rate；
- Context relevance；
- Candidate correction rate；
- Mock → Live；
- Review usefulness；
- Return interviews。

---

# 51. v1.0 Gate

## G0 Canonical

新母版落盘，旧文档明确 historical/current。

## G1 Baseline

当前 repo 全量测试、build、CI 合同可复现。

## G2 Candidate Representation

简历可以形成结构化候选人表示。

## G3 Evidence / Truth

事实边界可靠。

## G4 Question / Follow-up

连续追问解析。

## G5 Interview State

topic/open thread/claim 可稳定维护。

## G6 Context Compiler

不同来源可选择最小充分上下文。

## G7 Answer Planner

不同题型使用不同策略。

## G8 Open-world

简历外问题正常回答。

## G9 Live UX

cue-first / progressive disclosure。

## G10 Mock / Review Loop

训练与复盘能更新候选人状态。

## G11 Long-session

长会话无明显状态污染/性能退化。

## G12 Production

安全、隐私、迁移、CI、文档、发布全部闭环。

---

# 52. 版本路线

## v1.0-R1

从现有工作台升级成 Interview Intelligence Core。

必须完成：

- Candidate Representation；
- Evidence Graph；
- Truth Boundary；
- Job Representation；
- Interview State；
- Follow-up；
- Context Compiler；
- Answer Planner；
- Open-world routing；
- cue-first Live；
- eval harness；
- cross-session learning 基础；
- canonical docs。

## v1.1

- Voice Profile 深化；
- Interviewer State；
- company public context；
-更强 Mock；
- 性能调优。

## v1.2

- local embedding；
- local ASR 更完整；
- session intelligence；
- 更强多语言。

---

# 53. 不做清单

当前阶段不做：

- 自研基础大模型；
- Agent swarm 炫技；
- Neo4j 强迁移；
- PostgreSQL/Redis 云化重构；
- Tauri 重写；
- 招聘 ATS；
- 自动投递；
- 社区；
- 简历模板市场；
- “不可检测”军备竞赛；
- 为了功能数量增加新页面。

---

# 54. 成竹最终产品哲学

第一代工具问：

> 这一题答案是什么？

成竹问：

> **这一刻，这个候选人应该如何最好地表达真实的自己？**

第一代工具：

> Resume RAG。

成竹：

> Resume-bootstrapped Candidate Intelligence。

第一代工具：

> 上下文越多越好。

成竹：

> 最小充分上下文。

第一代工具：

> 每题完整答案。

成竹：

> cue-first，再按需展开。

第一代工具：

> AI 替你成为另一个人。

成竹：

> **让你已经拥有的知识、经验和判断，在压力最大的时刻仍能被准确调用出来。**

---

# 55. Canonical Definition

从 v1.0-R1 起，成竹正式定义为：

> **成竹 Chengzhu 是一个从简历启动、但不受简历限制的开放世界实时面试智能体。它通过 Candidate Representation 理解候选人的真实经历，通过 Evidence Graph 与 Truth Boundary 保证个人事实不被模型随意改写，通过 Interview State 理解当前面试正在发生什么，通过 Context Compiler 为每一问选择最小充分上下文，通过 Answer Planner 决定应该以何种结构和深度回答，并利用通用知识与开放世界推理处理个人材料之外的新问题。成竹在准备、模拟、正式面试与复盘之间形成持续学习闭环，使系统随着用户经历与面试次数增长而逐渐成为真正理解用户的 Personal Interview Intelligence。**

核心：

> **Candidate Representation × Interview State × Context Compiler × Answer Planner**

约束：

> **Evidence Graph × Truth Boundary**

增强：

> **Interviewer State × Voice Profile × Cross-session Learning**

品牌：

> **成竹 Chengzhu**

原则：

> **Resume-first, not Resume-bound.**

品牌句：

> **Ready before you speak.**

中文：

> **胸有成竹，从容上场。**

---

# 附录 A：当前仓库演进原则

1. 继承当前 `main` 的稳定功能。
2. 不做 big-bang rewrite。
3. 新 Intelligence Core 先以 feature flag 接入。
4. 新旧路径一段时间并存。
5. 每阶段先写 fixture 与 acceptance test。
6. 数据 migration 先于 UI 依赖。
7. Grounding 永远不得因新功能而降低。
8. Live latency 不得因架构抽象明显退化。
9. CI gate 不得减少来掩盖失败。
10. 所有新 inference 必须区分“事实”与“推断”。

---

# 附录 B：最关键验收样例

用户简历：

> 构建 RAG + Agent 系统，使用 Redis 保存部分 session state。

面试：

**问：你项目为什么用 Redis？**  
应使用真实项目事实 + Redis 原理。

**问：如果流量扩大 100 倍？**  
进入 hypothetical，允许开放系统设计。

**问：你们当时用了 Redis Cluster 吗？**  
如果无证据，不得说用了。

**问：那如果没用过，你会怎么迁？**  
允许基于 Redis Cluster 的通用知识现场设计。

这四问能够稳定切换，才算真正实现：

> Resume-first, not Resume-bound.

---

# 附录 C：当前战略判断

成竹不应该复制一个 AskCc，也不应该只复制一个 GhostInterview。

应该吸收两类产品各自最有价值的思想：

- 个人材料与事实一致性；
- 当前问题优先、最小上下文、开放技术推理；
- 完整 Prepare → Live → Review 闭环；
- 跨 session 学习。

最后形成成竹自己的核心：

> **真实的我 + 此刻的上下文 + 开放世界知识 + 可解释的回答策略。**
