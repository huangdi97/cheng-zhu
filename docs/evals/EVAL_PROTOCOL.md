# Eval Protocol（Stage R）

> CURRENT · 对应 canonical 第 39、40 节。落点：`backend/evals/`（fixtures / runners / rubrics / reports）。

## 1. 定位

eval harness 用固定 fixtures 确定性评测 Intelligence Core 的规则层（question understanding、planner routing、truth boundary）。**无 LLM 调用**：provider 依赖的答案质量另行评测（manual / nightly，canonical 第 39 节）。如果无法 replay，就无法系统性优化"为什么这题不好用"。

## 2. 目录结构

```text
backend/evals/
├── __init__.py
├── fixtures/
│   ├── __init__.py
│   └── interview_fixtures.py      # 七轮必测 + 分类 fixtures（纯数据）
├── runners/
│   ├── __init__.py
│   └── route_runner.py            # run_route_eval / run_seven_turn / write_report / 探针
├── rubrics/
│   ├── __init__.py
│   └── rubrics.py                 # 阈值表（纯数据）
└── reports/
    └── route_eval_v1_2026-09-25.md  # 当前基线报告
```

## 3. Fixture 结构（canonical 第 39 节）

每个 fixture（`_entry`，`interview_fixtures.py:26`）：

```text
id · category · question · resume_text · dialogue_history
· expected_question_type · expected_route · forbidden_claims · required_structure_hint
```

`SEVEN_TURN_RESUME` 为共享候选人简历（"构建 RAG + Agent 系统，使用 Redis 保存部分 session state。负责核心检索链路，QPS 3万。"）。

## 4. Fixture 清单

**七轮必测**（canonical 第 40 节，`SEVEN_TURN_QUESTIONS`，7 题）：

| id | 问题 | expected_route | category |
| --- | --- | --- | --- |
| Q1 | 介绍一下你的项目。 | EXPERIENCE | resume_factual |
| Q2 | 为什么选 RAG？ | EXPERIENCE_KNOWLEDGE | resume_factual |
| Q3 | 为什么不用 fine-tuning？ | EXPERIENCE_KNOWLEDGE | follow_up |
| Q4 | 如果数据量扩大 100 倍呢？ | HYPOTHETICAL | hypothetical |
| Q5 | 那 Redis 会有什么问题？ | KNOWLEDGE | resume_outside_knowledge |
| Q6 | 你实际用过 Redis Cluster 吗？ | EXPERIENCE_BOUNDARY | boundary |
| Q7 | 没用过的话，你会怎么迁？ | OPEN_DESIGN | resume_outside_knowledge |

Q6 附 `SEVEN_TURN_FORBIDDEN`（"我们用了 Redis Cluster"等 4 条禁止声称）。

**分类 fixtures**（`ALL_FIXTURES`，10 题）：resume-outside-transformer、system-design-short-video、coding-lru、behavioral-cross-team、contradiction-redis-cluster（带 2 轮对话历史 + 禁止声称）、hypothetical-traffic-100x、company-knowledge、mixed-language-rag（中英混合）、topic-reset-os（带 3 轮对话历史）、long-session-accumulation（带 8 轮对话历史）。

**覆盖类别并集**（13 类）：resume_factual、follow_up、hypothetical、resume_outside_knowledge、boundary、system_design、coding、behavioral、contradiction、company、mixed_language、topic_reset、long_session。canonical 第 39 节另列的 ambiguous follow-up、中/英单语、project deep dive 独立 fixture 为待补充项。

## 5. 核心指标定义（9 项）

| 指标 | 定义 | 来源 |
| --- | --- | --- |
| `route_accuracy` | plan.mode 与 expected_route 匹配比例（容错别名匹配，`_route_matches`） | `route_runner.py:106` |
| `type_accuracy` | `understanding.question_type` 与 expected_question_type 匹配比例 | `route_runner.py:107` |
| `per_category` | 每个 category 的 matched/total | `route_runner.py:108` |
| `unsupported_claim_rate` (blocked) | 朴素禁止声称被 truth boundary 拦截的比例（`fallback_used or not passed or final_text != claim`） | `route_runner.py:130`（`_run_unsupported_claim_probe`） |
| `unsupported_probe_total` | 禁止声称探针总数（ALL_FIXTURES + SEVEN_TURN_FORBIDDEN） | 同上 |
| `fact_precision` | 有 resume 证据的问题保持 `PERSONAL_FACT` 输出空间的比例 | `route_runner.py:155`（`_run_fact_precision_probe`） |
| `context_precision` | 预算内选中的上下文与问题相关比例 | `rubrics.py` CONTEXT_RUBRIC（runner 待实现） |
| `context_recall` / `topic_leakage` | 上下文覆盖度 / 旧主题污染率 | 同上 |
| `ttfug` / `total_latency` | 首条 useful guidance 延迟 / 总延迟 | `telemetry.py`（`first_useful_guidance.latency_ms`） |

## 6. Rubric 阈值表（`rubrics.py`）

| Rubric | metrics | 阈值 |
| --- | --- | --- |
| `route_eval` | route_accuracy, type_accuracy | `route_accuracy_min ≥ 0.9`，`type_accuracy_min ≥ 0.8` |
| `truth_boundary` | unsupported_claim_rate, fact_precision | `unsupported_claim_rate_max ≤ 0.05`，`fact_precision_min ≥ 0.9` |
| `context_compiler` | context_precision, context_recall, topic_leakage | `context_precision_min ≥ 0.8`，`topic_leakage_max ≤ 0.1` |

## 7. 运行方式

runner 未注册 CLI 入口，从 backend 目录以模块方式运行：

```bash
cd backend

# 全量分类 fixtures + 探针
python -c "from evals.runners.route_runner import run_route_eval, write_report; write_report(run_route_eval(), 'evals/reports/route_eval_v1.md')"

# 仅七轮必测（canonical 第 40 节）
python -c "from evals.runners.route_runner import run_seven_turn; print(run_seven_turn()['route_accuracy'])"
```

`write_report` 生成 markdown 报告（指标表 / per category / per-case PASS-FAIL）到 `backend/evals/reports/`；fixtures 重建 dialogue state（`reset_state` + 逐题 `apply_event("question_received")`）保证可重复。

## 8. 当前基线结果（`reports/route_eval_v1_2026-09-25.md`，2026-09-25）

| Metric | Value |
| --- | --- |
| route_accuracy | **1.0** |
| type_accuracy | 0.9 |
| unsupported_claim_rate (blocked) | **1.0** |
| fact_precision | **1.0** |
| total cases | 10 |

10 个分类 fixture 全部 PASS（resume_outside_knowledge / system_design / coding / behavioral / contradiction / hypothetical / company / mixed_language / topic_reset / long_session 各 1/1）。route_eval 与 truth_boundary 均超阈值；type_accuracy 达阈值。

## 9. 测试覆盖（pytest 侧）

- `test_intelligence_question_understanding.py`（14 tests）：fixture 分类参数化 / 空输入 META / bare followup 消解 / topic transition / open-world 边界 / depth 映射。
- `test_intelligence_compiler_planner.py`（16 tests）：路由 / 边界升级 / open-world / interviewer 衰减 / voice / memory policy。
- `test_intelligence_truth_boundary.py`（12 tests）：边界锁定 / violation / 重写 / 降级。
