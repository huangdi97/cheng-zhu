import type { StateCreator } from 'zustand'
import type { RootState } from './rootState'
import type { QAPair, QAStatus } from './types'

const CHUNK_THROTTLE_MS = 50
const MAX_TRANSCRIPTIONS = 200
const MAX_CANDIDATE_TRANSCRIPTIONS = 200

const _chunkBuffer: Map<string, { answer: string; think: string }> = new Map()
let _chunkFlushTimer: ReturnType<typeof setTimeout> | null = null
let _candidateSegmentIds: Array<string | null> = []

function takeTail<T>(items: T[], maxItems: number): T[] {
  return items.length > maxItems ? items.slice(-maxItems) : items
}

function normalizeVisionVerify(raw: unknown): QAPair['visionVerify'] | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const data = raw as { verdict?: unknown; reason?: unknown }
  const verdict = String(data.verdict || '').toUpperCase()
  if (verdict !== 'PASS' && verdict !== 'FAIL' && verdict !== 'UNKNOWN') return undefined
  return {
    verdict,
    reason: String(data.reason ?? ''),
  }
}

function _scheduleChunkFlush(set: (fn: (s: RootState) => Partial<RootState>) => void) {
  if (_chunkFlushTimer !== null) return
  _chunkFlushTimer = setTimeout(() => {
    _chunkFlushTimer = null
    const pending = new Map(_chunkBuffer)
    _chunkBuffer.clear()
    if (pending.size === 0) return
    set((s) => {
      const activeStreamingIds = new Set(s.streamingIds)
      return {
        qaPairs: s.qaPairs.map((qa) => {
          const buf = pending.get(qa.id)
          if (!buf || qa.status !== 'streaming' || !activeStreamingIds.has(qa.id)) return qa
          return {
            ...qa,
            thinkContent: buf.think ? qa.thinkContent + buf.think : qa.thinkContent,
            answer: buf.answer ? qa.answer + buf.answer : qa.answer,
            isThinking: buf.answer ? false : buf.think ? true : qa.isThinking,
          }
        }),
      }
    })
  }, CHUNK_THROTTLE_MS)
}

export interface CopilotHint {
  node_id?: string
  label?: string
  intent?: string
  confidence?: number
  high_risk?: boolean
  risk_advice?: string
  advice?: string
  predicted_followups?: Array<{ label?: string; question?: string }>
  uncertain?: boolean
  inferred_from_previous?: boolean
}

export interface QuestionParseStatus {
  stage: 'idle' | 'assembling' | 'parsed' | 'answering' | 'ignored' | 'discarded'
  message?: string
  raw_text?: string
  turn_id?: number
  clusters?: Array<{
    primary_question: string
    subquestions?: string[]
    constraints?: string[]
    context?: string[]
    question_type?: string
    confidence?: number
  }>
  needs_confirmation?: boolean
}

export interface InterviewSliceState {
  isRecording: boolean
  isPaused: boolean
  audioLevel: number
  candidateAudioLevel: number
  isTranscribing: boolean
  transcriptions: string[]
  transcriptionTimes: number[]
  interviewerPartial: string | null
  candidatePartial: string | null
  copilotHint: CopilotHint | null
  questionParseStatus: QuestionParseStatus | null
  candidateTranscriptions: string[]
  qaPairs: QAPair[]
  streamingIds: string[]
  currentStreamingId: string | null
  systemSummary: string
  memoManual: string
  translationsByQuestion: Record<string, { translated: string; to: string }>
  suggestionsById: Record<string, { text: string; question: string }>
  sessions: Array<{ id: string; label: string; created_at: number; qa_count: number; transcription_count: number; is_active: boolean; is_recording: boolean; is_paused: boolean }>
  activeSessionId: string
}

export interface InterviewSliceActions {
  setRecording: (v: boolean) => void
  setPaused: (v: boolean) => void
  setAudioLevel: (v: number) => void
  setCandidateAudioLevel: (v: number) => void
  setTranscribing: (v: boolean) => void
  addTranscription: (text: string) => void
  setInterviewerPartial: (text: string | null) => void
  setCandidatePartial: (text: string | null) => void
  setCopilotHint: (hint: CopilotHint | null) => void
  setQuestionParseStatus: (status: QuestionParseStatus | null) => void
  addCandidateTranscription: (text: string, meta?: { segmentId?: string; isFinal?: boolean }) => void
  startAnswer: (
    id: string,
    question: string,
    meta?: {
      source?: string
      modelName?: string
      questionType?: string
      questionCluster?: QAPair['questionCluster']
      clusterIndex?: number
      clusterCount?: number
    },
  ) => void
  appendThinkChunk: (id: string, chunk: string) => void
  appendAnswerChunk: (id: string, chunk: string) => void
  finalizeAnswer: (
    id: string,
    question: string,
    answer: string,
    thinkContent?: string,
    modelName?: string,
    firstTokenMs?: number,
    totalMs?: number,
  ) => void
  cancelAnswer: (id: string) => void
  errorAnswer: (id: string, message: string) => void
  setVisionVerify: (id: string, verdict: 'PASS' | 'FAIL' | 'UNKNOWN', reason: string) => void
  setInitData: (data: any) => void
  setMemo: (data: { system_summary?: string; memo_manual?: string }) => void
  addTranslation: (question: string, translated: string, to: string) => void
  addSuggestion: (id: string, text: string, question: string) => void
  setSessions: (items: Array<{ id: string; label: string; created_at: number; qa_count: number; transcription_count: number; is_active: boolean; is_recording: boolean; is_paused: boolean }>, activeId: string) => void
  clearSession: () => void
}

export type InterviewSlice = InterviewSliceState & InterviewSliceActions

export const createInterviewSlice: StateCreator<RootState, [], [], InterviewSlice> = (set) => ({
  isRecording: false,
  isPaused: false,
  audioLevel: 0,
  candidateAudioLevel: 0,
  isTranscribing: false,
  transcriptions: [],
  transcriptionTimes: [],
  interviewerPartial: null,
  candidatePartial: null,
  copilotHint: null,
  questionParseStatus: null,
  candidateTranscriptions: [],
  qaPairs: [],
  streamingIds: [],
  currentStreamingId: null,
  systemSummary: '',
  memoManual: '',
  translationsByQuestion: {},
  suggestionsById: {},
  sessions: [],
  activeSessionId: '',

  setRecording: (v) => set({ isRecording: v }),
  setPaused: (v) => set({ isPaused: v }),
  setAudioLevel: (v) => set({ audioLevel: v }),
  setCandidateAudioLevel: (v) => set({ candidateAudioLevel: v }),
  setTranscribing: (v) => set({ isTranscribing: v }),
  setInterviewerPartial: (text) => set({ interviewerPartial: text }),
  setCandidatePartial: (text) => set({ candidatePartial: text }),
  setCopilotHint: (hint) => set({ copilotHint: hint }),
  setQuestionParseStatus: (status) => set({ questionParseStatus: status }),
  addTranscription: (text) => set((s) => ({
    transcriptions: takeTail([...s.transcriptions, text], MAX_TRANSCRIPTIONS),
    transcriptionTimes: takeTail([...s.transcriptionTimes, Date.now() / 1000], MAX_TRANSCRIPTIONS),
  })),
  addCandidateTranscription: (text, meta) => set((s) => {
    const segmentId = meta?.segmentId || null
    if (segmentId) {
      const existingIndex = _candidateSegmentIds.lastIndexOf(segmentId)
      if (existingIndex >= 0 && existingIndex < s.candidateTranscriptions.length) {
        const next = [...s.candidateTranscriptions]
        next[existingIndex] = text
        return { candidateTranscriptions: next }
      }
    }
    if (s.candidateTranscriptions[s.candidateTranscriptions.length - 1] === text) {
      return { candidateTranscriptions: s.candidateTranscriptions }
    }
    const nextTranscriptions = [...s.candidateTranscriptions, text]
    const nextSegmentIds = [..._candidateSegmentIds, segmentId]
    const overflow = Math.max(0, nextTranscriptions.length - MAX_CANDIDATE_TRANSCRIPTIONS)
    _candidateSegmentIds = overflow > 0 ? nextSegmentIds.slice(overflow) : nextSegmentIds
    return {
      candidateTranscriptions: overflow > 0
        ? nextTranscriptions.slice(overflow)
        : nextTranscriptions,
    }
  }),

  startAnswer: (id, question, meta) =>
    set((s) => {
      const existing = s.qaPairs.find((qa) => qa.id === id)
      if (existing) {
        if (existing.status !== 'streaming') {
          return {
            currentStreamingId: s.currentStreamingId,
            streamingIds: s.streamingIds,
            qaPairs: s.qaPairs,
          }
        }
        const streamingIds = s.streamingIds.includes(id) ? s.streamingIds : [...s.streamingIds, id]
        return {
          currentStreamingId: id,
          streamingIds,
          qaPairs: s.qaPairs.map((qa) =>
            qa.id === id
              ? {
                  ...qa,
                  question,
                  questionSource: meta?.source ?? qa.questionSource,
                  modelLabel: meta?.modelName ?? qa.modelLabel,
                  questionType: meta?.questionType ?? qa.questionType,
                  questionCluster: meta?.questionCluster ?? qa.questionCluster,
                  clusterIndex: meta?.clusterIndex ?? qa.clusterIndex,
                  clusterCount: meta?.clusterCount ?? qa.clusterCount,
                }
              : qa,
          ),
        }
      }
      return {
        currentStreamingId: id,
        streamingIds: [...s.streamingIds, id],
        qaPairs: [
          ...s.qaPairs,
          {
            id,
            question,
            answer: '',
            thinkContent: '',
            isThinking: false,
            timestamp: Date.now() / 1000,
            questionSource: meta?.source,
            modelLabel: meta?.modelName,
            questionType: meta?.questionType,
            questionCluster: meta?.questionCluster,
            clusterIndex: meta?.clusterIndex,
            clusterCount: meta?.clusterCount,
            status: 'streaming' as QAStatus,
          },
        ],
      }
    }),

  appendThinkChunk: (id, chunk) => {
    const buf = _chunkBuffer.get(id) ?? { answer: '', think: '' }
    buf.think += chunk
    _chunkBuffer.set(id, buf)
    _scheduleChunkFlush(set)
  },

  appendAnswerChunk: (id, chunk) => {
    const buf = _chunkBuffer.get(id) ?? { answer: '', think: '' }
    buf.answer += chunk
    _chunkBuffer.set(id, buf)
    _scheduleChunkFlush(set)
  },

  finalizeAnswer: (id, question, answer, thinkContent, modelName, firstTokenMs, totalMs) => {
    _chunkBuffer.delete(id)
    set((s) => {
      const next = s.streamingIds.filter((x) => x !== id)
      const existing = s.qaPairs.some((qa) => qa.id === id)
      const qaPairs = existing
        ? s.qaPairs.map((qa) =>
            qa.id === id
              ? {
                  ...qa,
                  question,
                  answer,
                  thinkContent: thinkContent ?? qa.thinkContent,
                  isThinking: false,
                  modelLabel: modelName ?? qa.modelLabel,
                  firstTokenMs: firstTokenMs ?? qa.firstTokenMs,
                  totalMs: totalMs ?? qa.totalMs,
                  status: 'done' as QAStatus,
                }
              : qa,
          )
        : [
            ...s.qaPairs,
            {
              id,
              question,
              answer,
              thinkContent: thinkContent ?? '',
              isThinking: false,
              timestamp: Date.now() / 1000,
              modelLabel: modelName,
              firstTokenMs,
              totalMs,
              status: 'done' as QAStatus,
            },
          ]
      return {
        currentStreamingId: next.length ? next[next.length - 1] : null,
        streamingIds: next,
        qaPairs,
      }
    })
  },

  cancelAnswer: (id) => {
    _chunkBuffer.delete(id)
    set((s) => {
      const next = s.streamingIds.filter((x) => x !== id)
      return {
        currentStreamingId: next.length ? next[next.length - 1] : null,
        streamingIds: next,
        qaPairs: s.qaPairs.map((qa) =>
          qa.id === id ? { ...qa, isThinking: false, status: 'cancelled' as QAStatus } : qa,
        ),
      }
    })
  },

  errorAnswer: (id, message) => {
    _chunkBuffer.delete(id)
    set((s) => {
      const next = s.streamingIds.filter((x) => x !== id)
      return {
        currentStreamingId: next.length ? next[next.length - 1] : null,
        streamingIds: next,
        qaPairs: s.qaPairs.map((qa) =>
          qa.id === id
            ? { ...qa, isThinking: false, status: 'error' as QAStatus, errorMessage: message }
            : qa,
        ),
      }
    })
  },

  setVisionVerify: (id, verdict, reason) =>
    set((s) => ({
      qaPairs: s.qaPairs.map((qa) =>
        qa.id === id ? { ...qa, visionVerify: { verdict, reason } } : qa,
      ),
    })),

  setInitData: (data) => {
    _chunkBuffer.clear()
    const candidateSegments = Array.isArray(data.candidate_answer_segments)
      ? data.candidate_answer_segments
      : []
    const restoredCandidatePairs: Array<{ text: string; segmentId: string | null }> = candidateSegments.length > 0
      ? candidateSegments
          .map((segment: any) => ({
            text: String(segment?.text ?? '').trim(),
            segmentId: segment?.segment_id ? String(segment.segment_id) : null,
          }))
          .filter((segment: { text: string; segmentId: string | null }) => Boolean(segment.text))
      : (data.candidate_transcriptions ?? [])
          .map((text: unknown) => ({ text: String(text ?? '').trim(), segmentId: null }))
          .filter((segment: { text: string; segmentId: string | null }) => Boolean(segment.text))
    const restoredCandidatePairsTail = takeTail(restoredCandidatePairs, MAX_CANDIDATE_TRANSCRIPTIONS)
    const restoredCandidateTranscriptions = restoredCandidatePairsTail.map((segment) => segment.text)
    _candidateSegmentIds = restoredCandidatePairsTail.map((segment) => segment.segmentId)
    if (_chunkFlushTimer !== null) {
      clearTimeout(_chunkFlushTimer)
      _chunkFlushTimer = null
    }
    set({
      transcriptions: takeTail(data.transcriptions ?? [], MAX_TRANSCRIPTIONS),
      transcriptionTimes: [],
      candidateTranscriptions: restoredCandidateTranscriptions,
      qaPairs: (data.qa_pairs ?? []).map(
        (qa: Partial<QAPair> & { id: string; question: string; answer: string }) => {
          const visionVerify = normalizeVisionVerify((qa as any).visionVerify ?? (qa as any).vision_verify)
          return {
            ...qa,
            thinkContent: qa.thinkContent ?? '',
            isThinking: false,
            timestamp: qa.timestamp ?? Date.now() / 1000,
            questionSource: (qa as any).source ?? qa.questionSource,
            modelLabel: (qa as any).model_name ?? qa.modelLabel,
            questionType: qa.questionType ?? (qa as any).question_type,
            questionCluster: qa.questionCluster ?? (qa as any).question_cluster,
            clusterIndex: qa.clusterIndex ?? (qa as any).cluster_index,
            clusterCount: qa.clusterCount ?? (qa as any).cluster_count,
            status: qa.status ?? 'done' as QAStatus,
            ...(visionVerify ? { visionVerify } : {}),
          }
        },
      ),
      currentStreamingId: null,
      streamingIds: [],
      isRecording: data.is_recording ?? false,
      isPaused: data.is_paused ?? false,
      sttLoaded: data.stt_loaded ?? false,
      candidateSttLoaded: false,
      candidateSttLoading: false,
      candidateSttProvider: '',
      systemSummary: data.system_summary ?? '',
      memoManual: data.memo_manual ?? '',
      translationsByQuestion: {},
      suggestionsById: {},
      questionParseStatus: null,
      sessions: data.sessions ?? [],
      activeSessionId: data.active_id ?? data.session_id ?? '',
    })
  },

  clearSession: () => {
    _chunkBuffer.clear()
    _candidateSegmentIds = []
    if (_chunkFlushTimer !== null) {
      clearTimeout(_chunkFlushTimer)
      _chunkFlushTimer = null
    }
    set({
      transcriptions: [],
      transcriptionTimes: [],
      candidateTranscriptions: [],
      qaPairs: [],
      currentStreamingId: null,
      streamingIds: [],
      isPaused: false,
      candidateSttLoaded: false,
      candidateSttLoading: false,
      candidateSttProvider: '',
      systemSummary: '',
      memoManual: '',
      translationsByQuestion: {},
      suggestionsById: {},
      questionParseStatus: null,
    })
  },

  setMemo: (data) => set((s) => ({
    systemSummary: data.system_summary ?? s.systemSummary,
    memoManual: data.memo_manual ?? s.memoManual,
  })),

  addTranslation: (question, translated, to) => set((s) => {
    const key = String(question ?? '').trim()
    if (!key || !translated) return {}
    return { translationsByQuestion: { ...s.translationsByQuestion, [key]: { translated, to } } }
  }),

  addSuggestion: (id, text, question) => set((s) => ({
    suggestionsById: { ...s.suggestionsById, [id]: { text, question } },
  })),

  setSessions: (items, activeId) => set({
    sessions: items,
    activeSessionId: activeId || items.find((x) => x.is_active)?.id || '',
  }),
})
