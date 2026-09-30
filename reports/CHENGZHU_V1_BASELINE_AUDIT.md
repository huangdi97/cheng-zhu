# 成竹 Chengzhu v1.0 Baseline Audit

**日期**：2026-09-25
**分支**：`feat/chengzhu-v1-interview-intelligence`（自 `main` 新建）
**基线 HEAD**：`6dfa47520246a35350cfb5090a5abbc22a84739d`（`Initial public release: Cheng Zhu`）
**origin/main**：`6dfa475`（与本仓库一致，无远端新提交）

---

## 1. Repo tree（关键目录）

```text
backend/            约 185 个文件
  api/assist/       pipeline.py(2415 行) answer_worker.py(1571 行) scheduler.py asr_state.py routes.py
  api/              assist assist sessions realtime resume review kb prep copilot jobs common analytics
  services/         answer_grounding answer_depth copilot_strategy question_turn_parser memory
                    resume skill_builder prep_service practice_service review_analysis
                    review_async_analysis review_integration live_listen audio
  services/kb/      retriever store indexer chunker loaders(pdf/docx/doc/txt/md) ws types
  services/stt/     whisper_stream doubao_stream engines factory _cuda text_utils
  services/llm/     prompts streaming
  services/capture/ screen_capture _screen_capture_worker
  services/storage/ paths prep_space review knowledge resume_history job_tracker
  core/             config env session logger auth background resource_lanes
  tests/            90+ pytest 文件（含 stress/replay 脚本测试）
frontend/           React 18 + TS + Vite + Zustand + Tailwind；e2e Playwright + 视觉基线(linux/darwin)
desktop/            Electron main.js preload shortcuts windowOptions multiScreenBatch + node:test
.github/workflows/  ci.yml update-visual-snapshots.yml
docs/               DESIGN.md PRODUCT.md README.md CHANGELOG.md + stt/screenshots 子目录
```

## 2. 当前架构（审计结论）

- **实时链路**：Audio → VAD → InterviewerSegment → ASR worker（transcribe_with_fallback）→ AssistAsrStateMachine merge → PendingASRGroup → parse_question_turn → submit_answer_task（question cleanup + LLM correction）→ scheduler claim_next_dispatch → _process_question_parallel → answer_worker.process_question_parallel（上下文组装 852-1140）→ chat_stream_single_model → WS answer_chunk → ordered commit。
- **DI seam**：`AnswerWorkerDeps`（answer_worker.py:39-55）仅在 pipeline.py:2349-2396 构造——新 Intelligence Core 的接入点。
- **Question understanding 分散在三处**：parse_question_turn（asr_state.py:76-150）、submit-time cleanup/LLM correction（pipeline.py:694-762）、LLM question judge（pipeline.py:887-960）。
- **Context 注入**：answer_worker.py:852-1140 一个 290 行连续块（grounding→history→candidate context→bridges→structured prompt→depth→build_system_prompt）——最高价值提取目标。
- **存储**：5 个 SQLite DB（prep/review/knowledge/resume_history/job_tracker），全部 WAL，**均无 schema versioning**；intelligence.db 为新文件。
- **Session**：纯内存（core/session.py），不持久化；经 review_integration 落 review.db。
- **配置**：AppConfig pydantic 模型（约 80 个扁平字段）→ backend/config.json；resume_text 不持久化。

## 3. 当前功能（已实现，必须保留）

双通道采集、VAD、流式 ASR、partial/final、问题合并分组 interrupt、多模型回答调度/健康/fallback、简历/JD/Notes/Rolling Memo 注入、回答深度与 grounding、简历历史、PrepSpace、Skill Builder、Mock/Practice、KB RAG（FTS5 + CJK bigram + deadline watchdog）、OCR/Vision、截图解题、多会话、复盘、候选人口述采集、ASR 纠错、知识点沉淀、Job Tracker/Offer Compare、中英回答、TTS、快捷键、Overlay、UI 主题/可访问性/视觉回归。

## 4. 当前测试

- `python -m pytest -q`：**682 passed, 4 skipped, 0 failed**（59.7s）。4 个 skip 为环境性（test_kb_loaders.py 缺 docx/pypdf/reportlab 可选包，pytest.importorskip 门控）。
- `python -m ruff check .`：本机无 ruff（No module named ruff），以 `uvx ruff check .` 等价执行 → **All checks passed**。
- `python -m py_compile main.py api/assist/pipeline.py api/assist/answer_worker.py`：通过。
- 前端/desktop/Playwright：CI 已覆盖（ci.yml）；本机按需运行。

## 5. 当前已知风险

1. pipeline.py（2415 行）/answer_worker.py（1571 行）远超 300 行硬限制——Intelligence Core 拆分同时是瘦身机会；
2. 无 schema versioning/migration 机制（review.py 只有 ad-hoc _ensure_column，静默失败）；
3. Resume 解析只产出纯文本，无结构化表示；
4. 简历被当成答案边界：KB 检索失败时答案僵化（v1.0 的开放世界路由要解决）；
5. 无统一 telemetry 存储（只有结构化日志）；
6. config.py:153-157/200-201 注释乱码（cosmetic）。

## 6. 与 v1.0 目标差距（→ 落地方案）

| 差距 | 落地 |
| --- | --- |
| 无 Candidate Representation | backend/services/intelligence/candidate_representation.py + storage/intelligence.py（Stage A） |
| 无统一 Truth Boundary | backend/services/intelligence/truth_boundary.py facade（Stage B，复用 answer_grounding.py 规则） |
| 无 Job Representation | backend/services/intelligence/job_representation.py（Stage C） |
| 题型只有 8 类 | question_understanding.py 扩展到 21 类 + followup_resolver.py（Stage D） |
| 无 versioned Interview State | intelligence/interview_state.py（Stage E，增量事件更新） |
| 无 Interviewer State | intelligence/interviewer_state.py（Stage F，概率性） |
| 上下文注入分散且无预算 | intelligence/context_compiler.py + retrieval.py（Stage G，Provider 接口 + 评分 + Fast/Deep budget） |
| 无结构化 Answer Plan | intelligence/answer_planner.py（Stage H，吸收 answer_depth + copilot_strategy） |
| 简历外问题僵化 | intelligence/world_reasoning.py（Stage I，No evidence != No answer） |
| 无 Fast/Deep 双路径 | pipeline/answer_worker 双路径逻辑（Stage J） |
| Live UX 无 cue-first | frontend GuidanceViewModel（Stage K） |
| Review 无受控回写 | memory_policy.py 白名单（Stage L） |
| 无 eval harness | backend/evals/（Stage R） |
| 无 soak 报告 | reports/CHENGZHU_V1_SOAK_REPORT.md（Stage S） |
