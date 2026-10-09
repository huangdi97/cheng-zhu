# Chengzhu v2 Conversation Human-label Evaluation Protocol
## 2026-10-08

> 适用范围：Project Sync / Design Review 首批 dogfood 与真实用户验证。本协议不用于 synthetic CI gate，也不能单独证明 PMF。

## 1. 为什么必须独立做人类标注

以下指标不能由点击率或 synthetic replay 代替：Recall Precision、Source Attribution Accuracy、Direct Question Detection、Decision / Commitment State Precision、Opportunity Precision、Interruption Regret、Useful Silence Rate、Continue Write-back Accuracy、real cross-session value、cognitive load。

禁止把 USED/PINNED 自动等于 useful，DISMISSED 自动等于 wrong，suppressed 自动等于 useful silence，或 synthetic PASS 自动等于 real-user value。

## 2. JSONL 规则

每行一个 JSON object。kind 必须是 guidance、silence、direct_question、truth_item、continue、session_outcome 之一；reviewer 与 session_id 必填。可选共同字段：space_id、profile、event_id、timestamp、notes。

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

## 4. silence

silence_correct=true 表示这个时间窗口不主动打断是更好的动作；false 表示当时存在高价值、可溯源、时间敏感的信息且应该主动出现。

## 5. direct_question

predicted 与 actual 均为 bool。actual=true 表示当前说话者确实向用户提出需要回应的问题。不要把修辞问题、自问自答或口头语自动算 direct question。

## 6. truth_item

需要 predicted_type / actual_type / predicted_state / actual_state。重点检查 Proposal 是否误判 Decision、能力表态是否误判 Commitment、owner 是否凭空变成 me、Deadline 是否有明确来源、supersession 是否正确、OpenQuestion 是否真的未解决。

## 7. continue

writeback_accurate=true 要求 Follow-up / Task / Issue / Decision Log Draft 不包含未 review 的 AI candidate，owner/due/state 正确，source 可追溯，而且没有声称外部系统已经写入。

## 8. session_outcome

cognitive_load_delta 建议使用 -2 到 +2：-2 明显降低，-1 略有降低，0 无变化，+1 略有增加，+2 明显增加。would_reuse_space 为用户是否愿意继续使用同一 Space。

## 9. 聚合指标

脚本输出 opportunity_precision、interruption_regret、source_attribution_accuracy、recall_precision、useful_silence_rate、direct_question_precision、direct_question_recall、decision_commitment_state_precision、continue_writeback_accuracy、mean_cognitive_load_delta、space_reuse_intent_rate。

每项同时输出 value 与 n；n=0 时 value=null，绝不填 0 或 1。

## 10. 首批验证建议

只做 Project Sync / Design Review。每个用户先积累 5–10 个真实 Session；每场对 shown guidance 与关键 silence 抽样标注；每场结束至少标一次 Continue；每个 Space 至少跨 3 场。第一阶段重点是找错误模式，而不是追求漂亮平均分。

## 11. 状态升级边界

human-label report 本身只证明存在人工标签；它不能验证 reviewer 是否是真实外部用户，也不能单独支持 PMF_PROVEN = TRUE 或 V2_PRODUCTIZED_RELEASE = TRUE。

当有授权真实 pilot manifest 后，使用：

```bash
python scripts/v2_conversation_stable_readiness.py \
  human-report.json \
  real-pilot.json
```

稳定版产品证据阈值见 `docs/evals/V2_CONVERSATION_STABLE_PROMOTION_POLICY.json`。即使全部通过，也只允许：

```text
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = TRUE
```

stable 发布仍要走独立 packaged/release/security/public-truth review；PMF 仍需要持续使用、留存、价值与愿付费等更长期证据。

## 证据来源核验边界

标注工具本身不能核验 reviewer 身份或参会者是否属于真实外部用户。`HUMAN_LABELS_AVAILABLE` 只表示有非空人工标签；`REAL_CONVERSATION_USER_EVIDENCE_AVAILABLE` 默认保持 `false`。只有独立、获得适当授权的真实使用记录与研究协议才能进一步支持真实用户结论。

导出的标签种子可能包含私人会议内容与 source excerpt。只允许用户明确指定本地数据库和输出路径，采取最小化、脱敏和受控访问；不得把原始标签自动上传公开 GitHub 或 CI artifact。
