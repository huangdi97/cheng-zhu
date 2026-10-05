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

