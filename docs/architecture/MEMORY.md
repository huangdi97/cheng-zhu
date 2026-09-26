# Memory（Stage L/M）

> CURRENT · 对应 canonical 第 23、24、31、32 节。落点：`backend/services/intelligence/memory_policy.py`、`review_writeback.py`、`voice_profile.py`、storage 表 `memory_item` / `voice_profile`。

## 1. 定位

三级 Memory（canonical 第 23 节）：跨面试沉淀是受控的——禁止把一次 LLM 的 interviewer inference 永久写成事实。

## 2. 三级 Memory

| 层级 | 范围 | 当前实现 | 存储 |
| --- | --- | --- | --- |
| Working Memory | 当前几分钟，高精度、可回溯 | 内存会话状态（`core/session.py`）+ Interview State current/previous topic、open_threads | 内存（state snapshot 镜像到 `interview_state_snapshot`） |
| Session Memory | 整场面试 | topic / question tree / claims / open threads / key constraints；`interview_turn` 逐轮记录（问题/回答截 200 字符） | `intelligence.db` 表 `interview_turn` + `interview_session` |
| Long-term Candidate Memory | 跨面试 | **只写入白名单四类**（见下）；`memory_item` 表统一持久化 | `intelligence.db` 表 `memory_item` |

Session Memory 经 `review_integration` 落 `review.db`（复盘），经 `telemetry.record_turn` 落 `intelligence.db`（observability）——guidance 永不写成 candidate fact（`realtime_bridge.record_committed_turn` docstring）。

## 3. Controlled Write-back 白名单（canonical 第 23/31 节；`memory_policy.py`）

```python
WRITABLE_KINDS = {"knowledge_weakness", "repeated_topic", "user_confirmed_fact", "communication_profile"}
AUTO_WRITABLE_KINDS = {"knowledge_weakness", "repeated_topic", "communication_profile"}
```

| kind | 自动管道可写 | 需用户确认 | 语义 |
| --- | --- | --- | --- |
| `knowledge_weakness` | ✅ | — | 多次重复暴露的知识薄弱点 |
| `repeated_topic` | ✅ | — | 重复出现的主题 |
| `communication_profile` | ✅ | — | 用户表达偏好（口述统计） |
| `user_confirmed_fact` | ❌（无自动路径可代表用户设置） | ✅ 必须显式确认 | 已确认个人事实 |

守卫行为（`can_write_back` / `write_back_memory`，`memory_policy.py:26,38`）：

- kind 不在白名单 → 记 warning 并拒绝，永不 raise（denied 不计写入数）。
- `user_confirmed_fact` 无显式确认 flag → 拒绝（SAFETY 注释：no automatic path may set it on the candidate's behalf）。
- 写回统一经 `storage.intelligence.upsert_memory_item` 持久化。

**SAFETY 边界**：LLM 衍生的 interviewer inference（possible_focus / possible_concerns / planner hints）**绝不**经过本模块——interviewer state 是 planner 的概率性提示，永不是关于候选人的存储事实。

## 4. Review → Intelligence 写回（Stage L4；`review_writeback.py`）

`write_back_after_review(session_id, summary_result, analyzed_turns)`（`review_writeback.py:28`）：

- 复盘完成后，只有 policy-approved 的 kinds 通过 `memory_policy.write_back_memory` 落库：`knowledge_weakness` / `repeated_topic` / `communication_profile`（cap 8 条薄弱点）。
- 返回各 kind 实际写入数；被拒绝的尝试由 memory_policy 记 warning、不计入。
- INVARIANT（模块 docstring）：Review 永不自动把 LLM inference 写进 Candidate Facts；user-confirmed 新事实需显式确认、走用户 API（`PATCH /api/intelligence/claims/{claim_id}`），不在这里。

## 5. Personal Voice profile（Stage M，canonical 第 24 节；`voice_profile.py`）

目标：答案越来越像这个人，而不是越来越像"AI 面试模板"。

`build_voice_profile(samples, *, candidate_id, explicit_preferences)`（`voice_profile.py:92`）从**真实候选人口述**统计（真实口述采集来自面试复盘/候选人麦克风链路），不是 assistant 自己生成的答案——否则模型会学会模仿自己：

| 统计项 | 计算 |
| --- | --- |
| `first_sentence_style` | 首句习惯：`conclusion_first` / `context_first`（结论型 vs 铺垫型首句计数） |
| `answer_length_hint` | short（<60 字）/ medium（60-180）/ long（>180） |
| `directness` | 首句"第一人称+动词"（我用了/我负责…）起始的比例 |
| `technical_density` | ASCII 字符占比 + 技术词命中混合（纯中文闲聊趋近 0） |
| `filler_tendency` | 语气词（嗯/呃/那个/uh/um）占比 |
| `language` | CJK/ASCII 比例 → `zh-CN` / `en` / `mixed` |
| `forbidden_cliches` | 禁用模板短语（默认"作为一个AI/总的来说/综上所述" + 用户扩展，cap 8） |
| `sample_count` / `enabled` | 样本数 / 启用开关（默认 False） |

`apply_voice(profile, plan_prompt)`（`:114`）：

- 仅当 profile 启用时追加**有界、风格唯一**的指令块（`[表达风格要求]` + 边界声明 + 首句习惯 + 长度提示 + 直接度 + 禁用短语）。
- 块内自带 `_VOICE_BOUNDARY_LINE`："以下仅为表达风格要求，不得改变事实边界与个人经历的真实性。"——**apply_voice 不改变事实边界**（`test_apply_voice_respects_enabled_flag_and_fact_boundary` 回归）。
- 关闭时原样返回 plan_prompt；gated by `voice_profile_enabled`（默认 `False`，config.py:183）。

`save_voice_profile` / `load_voice_profile` 经 `storage.intelligence` 表 `voice_profile` 持久化；失败记 warning，永不 raise。

## 6. Cross-session Learning（canonical 第 31 节）

- 跨面试只写入：已确认个人事实、用户确认的表达偏好、多次重复暴露的知识薄弱点、用户确认的复盘结论。
- Long-term memory 的读取侧：`SessionMemoryProvider` 注入 memo/状态；KB RAG 继续服务 Personal Extended Context。
- 禁止把一次 LLM 的 interviewer inference 永久写成事实（canonical 第 23 节原文；由 memory_policy 白名单强制）。

## 7. 测试覆盖

- `test_memory_policy_denies_unconfirmed_facts_unknown_kinds_and_denied_write_back`（`test_intelligence_compiler_planner.py:221`）— 白名单 + 确认 + 拒绝路径
- `test_apply_voice_respects_enabled_flag_and_fact_boundary` / `test_voice_profile_build_from_samples_computes_stats`（`:200,210`）— voice 统计与事实边界
- `test_rebuild_never_duplicates_claim_rows` / `test_claim_status_update_roundtrip`（migration）— 长期事实回写幂等
