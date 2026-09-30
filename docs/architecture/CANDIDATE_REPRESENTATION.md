# Candidate Representation（Stage A）

> CURRENT · 对应 canonical 第 8、9.1、32 节。落点：`backend/services/intelligence/candidate_representation.py`、`backend/services/storage/intelligence.py`、`backend/api/intelligence/router.py`。

## 1. 定位

Candidate Representation 是"系统当前如何表示这个候选人"，不是训练新 LLM。`candidate_representation.py` 是**确定性** resume→structure builder：无 LLM、无网络、无延迟， intelligence core 在任何模型运行前总有一个 question-node 基线。

**SAFETY 约束**（模块 docstring）：内容是 question nodes / 待补信息，绝不生成个人事实；`truth_status` 只来自源材料本身，不超出原文行。

## 2. Schema（canonical 第 8.1 / 32 节）

`CandidateRepresentation`（`types.py:180`）核心字段：`candidate_id` / `profile_text` / `experiences` / `projects` / `claims` / `skills` / `stories` / `voice_profile` / `metrics` / `education` / `schema_version`。

| 实体 | storage 表 | 说明 |
| --- | --- | --- |
| claim | `claim` | 个人事实声称，含 `truth_status` / `confidence` / `metadata_json` |
| evidence | `evidence` | 每条 provenance（resume / user_confirmed 等 9 来源） |
| claim_evidence | `claim_evidence` | claim↔evidence 关联（edge table，FOREIGN_KEYS=ON） |
| experience | `experience` | 工作经历条目（期间/职位/内容） |
| project | `project` | 项目条目 |
| skill | `skill` | 技能 token |
| story | `story` | Story Bank 条目（BEHAVIORAL 检索用） |
| metrics | （存于 claim metadata / 行内提取） | **带单位**：`3万QPS` / `100倍` / `P50 300ms` |
| education | （education 实体） | 本科/硕士/博士等学位判定 |

每张表有 `schema_version` / `created_at` / `updated_at`（canonical 第 32 节要求）。

## 3. Truth Status（canonical 第 9.1 节，`types.py:25`）

| 状态 | 语义 |
| --- | --- |
| `VERIFIED` | 有直接证据确认；允许第一人称事实表达 |
| `SUPPORTED` | 由既有证据支撑；所有细节只能来自证据 |
| `INFERRED` | 推断（如"熟悉/了解/掌握"自评）；不得升级成"我做过" |
| `UNKNOWN` | 无可确认信息；必须设边界 |
| `CONTRADICTED` | 与证据矛盾；不得生成确定性声称 |

模型可以把 `UNKNOWN → INFERRED` 式推理升级，但**绝不**能在无证据时制造 `VERIFIED`。用户手动 verdict 覆盖模型（`PATCH /api/intelligence/claims/{claim_id}`）。

## 4. Resume Bootstrap 流程

```text
resume_text (+ interview_notes)
    ↓ build_candidate_representation / rebuild_and_persist   [candidate_representation.py:259,265]
    ↓ 确定性解析：section 检测（教育/工作/项目/技能）→ 每行一个 evidence
    ↓   + 可选 claim（action verb → SUPPORTED；熟悉/了解 → INFERRED）
    ↓   + metrics 带单位提取 + 去重（normalize line → stable sha1 hash，重跑 upsert 不重复）
    ↓ save_candidate_profile / save_claims / save_evidence_batch   [storage/intelligence.py:86,114]
    ↓ intelligence.db（新库，不触碰现有 5 个用户库）
    ↓ 成为 active candidate（active_candidate_id() = 最近更新的 profile）
```

关键点：

- 空简历返回空表示（无 claim、无异常），不崩溃（`candidate_representation.py:234`）。
- `interview_notes` 绕过 resume 分区，作为 `USER_CONFIRMED` 来源材料。
- 去重 INVARIANT：normalized line → (evidence, claim or None)，重复行永不多记（`:100` 注释）。
- 持久化失败只记 warning，不打断内存中的 build（`:281`）。
- `profile_text` 入库为 4000 字截断（`_PROFILE_TEXT_LIMIT`），resume 正文不进其他库、不进 config.json。
- `rebuild_and_persist` 当前由 `POST /api/intelligence/candidate/rebuild` 触发；resume 上传链路尚未自动调用它。

## 5. Experience Expansion（canonical 第 8.2 节）

`extract_experience_expansion(experience_text)`（`candidate_representation.py:289`）把简历一条（如"构建基于 RAG + Agent 的智能问答系统"）展开成**可追问维度**：

- 基础 10 问：为什么做/背景目标/架构设计/数据规模流转/效果评估指标/延迟优化/成本量级/技术取舍/失败场景/流量涨 10 倍/如果重做。
- keyword-aware 追加：含"缓存" → 一致性/失效策略；含"分布式" → 数据一致性/容灾演练；含"模型/llm/rag" → 模型效果评估/数据准备清洗。
- 上限 `_EXPANSION_LIMIT = 12`，`dict.fromkeys` 去重。

**边界**：自动生成的是"问题节点"和"待补信息"，不是自动生成个人事实（canonical 第 8.2 节原文）。

## 6. API 端点（`api/intelligence/router.py`，前缀 `/api/intelligence`）

| 端点 | 方法 | 行为 |
| --- | --- | --- |
| `/candidate` | GET | active candidate：profile 预览（400 字截断）+ claims + evidence + `claim_summary` |
| `/candidate/rebuild` | POST | 确定性 rebuild（resume_text ≤ 200k 字符 + interview_notes），持久化并成为 active |
| `/claims` | GET | active candidate 的 claims，strongest first（limit ≤ 2000） |
| `/claims/{claim_id}` | PATCH | 手动 truth_status 修正（5 值之外返回 422） |
| `/evidence` | GET | evidence 行，newest first |

PRIVACY：`/candidate` 只返回 profile 预览，完整存储的 resume 正文不经此 API 离开后端（`router.py:9,38-40,129-130`）。

## 7. 测试覆盖清单（`backend/tests/test_intelligence_candidate_job.py`，12 tests）

- `test_mixed_resume_builds_claims_with_supported_and_inferred_statuses` — action verb/self-assessment 两种状态
- `test_duplicate_resume_line_merges_and_keeps_distinct_evidence_links` — 去重
- `test_resume_metrics_are_extracted_with_units` — 指标带单位
- `test_resume_sections_are_parsed_into_entities` — 分段实体
- `test_empty_resume_and_empty_jd_yield_empty_representations` — 空输入边界
- `test_rebuild_and_persist_writes_claims_without_duplicating_on_rerun` — 重跑幂等
- `test_experience_expansion_returns_bounded_keyword_aware_questions` — 追问维度有界
- `test_jd_structures_title_level_and_requirements` — JD 结构化
- `test_alignment_classifies_requirement_by_available_evidence` — 可解释 alignment
- `test_alignment_with_claims_carries_evidence_ids_and_no_percentages` — 无假百分比
- `test_claims_for_subject_requires_every_qualifier` — composite-subject 规则
- `test_strongest_claim_excludes_contradicted_and_summary_counts` — CONTRADICTED 排除
- 另有 `test_intelligence_migration.py`（8 tests）：fresh install / 幂等 migration / 核心表存在 / 旧数据存活 / claim 状态回写 / backup 快照 / WAL 模式。
