# GitHub Conversation Connector
## Chengzhu v2 · first opt-in real external provider

**状态**：REAL ADAPTER CODE AVAILABLE / OPT-IN / REAL ACCOUNT EVIDENCE PENDING  
**Provider**：GitHub REST API  
**Capabilities**：`project.read` / `issue.create`

---

## 1. 为什么先做 GitHub

GitHub 同时覆盖两条最小但完整的外部集成路径：

```text
read:
repository issue
→ immutable external snapshot
→ Space selection
→ Session Pack
→ Manual Ask / Prepare / provenance

write:
reviewed CREATE_ISSUE_DRAFT
→ exact account
→ explicit owner/repo
→ Execution Request
→ second Execute
→ GitHub issue
→ external execution audit
```

因此它可以验证 Chengzhu 的 read/write 边界，而不需要先引入 Calendar + Mail + Task 三套 OAuth/runtime。

---

## 2. 默认仍然关闭

仅代码存在不代表 provider 已连接。

默认：

```text
CHENGZHU_GITHUB_CONNECTOR_ENABLE unset
→ adapter not registered
→ adapter_available = false
→ no account connected
→ no external call
```

显式启用：

```text
CHENGZHU_GITHUB_CONNECTOR_ENABLE=1
```

然后重启后端。

---

## 3. Credential boundary

推荐使用 GitHub fine-grained personal access token 或后续 GitHub App credential。

当前 adapter 只支持 env-backed opaque reference。GitHub API base 必须是 HTTPS，adapter 不自动跟随 HTTP redirect，避免 Authorization 被带到其他目标：

```text
provider:github:env:CHENGZHU_GITHUB_TOKEN
```

真实 token：

```text
CHENGZHU_GITHUB_TOKEN=<secret>
```

只存在后端进程环境。

禁止：

- 在 Connector UI 粘 token；
- 把 token 写进 product.db；
- 把 token 放进 account_hint；
- 把 Authorization header 写进 snapshot / audit；
- 把 token 导出到 Space/Session export。

---

## 4. 最小权限

如果只读 issue：

```text
project.read
→ GitHub repository permission: Issues = Read
```

如果需要真实创建 issue：

```text
issue.create
→ GitHub repository permission: Issues = Write
```

连接时 granted capability 必须与 provider scope contract 一致。GitHub fine-grained permission 是单一等级：只读记录为 `Issues: read`；只要包含 `issue.create`，最小 provider permission 记录为 `Issues: write`，它覆盖 issue read。

---

## 5. Verify

Connection 创建后仍然是：

```text
DISCONNECTED
```

点击“验证连接”后 adapter 会：

```text
resolve env credential reference
→ GET /user
→ explicit provider success
→ save safe account_hint (login)
→ CONNECTED
```

这里的 `CONNECTED` 只证明：

- opaque credential 可以解析；
- GitHub 身份认证成功；
- adapter/account health 成功。

它**不声称**某个具体 `owner/repo` 的 Issues read/write 已经被无副作用验证。目标仓库的 read 能力由真实 Sync 请求证明；write 能力只有第二次显式 Execute 的真实 provider 响应才能证明。

不会保存 token。

---

## 6. Read sync

GitHub read target 必须每次显式指定：

```text
owner/repo
```

请求：

```text
GET /repos/{owner}/{repo}/issues
```

如果某个目标仓库返回 403/404/422 等 target-specific client rejection，只记录该目标失败；已经通过 `/user` 的账号连接不会因此被整体降成 ERROR。401 / transport / provider-level failure 仍按账号或 provider 错误处理。

规则：

- 只导入 issue；
- GitHub issues endpoint 中混入的 pull request 必须过滤；
- 可按 state / labels 过滤；
- 使用 updated_at cursor，并带 1 秒 overlap 防止同秒更新遗漏；
- snapshot identity 仍由 Chengzhu canonical content hash 控制；
- source URL 进入 product.db 前去掉 query / fragment / userinfo；
- snapshot 默认 authority = REFERENCE_SOURCE；
- GitHub issue 不能自动升级成 Decision / Commitment / Deadline。

---

## 7. Write execution

只有：

```text
CREATE_ISSUE_DRAFT
+ status APPROVED
+ GITHUB connection CONNECTED
+ issue.create granted
```

才允许建立 Execution Request。

第二次显式 Execute 前，还必须填写：

```text
owner/repo
```

不会从：
- 当前 Space 名；
- 最近 Sync；
- account_hint；
- 历史 execution

自动猜目标。

Execution Request 还会在进入 provider adapter 前执行通用 outbound secret sanitization。若本地已审核 Draft 含 token/secret-shaped value：

- audit/request 只保存脱敏后的 provider payload；
- GitHub adapter 只收到脱敏后的 payload；
- `outbound_redaction_applied=true`；
- Continue UI 在第二次 Execute 前显式提示用户实际外发内容已被脱敏。

成功条件：

```text
POST /repos/{owner}/{repo}/issues
→ HTTP 201
→ issue number present
→ adapter ok=true
→ SUCCEEDED
```

issue body 会带不可见 marker：

```html
<!-- chengzhu-execution:<idempotency-key> -->
```

用于 provider-side reconciliation。它不表示 GitHub 原生提供幂等 create-issue API。

---

## 8. Failure semantics

明确 4xx provider rejection：

```text
FAILED
retry_safe = false
```

transport error / timeout / GitHub 5xx / malformed success：

```text
UNKNOWN_OUTCOME
```

原因：

> provider 可能已经接受 side effect，但 Chengzhu 没拿到确定结果。

UNKNOWN_OUTCOME 禁止直接 retry。

必须：

```text
provider-side check
→ reconciliation
→ CONFIRMED_SUCCEEDED
   or CONFIRMED_NOT_APPLIED
```

只有 `CONFIRMED_NOT_APPLIED` 才允许把同一个 audit row 标成 retry-safe。

---

## 9. Product UI

Conversation Space → Prepare → External Context：

1. 先在操作系统/启动环境设置 token；
2. 启动时显式开启 GitHub connector；
3. UI 只填写 token 的**环境变量名**；
4. 填 `owner/repo`；
5. 选择 Issues read / write capability；
6. 创建 connection metadata；
7. Verify；
8. Read Sync；
9. 逐条选择 immutable snapshot；
10. Preflight / Session Pack freeze。

Continue → Issue Draft：

1. 生成本地 Draft；
2. 用户 Review；
3. APPROVE；
4. 选 GitHub connected account；
5. 再填一次明确 `owner/repo`；
6. 创建 Execution Request；
7. 第二次点击 Execute；
8. 只有 provider 明确成功才显示 SUCCEEDED。

---

## 10. Evidence boundary

仓库单测 / E2E 可以证明：

```text
GITHUB_ADAPTER_CODE_AVAILABLE = TRUE
GITHUB_HTTP_CONTRACT_TESTED = TRUE
GITHUB_UI_SETUP_FLOW_TESTED = TRUE
GITHUB_READ_WRITE_BOUNDARY_TESTED_WITH_FAKE_HTTP = TRUE
```

没有用户提供真实 GitHub credential 和真实仓库 runtime replay 时，禁止声明：

```text
GITHUB_ACCOUNT_CONNECTED = TRUE
REAL_GITHUB_SYNC_EVIDENCE = TRUE
REAL_GITHUB_ISSUE_CREATED = TRUE
REAL_EXTERNAL_ACTION_EVIDENCE = TRUE
```

这些必须由本机真实 provider run 产生。
