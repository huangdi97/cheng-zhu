// 指南（Guidance）视图模型：把 WS `answer_done` 事件负载解析成首屏可安全渲染的纯数据。
// INVARIANT: 负载形状取决于后端版本（unknown），解析永不抛错；任何缺失/畸形字段都降级为空值，
// 组件拿到的一定是完整的 GuidanceViewModel，不需要再做防御。
// 纯视图模型层：刻意不 import React/Zustand，由组件按需消费。

export interface GuidanceViewModel {
  question: string
  resolvedQuestion: string
  coreIdeas: string[]
  evidence: string[]
  mode: string
  intent: string[]
  stateContext: string
  firstTokenMs: number | null
  totalMs: number | null
  hasAnswer: boolean
}

// 后端指引的条目上限：超出部分丢弃，保证 glance 首屏可扫读。
const CORE_IDEAS_CAP = 8
const EVIDENCE_CAP = 4

export const EMPTY_GUIDANCE_VIEW_MODEL: GuidanceViewModel = {
  question: '',
  resolvedQuestion: '',
  coreIdeas: [],
  evidence: [],
  mode: '',
  intent: [],
  stateContext: '',
  firstTokenMs: null,
  totalMs: null,
  hasAnswer: false,
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}

function toFiniteNumber(value: unknown): number | null {
  // 只接受有限数字：NaN/Infinity/字符串等一律视为缺失，前端不做隐式数值转换。
  if (typeof value === 'number' && Number.isFinite(value)) return value
  return null
}

function toStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string')
}

function toCappedStringList(value: unknown, cap: number): string[] {
  return toStringList(value).slice(0, cap)
}

export function buildGuidanceViewModel(payload: unknown): GuidanceViewModel {
  const data = isRecord(payload) ? payload : {}
  const guidance = isRecord(data.guidance) ? data.guidance : {}
  return {
    question: typeof data.question === 'string' ? data.question : '',
    resolvedQuestion: typeof guidance.resolved_question === 'string' ? guidance.resolved_question : '',
    coreIdeas: toCappedStringList(guidance.core_ideas, CORE_IDEAS_CAP),
    evidence: toCappedStringList(guidance.evidence, EVIDENCE_CAP),
    mode: typeof guidance.mode === 'string' ? guidance.mode : '',
    intent: toStringList(guidance.intent),
    stateContext: typeof guidance.state_context === 'string' ? guidance.state_context : '',
    firstTokenMs: toFiniteNumber(data.first_token_ms),
    totalMs: toFiniteNumber(data.total_ms),
    hasAnswer: typeof data.answer === 'string' && data.answer.trim().length > 0,
  }
}

// glance 首屏能否渲染：有当前问题或核心思路即可，完整答案属于展开后的内容。
export function isGlanceReady(vm: GuidanceViewModel): boolean {
  return vm.question.trim().length > 0 || vm.coreIdeas.length > 0
}

// ---------------------------------------------------------------------------
// R2 Fast Cue：guidance_fast 负载 → 首屏 cue 视图模型。Main UI 与 Overlay 共用。
// INVARIANT: cue 是内容（"RAG 更适合频繁更新的知识"），来源必须是四类之一；
// 解析永不抛错，未知来源一律降级为 WORLD_KNOWLEDGE（绝不冒充个人证据）。
// ---------------------------------------------------------------------------

export type CueSource = 'PERSONAL_EVIDENCE' | 'KB_KNOWLEDGE' | 'WORLD_KNOWLEDGE' | 'HUMAN_COACH'

export interface CueItem {
  text: string
  source: CueSource
  provenance: string
}

export interface FastCueViewModel {
  direction: string
  cues: CueItem[]
  cautions: string[]
  jobFocus: string
  responseMode: string
  level: string
  ttfugUserMs: number | null
  ttfugInternalMs: number | null
}

export const CUE_SOURCE_LABELS: Record<CueSource, string> = {
  PERSONAL_EVIDENCE: '个人来源',
  KB_KNOWLEDGE: '资料',
  WORLD_KNOWLEDGE: '通用知识',
  HUMAN_COACH: '教练建议',
}

const CUE_CAP = 5
const KNOWN_SOURCES = new Set<CueSource>(['PERSONAL_EVIDENCE', 'KB_KNOWLEDGE', 'WORLD_KNOWLEDGE', 'HUMAN_COACH'])

export function buildFastCueViewModel(payload: unknown): FastCueViewModel | null {
  if (!isRecord(payload)) return null
  const rawCues = Array.isArray(payload.cues) ? payload.cues : []
  const cues: CueItem[] = []
  for (const raw of rawCues) {
    if (!isRecord(raw) || typeof raw.text !== 'string' || !raw.text.trim()) continue
    const source = (typeof raw.source === 'string' && KNOWN_SOURCES.has(raw.source as CueSource)
      ? raw.source
      : 'WORLD_KNOWLEDGE') as CueSource
    cues.push({ text: raw.text, source, provenance: typeof raw.provenance === 'string' ? raw.provenance : '' })
    if (cues.length >= CUE_CAP) break
  }
  const direction = typeof payload.direction === 'string' ? payload.direction : ''
  if (!cues.length && !direction) return null
  return {
    direction,
    cues,
    cautions: toCappedStringList(payload.cautions, 3),
    jobFocus: typeof payload.job_focus === 'string' ? payload.job_focus : '',
    responseMode: typeof payload.response_mode === 'string' ? payload.response_mode : '',
    level: typeof payload.level === 'string' ? payload.level : 'L0',
    ttfugUserMs: toFiniteNumber(payload.ttfug_user_ms),
    ttfugInternalMs: toFiniteNumber(payload.ttfug_internal_ms),
  }
}

export interface LiveGuidance {
  vm: GuidanceViewModel
  cue: FastCueViewModel | null
}

/** QA 条目 → 首屏数据。qa.guidance 是 answer_done.guidance（内层对象），qa.fastCue 是 guidance_fast。 */
export function buildLiveGuidance(qa: { question?: string; answer?: string; guidance?: unknown; fastCue?: unknown; firstTokenMs?: number; totalMs?: number } | null | undefined): LiveGuidance {
  if (!qa) return { vm: EMPTY_GUIDANCE_VIEW_MODEL, cue: null }
  const vm = buildGuidanceViewModel({
    question: qa.question ?? '',
    answer: qa.answer ?? '',
    guidance: qa.guidance,
    first_token_ms: qa.firstTokenMs,
    total_ms: qa.totalMs,
  })
  const guidance = isRecord(qa.guidance) ? qa.guidance : {}
  const cue = buildFastCueViewModel(qa.fastCue ?? guidance.fast_cue)
  return { vm, cue }
}
