# Chengzhu v2.0-R1 — Objects, Data & Provenance

# 1. 设计目标

Conversation 的数据模型必须支持：

- 多场连续；
- 多参与者；
- topic/open-thread 状态；
- 决策与承诺；
- 来源与不确定性；
- supersession；
- session-scoped inference；
- deletion/export；
- profile-specific extension。

同时不能破坏 v1 Interview schema。

采用 additive migration，不做大爆炸 rename。

# 2. ConversationSpace

```text
ConversationSpace {
  id
  profile_template
  title
  description?
  status
  project_id?
  relationship_key?
  default_goal?
  default_assistance_mode
  selected_source_ids[]
  selected_quick_note_ids[]
  retention_policy
  created_at
  updated_at
}
```

语义：跨多场 Session 的 durable continuity boundary。

例：

```text
PDIG · Android Architecture
Acme · Customer Success
Manager 1:1
Q4 Roadmap
```

# 3. ConversationGoal

```text
ConversationGoal {
  id
  space_id
  title
  outcome_definition?
  status
  priority
  source?
  created_at
  resolved_at?
}
```

Goal 可以跨 Session 持续，直到 resolved/superseded。

# 4. ConversationSession

```text
ConversationSession {
  id
  space_id
  goal_ids[]
  template
  title
  scheduled_at?
  started_at?
  ended_at?
  capture_mode
  processing_mode
  assistance_mode
  consent_ack
  pack_id
  status
  source_calendar_event?
}
```

# 5. SessionPack

Frozen Pack family：

```text
ConversationSessionPack {
  id
  session_id
  space_id
  goal_ids[]
  person_snapshot_ref
  selected_source_refs[]
  selected_decision_refs[]
  selected_commitment_refs[]
  selected_quick_note_refs[]
  participant_context_refs[]
  policy_snapshot
  language_snapshot
  created_at
  digest
}
```

规则：

- Session 开始后 Pack 默认 immutable；
- live 临时信息进入 Session State，不偷偷改 frozen pack；
- 用户显式 Add to session 时记录 overlay delta；
- downstream guidance 必须能说明来自 pack 还是 live state。

# 6. Participant / Counterparty

```text
ConversationParticipant {
  id
  display_name?
  role?
  organization?
  identity_confidence
  identity_source
  visibility
}
```

```text
CounterpartyObservation {
  participant_id?
  kind: ROLE | PRIORITY | CONCERN | POSITION | AUTHORITY | RELATIONSHIP_CONTEXT
  value
  source_ref
  confidence
  epistemic_status: EXPLICIT | INFERRED | UNKNOWN
  persistence: SESSION | SPACE_CANDIDATE | USER_CONFIRMED
  expires_at?
}
```

严禁模型 inference 自动进入长期 Person/Counterparty memory。

# 7. Topic / Open Thread

```text
ConversationTopic {
  id
  session_id
  label
  started_at
  ended_at?
  confidence
  source_segment_ids[]
}
```

```text
OpenThread {
  id
  space_id
  session_id?
  kind
  text
  owner?
  status
  source_ref
  created_at
  resolved_at?
}
```

OpenThread 可以被后续 Session resolve。

# 8. ConversationItem

统一 envelope：

```text
ConversationItem {
  id
  space_id
  session_id
  type
  state
  title
  detail?
  speaker_id?
  owner_id?
  due_at?
  source_refs[]
  source_excerpt?
  confidence
  epistemic_status
  review_status
  supersedes_id?
  visibility
  created_at
  updated_at
}
```

type：

- Decision
- Commitment
- Task
- Deadline
- Risk
- Assumption
- OpenQuestion
- Proposal
- Objection
- Metric
- Status

state：

- PROPOSED
- AGREED
- COMMITTED
- DONE
- SUPERSEDED
- UNKNOWN

review_status：

- AI_EXTRACTED
- USER_CONFIRMED
- USER_EDITED
- USER_REJECTED
- SOURCE_CONFIRMED

# 9. Type-specific transition guards

## Decision

```text
PROPOSED → AGREED → SUPERSEDED
PROPOSED → SUPERSEDED
UNKNOWN → USER REVIEW
```

不得：

```text
silence → AGREED
summary text → AGREED
```

## Commitment

```text
PROPOSED → COMMITTED → DONE
COMMITTED → SUPERSEDED
```

COMMITTED 必须有：

- owner；
- explicit commitment evidence 或 user confirmation。

## Task

Task 可以 AI_EXTRACTED，但进入 external task system 前必须 review。

## Deadline

必须具备：

- concrete date/time 或明确相对条件；
- source；
- owner/context；
- ambiguity flag。

# 10. SourceRef

```text
SourceRef {
  id
  kind:
    TRANSCRIPT_SEGMENT
    USER_NOTE
    QUICK_NOTE
    DOCUMENT
    CALENDAR
    CONNECTOR
    SCREEN_CONTEXT
    USER_ASSERTION
    MODEL_INFERENCE
  uri?
  session_id?
  timestamp?
  excerpt?
  visibility
  integrity?
}
```

AI Summary 不是 authoritative source kind；它只能指向上游 SourceRefs。

# 11. Epistemic status

长期事实统一区分：

```text
OBSERVED
USER_CONFIRMED
SOURCE_CONFIRMED
INFERRED
UNKNOWN
```

UI：

- explicit/confirmed 可正常展示；
- inferred 必须标记不确定；
- unknown 不补全；
- stale 显示时间与来源。

# 12. GuidanceCandidate

```text
GuidanceCandidate {
  id
  session_id
  kind
  expression_action
  text
  source_refs[]
  created_at
  expires_at
  confidence
  score_breakdown
  suppression_reasons[]
  target_participant_id?
  topic_id?
}
```

candidate 不等于显示。只有 Arbiter 允许后才成为 GuidanceEvent。

# 13. GuidanceEvent

```text
GuidanceEvent {
  id
  candidate_id
  rendered_at
  kind
  display_mode
  user_action:
    NONE | EXPANDED | PINNED | DISMISSED | SNOOZED | USED
  speech_after_guidance?
  source_opened?
}
```

用于 local-first evaluation。

# 14. ContributionOpportunity

不是新 truth entity，而是 GuidanceCandidate 的特殊评估。

```text
OpportunityEvidence {
  current_topic_ref
  proposed_source_refs[]
  novelty_evidence
  already_mentioned_evidence
  goal_link
  role_link
  decision_impact
  social_risk
}
```

Opportunity TTL 很短。过期后不得在新 topic 继续浮现。

# 15. Continue / Write-back

会后 extraction 先生成 Candidate Set：

```text
ContinueCandidateSet {
  decisions[]
  commitments[]
  tasks[]
  deadlines[]
  risks[]
  open_questions[]
  followup_drafts[]
}
```

用户操作：

- Confirm；
- Edit；
- Reject；
- Merge；
- Supersede；
- Create external draft。

默认不自动写入外部系统。

# 16. Delete / Export

Delete ConversationSpace 必须处理：

- sessions；
- transcript；
- items；
- guidance events；
- derived memory；
- screen context；
- connector snapshots；
- local analytics。

外部系统已写出的对象只能发送 deletion request / tombstone metadata，不能假装远端已经删除。

Export 分层：

- transcript；
- personal notes；
- AI guidance；
- confirmed items；
- candidate/unconfirmed items；
- connector metadata；
- product events。

API keys/tokens 永不导出。

# 17. Migration

v2 migration：

- additive；
- v1 Interview tables 保持；
- future_profile contract 先稳定；
- Conversation tables 使用独立 namespace；
- 共享 source/provenance adapter；
- 不为了抽象漂亮而强制迁移所有 v1 Goal。

长期可以形成：

```text
ProfileAdapter
InterviewAdapter
ConversationAdapter
```

但 v2.0 不要求全仓 rename Candidate→Person。
