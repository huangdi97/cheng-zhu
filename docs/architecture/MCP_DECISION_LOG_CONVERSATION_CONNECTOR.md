# MCP Decision Log Conversation Connector
## Reviewed decision_log.write provider · v1

**日期**：2026-10-10  
**Provider ID**：`MCP`  
**Concrete capability**：`decision_log.write` only  
**Protocol**：MCP `2026-07-28` Streamable HTTP  
**状态**：OPT-IN REAL ADAPTER CODE / REAL SERVER EVIDENCE PENDING

---

## 1. 为什么只做 Decision Log

成竹的 MCP catalog 是协议级 capability contract，不等于任意 MCP server 都已经接线。

当前 concrete adapter 只关闭一个真实产品缺口：

    UPDATE_DECISION_LOG_DRAFT
    → user review
    → APPROVED
    → exact MCP connection
    → explicit external decision-log target
    → Execution Request
    → second explicit Execute
    → fixed verified MCP tool
    → SUCCEEDED / FAILED / UNKNOWN_OUTCOME audit

它不会把 MCP 变成任意工具执行器。

---

## 2. Protocol revision

当前 adapter 明确实现现代 MCP `2026-07-28`：

- 每个请求携带 protocol metadata；
- `server/discover` 发现 server capability / supported version；
- `tools/list` 验证 exact configured tool；
- `tools/call` 执行 reviewed external write。

官方参考：

- https://blog.modelcontextprotocol.io/posts/2026-07-28/
- https://modelcontextprotocol.io/specification/2026-07-28
- https://ts.sdk.modelcontextprotocol.io/v2/protocol-versions

当前不手写 legacy `initialize` / `Mcp-Session-Id` fallback。若 server 只支持 2025-era protocol，Verify fail-closed。

这是 deliberate boundary：不通过猜测旧 session 行为来冒充兼容。

---

## 3. Config / secret boundary

`product.db` 只保存：

    provider:mcp:env:<CONFIG_ENV>

Config env 示例：

    {
      "endpoint": "https://mcp.example.com/mcp",
      "tool_name": "chengzhu_update_decision_log",
      "bearer_token_env": "CHENGZHU_MCP_BEARER_TOKEN",
      "account_hint": "work-mcp"
    }

Config env 不允许直接包含 token / secret。

如果 server 需要 bearer token，真实 token 只存在于 `bearer_token_env` 指向的独立 process env。

Endpoint 规则：

- 公网/非 loopback 必须 HTTPS；
- localhost / loopback 开发服务允许 HTTP；
- userinfo / query / fragment 禁止进入 endpoint；
- UI 不读取 endpoint、tool name 或 token。

---

## 4. Fixed tool contract

Verify 必须真实执行：

    server/discover
    → tools/list
    → find exact configured tool_name
    → validate inputSchema

tool 必须接受 object properties：

- `title: string`
- `content: string`
- `target: string`
- `idempotency_key: string`

前端不能：

- 临时输入 tool name；
- 切换任意 MCP tool；
- 把 external target 当 tool name；
- 绕过 capability grant 调别的 tool。

---

## 5. Reviewed execution payload

APPROVED Decision Log Draft 才能进入 execution。

传给 MCP tool 的 canonical arguments：

    {
      "title": "<reviewed draft title>",
      "content": "<reviewed draft content>",
      "target": "<explicit external decision-log target>",
      "idempotency_key": "<Chengzhu execution key>"
    }

成竹不会自动附加未审核的 metadata / private transcript / raw source snapshot。

如果 outbound safety 层改写了 reviewed Draft，adapter fail-closed，要求重新审核。

---

## 6. Idempotency / failure semantics

`idempotency_key` 会作为 tool argument 发送，但 MCP 协议本身不保证 server/tool 真正执行幂等。

因此当前声明：

    provider_idempotency = UNVERIFIED_APPLICATION_ARGUMENT

分流：

- local config / target / schema failure → FAILED, retry_safe=false；
- `server/discover` / `tools/list` 的 429/5xx/transport failure → pre-write FAILED, retry_safe=true；
- `tools/call` 明确 JSON-RPC 4xx 或 `isError=true` → FAILED, retry_safe=false；
- `tools/call` timeout / transport close / 429 / 5xx / malformed/non-final outcome → UNKNOWN_OUTCOME；
- UNKNOWN_OUTCOME 禁止自动 retry，必须先在 provider 侧核对。

---

## 7. MRTR / Tasks boundary

现代 MCP 允许 `input_required` 与 Tasks extension。

成竹 v1 external write-back 不驱动这些多轮/异步结果。

若 decision-log tool 返回非 final `resultType`：

    UNKNOWN_OUTCOME / fail-closed

不会：

- 自动替用户回答 elicitation；
- 自动轮询 task；
- 把中间态当 SUCCEEDED。

---

## 8. Evidence boundary

仓库内可以证明：

    MCP_DECISION_LOG_ADAPTER_CODE = TRUE
    MCP_MODERN_PROTOCOL = 2026-07-28
    FIXED_TOOL_MAPPING = TRUE
    EXACT_TOOL_SCHEMA_VERIFY = TRUE
    REVIEWED_TWO_STEP_DECISION_LOG_WRITE = TRUE
    UNKNOWN_OUTCOME_PROTECTION = TRUE

没有真实 MCP server/runtime replay 时，禁止声明：

    REAL_MCP_SERVER_CONNECTED = TRUE
    REAL_DECISION_LOG_WRITE_PROVEN = TRUE

真实 provider evidence 至少需要：

1. 真实 modern MCP endpoint；
2. `server/discover` 成功；
3. exact `tools/list` schema verify；
4. APPROVED Decision Log Draft；
5. exact external target；
6. second explicit Execute；
7. final `tools/call` success result；
8. 可选 provider-side record verification。
