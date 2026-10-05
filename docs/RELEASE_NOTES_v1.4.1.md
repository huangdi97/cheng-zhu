# 成竹 Chengzhu v1.4.1

## 这是什么版本

v1.4.1 是 v1.4.0 的产品闭环修复，不增加新的一级功能。

它关闭最终 Friction Audit 中发现的一条真实断链：

```text
正式 Live
→ 结束面试
→ Verified realtime core 已停止
→ 但 Goal session / Reflection 产品层没有被正式 stop action 收尾
```

## 修复

### 正式 Live → Reflection

现在点击 **结束面试** 会按一个完整产品动作执行：

```text
POST /api/stop
→ productApi.liveEnd(session_id)
→ 关闭 Goal Session link
→ 清理本场 session overrides
→ 记录 live_completed
→ 绑定真实 review_session
→ 自动进入 Reflection
```

正常路径不再要求用户先去“历史”寻找刚刚结束的面试。

这使 Canonical 的交互预算真正成立：

```text
End Session → Reflection <= 1
```

正常情况为：

```text
结束面试
→ 自动进入 Reflection
```

即 **0 个额外操作**。

### Review 尚未生成时

如果 realtime core 已经成功结束，但 review row 还未就绪：

- 不伪造 Reflection；
- 自动回到当前 Goal 的「面试」；
- 明确提示“复盘正在生成”。

### 产品层关联失败时

如果录音已经停止，但 product-session 收尾失败：

- 不错误显示“结束面试失败”；
- 清除 stale Live UI；
- 进入「历史」；
- 给出明确的复盘关联错误提示。

### Renderer reload 恢复

如果 Live 期间 renderer 被刷新、内存中的 `osStore.live` 丢失：

- 从 `#/live/:sessionId` 恢复真实 session id；
- 仍然可以正确执行 Live → Reflection 收尾。

## Friction Audit

新增：

```text
reports/CHENGZHU_V1_4_FRICTION_AUDIT.md
```

六条 Canonical interaction budgets：

- Home → Practice
- Goal → Go Live
- Live → Quick Notes
- Live → Pin
- End Session → Reflection
- Reflection → Next Focus → Practice

全部按工程路径逐条核验。

该报告是 **工程/设计路径证据**，不是用户研究。

仍然保留：

```text
REAL_USER_EVIDENCE_PENDING
```

## 未改变的边界

v1.4.1 不改变：

- Frozen InterviewPack
- Context Compiler authority
- Provenance / Assertion / Session Statement
- Stream Truth Guard
- Fast Cue before Deep
- Share Privacy default OFF
- Human Coach policy
- Goal-centered IA
- Personal Conversation Intelligence Future Profile boundary

## 发布

Windows Release 继续要求：

- frontend / desktop / packaged backend sidecar 版本一致；
- backend / frontend / desktop / E2E / visual 全绿；
- bundled sidecar smoke；
- installer / portable；
- clean installer replay；
- SHA256；
- GitHub Release download-back；
- 安装后 packaged smoke。

代码签名证书、macOS signing/notarization、真实长期用户、真实付费 provider 与真实多小时会话仍属于外部证据。
