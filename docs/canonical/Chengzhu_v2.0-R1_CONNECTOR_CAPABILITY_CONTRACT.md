# Chengzhu v2 Conversation Connector Capability Contract
## Post-beta.2 Capability Registry + Audited Integration Boundary

**状态**：DESIGN COMPLETE / CAPABILITY REGISTRY AVAILABLE / INTEGRATION BOUNDARY CANDIDATE  
**适用**：Calendar / Docs / Mail / project tracker / MCP / reviewed external write-back  
**实现 PR**：#61（current-main rebuild；合并前不声明 stable runtime）

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
| Gmail | mail.read / email.send |
| Google Drive / Docs | docs.read |
| Microsoft Graph | calendar.read / mail.read / docs.read / project.read / email.send / task.create |
| GitHub | project.read / issue.create |
| MCP | server-defined subset of canonical capability vocabulary |

默认：

```text
adapter_available = false
connected account = 0
```

---

## 5. Provider scope / least privilege

Catalog provider 的 scope 必须由 granted capability 推导，并保存为最小权限集合。

示例：

```text
calendar.read → Google calendar.readonly
mail.read     → Gmail readonly
email.send    → Gmail send

calendar.read → Microsoft Calendars.Read
mail.read     → Microsoft Mail.Read
email.send    → Microsoft Mail.Send

project.read  → GitHub Issues: read
issue.create  → GitHub Issues: write
```

对于 catalog provider：

> supplied provider scopes 必须与 capability 推导出的最小集合一致。

MCP 使用：

```text
server-defined
```

Chengzhu 不伪造 MCP scope。

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
→ verify adapter + credential + scope + capability + health
→ CONNECTED
→ DISCONNECTED / ERROR / REVOKED
```

不提供“UI 直接把 status 改成 CONNECTED”的接口。

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
→ SUCCEEDED / FAILED / BLOCKED
```

仅 `SUCCEEDED` 可表示 provider 返回成功。

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
- 任何失败/不确定结果都不改写 Conversation truth 或 DraftAction approval。

---

## 16. Privacy / sanitization

Connector snapshot metadata 与 execution response 必须递归清洗敏感 key。

Provider URL 只保留：

```text
scheme + host + path
```

query / fragment 删除。

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

## 20. 当前 repo truth

PR #61 合并后允许声明：

```text
CONNECTOR_CAPABILITY_CONTRACT = IMPLEMENTED
CONNECTOR_REGISTRY_DEFAULT = FAIL_CLOSED
EXTERNAL_INTEGRATION_BOUNDARY = IMPLEMENTED
IMMUTABLE_EXTERNAL_SNAPSHOT_PATH = IMPLEMENTED
REVIEWED_TWO_STEP_EXECUTION_BOUNDARY = IMPLEMENTED
AMBIGUOUS_EXTERNAL_OUTCOME_GUARD = IMPLEMENTED
```

仍禁止在缺少真实 adapter/account/runtime evidence 时声明：

```text
CALENDAR_CONNECTOR_AVAILABLE = TRUE
MAIL_CONNECTOR_AVAILABLE = TRUE
DOCS_CONNECTOR_AVAILABLE = TRUE
PROJECT_TRACKER_CONNECTOR_AVAILABLE = TRUE
GOOGLE_ACCOUNT_CONNECTED = TRUE
MICROSOFT_ACCOUNT_CONNECTED = TRUE
GITHUB_ACCOUNT_CONNECTED = TRUE
MCP_SERVER_CONNECTED = TRUE
REAL_EXTERNAL_ACTION_EVIDENCE = TRUE
```

进一步实现细节见：

- [Conversation Integration Boundary](../architecture/CONVERSATION_INTEGRATION_BOUNDARY.md)

外部 provider 真正接线后，仍需独立 adapter tests、授权 evidence、runtime replay 与 external result evidence。
