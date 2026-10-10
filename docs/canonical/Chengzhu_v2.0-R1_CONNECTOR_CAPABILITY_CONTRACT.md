# Chengzhu v2 Conversation Connector Capability Contract
## Post-beta.2 Capability Registry + Audited Integration Boundary

**状态**：DESIGN COMPLETE / CAPABILITY REGISTRY AVAILABLE / INTEGRATION BOUNDARY IMPLEMENTED / GITHUB ADAPTER OPT-IN CANDIDATE  
**适用**：Calendar / Docs / Mail / project tracker / MCP / reviewed external write-back  
**主线边界**：PR #61 已合入 main（merge commit `72e810c1`）；当前 GitHub real adapter 在 `feat/chengzhu-v2-github-provider`，合并前不声明真实账户可用

---

## 1. 三层真相

连接器必须拆成三层：

```text
Capability Registry
→ Connected Account
→ External Execution Result
```

三层不能互相替代。

### Capability Registry

回答：

> 当前进程是否注册了一个真实 adapter，可满足 capability X？

默认空 registry / fail-closed。

### Connected Account

回答：

> 哪个用户批准的 provider account，在当前时刻通过了 credential + health + exact capability 校验？

仅 catalog 存在不算 connected。

### External Execution Result

回答：

> 某条已经过本地 review 的 DraftAction，是否经过第二次显式执行，并得到 provider 成功返回？

`APPROVED` 与 `PENDING` 都不等于 external success。

---

## 2. Canonical capability vocabulary

Session read capabilities：

- `calendar.read`
- `docs.read`
- `mail.read`
- `project.read`

Reviewed execution capabilities：

- `email.send`
- `task.create`
- `issue.create`
- `decision_log.write`

未知 capability 必须拒绝。

---

## 3. Read / write 必须分离

Session Policy `connector_permissions` 只允许 read capability。

若 Session permission 请求 write capability：

```text
WRITE_REQUIRES_EXPLICIT_EXECUTION_FLOW
```

写回必须走：

```text
Conversation truth
→ DraftAction
→ explicit review
→ APPROVED
→ exact provider/account selection
→ Execution Request
→ second explicit Execute
→ provider result/failure
→ audit
```

---

## 4. Provider catalog

内置 catalog 只是 adapter contract metadata，不是连接状态。

当前 catalog：

| Provider | Capabilities |
| --- | --- |
| Google Calendar | calendar.read |
| Gmail | email.send（send-only；mail.read 未实现） |
| Google Drive / Docs | docs.read |
| Microsoft To Do (Graph) | task.create only |
| Local Markdown / Obsidian | decision_log.write only |
| GitHub | project.read / issue.create |
| MCP | server-defined subset of canonical capability vocabulary |

默认仍然是：

```text
connected account = 0
```

GitHub、Google Calendar 与 Google Drive adapter 代码可随应用发布，但都必须显式 opt-in：

```text
CHENGZHU_GITHUB_CONNECTOR_ENABLE=1
CHENGZHU_GOOGLE_CALENDAR_CONNECTOR_ENABLE=1
CHENGZHU_GOOGLE_DRIVE_CONNECTOR_ENABLE=1
CHENGZHU_GOOGLE_MAIL_CONNECTOR_ENABLE=1
CHENGZHU_MICROSOFT_TODO_CONNECTOR_ENABLE=1
CHENGZHU_LOCAL_MARKDOWN_CONNECTOR_ENABLE=1
```

才注册为 `adapter_available=true`。Google Mail 当前只注册 `email.send`，不注册 `mail.read`；Microsoft To Do 当前只注册 `task.create`，不注册 Outlook/Calendar/Files read/write。MCP 仍不能仅凭 catalog 条目冒充真实 adapter。

---

## 5. Provider scope / least privilege

Catalog provider 的 scope 必须由 granted capability 推导，并保存为最小权限集合。

示例：

```text
calendar.read → Google calendar.events.readonly
email.send    → openid + email + Gmail send
mail.read     → 未实现；不因 email.send 偷加 Gmail readonly

task.create   → Microsoft Tasks.ReadWrite
decision_log.write → local.filesystem.markdown.write

project.read  → GitHub Issues: read
issue.create  → GitHub Issues: write
project.read + issue.create → GitHub Issues: write
```

对于 catalog provider：

> supplied provider scopes 必须与 capability 推导出的最小集合一致。

MCP 使用：

```text
server-defined
```

Chengzhu 不伪造 MCP scope。

---

## 5.1 Google Calendar native read contract

当前 `GOOGLE_CALENDAR` concrete adapter 只实现：

```text
calendar.read
→ CALENDAR_EVENT immutable snapshots
```

关键约束：

- access token 只通过 `provider:google-calendar:env:<ENV_VAR>` 解析；
- Verify 只做一页只读 probe，不偷偷执行 full sync；
- initial sync 使用 Google Events 原生分页并获得最后一页 `nextSyncToken`；
- HTTP 410 只重置 `calendar.read` cursor 并执行一次 full resync；
- cursor 与显式 `calendar_id` 绑定，禁止跨 calendar 复用 token；
- complete change set 超过 Chengzhu 当前 500 snapshot 安全上限时整次失败，不推进 token；
- cancelled event 保留为 immutable external observation；
- event snapshot 仍是 `REFERENCE_SOURCE`，不自动升级 Decision / Commitment / Deadline；
- 同一 external event 的历史 revision 继续保留审计，但只有 latest revision 可被新导入；
- 已导入 Session 遇到后续 reschedule/cancel 时保持本地冻结值，同时显式标记 `SOURCE_DRIFT / CANCELLED_UPSTREAM`；
- all-day event 不伪造 UTC midnight；`focusTime / outOfOffice / workingLocation` 不能导入为 Conversation Session；
- provider timezone 会进入 time semantics；
- future、non-cancelled、latest-revision meeting-like event 只有用户显式点击“作为下一场”后才创建本地 UPCOMING Session；
- 导入后 provider 后续变化不静默改写已创建 Session。

实现说明：
[Google Calendar Conversation Connector](../architecture/GOOGLE_CALENDAR_CONVERSATION_CONNECTOR.md)

---

## 5.2 Google Drive / Docs target-scoped read contract

当前 `GOOGLE_DRIVE` concrete adapter 只实现：

```text
docs.read
→ explicit folder FULL_TARGET_REFRESH
→ DOCUMENT immutable snapshots
```

关键约束：

- access token 只通过 `provider:google-drive:env:<ENV_VAR>` 解析；
- Verify 只做 account read probe，不把账号认证冒充 folder 可读；
- 每次 Sync 必须显式指定 `root` 或具体 folder id；
- Sync 先读取 folder metadata，证明 target 存在、是 folder、且未在 trash；
- folder direct children 必须完整分页后才能向 integration boundary 返回结果；
- direct children 超过 500 时整次失败，不保存“前 500 个”再假装完整；
- v1 provider 采用 user-triggered `FULL_TARGET_REFRESH`，不做 account-wide background mirror；
- Google Docs / Slides → `text/plain`，完整读取用于本地 full-content digest，但 snapshot retrieval 仅冻结前 20k 字符（`TEXT_EXPORT_EXCERPT_20K`）；
- Google Sheets → `text/csv`，并冻结 `partial_content=true / FIRST_SHEET_CSV_EXCERPT_20K`；
- 可文本化 blob 同样以完整读取内容计算 revision digest，但当前 retrieval scope = `FIRST_20000_CHARS`；
- full-content digest 进入 canonical snapshot hash metadata，使“前 20k 相同、尾部变化”的文档仍形成新 revision；
- 常见小型文本 blob → `files.get?alt=media`；
- PDF / image / binary / unsupported → metadata-only DOCUMENT，`content_available=false`；
- 超过 2MB 的文本不做静默截断后冒充完整正文；
- Drive snapshot 仍是 `REFERENCE_SOURCE`，不自动升级 Decision / Commitment / Deadline；
- user 必须显式勾选 snapshot 后它才进入 Space / Session Pack；
- 后续再次 Sync 生成新 immutable revision，不静默改写已开始 Session Pack；
- provider 没有任何 Drive write capability。

实现说明：
[Google Drive Conversation Connector](../architecture/GOOGLE_DRIVE_CONVERSATION_CONNECTOR.md)

---

## 5.3 Gmail reviewed send-only contract

当前 `GOOGLE_MAIL` concrete adapter 只实现：

```text
APPROVED FOLLOWUP_EMAIL_DRAFT
→ exact Gmail account
→ exact single recipient
→ Execution Request
→ second explicit Execute
→ users.messages.send
→ provider result / UNKNOWN_OUTCOME audit
```

最小权限冻结为：

```text
openid
email
https://www.googleapis.com/auth/gmail.send
```

其中 `openid + email` 只用于 OIDC UserInfo 身份校验，不授予 mailbox/message read。当前 provider **不实现**：

- `gmail.readonly`；
- `mail.read`；
- inbox/thread/message sync；
- Gmail snapshot；
- background polling；
- mailbox search。

关键约束：

- adapter 只有在 `CHENGZHU_GOOGLE_MAIL_CONNECTOR_ENABLE=1` 时注册；
- access token 只通过 `provider:google-mail:env:<ENV_VAR>` 解析；
- Verify 调 Google OIDC UserInfo，确认 `email_verified=true` 的账号 identity；
- Verify 不调用 Gmail `users.getProfile`，因为 send-only scope 不应为了展示账号而扩大到 mailbox read；
- Verify 只证明账号 identity / credential health，不证明 send 成功；
- 真正 `email.send` 只有第二次显式 Execute 得到 Gmail `messages.send` 成功返回后才成立；
- v1 一次 execution 只允许一个明确裸邮箱地址作为 recipient；
- MIME 由标准库构造，拒绝 CR/LF header injection 与多收件人字符串；
- provider 没有可依赖的 server-side idempotency key；审计 header 不是幂等保证；
- 4xx 明确拒绝可记录 FAILED；timeout / 5xx / 其他不确定传输进入 `UNKNOWN_OUTCOME`，禁止自动重试；
- 如果外发安全层检测到 secret 并改写 reviewed Draft，Gmail adapter 拒绝发送，要求用户回到 Draft 重新审核；
- Gmail provider 不会静默截断已审核 Subject/Body；超过 provider v1 安全上限时拒绝执行并要求修改/重新审核；
- 当前没有真实 Google account/runtime replay，因此不得声明真实邮件已成功发出。
- Google 官方将 `gmail.send` 归类为 **Sensitive scope**；公共/稳定 provider 还需要适用的 OAuth consent / app verification。CI/adapter 存在不能替代该外部发布门槛。

实现说明：
[Google Mail Conversation Connector](../architecture/GOOGLE_MAIL_CONVERSATION_CONNECTOR.md)

---

## 6. Credential boundary

`product.db` 只能保存 opaque credential reference：

- `keyring:...`
- `oskeychain:...`
- `provider:...`
- `plugin:...`

禁止保存：

- access token；
- refresh token；
- API key；
- cookie；
- Authorization header；
- password；
- private key；
- client secret。

Public API / export 只显示：

```text
credential_ref_present = true / false
```

---

## 7. Connection lifecycle

```text
create connection metadata
→ DISCONNECTED
→ verify adapter + credential reference + configured capability contract + provider identity health
→ CONNECTED
→ DISCONNECTED / ERROR / REVOKED
```

不提供“UI 直接把 status 改成 CONNECTED”的接口。

`CONNECTED` 表示 provider account identity / credential health 已验证；它不等于“任意目标资源的 capability 已证明”。对需要显式 target 的 provider（当前 GitHub / Google Calendar / Google Drive）：

- `project.read` 在真实 Sync 到具体 `owner/repo` 时证明；
- `calendar.read` 在真实 Sync 到具体 `calendar_id` 时证明；
- `docs.read` 在真实 folder probe + 完整 refresh 时证明；
- `issue.create` 在 reviewed + second explicit Execute 的真实 provider 响应时证明；
- 不使用 account-level health probe 冒充 target-level capability proof。

Revoke：

- 清除 opaque credential reference；
- 清除 sync cursor；
- 禁止未来 read/write；
- 不修改历史 Pack / snapshot / execution audit。

---

## 8. Preflight

请求 read capability 时，必须同时存在：

```text
registered adapter
+ CONNECTED account
+ exact capability grant
+ current adapter health
```

否则 fail-closed。

Preflight 冻结：

- requested capabilities；
- provider id；
- connection id；
- safe account hint；
- blocked reasons；
- explicit selected connector snapshot ids。

Start 必须先执行一次最新 Preflight/health + context fingerprint 校验，然后把**这次已经验证并进入 fingerprint 的 connector runtime 原样冻结到 Session Pack**。freeze_pack 不得再独立 resolve 第二套 provider health 结果，否则 Preview 与 Pack 可能发生 TOCTOU 漂移。

No placeholder provider.

---

## 9. Immutable external snapshot

外部 read 不是“每次 Live 重新查最新远程状态”。

路径：

```text
CONNECTED account
→ explicit Sync
→ adapter.read_context
→ immutable normalized snapshot
→ user selects snapshot in Space
→ Preflight
→ Session Pack freeze
```

snapshot provenance：

- provider；
- connection；
- capability；
- external kind；
- external id；
- content hash；
- occurred_at；
- visibility。

同一个 external object 内容变化后生成新 snapshot，不覆盖旧 snapshot。

---

## 9.1 Snapshot provenance hardening

schema v9 冻结以下规则：

```text
snapshot identity =
space_id
+ connection_id
+ capability
+ external_kind
+ external_id
+ Chengzhu canonical content_hash
```

- 相同外部对象同步到不同 Space 时必须形成各自 Space-scoped snapshot row；
- provider 自报 content hash 仅作为 provenance metadata 保存，不控制 Chengzhu identity；
- Space 不能持久化别的 Space 的 snapshot id；
- 每个 read capability 独立维护 sync cursor，禁止 Calendar / Docs / Mail / Project cursor 串流；
- 已开始 Session 继续使用 frozen snapshot，不被后续 Sync 改写。

---

## 10. External source authority

所有 connector snapshot 默认：

```text
authority = REFERENCE_SOURCE
```

即：

```text
Calendar event != Decision
Mail sentence != Commitment
GitHub issue != reviewed Deadline
```

必须继续走 Conversation review 才能升级长期 truth。

---

## 11. Session Pack

Pack 冻结：

- selected snapshot；
- snapshot content/provenance；
- exact connection grant；
- provider id；
- account hint；
- capability；
- content hash。

开始后：

- 新 Sync 不修改 Pack；
- account disconnect/revoke 不修改 Pack；
- provider health 变化不修改 Pack。

---

## 12. Manual Ask

Manual Ask 可以查询 frozen connector snapshot。

排序仍尊重 truth authority：

```text
CONFIRMED_TRUTH
> frozen personal evidence
> frozen reference source
> connector REFERENCE_SOURCE
> Quick Note
> screen/transcript observations
```

Connector 不因 provider 品牌而提高 truth authority。

---

## 13. Reviewed external execution

DraftAction mapping：

```text
FOLLOWUP_EMAIL_DRAFT
→ email.send

CREATE_TASK_DRAFT
→ task.create

CREATE_ISSUE_DRAFT
→ issue.create

UPDATE_DECISION_LOG_DRAFT
→ decision_log.write
```

流程：

```text
DRAFT
→ APPROVED
→ select CONNECTED account with exact write grant
→ create Execution Request (PENDING/BLOCKED)
→ second explicit Execute
→ EXECUTING
→ SUCCEEDED / FAILED / UNKNOWN_OUTCOME / BLOCKED
```

仅 provider **显式返回 boolean `ok=true`** 才可表示 `SUCCEEDED`。

`UNKNOWN_OUTCOME` 用于 timeout、transport exception、进程中断或缺少明确 `ok` 的 malformed outcome；它表示“外部副作用可能已经发生，但 Chengzhu 无法确认”，因此禁止直接 retry。

---

## 14. Idempotency

Execution Request 生成稳定 idempotency key，至少绑定：

- DraftAction；
- DraftAction version/update time；
- connection；
- capability；
- operation；
- target。

已经 `SUCCEEDED` 的 audit row 再次 Execute 不重复外部调用。

Idempotency key 只是 contract input，不等于所有 provider 天生幂等。Concrete adapter 必须真实把该 key 映射到 provider 的幂等机制，才能声明 provider-level retry safety。

明确失败的结果 envelope：

```json
{"ok": false, "error": "...", "retry_safe": false}
```

只有 `retry_safe=true` 时，Chengzhu 才允许对同一 audit row 再次 Execute。

---

## 15. Failure / revocation

Provider unhealthy、credential 被撤销或 capability 不再存在时：

- 新 Preflight fail-closed；
- 新 Sync 明确失败；
- external execution 在执行前重新校验；
- 已开始 Session 继续保留 frozen Pack；
- 不把 stale provider state 当 fresh；
- provider 明确 `ok=false` 记录 `FAILED`；
- transport exception / timeout / malformed outcome 记录 `UNKNOWN_OUTCOME`；
- `UNKNOWN_OUTCOME` 不改成 FAILED，也不能直接重试；
- 必须先在 provider 侧核对并记录 reconciliation；
- `CONFIRMED_SUCCEEDED` 保留为 USER_REPORTED_PROVIDER_CHECK，不伪造原 adapter 的 `ok=true`；
- `CONFIRMED_NOT_APPLIED` 才能把同一 audit row 标为 `retry_safe=true`；
- 任何失败/不确定结果都不改写 Conversation truth 或 DraftAction approval。

---

## 16. Privacy / sanitization

Connector snapshot 的 external id / title / excerpt / provider hash / metadata，以及 execution response 都必须做 value-level / key-level secret sanitization。

Reviewed DraftAction 进入 Execution Request 时也必须先生成 provider-safe payload：

- secret/token-shaped value 不得进入 execution audit 的 request；
- 不得原样发给 provider；
- audit 中冻结 `outbound_redaction_applied = true/false`；
- 若发生脱敏，第二次显式 Execute 前 UI 必须让用户看到“实际外发 payload 与本地 Draft 可能不同”。

Provider URL 只保留：

```text
scheme + host + path
```

userinfo / query / fragment 删除。除了按 key 删除 token/secret/auth 字段外，还要对普通字符串中的明显 credential-shaped value 做 redaction；opaque credential reference 也不能用 `provider:/plugin:` 外壳夹带真实 token。

---

## 17. Retention

普通 retention 可以清理：

- 未被 Space 选中；
- 超过 connector snapshot retention；
- 未冻结成 active source 的 snapshot row。

必须保留：

- Space 当前 selected snapshot；
- Session Pack 内 frozen copy；
- external execution audit；
- 被 execution audit 引用的 DraftAction。

---

## 18. Export

允许导出：

- public connection metadata；
- snapshot provenance；
- external execution audit。

禁止导出：

- credential_ref；
- token；
- secret；
- authorization material。

Manifest：

```text
contains_external_secrets = false
credential_refs_exported = false
```

---

## 19. Diagnostics

状态语义：

```text
NOT_CONFIGURED
ADAPTER_AVAILABLE_NOT_CONNECTED
CONNECTED
```

另报告：

- catalog；
- registered adapters；
- connections；
- connected count；
- snapshot count；
- execution count。

---

## 19.5 GitHub real provider

首个真实 provider 采用 GitHub REST：

```text
project.read
→ GET /repos/{owner}/{repo}/issues
→ filter pull_request rows
→ immutable ISSUE snapshot
→ explicit Space selection
→ Session Pack freeze

CREATE_ISSUE_DRAFT
→ APPROVED
→ exact GitHub connection
→ explicit owner/repo target
→ Execution Request
→ second Execute
→ POST /repos/{owner}/{repo}/issues
→ provider ok=true / FAILED / UNKNOWN_OUTCOME
```

安全约束：

- fine-grained PAT 最小权限只需 Issues read/write；
- token 不进入 product.db，不进入前端，不进入 export；
- product.db 只保存 `provider:github:env:<ENV_VAR>`；
- verify 时真实调用 `/user`；
- Sync 与 write target 都必须显式填写 `owner/repo`；
- GitHub issues endpoint 返回的 Pull Request 必须过滤；
- provider 5xx / transport failure 继续走 UNKNOWN_OUTCOME，不自动 retry；
- issue body 带 Chengzhu execution marker，便于 provider-side reconciliation；
- 没有真实 token/account/runtime evidence 时，禁止声明 `GITHUB_ACCOUNT_CONNECTED = TRUE`。

实现与使用说明见：

- [GitHub Conversation Connector](../architecture/GITHUB_CONVERSATION_CONNECTOR.md)

---

## 19.9 Microsoft To Do reviewed task-create provider

当前 `MICROSOFT_GRAPH` catalog 已从泛 Graph placeholder 收窄为唯一真实实现：

```text
CREATE_TASK_DRAFT
→ APPROVED
→ exact Microsoft To Do connection
→ target = default / explicit task-list id
→ Execution Request
→ second Execute
→ POST /me/todo/lists/{listId}/tasks
→ provider ok=true / FAILED / UNKNOWN_OUTCOME
```

最小 delegated permission：

```text
Tasks.ReadWrite
```

边界：

- adapter 默认不注册；只有 `CHENGZHU_MICROSOFT_TODO_CONNECTOR_ENABLE=1` 才 available；
- token 只通过 `provider:microsoft-graph:env:<ENV_VAR>` opaque ref 解析；
- Verify 使用 To Do list probe，只证明 Tasks.ReadWrite 当前可用于 To Do lists；
- 不实现 Outlook Mail / Calendar / OneDrive / Planner；
- 不实现 task read sync / background mirror；
- `default` target 在 Execute 时解析 built-in `defaultList`；
- 也允许用户显式填写 task-list id；
- provider 没有 Chengzhu 可依赖的 create-task idempotency primitive，因此 ambiguous outcome 必须进入 `UNKNOWN_OUTCOME`；
- 没有真实 Microsoft OAuth/account/runtime replay 前，不得声明真实 Task 已创建。

实现说明：

- [Microsoft To Do Conversation Connector](../architecture/MICROSOFT_TODO_CONVERSATION_CONNECTOR.md)

---

## 19.10 Local Markdown / Obsidian reviewed Decision Log provider

当前 `LOCAL_MARKDOWN` concrete adapter 只实现：

```text
UPDATE_DECISION_LOG_DRAFT
→ APPROVED
→ exact Local Markdown connection
→ relative .md target under configured root
→ Execution Request
→ second Execute
→ atomic local Markdown append
→ provider ok=true / FAILED / UNKNOWN_OUTCOME
```

边界：

- adapter 默认不注册；只有 `CHENGZHU_LOCAL_MARKDOWN_CONNECTOR_ENABLE=1` 才 available；
- product.db 只保存 `provider:local-markdown:env:<ENV_VAR>`，实际 root path 只从 backend process environment 解析；
- Verify 只证明 root 当前存在且可读写，不读取/索引 vault 内容；
- capability = `decision_log.write`，scope = `local.filesystem.markdown.write`；
- target 只能是 root 下相对 `.md` 路径，拒绝绝对路径、`..`、反斜杠 target、symlink target 与 root escape；
- existing target 超过 10 MiB 时在读取前拒绝；
- outbound payload 若被安全层脱敏修改，则拒绝写入，要求用户重新审核；
- write 使用同目录 temp + fsync + `os.replace`；
- 文件中写入 `chengzhu-execution:<idempotency_key>` marker，重复 Execute 可 provider-level 去重；
- replace 后异常继续由共享边界记录 `UNKNOWN_OUTCOME`，禁止自动 retry；
- 不提供 docs.read、目录枚举、搜索、删除、rename、shell、Git commit/push。

实现说明：

- [Local Markdown Decision Log Connector](../architecture/LOCAL_MARKDOWN_DECISION_LOG_CONNECTOR.md)

---

## 20. 当前 repo truth

PR #61 + GitHub provider + Calendar provider 合并后，repo engineering truth 允许声明：

```text
CONNECTOR_CAPABILITY_CONTRACT = IMPLEMENTED
CONNECTOR_REGISTRY_DEFAULT = FAIL_CLOSED
EXTERNAL_INTEGRATION_BOUNDARY = IMPLEMENTED
IMMUTABLE_EXTERNAL_SNAPSHOT_PATH = IMPLEMENTED
REVIEWED_TWO_STEP_EXECUTION_BOUNDARY = IMPLEMENTED
AMBIGUOUS_EXTERNAL_OUTCOME_GUARD = IMPLEMENTED
GITHUB_PROVIDER_ADAPTER = RUNTIME_AVAILABLE_OPT_IN
GOOGLE_CALENDAR_PROVIDER_ADAPTER = RUNTIME_AVAILABLE_OPT_IN
GOOGLE_DRIVE_PROVIDER_ADAPTER = RUNTIME_AVAILABLE_OPT_IN
GOOGLE_MAIL_PROVIDER_ADAPTER = RUNTIME_AVAILABLE_OPT_IN
MICROSOFT_TODO_PROVIDER_ADAPTER = RUNTIME_AVAILABLE_OPT_IN
LOCAL_MARKDOWN_DECISION_LOG_ADAPTER = RUNTIME_AVAILABLE_OPT_IN
```

仍禁止在缺少真实 adapter/account/runtime evidence 时声明：

```text
MAIL_CONNECTOR_AVAILABLE = TRUE
DRIVE_ACCOUNT_CONNECTED = TRUE
REAL_DRIVE_DOCUMENT_SYNC_PROVEN = TRUE
CALENDAR_ACCOUNT_CONNECTED = TRUE
PROJECT_TRACKER_ACCOUNT_CONNECTED = TRUE
GOOGLE_ACCOUNT_CONNECTED = TRUE
MICROSOFT_ACCOUNT_CONNECTED = TRUE
REAL_MICROSOFT_TASK_CREATE_PROVEN = TRUE
GITHUB_ACCOUNT_CONNECTED = TRUE
MCP_SERVER_CONNECTED = TRUE
REAL_EXTERNAL_ACTION_EVIDENCE = TRUE
```

进一步实现细节见：

- [Conversation Integration Boundary](../architecture/CONVERSATION_INTEGRATION_BOUNDARY.md)
- [Google Drive Conversation Connector](../architecture/GOOGLE_DRIVE_CONVERSATION_CONNECTOR.md)
- [Local Markdown Decision Log Connector](../architecture/LOCAL_MARKDOWN_DECISION_LOG_CONNECTOR.md)

外部 provider 真正接线后，仍需独立 adapter tests、授权 evidence、runtime replay 与 external result evidence。
