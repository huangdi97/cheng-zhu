# 成竹 Chengzhu v1.4.2

## 这是什么版本

v1.4.2 是 **Release provenance closure**。它不增加新的一级产品功能，也不改变 v1.3/v1.4 的 Goal-centered 产品设计。

本版本修复一个在 v1.4.1 发布审计中发现的发布一致性问题：

```text
Windows binaries built from commit A
        ↓
long-running Release workflow
        ↓
main advanced to commit B
        ↓
gh release create vX.Y.Z
(no explicit --target)
        ↓
GitHub created the tag on current main = B
```

因此 v1.4.1 的公开 tag 与当次 Windows 二进制的实际构建源码不是同一个 commit：

```text
v1.4.1 binaries source:
2355a1cdb71d60ae7f5d497150bdcd94499e9a3e

v1.4.1 tag:
df286e768a874eab12365259c50e7742c77c33d9
```

两者之间包含产品代码变化，所以这不是只需要改文档的差异。v1.4.2 重新从一个确定、CI 已验证的 SHA 构建并发布，恢复：

> **tag SHA = binary source SHA = CI-proven source SHA**

## 修复内容

### 1. Release workflow 固定源码 SHA

`workflow_dispatch` 新增：

```text
source_sha
```

自动发布器把刚刚通过 main CI 的准确 `head_sha` 传给 Release workflow。

Release workflow 的 checkout 不再依赖发布期间可能继续变化的 `main`。

### 2. tag 显式绑定构建 SHA

创建 Release 时显式执行等价于：

```text
gh release create v1.4.2 --target <exact-source-sha>
```

不再让 GitHub 从“创建 tag 那一刻的默认分支 HEAD”推断 target。

### 3. 三重 provenance invariant

Release pipeline 在三个阶段检查：

```text
after tag creation
before download-back
before final publish
```

每一步都要求：

```text
release tag SHA
==
CHENGZHU_RELEASE_SOURCE_SHA
```

不相等立即失败，不允许发布。

### 4. download-back evidence 记录 source/tag SHA

下载回验报告新增：

```text
source_sha
tag_sha
```

除了 installer / portable SHA256 和 packaged smoke 之外，现在还可以证明“下载到的资产属于哪个源码快照”。

### 5. 自动发布器改成 CI-SHA 驱动

新增通用：

```text
publish-current-on-green-main
```

逻辑：

```text
main CI success for SHA X
→ checkout SHA X
→ read version from SHA X
→ dispatch Release with source_sha=X
→ Release builds SHA X
→ tag points SHA X
```

以后不需要为每个补丁版本复制一份“publish-vX.Y.Z”逻辑。

### 6. CI 防回归

`scripts/check_release_version.py` 除了检查 frontend / desktop / lockfile / backend sidecar 版本一致，还检查：

- Release workflow 是否接受 `source_sha`；
- 是否使用 `CHENGZHU_RELEASE_SOURCE_SHA`；
- 是否通过 `--target $sourceSha` 创建 tag；
- auto-publisher 是否传入刚刚通过 CI 的 `workflow_run.head_sha`。

删除这些保护会直接使 CI 失败。

## 产品与设计

v1.4.2 不改变：

- Goal-centered IA
- Action Home
- Goal Room / Next Focus
- Person Workspace / Fact Inbox
- Quick Notes / Question Banks
- Practice 3.0 / Panel / Rubrics
- Content Coach × Delivery Coach
- Preflight 3.0
- Fast Cue before Deep
- Pin / Nudge / Closing Mode
- Overlay 3.0
- Reflection → Next Focus
- Local-first v1.4 validation
- Personal Conversation Intelligence Future Profile boundary

## 仍然诚实保留的边界

```text
REAL_USER_EVIDENCE_PENDING
PMF_PROVEN = FALSE
REAL_INTERVIEW_TRANSFER_PROVEN = FALSE
```

以及：

- Windows 代码签名证书；
- macOS signing / notarization；
- native interactive multi-monitor Overlay proof；
- public Human Coach relay；
- 真实长期用户；
- 真实付费 provider 的质量 / 延迟 / 成本矩阵；
- 真实多小时会话。

这些不是通过 synthetic 或 CI 可以制造出来的证据。

## 升级建议

请优先使用 v1.4.2 或更高版本。v1.4.1 的产品功能本身仍可运行，但其公开 tag 与发布二进制的源码 provenance 不一致，不再作为推荐的可复现发布基线。
