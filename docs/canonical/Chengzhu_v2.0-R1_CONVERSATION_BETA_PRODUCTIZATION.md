# Chengzhu v2.0-R1 Conversation Beta Productization Gate

> 日期：2026-10-07  
> 状态：PRODUCTIZATION CANDIDATE  
> 基线：main `5bbf134f`（PR #19 v2 Design/Runtime Closure merged）  
> 当前增量：PR #23 `test(v2): productize Conversation Beta packaged evidence`

---

# 0. 目的

v2 Design/Runtime Closure 已经回答：

> Conversation 是否有真实 runtime、truth/provenance、Preflight、Live、Continue、History 与可执行边界？

答案是 **YES**。

本文件回答下一件不同的问题：

> 这些能力是否在“真正打包后的 Windows 产品”里仍然成立，并且有足够证据升级为 Conversation Beta productized release？

这里严格禁止把以下概念混为一谈：

```text
source runtime
!= packaged runtime
!= packaged UI
!= clean install
!= published release
!= real user validation
```

---

# 1. 五级 Gate

## Gate A — Source Runtime Closure

要求：

- backend / frontend / desktop tests；
- Conversation E2E；
- visual；
- provenance / retention / deletion；
- frozen Session Pack；
- Guidance Arbiter；
- Profile-aware History；
- Privacy fail-closed；
- shared Interview regression。

当前状态：

```text
GATE_A_SOURCE_RUNTIME = PASS
```

证据：
- PR #19；
- `Chengzhu_v2.0-R1_DESIGN_RUNTIME_CLOSURE_MATRIX.md`；
- 最终 closure CI 全绿。

Gate A 只能支持：

```text
V2_RUNTIME_AVAILABLE = TRUE
```

不能支持：

```text
V2_PRODUCTIZED_RELEASE = TRUE
```

---

## Gate B — Windows Packaged Backend

必须使用：

```text
build/sidecar/.../chengzhu-backend.exe
```

而不是：

```text
python backend/main.py
```

至少证明：

1. fresh CHENGZHU_HOME；
2. sidecar 无系统 Python 假设；
3. frontend-dist 可服务；
4. intelligence.db 最新 migration；
5. product.db 最新 migration；
6. Interview Fast Cue 仍工作；
7. Conversation Space 创建；
8. explicit Counterparty State；
9. Conversation Session；
10. Preflight / resolved local path；
11. frozen Session Pack；
12. Direct Question Guidance；
13. reviewed Decision；
14. Continue / What changed；
15. sidecar restart；
16. Conversation History persistence；
17. frozen Session Context persistence；
18. install directory 不被 runtime 写脏；
19. LICENSE / notices bundled。

PR #23 把这些要求加入：

- `scripts/packaged_smoke.py`

完成标准：

```text
GATE_B_PACKAGED_BACKEND = PASS
```

必须来自 Windows CI 真实报告，不能只靠代码存在。

---

# 2. Gate C — Packaged Conversation UI

必须使用：

- packaged backend sidecar；
- `dist/desktop/win-unpacked/resources/frontend-dist`；
- production build；
- clean temporary user data。

最小证据集：

1. Conversation Home；
2. Space Overview；
3. Prepare；
4. Preflight + Session Pack Preview；
5. Live + Session Pulse；
6. provenance-tiered Manual Ask；
7. Continue + reviewed current-session truth；
8. Conversation History；
9. 390px Conversation Home。

证据目录：

```text
artifacts/release-evidence/v<app-version>/conversation-beta/
```

manifest 必须记录：

- app version；
- packaged backend executable；
- packaged frontend-dist；
- capture timestamp；
- Space / Session ids；
- evidence type；
- BrowserWindow 是否被真正证明；
- hosted-runner limitation。

PR #23 的 hosted-runner 证据类型：

```text
PACKAGED_SIDECAR_PLUS_PACKAGED_FRONTEND_DIST_PLAYWRIGHT
```

并明确：

```text
electron_browserwindow_proven = false
```

所以 Gate C 分两层：

### C1 — Packaged Web Surface

真实 packaged assets + real packaged backend + Chromium。

### C2 — Electron BrowserWindow

真实 Electron window / desktop shell。

当前 PR #23 只尝试把 **C1** 变成强制 Release workflow evidence。

禁止：

> 用 C1 的 Chromium 截图声明“Electron BrowserWindow 已验证”。

---

# 3. Gate D — Clean Install / Release Provenance

只有在准备真正发布 v2 stable / beta build 时执行。

要求：

- Electron installer；
- portable zip；
- clean install；
- installed-layout smoke；
- Conversation packaged backend smoke；
- Conversation packaged UI evidence；
- installer/portable SHA256；
- GitHub draft release；
- download-back；
- downloaded installer reinstall；
- downloaded artifacts hash verification；
- release target SHA = CI-proven SHA；
- published tag SHA = source SHA；
- README 与 release note 真相一致。

必须同时保留 Interview regression。

只有 Gate A+B+C+D 全 PASS 才允许：

```text
V2_PRODUCTIZED_RELEASE = TRUE
```

如果只完成 A+B+C：

```text
CONVERSATION_BETA_PACKAGED_CANDIDATE = TRUE
V2_PRODUCTIZED_RELEASE = FALSE
```

---

# 4. Gate E — Real Conversation Evidence

Gate E 不属于 CI。

第一批只验证：

- Project Sync；
- Design Review。

每一条 shown Guidance 最少需要真人标注：

- useful / not useful；
- was interruption appropriate；
- source correct；
- fact correct；
- should have stayed silent；
- missing opportunity；
- wrong stakeholder framing。

Session 级：

- Recall Precision；
- Opportunity Precision；
- Interruption Regret；
- Useful Silence Rate；
- Decision / Commitment extraction precision；
- Continue accuracy；
- preparation time reduction；
- willingness to reuse same Space；
- cognitive load。

只有 Gate E 可以支持：

```text
REAL_CONVERSATION_VALUE_PROVEN
```

长期才可能支持：

```text
PMF_PROVEN
```

---

# 5. 当前依赖边界

以下不因为 productization evidence 而自动变成“完成”：

| 能力 | 状态 | 升级需要 |
| --- | --- | --- |
| Conversation Screen Context | BLOCKED | 独立 Conversation namespace + policy + runtime evidence |
| Human Coach | BLOCKED | disclosure/policy/runtime evidence |
| Private Overlay | BLOCKED | Conversation presenter-visible control |
| Calendar / Docs / Mail connectors | NOT WIRED | 真实 connector + permission model |
| External email/task/issue execution | NOT WIRED | reviewed execute + connector result/audit |
| automatic participant chat notice/watermark | NOT WIRED | meeting-platform-specific runtime |
| real microphone / third-party meeting replay | EXTERNAL RUNTIME | 本机/真实会议证据 |
| real-user value | PENDING | 真人 Session |

这些不得用 mock、placeholder 或文档状态替代。

---

# 6. PR #23 具体完成定义

PR #23 只有在以下都成立时才允许 merge：

- `scripts/packaged_smoke.py` Conversation checks 在 Windows packaged-smoke PASS；
- release workflow Windows build PASS；
- Conversation packaged UI evidence 9/9；
- manifest 存在且 limitation 字段真实；
- existing v1.4 Interview evidence 不回归；
- backend/frontend/desktop/Playwright/visual/e2e-smoke 全绿；
- release job 不因为 Conversation evidence 修改既有 installer/hash/provenance 语义。

Merge 后允许更新：

```text
CONVERSATION_PACKAGED_BACKEND_EVIDENCE = PASS
CONVERSATION_PACKAGED_WEB_UI_EVIDENCE = PASS
CONVERSATION_BETA_PRODUCTIZATION_GATE_B_C1 = PASS
```

仍禁止：

```text
ELECTRON_CONVERSATION_UI_PROVEN = TRUE
V2_PRODUCTIZED_RELEASE = TRUE
REAL_USER_VALIDATED = TRUE
PMF_PROVEN = TRUE
```

除非对应独立证据真实存在。

---

# 7. 下一步顺序

PR #23 全绿并合并后：

1. 从 main 构建独立 Conversation Beta candidate；
2. 在真实 Windows 本机跑 Electron BrowserWindow Conversation replay；
3. 若需要，补 C2 evidence；
4. clean-install replay；
5. 再决定是否发 beta tag / release；
6. 小规模 Project Sync / Design Review dogfood；
7. 真人标注 Guidance；
8. 最后才讨论 Screen Context、Human Coach、connectors 与 external write-back。

这一路线刻意不以“功能数量”作为成熟度标准。
