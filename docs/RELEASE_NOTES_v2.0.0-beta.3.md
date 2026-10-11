# 成竹 Chengzhu v2.0.0-beta.3

## 这是什么版本

v2.0.0-beta.3 是 **Personal Conversation Intelligence** 的第三个 Windows Beta。它把 v2.0.0-beta.2 发布后已经在 `main` 完成的 Conversation 外部上下文、reviewed external execution、Windows packaged 修复与 grounding truth 修复收敛进新的公开候选。

它不会取代当前稳定版 v1.4.2。发布后必须保持：

```text
prerelease = true
latest = false
Stable Latest = v1.4.2
```

因此 beta.3 仍然只代表可安装、可审计、可回滚的工程 Beta，不代表 stable v2、真实用户价值或 PMF 已验证。

---

## 相比 beta.2 的主要变化

### 1. Conversation External Context 从 contract 推进到 concrete opt-in providers

当前 Beta 包含六个 concrete provider：

- **GitHub**：`project.read` + reviewed `issue.create`；
- **Google Calendar**：read-only `calendar.read`；
- **Google Drive / Docs**：read-only `docs.read`；
- **Gmail**：reviewed `email.send` only，不读取 inbox；
- **Microsoft To Do**：reviewed `task.create` only；
- **Local Markdown / Obsidian**：reviewed `decision_log.write` only。

所有 provider 均：

- 默认不自动连接；
- capability 与 provider scope 显式绑定；
- 没有真实 adapter / connected account / exact grant 时 fail-closed；
- credential 不写入 `product.db`；
- Session Pack 的 read permission 与 write execution 分离；
- 外部 snapshot 以 immutable provenance 进入 Space / Frozen Session Pack。

MCP 仍只有 capability contract，不伪装成已有 concrete provider/auth runtime。

### 2. Reviewed Draft 与外部副作用彻底分离

beta.3 冻结以下 runtime truth：

```text
Conversation truth
→ local DraftAction
→ user APPROVE / DISMISS

APPROVED
!= provider side effect

APPROVED
→ exact CONNECTED account
→ Execution Request
→ second explicit Execute
→ provider outcome
```

Preflight / Session Pack / Live Session Pulse 会分别显示：

```text
Reviewed Draft     = LOCAL_REVIEWED_DRAFT / DISABLED
External Execution = EXPLICIT_SECOND_STEP_PROVIDER / DISABLED
```

不会再用一个 `LOCAL_REVIEWED_DRAFT_ONLY` 标签混淆“本地审核”和“真实外部执行”。

### 3. 外部执行有独立审计、幂等与 UNKNOWN_OUTCOME 语义

reviewed write-back 支持：

- exact connection；
- exact target；
- capability re-check；
- execution request；
- second explicit Execute；
- deterministic audit；
- idempotency key；
- `SUCCEEDED / FAILED / UNKNOWN_OUTCOME / BLOCKED / CANCELLED`；
- provider-side reconciliation。

`UNKNOWN_OUTCOME` 不会被伪装成失败，也不会自动重试可能已经发生的副作用。

### 4. GitHub provider 已有真实测试账号 replay

2026-10-11 的本地全量收口已经在专用私有 throwaway repo 完成：

```text
real GitHub account
→ read snapshot
→ immutable frozen Session Pack
→ grounded Manual Ask
→ reviewed CREATE_ISSUE_DRAFT
→ APPROVE
→ explicit owner/repo target
→ second Execute
→ exactly one issue created
```

该证据证明 GitHub provider 的真实测试账号路径成立，但不表示任意用户账号已连接。

Google Calendar / Drive / Gmail / Microsoft To Do 的 adapter 与 fail-closed contract 已有工程覆盖；由于当前没有对应真实账号凭据，仍保持 `REAL_ACCOUNT_EVIDENCE_PENDING`。

### 5. Local Markdown / Obsidian Decision Log

新增 reviewed `decision_log.write` provider：

- root path 仅从本机环境变量解析；
- `product.db` 只保存 opaque credential reference；
- target 必须是 root 下 canonical relative `.md`；
- absolute path / traversal / backslash / symlink escape fail-closed；
- 只有 reviewed DraftAction + second explicit Execute 才能写文件；
- write result 进入 execution audit。

### 6. Windows packaged launch 的真实缺陷已修复

本地全量收口发现：此前 Windows packaged app 的 `desktop/package.json build.files` 漏掉 `overlayLayout.js`，导致 packaged Electron main process 在启动阶段直接失败。

beta.3 已包含：

- packaging manifest 修复；
- local-module/resource packaging regression tests；
- packaged GUI 启动证据；
- clean-install replay；
- portable replay。

### 7. Grounded retrieval 修复数字/版本/金额判别 token

修复了“泛词重合导致错误 grounded”的问题，例如：

```text
3 days  != 30 days
v2      != v3
2026    != 2025
$10k    != $100k
```

数字、版本、金额等 discriminative token 现在必须满足独立 token matching，避免仅凭周边通用词错误命中 frozen source。

### 8. Local Full Closure 与 Stable Promotion Gate

beta.3 包含新的：

- full local closure report；
- migration matrix；
- secret scan；
- real audio / local Whisper evidence；
- packaged / clean-install evidence；
- Conversation stable-readiness evaluator；
- human-label protocol；
- real-pilot manifest template；
- Stable Promotion Policy。

这些工具用于决定“是否有资格进入 stable v2”，而不是把 Beta 自动升级为 stable。

---

## 仍然明确不宣称

beta.3 仍然不代表：

- `V2_PRODUCTIZED_RELEASE = TRUE`；
- `V2_STABLE_RELEASE = TRUE`；
- `REAL_USER_VALIDATED = TRUE`；
- `PMF_PROVEN = TRUE`；
- Google / Microsoft real-account replay 已完成；
- Google OAuth sensitive-scope publication / verification 已完成；
- participant automatic chat notice / watermark 已完成；
- organization/shared team truth registry 已完成；
- Windows code signing 已完成；
- macOS signing/notarization 已完成。

真实用户证据仍必须来自真实 Project Sync / Design Review 使用与 human-label evaluation。

---

## 推荐验证顺序

beta.3 发布后优先验证：

1. Project Sync；
2. Design Review；
3. Recall Precision；
4. Opportunity Precision；
5. Interruption Regret；
6. Useful Silence；
7. Continue / Open Thread continuity value；
8. cognitive load；
9. connector setup / reviewed execution 的真实可理解性。

只有真实 pilot 满足 Stable Promotion Gate 后，才讨论 stable v2。

---

## Release channel

```text
Stable Latest = v1.4.2
Conversation Beta = v2.0.0-beta.3
Stable v2 = NOT CLAIMED
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

## License

MIT。第三方组件保留各自许可证，详见 `THIRD_PARTY_NOTICES.md`。
