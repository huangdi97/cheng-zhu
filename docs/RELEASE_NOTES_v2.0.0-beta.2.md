# 成竹 Chengzhu v2.0.0-beta.2

## 发布通道

这是 **Conversation Beta 第二个 Windows 预发布候选**，不是稳定版、也不是六种场景真实用户效果的证明。

- `prerelease=true`，`latest=false`；
- GitHub Stable Latest 继续保持 `v1.4.2`；
- 公开发布必须通过 final-head CI、Windows clean package、packaged UI evidence、download-back SHA256、安装/启动冒烟和 Git tag → immutable source SHA 取证；
- 若任一门禁失败，不能标记为已发布。

## 从 beta.1 到 beta.2

### 1. Conversation Live 音频状态一致性

- 串行化 Live 状态轮询，防止慢请求交错；
- start / pause / stop / end 会使之前发出的状态响应失效；
- 切换 Session 时必须核对 backend 返回的 `session_id` 才展示音频所有权；
- 操作进行中显示更新状态；后端不可达时展示 UNKNOWN，而不是错误声明录音已停止。

### 2. 六种 Profile-specific Playbooks

Project Sync、Design Review、Presentation / Q&A、1:1、Client Call 和 Negotiation 共用 Conversation Core，但具有各自的：

- success conditions；
- priority truth types；
- Prepare prompts；
- closing objective；
- explicit behavioral boundaries。

Playbook 从 Template Picker 进入 Prepare，开始 Session 时冻结进 Session Pack，Live 使用冻结副本，Continue 只呈现已审阅的结果证据。

### 3. 历史一致性与证据边界

- Continue 读取本场冻结的 Playbook，而不是当前最新模板；后续模板变更不会追溯改写本场结果定义；
- 未确认候选不得提升为已完成事实；reviewed output counts 不是会议质量/成功率/就绪度评分；
- 新增针对模板变化和采集状态异步竞态的工程回归测试；
- Interview 已验证的 v1.4 核心仍须通过共享回归测试，不因 Beta 改动宣称真实用户验证。

## 已存在的 Conversation Beta 主循环

```text
Conversation Home → Space → Next Focus → Prepare → Preflight
→ Frozen Session Pack → Participate → Continue → Next Focus → same Space
```

审阅后的 Decision / Commitment / Task / OpenQuestion / Risk、可追溯 Open Thread、人工 Screen Context、Session Policy、Manual Ask、真实音频转写桥及本地草稿继续使用 v2.0 Beta 的明确来源和权限边界。

## 仍未宣称可用

- Conversation AUTO Screen Context、Human Coach、Private Overlay 与 Share Privacy 自动保护；
- Calendar / Mail / Docs / 项目工具外部连接与真实发送/写回；
- 自动向第三方发送参与者同意通知；
- 真实麦克风/系统音频/第三方会议软件的全设备矩阵验收；
- 真实用户效用、认知负担改进、迁移效果或 PMF。

## 下载与回滚

从对应的 `v2.0.0-beta.2` GitHub **Pre-release** 页面下载签名/校验元数据与 Windows 安装包或便携版。仅当发布资产存在且下载回验通过时才可称为 Beta 发布。测试前备份本地数据，关闭正在进行的转写会话；如需稳定通道，回到 `v1.4.2` Stable Latest。

`BETA_ENGINEERING_EVIDENCE != REAL_USER_VALIDATED`。
