---
name: 成竹 Cheng Zhu
description: 本地优先的面试学习工具台：实时转录 + AI 回答 + 准备/复盘闭环，语义化多主题的 Operate 界面
colors:
  primary: "rgb(0 92 197)"
  secondary: "rgb(16 124 16)"
  tertiary: "rgb(184 134 11)"
  danger: "rgb(196 43 28)"
  neutral-bg: "rgb(255 255 255)"
  neutral-surface: "rgb(243 243 243)"
  neutral-elevated: "rgb(255 255 255)"
  neutral-border: "rgb(207 214 223)"
  text-primary: "rgb(30 30 30)"
  text-secondary: "rgb(80 80 80)"
  text-muted: "rgb(88 88 88)"
typography:
  display:
    fontFamily: "'Plus Jakarta Sans', 'Noto Sans SC', system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  body:
    fontFamily: "'Plus Jakarta Sans', 'Noto Sans SC', system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  caption:
    fontFamily: "'Plus Jakarta Sans', 'Noto Sans SC', system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "normal"
  mono:
    fontFamily: "'JetBrains Mono', 'Cascadia Code', 'Fira Code', monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  sm: "4px"
  md: "6px"
  lg: "8px"
  xl: "12px"
  xxl: "16px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  xxl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.neutral-bg}"
    typography: "{typography.caption}"
    rounded: "{rounded.md}"
    padding: "10px 20px"
  button-icon:
    backgroundColor: "transparent"
    textColor: "{colors.text-muted}"
    rounded: "{rounded.lg}"
    size: "32px"
  card:
    backgroundColor: "{colors.neutral-surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.lg}"
    padding: "20px"
  chip:
    backgroundColor: "{colors.neutral-bg}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.full}"
    padding: "2px 8px"
  input:
    backgroundColor: "{colors.neutral-surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: "8px 10px"
  switch:
    backgroundColor: "{colors.neutral-border}"
    rounded: "{rounded.full}"
    width: "36px"
    height: "20px"
---

# 成竹 Cheng Zhu — Design System

## Overview

**The Interview Workbench.** 一个「操作型（Operate）」面试学习工具台：用户在真实/模拟面试的高压、低注意力场景下操作它，界面必须克制、精确、低干扰——信息层级服务于「听题 → 转写 → 出答案」这条主链，而非装饰。

世界由三层构成：

1. **语义化多主题**：6 套主题（Light+/Dark+/Dark 高对比/Nord/Editorial Glass/Solarized Dark）共享同一套 `--c-*` 语义令牌。颜色按角色（背景/文本/强调）而非色相命名，换主题不改组件。
2. **玻璃拟态悬浮层**：popover、悬浮窗、下拉用半透明玻璃面（`backdrop-blur` + 细边框 + 大投影）从内容面浮起，与卡片/面板的「实色平面」分层。
3. **结果先行的节奏**：答案区、转录区、备忘区是三个并行的可读平面；实时状态用微光点、脉冲、电平条这类「低音量」动效表达，不抢注意力。

主题化机制是核心不变量：**任何新组件必须只用语义令牌（`bg-primary` / `text-secondary` / `accent-blue` 等），禁止硬编码色值**，否则多主题会立刻坏掉。

## Colors

颜色全部由 `frontend/src/index.css` 的 `--c-*` 语义令牌定义（Tailwind 通过 `rgb(var(--c-x) / <alpha>)` 映射），每套主题覆盖同一组变量。下方为默认浅色（Light+）的规范值；深色主题示例见后。

| 角色 | Light+ 规范值 | 用途 |
| --- | --- | --- |
| 强调 Primary（蓝） | `rgb(0 92 197)` | 主操作、当前激活、链接、焦点环 |
| 强调 Secondary（绿） | `rgb(16 124 16)` | 成功、录音中、「你自己」口述、在线状态 |
| 强调 Tertiary（琥珀） | `rgb(184 134 11)` | 注意/建议/待处理、教练建议卡 |
| 危险 Danger（红） | `rgb(196 43 28)` | 错误、删除、危险操作 |
| 背景 Neutral-bg | `rgb(255 255 255)` | 应用主背景 |
| 表面 Neutral-surface | `rgb(243 243 243)` | 卡片、面板次级背景 |
| 浮起 Neutral-elevated | `rgb(255 255 255)` | 浮层/强调卡片 |
| 边框 Neutral-border | `rgb(207 214 223)` | 分隔线、输入边框（弱） |
| 文本主 Text-primary | `rgb(30 30 30)` | 正文、标题 |
| 文本次 Text-secondary | `rgb(80 80 80)` | 说明、次要信息 |
| 文本弱 Text-muted | `rgb(88 88 88)` | 提示、时间戳、角标（对比度 ~4.6:1） |

**The Semantic Accent Rule.** 蓝=行动、绿=成功/录制、琥珀=注意/建议、红=错误/删除。新状态颜色必须先从这四色里取，不新增色相；需要「同义分层」时用同色相的不同透明度（`/10` `/15` `/25`）而非换色。

**The Muted Floor Rule.** 次要文本不低于 `text-muted` 的对比度（浅色主题 ~4.6:1，接近 WCAG AA）。禁止用比 `text-muted` 更浅的文本承载信息。

**The Status Gradient Rule.** 分数/风险梯度一律映射到语义强调色的透明度分层：好=绿、中=琥珀、差=红（如评分条 `accent-green / accent-amber / accent-red`）。禁止用 Tailwind 默认色相（emerald/red/amber 等）表达状态。

**The Kanban Stage Exception.** 求职看板的阶段色板（`job-tracker/stageConfig.tsx`）是有意保留的多色相数据可视化调色板，用于区分不同投递阶段（蓝/紫/绿/青/琥珀等），属于有意的主题无关例外；其余界面一律走语义令牌。

**The Overlay HUD Rule.** 悬浮窗（InterviewOverlay）是浮于第三方会议软件之上的 HUD，**有意不跟随主界面主题**（浅色玻璃，保证在任意会议软件上可读），其颜色统一收口到 `--c-ov-*` 令牌（surface/text/muted/border/accent/pass/fail/unknown）。悬浮窗内的状态语义与主界面一致：PASS=绿、FAIL=红、未知=灰。

深色主题（Dark+）关键值：背景 `rgb(15 15 18)`、文本主 `rgb(226 232 240)`、强调蓝 `rgb(99 102 241)`、强调绿 `rgb(34 197 94)`、表面 `rgb(26 26 36)`。Nord / Editorial Glass / Solarized Dark 覆盖同一角色集，仅换色相方向。

## Typography

**The Two-Face Rule.** 界面只用两族字体：正文字族 `Plus Jakarta Sans + Noto Sans SC`（拉丁与中文混排，标题/正文/说明同一族按字重分级），等宽字族 `JetBrains Mono`（数字、Token、时间戳、代码、转写序号）。不引入第三族。

层级（均为 Tailwind 工具类对应的实际字号）：

- **Display（标题）**：20px / 700，用于页面标题、卡片标题；大标题（复盘详情页）到 24–28px。
- **Body（正文）**：14px / 400，行高 1.6，用于转录、答案正文、说明。
- **Caption（小字）**：12px / 500，用于按钮、chip、标签、表格；密集信息区可到 10–11px（角标、时间戳、指标）。
- **Mono（等宽）**：12px，用于 Token 用量、首字/总耗时、转写序号、时间戳、代码块。

中文与英文混排默认由 Noto Sans SC 兜底；数字、指标、耗时一律用等宽 + `tabular-nums`，保证流式更新时数字不跳动。

## Layout

**The Two-Pane Interview Rule.** 实时辅助主工作区固定为「左转录 | 右答案」双栏（可拖分隔条 24%–62%，双击复位 32%），可选右侧 288px 备忘常驻栏。三栏是并列的「读」平面，不互相叠压；移动端退化为底部 tab 切换（实时转录 / AI 答案）。

- 顶部为应用壳 header：模块 tab + 右侧工具按钮（工作台/会场/折叠/知识库/设置/窗口控制），图标按钮统一 32px。
- 内容区用 `max-w` 居中容器（首页 5xl、详情 7xl、设置面板自适应）。
- 桌面优先；折叠转录栏、备忘栏在 `md` 以下隐藏，靠 tab/工作台访问。
- 弹层（popover/下拉）统一从触发元素右下浮出（`right-0 top-full`），不遮挡触发点。

## Elevation & Depth

**The Glass Float Rule.** 悬浮层（popover、工作台、会场设置、下拉）用玻璃面浮起：半透明表面 `backdrop-blur` + 细边框（`border-bg-hover/50`）+ 大投影（`shadow-2xl shadow-black/20`）+ 顶部 1px 渐变 hairline（`via-accent-blue/30`）。实体面板/卡片用实色平面（`bg-secondary/60` + 细边框），与玻璃层形成两级深度，不额外加投影。

**The Focus Ring Rule.** 键盘焦点用 2px 语义色外环（`outline: 2px solid rgb(var(--c-accent-blue) / 0.55)` + offset 2px），全局 `:focus-visible` 统一；hover 用背景/边框微变表达（`hover:bg-bg-tertiary/60`），不依赖位移。

## Shapes

**The Soft Corner Rule.** 用 Tailwind 原生圆角阶梯表达层级：输入/小控件 6px（`rounded-md`）、按钮/输入 8px（`rounded-lg`）、卡片/弹层 12px（`rounded-xl`）、大卡片/首页模块 16px（`rounded-2xl`）、chip/徽标/开关 全圆（`rounded-full`）。层级越高圆角越大；矩形（0px）仅用于像素级工具面（框选遮罩、分割条）。

## Components

- **Primary Button**：蓝底白字（`bg-accent-blue text-white`）、8px 圆角、12px 行高、hover 提亮（`brightness-110`）、disabled 降透明度。用于主行动（开始面试、截图审题、保存）。
- **Icon Button**：32×32 透明底、圆角 12px、muted 图标色；hover 背景+边框微变；必须带 `aria-label`/`title`。用于 header 工具与行内操作。
- **Card（模块卡/答案卡）**：`bg-secondary/60` + 细边框 + 12px 圆角；hover 边框转强调色（首页模块卡）或保持克制（答案卡）。
- **Chip / Badge**：全圆小标签，语义色 10–12% 透明度底 + 25–35% 边框 + 语义色文字，用于角色（面试官/你自己）、状态、模型名、来源。
- **Switch（Toggle）**：36×20 圆角轨道 + 白圆钮；开启=语义绿（带微光），关闭=边框灰。用于 Think/自动回答/纠错等开关。
- **Input / Textarea / Select**：`bg-tertiary` 实底 + 细边框 + 8px 圆角；focus 边框转语义蓝 + 2px 柔光环。设置面板大量使用。
- **Popover（玻璃浮层）**：见 Elevation & Depth；右上角 hairline、头部标题 + 关闭钮、底部可选操作区（如「高级参数」跳转）。
- **Panel（转录/备忘）**：内部滚动区 + 顶部条（标题 + 状态）；转录项带角色 chip 与时间戳，流式 partial 用语义色底 + 脉冲点。
- **Status/Toast**：toast 右上浮出（info/success/warn/error 四态），`aria-live` 通知状态变化。

## Do's and Don'ts

### Do:
- **Do** 只用语义令牌（`--c-*` / Tailwind 语义类）；新组件先映射到现有令牌，缺令牌才加变量。
- **Do** 让主行动一次可见：一个界面一个主按钮，蓝色唯一。
- **Do** 用透明度分层同色相（`/10` `/15` `/25`），不用新色相表达同义状态。
- **Do** 给所有纯图标按钮补 `aria-label`，保证键盘焦点环可见。
- **Do** 数字/耗时/指标用等宽字体 + `tabular-nums`。

### Don't:
- **Don't** 硬编码色值或新增色相表达状态（破坏多主题）。
- **Don't** 在内容平面（面板/卡片）上加投影冒充浮层；浮层才用玻璃+投影。
- **Don't** 用 `text-muted` 更浅的对比度承载信息（浅色主题下限 88/88/88）。
- **Don't** 引入第三族字体或新的圆角体系。
- **Don't** 让弹层遮挡触发点；统一从触发元素右下浮出。
