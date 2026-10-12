# 成竹 Chengzhu v2.0.0-beta.5

## 版本定位

v2.0.0-beta.5 是 **Personal Conversation Intelligence** 的 pre-pilot hardening Windows Beta。

它不继续扩大 Conversation 功能面。相对已发布 beta.4，本版本只把两类已经在 main 完成并经过独立工程验证的收口带进新的可下载安装包：

1. **dependency / build-release security hardening**；
2. **Stable evidence cohort-binding hardening（policy v4）**。

发布后仍必须保持：

```text
prerelease = true
latest = false
Stable Latest = v1.4.2
V2_STABLE_RELEASE = FALSE
PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

beta.5 的目标是成为下一阶段授权真实 Project Sync / Design Review pilot 的统一二进制与评测工具基线，而不是用更多 Beta 功能替代真实验证。

---

## 相比 beta.4 的变化

### 1. Scope-aware npm dependency security gate

CI 不再把 `npm audit` 总数直接描述成 packaged-runtime 风险，而是分别审计：

```text
frontend production graph
frontend full dev/build graph
desktop full graph
Electron shipped runtime exception
```

当前冻结结果：

```text
Frontend production:
  total = 0
  high = 0
  critical = 0

Frontend full:
  moderate = 2
  high = 6
  critical = 0

Desktop full:
  moderate = 8
  high = 0
  critical = 0

Electron runtime blocking = 0
Desktop build/toolchain high = 0
```

Frontend full 中剩余 high findings 位于 Tailwind 3 dev/build graph。它们不会被伪装为用户安装包中的同等 runtime 漏洞；本版本也不会为了把审计计数变成 0 就强行做 Tailwind 4 大版本 UI/build 迁移。

### 2. electron-builder 25.1.8 → 26.17.0

Desktop build/release toolchain 升级至：

```text
electron-builder = 26.17.0
```

升级前的 desktop full audit 为：

```text
12 high
1 critical
```

升级后：

```text
0 high
0 critical
8 moderate
```

这是 build/release supply-chain hardening，不改变 Chengzhu Conversation 的业务真值、权限边界或外部执行语义。

### 3. Vite 6.4.3 → 6.4.4

Frontend 升级：

```text
vite 6.4.3
→
vite 6.4.4
```

使用 npm 实际解析生成的 exact lockfile，不手工改 integrity/hash。

Vite 6.4.4 是 6.4 line 对 6.4.3 及更早版本近期 dev-server 安全问题的修复版本；该 patch 不改变生产 runtime architecture。

### 4. Third-party notices 与真实 lockfile 对齐

`THIRD_PARTY_NOTICES.md` 与当前：

- Frontend Vite 6.4.4 exact lock；
- Desktop electron-builder 26.17.0 exact lock；
- Backend Python dependency truth；

保持一致。

Release license gate 仍然是硬门禁。

---

## Stable evidence policy v4：绑定真实授权 pilot cohort

beta.4 发布时冻结的是 Stable Promotion Policy v3。beta.5 收入其后的 evaluator hardening：

```text
STABLE_PROMOTION_POLICY = v2.0-R1-stable-promotion-4
NUMERICAL_THRESHOLDS_CHANGED_FROM_V3 = FALSE

HUMAN_REPORT_CONTRACT = v2.0-R1-human-eval-4
PILOT_MANIFEST_CONTRACT = v2.0-R1-pilot-cohort-2
```

### 5. 不再信任手填的聚合 pilot 数字

旧 manifest 可手填：

```text
distinct_users
sessions
cross_session_spaces
```

policy v4 改为逐场枚举：

```json
{
  "session_id": "cv_...",
  "space_id": "cs_...",
  "user_ref": "local-pseudonym-01"
}
```

Evaluator 从逐场 row 自动推导：

- distinct users；
- sessions；
- cross-session spaces。

`user_ref` 只能是本地稳定匿名代号，不应填写姓名、邮箱；它不是身份认证，也不把 Chengzhu 变成 identity-verification system。

### 6. Human labels 必须属于 authorized pilot cohort

Stable readiness 不再接受“两份各自好看的证据”被错误拼接。

每一个 human-report Session 必须与 pilot manifest 精确匹配：

```text
session_id
+
profile
+
space_id
```

否则 fail closed。

`AUTHORIZED_REAL_USE` attestation 仍然必须存在；cohort binding 提高的是 consistency / auditability，不是密码学身份认证。

### 7. 只允许首发目标 Profile 进入 Stable 指标

Stable metric population 固定为：

```text
PROJECT_SYNC
DESIGN_REVIEW
```

Presentation/Q&A、1:1、Client Call、Negotiation 或其它 Profile 的高分不能抬高首发 Stable Gate。

### 8. 每个 Stable 指标必须覆盖两个 launch profile

不是“总 n 足够”就可以。

每一个 Stable metric 都必须在：

```text
Project Sync
+
Design Review
```

两边都有 policy-allowed sample。

因此，一个已充分评测的 Project Sync 不能替代完全没测的 Design Review，反之亦然。

### 9. Pilot period 必须是 timezone-aware ISO-8601

manifest 的：

```text
started_at
ended_at
```

必须带时区，并满足 started_at <= ended_at。

旧 count-only manifest 在 policy v4 下 fail closed。

### 10. 数值阈值没有降低

policy v4 不修改 beta.4 / policy v3 已冻结的数值阈值，也不在看到真实 pilot 结果后扩宽样本人口。

它是 **real-pilot 之前的 evidence-design correction**，不是 post-hoc 调参。

---

## beta.4 已有产品能力保持不变

beta.5 继承 beta.4 已发布的：

- schema v10 immutable AI prediction snapshot；
- local explicit Pilot Feedback Bridge；
- schema v11 Direct Question capture-time prediction provenance；
- schema v12 auto-runtime Guidance/SILENT provenance；
- feedback retention integrity；
- reviewed Draft 与 explicit second-step external execution 分离；
- GitHub / Google Calendar / Google Drive / Gmail / Microsoft To Do / Local Markdown provider runtime；
- Manual + explicit-start AUTO Screen Context；
- Conversation Human Coach；
- desktop Share Privacy / Private Overlay runtime boundary。

本版本不扩展这些产品能力。

---

## beta.4 provenance 保持不可变

已发布 beta.4：

```text
v2.0.0-beta.4
source/tag =
0e1d89ad381a93c1dcd9725418d9cbd5b3c71fcc
```

不得把 beta.5 的 security / policy-v4 hardening 倒写成 beta.4 已包含能力。

beta.5 必须从全新的 exact green main SHA 重建、重新安装、download-back、reinstall、packaged-smoke，并使用全新的 tag。

---

## 仍然明确不宣称

beta.5 不代表：

- `V2_STABLE_RELEASE = TRUE`；
- `PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = TRUE`；
- `REAL_USER_VALIDATED = TRUE`；
- `PMF_PROVEN = TRUE`；
- Google Calendar / Drive / Gmail / Microsoft To Do real-account replay 已完成；
- Google OAuth sensitive-scope publication / verification 已完成；
- Windows code signing 已完成；
- macOS signing / notarization 已完成。

外部账号当前事实仍是：

```text
GitHub real throwaway replay = PASS
Local Markdown = local runtime
Google Calendar = BLOCKED_ACCOUNT
Google Drive = BLOCKED_ACCOUNT
Gmail = BLOCKED_ACCOUNT + external OAuth publication gate
Microsoft To Do = BLOCKED_ACCOUNT
```

---

## beta.5 后的正确下一步

beta.5 之后停止继续通过新的产品功能替代真实验证。

优先进入授权真实：

1. Project Sync pilot；
2. Design Review pilot；
3. 逐场 cohort manifest（local pseudonym）；
4. in-product explicit self-report；
5. independent human review；
6. policy v4 stable-readiness；
7. Google / Microsoft real-account replay（有账号/凭据时）；
8. critical privacy / data-loss incident = 0；
9. 只有 evidence thresholds 全部通过后才进入 stable review。

即使 Stable Gate PASS，也只是允许 **stable release review**，不会自动发布 stable，也不证明 PMF。

---

## Release gate

beta.5 必须完整复用 exact-SHA Windows release path：

```text
green main SHA
==
release checkout SHA
==
installer / portable source SHA
==
public tag SHA
```

并通过：

- Backend / Frontend / Desktop；
- dependency-security；
- Playwright / visual regression；
- e2e smoke；
- packaged smoke；
- Windows installer + portable build；
- clean-install replay；
- draft GitHub Release；
- asset SHA256 download-back；
- downloaded installer reinstall；
- downloaded packaged smoke；
- prerelease channel verification；
- Stable Latest preservation；
- post-publish verification metadata regression。

---

## Release channel

```text
Stable Latest = v1.4.2
This candidate = v2.0.0-beta.5 prerelease
Stable v2 = NOT CLAIMED
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

## Windows signing

当前 Windows Beta 仍为 unsigned engineering/prerelease distribution。Windows SmartScreen 警告仍可能出现；这与 runtime correctness / release provenance 是不同的发布层问题。

## License

MIT。第三方组件保留各自许可证，详见 `THIRD_PARTY_NOTICES.md`。
