# Prepare / Mock / Review（Stage L）

> CURRENT · 对应 canonical 第 25、26、30、31 节。落点：`backend/services/prep_service.py`、`practice_service.py`、`backend/services/intelligence/job_representation.py`、`job_workspace.py`、`review_writeback.py`、`backend/api/prep/`、`backend/api/review/router.py`。

## 1. 定位

准备、模拟与复盘纳入同一条学习闭环。围绕 **Job Workspace** 组织，不把"题库"做成产品中心（canonical 第 25 节）。

## 2. Prepare：Job Workspace

一场目标岗位包括（canonical 第 25 节）：JD / 公司 / Candidate × Job Alignment / 简历攻击面 / Gap Map / Question Graph / Story Bank / Quick Mock / Deep Mock。

当前实现：

| 能力 | 实现 | 落点 |
| --- | --- | --- |
| JD 结构化 | `build_job_representation(jd_text, company, title, role)` → company/title/level/requirements（must-have / nice-to-have / technology / competency） | `intelligence/job_representation.py` |
| Candidate × Job Alignment | `compute_alignment(job, resume_text, claim_texts, claim_ids)` → 每条 requirement 一个可解释状态，claim 关联带 evidence_ids | 同上 + `api/intelligence/router.py:228-245` |
| Alignment 状态 | `STRONG_MATCH / PARTIAL_MATCH / KNOWLEDGE_MATCH / GAP / UNKNOWN`——**不出"93% match"**（`AlignmentStatus` docstring） | `intelligence/types.py:57` |
| 岗位洞察 | `generate_insight(role, company, jd_text, resume_text)` → focus_points / strengths / gaps（各 3-6 条，每条 20 字以内） | `services/prep_service.py:96` |
| 技能卡 | `generate_skill_cards(role, jd_text, resume_text)`——Candidate enrichment + Gap discovery（canonical 第 33.7 节，不再是"技能卡即边界"） | `services/prep_service.py:150` |
| 启动包 | `build_launch_pack(space)` 聚合 JD/洞察/技能卡/问题 | `services/prep_service.py:175` |
| 题目生成 | `generate_questions(role, jd_text, resume_text)` → Question Graph 初始节点 | `services/prep_service.py:284` |

### Job Workspace（`POST /api/intelligence/workspace`，确定性、无 LLM）

`intelligence/job_workspace.py` 在 JD 结构化 + Alignment 之上组合四块，前端 `JobWorkspacePanel` 展示在准备空间详情页：

| 区块 | 来源与规则 |
| --- | --- |
| Gap Map | alignment 的 `GAP`（must-have → 优先）/ `KNOWLEDGE_MATCH`（可用知识回答，但无证据不能说做过）/ `PARTIAL_MATCH`（补充）+ 复盘写回的 `knowledge_weakness`（≥2 次确认 → 优先）与 `repeated_topic`；按主题去重，无百分比 |
| 简历攻击面 | 仅 `VERIFIED/SUPPORTED` 的 fact claim；与岗位对齐、带指标的经历排前，附风险提示与追问维度（`extract_experience_expansion`） |
| Question Graph | 追问**树**（`parent_id`）：经历深挖链 + 每个 Gap 的「知识 → 事实边界 → 开放设计」链 |
| Stories | 已存真实故事 + 缺失胜任力的找故事提示（只指向候选人自己的材料，**从不生成事件**） |

`POST /api/intelligence/job/rebuild` 契约不变（不含 `workspace`）。

## 3. Mock：基于 gap 动态追问

`backend/services/practice_service.py`：

- `start_session(space_id, rounds=5)`：从 PrepSpace 的题目集开一场模拟（`_ensure_questions` 保证题目存在）。
- Gap 焦点（`_gap_focus` → `job_workspace.mock_gap_focus`）：用**本准备空间自己的 JD** × 候选人证据 + 复盘写回弱项算 Gap（不读全局"最近岗位"、不落库）；Intelligence 层失败时降级为普通练习。响应带 `gap_focus`，前端在"本场优先补弱项"中展示。
- 题池顺序：先按薄弱点排序（`_order_by_weak_points`，关键词 = 复盘画像弱项 ∪ Gap 主题），再由 `_merge_gap_questions` 在第一题热身后穿插 Gap 题（`type: gap`，去重）。
- `_pick_next` 选题：`pending_followups` 优先——基于你上一题回答的**动态追问**（`type: follow_up`）；其余按上述题池顺序。
- `_feedback_payload(turn)`：每轮反馈带 `follow_up_questions`（来自逐题分析 `review_analysis.analyze_turn`）。
- `_build_report(session)`（`:166`）：整场报告（`_avg_score` 汇总）。
- 无真实故事的 BEHAVIORAL 题：不编事件，提供找故事的方向（canonical 第 26 节；planner BEHAVIORAL 模式同样约束）。

Mock 与 Live 共享同一 Intelligence core：题型判定 / claim 边界 / 追问维度一致（canonical 第 26 节）。

## 4. Review 闭环

- **真实问答录制**：面试复盘录制真实问答 + ASR 纠错（`services/review_analysis.py` / `review_async_analysis.py`）。
- **Question Tree / coverage**：整场复盘总结逐题分析；Session Memory 的 topic / claims / open threads 支撑覆盖统计（canonical 第 30 节 Post-interview Debrief）。
- **导出**：`GET /api/review/sessions/{session_id}/export?format=md`（`api/review/router.py:490`）。
- **受控写回**（canonical 第 31 节 Cross-session Learning）：复盘完成后 `write_back_after_review(session_id, summary_result, analyzed_turns)`（`intelligence/review_writeback.py:28`）把 learning 结果写回长期记忆——只有白名单 kind 通过。

闭环：

```text
Prepare（JD → Alignment/Gap Map）
    ↓ Mock（gap 驱动动态追问 → 反馈 → 薄弱点暴露）
    ↓ Live（真实面试，Intelligence core 同一套边界）
    ↓ Review（Question Tree / coverage / 整场总结）
    ↓ 写回白名单（knowledge_weakness / repeated_topic / communication_profile）
    ↓ 下一次 Prepare 的 Gap Map 与 Mock 追问更准
```

## 5. 写回白名单（详见 MEMORY.md 第 3 节）

| kind | 自动管道 | 需用户确认 |
| --- | --- | --- |
| `knowledge_weakness` | ✅（cap 8 条） | — |
| `repeated_topic` | ✅ | — |
| `communication_profile` | ✅ | — |
| `user_confirmed_fact` | ❌ 无自动路径 | ✅ 显式确认（PATCH claims） |

LLM 的 interviewer inference（possible_focus / possible_concerns / planner hints）**绝不**进入写回路径（`memory_policy.py` SAFETY 注释）。

## 6. 拒绝的写回路径

- Review / Mock 分析产出的其他结论（LLM 总结文本）不自动落 `memory_item`；
- 用户确认的新事实走 `PATCH /api/intelligence/claims/{claim_id}`（手动 truth_status 修正），不由自动管道代表用户设置；
- 写回失败（kind 不在白名单 / 未确认）记 warning 并拒绝，永不 raise、不静默丢失（denied 有日志可追溯）。

## 7. 与 Intelligence core 的关系

- Prepare 的 Alignment 使用 `compute_alignment`（Job Representation，Stage C）；
- Mock 的追问维度使用 `extract_experience_expansion`（Candidate Representation，Stage A）；
- Mock 的题型/边界与 Live 共用 Question Understanding / Truth Boundary（Stage D/B）；
- Review 的写回经 `memory_policy`（Stage L）白名单守卫。
