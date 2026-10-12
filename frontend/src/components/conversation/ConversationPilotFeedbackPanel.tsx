import { useEffect, useMemo, useState } from 'react'
import { conversationApi } from '@/lib/conversationApi'
import type { ConversationFeedbackReview } from '@/lib/conversationContracts'
import { SecondaryButton, StatusBadge } from '@/components/os/ui'

type Presentation = 'POST_SESSION' | 'SPACE_REVIEW'

function isBoolean(value: unknown): value is boolean {
  return typeof value === 'boolean'
}

function guidanceComplete(entry: ConversationFeedbackReview['guidance'][number]): boolean {
  const labels = entry.feedback?.labels ?? {}
  if (!isBoolean(labels.useful) || !isBoolean(labels.interruption_regret)) return false
  if (entry.event.source_refs.length && !isBoolean(labels.source_correct)) return false
  if (entry.event.kind === 'RECALL' && !isBoolean(labels.recall_correct)) return false
  return true
}

export default function ConversationPilotFeedbackPanel({
  sessionId,
  presentation = 'SPACE_REVIEW',
}: {
  sessionId: string
  presentation?: Presentation
}) {
  const [review, setReview] = useState<ConversationFeedbackReview | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')

  const reload = async () => {
    const next = await conversationApi.feedbackReview(sessionId)
    setReview(next)
  }

  useEffect(() => {
    let alive = true
    conversationApi.feedbackReview(sessionId)
      .then((next) => { if (alive) setReview(next) })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : String(e)) })
    return () => { alive = false }
  }, [sessionId])

  const submit = async (
    kind: 'GUIDANCE' | 'SILENCE' | 'CONTINUE' | 'SESSION_OUTCOME',
    targetId: string,
    labels: Record<string, boolean | number | null>,
  ) => {
    const key = `${kind}:${targetId || 'session'}:${Object.keys(labels)[0] || 'label'}`
    setBusy(key); setError(''); setSaved('')
    try {
      await conversationApi.recordFeedback(sessionId, { kind, target_id: targetId, labels })
      await reload()
      setSaved('已保存在本机')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy('')
    }
  }

  const completion = useMemo(() => {
    if (!review) return { quick: 0, quickTotal: 3, detail: 0, detailTotal: 0 }
    const continueLabels = review.continue_feedback?.labels ?? {}
    const outcome = review.session_outcome?.labels ?? {}
    const quick = [
      isBoolean(continueLabels.writeback_accurate),
      isBoolean(outcome.would_reuse_space),
      typeof outcome.cognitive_load_delta === 'number',
    ].filter(Boolean).length
    const detail = review.guidance.filter(guidanceComplete).length
      + review.silence.filter(({ feedback }) => isBoolean(feedback?.labels.silence_correct)).length
    return {
      quick,
      quickTotal: 3,
      detail,
      detailTotal: review.guidance.length + review.silence.length,
    }
  }, [review])

  if (!review) {
    return <div className="rounded-xl border border-bg-tertiary/70 p-3 text-xs text-text-muted">正在载入本机试用反馈…</div>
  }

  const outcome = review.session_outcome?.labels ?? {}
  const continueLabels = review.continue_feedback?.labels ?? {}

  const quickDebrief = (
    <div className="space-y-3" data-testid="conversation-quick-debrief">
      <div className="rounded-lg border border-bg-tertiary/70 bg-bg-secondary/25 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-xs font-semibold text-text-secondary">会后快速回顾</div>
            <p className="mt-1 text-[10px] leading-relaxed text-text-muted">趁这场对话还新鲜，只回答 3 个问题。详细 Guidance / SILENT 回看可以稍后做。</p>
          </div>
          <StatusBadge tone={completion.quick === completion.quickTotal ? 'ok' : 'info'}>QUICK {completion.quick}/{completion.quickTotal}</StatusBadge>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-bg-tertiary/70 p-3">
          <div className="text-xs font-semibold text-text-secondary">Continue 是否准确？</div>
          <p className="mt-1 text-[10px] text-text-muted">检查 Decision / Commitment / Open Question / 草稿是否只用了已审核真值，owner / due / state / source 是否正确。</p>
          <div className="mt-2 flex gap-2">
            <SecondaryButton disabled={Boolean(busy)} onClick={() => submit('CONTINUE', '', { writeback_accurate: true })}>准确{continueLabels.writeback_accurate === true ? ' ✓' : ''}</SecondaryButton>
            <SecondaryButton disabled={Boolean(busy)} onClick={() => submit('CONTINUE', '', { writeback_accurate: false })}>有错误{continueLabels.writeback_accurate === false ? ' ✓' : ''}</SecondaryButton>
          </div>
        </div>

        <div className="rounded-lg border border-bg-tertiary/70 p-3">
          <div className="text-xs font-semibold text-text-secondary">还愿意继续用这个 Space 吗？</div>
          <div className="mt-2 flex gap-2">
            <SecondaryButton disabled={Boolean(busy)} onClick={() => submit('SESSION_OUTCOME', '', { would_reuse_space: true })}>愿意{outcome.would_reuse_space === true ? ' ✓' : ''}</SecondaryButton>
            <SecondaryButton disabled={Boolean(busy)} onClick={() => submit('SESSION_OUTCOME', '', { would_reuse_space: false })}>不愿意{outcome.would_reuse_space === false ? ' ✓' : ''}</SecondaryButton>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-bg-tertiary/70 p-3">
        <div className="text-xs font-semibold text-text-secondary">相比没有成竹，这场认知负担怎样？</div>
        <p className="mt-1 text-[10px] text-text-muted">-2 明显降低 · -1 略有降低 · 0 无变化 · +1 略有增加 · +2 明显增加</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {[-2, -1, 0, 1, 2].map((value) => (
            <SecondaryButton key={value} disabled={Boolean(busy)} onClick={() => submit('SESSION_OUTCOME', '', { cognitive_load_delta: value })}>
              {value > 0 ? `+${value}` : value}{outcome.cognitive_load_delta === value ? ' ✓' : ''}
            </SecondaryButton>
          ))}
        </div>
      </div>
    </div>
  )

  const detailedReview = (
    <div className="space-y-4">
      {review.guidance.length ? <div className="space-y-3">
        <div className="text-xs font-semibold text-text-secondary">这场显示过的 Guidance</div>
        {review.guidance.slice(0, 8).map(({ event, feedback }) => {
          const labels = feedback?.labels ?? {}
          return <div key={event.id} className="rounded-lg border border-bg-tertiary/70 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge tone={event.kind === 'RISK' ? 'risk' : 'muted'}>{event.kind}</StatusBadge>
              <span className="text-[10px] text-text-muted">{event.reason}</span>
            </div>
            <p className="mt-1 text-xs text-text-primary">{event.text || event.expression_action}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <SecondaryButton disabled={Boolean(busy)} onClick={() => submit('GUIDANCE', event.id, { useful: true })}>有用{labels.useful === true ? ' ✓' : ''}</SecondaryButton>
              <SecondaryButton disabled={Boolean(busy)} onClick={() => submit('GUIDANCE', event.id, { useful: false })}>没帮上忙{labels.useful === false ? ' ✓' : ''}</SecondaryButton>
              <SecondaryButton disabled={Boolean(busy)} onClick={() => submit('GUIDANCE', event.id, { interruption_regret: true })}>打断了表达{labels.interruption_regret === true ? ' ✓' : ''}</SecondaryButton>
              <SecondaryButton disabled={Boolean(busy)} onClick={() => submit('GUIDANCE', event.id, { interruption_regret: false })}>时机可以{labels.interruption_regret === false ? ' ✓' : ''}</SecondaryButton>
              {event.source_refs.length ? <>
                <SecondaryButton disabled={Boolean(busy)} onClick={() => submit('GUIDANCE', event.id, { source_correct: true })}>来源正确{labels.source_correct === true ? ' ✓' : ''}</SecondaryButton>
                <SecondaryButton disabled={Boolean(busy)} onClick={() => submit('GUIDANCE', event.id, { source_correct: false })}>来源有误{labels.source_correct === false ? ' ✓' : ''}</SecondaryButton>
              </> : null}
              {event.kind === 'RECALL' ? <>
                <SecondaryButton disabled={Boolean(busy)} onClick={() => submit('GUIDANCE', event.id, { recall_correct: true })}>Recall 正确{labels.recall_correct === true ? ' ✓' : ''}</SecondaryButton>
                <SecondaryButton disabled={Boolean(busy)} onClick={() => submit('GUIDANCE', event.id, { recall_correct: false })}>Recall 有误{labels.recall_correct === false ? ' ✓' : ''}</SecondaryButton>
              </> : null}
            </div>
          </div>
        })}
      </div> : <p className="text-[11px] text-text-muted">这场没有可标注的已显示 Conversation AI Guidance。</p>}

      {review.silence.length ? <div className="space-y-2">
        <div className="text-xs font-semibold text-text-secondary">SILENT / 被抑制的时机</div>
        {review.silence.slice(0, 6).map(({ event, feedback }) => <div key={event.id} className="rounded-lg border border-bg-tertiary/70 p-3">
          <div className="text-[11px] text-text-muted">{event.kind} · {event.reason}</div>
          <div className="mt-2 flex flex-wrap gap-2">
            <SecondaryButton disabled={Boolean(busy)} onClick={() => submit('SILENCE', event.id, { silence_correct: true })}>保持沉默是对的{feedback?.labels.silence_correct === true ? ' ✓' : ''}</SecondaryButton>
            <SecondaryButton disabled={Boolean(busy)} onClick={() => submit('SILENCE', event.id, { silence_correct: false })}>这里应该提醒{feedback?.labels.silence_correct === false ? ' ✓' : ''}</SecondaryButton>
          </div>
        </div>)}
      </div> : null}
    </div>
  )

  const header = (
    <div className="rounded-lg border border-bg-tertiary/70 bg-bg-secondary/25 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge tone="info">LOCAL ONLY</StatusBadge>
        <StatusBadge tone="muted">SELF REPORT</StatusBadge>
        <StatusBadge tone="muted">NO TELEMETRY</StatusBadge>
        {completion.detailTotal ? <StatusBadge tone={completion.detail === completion.detailTotal ? 'ok' : 'muted'}>DETAIL {completion.detail}/{completion.detailTotal}</StatusBadge> : null}
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-text-muted">这些是你明确填写的质量标签，不会从 Pin / 忽略 / 点击率推断。它们可进入本机 human-label 评估，但不会自动证明“真实外部用户已验证”，也不会自动把 v2 升为 Stable 或 PMF。</p>
    </div>
  )

  const feedbackBody = (
    <div className="mt-3 space-y-4">
      {header}
      {quickDebrief}
      {presentation === 'POST_SESSION' && completion.detailTotal ? (
        <details className="rounded-xl border border-bg-tertiary/70 p-3">
          <summary className="cursor-pointer text-xs font-semibold text-text-secondary">详细回看 Guidance / SILENT · {completion.detail}/{completion.detailTotal}</summary>
          <div className="mt-3">{detailedReview}</div>
        </details>
      ) : detailedReview}
      {saved ? <p role="status" className="text-[11px] text-status-direct">{saved}</p> : null}
      {error ? <p role="alert" className="text-[11px] text-status-risk">{error}</p> : null}
    </div>
  )

  if (presentation === 'POST_SESSION') {
    return (
      <section className="mt-4 rounded-2xl border border-accent-blue/25 bg-bg-primary/55 p-4" data-testid="conversation-post-session-debrief">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">这场刚结束，先留 20 秒反馈</h3>
            <p className="mt-1 text-[11px] text-text-muted">即时自报优先于几天后回忆；只保存在这台设备，详细复核可稍后继续。</p>
          </div>
          <StatusBadge tone={completion.quick === completion.quickTotal ? 'ok' : 'info'}>{completion.quick === completion.quickTotal ? 'QUICK DONE' : 'QUICK DEBRIEF'}</StatusBadge>
        </div>
        {feedbackBody}
      </section>
    )
  }

  return (
    <details className="mt-4 rounded-xl border border-accent-blue/20 bg-bg-primary/55 p-3" data-testid="conversation-pilot-feedback">
      <summary className="cursor-pointer text-xs font-semibold text-text-secondary">试用反馈 · 仅保存在本机 · QUICK {completion.quick}/{completion.quickTotal}</summary>
      {feedbackBody}
    </details>
  )
}
