/** v2.0-R1 Personal Conversation Intelligence runtime contracts. */
export type ConversationProfile =
  | 'PROJECT_SYNC'
  | 'DESIGN_REVIEW'
  | 'PRESENTATION_QA'
  | 'ONE_ON_ONE'
  | 'CLIENT_CALL'
  | 'NEGOTIATION'

export type AssistanceMode = 'QUIET' | 'BALANCED' | 'ACTIVE' | 'PRESENTATION' | 'ONE_ON_ONE'
export type CaptureMode = 'TRANSCRIPT' | 'NOTES_ONLY' | 'NO_CAPTURE'
export type ProcessingMode = 'LOCAL' | 'CLOUD' | 'OFF'

export interface ConversationSessionPolicy {
  transcript_retention: string
  screen_context: 'OFF' | 'MANUAL' | 'AUTO'
  ai_assistance: 'AI_FORBIDDEN' | 'AI_LIMITED' | 'AI_ALLOWED' | 'AI_EXPECTED'
  human_assistance: 'HUMAN_FORBIDDEN' | 'HUMAN_PRACTICE_ONLY' | 'HUMAN_ALLOWED'
  share_privacy: 'OFF' | 'PRIVATE_OVERLAY'
  external_writeback: 'OFF' | 'REVIEW_REQUIRED'
  participant_consent_status: 'NOT_RECORDED' | 'USER_REPORTS_ALLOWED' | 'USER_REPORTS_CONSENTED' | 'NOT_APPLICABLE'
  participant_transparency_plan: 'NOT_RECORDED' | 'USER_WILL_NOTIFY_VERBALLY' | 'USER_WILL_NOTIFY_IN_CHAT' | 'USER_REPORTS_ALREADY_NOTIFIED' | 'NOT_APPLICABLE'
  connector_permissions: string[]
  speaker_biometric_identity: 'OFF'
  emotion_sentiment_profiling: 'OFF'
  hidden_intent_claims: 'OFF'
}

export interface CounterpartyState {
  known_explicit: {
    priority?: string
    concern?: string
    stated_position?: string
    decision_authority?: string
    relationship_context?: string
  }
  source_refs: SourceRef[]
  confidence: number
  temporary_inferences: Array<Record<string, unknown>>
  unknown: string[]
}

export type GuidanceKind =
  | 'RECALL'
  | 'TALKING_POINT'
  | 'ANSWER_CUE'
  | 'QUESTION'
  | 'RISK'
  | 'DELIVERY'
  | 'CONTRIBUTION_OPPORTUNITY'

export type ExpressionAction =
  | 'SILENT'
  | 'ANSWER'
  | 'RECALL'
  | 'ADD_TALKING_POINT'
  | 'ASK_QUESTION'
  | 'FLAG_RISK'
  | 'CLARIFY'
  | 'SUMMARIZE'
  | 'COMMIT_NEXT_STEP'

export type ConversationItemType =
  | 'Decision'
  | 'Commitment'
  | 'Task'
  | 'Deadline'
  | 'Risk'
  | 'Assumption'
  | 'OpenQuestion'
  | 'Proposal'
  | 'Objection'
  | 'Metric'
  | 'Status'

export type ConversationItemState = 'PROPOSED' | 'AGREED' | 'COMMITTED' | 'DONE' | 'SUPERSEDED' | 'UNKNOWN'
export type ReviewStatus = 'AI_EXTRACTED' | 'USER_CONFIRMED' | 'USER_EDITED' | 'USER_REJECTED' | 'SOURCE_CONFIRMED'
export type EpistemicStatus = 'OBSERVED' | 'USER_CONFIRMED' | 'SOURCE_CONFIRMED' | 'INFERRED' | 'UNKNOWN'

export interface SourceRef {
  id?: string
  kind: string
  uri?: string
  session_id?: string
  timestamp?: number
  excerpt?: string
  visibility?: string
  version_id?: string
  content_hash?: string
}

export interface ConversationTemplate {
  key: ConversationProfile
  label: string
  default_mode: AssistanceMode
  guidance: GuidanceKind[]
  runtime_available: boolean
  launch_wedge: boolean
  specialized_behavior_validated: boolean
  stable_release: boolean
  real_user_validated: boolean
  maturity: 'BETA_WEDGE' | 'SHARED_RUNTIME_TEMPLATE'
}

export interface ConversationSpace {
  id: string
  profile: ConversationProfile
  title: string
  description: string
  status: 'ACTIVE' | 'ARCHIVED'
  project_id: string
  relationship_key: string
  default_goal: string
  default_mode: AssistanceMode
  selected_source_ids: string[]
  selected_quick_note_ids: string[]
  retention_policy: Record<string, unknown>
  created_at: number
  updated_at: number
  next_session?: ConversationSession | null
  last_session?: ConversationSession | null
  open_commitments_count?: number
  open_questions_count?: number
}

export interface ConversationGoal {
  id: string
  space_id: string
  title: string
  outcome_definition: string
  status: string
  priority: number
  source: Record<string, unknown>
  created_at: number
  resolved_at: number | null
}

export interface ConversationParticipant {
  id: string
  space_id: string
  session_id: string | null
  display_name: string
  role: string
  organization: string
  identity_confidence: number
  identity_source: string
  visibility: string
  observations: Array<Record<string, unknown>>
  counterparty_state: CounterpartyState
}

export interface ConversationSession {
  id: string
  space_id: string
  goal_ids: string[]
  template: ConversationProfile
  title: string
  scheduled_at: number | null
  started_at: number | null
  ended_at: number | null
  capture_mode: CaptureMode
  processing_mode: ProcessingMode
  assistance_mode: AssistanceMode
  consent_ack: boolean
  policy: ConversationSessionPolicy
  pack_id: string
  status: 'UPCOMING' | 'ACTIVE' | 'ENDED'
  state: { current_topic?: string; open_threads?: string[]; last_guidance_id?: string }
  created_at: number
  updated_at: number
}

export interface ConversationItem {
  id: string
  space_id: string
  session_id: string
  type: ConversationItemType
  state: ConversationItemState
  title: string
  detail: string
  speaker_id: string
  owner_id: string
  due_at: string
  source_refs: SourceRef[]
  source_excerpt: string
  confidence: number
  epistemic_status: EpistemicStatus
  review_status: ReviewStatus
  supersedes_id: string
  visibility: string
  created_at: number
  updated_at: number
}

export interface ConversationGuidance {
  id: string
  session_id: string
  candidate_id: string
  kind: GuidanceKind
  expression_action: ExpressionAction
  text: string
  source_refs: SourceRef[]
  status: 'SHOWN' | 'SUPPRESSED'
  reason: string
  score: Record<string, number>
  user_action: string
  rendered_at: number | null
  created_at: number
}

export interface ConversationOpenThread {
  id: string
  space_id: string
  session_id: string | null
  kind: 'OpenQuestion' | 'Risk' | 'Objection' | string
  text: string
  owner_id: string
  status: 'OPEN' | 'RESOLVED' | string
  source_refs: SourceRef[]
  created_at: number
  resolved_at: number | null
}

export interface ConversationSpaceDetail extends ConversationSpace {
  goals: ConversationGoal[]
  sessions: ConversationSession[]
  participants: ConversationParticipant[]
  decisions: ConversationItem[]
  commitments: ConversationItem[]
  open_questions: ConversationItem[]
  objections: ConversationItem[]
  next_session: ConversationSession | null
  recent_decisions: ConversationItem[]
  last_session_delta: null | {
    session_id: string
    title: string
    what_changed: ConversationItem[]
    pins: ConversationGuidance[]
    review_required: number
  }
  threads: ConversationOpenThread[]
}

export interface ConversationPrepare {
  space: Pick<ConversationSpace, 'id' | 'profile' | 'title' | 'description' | 'default_goal' | 'default_mode' | 'selected_source_ids' | 'selected_quick_note_ids'>
  goals: ConversationGoal[]
  next_session: ConversationSession | null
  open_commitments: ConversationItem[]
  open_questions: ConversationItem[]
  open_threads: ConversationOpenThread[]
  related_decisions: ConversationItem[]
  participants: ConversationParticipant[]
  selected_sources: string[]
  selected_quick_notes: string[]
  brief: { last_change: ConversationItem | null; unresolved_count: number; known_participants: number }
  agenda: string[]
  expected_questions: string[]
  contribution_candidates: Array<{ text: string; source_refs: SourceRef[]; kind: string }>
}

export interface ConversationHome {
  state: 'EMPTY' | 'ACTIVE'
  spaces: ConversationSpace[]
  next_session: ConversationSession | null
  next_focus: null | { kind: string; title: string; space_id: string }
  owed_by_me: ConversationItem[]
  open_questions: ConversationItem[]
  recent_change: ConversationItem | null
}

export interface ConversationProcessingRuntime {
  mode: ProcessingMode
  capture_mode: CaptureMode
  configured_stt_provider: string
  main_audio_remote_possible: boolean
  self_mic_remote_possible: boolean
  data_path: {
    capture: 'LOCAL_DEVICE_CAPTURE' | 'NO_CAPTURE' | 'STRUCTURED_NOTES_ONLY' | string
    stt: 'LOCAL_ONLY' | 'REMOTE_POSSIBLE' | 'NOT_USED' | string
    inference: 'LOCAL_DETERMINISTIC' | string
    retention: 'LOCAL_PRODUCT_DB' | string
    writeback: 'DISABLED' | 'LOCAL_REVIEWED_DRAFT_ONLY' | string
    audio_retention: string
    transcript_retention: string
  }
  blockers: string[]
}

export interface ConversationPreflight {
  session: ConversationSession
  space: ConversationSpace
  items: Array<{ key: string; label: string; value: string | number | boolean; ok: boolean }>
  blockers: Array<{ key: string; label: string; message: string }>
  warnings: Array<{ key: string; label: string; message: string }>
  policy: ConversationSessionPolicy
  processing_runtime: ConversationProcessingRuntime
  pack_preview: {
    goal_ids: string[]
    selected_source_ids: string[]
    selected_quick_note_ids: string[]
    sources: Array<{
      material_id: string
      version_id: string
      title: string
      kind: string
      usage: string
      content_hash: string
      is_personal_evidence: boolean
    }>
    skipped_sources: Array<{ id: string; title: string; reason: string }>
    quick_notes: Array<{ id: string; title: string }>
    missing_quick_note_ids: string[]
    participants_count: number
    confirmed_items_count: number
    expression_profile: Record<string, unknown>
    processing_runtime: {
      mode: ProcessingMode
      capture_mode: CaptureMode
      configured_stt_provider: string
      main_audio_remote_possible: boolean
      self_mic_remote_possible: boolean
      blockers: string[]
    }
    policy: ConversationSessionPolicy & { capture_mode: CaptureMode; processing_mode: ProcessingMode; assistance_mode: AssistanceMode }
  }
  privacy_note: string
}

export interface ConversationContinue {
  session: ConversationSession
  decisions: ConversationItem[]
  commitments: ConversationItem[]
  open_questions: ConversationItem[]
  candidates: ConversationItem[]
  what_changed: ConversationItem[]
  pins: ConversationGuidance[]
  next_focus: null | { kind: string; title: string; source_ref: string }
  review_required: number
}

export interface ConversationDraftAction {
  id: string
  space_id: string
  session_id: string | null
  kind: 'FOLLOWUP_EMAIL_DRAFT' | 'CREATE_TASK_DRAFT' | 'CREATE_ISSUE_DRAFT' | 'UPDATE_DECISION_LOG_DRAFT'
  title: string
  content: string
  target: string
  payload: Record<string, unknown>
  source_refs: SourceRef[]
  status: 'DRAFT' | 'APPROVED' | 'DISMISSED'
  created_at: number
  updated_at: number
}

export interface ConversationTranscriptSegment {
  id: string
  space_id: string
  session_id: string
  channel: 'PRIMARY_AUDIO' | 'SELF_MIC' | string
  text: string
  provider: string
  source: string
  is_final: boolean
  created_at: number
}

export interface ConversationAskMatch {
  id: string
  kind: 'CONFIRMED_ITEM' | 'FROZEN_SOURCE' | 'QUICK_NOTE' | 'TRANSCRIPT_SEGMENT'
  authority: 'CONFIRMED_TRUTH' | 'PERSONAL_EVIDENCE' | 'REFERENCE_SOURCE' | 'USER_NOTE_NOT_EVIDENCE' | 'OBSERVED_NOT_CONFIRMED'
  title: string
  excerpt: string
  item_type: string
  state: string
  review_status: string
  source_refs: SourceRef[]
}

export interface ConversationAskResult {
  answer: string
  matches: ConversationAskMatch[]
  grounded: boolean
  truth_confirmed: boolean
}

export interface ConversationSessionContext {
  session_id: string
  space: { id: string; profile?: ConversationProfile; title?: string }
  brief: {
    goal?: string
    goals?: Array<{ id: string; title: string; outcome_definition: string; priority: number }>
    agenda?: string[]
    expected_questions?: string[]
    unresolved_count?: number
    known_participants?: number
    contribution_candidates?: Array<{ text: string; source_refs: SourceRef[]; kind: string }>
  }
  sources: Array<{
    material_id: string
    version_id: string
    title: string
    kind: string
    usage: string
    content_hash: string
    is_personal_evidence: boolean
  }>
  quick_notes: Array<{ id: string; title: string }>
  participants: Array<{
    id: string
    display_name: string
    role: string
    organization: string
    counterparty_state: CounterpartyState
  }>
  expression_profile: Record<string, unknown>
  processing_runtime: Partial<ConversationProcessingRuntime>
  policy: ConversationSessionPolicy
  pack_digest: string
}

export interface ConversationCaptureStatus {
  active: boolean
  session_id: string
  owns_requested_session: boolean
  device_id: number | null
  candidate_mic_device_id: number | null
  mode: 'TRANSCRIPTION_ONLY' | 'IDLE'
  paused?: boolean
}

export interface ConversationHistoryItem extends ConversationSession {
  space_title: string
  space_profile: ConversationProfile
  decisions_count: number
  commitments_count: number
  open_questions_count: number
  review_required: number
}
