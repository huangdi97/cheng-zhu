# Prepare / Mock / Review（Stage L）

> CURRENT · 对应 canonical 第 25、26、30、31 节。落点：`backend/services/prep_service.py`、`practice_service.py`、`backend/services/intelligence/job_representation.py`、`review_writeback.py`、`backend/api/prep/`、`backend/api/review/router.py`。

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

**Gap Map**：`gaps`（LLM 洞察）+ alignment `GAP/KNOWLEDGE_MATCH` 状态（确定性）共同构成；缺口是 Mock 动态追问的输入。

## 3. Mock：基于 gap 动态追问

`backend/services/practice_service.py`：

- `start_session(space_id, rounds=5)`：从 PrepSpace 的题目集开一场模拟（`_ensure_questions` 保证题目存在）。
- `_pick_next`（`:79`）选题顺序：
  1. `pending_followups` 优先——基于你上一题回答的**动态追问**（`type: follow_up`）；
  2. 其余按薄弱点排序（`_order_by_weak_points`，`_weak_keywords(profile)` 来自知识薄弱点沉淀）。
- `_feedback_payload(turn)`（`:139`）：每轮反馈带 `follow_up_questions`（来自 Experience Expansion 追问维度，非假事实）。
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
