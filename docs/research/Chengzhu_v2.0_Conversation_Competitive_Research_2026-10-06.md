# Chengzhu v2.0 Conversation Competitive Research
## 2026-10-06｜从“会议纪要”到“会中执行智能”的竞争面

**目的**：为 v2.0-R1 Personal Conversation Intelligence 提供 2026-10-06 时点的外部产品事实与设计含义。  
**证据边界**：只记录公开官方页面能支持的产品能力；不把营销口径当真实效果，不据此宣称 Chengzhu 的真实用户价值已验证。

---

## 1. 结论先行

2026 年的竞争面已经明显从“转写 + 会后摘要”移动到“会中辅助 + 连续上下文 + action”。

因此 Chengzhu 不应把以下能力当核心差异：

- transcript；
- summary；
- action items；
- catch me up；
- meeting Q&A；
- agenda；
- task draft / sync；
- 单纯的实时提示卡。

这些能力正在成为会议 AI 的基础设施或相邻能力。

Chengzhu v2 的产品差异继续冻结为：

1. **Personal continuity**：围绕“这个人自己的长期事实、项目、关系、承诺和目标”跨多场延续，而不是团队会议档案本身；
2. **Provenance-aware truth**：Proposal / Decision / Commitment / Deadline / Open Question 的状态和来源分开，不把 transcript 或 model summary 直接升级成 truth；
3. **Contribution Opportunity**：不是“检索到内容就弹”，而是判断现在是否值得说；
4. **SILENT / Interruption Control**：不打断本身是一等动作；
5. **Stakeholder-aware Expression**：对不同受众调整表达结构，但不改写事实；
6. **Private sidecar**：跨 Zoom / Meet / Teams / 腾讯会议 / 飞书等会议软件，不要求进入对方会议空间；
7. **Fail-closed privacy**：UI 中选择 Local / Private / No write-back 必须对应真实 runtime 数据路径；无法证明就阻断，而不是保留假开关。

---

## 2. Otter.ai Live Assist：实时 coaching 已经进入主流竞争区

官方 2026-07-21 发布页面：

https://otter.ai/blog/otter-ai-introduces-live-assist-the-first-live-coaching-agent-for-every-call

公开能力包括：

- 在任何 call 上提供 glanceable、in-the-moment guidance；
- tip card 可提示要问的问题、要覆盖的 point、talk track；
- 可通过 Agent Builder 用 playbook、SOP、过去会议、关键资源做 grounding；
- 可跟踪目标是否完成；
- 覆盖 sales discovery、objection handling、technical pre-sales、renewal/QBR 等场景。

### 对 Chengzhu 的含义

**“实时提示卡”本身已经不能构成 moat。**

Chengzhu 必须把差异放在：
- 来源是否允许用于 Guidance；
- 同义内容是否已经说过；
- 当前是否应该保持 SILENT；
- 当前建议是否来自用户自己的长期可信上下文；
- 对方角色/明确 concern 是否影响表达；
- Direct Question / Critical Risk 是否能抢占旧 Opportunity；
- 一场结束后的 Decision / Commitment 是否进入下一场，而不是只进入 searchable transcript。

---

## 3. Microsoft Teams Facilitator：agenda / timer / tasks 正在成为会议执行基础层

官方页面：

https://support.microsoft.com/en-us/teams/copilot/facilitator-in-microsoft-teams-meetings

公开能力包括：

- real-time AI notes；
- key decisions 与 open questions；
- meeting chat 问答；
- 从 meeting invite / notes 读取 agenda；
- 没有 agenda 时提示定义 meeting goal；
- agenda timer、topic time allocation、超时提醒；
- meeting task 管理，并可与 Planner 同步。

### 对 Chengzhu 的含义

Agenda / pacing / task tracking 可以作为 **secondary execution surface**，但不应抢占 Chengzhu 的 primary Live Guidance。

建议产品层级：

```text
Primary:
Current Topic
→ One Guidance
→ Source / Warning

Secondary:
Agenda / Timebox
Open Threads
Notes / Transcript
Pins
```

即：Teams 更偏“让整场会议运转”，Chengzhu 更偏“帮助这个用户在这场对话里做对下一步表达与决策”。

---

## 4. Granola：botless + 私有默认验证了 sidecar 路线，但“本地捕获”不能偷换成“本地处理”

官方页面：

https://www.granola.ai/ai-meeting-assistant

公开定位包括：

- no bot joins；
- meeting audio 在设备上捕获；
- 用户笔记与 meeting audio 结合；
- notes private by default；
- before / during / after；
- 可跨过去 meeting 查询；
- 会后 draft follow-up、连接既有工具。

### 对 Chengzhu 的含义

Chengzhu 的 Desktop Sidecar / local-first 是合理方向，但产品文案必须进一步拆开：

```text
Capture locality
!=
STT locality
!=
LLM processing locality
!=
Retention locality
!=
Write-back locality
```

因此 Session Preflight 必须显示 **resolved data path**。  
“Local” 不是一个装饰性 select value；如果共享 STT 有远程路径，Conversation 必须 fail-closed。

---

## 5. Zoom AI Companion：in-meeting Q&A / catch-up 已经是基础能力

官方页面：

https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0057748

公开能力包括：

- Catch me up；
- Was my name mentioned；
- What are the action items；
- 自定义会议问题，例如是否已经同意日期、是否形成命名决策。

### 对 Chengzhu 的含义

Manual Ask / source-aware Recall 必须存在，但不能把它当核心差异。  
真正的差异是：

- 只查**允许进入本场的来源**；
- 没有足够可信来源时明确回答“没有找到”，而不是补全；
- 结构化 truth state 可以跨场继续；
- 用户无需把会议平台变成组织级知识库才能获得个人 continuity。

---

## 6. Google Meet / Gemini：notes + action items 已高度商品化

官方页面：

https://workspace.google.com/solutions/ai/ai-note-taking/

公开能力包括：

- real-time note taking；
- action items；
- 会后自动组织到 Google Doc。

### 对 Chengzhu 的含义

Continue 不应以 summary / transcript 为第一屏。  
第一屏继续冻结为：

- What changed；
- Decisions；
- Commitments；
- Open Questions；
- Pins；
- Follow-up；
- Next Focus。

Transcript / summary 是第二层。

---

## 7. 竞争矩阵

| 能力 | Otter Live Assist | Teams Facilitator | Granola | Zoom AI Companion | Chengzhu v2 目标 |
|---|---|---|---|---|---|
| Transcript / notes | 强 | 强 | 强 | 强 | 基础能力 |
| In-meeting Q&A | 有 | 有 | 有 | 有 | Manual Ask，必须 source-aware |
| Real-time coaching | 强 | 部分 | 非核心 | 部分 | 强，但由 Arbiter 控制 |
| Agenda / timing | 部分 | 强 | 非核心 | 非核心 | Secondary surface |
| Cross-session memory | 有 | 组织生态 | 有 | 平台内 | Personal continuity |
| Provenance-aware state | 非核心公开卖点 | 部分 | 非核心 | 非核心 | 核心 |
| Explicit SILENT | 非公开核心 | 非公开核心 | 非公开核心 | 非公开核心 | 核心 |
| Stakeholder-aware expression | 有场景化 | 有 | 部分 | 非核心 | 核心，禁止隐藏心理推断 |
| Botless sidecar | Desktop 可跨平台 | 否 | 强 | 平台内 | 强 |
| Fail-closed local path | 未作为核心公开层 | 组织策略 | 强调本机捕获 | 平台策略 | 核心产品面 |
| Reviewed write-back | 有 integration | 有 task sync | 有 integrations | 有平台动作 | 先 Draft / Review，再 connector |

---

## 8. 直接进入 v2 设计的变更

本轮研究不改变 v2 核心定位，但增加以下冻结项：

### 8.1 Runtime Data Path 是 Preflight 一等字段

必须分清：
- capture；
- STT；
- LLM / inference；
- retention；
- external write-back。

如果用户选择的 policy 与实际 runtime 不一致：
- 不降级成 warning；
- 不自动切换到远程；
- **阻止开始**。

### 8.2 Agenda / pacing 只做 secondary execution surface

不把产品变成 Teams Facilitator 克隆。  
Live Primary 始终只有一个最高价值 Guidance。

### 8.3 “Real-time card” 不再写成差异本身

差异写成：

```text
right personal context
+ right provenance
+ right stakeholder
+ right moment
+ permission to stay silent
```

### 8.4 Connector / write-back 继续 Review-first

即使竞品已经自动同步 Planner / CRM，Chengzhu 在个人产品阶段仍默认：

```text
No auto-send
No auto-create external task
No silent connector write
Draft → Review → Explicit Action
```

### 8.5 Botless sidecar 必须把 participant transparency 做成一等 Preflight 状态

Granola 的公开透明性设计明确承认 botless/local app 的一个 trade-off：不像 meeting bot 那样天然出现在参会列表，用户需要其他机制让参与者知道正在转写。Granola 提供 verbal heads-up、meeting chat notice、watermark 等路径。

官方来源：

- https://www.granola.ai/transparency
- https://www.granola.ai/blog/why-granola-doesnt-use-a-bot

Chengzhu 当前没有 Conversation chat connector / watermark runtime，因此不应伪装“已自动通知”。v2 冻结：

```text
participant consent status
!=
participant transparency plan
!=
system verified consent
```

Preflight 需要记录用户报告的 transparency plan：
- verbal heads-up；
- chat notice；
- already notified；
- not applicable；
- not recorded。

没有记录时：
- 给 warning；
- 不替用户做法律判断；
- 不把 warning 偷换成“其他参与者已同意”。

### 8.5 Evaluation 不能用 adoption 偷换 precision

本地可直接观测：
- source attribution coverage；
- guidance adoption；
- dismissal；
- suppression；
- duplicate suppression；
- review queue；
- approved draft rate。

必须真人标注：
- Recall Precision；
- Opportunity Precision；
- Interruption Regret；
- Useful Silence；
- real cross-session value；
- real cognitive load。

---

## 9. 当前证据边界

本研究可以支持：

```text
COMPETITIVE_RESEARCH_REFRESHED = TRUE
DESIGN_DIRECTION_SUPPORTED = TRUE
```

不能支持：

```text
CHENGZHU_BETTER_THAN_COMPETITORS = TRUE
REAL_USER_VALUE_PROVEN = TRUE
PMF_PROVEN = TRUE
```

后两类只能来自真实用户与真实对话评测。
