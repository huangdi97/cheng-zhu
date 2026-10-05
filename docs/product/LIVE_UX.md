# Live UX — Goal-centered Live Cockpit

> **CURRENT · v1.4.x**
>
> Product Canonical: `docs/canonical/Chengzhu_v1.3-R2_CANONICAL.md`  
> Validation addendum: `docs/canonical/Chengzhu_v1.4-R1_VALIDATION_HARDENING.md`  
> Frozen realtime core: `docs/canonical/Chengzhu_v1.2-R2_CANONICAL.md`

## 1. 定位

Live 不是“答案生成器页面”，而是 Goal-centered Interview OS 的实时阶段：

```text
Goal
→ Preflight
→ Live
→ Reflection
→ Next Focus
```

Live 的第一原则：

> **Cue before essay. 用户扫一眼就能继续说，而不是低头照稿。**

Verified Core 负责实时正确性；v1.3/v1.4 产品层负责让用户只看到当前真正需要的东西。

---

## 2. 第一层信息层级

正式 Live 的视觉优先级固定为：

```text
1. 当前 Question
2. Fast Cue
3. Source / Warning
```

Deep Answer、Transcript、Quick Notes、Screen、References、Human Coach 和历史轮次全部属于第二层。

禁止重新把完整长答案变成默认视觉中心。

### Fast Cue

Fast Cue 在 Deep Answer 之前由 realtime pipeline 产生并广播。

用户可看到：

- 一句话方向；
- 2–5 条可扫读 cue；
- cue 的来源；
- 必要的事实边界 / caution；
- 本场 Goal 上下文。

来源 taxonomy：

```text
PERSONAL_EVIDENCE
KB_KNOWLEDGE
WORLD_KNOWLEDGE
HUMAN_COACH
```

只有 `PERSONAL_EVIDENCE` 可以支持“我做过 / 我负责”。

---

## 3. 单一 Live 状态

Live 不同时向用户暴露 ASR / Retrieval / Compiler / LLM 四套 loading。

产品状态收敛为：

```text
Listening
Question detected
Preparing
Cue ready
Answering
Reconnecting
```

Diagnostics 可以显示内部阶段，但主 Live UI 不显示工程流水线。

---

## 4. GuidanceViewModel

主窗口和 Overlay 必须消费同一份 `GuidanceViewModel`。

核心字段覆盖：

- resolved question；
- Fast Cue；
- source；
- warning / truth boundary；
- Deep Answer availability；
- timing metadata；
- current Goal/session context。

禁止主窗口和 Overlay 各自重新解析 raw answer，避免展示语义漂移。

---

## 5. Deep Answer

Deep Answer 是第二层渐进披露：

```text
Fast Cue
   ↓
[展开完整回答]
   ↓
Deep Answer
```

Deep 适用于：

- 用户需要更多结构；
- System Design / Case 等复杂问题；
- 想查看完整 trade-off；
- 复盘或练习时继续深入。

Deep 不能阻塞 Fast Cue。

---

## 6. 当前轮与历史轮

当前问题拥有视觉权威。

过去轮次：

- 默认折叠 / 降低视觉层级；
- 可以回看；
- 不与当前 Cue 抢视觉注意力。

新问题到来时：

- 旧 Deep 不应继续占据主视野；
- 当前 Question / Cue 必须成为主焦点。

---

## 7. Quick Notes

Quick Notes 是用户自己写给自己的现场短笔记：

```text
Quick Note
!= Evidence
!= KB
!= Memory
!= confirmed Claim
```

Live 中：

- Goal-scoped notes 一键打开；
- 默认只读；
- 不自动改写；
- 不自动升级为个人事实；
- 可以承载“想问”“边界提醒”“技术词”等短信息。

---

## 8. Pin Moment

用户可以用按钮或 `Ctrl+P` 标记当前时刻：

- 重要；
- 我答崩了；
- 对方透露关键信息；
- 下一场要准备；
- 事实需要确认。

Pin 是用户判断，不是 AI 自动评分。

Pin 在 Reflection 第一屏优先于通用 AI 总结，并且只有用户动作才可以进一步转成：

- Next Focus；
- Story；
- Fact Check。

---

## 9. Nudge / Open Thread

Nudge 是 Fast Cue 之后的低优先级提示。

类型：

```text
MISSING_DIMENSION
LIKELY_FOLLOWUP
FACT_BOUNDARY
ASK_BACK_OPPORTUNITY
```

必须满足：

- 没有新问题；
- 用户没有正在说话；
- 置信度达到阈值；
- proactive guidance 开启；
- 一次只显示一个。

优先级永远：

```text
Fast Cue > Warning > Nudge
```

Nudge 必须支持 cooldown、duplicate suppression、already-mentioned suppression、新问题取消。

---

## 10. Closing Mode

当 Question Understanding 识别到：

```text
“你还有什么想问我们的吗？”
```

进入 Closing Mode。

建议来源：

- Goal；
- 公司 / 岗位上下文；
- 本场真实 transcript；
- 面试官本场透露的信息；
- Quick Notes 中的“想问”；
- 尚未解决的 open threads。

优先生成上下文化追问，而不是默认“公司文化怎么样”这种 generic 问题。

---

## 11. Overlay 3.0

Overlay 由三个独立维度控制：

### Dock

```text
Top
Left
Right
Free
```

### Interaction

```text
Passive
Interactive
```

### Size

```text
Compact
Standard
Focus
```

Idle 时应尽量收敛，例如：

```text
● Listening · MindRank
```

Cue 到来时自动展开；空闲后可以回到 Compact。

Overlay 只是显示层，不重新实现 Intelligence。

---

## 12. Human Coach

Human Coach 是独立 Guidance Source，不是“秘密答案来源”。

默认：

```text
HUMAN_PRACTICE_ONLY
```

正式 Live 只有 `HUMAN_ALLOWED` 时才能显示。

Coach suggestion：

- 必须明确标为教练；
- 永远不能成为 Evidence；
- 不允许远程键鼠控制；
- 不做 anti-proctoring / detection evasion。

---

## 13. Share Privacy

默认：

```text
OFF
```

含义：

> 尽量减少成竹私人内容在受支持的屏幕共享/录屏路径中意外出现。

不代表：

- undetectable；
- 绕过会议软件；
- 绕过监考；
- 绕过反作弊。

---

## 14. Live → Reflection

正式结束动作必须闭合完整产品链：

```text
结束面试
→ stop Verified realtime core
→ product live/end
→ close Goal session link
→ clear session overrides
→ record live_completed
→ obtain reflection_ref
→ Reflection
```

如果 review 尚未生成：

- 不伪造 Reflection；
- 返回 Goal Interviews；
- 明确告诉用户“复盘正在生成”。

如果 product linkage 失败但 realtime 已经停止：

- 不错误说“结束面试失败”；
- 清除 stale Live UI；
- 进入 History；
- 给出可行动的关联错误提示。

---

## 15. Performance boundary

必须持续证明：

```text
Fast Cue before Deep
InterviewPack frozen
Context Compiler authoritative
no latest-job drift
truth boundary preserved
```

Goal / Library / analytics 渲染不能进入 realtime critical path。

---

## 16. 当前 Done

v1.4.x 当前产品状态：

- Preflight 3.0 — PRODUCT_COMPLETE
- cue-first hierarchy — PRODUCT_COMPLETE
- Deep secondary disclosure — PRODUCT_COMPLETE
- Quick Notes — PRODUCT_COMPLETE
- Pin — PRODUCT_COMPLETE
- Nudge — PRODUCT_COMPLETE
- Closing Mode — PRODUCT_COMPLETE
- Overlay 3.0 — PRODUCT_COMPLETE
- Human Coach policy — PRODUCT_COMPLETE
- Share Privacy — PRODUCT_COMPLETE
- Live → Reflection closure — v1.4.1 closure path

真正还需要真实用户验证的是：

- Cue 是否在压力环境下真的好扫；
- Overlay 是否干扰会议；
- Nudge 是否足够安静；
- Live → Reflection 是否符合真实使用习惯。

这些保持：

```text
REAL_USER_EVIDENCE_PENDING
```
