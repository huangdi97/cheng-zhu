# Gmail Conversation Connector
## Reviewed send-only provider · v1

**日期**：2026-10-10
**Provider ID**：GOOGLE_MAIL
**能力**：email.send only
**状态**：OPT-IN REAL ADAPTER CODE / REAL ACCOUNT EVIDENCE PENDING

---

## 1. 产品边界

Gmail 在 Chengzhu 中不是 inbox mirror，也不是邮件知识库。

唯一主链：

    Continue
    → FOLLOWUP_EMAIL_DRAFT
    → user reviews local Draft
    → APPROVED
    → exact Gmail account
    → exact single recipient
    → Execution Request
    → second explicit Execute
    → Gmail messages.send
    → SUCCEEDED / FAILED / UNKNOWN_OUTCOME audit

明确不实现 mail.read、gmail.readonly、inbox/thread/message sync、mail snapshot、mailbox search、background polling 或 silent send。

## 2. 最小权限

OAuth 最小权限：openid、email、https://www.googleapis.com/auth/gmail.send。

- openid + email：只用于 OIDC UserInfo identity。
- gmail.send：只用于 reviewed external send。
- 不因为 Verify 需要显示账号而扩大到 gmail.readonly。

## 3. Credential boundary

product.db 只保存 opaque reference：provider:google-mail:env:<ENV_VAR>。

access token 本身不进入 product.db、frontend state、export、execution audit 或 provider response。

Adapter 只有在 CHENGZHU_GOOGLE_MAIL_CONNECTOR_ENABLE=1 时注册。

## 4. Verify semantics

Verify 调 Google OIDC UserInfo endpoint，并要求 HTTP 200、email 存在、email_verified=true、且 email 是单一裸邮箱。

Verify 只证明 Google account identity 与当前 token 的 UserInfo identity health；不证明 email.send 已经成功，更不证明 mailbox readable 或 recipient delivery。

第一次真实 send 的 provider response 才是 email.send execution evidence。

## 5. Draft / target contract

只允许 FOLLOWUP_EMAIL_DRAFT → SEND_EMAIL → email.send。

v1 target 必须是一个明确的裸邮箱地址。拒绝空 target、多收件人、display-name form 与 CR/LF header injection。v1 不支持 Cc/Bcc/multiple recipients。

## 6. MIME contract

使用标准库构造 RFC message：From = verified Gmail account；To = exact reviewed target；Subject = reviewed Draft title；body = reviewed Draft content；UTF-8 plain text；base64url 编码进入 Gmail raw。

X-Chengzhu-Execution-ID 仅用于审计关联，不是 provider-side idempotency guarantee。

## 7. Secret-redaction boundary

如果 shared execution safety 层发现 secret 并导致 outbound 内容与刚审核的 Draft 不同，Gmail adapter 拒绝发送。

正确路径是：remove secret → regenerate/review Draft → new Execution Request → second explicit Execute。

## 8. Failure / idempotency semantics

Gmail messages.send 没有 Chengzhu 可依赖的 provider-side idempotency key。

- 明确 4xx rejection（408/425/429 除外）：FAILED，且不自动重试。
- 408/425/429、5xx、timeout、transport exception：UNKNOWN_OUTCOME，禁止自动重试。
- 用户必须先在 provider 侧核对，再记录 CONFIRMED_SUCCEEDED 或 CONFIRMED_NOT_APPLIED。
- 只有确认外部副作用未发生后，才允许安全重试。

## 9. Product UI

Prepare / Connector setup 显示 send-only、runtime opt-in env、token env variable name、required scopes，以及 no inbox read / no snapshot / no sync。

Verify 后只显示 verified account identity；Continue 中仍需 Follow-up Draft → local APPROVE → exact Gmail connection → single recipient → Execution Request → second Execute。只有 provider 明确成功才显示 SUCCEEDED。

## 10. Evidence truth

仓库内可证明：GMAIL_ADAPTER_CODE、GMAIL_SEND_ONLY_CONTRACT、OIDC_IDENTITY_CONTRACT、REVIEWED_TWO_STEP_SEND、UNKNOWN_OUTCOME_PROTECTION 均成立，MAILBOX_READ=false。

在没有真实 Google OAuth/account replay 前，不得声明 GMAIL_ACCOUNT_CONNECTED、REAL_GMAIL_SEND_PROVEN 或 REAL_RECIPIENT_DELIVERY_PROVEN。Provider accepted send 与真实 delivery 也不是同一个事实。