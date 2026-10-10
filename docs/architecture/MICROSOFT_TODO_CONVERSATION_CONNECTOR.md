# Microsoft To Do Conversation Connector
## Reviewed task-create provider · v1

**日期**：2026-10-10  
**Provider ID**：`MICROSOFT_GRAPH`  
**能力**：`task.create` only  
**状态**：OPT-IN REAL ADAPTER CODE / REAL ACCOUNT EVIDENCE PENDING

---

## 1. 产品边界

Microsoft Graph 在 Chengzhu v1 connector 中不是 Outlook/OneDrive/Teams 全家桶。

当前唯一主链：

    Continue
    → CREATE_TASK_DRAFT
    → user reviews local Draft
    → APPROVED
    → exact Microsoft To Do connection
    → target = default 或明确 task-list id
    → Execution Request
    → second explicit Execute
    → POST /me/todo/lists/{listId}/tasks
    → SUCCEEDED / FAILED / UNKNOWN_OUTCOME audit

当前明确不实现：

- Outlook Mail read/send；
- Calendar read/write；
- OneDrive / SharePoint read；
- Planner / Project read；
- To Do task sync；
- background polling；
- account-wide mirror；
- silent task creation。

---

## 2. 最小权限

官方 Microsoft Graph delegated permission：`Tasks.ReadWrite`。

它用于 signed-in user 的 To Do task/list read-write；当前 Chengzhu 只使用其中完成 **list probe + reviewed task create** 所必需的部分。

官方参考：

- https://learn.microsoft.com/en-us/graph/permissions-reference#tasksreadwrite
- https://learn.microsoft.com/en-us/graph/api/todotask-post-tasks
- https://learn.microsoft.com/en-us/graph/api/todotasklist-list

当前不申请 `Mail.Read`、`Mail.Send`、`Calendars.Read`、`Files.Read`、`Tasks.Read` 等与当前 task-create 产品边界无关的 Graph scope。

---

## 3. Credential boundary

`product.db` 只保存 opaque reference：

    provider:microsoft-graph:env:<ENV_VAR>

例如：

    provider:microsoft-graph:env:CHENGZHU_MICROSOFT_GRAPH_ACCESS_TOKEN

Access token 本身不进入 product.db、frontend state、export、execution audit 或 provider response。

Adapter 只有在 `CHENGZHU_MICROSOFT_TODO_CONNECTOR_ENABLE=1` 时注册。

---

## 4. Verify semantics

Verify 使用 `GET /me/todo/lists`，并只读取 bounded list metadata：id、displayName、isOwner、isShared、wellknownListName。

    Verify PASS
    = Tasks.ReadWrite 对 Microsoft To Do lists 当前可用
    != task.create 已成功
    != Outlook/Calendar/Drive capability
    != provider delivery/notification evidence

第一次真实 `POST .../tasks` 成功才是 task.create execution evidence。

---

## 5. Target contract

v1 支持两种 target：

### default

`default` 会在 Execute 时读取 To Do lists，寻找 `wellknownListName = defaultList`，再使用其真实 list id。

### explicit list id

用户也可以显式填写 task-list id。

Chengzhu 不会按 displayName 猜 list、自动选最近使用 list，或从另一个 Space / 历史 execution 猜目标。

---

## 6. Reviewed payload contract

`CREATE_TASK_DRAFT` 只在用户本地 APPROVE 后才能创建 Execution Request。

发送到 Graph 的 payload 只包含 reviewed title 与 reviewed plain-text body。当前不会把未单独审核的 due date / reminder / recurrence 自动塞入 Microsoft task。

如果 shared execution safety 层对 reviewed Draft 做了 secret redaction，Microsoft To Do adapter 会拒绝执行，要求用户回到 Draft 修改并重新审核。

同样不会静默截断：title > 500 chars 或 body > 20000 chars 时直接拒绝。

---

## 7. Failure / idempotency semantics

当前 Microsoft Graph To Do create task API 没有 Chengzhu 可依赖的 provider-side idempotency key。

- 明确 4xx rejection（408/425/429 除外）→ `FAILED`；
- 408 / 425 / 429 / 5xx / timeout / transport exception → `UNKNOWN_OUTCOME`；
- `UNKNOWN_OUTCOME` 禁止自动 retry；
- 用户必须先到 Microsoft To Do 侧核对；
- 只有 `CONFIRMED_NOT_APPLIED` 才能把同一 audit row 变成 retry-safe。

Chengzhu 自己的 execution idempotency key 只用于本地 audit/request 去重，不声称 Microsoft provider 会据此幂等。

---

## 8. Product UI

Prepare / Connector setup 显示 Microsoft To Do、`task.create` only、`Tasks.ReadWrite`、runtime opt-in env、token env variable name、no read sync / no Outlook / no OneDrive，以及 Verify 与 real task.create 的证据区别。

Continue 主链：

    Task Draft
    → Confirm Draft
    → select exact Microsoft To Do connection
    → default / explicit list id
    → Create Execution Request
    → Execute external action

只有 Graph 201 + task id 才显示 direct `SUCCEEDED`。

---

## 9. Public release / evidence boundary

仓库内可以证明：

    MICROSOFT_TODO_ADAPTER_CODE = TRUE
    TASKS_READWRITE_LEAST_PRIVILEGE_CONTRACT = TRUE
    REVIEWED_TWO_STEP_TASK_CREATE = TRUE
    UNKNOWN_OUTCOME_PROTECTION = TRUE
    OUTBOUND_REDACTION_GUARD = TRUE

没有真实 Microsoft OAuth/account replay 时，禁止声明：

    MICROSOFT_ACCOUNT_CONNECTED = TRUE
    REAL_MICROSOFT_TASK_CREATE_PROVEN = TRUE
    REAL_TASK_VISIBLE_IN_TODO_PROVEN = TRUE

真实 provider evidence 至少需要：真实 delegated token、Verify list probe、APPROVED Task Draft、second explicit Execute、Graph 201 + task id；可再人工核对 task 在目标 To Do list 中可见。

---

## 10. 为什么现在只做 To Do task.create

Conversation v2 当前真正缺少的 write capability 是 `Task Draft → real task provider`，不是把 Microsoft Graph 整套生态接进来。

当前适配器 deliberately narrow：

    one DraftAction
    → one capability
    → one exact account
    → one exact target
    → one explicit side effect

后续如果增加 Outlook Calendar / Mail / OneDrive / Planner，必须分别建立最小权限、read/write、snapshot/provenance、failure semantics 和真实 runtime evidence，不能因为 provider_id 都叫 Microsoft Graph 就默认继承。
