/**
 * Live companions with lower priority than Fast Cue and warnings:
 *  - NudgeBar (canonical §14): asks the server whether a nudge is warranted
 *    only in gaps; the server applies speech-active / new-question /
 *    cooldown / duplicate / one-at-a-time suppression.
 *  - ClosingPanel (canonical §15): when the interviewer opens the floor,
 *    suggests questions built from this interview, not generic ones.
 */
import { useEffect, useRef, useState } from 'react'
import { Lightbulb, MessageCircleQuestion, X } from 'lucide-react'
import { productApi, type ClosingSuggestion, type Nudge } from '@/lib/productApi'
import { useInterviewStore } from '@/stores/configStore'
import { useOsStore } from '@/stores/osStore'

const QTYPE: Record<string, string> = {
  system_design: 'SYSTEM_DESIGN', project: 'PROJECT_DEEP_DIVE', behavioral: 'BEHAVIORAL', technical: 'KNOWLEDGE',
  coding: 'CODING', troubleshooting: 'KNOWLEDGE',
}
const NUDGE_INTERVAL_MS = 6000
const SPEAKING_WINDOW_MS = 2500

export function NudgeBar() {
  const live = useOsStore((s) => s.live)
  const isRecording = useInterviewStore((s) => s.isRecording)
  const proactive = useInterviewStore((s) => s.config?.proactive_guidance_enabled !== false)
  const [nudge, setNudge] = useState<Nudge | null>(null)
  const lastQaId = useRef<string | null>(null)
  const lastCandidateChange = useRef(0)
  const candidateLen = useRef(0)

  useEffect(() => useInterviewStore.subscribe((s) => {
    if (s.candidateTranscriptions.length !== candidateLen.current) {
      candidateLen.current = s.candidateTranscriptions.length
      lastCandidateChange.current = Date.now()
    }
    const latest = s.qaPairs[s.qaPairs.length - 1]
    if (latest && latest.id !== lastQaId.current) {
      lastQaId.current = latest.id
      setNudge(null)
      const sid = useOsStore.getState().live?.sessionId
      if (sid) void productApi.nudgeNewQuestion(sid).catch(() => undefined)
    }
  }), [])

  useEffect(() => {
    if (!live || !isRecording || !proactive) return
    const tick = () => {
      const s = useInterviewStore.getState()
      const latest = s.qaPairs[s.qaPairs.length - 1]
      if (!latest) return
      const streaming = s.streamingIds.includes(latest.id)
      void productApi.evaluateNudge({
        session_id: live.sessionId,
        candidate_text: s.candidateTranscriptions.slice(-4).join(' '),
        question_type: QTYPE[latest.questionType ?? ''] ?? '',
        candidate_speaking: Date.now() - lastCandidateChange.current < SPEAKING_WINDOW_MS,
        new_question_pending: Date.now() - latest.timestamp < 2000,
        cue_state: streaming && !latest.fastCue ? 'PREPARING' : '',
        interviewer_recent: s.transcriptions.slice(-3),
      }).then((res) => { if (res.nudge) setNudge(res.nudge) }).catch(() => undefined)
    }
    const timer = window.setInterval(tick, NUDGE_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [live, isRecording, proactive])

  if (!nudge) return null
  const resolve = (status: 'DISMISSED' | 'USED') => {
    void productApi.nudgeStatus(nudge.id, status).catch(() => undefined)
    setNudge(null)
  }
  return (
    <div role="status" aria-live="polite" data-testid="nudge-bar"
      className="mx-3 md:mx-5 mb-1 flex flex-wrap items-center gap-2 rounded-xl border border-bg-hover/60 bg-bg-secondary/70 px-3 py-1.5 text-xs text-text-secondary">
      <Lightbulb className="h-3.5 w-3.5 text-accent-amber" aria-hidden />
      <span className="min-w-0 flex-1">{nudge.text}</span>
      <button type="button" className="text-accent-blue hover:underline" onClick={() => resolve('USED')}>用上了</button>
      <button type="button" className="text-text-muted hover:text-text-primary" onClick={() => resolve('DISMISSED')}>忽略</button>
      <button type="button" className="text-text-muted hover:text-text-primary" title="关闭主动提示"
        onClick={() => { void productApi.disableNudges().catch(() => undefined); setNudge(null) }}>不再提示</button>
    </div>
  )
}

export function ClosingPanel() {
  const live = useOsStore((s) => s.live)
  const qaPairs = useInterviewStore((s) => s.qaPairs)
  const [suggestions, setSuggestions] = useState<ClosingSuggestion[] | null>(null)
  const checked = useRef<Set<string>>(new Set())
  const latest = qaPairs[qaPairs.length - 1]

  useEffect(() => {
    if (!latest || checked.current.has(latest.id)) return
    checked.current.add(latest.id)
    void productApi.closingDetect(latest.question).then((res) => {
      if (!res.trigger) return
      const s = useInterviewStore.getState()
      const transcript = [
        ...s.transcriptions.slice(-30).map((text) => ({ speaker: 'interviewer', text })),
        ...s.candidateTranscriptions.slice(-10).map((text) => ({ speaker: 'candidate', text })),
      ]
      return productApi.closingSuggest({ session_id: live?.sessionId ?? '', goal_id: live?.goalId ?? null, text: latest.question, transcript })
        .then((r) => setSuggestions(r.suggestions))
    }).catch(() => undefined)
  }, [latest, live])

  if (!suggestions?.length) return null
  return (
    <section aria-label="收尾提问建议" data-testid="closing-panel"
      className="mx-3 md:mx-5 mb-1 rounded-xl border border-accent-blue/25 bg-accent-blue/5 px-3 py-2">
      <div className="flex items-center gap-2 text-xs font-semibold text-text-primary">
        <MessageCircleQuestion className="h-3.5 w-3.5 text-accent-blue" aria-hidden /> 可以反问
        <button type="button" aria-label="关闭收尾建议" className="ml-auto text-text-muted hover:text-text-primary" onClick={() => setSuggestions(null)}><X className="h-3.5 w-3.5" aria-hidden /></button>
      </div>
      <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-xs text-text-secondary">
        {suggestions.map((s) => <li key={s.text}>{s.text}<span className="ml-1 text-[10px] text-text-muted">（{s.basis}）</span></li>)}
      </ol>
    </section>
  )
}
