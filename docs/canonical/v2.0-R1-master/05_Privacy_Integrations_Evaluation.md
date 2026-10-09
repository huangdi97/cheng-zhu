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

## Integration Boundary 已进入 runtime

纯仓库层不再只有“connector placeholder”。schema v8 定义三层独立对象：

```text
Connection descriptor
→ immutable Connector Snapshot
→ explicit Space selection
→ Frozen Session Pack source

APPROVED DraftAction
→ Execution Request
→ second explicit Execute
→ provider result / failure audit
```

### 8.1 Provider capability / least privilege

Provider catalog 只表达 capability 与最小 scope，不表达“已经连接”。

当前 catalog：
- Google Calendar：`calendar.read`；
- Gmail：`mail.read` / `mail.send` 分离；
- Google Drive / Docs：`docs.read`；
- Microsoft Graph：calendar / mail / docs / task read 与 mail/task write 分离；
- GitHub：issues read / write 分离；
- MCP：context.read / action.execute 分离。

规则：
- requested permission 必须被某个真实 `CONNECTED + adapter available` connection 覆盖；
- 不允许 silent scope escalation；
- read scope 不自动获得 write；
- provider adapter 未接线时 fail-closed。

### 8.2 Secret boundary

`product.db` **禁止保存 OAuth token / API secret**。

只允许 opaque credential ref：

```text
keyring:...
oskeychain:...
provider:...
plugin:...
```

真实 provider adapter 负责向 OS keychain / provider credential store 取凭据。

### 8.3 Read snapshot boundary

外部 Calendar / Mail / Docs / Issue 数据进入 Chengzhu 后，先变成：

```text
CONNECTOR_SNAPSHOT
+ provider / external id
+ content hash
+ occurred_at
+ visibility
+ provenance
```

Snapshot：
- 是 source；
- 不自动变 Conversation truth；
- 只有用户在 Space 中显式选择后，才进入下一场 Session Pack；
- Session 开始后 snapshot 更新不静默改写旧 Pack；
- Manual Ask 可检索 frozen snapshot，但 authority 仍是 `REFERENCE_SOURCE`。

同步 cursor / token 由 provider adapter 持久化；provider 不同可使用 sync token、delta cursor、ETag 或 MCP server-defined cursor。

### 8.4 Retention / export

Connector snapshot 独立 retention：
- Minimum：7 天；
- Standard：30 天；
- 当前 Space 仍显式选中的 snapshot 不被普通 retention 删除；
- 已经冻结进 Session Pack 的副本不被 snapshot retention 反向改写。

Export：
- 可导出 connector snapshot provenance；
- 可导出 external execution audit；
- 不导出 credential ref / token / secret。

## Write-back

DraftAction 仍必须先经过：

```text
DRAFT
→ APPROVED
```

但 pure-repo execution boundary 已扩展为：

```text
APPROVED DraftAction
→ explicit Execution Request
→ scope / connection / adapter recheck
→ second explicit Execute
→ PENDING / EXECUTING / SUCCEEDED / FAILED / BLOCKED
→ provider response + idempotency audit
```

硬规则：
- APPROVED 不等于 sent / created；
- 缺 scope → BLOCKED；
- 未连接 → BLOCKED；
- adapter 不存在 → BLOCKED；
- provider error → FAILED；
- 同一个 draft / connection / operation / target 复用 idempotency key，避免双发；
- 只有 `SUCCEEDED + provider response` 才能宣称外部动作成功；
- 普通 retention 不删除已有 external execution audit。

## 当前 external gate

当前仓库拥有 **Integration Boundary runtime**，但默认不携带真实 Google / Microsoft / GitHub / MCP adapter，也没有用户 OAuth credential provisioning。

因此允许写：

```text
INTEGRATION_BOUNDARY_AVAILABLE = TRUE
REVIEWED_EXTERNAL_EXECUTION_BOUNDARY_AVAILABLE = TRUE
PROVIDER_ADAPTERS_CONFIGURED = FALSE
```

不能写：

```text
GOOGLE_CALENDAR_CONNECTED = TRUE
MAIL_SENT = TRUE
TASK_CREATED = TRUE
ISSUE_CREATED = TRUE
```

除非未来 provider adapter 真实执行并返回成功证据。

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
