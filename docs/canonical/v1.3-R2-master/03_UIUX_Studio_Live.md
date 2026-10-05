# 39. UI/UX 总原则 3.0：把系统复杂度藏起来

v1.3 的 UI 不再追求“把每个模块都展示出来”，而追求：

> **对象稳定、下一动作清楚、Live 极简、复杂能力随上下文出现。**

十二条原则：

1. Goal 优先于功能模块；
2. 用户动作优先于系统状态；
3. Studio 信息完整，Live 信息克制；
4. Cue 优先，Essay 后置；
5. Next Focus 优先于评分；
6. Fact Inbox 优先于 Evidence database；
7. Material role 必须清楚；
8. 边缘动作进入 Command Palette / Context menu；
9. 同一对象不要在多个一级入口重复；
10. 每个页面最多一个主 CTA；
11. 状态只在一个地方展示，不让 loading 信号四处闪；
12. 所有自动化都必须允许用户知道“它做了什么、基于什么”。

---

# 40. 两种产品状态：Studio 与 Live Cockpit

## Studio

普通主窗口，用于：

- Goal；
- Prepare；
- Practice；
- Me；
- Library；
- History；
- Settings；
- Reflection。

Studio 是“慢思考、可编辑、可追溯”的空间。

## Live Cockpit

只有进入 Session 后出现。

Live 不显示复杂导航，主界面只保留：

```text
Question
Fast Cue
Source / Warning
```

Deep Answer、Transcript、Screen、References、Coach、Quick Notes 都是第二层。

用户不用点击“切换到 Cockpit”，而是从 Preflight 自动进入；结束 Session 自动回 Studio。

---

# 41. UI 视觉系统 3.0：Professional Workbench, not AI Dashboard

视觉目标：

- 专业桌面工作台；
- 安静；
- 高信息可读性；
- 不炫技；
- 不赛博；
- 不做“作弊神器”视觉；
- 不用大面积渐变制造 AI 感。

## 41.1 色彩

Light：

- Canvas `#F6F7F6`
- Surface `#FFFFFF`
- Surface Alt `#F0F3F1`
- Bamboo `#2F6B57`
- Ink Blue `#3F6475`
- Text `#1B2420`
- Secondary `#58625D`

正文级状态色：

- Direct Evidence `#256A4B`
- Supporting `#317566`
- Inferred `#86551F`
- No Evidence `#636A66`
- Risk `#AD4545`

状态永远配 icon + label，不只靠颜色。

## 41.2 Typography

- 中文：系统 UI Sans；
- 英文：Inter / system sans；
- Code：JetBrains Mono；
- Live Cue：15–16px 起；
- Overlay：12–24px 可调；
- 大标题少，减少 Dashboard 化。

## 41.3 Density

Studio：中等信息密度。

Live：高可扫读密度，但单屏元素更少。

Card 只在真正存在分组意义时使用；不要把每条信息都包成 Card。

## 41.4 Action Design

默认显示：

- 主动作；
- 一个次动作；
- 其余进入 `⋯`。

这样避免每行出现 5–7 个按钮。

---

# 42. 信息架构 v1.3：Goal-centered

正式一级导航：

```text
首页
求职目标
我的成竹
练习
资料库
历史
设置
```

右上固定：

```text
[上场]
```

可选全局：

```text
Search / Ctrl+K
```

说明：

- **上场** 是动作，不是一级导航；
- **准备** 属于 Goal；
- **复盘** 属于 Session / History / Goal；
- **岗位 / Job Tracker** 统一为“求职目标”；
- **Knowledge / Quick Notes / Question Bank** 统一进入资料库，但按角色分区；
- “我的成竹”只管理 Person，不承载 Job。

---

# 43. 首页：Action Home，不做指标 Dashboard

首页只回答三件事：

1. 下一场是什么？
2. 当前最值得做什么？
3. 有没有 blocker？

Wireframe：

```text
┌──────────────────────────────────────────────────────────┐
│ 成竹                         Ctrl+K               [上场] │
├─────────────┬────────────────────────────────────────────┤
│ 首页        │ 下一场                                     │
│ 求职目标    │ MindRank · 技术二面 · 明天 14:00           │
│ 我的成竹    │ [继续准备] [开始演练] [Preflight]           │
│ 练习        ├────────────────────────────────────────────┤
│ 资料库      │ Next Focus                                 │
│ 历史        │ Redis Cluster：有知识，无生产经历来源       │
│ 设置        │ [准备这个问题]                             │
│             ├────────────────────────────────────────────┤
│             │ 需要你处理                                 │
│             │ 3 个事实待确认 · 1 个 Story 缺口           │
│             ├────────────────────────────────────────────┤
│             │ 最近 Session                               │
│             │ MindRank 技术一面 · System Design depth    │
└─────────────┴────────────────────────────────────────────┘
```

不默认放：

- 大量图表；
- 准备度百分比；
- “AI 分析指数”；
- 无行动意义的累计数字。

---

# 44. 我的成竹：从“数据管理”升级为 Person Workspace

Tabs：

```text
概览 | 简历 | 项目 | 待确认 | Stories | Skills | 我的表达
```

`待确认` 是 Fact Inbox，不默认显示底层 Graph 术语。

## Fact Inbox

例：

```text
需要你确认 · 4

WenNian
“我负责完整 RAG 架构设计”

材料目前能证明：参与设计
不能证明：主导全部架构

你实际情况是？
[我主导] [我参与] [修改表述]
```

确认之后才进入稳定 Personal Context。

高级用户可在 detail drawer 查看：

- source excerpt；
- provenance status；
- assertion status；
- session history；
- linked Story；
- linked Skill。

---

# 45. Stories UI：从卡片收藏升级为真实故事资产

Stories 页面按能力标签浏览：

```text
Ownership
Conflict
Failure
Leadership
Ambiguity
Collaboration
Difficult Problem
```

缺失状态比空白页更重要：

```text
你还没有“失败与反思”故事

很多 Hiring Manager 会追问失败、复盘和改变。
[开始 5 分钟 Story Builder]
```

Story detail：

- Situation；
- Challenge；
- Action；
- Result；
- Reflection；
- linked sources；
- related questions；
- last used session；
- `Practice this story`。

---

# 46. 求职目标 UI：Goal 是唯一岗位中心

列表页面不是 Job Tracker 看板优先，而是 Goal list：

```text
Active
MindRank · AIDD Agent Engineer       技术二面 · 明天
德睿智药 · AI Product               待安排
康龙化成 · AI 应用实施              已完成
```

每个 Goal 进入 Goal Room：

```text
概览 | 准备 | 面试 | Offer
```

Applications status 可以是 Goal metadata，不需要先让产品变成 ATS。

Goal detail 中 Resume/JD/Materials 都明确来源；不让用户在另一个“岗位”页面重复维护一份。

---

# 47. Goal Prepare Workspace

Prepare 页面不是“题库瀑布流”，而是行动顺序。

```text
Next Focus
Gap Map
Attack Surface
Question Graph
Skills / Stories
Materials
InterviewPack Preview
```

默认首屏：

```text
Next Focus
──────────
1. Redis Cluster：事实边界
2. System Design：scale reasoning
3. Ownership Story：待补
```

点一个 Focus，进入单任务页面，避免同时展示全部图谱。

Question Graph 默认折叠，只展开当前 Focus 的分支。

---

# 48. Practice UI 3.0

Practice 分两步：Setup → Session。

## Setup

```text
Practice · MindRank

轮次        技术一面
面试官风格  强追问
难度        标准
题目来源    Goal + 最近弱点

[开始]
```

高级设置折叠：

- Question Bank；
- Language；
- Coding Language；
- Duration；
- Human Coach；
- Delivery analysis。

## Session

主界面保持对话感，不在用户回答前显示参考答案。

回答结束后只给极短反馈：

```text
✓ trade-off 清楚
! ownership 不够具体

下一问：那你个人真正负责了哪部分？
```

完整 Content / Delivery feedback 在 Session 后显示。

---

# 49. Live Preflight 3.0：告诉用户“这一场到底带进去什么”

Preflight 不显示工程版本号为主，而显示可理解来源。

```text
上场前检查

Goal
MindRank · AIDD Agent Engineer

个人上下文
郝磊-简历.pdf                   [来自 我的成竹]
3 个 Skill Cards                [Goal 默认]
2 个 Stories                    [Goal 默认]

Knowledge
AIDD Notes                      [Goal 默认]
RAG Notes                       [本场覆盖]

Quick Notes
MindRank 二面                   [本场]

回答
中文 · 技术词保留英文           [我的表达]
Python                          [Goal 默认]

AI Assistance
Allowed                         [本场设置]

Human Coach
Practice only / Off             [系统默认]

Share Privacy
Off                             [本场设置]

音频
✓ 麦克风
✓ 系统音频
✓ STT

[冻结并开始]
```

技术上的 Candidate v7 / Pack hash 可放在 Diagnostics，不应成为普通用户主要信息。

---

# 50. Live Main UI 3.0：三层首屏

首屏固定三层：

```text
1. Question
2. Cue
3. Source / Warning
```

Wireframe：

```text
● Cue ready

为什么不用 fine-tuning？
────────────────────────────
• 知识更新频繁，RAG 不需要重新训练
• 检索来源可追溯
• 结合 WenNian 的文档更新讲
────────────────────────────
你的经历
✓ WenNian：RAG + Agent

注意
! 没有 fine-tuning 生产经历

[展开完整回答]
```

系统状态只有一处：

```text
Listening
Question detected
Preparing
Cue ready
Answering
Reconnecting
```

不要同时出现 ASR / retrieval / LLM / compiler 四套 loading。

---

# 51. Overlay 3.0：Dock × Interaction × Size

Overlay 不是永久大浮窗。

用户设置三个维度：

```text
Dock
Top / Left / Right / Free

Interaction
Passive / Interactive

Size
Compact / Standard / Focus
```

## Idle Compact

```text
● Listening · MindRank
```

## Cue arrives

```text
┌──────────────────────────────┐
│ 为什么不用 fine-tuning？    │
│                              │
│ • 更新快                     │
│ • 可追溯                     │
│ • WenNian 可讲               │
│                              │
│ ! 无生产 fine-tune 经历      │
└──────────────────────────────┘
```

## Focus

用于：

- Full answer；
- Coding；
- System Design；
- OOD；
- References。

问题结束后自动回 Compact，可由用户关闭自动收起。

Main UI 与 Overlay 必须共用同一 GuidanceViewModel。

---

# 52. Share Privacy UI

继续遵守 v1.2-R2：默认 OFF，定义为私人内容保护，不承诺不可检测。

设置文案：

```text
屏幕共享保护
[ OFF ]

减少 Chengzhu 私人窗口在受支持的屏幕共享/录制路径中
意外出现。不同系统与捕获方式可能不同，这不是安全保证。
```

Preflight 必须显示本场实际值。

---

# 53. Human Coach UI：Practice-first

Human Coach 默认出现在 Practice Setup，而不是 Live 首页主入口。

Practice：

```text
Human Coach
[邀请]
```

正式 Live：

只有 Human Assistance Policy 允许时才显示。

Candidate 侧来源分离：

```text
AI
• ...

Coach
• ...
```

Coach Suggestion 永远不是 Evidence。

---

# 54. Reflection UI 3.0：先给下一步，再给完整分析

默认 Summary：

```text
这场之后

下一步
System Design scale reasoning
[开始练习]

做得好的
RAG trade-off 讲得具体
“你的真实原话……”

需要改进
多次使用“我们”，个人职责不清
“你的真实原话……”

待确认事实
Redis Cluster
[确认] [口误]

值得建立的 Story
线上事故恢复
[创建 Story]

[查看完整逐轮分析]
```

完整 Timeline 才展示：

- raw question；
- resolved question；
- candidate actual speech；
- Fast Cue；
- Deep Answer；
- Coach Cue；
- selected context；
- reference fragment；
- assertion event；
- latency。

Reflection 输出直接回 Goal 的 Next Focus。

---

# 55. Settings 3.0：可搜索、默认值与本场覆盖分离

分组：

```text
General
Models
Speech & Audio
Language
Live & Overlay
Privacy
Knowledge
Shortcuts
Data & Export
Diagnostics
```

支持：

```text
Ctrl+F 搜设置
Ctrl+, 打开设置
```

每个可被 Session 覆盖的设置标记：

```text
Account default
Goal default
This session
```

避免用户不知道修改会影响本场、后续还是全局。

---

# 56. Empty / Loading / Processing / Error State 3.0

状态设计必须按对象语义，而不是通用 Spinner。

## Material

```text
Processing
Ready
Failed
Replacing
```

替换文件时：上一版保持可用，直到新版 Ready；不要让当前 Goal 突然失去材料。

## Fast Cue

- Preparing；
- Cue unavailable, deep answer continues；
- Provider fallback；
- Offline knowledge only。

## Goal

- No JD；
- No Resume；
- No upcoming interview；
- Archived。

## Human Coach

- waiting；
- connected；
- reconnecting；
- permission changed；
- revoked。

所有 Error 都必须有下一步动作。

---

# 57. Accessibility、Keyboard 与 Desktop Interaction

必须支持：

- 全键盘导航；
- Focus ring；
- ARIA；
- Screen reader；
- Reduced motion；
- Font scaling；
- High contrast；
- Light/Dark；
- 390px；
- 小 Overlay；
- 关键动作不依赖 hover。

核心快捷键建议：

```text
Ctrl+K       Command Palette
Ctrl+,       Settings
Ctrl+P       Pin Moment（Session 中）
Ctrl+N       Quick Notes（Session 中）
Ctrl+B       Show/Hide Overlay（沿用现有习惯时）
Esc          Close transient UI
```

快捷键以真实仓库冲突审计为准，不能硬覆盖现有用户绑定。

---
