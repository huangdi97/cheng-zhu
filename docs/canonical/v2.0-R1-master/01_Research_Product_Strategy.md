# Chengzhu v2.0-R1 — Market / Product Research Synthesis
## 复核日期：2026-10-06

> 本文用于决定 Chengzhu v2 的产品边界，不表示复制竞品实现。优先引用官方产品与帮助文档。

# 1. 结论先行

2026 年会议 AI 已从“bot + transcript + summary”进入四条主线：

1. **botless/system-audio capture**；
2. **before / during / after continuity**；
3. **实时 coaching / live assist**；
4. **meeting memory → workflow / agent / MCP**。

因此 Chengzhu 不能把“实时建议”“跨会话记忆”“MCP”本身当作唯一差异。

真正有机会形成差异的是：

```text
Provenance-aware personal memory
×
Conversation-state reasoning
×
Contribution Opportunity
×
Stakeholder-aware expression
×
Explicit silence / interruption control
×
Decision/Commitment truth semantics
```

# 2. Granola

官方：
- https://www.granola.ai/
- https://www.granola.ai/integrations
- https://www.granola.ai/mcp

当前值得吸收：

- 不作为 visible meeting bot 加入通话；
- private-by-default；
- calendar brief；
- meeting memory；
- notes / action / follow-up；
- MCP 把会议历史开放给其它 AI；
- meeting context 流向 CRM / project / docs。

对 Chengzhu 的启发：

- Desktop sidecar 路线成立；
- Before Brief 必须成为一等体验；
- Conversation memory 应能被未来 agent/connector 使用；
- 但“搜索会议历史”已经商品化，不能成为唯一核心价值。

# 3. Hedy

官方：
- https://www.hedy.ai/
- https://www.hedy.ai/features/
- https://hedy.ai/help/automatic-suggestions/

Hedy 已经证明：

- live suggestions；
- talking point / blind spot / question；
- cross-session memory；
- session type；
- suggestion frequency；
- local/on-device processing；
- cross-session source-aware context。

尤其其 Automatic Suggestions 已采用“分析 → quality filtering → timing”的思路，并允许 Selective / Balanced / Frequent。

对 Chengzhu 的启发：

- v2 必须有统一 Guidance Arbiter；
- suggestion budget 是核心 UX，不是参数细节；
- proactive assistance 的竞争点已从“会不会生成”进入“值不值得打断”。

Chengzhu 必须进一步解决：

- provenance stronger than relevance；
- state semantics（proposed/agreed/committed）；
- contribution novelty；
- explicit silence；
- source visibility；
- social/interruption risk。

# 4. Otter Live Assist / Meeting Agents

官方：
- https://otter.ai/blog/otter-ai-introduces-live-assist-the-first-live-coaching-agent-for-every-call
- https://help.otter.ai/

Otter 在 2026 年明确进入 glanceable live coaching / meeting agents，并支持会议中语音命令创建 action item 等。

结论：

- “实时 glanceable coaching”已经进入主流竞争；
- Chengzhu 的 Fast Cue 资产仍有复用价值；
- v2 不应把 chatbot/agent 永久放在 Live 第一层；
- action execution 必须比竞品更强调用户确认与 provenance。

# 5. Microsoft Teams Facilitator

官方：
- https://learn.microsoft.com/MicrosoftTeams/facilitator-teams

Facilitator 强调：

- agenda；
- live notes；
- action-oriented meeting；
- Planner 等工作流集成；
- @Facilitator 交互。

结论：

- 大平台最终会把 notes/tasks 深度绑定办公套件；
- 独立产品不应该与 Microsoft/Google 正面比“组织级纪要”；
- Chengzhu 应聚焦“个人在对话中如何更好参与”，并保持跨平台。

# 6. Zoom AI Companion

官方：
- https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0057748

当前能力包括：

- catch me up；
- was my name mentioned；
- action items；
- “是否已经做了某个决定”类 meeting Q&A。

结论：

- “Ask meeting”是 baseline；
- v2 可以提供 manual Ask，但它不是首页与 Live hero；
- 真差异是无需用户主动问，就能在值得的时候发现 opportunity/risk。

# 7. Google Meet Gemini

官方：
- https://support.google.com/meet/answer/14754931

核心：

- take notes；
- summary so far；
- Calendar / Docs continuity；
- meeting recap。

结论：

- summary/catch-up 是平台能力；
- Chengzhu 不应围绕 transcript/summary 建产品 identity。

# 8. Notion AI Meeting Notes

官方：
- https://www.notion.com/help/ai-meeting-notes
- https://www.notion.com/releases/2026-03-12

值得吸收：

- desktop system audio；
- calendar binding；
- custom meeting instructions；
- action items；
- transcript retention；
- explicit consent controls；
- workspace-wide enforced consent。

尤其值得借鉴的是：consent / retention 是 UI 和 admin policy，不是藏在隐私条款里的文字。

Chengzhu 结论：

- Preflight 必须把 capture / consent / retention / processing mode 产品化；
- 不把“用户点击开始”视为第三方同意；
- 不自动共享；
- conversation delete 必须级联派生 memory/items。

# 9. Read AI

官方：
- https://www.read.ai/meeting-tools
- https://support.read.ai/hc/en-us/articles/33462537362579-Using-Read-s-live-meeting-dashboard

Read 的 live dashboard 提供：

- transcript；
- notes；
- metrics；
- participant / engagement / sentiment；
- speaking speed / filler。

Chengzhu 明确 **不吸收**：

- 情绪/engagement 推断作为产品权威；
- “read the room”分数；
- participant performance ranking。

原因：

- 高推断风险；
- 容易让用户过度相信模型对他人心理/情绪的判断；
- 与 Chengzhu 的 explicit/known provenance 原则冲突。

# 10. Fireflies / AskFred

官方：
- https://guide.fireflies.ai/articles/6556345325-askfred-ask-fred-questions-from-your-meetings-in-fireflies-and-get-answers

它证明 meeting-specific chat、meeting skills、自动会后 prompt 已经是成熟 baseline。

Chengzhu 可以保留 Ask，但必须 secondary。

# 11. 市场空位

到 2026-10，市场已经有：

```text
Capture      crowded
Transcript   crowded
Summary      crowded
Action items crowded
Meeting Q&A  crowded
Live coaching emerging/crowded
Memory       emerging
MCP          emerging
```

仍然没有被很好解决的组合问题：

> “在这个时刻，我有一个可靠来源的信息值得贡献吗？它之前有人说过吗？它是否和现有决定冲突？面对这个对象该怎么表达？如果没有足够价值，系统能否选择不打扰？”

因此 v2 不应该追求“更频繁的 AI”，而应该追求：

```text
fewer
better
source-backed
timely
socially-aware
guidance
```

# 12. 设计取舍

吸收：

- Granola：botless / Brief / private / integrations / MCP；
- Hedy：proactive suggestion + cross-session + suggestion frequency；
- Otter：glanceable live coaching；
- Teams：agenda / action continuity；
- Zoom/Gemini：catch-up / manual Q&A；
- Notion：consent / retention UI。

拒绝：

- transcript wall 作为主界面；
- summary 作为核心差异；
- sentiment / engagement as truth；
- invisible psychological profiling；
- auto-action without confirmation；
- 七种实时提示同时显示；
- 模型把“无人反对”升级成 AGREED；
- “AI productivity score”。

# 13. v2 positioning

一句话：

> **成竹不是替你参加会议，也不只是替你记会议；它帮助你在正确时刻调用正确的自己。**

英文：

> **Know what matters. Say what is yours. At the right moment.**
