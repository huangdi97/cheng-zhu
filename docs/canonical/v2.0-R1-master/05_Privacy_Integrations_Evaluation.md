# Chengzhu v2.0-R1 — Privacy, Integrations, Evaluation & Rollout

# 1. Privacy stance

Conversation Profile 比 Interview 更敏感，因为包含第三方声音、组织信息、客户信息和跨系统数据。

默认：

```text
Local-first
Private by default
No auto-share
No auto-send
No automatic external write-back
Minimal retention
Explicit source selection
Explicit consent acknowledgement
```

# 2. Capture Modes

```text
TRANSCRIPT
NOTES_ONLY
NO_CAPTURE
```

TRANSCRIPT 不等于保存音频。

音频 retention 独立控制。

# 3. Processing Modes

```text
LOCAL
CLOUD
OFF
```

UI 必须解释：

- 什么在本机；
- 什么会发送给 provider；
- 是否保存；
- fallback 会发生什么。

Provider failure 不允许 silently switch 到更宽松 privacy mode。

# 4. Consent

产品必须提示用户：

- 转写/录音规则依场景、组织政策和适用法律而异；
- 用户应确认有权进行当前 capture；
- 企业未来可配置 enforced consent announcement。

系统不声称“点击开始即代表所有参与者同意”。

# 5. Speaker identity

默认使用 session-local diarization labels：

```text
Speaker A
Speaker B
```

只有 calendar/用户明确 mapping 后才绑定名字。

禁止默认做长期 voice biometric identity。

# 6. Counterparty privacy

不持久化：

- hidden emotion；
- personality diagnosis；
- inferred trust；
- inferred willingness to pay；
- inferred private intent。

Temporary inference 有 TTL。

# 7. Screen Context

Screen Context 默认 OFF / explicit opt-in。

允许：

- manual screenshot；
- selected window；
- selected region。

敏感窗口可 exclude。

屏幕内容进入 Session Pack/Live context 前做 visibility 标记。

# 8. Connectors

## Read-only first

优先：

- Calendar；
- docs；
- approved project sources；
- approved email threads；
- task/issue tracker。

每个 connector scope 明确。

## Source authority

Connector payload 是 source，不自动变 truth。

## Write-back

第一阶段只生成 DraftAction：

```text
CREATE_TASK_DRAFT
CREATE_ISSUE_DRAFT
FOLLOWUP_EMAIL_DRAFT
UPDATE_DECISION_LOG_DRAFT
```

用户确认后才能执行。

# 9. MCP

长期 MCP 支持分两方向：

### Chengzhu as MCP client
Prepare/Continue 获取授权上下文。

### Chengzhu as MCP server
让其它 agent 查询：

- confirmed decisions；
- confirmed commitments；
- approved notes；
- session summaries；
- provenance refs。

默认不暴露原始 transcript 与私人 Quick Notes，除非 scope 明确。

# 10. Data retention

每类独立：

- audio；
- transcript；
- screen；
- guidance events；
- analytics；
- confirmed items；
- connector snapshots。

提供 presets：

- Minimum；
- Standard；
- Custom。

# 11. Delete

Delete Session：

- transcript；
- screen；
- unconfirmed items；
- guidance；
- derived local memory。

Confirmed item 如被其它 Session 继承，删除时必须提示影响并支持 provenance tombstone / detach，而不是 dangling ref。

# 12. Export

分类导出，不能混成一个 JSON 黑盒：

- transcript；
- notes；
- confirmed items；
- unconfirmed AI candidates；
- guidance；
- analytics；
- source manifest。

# 13. Evaluation Matrix

## Conversation State

- topic segmentation；
- question target；
- open thread continuity；
- state transition accuracy。

## Provenance

- source attribution；
- superseded filtering；
- visibility enforcement；
- no self-citation loop。

## Guidance

- relevance；
- novelty；
- source quality；
- timing；
- interruption regret；
- duplication；
- adoption。

## Contribution Opportunity

核心不是 recall，而是 precision。

需要人工 gold：

- SHOULD_SHOW；
- COULD_SHOW；
- SHOULD_STAY_SILENT。

## Continue

- Decision precision；
- Commitment owner precision；
- deadline precision；
- proposal vs agreed separation；
- supersession chain。

# 14. Synthetic / Internal Dogfood

没有真实用户时允许做：

- scripted multi-speaker sessions；
- recorded synthetic audio；
- 30-session continuity；
- 100-session state reliability；
- provider failure；
- offline/reconnect；
- stale-memory tests；
- privacy deletion；
- export/reimport；
- profile switching。

这些只证明 engineering。

# 15. Release Gates

v2 engineering release 前至少：

- v1 Interview non-regression；
- migration rollback/recovery；
- Conversation data tests；
- provenance golden set；
- opportunity suppression tests；
- functional Playwright；
- visual regression；
- packaged Windows runtime；
- clean install；
- runtime screenshots；
- profile-switching evidence；
- long session soak；
- delete/export evidence。

# 16. Real-user gates

真实参与者才可以回答：

- proactive guidance 是否烦；
- Contribution Opportunity 是否真的有用；
- 用户是否更愿意说出自己已有但忘记的信息；
- false-positive risk 的容忍度；
- 1:1 场景是否让人不舒服；
- cross-session memory 是否建立信任；
- Conversation Room 是否成为持续工作区。

未完成前：

```text
REAL_CONVERSATION_USER_EVIDENCE_PENDING
```

# 17. Rollout

## v2.0-alpha
内部 / synthetic：
- Project Sync；
- Design Review；
- Conversation Room；
- Prepare；
- item extraction；
- Continue；
- Manual Ask。

## v2.0-beta
加入：
- Contribution Opportunity；
- Guidance Arbiter；
- live overlay；
- cross-session memory；
- calendar read-only。

## v2.0-RC
加入：
- profile templates；
- connector drafts；
- packaged runtime evidence；
- migration/export/delete；
- final UI polish。

## v2.x later
真实 evidence 后：
- richer connectors；
- reviewed write-back；
- mobile capture；
- team shared context。

# 18. Business boundary

先做个人：

```text
Personal Conversation Intelligence
```

不直接做：

- enterprise meeting recorder；
- company-wide surveillance；
- sales rep ranking；
- manager sentiment dashboard；
- employee productivity scoring。

这让 Chengzhu 保持“帮助用户表达自己”，而不是“替组织观察所有人”。
