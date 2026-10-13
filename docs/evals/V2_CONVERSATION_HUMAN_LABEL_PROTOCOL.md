# Chengzhu v2 Conversation Human-label Evaluation Protocol
## 2026-10-08

> 适用范围：Project Sync / Design Review 首批 dogfood 与真实用户验证。本协议不用于 synthetic CI gate，也不能单独证明 PMF。

## 1. 为什么必须独立做人类标注

以下指标不能由点击率或 synthetic replay 代替：Recall Precision、Source Attribution Accuracy、Direct Question Detection、Decision / Commitment State Precision、Opportunity Precision、Interruption Regret、Useful Silence Rate、Continue Write-back Accuracy、real cross-session value、cognitive load。

禁止把 USED/PINNED 自动等于 useful，DISMISSED 自动等于 wrong，suppressed 自动等于 useful silence，或 synthetic PASS 自动等于 real-user value。

## 2. JSONL 规则

每行一个 JSON object。kind 必须是 guidance、silence、direct_question、truth_item、continue、session_outcome 之一；reviewer 与 session_id 必填。可选共同字段：space_id、profile、event_id、timestamp、notes。

为了进入 Stable Promotion Gate，人工标签还必须显式写 `label_source`：

- `INDEPENDENT_HUMAN_REVIEW`：独立人工 reviewer 按本协议复核；
- `LOCAL_IN_PRODUCT_EXPLICIT_SELF_REPORT`：用户在成竹 Continue 里显式填写的本机自报；
- 缺失/空值会被汇总为 `UNSPECIFIED`，可用于调试汇总，但 **永远不能满足 Stable Gate 的指标来源要求**。

`reviewer` 是去重与审计标识，不是身份认证；即使填写真实姓名，也不能替代 authorized pilot manifest。

运行：python scripts/v2_conversation_human_eval.py labels.jsonl --out report.json --markdown-out report.md

从本地 dogfood 数据先生成“待人工标注 seed”：

python scripts/v2_conversation_label_seed.py --db <CHENGZHU_HOME>/data/product.db --out labels.seed.jsonl

seed 中 reviewer、useful、actual_type、silence_correct、cognitive_load_delta 等标签字段都是空值；它只是 review queue，不是评测证据。

没有有效 human label 时 status 必须是 INSUFFICIENT_EVIDENCE；不会生成 PASS。

**标注文件保护与校验**：
- `--out` 不能指向输入 `product.db`；导出种子不会覆盖已存在的 JSONL 或人工标注文件。重复导出应使用新的文件名。
- 汇总工具的 `--out` / `--markdown-out` 不能覆盖输入标签，也不能互相指向同一文件。
- 同一个 reviewer 对同一 session/kind/event 的重复标注会被拒绝；不同 reviewer 可分别标注同一事件。
- `cognitive_load_delta` 只允许 -2 到 +2 的有限数值，不能使用布尔值、NaN、Infinity 或超出量表的分值。无标签仍为 null，不计入分母。
- 含 transcript/source excerpt 的种子和标注仅保存在本地受控路径，不应进入公开仓库或 CI artifact。

## 3. guidance

guidance_class 可取 PROACTIVE、RECALL、DIRECT_QUESTION、CRITICAL_RISK、DELIVERY。

useful=true 的含义：如果没有这条提示，用户有较大概率会漏掉一个对当前目标有价值的信息、问题、风险或表达动作。不是“文字不错”。

interruption_regret=true 的含义：即使内容正确，这个时机弹出仍使表达、倾听或对话节奏变差。

source_correct=true 必须同时满足：来源确实支持内容、visibility 允许本场使用、没有把 Quick Note 或 transcript observation 冒充 confirmed truth、frozen source version 正确。

recall_correct 仅用于 RECALL：对象正确、状态仍有效、没有被 supersede/tombstone，并且与当前话题相关。

### Longitudinal Recall Utility（Policy v8）

`recall_correct` 证明“记得对”，但不能证明“跨场记忆真的帮到用户”。Policy v8 因此增加 `longitudinal_recall_utility_rate`，只使用同时满足以下条件的 Guidance：

```text
origin.kind = TRANSCRIPT_AUTO
guidance_class = RECALL
primary source_ref.kind = CONVERSATION_ITEM
source_ref.space_id = current space_id
source_ref.session_id != current session_id
explicit local self-report useful = true / false
```

新 runtime 会把被 Recall 的已确认 Conversation Item 作为 **第一主 provenance ref**，并冻结 `id / space_id / session_id / review_status / state`。底层 transcript/document ref 仍保留在后面，但不能替代这条 longitudinal provenance。

边界：

- 同一 Session 刚确认的 item 不算跨场价值；
- 不同 Space 的 item 不算；
- manual Guidance Lab / pre-v12 非自动 Guidance 不算；
- pre-fix RECALL 没有 `CONVERSATION_ITEM + source_session_id` 时，不得根据标题、时间、底层 transcript ref 或当前数据库状态事后补造；
- independent reviewer 可以判断 `recall_correct`，但不能替用户回答“这条长期记忆对我有没有用”；Stable 的 longitudinal utility 只接受 `LOCAL_IN_PRODUCT_EXPLICIT_SELF_REPORT`。

Policy v8 不另拍一套宽松数字：阈值 `>=0.80` 复用既有 Opportunity usefulness 门槛，`min_n>=20` 复用既有 Recall 样本底线。

## 4. silence

silence_correct=true 表示这个时间窗口不主动打断是更好的动作；false 表示当时存在高价值、可溯源、时间敏感的信息且应该主动出现。

schema v12 起，Useful Silence 的 Stable 样本只来自真实自动 transcript runtime 且 `origin.decision_class=ARBITER` 的 SILENT 决策。以下静默仍保留审计，但不进入 Useful Silence 分母：

- `MODE_FORCED`：例如 Quiet mode 强制不主动提示；
- `PROFILE_FORCED`：Profile 本身不允许该 Guidance lane；
- `PROVENANCE_FORCED`：来源/visibility 不允许展示。

这些是 policy/profile/provenance compliance，不是 Guidance Arbiter 对“此刻值不值得打断”的自由判断，混入分母会虚高 Useful Silence。

## 4.1 v12 Auto-runtime Evidence Contract

Stable 的实时 Guidance 人体评测只允许来自真实自动 TRANSCRIPT 主路径，不允许用高级手工 Guidance Lab 或 pre-v12 历史事件补样本。

每个可评估的 final PRIMARY_AUDIO turn 在 v12 runtime 中必须留下：

```text
conversation_transcript_segment
→ exactly one automatic decision evidence
   ├─ SHOWN Guidance
   └─ SILENT / SUPPRESSED Guidance
→ origin = {
     kind: TRANSCRIPT_AUTO,
     transcript_segment_id,
     channel,
     ai_assistance,
     assistance_mode,
     decision_class
   }
```

Stable live-guidance population 要求：

- `origin.kind = TRANSCRIPT_AUTO`；
- `origin.transcript_segment_id` 非空；
- Opportunity / Interruption / Source Attribution / Recall 使用自动 SHOWN Guidance；
- Useful Silence 进一步要求 `decision_class = ARBITER`；
- manual Guidance Lab、没有 v12 origin 的历史 Guidance、forced silence 不进入这些指标分母。

pre-v12 历史事件不得根据 `reason=TRANSCRIPT_*` 事后回填 origin；历史样本身份必须保持不可重建，避免评测口径随代码演进漂移。

## 5. direct_question

`predicted` 与 `actual` 均为 bool。actual=true 表示当前说话者确实向用户提出需要回应的问题。不要把修辞问题、自问自答或口头语自动算 direct question。

### v11 prediction provenance

Direct Question Precision / Recall 必须使用 **capture-time frozen prediction**，不能在评估时用当前 detector 重跑历史 transcript：

```text
final PRIMARY_AUDIO transcript
→ analysis.direct_question = {
    eligible,
    predicted,
    detector_version,
    channel,
    ai_assistance
  }
→ immutable row in product.db
→ label seed predicted
→ independent reviewer fills actual
```

当前 detector version 为 `heuristic-v1`。未来即使 detector 规则升级，旧 transcript 的 `predicted` 仍保持当时版本的结果；这是 precision / recall 可复现性的必要条件。

只有 capture-time `eligible=true` 的 versioned row 才进入 Direct Question 指标集合。若当时自动 transcript Guidance 未启用（`AI_LIMITED` / `AI_FORBIDDEN`，或 channel 为 `SELF_MIC`），snapshot 会明确记录 `eligible=false`；这表示 detector 当时没有作为产品能力运行，row 应从 reviewer queue / precision / recall 分母中排除，而不是记作 prediction 缺失。

对 pre-v11 历史 transcript，如果没有冻结的 `analysis.direct_question`：

```text
predicted = null
prediction_unavailable = true
```

这类 row 不进入 Direct Question Precision / Recall 分母。**禁止**为了增加样本量而用新版 detector 重跑旧文本、根据是否出现 ANSWER_CUE 倒推所有负样本，或把人工 actual 回填成 predicted。

`SELF_MIC` 不属于对方直接提问检测集合，因此不会进入 direct-question reviewer queue。Stable Gate 的 Direct Question Precision / Recall 仍要求 `label_source=INDEPENDENT_HUMAN_REVIEW`。

Direct Question 指标只有在存在 final transcript 时才有可复核样本；`NOTES_ONLY` Session 不会凭空生成此类 row。由于 prediction snapshot 与 transcript 共用其 retention 生命周期，pilot 应在 transcript retention 清理前完成 seed 导出 / independent review，或明确延长经授权的本地 retention。不要为了凑样本而关闭隐私清理或重建已删除的原始对话。

## 6. truth_item

需要 predicted_type / actual_type / predicted_state / actual_state。重点检查 Proposal 是否误判 Decision、能力表态是否误判 Commitment、owner 是否凭空变成 me、Deadline 是否有明确来源、supersession 是否正确、OpenQuestion 是否真的未解决。

`decision_commitment_state_precision` 的分母不是所有 truth item，而是模型 **预测为** `Decision / Commitment / Task` 的 row。Task 在产品真值模型中与 Commitment 共用 COMMITTED/owner 约束，因此属于该指标目标类。预测为 OpenQuestion / Risk / Proposal / Deadline 等 row 不得用来稀释这个 precision 分母；若模型把 Proposal 错预测成 Decision，则 predicted_type=Decision，仍然必须进入分母并计错。

## 7. continue

writeback_accurate=true 要求 Follow-up / Task / Issue / Decision Log Draft 不包含未 review 的 AI candidate，owner/due/state 正确，source 可追溯，而且没有声称外部系统已经写入。



## 7.1 Feedback retention integrity

本机显式 feedback 与其被标注对象遵循同一可解释生命周期：

```text
GUIDANCE / SILENCE feedback
→ target = conversation_guidance_event
→ target Guidance 到期删除
→ dependent feedback 同一次 confirmed retention cleanup 删除

CONTINUE / SESSION_OUTCOME feedback
→ target = Session-level outcome
→ 不随单条 Guidance retention 删除
→ 随 Session / Space 删除边界清理
```

`retention_preview()` 必须在用户确认前显式列出：

- `dependent_human_feedback`：即将随目标 Guidance 一起删除的反馈；
- `orphan_human_feedback`：旧版本可能已经留下、但目标 Guidance 不存在的不可审计反馈。

旧 orphan feedback 不是可用 evaluation evidence。diagnostics 会报告 `orphan_guidance_feedback_rows`；存在时 `human_feedback_integrity = NEEDS_RETENTION_CLEANUP`。显式执行 retention cleanup 后才恢复 `AVAILABLE`。

这条规则的目标是同时满足两件事：不为了评测永久绕过用户配置的隐私 retention，也不保留失去被标注事件后无法解释的孤儿标签。

## 8. session_outcome

cognitive_load_delta 建议使用 -2 到 +2：-2 明显降低，-1 略有降低，0 无变化，+1 略有增加，+2 明显增加。would_reuse_space 为用户是否愿意继续使用同一 Space。

## 9. 聚合指标

脚本输出 opportunity_precision、interruption_regret、source_attribution_accuracy、recall_precision、**longitudinal_recall_utility_rate**、useful_silence_rate、direct_question_precision、direct_question_recall、decision_commitment_state_precision、continue_writeback_accuracy、mean_cognitive_load_delta、space_reuse_intent_rate。

每项同时输出 value 与 n；n=0 时 value=null，绝不填 0 或 1。

## 10. 首批验证建议

只做 Project Sync / Design Review。每个用户先积累 5–10 个真实 Session；每场对 shown guidance 与关键 silence 抽样标注；每场结束至少标一次 Continue；每个 Space 至少跨 3 场。第一阶段重点是找错误模式，而不是追求漂亮平均分。

## 10.1 产品内 Pilot Evidence Bridge（beta.3 后）

Conversation Continue 允许用户在会后显式填写本机反馈。当前产品把这条链分成两层：

**第一层：结束 Session 后原地出现的 Quick Debrief**

- Continue：`writeback_accurate`；
- Session Outcome：`would_reuse_space`；
- Session Outcome：`cognitive_load_delta`。

这三项应直接出现在 Live → End → Continue 的会后结果区，不要求用户先返回 Space、重新找到 Session 或展开评估工具。它们代表用户刚结束真实会话时的显式自报，不等同于自动 telemetry。

**第二层：详细事件级 Review**

- shown Guidance：`useful`、`interruption_regret`、`source_correct`；RECALL 额外允许 `recall_correct`；
- SILENT / suppressed decision：`silence_correct`。

详细 Review 仍保留在同一会后入口和 Space 历史回看入口，但不应阻塞用户完成 Continue，也不应为了提高样本量强迫逐条标完整场事件。

设计原则：

1. 优先在事件刚结束时采集少量主观结果，降低延迟回忆造成的失真；
2. Quick Debrief 只保留 3 个最小必要问题，避免评估本身增加认知负担、降低长期填写率；
3. 事件级 Guidance / SILENT 标注采用 progressive disclosure，可稍后补；
4. Quick Debrief 完成度和详细标注完成度可显示为本机进度，但**不是** quality score、meeting score 或 Stable readiness score；
5. 不因为 UI 更容易填写而改变任何 Stable Promotion threshold、label source 或 cohort 口径。

硬边界：

1. 反馈写入 `conversation_human_feedback`，只保存在本机 product.db；当前没有远程 telemetry uploader；
2. Product API 固定记录 `reviewer_kind=SELF_USER`，前端不能自称 `VERIFIED_EXTERNAL_USER`；
3. Pin / Used / Dismissed / click-through 不会被自动转换成 useful / wrong / silence_correct；
4. 产品内自报只能叫 `LOCAL_EXPLICIT_SELF_REPORT`，不能单独证明 reviewer 身份、授权真实 pilot 或 PMF；
5. 原始 labels 与可能包含的 notes 仍按私人评估数据处理，不自动上传公开仓库或 CI artifact。

导出产品内显式反馈：

```bash
python scripts/v2_conversation_feedback_export.py \
  --db <CHENGZHU_HOME>/data/product.db \
  --out in-product-self-report.jsonl
```

与独立 reviewer 标签可以分文件聚合，避免手工拼接：

```bash
python scripts/v2_conversation_human_eval.py \
  in-product-self-report.jsonl \
  independent-review.jsonl \
  --out human-report.json \
  --markdown-out human-report.md
```

同一 reviewer / session / kind / event 即使跨文件重复也会被拒绝。

### Prediction leakage 防线

schema v10 起，AI_EXTRACTED Conversation Item 在创建时冻结不可变 `prediction_json`。Continue 的 CONFIRM / EDIT / REJECT / DONE / SUPERSEDE 只能修改当前 truth row，不得改写 prediction snapshot。

因此 label seed 的 `predicted_type / predicted_state` 只允许来自：

1. v10+ immutable prediction snapshot；或
2. 历史 pre-v10 且仍处于 `AI_EXTRACTED`、尚未人工 review 的 row。

若一个历史 item 已被 review、但没有原始 prediction snapshot，则：

```text
predicted_type = null
predicted_state = null
prediction_unavailable = true
```

宁可从 precision 分母中排除，也禁止把 post-review truth 倒灌成模型 prediction。Decision / Commitment state 的独立 reviewer 应标注“在该 prediction 时刻、按 Truth Boundary 应输出的类型/状态”，而不是事后拿最终长期状态倒推当时预测。

## 10.2 Human-report cohort / metric contract v6

`v2_conversation_human_eval.py` 现在输出：

```text
report_contract_version = v2.0-R1-human-eval-6
cohort.status
cohort.sessions[] = {session_id, profile, space_id}
metrics_by_profile_and_label_source
```

同一 `session_id` 如果在标签文件中出现不一致的 profile / space，report 必须标记 `cohort.status=INCOMPLETE`。Stable evaluator v4 会 fail closed。

Stable metric 不再读取“全 profile 总分”作为 promotion 分数，而只读取：

```text
PROJECT_SYNC + DESIGN_REVIEW
×
metric.allowed_label_sources
```

这意味着其它 Conversation Profile 的标签可以用于研发分析，但不能替首发验证楔子抬高 Stable Gate。

对应 pilot manifest contract = `v2.0-R1-pilot-cohort-2`。manifest 逐场记录 `session_id / space_id / local pseudonymous user_ref`；Stable evaluator 自动推导 profile session 数、distinct pseudonymous users 与 cross-session Spaces，并验证 human-report Session 全部属于授权 cohort。当前 policy v8 继续规定：一个 Space 只有在 **全部 selected Session 绑定同一个 pseudonymous user_ref 且至少有 3 个授权 Session** 时才计为 cross-session Space；混合多个 user_ref 的同一 Space直接 fail-closed。除此之外，重复使用本身不再被当成长期价值的替代证据：Stable 还要求足够的、带 prior-session Conversation Item provenance 的自动 RECALL 获得用户显式 useful 自报。该资格不能由 2 场重复使用、多人共享同一 Space、手填 aggregate count、reuse intent 或后处理推断替代。

原始 label / report / manifest 都可能包含私人会议标识，继续保持本地受控存储，不应上传公开仓库或 CI artifact。

## 10.3 Authorized pilot manifest builder

Policy v4 不再建议手抄 `session_id / space_id / profile / period`。仓库提供本地 builder：

```text
scripts/v2_conversation_pilot_manifest.py
```

它只读取 `product.db` 中这些 Session 事实：

- `session_id`；
- `space_id`；
- frozen Session `template/profile`；
- `status`；
- `started_at / ended_at`；
- `consent_ack`；
- matching Frozen Session Pack provenance。

它**不会**读取或复制 transcript、参与者姓名、Space 标题、Guidance 内容、资料正文，也不会从数据库猜“这个人是谁”或“这场是否获得真实授权”。

每个入选 Session 的 `user_ref` 必须由 pilot operator 显式提供本地匿名 token：

```bash
python scripts/v2_conversation_pilot_manifest.py \
  --db <CHENGZHU_HOME>/data/product.db \
  --session cv_project_01=pilot-user-01 \
  --session cv_design_01=pilot-user-02 \
  --out pilot-manifest.draft.json
```

默认输出故意是：

```text
evidence_type = DRAFT_AUTHORIZED_REAL_CONVERSATION_PILOT
critical_incidents = null
attestations = []
```

因此不能直接通过 Stable evaluator。

Builder 会 fail closed：

- 只允许 `ENDED` Session；
- 只允许 `PROJECT_SYNC / DESIGN_REVIEW`；
- 要求 Session consent acknowledgement；
- 要求可验证 Frozen Session Pack；
- 重复 / 不存在 Session 拒绝；
- `user_ref` 只允许本地 pseudonym token 形状，不允许 email / free-text name；
- period 从入选 Session 的真实时间自动推导为 timezone-aware UTC；
- 输出文件已存在时拒绝覆盖。

确认 draft 与真实授权 pilot 范围完全一致后，operator 必须重新显式 finalize，并逐项声明：

```bash
python scripts/v2_conversation_pilot_manifest.py \
  --db <CHENGZHU_HOME>/data/product.db \
  --session cv_project_01=pilot-user-01 \
  --session cv_design_01=pilot-user-02 \
  --finalize \
  --critical-incidents 0 \
  --attest AUTHORIZED_REAL_USE \
  --attest NO_SYNTHETIC_ROWS_IN_HUMAN_EVAL \
  --attest RAW_LABELS_KEPT_LOCAL \
  --attest NO_CRITICAL_PRIVACY_INCIDENT \
  --attest NO_KNOWN_DATA_LOSS \
  --out real-pilot.json
```

少任意一项 attestation 或不显式提供 incident count，都不能 finalize。

边界仍然是：

```text
DB session membership verified
!= human identity verified
!= authorization verified by system
!= participant consent independently verified
!= REAL_USER_VALIDATED
!= PMF_PROVEN
```

五项 attestation 是 operator declaration，不是 Chengzhu 的身份认证或法律证明。manifest / labels / report 均应保存在本地受控路径，不上传公开仓库或 CI artifact。

## 10.2 Real Pilot Workspace

真实 pilot 推荐通过：

`docs/evals/V2_CONVERSATION_REAL_PILOT_RUNBOOK.md`

和：

`scripts/v2_conversation_pilot_workspace.py`

组织证据。Workspace 只编排既有 seed / self-report / manifest / human-eval / stable-readiness 语义，不创造新的 label source，也不改变本协议中的人工标注定义。

关键保护：

- 只导出显式选择的 Session；
- policy / draft manifest / self-report / final manifest 使用 SHA256 检测冻结输入漂移；
- unlabeled seed 不能直接作为 human evidence；
- existing workspace/evaluation 不覆盖；
- raw review material 继续只留本机。


## 11. 状态升级边界

human-label report 本身只证明存在人工标签；它不能验证 reviewer 是否是真实外部用户，也不能单独支持 PMF_PROVEN = TRUE 或 V2_PRODUCTIZED_RELEASE = TRUE。

当有授权真实 pilot manifest 后，使用：

```bash
python scripts/v2_conversation_stable_readiness.py \
  human-report.json \
  real-pilot.json
```

稳定版产品证据阈值见 `docs/evals/V2_CONVERSATION_STABLE_PROMOTION_POLICY.json`。当前源码 policy v8 继承 v4 的 authorized-cohort binding、v5 的 >=3 Session cross-session floor、v6 的 UNIQUE_EVENT_PER_METRIC sample unit 与 v7 的单 pseudonymous-user Space binding，并增加“**跨场记忆必须对用户有用**”的 longitudinal Recall Utility Gate。2 场重复使用、多人各用同一 Space、reuse intent 或 Recall correctness 本身都不能替代这个用户价值指标。Longitudinal Recall Utility 只接受本机显式 self-report；Recall correctness / Source Attribution / Direct Question / Decision-State / Continue Accuracy 等客观质量指标仍要求 `INDEPENDENT_HUMAN_REVIEW`。总体 aggregate 再漂亮，也不能用错误来源、错误 cohort、缺失 prior-session provenance 或历史回填替代该指标所需证据。即使全部通过，也只允许：

```text
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = TRUE
```

stable 发布仍要走独立 packaged/release/security/public-truth review；PMF 仍需要持续使用、留存、价值与愿付费等更长期证据。

## 证据来源核验边界

标注工具本身不能核验 reviewer 身份或参会者是否属于真实外部用户。`HUMAN_LABELS_AVAILABLE` 只表示有非空人工标签；`REAL_CONVERSATION_USER_EVIDENCE_AVAILABLE` 默认保持 `false`。只有独立、获得适当授权的真实使用记录与研究协议才能进一步支持真实用户结论。

导出的标签种子可能包含私人会议内容与 source excerpt。只允许用户明确指定本地数据库和输出路径，采取最小化、脱敏和受控访问；不得把原始标签自动上传公开 GitHub 或 CI artifact。
