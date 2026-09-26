# Intelligence Core 架构总览

> CURRENT · 对应 canonical：[docs/canonical/Chengzhu_v1.0-R1_CANONICAL.md](../canonical/Chengzhu_v1.0-R1_CANONICAL.md) 第 7、33、34 节。
> 本文描述**已实现**的系统；设计愿景以 canonical 为准。

## 1. 定位

成竹 v1.0 的核心不是多 Agent 数量，而是**八个可解释模块 + 增强层**（canonical 第 7 节）。所有模块落在 `backend/services/intelligence/`，通过 `types.py` 中的显式 typed contract 交互，禁止跨模块传 raw dict。新模块通过 facade/adapter 吸收现有能力（canonical 第 33 节），`services/answer_grounding.py` 始终是安全基础，永不被削弱。

## 2. 八模块总览

| # | 模块 | 职责 | 入口 API | 落点文件 |
| --- | --- | --- | --- | --- |
| 1 | Candidate Representation | 简历 → 结构化候选人表示（claim/evidence/experience/skill…），纯确定性无 LLM | `build_candidate_representation` / `rebuild_and_persist` | `backend/services/intelligence/candidate_representation.py` |
| 2 | Evidence Graph / Truth Boundary | claim-evidence 关系图 + 个人事实边界（输出空间、claim policy、生成后检查） | `analyze_truth_boundary` / `check_generated_answer` / `claims_for_subject` | `truth_boundary.py`（facade）+ `evidence_graph.py` |
| 3 | Job Representation | JD → 结构化岗位 + 可解释 alignment（5 状态，不出"93% match"） | `build_job_representation` / `compute_alignment` | `job_representation.py` |
| 4 | Interview State | 这场面试进行到哪里：versioned state，增量事件 fold，快照恢复 | `apply_event` / `get_state` / `restore_from_snapshot` | `interview_state.py` |
| 5 | Question Understanding | 面试官真正在问什么：21 类题型 + intent + 指代消解 | `understand_question` / `classify_question_type_21` | `question_understanding.py` + `followup_resolver.py` |
| 6 | Context Compiler | 从全部上下文编译"最小充分上下文包"（Provider 接口 + 评分 + 预算） | `ContextCompiler.compile` | `context_compiler.py` + `retrieval.py` |
| 7 | Answer Planner | 决定 HOW 回答：mode/structure/claim 约束，永远不出事实 | `create_plan` / `route_for` | `answer_planner.py` |
| 8 | Open-world Reasoning | 没有简历证据 ≠ 不能回答：路由允许 World Knowledge = yes | `WorldRoute` / `route_world_knowledge` | `world_reasoning.py` |

## 3. 各模块要点

**Candidate Representation**（canonical 第 8 节）：确定性 builder，action verbs → `SUPPORTED`，"熟悉/了解/掌握" → `INFERRED`，绝不生成超出原文的事实。空简历返回空表示而非异常。

**Evidence Graph / Truth Boundary**（canonical 第 9 节）：`evidence_graph.py` 维护 claim→evidence provenance 与 composite-subject 规则（问 "Redis Cluster" 不会静默变成更宽的 "Redis" claim）；`truth_boundary.py` 是 `answer_grounding.py` 的 compatibility facade，输出空间 3 值 + 生成后 6 类 violation 检查。

**Job Representation**（canonical 第 10 节）：JD 展开为 company/title/level/requirements（must-have / nice-to-have / technology / competency），alignment 使用 `STRONG_MATCH / PARTIAL_MATCH / KNOWLEDGE_MATCH / GAP / UNKNOWN` 五个可解释状态。

**Interview State**（canonical 第 11 节）：state 是 `InterviewEvent` 的 fold，LLM 每轮不重写整场；每个已提交版本持久化为 `interview_state_snapshot`，崩溃后可精确恢复。

**Question Understanding**（canonical 第 13 节）：21 类题型判定 + bare follow-up（"为什么不用那个？"）对 recent question / topic / open threads / 最近 claim 的消解，输出完整问题而非悬挂 cue。

**Context Compiler**（canonical 第 14-15 节）：Provider 贡献候选 → 可解释权重评分 → rerank → token 预算裁剪。Fast(1400)/Deep(3200) 双预算；单项 provider 失败不丢整个包。

**Answer Planner**（canonical 第 16-17 节）：吸收 `answer_depth.py`（深度契约）与 `copilot_strategy.py`（interviewer focus 意图），先输出结构化 plan（mode/structure/claim 约束/深度/surface），同一 LLM 不同题型产生可见不同的结构。

**Open-world Reasoning**（canonical 第 18 节）：`_KNOWLEDGE_ONLY_TYPES`（KNOWLEDGE/CODING/SYSTEM_DESIGN/OOD/DEBUGGING/CASE/PRODUCT/BUSINESS/COMPANY/META）不要求个人证据；严禁把"没有简历证据"误判成"不能回答"。

## 4. 增强层（第二层）

| 能力 | 职责 | 落点文件 |
| --- | --- | --- |
| Interviewer State | 概率性面试官 focus/concerns，只服务 planner | `interviewer_state.py` |
| Personal Voice | 真实口述统计的表达风格（不改变事实边界） | `voice_profile.py` |
| Controlled Memory | Review/Mock → 长期记忆的白名单写回 | `memory_policy.py` + `review_writeback.py` |
| Realtime Bridge | 现有 answer pipeline 的一键接入点 | `realtime_bridge.py` |
| Telemetry | 统一 observability 事件（fire-and-forget） | `telemetry.py` |

## 5. 与现有模块的兼容映射（canonical 第 33 节）

| 现有模块 | 演进为 | 现状 |
| --- | --- | --- |
| `services/answer_grounding.py` | Truth Boundary compatibility facade | ✅ `truth_boundary.py` 引用其确定性规则 |
| `services/question_turn_parser.py` | Question Understanding + Follow-up Resolver 的一部分 | ✅ 语音分段留在原处，题型判定升级 |
| `services/memory.py` | Working / Session Memory provider | ✅ 经 `SessionMemoryProvider` 注入 |
| `services/answer_depth.py` + `services/copilot_strategy.py` | Answer Planner | ✅ 深度契约 + intent 已吸收 |
| `services/kb/` | Personal Extended Context | ✅ 经 `KBProvider` 注入，不当候选人全部事实 |
| `services/skill_builder.py` | Candidate enrichment + Gap discovery | ✅ prep/技能卡保留 |

## 6. 持久化与 API

- 存储：`backend/services/storage/intelligence.py` + `intelligence_migrations.py`（`intelligence.db`，17 张表，schema versioning，WAL，`backup_database()` 升级前快照）。现有 5 个用户库（prep/review/knowledge/resume_history/job_tracker）不被触碰。
- REST：`backend/api/intelligence/router.py`，注册前缀 `/api/intelligence`，全部端点确定性/存储读写，无 LLM 调用。

## 7. Feature Flags（`backend/core/config.py:170-187`）

| Flag | 默认 | Stage | 含义 |
| --- | --- | --- | --- |
| `intelligence_candidate_v1` | `True` | A | 简历 → 结构化候选人表示 |
| `intelligence_context_compiler_v1` | `True` | G | 最小充分上下文包（**尚未接入 answer_worker**） |
| `intelligence_answer_planner_v1` | `True` | H | 结构化回答计划 + Truth Boundary post-check |
| `intelligence_live_cue_v1` | `True` | J | Live cue-first 双路径 + TTFUG/turn telemetry |
| `interviewer_state_enabled` | `True` | F | 概率性面试官状态；关闭时系统功能完全正常 |
| `voice_profile_enabled` | `False` | M | 个人表达风格；关闭时答案不受风格影响 |
| `ai_policy_mode` | `"AI_ALLOWED"` | P | AI_FORBIDDEN / AI_LIMITED / AI_ALLOWED / AI_EXPECTED |
| `raw_audio_retention_sessions` | `0` | P | 原始音频保留场次；0 = 不长期保存 |

关闭任一 flag 时系统降级到既有确定性路径，功能不中断（canonical 第 33.1 节 feature flag 接入策略）。

## 8. 落地状态与已知风险

- Context Compiler 已实现并有单测（`test_intelligence_compiler_planner.py`），但 `answer_worker` 尚无调用点——`intelligence_context_compiler_v1` 当前只定义未消费。
- `realtime_bridge.py` 无直接单测；其失败会降级到 legacy path（`answer_worker.py:1144-1146` 记录 warning）。
- `pipeline.py`（2415 行）/`answer_worker.py`（1687 行）仍超 300 行硬限制，是后续瘦身目标（baseline audit 第 5 节）。
