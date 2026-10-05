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
- SYSTEM_DESIGN；- CODING；
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
