import { apiRequest as request } from './api'
import type {
  AssistanceMode,
  CaptureMode,
  ConversationCaptureStatus,
  ConversationContinue,
  ConversationDraftAction,
  ConversationGuidance,
  ConversationHistoryItem,
  ConversationHome,
  ConversationItem,
  ConversationItemType,
  ConversationPreflight,
  ConversationPrepare,
  ConversationProfile,
  ConversationSession,
  ConversationTranscriptSegment,
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
  history: (limit = 100) => request<{ items: ConversationHistoryItem[] }>(`${B}/history?limit=${limit}`),
  diagnostics: () => request<Record<string, unknown>>(`${B}/diagnostics`),
  demo: () => request<{
    evidence: 'SYNTHETIC_DEMO'
    scenario: string
    title: string
    goal: string
    steps: Array<{ kind: string; title: string; input: string; output: string; state?: string; source?: string }>
    privacy: Record<string, string>
  }>(`${B}/demo`),
  adhoc: (body: { title?: string; profile?: ConversationProfile; assistance_mode?: AssistanceMode } = {}) =>
    request<{ space: ConversationSpace; session: ConversationSession; pack: Record<string, unknown> }>(`${B}/adhoc`, json('POST', body)),
  spaces: (status = '') => request<unknown>(`${B}/spaces${status ? `?status=${encodeURIComponent(status)}` : ''}`).then((p) => list<ConversationSpace>(p)),
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
  retentionPreview: (id: string) => request<{
    space_id: string
    policy: Record<string, unknown>
    would_delete: { transcript_segments: number; guidance_events: number; draft_actions: number }
    kept: Record<string, string>
    destructive: boolean
  }>(`${B}/spaces/${encodeURIComponent(id)}/retention`),
  applyRetention: (id: string, confirm: boolean) =>
    request<{ deleted: Record<string, number>; policy: Record<string, unknown> }>(`${B}/spaces/${encodeURIComponent(id)}/retention/apply`, json('POST', { confirm })),

  addGoal: (id: string, body: { title: string; outcome_definition?: string; priority?: number }) =>
    request(`${B}/spaces/${encodeURIComponent(id)}/goals`, json('POST', body)),
  addParticipant: (id: string, body: {
    display_name?: string
    role?: string
    organization?: string
    explicit_priority?: string
    explicit_concern?: string
    stated_position?: string
    decision_authority?: string
    relationship_context?: string
    source_refs?: Array<Record<string, unknown>>
  }) => request(`${B}/spaces/${encodeURIComponent(id)}/participants`, json('POST', body)),
  createSession: (id: string, body: {
    title?: string
    goal_ids?: string[]
    scheduled_at?: number | null
    capture_mode: CaptureMode
    processing_mode: ProcessingMode
    assistance_mode: AssistanceMode
    consent_ack: boolean
    policy?: Partial<ConversationSession['policy']>
  }) => request<ConversationSession>(`${B}/spaces/${encodeURIComponent(id)}/sessions`, json('POST', body)),
  session: (id: string) => request<ConversationSession>(`${B}/sessions/${encodeURIComponent(id)}`),
  deleteSession: (id: string, confirmed_policy: 'BLOCK' | 'TOMBSTONE' = 'BLOCK') =>
    request<{ deleted: boolean; session_id: string; provenance_tombstones: number }>(`${B}/sessions/${encodeURIComponent(id)}/delete`, json('POST', { confirmed_policy })),

  patchSession: (id: string, body: Partial<Pick<ConversationSession, 'assistance_mode' | 'capture_mode' | 'processing_mode' | 'consent_ack' | 'policy'>>) =>
    request<ConversationSession>(`${B}/sessions/${encodeURIComponent(id)}`, json('PATCH', body)),
  ask: (id: string, question: string) =>
    request<{ answer: string; matches: ConversationItem[]; grounded: boolean }>(`${B}/sessions/${encodeURIComponent(id)}/ask`, json('POST', { question })),
  captureStatus: (id: string) =>
    request<ConversationCaptureStatus>(`${B}/sessions/${encodeURIComponent(id)}/capture`),
  captureStart: (id: string, device_id: number, candidate_mic_device_id?: number | null) =>
    request<ConversationCaptureStatus>(`${B}/sessions/${encodeURIComponent(id)}/capture/start`, json('POST', {
      device_id,
      ...(candidate_mic_device_id != null ? { candidate_mic_device_id } : {}),
    })),
  capturePause: (id: string) =>
    request<ConversationCaptureStatus>(`${B}/sessions/${encodeURIComponent(id)}/capture/pause`, json('POST')),
  captureResume: (id: string) =>
    request<ConversationCaptureStatus>(`${B}/sessions/${encodeURIComponent(id)}/capture/resume`, json('POST')),
  captureStop: (id: string) =>
    request<ConversationCaptureStatus>(`${B}/sessions/${encodeURIComponent(id)}/capture/stop`, json('POST')),
  transcript: (id: string, limit = 100) =>
    request<unknown>(`${B}/sessions/${encodeURIComponent(id)}/transcript?limit=${limit}`).then((p) => list<ConversationTranscriptSegment>(p)),
  guidanceHistory: (id: string, limit = 30) =>
    request<unknown>(`${B}/sessions/${encodeURIComponent(id)}/guidance?limit=${limit}`).then((p) => list<ConversationGuidance>(p)),
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
