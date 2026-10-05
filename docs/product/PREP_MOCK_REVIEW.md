# Goal Prepare / Practice / Reflection

> **CURRENT · v1.4.x**
>
> v1.2 的 PrepSpace / Job Workspace 仍作为兼容数据与底层能力存在，但不再是当前产品信息架构。
> 当前产品围绕 **Goal** 组织。

## 1. 产品闭环

```text
Goal
→ Next Focus
→ Prepare
→ Practice
→ Preflight
→ Live
→ Reflection
→ Next Focus
```

核心原则：

> 用户不需要理解系统有多少模块，只需要知道这个岗位下一步最值得做什么。

---

## 2. Goal

一个 Goal = 一个具体的公司 × 岗位长期工作空间。

包含：

- company；
- role；
- JD；
- stage；
- interview round / next interview；
- materials；
- Quick Notes；
- Question Banks；
- sessions；
- Reflection；
- Offer；
- Next Focus。

Goal 不是 PrepSpace 的 UI 别名。旧 PrepSpace 只作为兼容 / legacy link 保留。

---

## 3. Goal Room

Goal Room 四个主视图：

```text
概览
准备
面试
Offer
```

### 概览

优先显示：

- Next Focus；
- 下一场；
- What We Know；
- Recent Sessions；
- Progress Trends。

禁止虚假：

- readiness score；
- offer probability；
- candidate percentile。

### 准备

面向用户呈现：

- 准备缺口；
- 最可能被深挖的经历；
- 可能追问；
- Stories；
- 本场带入内容；
- Pack preview。

底层可以复用 Alignment / Gap Map / Question Graph，但 UI 不要求用户理解这些内部术语。

---

## 4. Next Focus

Next Focus 每个 Goal 只保持少量高优先级动作。

来源：

1. 用户显式选择；
2. Reflection；
3. Practice weakness；
4. Fact boundary；
5. JD gap；
6. Story gap。

每一项必须有：

- title；
- 人话原因；
- source；
- action。

排序可以使用 rubric 权重，但**不得把“第 1.0 级 / 满级 4 / 岗位权重 18”这类评测器调试语言直接展示给用户**。

---

## 5. Materials

资料角色必须分开：

```text
Resume
Project Material
Knowledge Base
Quick Notes
Question Bank
Skill Card
Story
```

重要边界：

```text
KB knowledge != personal evidence
Quick Note != evidence
generated question != real interview question
```

Material lifecycle：

```text
PROCESSING
READY
FAILED
REPLACING
```

替换文件时，旧 READY 版本继续可用，直到新版本 READY。

---

## 6. Fact Inbox

Evidence Graph 不直接暴露为数据库界面。

产品入口：

```text
我的成竹
→ 待确认
```

例如：

```text
“我负责完整 RAG 架构设计”

材料目前支持：
参与设计

[我主导]
[我参与]
[修改]
[查看来源]
```

用户确认不会凭空提高 Provenance。

v1.4 还观察：

- backlog；
- resolution；
- dismiss；
- reopen；
- resolve time。

如果 burden 变高，应减少生成 / 合并，而不是增加提醒。

---

## 7. Story

Story Bank 按能力组织：

- Ownership / 个人职责；
- Conflict；
- Failure；
- Leadership；
- Ambiguity；
- Collaboration；
- Difficult Problem；
- Influence；
- Trade-off；
- Learning。

没有真实故事时：

- 给找故事方向；
- 可以启动 Story Builder；
- 不生成虚构经历。

---

## 8. Practice 3.0

Practice Setup：

```text
Goal
Round
Persona
Demeanor
Difficulty
Question Sources
Language
Human Coach
```

Round：

- Technical；
- Project Deep Dive；
- System Design；
- Hiring Manager；
- HR；
- Behavioral；
- Product / Case。

Demeanor：

- Neutral；
- Friendly；
- Skeptical；
- Strong Follow-up；
- Fast-paced。

Difficulty：

- Warmup；
- Standard；
- Pressure。

Sources：

- Goal Question Graph；
- Recent Weakness；
- My Question Bank；
- Role Bank。

---

## 9. Adaptive Follow-up

下一问受：

```text
Goal
Round
Persona
Demeanor
Difficulty
current answer
Question Graph
Recent Weakness
open threads
```

共同影响。

支持：

- follow-up；
- challenge；
- constraint change；
- ownership probe；
- quantify；
- clarify；
- contradiction probe；
- closing question。

不是固定题单播放器。

---

## 10. Question Banks

题目 origin 必须明确：

```text
CURATED
IMPORTED
GENERATED
PREVIOUS_SESSION
USER_ADDED
```

模型生成题不能伪装成“真实面经”。

---

## 11. Panel / Multi-persona

Practice 支持 2–3 个 personas。

示例：

```text
Tech Lead
Hiring Manager
Product Partner
```

每轮只有一个 current speaker。

Follow-up 保持 persona concern / style 连续，不允许三个人同时抢话。

---

## 12. Content Coach × Delivery Coach

### Content Coach

看：

- 是否回答问题；
- truth boundary；
- technical depth；
- structure；
- trade-off；
- ownership；
- evidence；
- follow-up resilience。

Finding 必须引用用户真实口述，而不是 AI answer。

### Delivery Coach

看：

- time to conclusion；
- duration；
- pace；
- pause；
- repetition；
- fillers；
- possible scripted delivery。

不输出单一综合分。

---

## 13. Progress Trends

只在同一个 Goal 内展示解释性趋势。

例如：

```text
技术深度      在改善
个人职责      反复出现
结论时间      在改善
```

不做：

- candidate ranking；
- offer probability；
- composite readiness score。

---

## 14. Reflection

Reflection 第一屏：

```text
下一步
做得好的
需要改进
待确认事实
Story 机会
用户 Pin
```

完整逐轮 timeline 第二层。

每个 finding 必须能回到：

- question；
- actual speech；
- source。

---

## 15. Reflection write-back

Reflection 不是只显示报告。

支持真实动作：

- Practice this；
- Set as Next Focus；
- Confirm fact；
- Mark mistake；
- Add source；
- Create Story；
- Add Quick Note；
- Don't remember。

闭环：

```text
Reflection
→ ReflectionAction
→ Next Focus
→ Goal Overview
→ next Practice
```

Pin 只有用户显式动作后才能升为 Next Focus。

---

## 16. History

History 统一：

- Real Interviews；
- Practice Sessions；
- Reflections。

Goal 内和 History 打开的 Session 是同一份数据，不复制。

---

## 17. v1.4 validation

本地产品验证回答六个问题：

A. Goal 是否持续复用？  
B. Reflection 是否改变下一轮？  
C. Fast Cue 是否真的有帮助？  
D. Practice 是否迁移？  
E. Fact Inbox 是否成为负担？  
F. Quick Notes / Pin 是否真的创造价值？

证据等级：

```text
NO_DATA
SYNTHETIC_DOGFOOD
LOCAL_DEVICE_USAGE
REAL_USER_EVIDENCE
```

自动化 / synthetic 只证明工程闭环。

```text
REAL_USER_EVIDENCE_PENDING
```

必须保持真实。

---

## 18. 兼容底层

当前产品层仍复用已经验证的：

- Job Representation；
- Candidate × Job alignment；
- Question Graph；
- Story / Skill；
- Review；
- memory policy；
- InterviewPack；
- Context Compiler。

不要为了 Goal-centered UI 重写 Verified Core。

---

## 19. Done

当前 v1.4.x 工程状态：

- Goal Room — PRODUCT_COMPLETE
- Next Focus — PRODUCT_COMPLETE
- Prepare — PRODUCT_COMPLETE
- Practice 3.0 — PRODUCT_COMPLETE
- Panel — PRODUCT_COMPLETE
- Question Banks — PRODUCT_COMPLETE
- Content/Delivery Coach — PRODUCT_COMPLETE
- Reflection write-back — AUTHORITATIVE
- Progress Trends — PRODUCT_COMPLETE
- local validation — ENGINEERING_COMPLETE

真实用户效果仍保持：

```text
REAL_USER_EVIDENCE_PENDING
```
