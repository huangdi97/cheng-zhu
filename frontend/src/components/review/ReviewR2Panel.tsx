import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { api, getErrorMessage } from '@/lib/api'
import { CUE_SOURCE_LABELS, type CueSource } from '@/lib/guidanceViewModel'
import { useInterviewStore } from '@/stores/configStore'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'

// R2 Stage W「Review 2.0」：每轮区分 候选人实际说的 与 AI 提示；显示 Fast Cue、来源、
// 上下文选择、延迟、provider；本场口述但无来源的陈述只能在这里确认/否认/标记口误/不记住。

interface TurnTrace {
  question_raw?: string
  resolved_question?: string
  response_mode?: string
  fast_cue?: { direction?: string; cues?: Array<{ text: string; source: string }>; cautions?: string[] }
  context?: Array<{ fragment_id: string; source_type: string; provenance?: string }>
  latency?: Record<string, number | null>
  provider?: string
  model?: string
  stream_guard_rewrites?: number
}

interface R2Turn {
  qa_id: string
  question: string
  candidate_actual_speech: string
  trace: TurnTrace
}

interface R2Claim {
  id: string
  text: string
  session_status: string
  provenance_status: string
  review_state: string
  session_label?: string
  provenance_label?: string
}

function ms(v: number | null | undefined) {
  return v == null ? '—' : `${v}ms`
}

export default function ReviewR2Panel({ reviewSessionId }: { reviewSessionId: number }) {
  const pushToast = useInterviewStore((s) => s.pushToast)
  const setAppMode = useUiPrefsStore((s) => s.setAppMode)
  const [turns, setTurns] = useState<R2Turn[]>([])
  const [claims, setClaims] = useState<R2Claim[]>([])
  const [open, setOpen] = useState<string | null>(null)

  const load = useCallback(() => {
    Promise.resolve()
      .then(() => api.intelReviewR2(reviewSessionId))
      .then((res) => { setTurns((res?.turns ?? []) as unknown as R2Turn[]); setClaims((res?.session_claims ?? []) as unknown as R2Claim[]) })
      .catch(() => { setTurns([]); setClaims([]) })
  }, [reviewSessionId])
  useEffect(() => { load() }, [load])

  const decide = async (claimId: string, action: 'confirm' | 'deny' | 'forget' | 'slip') => {
    try {
      if (action === 'slip') await api.intelResolveSessionClaim(claimId, 'slip')
      else await api.intelReviewSessionClaim(claimId, action)
      load()
    } catch (error) {
      pushToast(getErrorMessage(error, '操作失败'), 'error')
    }
  }

  const traced = turns.filter((t) => t.trace && Object.keys(t.trace).length > 0)
  if (!traced.length && !claims.length) return null

  return (
    <section className="border-t border-bg-hover/80 py-4 space-y-4" data-testid="review-r2">
      {claims.length > 0 && (
        <div>
          <h3 className="text-base font-semibold text-text-primary">本场口述的陈述</h3>
          <p className="mt-1 text-xs text-text-secondary">这些是你在面试中亲口说过、但 Interview Pack 里暂无来源支持的内容。只有在这里确认，才会成为长期事实；确认不等于有证据。</p>
          <ul className="mt-2 space-y-2">
            {claims.map((c) => (
              <li key={c.id} className="rounded-xl border border-bg-hover/60 bg-bg-secondary p-3">
                <div className="flex flex-wrap items-center gap-2 text-[11px]">
                  <AlertTriangle className="w-3.5 h-3.5 text-status-inferred" aria-hidden />
                  <span className="font-medium text-status-inferred">{c.session_label || c.session_status}</span>
                  <span className="text-status-unknown">{c.provenance_label || c.provenance_status}</span>
                  <span className="text-text-muted">状态：{c.review_state}</span>
                </div>
                <p className="mt-1 text-sm text-text-primary">{c.text}</p>
                <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                  <button type="button" className="rounded-full border border-status-direct/40 px-2 py-0.5 text-status-direct" onClick={() => void decide(c.id, 'confirm')}>用户确认</button>
                  <button type="button" className="rounded-full border border-status-risk/40 px-2 py-0.5 text-status-risk" onClick={() => void decide(c.id, 'deny')}>否认</button>
                  <button type="button" className="rounded-full border border-bg-hover px-2 py-0.5 text-text-secondary" onClick={() => void decide(c.id, 'slip')}>标记口误</button>
                  <button type="button" className="rounded-full border border-bg-hover px-2 py-0.5 text-text-secondary" onClick={() => setAppMode('resume-opt')}>补来源</button>
                  <button type="button" className="rounded-full border border-bg-hover px-2 py-0.5 text-text-muted" onClick={() => void decide(c.id, 'forget')}>不记住</button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
      {traced.length > 0 && (
        <div>
          <h3 className="text-base font-semibold text-text-primary">每轮提示与来源</h3>
          <ul className="mt-2 space-y-2">
            {traced.map((t) => {
              const cue = t.trace.fast_cue ?? {}
              const expanded = open === t.qa_id
              return (
                <li key={t.qa_id} className="rounded-xl border border-bg-hover/60 bg-bg-secondary p-3 text-xs">
                  <button type="button" className="w-full text-left" aria-expanded={expanded} onClick={() => setOpen(expanded ? null : t.qa_id)}>
                    <span className="font-medium text-text-primary">{t.question}</span>
                    <span className="ml-2 text-text-muted">{t.trace.response_mode} · 提示 {ms(t.trace.latency?.ttfug_user_ms ?? t.trace.latency?.ttfug_internal_ms)} · 首字 {ms(t.trace.latency?.ttfa_ms)}</span>
                  </button>
                  {expanded && (
                    <div className="mt-2 grid gap-2 md:grid-cols-2">
                      <div>
                        <div className="text-[10px] font-semibold text-text-muted">你实际说的</div>
                        <p className="mt-0.5 whitespace-pre-wrap text-text-secondary">{t.candidate_actual_speech || '（未开启候选人转写）'}</p>
                      </div>
                      <div>
                        <div className="text-[10px] font-semibold text-text-muted">AI Fast Cue{t.trace.resolved_question && t.trace.resolved_question !== t.question ? ` · 审题：${t.trace.resolved_question}` : ''}</div>
                        <ul className="mt-0.5 space-y-0.5 text-text-secondary">
                          {(cue.cues ?? []).map((c, i) => (
                            <li key={i}>• {c.text} <span className="text-text-muted">[{CUE_SOURCE_LABELS[c.source as CueSource] ?? c.source}]</span></li>
                          ))}
                          {(cue.cautions ?? []).map((c, i) => <li key={`r${i}`} className="text-status-risk">! {c}</li>)}
                        </ul>
                      </div>
                      <div className="md:col-span-2 text-[10px] text-text-muted">
                        上下文：{(t.trace.context ?? []).map((c) => `${c.source_type}${c.provenance ? `(${c.provenance})` : ''}`).join('、') || '—'}
                        {' · '}Provider：{t.trace.provider || '—'} {t.trace.model ? `(${t.trace.model})` : ''}
                        {' · '}QBD {ms(t.trace.latency?.qbd_ms)} · TTD {ms(t.trace.latency?.ttd_ms)}
                        {t.trace.stream_guard_rewrites ? ` · 事实边界改写 ${t.trace.stream_guard_rewrites} 处` : ''}
                      </div>
                      <div className="md:col-span-2 flex flex-wrap gap-1.5">
                        <button type="button" className="rounded-full border border-bg-hover px-2 py-0.5 text-[11px] text-text-secondary" onClick={() => setAppMode('prep')}>再练</button>
                        <button type="button" className="rounded-full border border-bg-hover px-2 py-0.5 text-[11px] text-text-secondary" onClick={() => setAppMode('resume-opt')}>创建 Story</button>
                      </div>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </section>
  )
}
