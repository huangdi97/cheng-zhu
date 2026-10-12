# 成竹 Chengzhu v2.0.0-beta.5

## 这是什么版本

v2.0.0-beta.5 是 **Personal Conversation Intelligence** 的 post-beta.4 hardening Windows Beta 候选。

它不继续扩大 Conversation 用户功能面；它把 beta.4 发布后已经在当前 main 收口的两类 hardening 一起带进新的可下载安装包：**依赖安全分层审计 / Desktop builder / Frontend Vite hardening**，以及 **Stable Promotion evaluator 的 authorized-cohort binding policy v4**。beta.4 的 tag/source 与其发布时 policy v3 provenance 保持不可变。

发布后仍必须保持：

```text
prerelease = true
latest = false
Stable Latest = v1.4.2
V2_STABLE_RELEASE = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

beta.5 的目的，是让下一阶段真实 Project Sync / Design Review pilot 使用与当前 hardened main **以及当前 evaluator contract** 一致的二进制，而不是继续用 beta.4 的旧 build-tool surface / policy-v3 evaluator。

---

## 相比 beta.4 的主要变化

### 1. npm security gate 从“总数”改为执行面分层

CI 新增 scope-aware npm dependency security gate，分别审计：

```text
frontend production graph
frontend full dev/build graph
desktop full graph
Electron shipped runtime exception
```

这避免把开发/构建工具链的 advisory 总数错误描述成“用户安装包中存在同等数量的 runtime 高危漏洞”。

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

Electron runtime blocking:
  0

Desktop build/toolchain high:
  0
```

Frontend full 中剩余 findings 位于 Tailwind 3 dev/build graph。它们不会被伪装为 packaged-runtime 漏洞；也不会为了把 audit 计数变成 0 就在本版本强行迁移 Tailwind 4。

### 2. electron-builder 25.1.8 → 26.17.0

Desktop builder toolchain 升级到 maintained v26 line：

```text
electron-builder = 26.17.0
```

升级前的 desktop full audit：

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

Electron runtime 本身没有新增 blocking high/critical finding。

这是一项 build/release supply-chain hardening；它不意味着成竹的业务逻辑或用户数据权限发生变化。

### 3. Vite 6.4.3 → 6.4.4

Frontend build/dev server 升级：

```text
vite 6.4.3
→
vite 6.4.4
```

使用 npm 真实解析生成的 lockfile，不手工编辑 integrity/hash。

该 patch 关闭当前 6.4.x line 中 beta.4 之后识别出的 dev-server advisory exposure，同时保持现有 React/Vite architecture，不进行大版本框架迁移。

### 4. License / notices 与真实 lockfile 同步

`THIRD_PARTY_NOTICES.md` 重新与：

- Frontend Vite 6.4.4 exact lock；
- Desktop electron-builder 26.17.0 exact lock；
- Backend Python dependency truth；

对齐。

Release license gate 仍然保留，不因为 security upgrade 放松许可检查。

### 5. Stable Promotion evaluator policy v4 cohort binding

beta.4 发布后继续审计 Stable evaluator，发现旧 count-only pilot manifest 与 human-report cohort 可以在结构上被错误拼接，而且非首发 Conversation Profile 的漂亮指标理论上可以抬高首发 Stable Gate。

当前 main 已升级为：

```text
STABLE_PROMOTION_POLICY = v2.0-R1-stable-promotion-4
HUMAN_REPORT_CONTRACT = v2.0-R1-human-eval-4
PILOT_MANIFEST_CONTRACT = v2.0-R1-pilot-cohort-2

HAND_ENTERED_PROFILE_COUNTS = FORBIDDEN
PROFILE_COUNTS = DERIVED_FROM_ENUMERATED_SESSIONS
HUMAN_LABEL_SESSION_MEMBERSHIP = exact session_id + profile + space_id
STABLE_METRIC_PROFILES = PROJECT_SYNC + DESIGN_REVIEW
EACH_STABLE_METRIC_REQUIRES_BOTH_LAUNCH_PROFILES = TRUE
OUT_OF_SCOPE_PROFILE_SCORE_INFLATION = FORBIDDEN
```

数值阈值没有因 v4 放宽。v4 只强化 evidence cohort / population binding，并继续保持本地匿名 `user_ref`；它不是身份认证，也不证明真实用户价值或 PMF。

### 6. beta.4 provenance 保持不可变

已发布 beta.4：

```text
v2.0.0-beta.4
source/tag =
0e1d89ad381a93c1dcd9725418d9cbd5b3c71fcc
```

不会被改写成“已经包含 beta.5 security hardening”。

beta.5 必须从新的 exact green main SHA 重新 build、clean-install、download-back、reinstall、packaged-smoke，并使用新的 tag。

---

## beta.4 已有的 Conversation 能力保持不变

beta.5 继承 beta.4 已发布的 Conversation runtime，同时采用 post-beta.4 的 Stable evaluator policy v4：

- schema v10 immutable AI prediction snapshot；
- local explicit Pilot Feedback Bridge；
- schema v11 Direct Question capture-time prediction provenance；
- schema v12 auto-runtime Guidance/SILENT provenance；
- feedback retention integrity；
- beta.4 runtime 中的 Stable Promotion Policy v3 provenance；beta.5 evaluator 使用 policy v4 cohort binding；
- reviewed Draft 与 explicit second-step external execution 分离；
- GitHub / Google Calendar / Google Drive / Gmail / Microsoft To Do / Local Markdown provider runtime；
- Manual + explicit-start AUTO Screen Context；
- Conversation Human Coach；
- desktop Share Privacy / Private Overlay runtime boundary。

本版本没有因为安全 hardening 修改这些产品 truth。

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

beta.5 之后停止继续通过“更多 Beta 功能”替代真实验证。

优先进入：

1. 授权真实 Project Sync pilot；
2. 授权真实 Design Review pilot；
3. in-product explicit self-report；
4. independent human review；
5. frozen Stable Promotion Policy v3；
6. real-account connector replay（有账号/凭据时）；
7. critical privacy / data-loss incident = 0；
8. Stable review only after evidence thresholds pass。

仍然没有足够真实用户证据时，继续保持 prerelease，不升级 stable。

---

## Release gate

beta.5 必须完整复用现有 exact-SHA Windows release path：

```text
green main SHA
==
release checkout SHA
==
installer / portable source SHA
==
public tag SHA
```

同时必须通过：

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
