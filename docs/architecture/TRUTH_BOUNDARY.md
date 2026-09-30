# Truth Boundary（Stage B）

> CURRENT · 对应 canonical 第 9、48 节。落点：`backend/services/intelligence/truth_boundary.py`（facade）、`backend/services/answer_grounding.py`（安全基础）、`backend/api/assist/answer_worker.py:1445-1475`（接线）。

## 1. 定位

Truth Boundary 是个人事实的统一约束层：输出空间区分 + claim policy + 生成后检查。`truth_boundary.py` 是 `services/answer_grounding.py` 的 **compatibility facade**——grounding 的确定性规则保留并作为安全基础，本模块把它升级为统一 Truth Boundary。**Grounding 永不被新功能削弱**（模块 docstring COMPATIBILITY 注释；canonical 第 9.4 节）。

## 2. 输出空间（canonical 第 9 节，`types.py:36`）

| OutputSpace | 语义 |
| --- | --- |
| `PERSONAL_FACT` | 个人事实表达，受 claim policy 约束 |
| `KNOWLEDGE_JUDGMENT` | 通用知识判断，自由表达，不强套简历 |
| `HYPOTHETICAL` | 假设/开放推理，用条件句表达 |

`classify_output_space(grounding)`（`truth_boundary.py:79`）由确定性 grounding 判定：

- grounding 不适用 → `KNOWLEDGE_JUDGMENT`
- `status == "supported"` → `PERSONAL_FACT`
- `unsupported` / `explicit_negative` / `no_profile` → `HYPOTHETICAL`
- 其余（`related_only`）→ `KNOWLEDGE_JUDGMENT`

## 3. Claim Policy 表（`truth_boundary.py:22`，canonical 第 9.3 节）

| TruthStatus | 允许的语言 |
| --- | --- |
| `VERIFIED` | 允许第一人称事实表达 |
| `SUPPORTED` | 允许谨慎第一人称；所有细节只能来自既有证据 |
| `INFERRED` | 不得升级成"我做过"；只能表达推断 |
| `UNKNOWN` | 必须设边界；先说明没有可确认的经历 |
| `CONTRADICTED` | 禁止确定性声称；必须说明与证据矛盾 |

`claim_policy_text(status)` 输出 prompt-ready 的一行；`TruthBoundary.prompt_contract()` 把 grounding 契约 + 输出空间行拼进生成前 prompt。

## 4. 与 answer_grounding.py 的关系

- `analyze_truth_boundary(question, resume_text=, interview_notes=)`：先调 `analyze_experience_grounding`（legacy 确定性规则），再把 legacy status 映射到统一 `TruthStatus`（`map_grounding_status`，`truth_boundary.py:90`）：
  - `supported → SUPPORTED`、`related_only → INFERRED`、`explicit_negative → CONTRADICTED`、`unsupported/no_profile/not_applicable → UNKNOWN`。
- `enforce_truth(answer, boundary)`：直接委托 `enforce_experience_answer`——**永不降低**既有确定性约束。
- `TruthBoundary` 是 frozen dataclass：`grounding` / `output_space` / `truth_status`，附 `public_payload()` 与 `prompt_contract()`。

## 5. 生成后检查（canonical 第 9 节；`check_generated_answer`，`truth_boundary.py:158`）

6 类 violation 检测：

| violation kind | 检测内容 |
| --- | --- |
| `internal_system_leakage` | 答案泄露内部系统信息（"简历/证据/系统/助手…没有/无法…"类表述） |
| `subject_substitution` | 疑似偷换对象（"这块我主要是/换个话题/其实我更熟悉"且 grounding 适用） |
| `unexpected_metric` | `SUPPORTED/VERIFIED` 边界下出现证据与问题文本之外的数字/百分比 |
| `unsupported_personal_claim` | 无证据第一人称经历声称（对所有非 supported 输出检查："no evidence" 绝不变成"我做过"；evidence 锚定要求 composite match——声称文本的每个 meaningful term 都被证据覆盖） |
| 证据矛盾 | `CONTRADICTED` 声明与确定性 grounding 冲突 |
| 否则保守误报 | grounding 判定 prose 可接受（如诚实否定）时，violation 清空并放行（`grounding_kept_prose`） |

violation 触发后的行为链（rewrite / downgrade / fallback）：

```text
violations 非空
    ↓ enforce_truth → 重写为确定性 bounded answer（rewrite_to_deterministic）
    ↓ 重写成功 → final_text = 重写结果，fallback_used=True，passed=False
    ↓ grounding 判 prose 可接受 → 保留原文（保守误报豁免）
    ↓ 非经历验证题 + 无证据第一人称声称 → _downgrade_to_boundary
        （"我用了X" → "可以用X"；无法替换时加"（事实边界：我没有直接做过这件事…）"前缀）
```

## 6. 实时接线（`answer_worker.py:1445-1475`）

- 严格 ground（`strict_grounding_buffer`）先生效：`enforce_experience_answer` 替换（`ANSWER_FACT_GUARD_REPLACED` 日志）。
- 再跑统一 post-check（gated by `intelligence_answer_planner_v1`）：`check_generated_answer(TruthBoundary(grounding, classify_output_space, map_grounding_status), evidence_texts=[evidence_excerpt], question_text)`；`fallback_used` 时替换 full_answer 并记 `TRUTH_BOUNDARY_REWRITE id=… violations=[…]`。
- grounding 已接受的 violation 在此**不会**被重复 flag（`answer_worker.py:1445-1448` 注释）。

## 7. Eval 指标（canonical 第 39 节；`backend/evals/rubrics/rubrics.py`）

| 指标 | 含义 | 当前基线（2026-09-25） | 阈值 |
| --- | --- | --- | --- |
| `unsupported_claim_rate` (blocked) | 朴素禁止声称被 truth boundary 拦截的比例 | **1.0** | max 0.05 |
| `fact_precision` | 有 resume 证据的问题保持 `PERSONAL_FACT` 输出空间的比例 | **1.0** | min 0.9 |

探针实现见 `backend/evals/runners/route_runner.py:130-169`（`_run_unsupported_claim_probe` / `_run_fact_precision_probe`）。

## 8. 测试覆盖（`backend/tests/test_intelligence_truth_boundary.py`，12 tests）

边界锁定（supported/experience verification）、无简历保持 hypothetical+unknown、非经历题 = knowledge_judgment、无证据声称被重写、诚实否定通过检查、证据外指标被标记重写、内部泄露检测、legacy status 映射、claim policy 文本非空/回退、输出空间分类、prompt 契约输出空间行。

## 9. 安全边界（canonical 第 48 节）

不得：把 inference 写成 verified；伪造经历/成果指标；在无证据时生成第一人称经历声称；自动修改用户证据。用户手动 verdict（PATCH claims）是唯一的状态覆盖路径。
