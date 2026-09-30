# Privacy 与 Interview Policy（Stage P）

> CURRENT · 对应 canonical 第 46、47、48、53 节。落点：`backend/core/config.py:184-187`、`backend/services/storage/paths.py`、`services/storage/intelligence.py`、`api/intelligence/router.py`、`api/sessions/router.py`、`api/review/router.py:490`。

## 1. Local-first 原则（canonical 第 46 节）

默认：

- 简历本地；
- 本地 DB（SQLite，`backend/data/`）；
- API key 本地（`backend/config.json`，用户自己的 provider key）；
- 原始音频不长期保存；
- 尽量只向模型 provider 发送当前必要上下文；
- session 可删除；
- 数据可导出；
- 用户能看到云端处理范围。

后续可做（canonical 第 46 节）：local ASR、local embeddings、optional local LLM。

## 2. 数据存储位置

全部运行时数据统一放在 `backend/data/`（`storage/paths.py`，旧版 `backend/*.db` 自动迁移一次）：

| 数据 | 位置 | 说明 |
| --- | --- | --- |
| Intelligence Core | `backend/data/intelligence.db` | 17 张表，WAL，schema versioning；`backup_database()` 升级前快照（+wal/shm） |
| 面试 PrepSpace | `backend/data/prep.db` / `prep.sqlite` | JD、洞察、技能卡、题目 |
| 面试复盘 | `backend/data/review.db` / `review.sqlite` | 真实问答记录、逐题分析 |
| 本地知识库 | `backend/data/knowledge.db`、`kb.sqlite`、`kb/` | FTS5 + CJK 索引、文档 |
| 简历历史 | `backend/data/resume_history.db`、`resume_uploads/` | 历史记录 id |
| 求职看板 | `backend/data/job_tracker.db` | Job Tracker / Offer Compare |
| 配置 | `backend/config.json` | **不存 resume 正文**——只存 `resume_active_history_id`（当前生效简历对应的历史记录 id，`config.py:168-169`） |

结构化表示中的 `profile_text` 入 `intelligence.db` 时为 **4000 字截断**（`_PROFILE_TEXT_LIMIT`）；API `/candidate` 只返回 **400 字预览**——完整 resume 正文永不经 Intelligence API 离开后端（`api/intelligence/router.py:8-11,38-40,129` PRIVACY 注释）。

## 3. Raw audio retention policy

- `raw_audio_retention_sessions: int = 0`（`config.py:187`，canonical 第 46 节"原始音频不长期保存"）：**默认不长期保存原始音频**；值 > 0 表示保留最近 N 场。
- 默认不自动上传原始音频到任何云端（canonical 第 48 节安全边界："默认上传原始音频"为禁止项）。
- ASR 引擎（远端 STT + Whisper fallback）只接收当前音频段；转写文本本地落库，音频缓冲不持久化。

## 4. Session delete / export

| 操作 | 入口 | 说明 |
| --- | --- | --- |
| 删除会话 | `DELETE /api/sessions/{sid}`（`api/sessions/router.py:80`） | 会话可删除（canonical 第 46 节） |
| 导出复盘 | `GET /api/review/sessions/{session_id}/export?format=md`（`api/review/router.py:490`） | 数据可导出 |
| State 重置 | `POST /api/intelligence/state/reset` | 清空指定会话的 interview state |
| Intelligence 快照 | `interview_state_snapshot` 表 | 随会话存在；`drop_session` 清内存 state |

## 5. Provider data disclosure（发送给模型 provider 的内容）

云端处理范围（canonical 第 46 节"用户能看到云端处理范围"）——LLM 请求包含：

- 当前问题文本（`question_text`，含题目/追问消解结果）；
- grounding 证据摘录（`evidence_excerpt`，支撑个人事实的片段）；
- resume 上下文行（`include_resume` 时按行注入，非全文）；
- JD 文本（`jd_context` 段）与面试笔记（`notes` 段）、Rolling Memo（`memo_context`）；
- 本地知识库命中片段（KB hits）；
- Intelligence 注入块：`plan_prompt`（模式指令）与 `state_context`（面试状态承接块，截 600 字符）；
- 截图审题时：用户主动粘贴的图片/题面。

**不发送**：完整 resume 正文、完整长期记忆库、telemetry 正文（截 200 字符）、API key。多 provider 场景下每个 provider 只收到同一请求的当前必要上下文（canonical 第 46 节）。日志记录 ID / 状态，不记录隐私正文。

## 6. AI policy mode（canonical 第 47 节）

| 模式 | 语义 |
| --- | --- |
| `AI_FORBIDDEN` | 本场明确禁止 AI 辅助 |
| `AI_LIMITED` | 有限辅助 |
| `AI_ALLOWED` | 允许辅助（当前默认，`config.py:185`） |
| `AI_EXPECTED` | 本场预期使用 AI（如在线笔试） |

- 类型定义：`AIPolicyMode`（`types.py:421`，4 值）；配置项 `ai_policy_mode`；`interview_session` 表带 `ai_policy_mode TEXT NOT NULL DEFAULT 'AI_ALLOWED'` 列（per-session 支持）。
- **AI_FORBIDDEN 行为**（canonical 第 47 节）：成竹保留 Prepare / Mock / Review；**Live guidance 默认关闭**。
- 落地状态：`ai_policy_mode` 的存储与枚举已实现；per-session 的 AI_FORBIDDEN 强制关闭 Live guidance 尚未在实时链路生效——当前以配置声明为主（不提供反监考能力的承诺见第 7 节）。

## 7. 不实现反监考的承诺

canonical 第 47 节 + 第 53 节"不做清单" + README 免责：

- **不开发反监考、规避检测等能力**；
- 项目仅供学习研究，请勿用于学术不端、违规考试或其他不合规场景；使用后果自行承担；
- AI_FORBIDDEN 标记是用户对使用边界的**显式自我约束**，不是技术对抗手段。

## 8. 安全边界（canonical 第 48 节）

不得：

- 伪造用户工作经历、伪造成果指标（Truth Boundary + claim policy 强制）；
- 把 inference 写成 verified（`VERIFIED` 仅来自证据/用户 verdict）；
- 自动修改用户证据（PATCH claims 是唯一手动修正路径）；
- 把一次 interviewer inference 永久记忆（memory_policy 白名单强制）；
- 默认上传原始音频（`raw_audio_retention_sessions = 0`）;
- 偷偷更改用户 provider key（config.json 用户自持）;
- 降低测试 Gate 来"通过"。

## 9. Sensitive data minimization（全局规范第 39 节）

- API 只返回当前任务需要的数据：`/candidate` 400 字预览、claims/evidence 分页（limit ≤ 2000）；
- telemetry / interview turn 文本截 200 字符；context item 截 400-600 字符；
- 屏幕题目截 200 字符；mock feedback 的追问维度来自 Experience Expansion（问题节点），不携带完整简历。
