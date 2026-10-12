# 成竹 Chengzhu v2.0.0-beta.6

## 这是什么版本

v2.0.0-beta.6 是 **Personal Conversation Intelligence** 的 real-pilot operationalization Windows Beta 候选。

beta.5 已经把 schema v10–v12 Pilot Evidence Bridge、dependency-security hardening 与 authorized-cohort Stable evaluator 打进公开 Beta；beta.6 不继续扩大 Conversation 功能面，而是解决真实 pilot 的两个执行问题：

1. 用户结束真实 Session 后，反馈入口不能藏在回到 Space 之后的折叠区；
2. operator 不能为了找到可进入 cohort 的 Session 而手工翻 SQLite 或打开私密 transcript。

因此 beta.6 的产品侧重点是：

```text
End Session
→ Continue
→ immediate Quick Debrief
→ optional detailed Guidance / SILENT review
→ later authorized pilot workspace + independent review
```

发布后仍必须保持：

```text
prerelease = true
latest = false
Stable Latest = v1.4.2
V2_STABLE_RELEASE = FALSE
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

---

## 相比 beta.5 的主要变化

### 1. End → Continue 后原地出现 Quick Debrief

真实 Conversation Session 结束后，不再要求用户先返回 Space、重新找到 Session、再展开 Pilot Feedback。

Continue 结果区直接出现 3 个最小必要显式 self-report：

```text
Continue 是否准确？
还愿意继续用这个 Space 吗？
相比没有成竹，这场认知负担怎样？  (-2..+2)
```

边界保持不变：

- 只写本机 `conversation_human_feedback`；
- Product API reviewer provenance 仍为 `SELF_USER`；
- 不做 remote telemetry；
- 不从 Pin / Used / Dismissed / click-through 推断标签；
- Quick Debrief 完成度不是 meeting quality score；
- 正向 self-report 不会自动升级 Stable / REAL_USER_VALIDATED / PMF。

### 2. Guidance / SILENT 详细 Review 改为 progressive disclosure

事件级详细回看仍然存在，包括：

- Guidance useful；
- interruption regret；
- source correctness；
- Recall correctness；
- arbiter SILENT correctness。

但它不再与最小会后反馈竞争第一视觉层。用户可以：

```text
先完成 3 项 Quick Debrief
→ 继续离开 / 回到 Space
→ 有需要时再补详细事件级 Review
```

同一可复用组件同时用于：

- Live → End → Continue 的即时 Debrief；
- Space → Continue 的后续补标。

### 3. Stable Promotion Policy v6：cohort 与样本单位同时 fail-closed

beta.5 发布后继续审计 Stable cohort contract，冻结为：

```text
STABLE_PROMOTION_POLICY = v2.0-R1-stable-promotion-6
PROJECT_SYNC:
  >= 5 pseudonymous users
  >= 20 authorized real Sessions
  >= 3 cross-session Spaces
DESIGN_REVIEW:
  >= 5 pseudonymous users
  >= 20 authorized real Sessions
  >= 3 cross-session Spaces

qualifying cross-session Space:
  >= 3 authorized Sessions
```

这是 acceptance floor，不是统计学样本量声明，也没有因为 beta.6 放宽任何指标阈值。

### 4. Authorized pilot manifest + frozen workspace orchestration

post-beta.5 source tree 新增 fail-closed operator tooling：

```text
explicit Session/user_ref assignments
→ DRAFT pilot manifest
→ selected-session-only review seed
→ selected-session-only self-report export
→ frozen Stable policy bytes/hash
→ explicit operator attestations
→ FINAL authorized cohort
→ independent review
→ frozen-policy Stable readiness evaluation
```

它会：

- 拒绝静默覆盖旧 workspace；
- 冻结 `selected-cohort.snapshot.json`、Stable policy、manifest/self-report 等输入并记录 hashes；
- selected-cohort snapshot 只包含 selected Session 结构 + 本地匿名 `user_ref` + Frozen Session Pack identity/digest（并重新计算 payload canonical digest 校验 stored digest），不含 transcript / participant / Guidance / source text；
- finalize 时从当前 SQLite 逻辑状态重新计算 selected cohort，对任何 selected Session/Pack drift fail-closed；
- final manifest 生成后、任何 final evidence 落盘前，再次重算 selected cohort；若 build_manifest 的独立 live-DB 读取窗口内发生结构漂移，同样 fail-closed，避免 check-then-use provenance race；
- 允许与 cohort 无关的新 Session / WAL-backed 数据库变化，不把整库文件变化误判成 cohort drift；
- SQLite 主 `product.db` 文件 SHA256 仅作为 advisory，因为 WAL 可能包含尚未 checkpoint 的逻辑状态；
- 只把显式选择的 Session 放入 workspace。

它不会系统验证：

- 人的真实身份；
- real-world authorization；
- participant consent；
- operator attestation 的真实性；
- PMF。

### 5. Independent-review rows are event-bound to the frozen seed

继续审计真实 pilot Stable evidence 链时发现：仅把 human-report 的 Session/profile/Space 绑定到 authorized cohort 还不够。如果 reviewer JSONL 可以自行增加一个不存在于 `independent-review.seed.jsonl` 的 event，或者改写 frozen prediction/runtime origin，再标成 `INDEPENDENT_HUMAN_REVIEW`，就可能人为放大 Stable metric 的样本数或分数。

beta.6 因此把 pilot workspace contract 升级，并要求 `evaluate` 在 aggregation 前：

```text
re-verify independent-review.seed.jsonl SHA256
→ index frozen seed by session_id + kind + event_id
→ require every reviewer row to exist in the frozen seed
→ compare all immutable fields exactly
→ permit only reviewer / label_source / notes / human label fields to change
→ then aggregate
```

明确 fail-closed：

- invented event；
- changed prediction / predicted state；
- changed profile / Space；
- changed transcript/runtime origin；
- changed source refs / detector provenance；
- unknown extra immutable field；
- tampered seed bytes。

`evaluation-manifest.json` 记录 frozen seed SHA、seed row 数、verified review row 数和 event-level binding 状态。

这仍然不系统验证 reviewer 身份或是否真的独立；它关闭的是**事件级证据来源完整性**，不是身份认证。

同一审计还发现，旧 human-eval 虽阻止“同一 reviewer 重复同一 event”，却允许多个 reviewer 对同一 event 的同一 metric 分别贡献一行，导致 Stable `min_n` 可能退化为 annotation count。Policy v6 / Human Eval v5 现在冻结：

```text
METRIC_SAMPLE_UNIT = UNIQUE_EVENT_PER_METRIC
DUPLICATE_EVENT_METRIC = FAIL_CLOSED
NUMERICAL_THRESHOLDS_CHANGED = FALSE
MIN_N_NUMBERS_CHANGED = FALSE
PROFILE_FLOORS_CHANGED = FALSE
```

因此 20 个 reviewer 重复标 1 个真实 event 仍然只能算 1 个产品事件样本；self-report 与 independent review 也不能对同一 metric/event 双计。多 reviewer 的原始标签可用于独立的一致性分析，但 Stable 聚合前必须先得到单一 resolved observation。

### 6. Privacy-minimized pilot Session inventory

为避免 operator 为了找 Session ID 而打开私密内容，source-side workspace CLI 新增：

```bash
python scripts/v2_conversation_pilot_workspace.py inspect --db <product.db>
python scripts/v2_conversation_pilot_workspace.py inspect --db <product.db> --eligible-only
```

inventory 只暴露机器可验证结构：

- session_id / space_id；
- frozen profile；
- status + UTC start/end；
- consent acknowledgement 是否记录；
- matching Frozen Session Pack 是否可验证；
- structural blockers；
- explicit local self-report 数量；
- Quick Debrief 0..3 完成度。

明确不导出：

- Session / Space title；
- participants；
- transcript；
- Guidance text；
- source excerpts；
- user_ref。

而且：

```text
structurally_selectable
!= authorized real use
!= verified identity
!= independently verified participant consent
!= real-user validation
```

该 inventory 是 source-side operator tooling，不应伪装成 beta.6 普通用户 UI。

---

## beta.5 已有能力继续保留

beta.6 继承 beta.5 的：

- schema v10 immutable AI prediction snapshot；
- local explicit Pilot Feedback Bridge；
- schema v11 Direct Question capture-time prediction provenance；
- schema v12 auto-runtime Guidance/SILENT provenance；
- feedback retention integrity；
- scope-aware npm security gate；
- electron-builder 26.17.0；
- Vite 6.4.4；
- reviewed Draft 与 explicit second-step external execution 分离；
- GitHub / Google Calendar / Google Drive / Gmail / Microsoft To Do / Local Markdown provider runtime；
- Manual + explicit-start AUTO Screen Context；
- Conversation Human Coach；
- desktop Share Privacy / Private Overlay runtime boundary。

---

## 仍然明确不宣称

beta.6 不代表：

- `V2_STABLE_RELEASE = TRUE`；
- `PRODUCT_EVIDENCE_READY_FOR_STABLE_RELEASE_REVIEW = TRUE`；
- `REAL_USER_VALIDATED = TRUE`；
- `PMF_PROVEN = TRUE`；
- 任何 structurally selectable Session 都是 authorized real use；
- Google Calendar / Drive / Gmail / Microsoft To Do real-account replay 已完成；
- Google OAuth sensitive-scope publication / verification 已完成；
- Windows code signing 已完成；
- macOS signing / notarization 已完成。

当前外部账号事实仍是：

```text
GitHub real throwaway replay = PASS
Local Markdown = local runtime
Google Calendar = BLOCKED_ACCOUNT
Google Drive = BLOCKED_ACCOUNT
Gmail = BLOCKED_ACCOUNT + external OAuth publication gate
Microsoft To Do = BLOCKED_ACCOUNT
```

---

## beta.6 后的正确下一步

beta.6 的目的就是停止继续用“工程能力”替代真实验证。

发布后优先：

1. 用 beta.6 做授权真实 Project Sync；
2. 用 beta.6 做授权真实 Design Review；
3. 会后完成 Quick Debrief；
4. operator 用 privacy-minimized inventory 显式选择 Session；
5. 建立 frozen pilot workspace；
6. independent human review；
7. 用 frozen Stable Policy v6 跑 readiness；
8. 不足就修产品/继续收合法证据，不降阈值。

没有真实 pilot evidence 时，不升级 stable。

---

## Release gate

beta.6 的 generic publisher 还要求：完成 CI 的 SHA 在 dispatch 时仍然是 **当前 main tip**。如果 main 已前进，旧绿色 CI 必须 no-op，不能把过时 SHA 发布成同一 prerelease 版本。

beta.6 必须完整通过现有 exact-SHA Windows release path：

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
- Playwright / visual；
- e2e smoke；
- packaged smoke；
- Windows installer + portable build；
- clean-install replay；
- draft GitHub Release；
- SHA256 download-back；
- downloaded installer reinstall；
- downloaded packaged smoke；
- prerelease channel；
- Stable Latest preservation；
- tag/source invariant；
- post-publish verification metadata regression。

## Release channel

```text
Stable Latest = v1.4.2
This candidate = v2.0.0-beta.6 prerelease
Current published Conversation Beta before this candidate = v2.0.0-beta.5
Stable v2 = NOT CLAIMED
REAL_USER_VALIDATED = FALSE
PMF_PROVEN = FALSE
```

## Windows signing

当前 Windows Beta 仍为 unsigned engineering/prerelease distribution。Windows SmartScreen 警告仍可能出现；这与 runtime correctness / release provenance 是不同发布层问题。

## License

MIT。第三方组件保留各自许可证，详见 `THIRD_PARTY_NOTICES.md`。
