/**
 * Future Personal Conversation Intelligence contracts.
 *
 * Interview is the only productized profile in v1.x. These interfaces keep the
 * shared product/core vocabulary generalizable without adding Meeting routes,
 * database tables, or runtime behavior ahead of evidence.
 */
export type ConversationProfile =
  | 'INTERVIEW'
  | 'MEETING'
  | 'PRESENTATION_QA'
  | 'ONE_ON_ONE'
  | 'DESIGN_REVIEW'
  | 'CLIENT_CALL'
  | 'NEGOTIATION'

export type GuidanceKind =
  | 'RECALL'
  | 'TALKING_POINT'
  | 'ANSWER_CUE'
  | 'QUESTION'
  | 'RISK'
  | 'DELIVERY'
  | 'CONTRIBUTION_OPPORTUNITY'

export type ExpressionIntent =
  | 'ANSWER'
  | 'ADD_CONTEXT'
  | 'ASK'
  | 'CLARIFY'
  | 'CHALLENGE'
  | 'WARN'
  | 'SUMMARIZE'
  | 'STAY_SILENT'

export type ConversationFactKind =
  | 'DECISION'
  | 'COMMITMENT'
  | 'TASK'
  | 'DEADLINE'
  | 'RISK'
  | 'ASSUMPTION'
  | 'OPEN_QUESTION'
  | 'PROPOSAL'
  | 'OBJECTION'
  | 'METRIC'
  | 'STATUS'

export type ConversationFactState =
  | 'PROPOSED'
  | 'AGREED'
  | 'COMMITTED'
  | 'DONE'
  | 'SUPERSEDED'
  | 'UNKNOWN'

export interface ConversationGoal {
  id: string
  title: string
  objective: string
  profile: ConversationProfile
  metadata?: Record<string, unknown>
}

export interface CounterpartyState {
  /** Observed/explicit state only — never private mental-state inference. */
  id?: string
  display_name?: string
  role?: string
  observed_priorities: string[]
  explicit_constraints: string[]
  open_threads: string[]
}

export interface ConversationState {
  profile: ConversationProfile
  goal_id: string
  current_topic: string
  current_speaker_id: string
  active_question: string
  open_threads: string[]
  counterparties: CounterpartyState[]
}

export interface ConversationGuidance {
  kind: GuidanceKind
  text: string
  intent: ExpressionIntent
  source_refs: string[]
  confidence?: number
  interrupt_cost?: number
}
