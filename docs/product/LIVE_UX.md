# Live UX（Stage K）

> CURRENT · 对应 canonical 第 20、43 节。落点：`backend/api/assist/answer_worker.py:1584-1598`（guidance payload）、`frontend/src/hooks/useInterviewWS.ts`、`frontend/src/components/AnswerPanel.tsx` 等。
> 落地状态：cue-first 的**数据契约已实现**（后端 guidance payload）；前端 GuidanceViewModel 组件为当前落地边界（见第 4 节）。

## 1. 定位

不是所有问题都展示完整答案。目标（canonical 第 20 节）：**用户扫一眼就能继续说，而不是低头照稿念**。

## 2. cue-first 默认第一屏

canonical 第 20 节定义的第一屏结构：

```text
当前问题
为什么不用 fine-tuning？

核心思路
• 数据持续更新
• 可追溯
• 成本与迭代速度

我的证据
WenNian · RAG 决策

[展开]
```

| 区块 | 数据来源 | 说明 |
| --- | --- | --- |
| 当前问题 | `answer_done.question`（display_question） | 已识别/清洗后的问题 |
| 核心思路 | `guidance.core_ideas` ← `plan.structure`（前 6 项） | 该模式回答骨架的分段名（结论/项目事实/trade-off…） |
| 我的证据 | `guidance.evidence` ← `experience_grounding.evidence_excerpt[:160]` | 支撑个人事实的证据摘录 |
| [展开] | 渐进披露入口 | 展开完整答案与更多内容 |

cue-first 由 `AnswerPlan.surface = "cue_first"`（Stage H）声明；第一屏内容全部来自 Intelligence 层 payload，组件**不再**消费 raw prompt 响应（`answer_worker.py:1584-1585` 注释）。

## 3. GuidanceViewModel 数据流

后端已实现（`answer_worker.py:1584-1598`）：

```text
answer_worker 提交 commit
    ↓ _broadcast({"type": "answer_done", id, question, answer, think, model_name,
    ↓              first_token_ms, total_ms, guidance: {...}})
    ↓ guidance = {
    ↓     core_ideas:        plan.structure[:6]        # 核心思路（骨架分段名）
    ↓     evidence:          grounding.evidence_excerpt[:160]  # 我的证据
    ↓     mode:              plan.mode                 # 响应模式
    ↓     intent:            plan.intent[:3]           # 当前意图
    ↓     resolved_question: understanding.resolved_question  # 消解后问题
    ↓     state_context:     compact_state_context     # 面试状态承接块
    ↓ }
```

前端当前状态（`frontend/src/hooks/useInterviewWS.ts:180-196`）：

- `answer_done` → `finalizeAnswer(...)`（落答案区 + TTS 播报）已实现；
- `msg.guidance` 的消费（`buildGuidanceViewModel` → cue-first 组件）**尚未接线**——payload 已发出，前端读取为下一步落地项。

## 4. 展开内容（canonical 第 20 节 Guidance Surface）

支持的面（实现状态见标注）：

| Surface | 内容 | 状态 |
| --- | --- | --- |
| QUICK CUE | 一句话结论 + 关键词 | payload 已有（core_ideas/mode）；组件待接 |
| STRUCTURE | 回答骨架（分段名序列） | 同上 |
| EVIDENCE | 证据摘录 | 同上（evidence 字段） |
| FULL ANSWER | 完整流式回答 | ✅ AnswerPanel + answer_chunk 流式 |
| INTENT | 当前问题意图（面试官可能在验证什么，概率性措辞） | payload 已有（intent/state_context） |
| TRADEOFF / CAUTION / FOLLOW-UP | 取舍/边界提示/追问预测 | Deep Path 规划项；逐步落地 |

第一屏以外的完整答案由现有 `AnswerPanel` 流式渲染（`answer_chunk` → `appendAnswerChunk` → `finalizeAnswer`）。

## 5. 兼容性（canonical 第 43、44 节 UI 迁移原则）

- **Overlay（悬浮窗）**：现有 `InterviewOverlay` + 桌面端悬浮问答框保留；cue-first 组件落地后在同区域渲染第一屏，不新增独立窗口。
- **截图/识图**：`ScreenshotModePanel` + `WrittenExamTest` 链路保留；written exam 场景只注入 `state_context`（不注入 plan_prompt），第一屏兼容截图审题流程。
- **快捷键**：现有 `⌘⇧J / Ctrl+Shift+J` 折叠转录面板、Boss Key、托盘保留（canonical 第 43 节桌面策略）；UI 迁移不破坏既有快捷键契约。
- **视觉回归**：frontend 视觉基线（linux/darwin）继续覆盖；cue-first 组件接入时同步更新基线（canonical 第 44 节）。
- **Feature flag**：`intelligence_live_cue_v1`（默认 `True`）gate 后端 payload 与 TTFUG telemetry；关闭时前端走纯 `answer_done` 既有路径，功能不中断。

## 6. 现有第一屏（未接 payload 时的降级）

当前线上行为（README"面试主流程"）：左侧实时转写落字 + 自动识别问题，右侧答案区按模型配置流式生成；普通定义题默认短答，开放题自动切深度回答并承接上下文。cue-first 数据契约就绪后，第一屏切换为第 2 节结构，用户行为不变（听题 + 扫一眼继续说）。
