import { apiRequest as request } from './api'
import type {
  AssistanceMode,
  CaptureMode,
  ConversationContinue,
  ConversationDraftAction,
  ConversationGuidance,
  ConversationHome,
  ConversationItem,
  ConversationItemType,
  ConversationPreflight,
  ConversationPrepare,
  ConversationProfile,
  ConversationSession,
  ConversationSpace,
  ConversationSpaceDetail,
  ConversationTemplate,
  ProcessingMode,
  SourceRef,
} from './conversationContracts'

const B = '/api/product/conversation'
const json = (method: string, body?: unknown): RequestInit => ({ method, body: JSON.stringify(body ?? {}) })

function list<T>(payload: unknown): { items: T[] } {
  const items = (payload as { items?: unknown } | null)?.items
  return { items: Array.isArray(items) ? (items as T[]) : [] }
}

export const conversationApi = {
  templates: () => request<unknown>(`${B}/templates`).then((p) => list<ConversationTemplate>(p)),
  home: () => request<ConversationHome>(`${B}/home`),
  adhoc: (body: { title?: string; profile?: ConversationProfile; assistance_mode?: AssistanceMode } = {}) =>
    request<{ space: ConversationSpace; session: ConversationSession; pack: Record<string, unknown> }>(`${B}/adhoc`, json('POST', body)),
  spaces: () => request<unknown>(`${B}/spaces`).then((p) => list<ConversationSpace>(p)),
  createSpace: (body: {
    title: string
    profile: ConversationProfile
    description?: string
    default_goal?: string
    default_mode?: AssistanceMode | ''
  }) => request<ConversationSpace>(`${B}/spaces`, json('POST', body)),
  space: (id: string) => request<ConversationSpaceDetail>(`${B}/spaces/${encodeURIComponent(id)}`),
  patchSpace: (id: string, body: Partial<ConversationSpace>) =>
    request<ConversationSpace>(`${B}/spaces/${encodeURIComponent(id)}`, json('PATCH', body)),
  deleteSpace: (id: string) => request<{ deleted: boolean }>(`${B}/spaces/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  prepare: (id: string) => request<ConversationPrepare>(`${B}/spaces/${encodeURIComponent(id)}/prepare`),
  exportSpace: (id: string) => request<Record<string, unknown>>(`${B}/spaces/${encodeURIComponent(id)}/export`),
  addGoal: (id: string, body: { title: string; outcome_definition?: string; priority?: number }) =>
    request(`${B}/spaces/${encodeURIComponent(id)}/goals`, json('POST', body)),
  addParticipant: (id: string, body: { display_name?: string; role?: string; organization?: string }) =>
    request(`${B}/spaces/${encodeURIComponent(id)}/participants`, json('POST', body)),
  createSession: (id: string, body: {
    title?: string
    goal_ids?: string[]
    scheduled_at?: number | null
    capture_mode: CaptureMode
    processing_mode: ProcessingMode
    assistance_mode: AssistanceMode
    consent_ack: boolean
  }) => request<ConversationSession>(`${B}/spaces/${encodeURIComponent(id)}/sessions`, json('POST', body)),
  session: (id: string) => request<ConversationSession>(`${B}/sessions/${encodeURIComponent(id)}`),
  patchSession: (id: string, body: Partial<Pick<ConversationSession, 'assistance_mode' | 'capture_mode' | 'processing_mode' | 'consent_ack'>>) =>
    request<ConversationSession>(`${B}/sessions/${encodeURIComponent(id)}`, json('PATCH', body)),
  ask: (id: string, question: string) =>
    request<{ answer: string; matches: ConversationItem[]; grounded: boolean }>(`${B}/sessions/${encodeURIComponent(id)}/ask`, json('POST', { question })),
  preflight: (id: string) => request<ConversationPreflight>(`${B}/sessions/${encodeURIComponent(id)}/preflight`),
  start: (id: string) => request<{ session: ConversationSession; pack: Record<string, unknown> }>(`${B}/sessions/${encodeURIComponent(id)}/start`, json('POST')),
  end: (id: string) => request<ConversationContinue>(`${B}/sessions/${encodeURIComponent(id)}/end`, json('POST')),
  continue: (id: string) => request<ConversationContinue>(`${B}/sessions/${encodeURIComponent(id)}/continue`),
  addItem: (id: string, body: {
    item_type: ConversationItemType
    title: string
    owner_id?: string
    due_at?: string
    source_refs?: SourceRef[]
    source_excerpt?: string
    confidence?: number
    epistemic_status?: string
    review_status?: string
  }) => request<ConversationItem>(`${B}/sessions/${encodeURIComponent(id)}/items`, json('POST', body)),
  reviewItem: (id: string, action: 'CONFIRM' | 'EDIT' | 'REJECT' | 'DONE' | 'SUPERSEDE', patch: Record<string, unknown> = {}) =>
    request<ConversationItem>(`${B}/items/${encodeURIComponent(id)}/review`, json('POST', { action, patch })),
  evaluateGuidance: (id: string, body: {
    current_topic?: string
    direct_question?: string
    answer_cue?: string
    candidate_text?: string
    source_refs?: SourceRef[]
    user_speaking?: boolean
    relevance?: number
    novelty?: number
    provenance_strength?: number
    role_relevance?: number
    goal_relevance?: number
    urgency?: number
    decision_impact?: number
    interruption_cost?: number
    already_mentioned?: number
    uncertainty?: number
    social_risk?: number
    stale_context_risk?: number
  }) => request<{ guidance: ConversationGuidance | null; suppressed: string | null; event?: ConversationGuidance }>(
    `${B}/sessions/${encodeURIComponent(id)}/guidance/evaluate`, json('POST', body),
  ),
  guidanceAction: (id: string, action: string) =>
    request<ConversationGuidance>(`${B}/guidance/${encodeURIComponent(id)}/status`, json('POST', { action })),
  followupDraft: (sessionId: string) =>
    request<ConversationDraftAction>(`${B}/sessions/${encodeURIComponent(sessionId)}/followup-draft`, json('POST')),
  draftActions: (spaceId: string) =>
    request<unknown>(`${B}/spaces/${encodeURIComponent(spaceId)}/draft-actions`).then((p) => list<ConversationDraftAction>(p)),
  reviewDraftAction: (id: string, action: 'APPROVE' | 'DISMISS' | 'RESET') =>
    request<ConversationDraftAction>(`${B}/draft-actions/${encodeURIComponent(id)}/review`, json('POST', { action })),
}
