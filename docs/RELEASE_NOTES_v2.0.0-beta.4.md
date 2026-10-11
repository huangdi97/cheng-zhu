# 成竹 Chengzhu v2.0.0-beta.4

## 这是什么版本

v2.0.0-beta.4 是 **Personal Conversation Intelligence** 的第四个 Windows Beta 候选。

它不是继续扩大 Conversation 功能面的版本，而是把 beta.3 之后已经在 `main` 完成的 **真实 pilot 证据链收口** 带进可安装包：预测 provenance、显式本机反馈、Direct Question 可复现评测、feedback retention integrity、自动 Guidance/SILENT runtime provenance，以及更严格的 Stable Promotion 指标分母。

发布后仍必须保持：

```text
prerelease = true
latest = false
Stable Latest = v1.4.2
V2_STABLE_RELEASE = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

beta.4 证明的是“可以开始可信地做真实 Project Sync / Design Review pilot”的工程准备度，不代表真实用户价值已经验证。

---

## 相比 beta.3 的主要变化

### 1. Pilot Evidence Bridge：显式反馈而不是行为代理

Conversation Continue 新增本机显式 feedback bridge。

可记录：

- shown Guidance：useful / interruption regret / source correctness；
- RECALL：额外 recall correctness；
- SILENT：silence correctness；
- Continue：write-back accuracy；
- Session Outcome：cognitive-load delta / same-Space reuse intent。

硬边界：

```text
Pin / Used / Dismissed
!=
human quality label

SELF_USER
!=
verified external user

local feedback
!=
authorized real pilot
```

反馈保存在本机 `product.db`；没有远程 pilot telemetry uploader。

### 2. schema v10：冻结 AI_EXTRACTED 原始预测

AI_EXTRACTED Conversation Item 在创建时冻结 immutable `prediction_json`。

Continue 中后续的：

- CONFIRM；
- EDIT；
- REJECT；
- DONE；
- SUPERSEDE；

只改变当前 truth row，不会回写原始 prediction。

pre-v10 已经经过人工 review、但没有可恢复原始 prediction 的历史 row 会标记：

```text
prediction_unavailable = true
```

不会用 post-review truth 冒充模型预测。

### 3. Reviewed Draft 与真实外部执行路径继续保持分离

Preflight / Session Pack / Live Session Pulse 会分别显示：

```text
Reviewed Draft
= LOCAL_REVIEWED_DRAFT / DISABLED

External Execution
= EXPLICIT_SECOND_STEP_PROVIDER / DISABLED
```

本地 `APPROVED` Draft 仍不等于 provider side effect；真实外部动作需要 exact connection / target / capability re-check 与第二次显式 Execute。

### 4. schema v11：Direct Question prediction provenance

每条 eligible final transcript 在 capture time 冻结：

```text
analysis.direct_question = {
  eligible,
  predicted,
  detector_version,
  channel,
  ai_assistance
}
```

当前 detector version：

```text
heuristic-v1
```

Direct Question Precision / Recall 因此可以同时拥有 predicted=true 与 predicted=false 的真实历史分母。

以下行为被禁止：

- 用新版 detector 重跑旧 transcript 来制造历史 prediction；
- 根据是否出现 ANSWER_CUE 倒推所有负样本；
- 把 reviewer actual 回填成 predicted。

AI_LIMITED / AI_FORBIDDEN / SELF_MIC 等当时未运行该自动能力的 row 明确为 evaluation-ineligible，而不是“prediction 缺失”。

### 5. schema v12：Auto-runtime Evidence Contract

beta.4 为 automatic transcript Guidance 增加 immutable `origin_json`：

```text
final PRIMARY_AUDIO transcript
→ exact transcript_segment_id
→ automatic decision
   ├─ SHOWN
   └─ SILENT / SUPPRESSED
→ origin {
     kind = TRANSCRIPT_AUTO
     transcript_segment_id
     channel
     ai_assistance
     assistance_mode
     decision_class
   }
```

这解决了 beta.3 后评测审计发现的关键错位：

- 真实自动路径过去会在很多“不提示”场景直接 return None；
- 高级手工 Guidance Lab 反而会持久化 SUPPRESSED event；
- 若不区分来源，Useful Silence 等指标可能由手工验证事件代表真实 runtime。

现在：

- Stable live-guidance 指标只接受 `TRANSCRIPT_AUTO`；
- pre-v12 Guidance 不按 reason 字符串事后回填 origin；
- advanced/manual Guidance Lab 保留工程验证价值，但不进入 Stable live metric 分母。

### 6. Useful Silence 只统计真正的 Arbiter 决策

自动 SILENT provenance 区分：

- `ARBITER`；
- `MODE_FORCED`；
- `PROFILE_FORCED`；
- `PROVENANCE_FORCED`。

只有 `ARBITER` 进入 Useful Silence Rate。

Quiet mode、Profile 禁止某 Guidance lane、来源 visibility 阻断等仍然是重要的 policy-compliance 证据，但不会成为“白送的正确静默样本”。

### 7. Decision / Commitment / Task 指标分母修正

Stable 的 `decision_commitment_state_precision` 不再把所有 truth item 混进分母。

目标预测类固定为：

```text
Decision
Commitment
Task
```

Task 在当前产品 truth model 中与 Commitment 共用 COMMITTED / owner 约束。

OpenQuestion / Risk / Proposal / Deadline 等预测类型不能通过大量“容易正确”的样本稀释这一 precision 指标；如果模型把 Proposal 错预测成 Decision，则仍然进入分母并计错。

### 8. Stable Promotion Policy v3

Stable Promotion Policy 从：

```text
v2.0-R1-stable-promotion-2
```

升级为：

```text
v2.0-R1-stable-promotion-3
```

**数值阈值没有降低，也没有修改。**

v3 在任何真实 pilot 结果出现前冻结：

- allowed label sources；
- live-guidance runtime provenance；
- Useful Silence decision class；
- Decision / Commitment / Task 指标人口。

这是 pre-pilot evidence-design correction，不是为了让失败数据变 PASS 的 post-hoc 调参。

### 9. Feedback retention integrity

Guidance/SILENCE feedback 与其被标注目标共享可解释生命周期：

```text
Guidance expires under retention
→ dependent GUIDANCE/SILENCE feedback
→ same confirmed cleanup
```

旧版本可能留下的 orphan feedback 会被显式检测：

```text
orphan_guidance_feedback_rows
human_feedback_integrity = NEEDS_RETENTION_CLEANUP
```

`retention_preview` 会在用户确认前分别展示：

- dependent human feedback；
- legacy orphan human feedback。

Space UI 与确认弹窗也显示这些删除数量。

Continue / Session Outcome 会话级反馈不会因为一条 Guidance 到期而被连带删除。

### 10. Release verification workflow hardening

beta.4 继承 beta.3 已完成的 exact-SHA / draft download-back / clean-install / SHA256 / reinstall / smoke / tag-source provenance gate，并包含 beta.3 发布后修复的 post-publish evidence-enrichment PowerShell 兼容问题与回归保护。

发布工作流仍要求：

```text
main green SHA
==
release checkout SHA
==
installer / portable source SHA
==
public tag SHA
```

---

## 仍然明确不宣称

beta.4 不代表：

- `V2_STABLE_RELEASE = TRUE`；
- `PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = TRUE`；
- `REAL_USER_VALIDATED = TRUE`；
- `PMF_PROVEN = TRUE`；
- Google Calendar / Drive / Gmail / Microsoft To Do real-account replay 已完成；
- Google OAuth sensitive-scope publication / verification 已完成；
- Windows code signing 已完成；
- macOS signing / notarization 已完成。

外部账号当前事实仍是：

```text
GitHub real throwaway replay = PASS
Local Markdown = local runtime, no cloud account required
Google Calendar = BLOCKED_ACCOUNT
Google Drive = BLOCKED_ACCOUNT
Gmail = BLOCKED_ACCOUNT + external OAuth publication gate
Microsoft To Do = BLOCKED_ACCOUNT
```

---

## beta.4 后的正确下一步

不要继续把新的 Beta 功能堆叠当成验证。

优先做真实、授权的：

1. Project Sync pilot；
2. Design Review pilot；
3. independent human review；
4. Opportunity Precision；
5. Interruption Regret；
6. Recall Precision；
7. Source Attribution Accuracy；
8. Useful Silence（仅 ARBITER）；
9. Direct Question Precision / Recall；
10. Decision / Commitment / Task State Precision；
11. Continue Write-back Accuracy；
12. cognitive-load delta；
13. same-Space reuse intent。

只有满足 frozen Stable Promotion Policy v3，并通过独立 release/security/public-truth review 后，才讨论 stable v2。

---

## Release channel

```text
Stable Latest = v1.4.2
This candidate = v2.0.0-beta.4 prerelease
Stable v2 = NOT CLAIMED
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

## License

MIT。第三方组件保留各自许可证，详见 `THIRD_PARTY_NOTICES.md`。
