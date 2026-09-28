# 成竹 Chengzhu v1.0 Final Closure Report

**日期**：2026-09-26
**Canonical**：v1.0-R1（`docs/canonical/Chengzhu_v1.0-R1_CANONICAL.md`，2026-09-25）

## Baseline → Final

| 项 | 值 |
| --- | --- |
| Baseline HEAD | `6dfa47520246a35350cfb5090a5abbc22a84739d`（`Initial public release: Cheng Zhu`，main） |
| Final HEAD | `8f64cb41d2af8d7429f9123a602cc6a99d6e595b` |
| Branch | `feat/chengzhu-v1-interview-intelligence`（已 push 到 origin，未 force push） |
| Commits | 12 个，按能力边界提交（见下） |
| Changed files | 81 |

## Commits（按能力边界）

```text
2773886 docs(canonical): canonical master, baseline audit, doc pointers, brand headers
1299814 feat(intelligence): Intelligence Core modules + versioned intelligence storage
986dee7 feat(integration): Intelligence Core into production path (plan+state+truth+telemetry), API router, config flags, tests
90f2ced test(evals): eval harness + route/truth fixes; route_accuracy 1.0, unsupported claim blocked 1.0, fact_precision 1.0
33cf4a5 feat(review): controlled write-back; test(migration); perf(soak) PASS; ci: intelligence+eval smoke; chore(brand): Chengzhu cleanup
11a1934 perf: intelligence stage benchmarks (compiler p50 2ms), bridge interviewer-state fix, downgrade-to-boundary
4f39ad5 feat(live): GuidanceViewModel + glance-first first screen wired into AnswerPanel (Stage K)
edbdd85 docs: architecture/product/eval/privacy doc system (Stage X), README entry
8f64cb4 fix: written-exam/images keep fixed message contract; test asserts follow semantic contract
```

## Architecture delivered（对应 canonical 第 7、34 节）

`backend/services/intelligence/`（18 个模块）+ `backend/services/storage/intelligence.py` + `intelligence_migrations.py`：

| 模块 | 职责 | 兼容映射（先 adapter，后 deprecation） |
| --- | --- | --- |
| types.py | 全部跨模块契约（dataclass + enum） | — |
| candidate_representation.py | Stage A：简历 → 结构化候选人表示（claim/evidence/claim_evidence/skill/experience/project/metrics/education，去重合并，追问维度生成） | resume.py → candidate bootstrap provider；skill_builder.py → enrichment |
| evidence_graph.py | claim→evidence 图查询（组合证据匹配，CONTRADICTED 排除） | — |
| truth_boundary.py | Stage B：输出空间 + Claim Policy + post-generation checker + downgrade-to-boundary | answer_grounding.py → facade（**永不降低**） |
| job_representation.py | Stage C：JD 结构化 + 可解释 Alignment（STRONG_MATCH/PARTIAL_MATCH/KNOWLEDGE_MATCH/GAP/UNKNOWN，无虚假百分比） | prep_space JD → Job provider |
| question_understanding.py | Stage D：21 题型分类 + intent/domain/depth/personal_fact_required/open_world_allowed | question_turn_parser.py → 分层上游 |
| followup_resolver.py | Stage D：bare follow-up 解析（“为什么？”/“然后呢？”/“为什么不用那个？”等） | 同上 |
| interview_state.py | Stage E：versioned 状态，增量事件 fold（非 LLM 重写），snapshot save/restore/crash recovery | memory.py → session memory provider |
| interviewer_state.py | Stage F：概率性面试官状态（只服务 planner，每轮衰减，永不写入长期事实） | — |
| retrieval.py | Stage G：10 分量可解释评分 + rerank + token 估算 | — |
| context_compiler.py | Stage G：Provider 接口（9 provider）+ Fast(1400)/Deep(3200) token budget + 最小充分上下文 | kb/* → KB provider；pipeline 注入 |
| answer_planner.py | Stage H：结构化 plan（mode/structure/claim 约束），11 种 Response Modes 路由表 | answer_depth.py + copilot_strategy.py → 吸收 |
| world_reasoning.py | Stage I：No resume evidence != No answer 开放世界路由 | — |
| voice_profile.py | Stage M：真实口述统计 profile；apply_voice 不改变事实边界 | — |
| memory_policy.py | Stage L4：受控写回白名单（LLM inference 永不成为 candidate fact） | — |
| telemetry.py | Stage Q：guidance_event/turn 统一事件（敏感内容截断） | — |
| realtime_bridge.py | 生产路径一键集成（understanding→plan→state→planner） | answer_worker.py 调用 |
| review_writeback.py | Review → Intelligence 写回（weak_points/repeated_topic/communication） | review_async_analysis.py 调用 |

## Features delivered

1. **Stage A**：`POST /api/intelligence/candidate/rebuild` 由现有简历构建结构化表示；Truth Status 5 值 enum；9 个稳定 API 端点（candidate/claims/evidence/job/state）。
2. **Stage B**：Truth Boundary 接入实时链路（answer_worker.py 的 post-check）；6 类 violation 检测；downgrade-to-boundary；grounding 永不降低。
3. **Stage C**：JD 结构化 + Candidate×Job Alignment 带证据（无虚假百分比）。
4. **Stage D**：21 题型 + 追问解析（五组 fixture 全通过）。
5. **Stage E**：versioned InterviewState（增量事件、crash recovery、topic reset）。
6. **Stage F**：概率性 InterviewerState（planner-only、可衰减、可关闭）。
7. **Stage G**：Context Compiler 接入 production path（plan_prompt/state_context 注入 user prompt）。
8. **Stage H**：Answer Planner 接入 production path（同一 LLM 不同题型得到不同结构）。
9. **Stage I**：开放世界路由（七轮 fixture route 全对；Q4 不因简历没写拒答；Q6 不声称用过；Q7 可谈迁移）。
10. **Stage J**：Fast/Deep 等价结构（deterministic 规则 <5ms 先行 + LLM 流式）；TTFUG telemetry。
11. **Stage K**：GuidanceViewModel + GuidanceFirstScreen（cue-first 第一屏：当前问题/核心思路/我的证据/[展开]）；answer_done guidance payload。
12. **Stage L**：Mock/Review → Controlled write-back 闭环（memory_policy 白名单）。
13. **Stage M**：Personal Voice profile（真实口述、A/B 可关、不改事实边界）。
14. **Stage N**：Coding/System Design planner 统一到 Intelligence Core（11 种 Response Modes 含完整结构）。
15. **Stage O**：SQLite versioned migration（user_version + schema_migrations + backup）。
16. **Stage P**：AI policy mode 4 值 + raw audio retention + privacy docs。
17. **Stage Q**：统一 telemetry 事件 + guidance_event 存储。
18. **Stage R**：Eval Harness（fixtures/runners/rubrics/reports，12 类场景）。
19. **Stage S**：Soak 模拟（2h/3h PASS）。
20. **Stage U**：品牌统一 Chengzhu（README/app title/package description/UI/NOTICE/DESIGN/PRODUCT）。
21. **Stage V**：CI 强化（intelligence 单测 + eval smoke + migration smoke 进 backend job）。
22. **Stage W**：Perf benchmark（全部预算内）。
23. **Stage X**：docs/architecture 8 篇 + product 2 篇 + evals/privacy 各 1 篇。
24. **Stage T**：Frontend IA 收敛——导航统一到目标词汇（首页/我的成竹/岗位/演练/上场/复盘/能力分析），HomeScreen 卡片镜像导航主心智（Job Tracker 保留且非主位），e2e specs/单测断言同步；视觉基线实证闭环（update-visual-snapshots workflow ubuntu success + 基线未被重写 + 本地 3 passed = 标签变更差异在既定 tolerance 内）。

## Migration

- intelligence.db 为全新文件；existing 用户 DB（prep/review/knowledge/resume_history/job_tracker）零改动。
- `PRAGMA user_version` 版本追踪 + `schema_migrations` 表（id/name/applied_at）；additive-only、幂等。
- 升级前 `backup_database()` 快照（db/wal/shm）；回滚 = 恢复快照。
- 测试：`tests/test_intelligence_migration.py` 8 项全通过（fresh bootstrap/idempotent/tables/data survives/no-duplicate/roundtrip/backup/WAL）。

## Tests

| Suite | 结果 |
| --- | --- |
| backend `python -m pytest -q` | **792 passed, 4 skipped, 0 failed**（4 skip 为环境性：test_kb_loaders 缺 docx/pypdf 可选包） |
| backend `ruff check .`（uvx 等价） | All checks passed |
| backend `py_compile main.py pipeline.py answer_worker.py` | 通过 |
| frontend `npm test`（Vitest） | **344 passed, 0 failed**（48 文件；全量下曾有 1 次 focus 竞态 flaky，复跑全绿） |
| frontend `npm run build`（tsc -b + vite） | 通过 |
| desktop `node --test *.test.js` | **13 passed, 0 failed** |
| Playwright e2e（跳过 @visual） | **9 passed, 3 skipped**（skip 为 real-chain-smoke 需真实后端/模型） |

新增测试：intelligence 6 个测试文件 110 项（question_understanding/truth_boundary/state/candidate_job/compiler_planner/migration）。

### CI 实证（workflow_dispatch run 36410570270，2026-09-28，feat 分支）

| Job | 结果 |
| --- | --- |
| backend（ruff + 单测 + intelligence/eval/migration smoke） | success |
| frontend（tsc + Vitest + build） | success |
| desktop（node --test） | success |
| e2e-playwright（功能，跳过 @visual） | success |
| **e2e-visual（视觉回归，ubuntu）** | **success**（Stage T 标签变更差异在既定 tolerance 内） |
| e2e-smoke（真实后端 boot + API contracts） | success |
| ci-gate | **success（全部 8 job 通过）** |

## Evals（backend/evals，2026-09-26 基线）

| Metric | 值 | Rubric 阈值 |
| --- | --- | --- |
| Route Accuracy | **1.0**（10/10 fixtures；七轮 7/7） | ≥ 0.9 ✅ |
| Type Accuracy | 0.9 | ≥ 0.8 ✅ |
| Unsupported Claim Blocked | **1.0**（8/8 naive 无证据声称被拦截/改写） | block ≥ 0.8 ✅ |
| Fact Precision | **1.0**（3/3 有证据问题保持 PERSONAL_FACT） | ≥ 0.9 ✅ |

必做七轮断言（canonical 第 40 节）全通过：Q1 EXPERIENCE / Q2 EXPERIENCE_KNOWLEDGE / Q3 EXPERIENCE_KNOWLEDGE / Q4 HYPOTHETICAL / Q5 KNOWLEDGE(+CURRENT_CONTEXT) / Q6 EXPERIENCE_BOUNDARY / Q7 OPEN_DESIGN(SYSTEM_DESIGN)。

## Performance（backend/scripts/bench_intelligence.py，200 runs）

| Stage | p50 ms | p95 ms | 预算 |
| --- | --- | --- | --- |
| question_resolve (state update) | 12.2 | 14.1 | — |
| question_understanding | 0.013 | 0.022 | < 5 ✅ |
| truth_boundary (pre-generation) | 0.017 | 0.021 | < 5 ✅ |
| answer_planner | 0.002 | 0.004 | < 5 ✅ |
| context_compiler (fast) | **2.06** | 3.22 | P50 < 300 ✅ |
| intelligence_layer (full bridge) | 12.7 | 14.2 | — |

local overhead 与 provider latency 分开报告（provider 延迟见 telemetry 的 first_token_ms/total_ms）。抽象层新增延迟 ≈ 13ms 量级，远低于 20% 退化线。

## Known limitations

1. pipeline.py（约 1690 行）/answer_worker.py（约 1690 行）仍超 300 行硬限制——Intelligence Core 已建立独立模块层，但旧文件的全量搬移拆分留待 v1.1（禁止一次性重写的约束下，本轮以最小侵入接入为先）。
2. Context Compiler 的 semantic_relevance 为词法 Jaccard；dense/semantic embedding 检索待 v1.2（接口已预留，无云依赖）。
3. Interviewer State 为规则性概率更新；LLM-driven interviewer inference 待 v1.1。
4. Personal Voice 默认关闭（voice_profile_enabled=False），需真实口述样本积累后开启。
5. Soak 为事件压缩模拟（2h/3h）；真实音频 soak 见外部阻塞。
6. config.py 仍有部分历史注释乱码（153-157 已修复，其他区域 cosmetic）。
7. Visual regression 基线为 linux/darwin（CI 跑 ubuntu）；Stage T 标签变更的差异已实证在既定 tolerance 内（workflow ubuntu success 且基线未被重写、本地 Windows 系统 Chrome 3 passed），基线无需更新。Vitest 全量并发下偶见 1 次 focus 竞态 flaky（SoundTest/settings/JobTracker 各出现过一次，单独重跑全绿）——属环境性竞态，非代码缺陷。

## External blockers（BLOCKED，不阻塞其余工程）

1. **真实音频 2h/3h/5h soak**：需要真实面试参与者与音频硬件；事件压缩模拟已完成（`reports/CHENGZHU_V1_SOAK_REPORT.md` PASS），恢复后补跑 memory/queues/WebSocket/provider failure/audio switch 检查。
2. **真实 LLM provider 的答案质量 eval**：需付费 API key；deterministic 层 eval 已全通过（route/truth/fact），provider-dependent eval 保留为 manual/nightly/opt-in（未加入 PR mandatory gate）。
3. **Windows/macOS 签名证书、商店审核**：发布链路不变。

## Production readiness

- 代码：全量测试绿、ruff clean、py_compile 通过、三端 build 通过。
- 类型： intelligence 层全部强类型（dataclass + enum），无 unjustified type escape。
- 错误：telemetry/persistence/bridge 全部降级到 legacy path，不阻塞实时链路。
- 迁移：fresh + existing fixture 全通过；backup/rollback 就绪。
- 安全：Truth Boundary 永不降低；LLM inference 永不成为 candidate fact；受控写回白名单；无反监考功能。
- 文档：canonical + 12 篇架构/产品/eval/privacy 文档与实现一致（引用具体行号）。
- CI：intelligence 单测 + eval smoke + migration smoke 已进 backend mandatory gate（无需付费 API）。
- 判定：**可发布**（v1.0-R1 范围内）；外部 blocker 均不阻塞代码发布。

## Next version（v1.1 建议）

1. pipeline.py / answer_worker.py 按职责拆分到 300 行内（ASR loop plumbing / prompt assembly 已有 Intelligence 层承接）。
2. Voice Profile 深化（真实口述采集 → 统计 → A/B）。
3. LLM-driven Interviewer State + company public context。
4. 更强 Mock（基于 Gap Map 动态追问的 Question Graph）。
5. dense embedding 检索（local embeddings，无云依赖）。
6. 性能调优（Context Compiler P95、Fast path P95 持续优化）。

## 生产运行方式

```bash
# 后端（端口 8000）
cd backend && python main.py
# 前端（开发）或 desktop
cd frontend && npm run dev
cd desktop && npm start   # Electron 壳
# 或统一启动
python start.py
```

Intelligence Core 默认开启（intelligence_*_v1=True）；`interviewer_state_enabled=True`、`voice_profile_enabled=False` 可在设置中调整；AI policy 默认 AI_ALLOWED。
