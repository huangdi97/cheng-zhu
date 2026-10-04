/** Typed client for the v1.3 Goal-centered product API (`/api/product`). */
import { apiRequest as request, apiUpload as uploadRequest } from './api'

const B = '/api/product'
const q = (params: Record<string, string | number | boolean | undefined | null>) => {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  return entries.length ? `?${entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join('&')}` : ''
}
const json = (method: string, body?: unknown): RequestInit => ({ method, body: JSON.stringify(body ?? {}) })

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type GoalStatus = 'ACTIVE' | 'PAUSED' | 'COMPLETED' | 'ARCHIVED'
export type OfferState = 'NONE' | 'PENDING' | 'RECEIVED' | 'NEGOTIATING' | 'ACCEPTED' | 'DECLINED'

export interface Goal {
  id: string
  title: string
  company: string
  role: string
  jd: string
  status: GoalStatus
  stage: string
  next_interview_at: number | null
  interview_round: string
  goal_notes: string
  selected_resume_id: number | null
  selected_material_ids: string[]
  selected_kb_ids: string[]
  selected_quick_note_ids: string[]
  active_question_bank_ids: string[]
  next_focus_id: string
  offer_state: OfferState
  role_family: string
  legacy_prep_space_id: number | null
  application_id: number | null
  last_opened_at: number | null
  created_at: number
  updated_at: number
}

export interface FocusAction {
  key: string
  label: string
}

export interface NextFocusItem {
  id: string
  goal_id: string
  type: string
  title: string
  reason: string
  source_kind: string
  source_ref: string
  actions: FocusAction[]
  priority: number
  status: string
  origin: 'USER' | 'DERIVED'
}

export interface GoalInterview {
  id: string
  goal_id: string
  round: string
  kind: 'REAL' | 'MOCK'
  status: 'UPCOMING' | 'DONE' | 'CANCELLED'
  scheduled_at: number | null
  notes: string
}

export interface GoalOffer {
  goal_id: string
  status: OfferState
  comp: string
  deadline: number | null
  notes: string
  updated_at: number | null
}

export interface HistoryItem {
  key: string
  type: 'REAL' | 'PRACTICE'
  guided: boolean
  reflection_ref: { session_kind: 'PRACTICE' | 'REVIEW'; session_ref: string }
  review_session_id: number | null
  goal_id: string
  goal_title: string
  round: string
  title: string
  panel: boolean
  started_at: number
  ended_at: number | null
  turn_count?: number
  has_reflection_actions?: boolean
}

export interface GoalDetail extends Goal {
  interviews: GoalInterview[]
  offer: GoalOffer
  next_focus: NextFocusItem[]
  sessions: HistoryItem[]
}

export interface AttentionItem {
  kind: string
  text: string
  count?: number
  action: { key: string; label: string; goal_id?: string; target?: string }
}

export interface HomeSummary {
  state: 'NO_GOAL' | 'GOAL_NO_SESSION' | 'ACTIVE'
  primary_action: { key: string; label: string; goal_id?: string }
  next_interview: null | {
    goal_id: string
    interview_id: string
    title: string
    company: string
    role: string
    round: string
    scheduled_at: number
    actions: FocusAction[]
  }
  focus_goal: { id: string; title: string } | null
  next_focus: NextFocusItem[]
  needs_attention: AttentionItem[]
  recent_session: HistoryItem | null
  active_goal_count: number
}

export interface GapItem {
  topic: string
  status: string
  source: string
  priority: string
  reason: string
}

export interface QuestionNode {
  id: string
  text: string
  kind: string
  source: string
  parent_id: string
}

export interface StoryCoverage {
  categories: Array<{ key: string; label: string; story_ids: string[] }>
  missing: Array<{ key: string; label: string }>
}

export interface GoalPrepare {
  goal_id: string
  next_focus: NextFocusItem[]
  gap_map: GapItem[]
  attack_surface: Array<{ claim_id: string; text: string; risks: string[]; probes: string[] }>
  question_graph: QuestionNode[]
  stories: { items: Array<{ id: string; title: string; tags: string[] }>; prompts: Array<{ competency: string; hint: string }>; coverage: StoryCoverage }
  has_jd: boolean
  materials: { included: PackMaterial[]; skipped: Array<{ material_id: string; title: string; reason: string }>; selected_ids: string[] }
  pack_preview: { quick_notes: Array<{ id: string; title: string; content: string }>; materials: PackMaterial[]; legacy_prep_space_id: number | null }
}

export interface PackMaterial {
  material_id: string
  version_id: string
  version: number
  title: string
  kind: string
  usage: string
  is_personal_evidence: boolean
}

export type MaterialState = 'PROCESSING' | 'READY' | 'FAILED' | 'REPLACING'

export interface MaterialVersion {
  id: string
  version: number
  filename: string
  status: string
  error: string
  chars: number
  created_at: number
}

export interface Material {
  id: string
  kind: 'PROJECT' | 'KB'
  usage: 'FACTS' | 'REFERENCE' | 'BOTH'
  title: string
  active_version_id: string
  created_at: number
  updated_at: number
  lifecycle: {
    state: MaterialState
    active_version: MaterialVersion | null
    latest_version: MaterialVersion | null
    error: string
    actions: string[]
  }
}

export interface QuickNote {
  id: string
  scope: 'GLOBAL' | 'GOAL'
  goal_id: string | null
  title: string
  content: string
  pinned: boolean
  sort_order: number
  tags: string[]
  revision: number
  created_at: number
  updated_at: number
}

export interface QuestionBank {
  id: string
  name: string
  scope: string
  role: string
  company: string
  source_type: string
  goal_id: string | null
  builtin: boolean
  item_count: number
}

export interface QuestionBankItem {
  id: string
  bank_id: string
  text: string
  category: string
  difficulty: 'WARMUP' | 'STANDARD' | 'PRESSURE'
  origin: string
  source_url: string
  label: string
  rounds: string[]
}

export interface FactInboxCard {
  id: string
  text: string
  project: string
  source: string
  provenance_status: string
  risk: 'HIGH' | 'MEDIUM' | 'LOW'
  supported_label: string
  lead_language: boolean
  primary_actions: string[]
  more_actions: string[]
}

export interface FactInbox {
  count: number
  items: FactInboxCard[]
  batch: { count: number; ids: string[] } | null
  merge_suggestions: string[][]
  policy: { mode: 'STANDARD' | 'HIGH_ONLY'; reasons: string[] }
}

export interface Option {
  key: string
  label: string
}

export interface PersonaOption extends Option {
  concern: string
  followup_style: string
  demeanor: string
}

export interface PracticeOptions {
  rounds: Option[]
  demeanors: Option[]
  difficulties: Option[]
  sources: Option[]
  personas: PersonaOption[]
  defaults?: PracticeDefaults
}

export interface PracticeDefaults {
  round: string
  focus: { id: string; type: string; title: string; reason: string } | null
  demeanor: string
  difficulty: string
  sources: string[]
}

export interface PracticeConfig {
  goal_id?: string | null
  round: string
  personas: string[]
  demeanor: string
  difficulty: string
  sources: string[]
  questions: number
  language: 'zh' | 'en'
  human_coach?: boolean
  focus?: PracticeDefaults['focus']
  guided?: boolean
  delivery_analytics?: boolean
  closing?: boolean
}

export interface PracticeQuestion {
  id: string
  seq: number
  question: string
  move: string
  source: string
  persona_id: string
  persona_label: string
}

export interface PanelState {
  personas: Array<{ id: string; label: string; concern: string; followup_style: string; demeanor: string }>
  current_speaker: string
  next_speaker: string
  shared_topic: string
  is_panel: boolean
}

export interface ContentFinding {
  signal: string
  dimension: string
  level: number
  finding: string
  evidence_from_actual_speech: string
  action: string
}

export interface PracticeFeedback {
  content: { signals: Record<string, number>; findings: ContentFinding[]; strengths: Array<{ dimension: string; evidence_from_actual_speech: string }> }
  delivery: null | { metrics: Record<string, number | boolean | null>; advice: string[] }
}

export interface PracticeReport {
  practice_id: string
  review_session_id: number | null
  goal_id: string | null
  turn_count: number
  went_well: string[]
  to_improve: string[]
  delivery: string[]
}

export interface PracticeStartResult {
  practice_id: string
  config: PracticeConfig
  question: PracticeQuestion
  panel: PanelState
  pool_size: number
  total: number
}

export interface PracticeAnswerResult {
  done: boolean
  answered: number
  feedback: PracticeFeedback
  next_question?: PracticeQuestion
  panel?: PanelState
  report?: PracticeReport
}

export interface PinMoment {
  id: string
  session_kind: 'LIVE' | 'PRACTICE'
  session_id: string
  turn_id: string
  goal_id: string | null
  tag: string
  tag_label?: string
  question: string
  transcript_excerpt: string
  note: string
  ts: number
}

export interface ReflectionFinding {
  id: string
  kind: string
  kind_label?: string
  dimension?: string
  dimension_label?: string
  finding: string
  action_hint?: string
  turn_id?: string
  question: string
  actual_speech: string
  source?: string
  occurrences?: number
  session_claim_id?: string
  claim_id?: string
}

export interface Reflection {
  session_kind: 'PRACTICE' | 'REVIEW'
  session_ref: string
  goal_id: string | null
  title: string
  first_screen: {
    next_step: null | { kind: string; title: string; reason: string; finding_id?: string; pin_id?: string; goal_id?: string | null }
    pinned_moments: PinMoment[]
    went_well: Array<{ dimension: string; dimension_label: string; question: string; actual_speech: string }>
    to_improve: ReflectionFinding[]
    fact_checks: ReflectionFinding[]
    story_opportunities: Array<{ id: string; kind: string; question: string; actual_speech: string; hint: string }>
  }
  delivery: string[]
  timeline: Array<{ turn_id: string; seq: number; question: string; actual_speech: string; move: string; persona: string; content: PracticeFeedback['content'] }>
  actions: string[]
  ask_cue_feedback: boolean
}

export interface PreflightItem {
  key: string
  label: string
  value: string | number | boolean
  origin: string
  origin_label: string
  ok: boolean
  hint: string
}

export interface Preflight {
  goal: { id: string; title: string }
  items: PreflightItem[]
  blockers: PreflightItem[]
  share_privacy_note: string
}

export interface Nudge {
  id: string
  kind: string
  text: string
  topic_key: string
  status: string
  priority: number
}

export interface ClosingSuggestion {
  kind: string
  source: string
  text: string
  basis: string
}

export interface SettingLayer {
  value: unknown
  origin: 'SESSION' | 'GOAL' | 'GLOBAL' | 'SYSTEM'
  origin_label: string
  label: string
  group: string
  goal_value: unknown
  session_value: unknown
  global_value: unknown
}

export interface TrendDimension {
  dimension: string
  label: string
  series: number[]
  direction: 'IMPROVING' | 'DECLINING' | 'REPEATING' | 'STABLE' | 'INSUFFICIENT'
  text: string
}

export interface Trends {
  goal_id: string | null
  sessions: number
  dimensions: TrendDimension[]
  delivery: null | { text: string; direction: string; series: number[] }
  note: string
}

export interface Rubric {
  role_family: string
  label: string
  dimensions: Array<{ key: string; label: string; weight: number }>
  levels: Record<string, string>
  note: string
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

/**
 * The practice setup screen reads these lists directly. A partial or unexpected
 * payload must render the setup with empty pickers, never crash the page.
 */
function withPracticeDefaults(payload: unknown): PracticeOptions {
  const p = (payload ?? {}) as Partial<PracticeOptions>
  return {
    rounds: p.rounds ?? [],
    demeanors: p.demeanors ?? [],
    difficulties: p.difficulties ?? [],
    sources: p.sources ?? [],
    personas: p.personas ?? [],
    defaults: p.defaults,
  }
}

/**
 * Response normalisers for the v1.3 product API.
 *
 * Every screen under `components/os` reads these payloads directly, and the
 * bodies are untrusted. A partial or unexpected response is coerced to the
 * endpoint's documented empty shape here — at the boundary — instead of letting
 * `.map` / `.filter` / `.length` crash the whole screen.
 */
function itemsList<T>(payload: unknown): { items: T[] } {
  const items = (payload as { items?: unknown } | null)?.items
  return { items: Array.isArray(items) ? (items as T[]) : [] }
}

function withHomeDefaults(payload: unknown): HomeSummary {
  const p = (payload ?? {}) as Partial<HomeSummary>
  // An unknown body degrades to the neutral "no sessions yet" state. Claiming
  // NO_GOAL would tell a user who already has goals to create their first one.
  return {
    state: p.state === 'NO_GOAL' || p.state === 'GOAL_NO_SESSION' ? p.state : 'ACTIVE',
    primary_action: p.primary_action ?? { key: 'create_goal', label: '创建第一个求职目标' },
    next_interview: p.next_interview ?? null,
    focus_goal: p.focus_goal ?? null,
    next_focus: Array.isArray(p.next_focus) ? p.next_focus : [],
    needs_attention: Array.isArray(p.needs_attention) ? p.needs_attention : [],
    recent_session: p.recent_session ?? null,
    active_goal_count: p.active_goal_count ?? 0,
  }
}

function withNextFocusDefaults(payload: unknown): { items: NextFocusItem[]; practice_defaults: PracticeDefaults } {
  const p = (payload ?? {}) as Partial<{ items: NextFocusItem[]; practice_defaults: PracticeDefaults }>
  return {
    items: Array.isArray(p.items) ? p.items : [],
    practice_defaults: p.practice_defaults ?? { round: '', focus: null, demeanor: '', difficulty: '', sources: [] },
  }
}

function withStoryCoverageDefaults(payload: unknown): { stories: Array<Record<string, unknown>> } & StoryCoverage {
  const p = (payload ?? {}) as Partial<{ stories: Array<Record<string, unknown>> } & StoryCoverage>
  return {
    stories: Array.isArray(p.stories) ? p.stories : [],
    categories: Array.isArray(p.categories) ? p.categories : [],
    missing: Array.isArray(p.missing) ? p.missing : [],
  }
}

function withFactInboxDefaults(payload: unknown): FactInbox {
  const p = (payload ?? {}) as Partial<FactInbox>
  return {
    count: p.count ?? 0,
    items: Array.isArray(p.items) ? p.items : [],
    batch: p.batch ?? null,
    merge_suggestions: Array.isArray(p.merge_suggestions) ? p.merge_suggestions : [],
    policy: p.policy ?? { mode: 'STANDARD', reasons: [] },
  }
}

function withTrendsDefaults(payload: unknown): Trends {
  const p = (payload ?? {}) as Partial<Trends>
  const dimensions = Array.isArray(p.dimensions)
    ? p.dimensions
        .filter((d): d is TrendDimension => Boolean(d && typeof d === 'object'))
        .map((d) => ({
          dimension: typeof d.dimension === 'string' ? d.dimension : '',
          label: typeof d.label === 'string' ? d.label : (typeof d.dimension === 'string' ? d.dimension : '趋势'),
          series: Array.isArray(d.series) ? d.series.filter((n): n is number => typeof n === 'number' && Number.isFinite(n)) : [],
          direction: (['IMPROVING', 'DECLINING', 'REPEATING', 'STABLE', 'INSUFFICIENT'] as const).includes(d.direction)
            ? d.direction
            : 'INSUFFICIENT',
          text: typeof d.text === 'string' ? d.text : '',
        }))
        .filter((d) => d.dimension || d.label)
    : []
  const rawDelivery = p.delivery
  const delivery = rawDelivery && typeof rawDelivery === 'object'
    ? {
        text: typeof rawDelivery.text === 'string' ? rawDelivery.text : '',
        direction: typeof rawDelivery.direction === 'string' ? rawDelivery.direction : 'INSUFFICIENT',
        series: Array.isArray(rawDelivery.series)
          ? rawDelivery.series.filter((n): n is number => typeof n === 'number' && Number.isFinite(n))
          : [],
      }
    : null
  return {
    goal_id: typeof p.goal_id === 'string' ? p.goal_id : null,
    sessions: typeof p.sessions === 'number' && Number.isFinite(p.sessions) ? p.sessions : 0,
    dimensions,
    delivery,
    note: typeof p.note === 'string' ? p.note : '',
  }
}

export const productApi = {
  home: () => request<unknown>(`${B}/home`).then(withHomeDefaults),

  goals: (status = '') => request<unknown>(`${B}/goals${q({ status })}`).then((b) => itemsList<Goal>(b)),
  createGoal: (body: Partial<Pick<Goal, 'company' | 'role' | 'jd' | 'stage' | 'interview_round' | 'goal_notes'>> & { next_interview_at?: number | null }) =>
    request<Goal>(`${B}/goals`, json('POST', body)),
  goal: (id: string, opened = false) => request<GoalDetail>(`${B}/goals/${encodeURIComponent(id)}${q({ opened: opened || undefined })}`),
  patchGoal: (id: string, patch: Partial<Goal>) => request<Goal>(`${B}/goals/${encodeURIComponent(id)}`, json('PATCH', patch)),
  deleteGoal: (id: string) => request<{ deleted: boolean }>(`${B}/goals/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  prepare: (id: string) => request<GoalPrepare>(`${B}/goals/${encodeURIComponent(id)}/prepare`),
  addInterview: (id: string, body: { round: string; scheduled_at: number | null; kind?: string; notes?: string }) =>
    request<GoalInterview>(`${B}/goals/${encodeURIComponent(id)}/interviews`, json('POST', body)),
  patchInterview: (iid: string, body: Partial<GoalInterview>) => request<GoalInterview>(`${B}/interviews/${encodeURIComponent(iid)}`, json('PATCH', body)),
  deleteInterview: (iid: string) => request<{ deleted: boolean }>(`${B}/interviews/${encodeURIComponent(iid)}`, { method: 'DELETE' }),
  putOffer: (id: string, body: Partial<GoalOffer>) => request<GoalOffer>(`${B}/goals/${encodeURIComponent(id)}/offer`, json('PUT', body)),

  nextFocus: (goalId: string, refresh = false) =>
    request<unknown>(`${B}/goals/${encodeURIComponent(goalId)}/next-focus${q({ refresh: refresh || undefined })}`)
      .then(withNextFocusDefaults),
  setNextFocus: (goalId: string, body: { type: string; title: string; reason?: string; source_kind?: string; source_ref?: string }) =>
    request<NextFocusItem>(`${B}/goals/${encodeURIComponent(goalId)}/next-focus`, json('POST', body)),
  completeFocus: (id: string) => request<{ item: NextFocusItem }>(`${B}/next-focus/${encodeURIComponent(id)}/complete`, json('POST')),
  dismissFocus: (id: string) => request<{ item: NextFocusItem }>(`${B}/next-focus/${encodeURIComponent(id)}/dismiss`, json('POST')),

  history: (params: { goal_id?: string; type?: string; round?: string; since?: number; until?: number } = {}) =>
    request<unknown>(`${B}/history${q(params)}`).then((b) => itemsList<HistoryItem>(b)),
  linkHistoryGoal: (reviewSessionId: number, goalId: string, kind = 'REAL') =>
    request(`${B}/history/${reviewSessionId}/goal`, json('POST', { goal_id: goalId, kind })),
  trends: (goalId = '') => request<unknown>(`${B}/trends${q({ goal_id: goalId })}`).then(withTrendsDefaults),

  materials: (kind = '') => request<unknown>(`${B}/materials${q({ kind })}`).then((b) => itemsList<Material>(b)),
  createMaterial: (fields: { title: string; kind: string; usage: string; text?: string; file?: File | null }) => {
    const form = new FormData()
    form.append('title', fields.title)
    form.append('kind', fields.kind)
    form.append('usage', fields.usage)
    if (fields.text) form.append('text', fields.text)
    if (fields.file) form.append('file', fields.file)
    return uploadRequest<Material>(`${B}/materials`, form)
  },
  replaceMaterial: (id: string, fields: { text?: string; file?: File | null }) => {
    const form = new FormData()
    if (fields.text) form.append('text', fields.text)
    if (fields.file) form.append('file', fields.file)
    return uploadRequest<Material>(`${B}/materials/${encodeURIComponent(id)}/replace`, form)
  },
  retryMaterial: (id: string, fields: { text?: string; file?: File | null }) => {
    const form = new FormData()
    if (fields.text) form.append('text', fields.text)
    if (fields.file) form.append('file', fields.file)
    return uploadRequest<Material>(`${B}/materials/${encodeURIComponent(id)}/retry`, form)
  },
  setMaterialUsage: (id: string, usage: string) => request<Material>(`${B}/materials/${encodeURIComponent(id)}`, json('PATCH', { usage })),
  deleteMaterial: (id: string) => request<{ deleted: boolean }>(`${B}/materials/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  quickNotes: (params: { goal_id?: string; scope?: string; context?: string } = {}) =>
    request<unknown>(`${B}/quick-notes${q(params)}`).then((b) => itemsList<QuickNote>(b)),
  createQuickNote: (body: { content: string; title?: string; scope?: string; goal_id?: string | null; pinned?: boolean; tags?: string[] }) =>
    request<QuickNote>(`${B}/quick-notes`, json('POST', body)),
  patchQuickNote: (id: string, body: Partial<QuickNote> & { base_revision?: number }) =>
    request<QuickNote>(`${B}/quick-notes/${encodeURIComponent(id)}`, json('PATCH', body)),
  deleteQuickNote: (id: string) => request<{ deleted: boolean }>(`${B}/quick-notes/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  reorderQuickNotes: (ids: string[]) => request<{ changed: number }>(`${B}/quick-notes/reorder`, json('POST', { ids })),

  banks: (params: { role?: string; goal_id?: string } = {}) =>
    request<unknown>(`${B}/question-banks${q(params)}`).then((b) => itemsList<QuestionBank>(b)),
  createBank: (body: { name: string; scope?: string; role?: string; goal_id?: string | null }) => request<QuestionBank>(`${B}/question-banks`, json('POST', body)),
  bankItems: (id: string) =>
    request<unknown>(`${B}/question-banks/${encodeURIComponent(id)}/items`).then((b) => itemsList<QuestionBankItem>(b)),
  addBankItem: (id: string, body: { text: string; category?: string; difficulty?: string; origin?: string; source_url?: string; rounds?: string[] }) =>
    request<QuestionBankItem>(`${B}/question-banks/${encodeURIComponent(id)}/items`, json('POST', body)),
  importBankItems: (id: string, lines: string[], sourceUrl = '') =>
    request<{ imported: number }>(`${B}/question-banks/${encodeURIComponent(id)}/import`, json('POST', { lines, source_url: sourceUrl })),
  deleteBank: (id: string) => request<{ deleted: boolean }>(`${B}/question-banks/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  deleteBankItem: (id: string) => request<{ deleted: boolean }>(`${B}/question-bank-items/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  factInbox: (opened = false) =>
    request<unknown>(`${B}/fact-inbox${q({ opened: opened || undefined })}`).then(withFactInboxDefaults),
  factAction: (claimId: string, action: string, payload: Record<string, unknown> = {}) =>
    request<Record<string, unknown>>(`${B}/fact-inbox/${encodeURIComponent(claimId)}`, json('POST', { action, payload })),
  factBatch: (ids: string[], action: string) => request<{ done: string[]; failed: string[] }>(`${B}/fact-inbox/batch`, json('POST', { ids, action })),
  factMetrics: () => request<Record<string, unknown>>(`${B}/fact-inbox/metrics`),
  storyCoverage: () => request<unknown>(`${B}/stories/coverage`).then(withStoryCoverageDefaults),

  practiceOptions: (goalId = '') =>
    request<unknown>(`${B}/practice/options${q({ goal_id: goalId })}`).then(withPracticeDefaults),
  startPractice: (cfg: PracticeConfig) => request<PracticeStartResult>(`${B}/practice`, json('POST', cfg)),
  answerPractice: (id: string, body: { answer: string; duration_ms?: number | null }) =>
    request<PracticeAnswerResult>(`${B}/practice/${encodeURIComponent(id)}/answer`, json('POST', body)),
  finishPractice: (id: string) => request<PracticeReport>(`${B}/practice/${encodeURIComponent(id)}/finish`, json('POST')),
  practice: (id: string) => request<Record<string, unknown>>(`${B}/practice/${encodeURIComponent(id)}`),
  rubrics: (roleFamily = '') => request<Rubric | { items: Rubric[] }>(`${B}/rubrics${q({ role_family: roleFamily })}`),

  preflight: (goalId: string, overrides: Record<string, unknown> = {}) => request<Preflight>(`${B}/live/preflight`, json('POST', { goal_id: goalId, overrides })),
  liveStart: (goalId: string, overrides: Record<string, unknown> = {}) =>
    request<{ session_id: string; goal_id: string; pack: Record<string, unknown> }>(`${B}/live/start`, json('POST', { goal_id: goalId, overrides })),
  liveEnd: (sessionId = '', reviewSessionId: number | null = null) =>
    request<{ session_id: string; goal_id: string | null; review_session_id: number | null; reflection_ref: { session_kind: string; session_ref: string } | null }>(
      `${B}/live/end`, json('POST', { session_id: sessionId, review_session_id: reviewSessionId })),

  createPin: (body: { session_id?: string; session_kind?: 'LIVE' | 'PRACTICE'; tag: string; turn_id?: string; question?: string; transcript_excerpt?: string; note?: string; goal_id?: string | null }) =>
    request<PinMoment>(`${B}/pins`, json('POST', body)),
  patchPin: (id: string, body: { tag?: string; note?: string }) => request<PinMoment>(`${B}/pins/${encodeURIComponent(id)}`, json('PATCH', body)),
  promotePin: (id: string, goalId?: string | null) => request<NextFocusItem>(`${B}/pins/${encodeURIComponent(id)}/promote`, json('POST', { goal_id: goalId ?? null })),

  evaluateNudge: (body: Record<string, unknown>) => request<{ nudge: Nudge | null; suppressed: string | null }>(`${B}/nudges/evaluate`, json('POST', body)),
  nudgeStatus: (id: string, status: 'DISMISSED' | 'USED') => request(`${B}/nudges/${encodeURIComponent(id)}`, json('POST', { status })),
  nudgeNewQuestion: (sessionId: string) => request(`${B}/nudges/session/${encodeURIComponent(sessionId)}/new-question`, json('POST')),
  disableNudges: () => request(`${B}/nudges/disable`, json('POST')),
  closingDetect: (text: string) => request<{ trigger: string | null }>(`${B}/closing/detect`, json('POST', { text })),
  closingSuggest: (body: { session_id?: string; goal_id?: string | null; text?: string; transcript?: Array<{ speaker: string; text: string }>; open_threads?: string[] }) =>
    request<{ trigger: string; suggestions: ClosingSuggestion[] }>(`${B}/closing/suggest`, json('POST', body)),

  reflection: (kind: string, ref: string) => request<Reflection>(`${B}/reflection/${kind.toLowerCase()}/${encodeURIComponent(ref)}`),
  reflectionAction: (kind: string, ref: string, body: { action: string; finding: Record<string, unknown>; goal_id?: string | null; payload?: Record<string, unknown> }) =>
    request<Record<string, unknown>>(`${B}/reflection/${kind.toLowerCase()}/${encodeURIComponent(ref)}/actions`, json('POST', body)),
  reflectionFeedback: (kind: string, ref: string, answer: 'YES' | 'SOMEWHAT' | 'NO') =>
    request(`${B}/reflection/${kind.toLowerCase()}/${encodeURIComponent(ref)}/feedback`, json('POST', { question: 'fast_cue_helpful', answer })),

  settingLayers: (goalId = '', sessionId = '') =>
    request<{ items: Record<string, SettingLayer>; origin_labels: Record<string, string> }>(`${B}/settings/layers${q({ goal_id: goalId, session_id: sessionId })}`),
  setSettingLayer: (scope: 'GOAL' | 'SESSION', scopeId: string, key: string, value: unknown) =>
    request(`${B}/settings/layers`, json('PUT', { scope, scope_id: scopeId, key, value })),
  clearSettingLayer: (scope: 'GOAL' | 'SESSION', scopeId: string, key = '') =>
    request(`${B}/settings/layers${q({ scope, scope_id: scopeId, key })}`, { method: 'DELETE' }),

  validation: () => request<Record<string, unknown>>(`${B}/validation`),
  clearEvents: () => request<{ deleted: number }>(`${B}/events`, { method: 'DELETE' }),
  exportData: (body: { kind: string; goal_id?: string; session_kind?: string; session_ref?: string }) =>
    request<{ kind: string; path: string; filename: string; data: unknown }>(`${B}/export`, json('POST', body)),
  deleteSession: (kind: string, ref: string) => request<Record<string, unknown>>(`${B}/sessions/${kind.toLowerCase()}/${encodeURIComponent(ref)}`, { method: 'DELETE' }),
  integrity: (repair = false) => request<{ ok: boolean; issues: unknown[] }>(`${B}/integrity${q({ repair: repair || undefined })}`),
}

/** Fire-and-forget local product event (never throws, never blocks UI). */
export function track(name: string, props: Record<string, unknown> = {}, ids: { goal_id?: string; session_id?: string } = {}): void {
  try {
    void request(`${B}/events`, json('POST', { name, props, ...ids })).catch(() => undefined)
  } catch {
    /* api unavailable (tests, offline) */
  }
}
