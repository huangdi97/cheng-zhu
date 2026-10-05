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