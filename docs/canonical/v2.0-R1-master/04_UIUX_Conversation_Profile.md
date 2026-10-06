# Chengzhu v2.0-R1 — UI/UX: Conversation Profile

# 1. Visual Direction

继续：

```text
Professional Workbench
not AI Dashboard
not surveillance dashboard
not transcript wall
not cyberpunk copilot
```

关键词：

- quiet；
- high-signal；
- source-visible；
- minimal interruption；
- light-first；
- dark complete；
- one primary action；
- one primary live guidance。

# 2. Profile Switcher

Brand 下方：

```text
成竹
[ 面试 ▾ ]
```

Options：

- 面试；
- 对话（Beta）。

切换 Profile 不是换账号，也不迁移数据；只是改变当前 work surface 与默认 actions。

# 3. Conversation Home

Desktop：

```text
┌──────────────────────────────────────────────────────────┐
│ 对话                                      [开始临时会话] │
│                                                          │
│ 下一场                                                    │
│ PDIG · Android Architecture Review · 明天 15:00          │
│ [准备下一场]                                              │
│                                                          │
│ Next Focus                                                │
│ · 先确认 rollback owner                                  │
│ · 带上 Q4 10x benchmark                                  │
│                                                          │
│ 我欠的                    等待 / 未解决                    │
│ · benchmark · 今天        · migration owner 未确认        │
│                                                          │
│ 最近变化                                                  │
│ · offline sync v2 已 AGREED · 来源 10/05 Design Review   │
└──────────────────────────────────────────────────────────┘
```

不展示：

- total meetings；
- words spoken；
- engagement chart；
- productivity score。

# 4. Conversation Space List

按用户心智分组：

- 最近；
- Upcoming；
- Active；
- Archived。

条目：

```text
PDIG · Android Architecture
Design Review · 明天 15:00
2 open commitments · 1 open question
```

不是 CRM pipeline。

# 5. Create Space

最短流程：

1. 名称；
2. Template；
3. 可选 project/context；
4. 默认 assistance mode。

不要一次要求上传十种资料。

Templates：

- Project Sync；
- Design Review；
- Presentation / Q&A；
- 1:1；
- Client Call；
- Negotiation。

# 6. Conversation Room

Tabs 固定：

```text
[概览] [准备] [会话] [决策]
```

## 概览

优先：

- Next Focus；
- next session；
- open commitments；
- open questions；
- recent decisions；
- last change。

## 准备

不是资料仓库，而是“下一场要带什么”。

Sections：

- Session Goal；
- Agenda；
- Brief；
- unresolved；
- related decisions；
- participants；
- Sources；
- Quick Notes；
- likely questions；
- Session Pack Preview。

## 会话

按时间列出 session + continue 状态。

## 决策

Decision chain：

```text
Android offline sync v2
AGREED · 10/05
来源：Design Review · 32:14
supersedes → offline sync v1
```

Proposal / Objection 可展开，但不抢主层。

# 7. Participant UI

Participants 不是“人物心理画像”。

Card 仅显示：

- 名称；
- role；
- organization；
- explicit priority；
- explicit concern；
- source；
- confidence。

Inferred 信息视觉上必须弱化并明确：

```text
临时推断 · 仅本场
```

# 8. Prepare Brief

一屏完成：

```text
这场要达成什么
上次发生了什么
还欠什么
还没决定什么
谁会参加
带入什么
我想提醒自己的 1–3 件事
```

AI 可以建议，但用户可以删改。

# 9. Preflight 2.0

```text
本次会话
PDIG · Android Architecture Review

目标
决定 conflict merge strategy

参与者
已知 5 人 · 1 人身份未确认

带入来源
项目材料 3
历史决策 2
Quick Notes 2

帮助方式
Balanced

Capture
转写：开启
音频保留：关闭
处理：Local / Cloud

Consent
[我已确认当前场景允许转写/记录]

External Actions
自动写入：关闭

[开始]
```

任何 consent 文案不得伪装法律判断。

# 10. Live Cockpit

默认 Compact：

```text
● Listening · PDIG

当前：offline migration

Recall
上周你承诺今天补 benchmark。
来源：Design Review · 09/24
```

只有一张 primary guidance。

Expanded：

```text
Recall
上周你承诺今天补 benchmark。

来源
Design Review · 09/24 · 31:22

[展开来源] [Pin] [忽略] [稍后]
```

Contribution Opportunity：

```text
值得补充
Q4 benchmark 已覆盖 10x data scale。
来源：Benchmark Note · confirmed

[展开来源] [Pin] [忽略]
```

Risk：

```text
注意
当前说法可能与 09/20 的 Android-first 决策不一致。

[看原决定] [忽略]
```

Question：

```text
还没明确
上线日期定了，但 rollback owner 还没有确定。

[提醒我问] [忽略]
```

# 11. Live Controls

允许：

- Pause suggestions；
- Quiet/Balanced/Active；
- Ask Chengzhu；
- Quick Notes；
- Pin；
- Hide transcript；
- stop session。

不允许满屏：

- 7 kind toggles；
- 10 metrics；
- full transcript by default；
- participant sentiment。

# 12. Manual Ask

Manual Ask 是 secondary drawer：

```text
问成竹…
“上次谁说负责 benchmark？”
“我们之前为什么拒绝方案 A？”
“这个问题怎么对客户解释？”
```

回答必须 source-aware。

# 13. Continue

第一屏：

```text
这场之后

改变了什么
Decision
✓ offline sync v2 — 待确认 / 已确认

Commitments
我 · migration benchmark · 10/08

Open Questions
rollback owner

Pins
2

下一步
下次先确认 rollback owner

[确认并写回] [逐项检查]
```

AI_EXTRACTED item 明确标“待确认”。

# 14. Decision Review

逐项 review：

```text
“采用 offline sync v2”
模型识别：AGREED
来源：Alex 42:15 “那我们就按 v2 做”
置信：高

[确认] [改为 Proposal] [修改] [拒绝]
```

这比一键“AI 生成决策”更重要。

# 15. Follow-up

可以生成：

- follow-up email draft；
- project update draft；
- issue/task draft；
- meeting recap。

但默认：

```text
Draft only
No auto-send
```

# 16. Profile-specific UI

## Project Sync

强调：

- Owed by me；
- waiting；
- blockers；
- status deltas。

## Design Review

强调：

- decision；
- proposal；
- objection；
- trade-off；
- unresolved risk。

## Presentation / Q&A

Live 增加：

- current section；
- time remaining；
- Q&A direct question。

不加 productivity metrics。

## 1:1

强调：

- last commitments；
- follow-up；
- user-authored relationship notes；
- sensitive privacy。

## Client Call

强调：

- client explicit priorities；
- promises；
- next checkpoint；
- risk。

## Negotiation

强调：

- proposal / counterproposal；
- constraints；
- unconfirmed terms；
- commitment caution。

# 17. Empty / Error / Fallback

Empty 必须给行动：

- 没有 Space → 创建第一个对话空间；
- 没有 history → 从一次临时会话开始；
- 没有 calendar → 手动开始；
- provider offline → 仅转写/本地 notes；
- ASR unavailable → manual notes；
- uncertain speaker → owner unknown，不猜。

# 18. Accessibility

必须：

- keyboard-only；
- visible focus；
- ARIA；
- reduced motion；
- font scaling；
- high contrast；
- screen reader；
- 390px Prepare/Continue；
- high DPI；
- no hover-only action。

快捷键建议：

```text
Ctrl+K   Command Palette
Ctrl+P   Pin
Ctrl+Shift+Space  Pause/Resume proactive guidance
Ctrl+Enter Manual Ask
```

# 19. UI Acceptance

每一页问：

- 用户下一步是否清楚？
- 是否把 transcript 当产品中心？
- 是否出现工程术语？
- 是否同时显示多个 AI 建议？
- source 是否可追溯？
- inferred 是否与 known 混淆？
- 是否出现 emotion / engagement score？
- 是否因“智能”增加了打扰？
- 是否保留 SILENT 可能？
