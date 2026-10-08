# Chengzhu v2.0-R1 — Onboarding, Upgrade, Operations, Business & Final Acceptance

# 1. v1 → v2 Upgrade

v1.4.2 用户升级后默认仍进入 **Interview Profile**。

不得：

- 自动切换到 Conversation；
- 自动扫描全部历史并生成对话画像；
- 自动导入 Calendar；
- 自动开启 microphone/capture。

首次显示轻量入口：

```text
新：对话 Beta
把成竹用于项目同步、设计评审、1:1、客户会等真实对话。
[了解并开启]
```

用户 opt-in 后才出现 Conversation Profile。

# 2. Conversation Onboarding

目标不是“设置完成”，而是跑通一次可理解的价值链。

```text
开启 Conversation
→ Privacy / Capture defaults
→ 创建第一个 Space
→ 选择 Template
→ 填一个 Goal
→ 加 1–3 个来源或 Quick Note（可跳过）
→ Guided Dry Run
→ 看一次 Recall / Question / Stay Silent 示例
→ 完成
```

如果用户已有 v1 项目材料，可以显式选择复用；不自动全量带入。

# 3. Guided Dry Run

因为真实会议不可重复，首次体验提供一个 synthetic local scenario：

- 30–60 秒；
- 明确标注 Demo；
- 展示 Proposal ≠ Decision；
- 展示 Recall；
- 展示 Contribution Opportunity；
- 展示 suppression / SILENT；
- 展示 Continue review。

Demo evidence 永远标：

```text
SYNTHETIC_DEMO
```

# 4. Meeting Discovery / Notifications

v2 可以检测“可能即将进入会话”，但必须低侵入。

来源：

- Calendar connector；
- desktop microphone-in-use heuristic；
- manual start。

通知：

```text
PDIG Design Review · 10 分钟后
[准备] [忽略]
```

不得因检测到 mic 使用就开始录音。

# 5. Ad-hoc Conversation

没有 Calendar 也能：

```text
[开始临时会话]
→ 创建一个本地临时 Space-backed continuity container
→ 使用选择的 Template
→ Start
```

当前 runtime 不建立第二套“standalone Session”真相模型。临时会话从创建起就属于一个普通本地 Space，因此结束后：

- 可以继续保留这个临时 Space，下一场沿用 continuity；
- 可以重命名 / 调整 Goal / Sources，使它成为长期 Space；
- 不需要保留时，显式删除该临时 Space（遵循现有 provenance / tombstone / destructive confirmation 规则）。

这避免同一套 Decision / Commitment / provenance 在“Space Session”和“standalone Session”之间出现双真相。

# 6. Global Search / Command

Ctrl+K 在 Conversation Profile：

- 创建 Space；
- 准备下一场；
- 开始临时会话；
- 找 Decision；
- 找 Commitment；
- 找 Open Question；
- 打开 Quick Notes；
- Pause suggestions；
- 切换 assistance mode；
- Export current session。

Search result 必须带 source/time/space，不做无来源“AI answer”。

Runtime closure（2026-10-08）：

- Ctrl+K 已接入 Find Decision / Commitment / Open Question；
- 结果显示 Space / Session / time / review state / source kind；
- Export current session 导出分类化 local JSON；
- 不把 search 结果或 export 动作解释成外部同步。

# 7. Notifications after meeting

默认仅本机：

- unresolved commitment due soon；
- next session upcoming；
- user-owned deadline；
- requested follow-up。

不默认发送“你今天会议表现如何”之类评价通知。

# 8. Internationalization

五层语言继续复用：

- UI Language；
- Speech/ASR Language；
- Answer/Expression Language；
- Coding Language；
- Technical Term Policy。

Conversation 新增：

- participant language hint；
- translation display policy。

翻译后的文本必须能追溯原 transcript，不把翻译当原始 source。

# 9. Time / Date semantics

Commitment/Deadline 解析必须保存：

- original text；
- normalized datetime；
- timezone；
- ambiguity。

例如“下周五”如果 timezone/context 不明确，必须进入 review。

Runtime closure：

- product schema v6 为 `conversation_item` 增加 additive `time_semantics_json`；
- transcript 抽出的相对 Deadline 保留原话并默认 `AMBIGUOUS`；
- Deadline 在 normalized datetime + timezone 明确前不能从 review queue 升级为长期确认状态；
- 带时间的 Commitment / Task 同样不能把 unresolved temporal metadata 静默写成 COMMITTED；
- `due_at` 保留兼容字段，但 canonical temporal provenance 以 time semantics envelope 为准。

# 10. Offline

Local mode 目标：

- ASR（如设备支持）；
- local state；
- notes；
- confirmed memory；
- local model guidance（如用户配置）。

Cloud unavailable 时：

- 不丢 transcript queue；
- 不伪造 guidance；
- UI 明确 degraded mode。

# 11. Diagnostics

Settings > Diagnostics 新增：

- audio capture；
- diarization；
- local/cloud processing；
- connector health；
- Context Compiler；
- retrieval；
- state engine；
- guidance arbiter；
- export/delete integrity。

普通用户只看到：

```text
可用 / 受限 / 需要处理
```

raw JSON 二级展开。

# 12. Security

必须保持：

- tokens encrypted/OS keychain where available；
- connector scope least privilege；
- no API key in export/log/screenshot；
- redacted diagnostic bundle；
- local DB migration backup；
- destructive action confirmation；
- no remote listener by default。

# 13. Telemetry

默认 local-first。

Remote telemetry future opt-in only，且不能上传：

- raw transcript；
- audio；
- private notes；
- source excerpts；
- screen captures。

允许的最小匿名事件未来也必须有 schema/version/consent。

# 14. Business Model Boundary

v2 的商业对象首先仍是个人专业用户，而不是组织监控。

建议产品层级只作为未来定价假设，不写成已验证：

### Free / Trial hypothesis
- limited history；
- manual sessions；
- core notes/continue。

### Pro hypothesis
- longer memory；
- live Contribution Opportunity；
- local model options；
- connectors；
- advanced profile templates。

### Team/Enterprise future
只有个人价值验证后再做：

- shared spaces；
- org policy；
- admin retention；
- team memory；
- enterprise connectors。

禁止把 employee scoring 作为企业卖点。

# 15. Success Metric Hierarchy

North-star 不能是 meeting count。

设计阶段候选：

```text
Useful Conversation Continuity
```

由以下真实行为组合验证：

- same Space reused；
- confirmed item reused；
- source opened；
- useful guidance adopted；
- Continue completed；
- next session uses prior state。

在没有真实用户前不得固化为增长 KPI。

# 16. Product Copy

推荐中文：

> 成竹帮你把过去真正发生过的事带进下一场对话，并在值得开口的时候提醒你。

推荐英文：

> Know what matters. Say what is yours. At the right moment.

避免：

- “读懂对方心理”；
- “永远知道该说什么”；
- “不会漏掉任何机会”；
- “100% accurate meeting memory”；
- “undetectable”。

# 17. Support / Troubleshooting

必须覆盖：

- 录不到系统音频；
- speaker label 不准；
- Calendar disconnected；
- provider unavailable；
- local model too slow；
- source 找不到；
- wrong Decision extraction；
- accidental recording；
- delete/export；
- SmartScreen；
- overlay geometry。

每个错误都给下一步，不只给 error code。

# 18. Final Design Acceptance Matrix

## Product
- [x] v2 definition
- [x] launch wedge
- [x] all profile templates
- [x] IA
- [x] core loop
- [x] onboarding
- [x] upgrade
- [x] ad-hoc sessions
- [x] search/commands

## Data / Truth
- [x] Space
- [x] Goal
- [x] Pack
- [x] Session
- [x] Participant
- [x] Counterparty observation
- [x] Topic/OpenThread
- [x] Conversation Item
- [x] state transitions
- [x] provenance
- [x] supersession
- [x] delete/export

## Intelligence
- [x] state engine
- [x] question targeting
- [x] Context Compiler
- [x] Recall
- [x] Talking Point
- [x] Answer Cue
- [x] Question
- [x] Risk
- [x] Delivery
- [x] Contribution Opportunity
- [x] Expression Planner
- [x] SILENT
- [x] Guidance Arbiter
- [x] suggestion budget
- [x] feedback loop
- [x] memory write-back

## UI/UX
- [x] Profile Switcher
- [x] Home
- [x] Space list
- [x] Room
- [x] Prepare
- [x] Participant UI
- [x] Preflight
- [x] Live
- [x] Manual Ask
- [x] Continue
- [x] Decision Review
- [x] Follow-up drafts
- [x] empty/error/fallback
- [x] accessibility
- [x] light/dark/narrow/high-DPI requirements

## Privacy / Integration
- [x] capture modes
- [x] processing modes
- [x] consent
- [x] retention
- [x] screen context
- [x] speaker identity boundary
- [x] connector authority
- [x] reviewed write-back
- [x] MCP client/server boundary
- [x] telemetry boundary

## Validation / Release
- [x] synthetic truth
- [x] real-user truth boundary
- [x] eval dimensions
- [x] engineering stages
- [x] Windows gates
- [x] Interview non-regression
- [x] Reality Report contract

# 19. Final Design Verdict

当本目录与 executable contracts 在 CI 中通过时，可声明：

```text
CHENGZHU_V2_0_R1_DESIGN = COMPLETE
CHENGZHU_V2_0_R1_CONTRACT = COMPLETE
```

仍必须保持：

```text
V2_ENGINEERING_COMPLETE = FALSE
REAL_CONVERSATION_USER_EVIDENCE_PENDING = TRUE
PMF_PROVEN = FALSE
```
