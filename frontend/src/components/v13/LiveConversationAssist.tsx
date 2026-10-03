import { useEffect, useMemo, useRef, useState } from 'react'
import { CornerDownRight, MessageCircleQuestion, X } from 'lucide-react'
import { api, type ProductGoal } from '@/lib/api'
import { useInterviewStore } from '@/stores/configStore'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'

const CLOSING_RE = /(有什么(想|要)?问|还有什么问题|你想了解什么|anything (you('|’)d like to|else you want to) ask|questions? for (me|us))/i

function nudgeFor(question: string, type?: string, followups?: Array<{ question?: string }>) {
  const predicted = followups?.find((x) => x.question)?.question
  if (predicted) return { kind: 'LIKELY_FOLLOWUP', text: `可能继续追问：${predicted}` }
  const t = (type || '').toLowerCase()
  if (t.includes('system') || /设计|架构|scale|扩容|高可用/i.test(question)) {
    return { kind: 'MISSING_DIMENSION', text: '还可以检查：failure mode / reliability / observability 有没有讲到。' }
  }
  if (t.includes('experience') || /项目|经历|负责|做过/i.test(question)) {
    return { kind: 'LIKELY_FOLLOWUP', text: '可能继续追问：你的 ownership、量化结果，以及当时最关键的 trade-off。' }
  }
  return null
}

/** v1.3: proactive help is deliberately weak. Fast Cue and warnings always win. */
export default function LiveConversationAssist() {
  const qaPairs = useInterviewStore((s) => s.qaPairs)
  const candidatePartial = useInterviewStore((s) => s.candidatePartial)
  const candidateAudioLevel = useInterviewStore((s) => s.candidateAudioLevel)
  const copilotHint = useInterviewStore((s) => s.copilotHint)
  const activeGoalId = useUiPrefsStore((s) => s.activeGoalId)
  const [goal, setGoal] = useState<ProductGoal | null>(null)
  const [dismissed, setDismissed] = useState<string | null>(null)
  const shownRef = useRef<string | null>(null)

  useEffect(() => {
    if (!activeGoalId) { setGoal(null); return }
    api.productGoal(activeGoalId).then(setGoal).catch(() => setGoal(null))
  }, [activeGoalId])

  const latest = qaPairs[qaPairs.length - 1]
  const previous = qaPairs[qaPairs.length - 2]
  const isClosing = Boolean(latest?.question && CLOSING_RE.test(latest.question))
  const nudge = useMemo(
    () => latest && latest.status === 'done' && !isClosing
      ? nudgeFor(latest.question, latest.questionType, copilotHint?.predicted_followups)
      : null,
    [copilotHint?.predicted_followups, isClosing, latest],
  )
  const speaking = Boolean(candidatePartial?.trim()) || candidateAudioLevel > 35
  const key = isClosing ? `closing:${latest?.id}` : nudge ? `nudge:${latest?.id}:${nudge.kind}` : ''
  const visible = Boolean(key && dismissed !== key && !speaking)

  useEffect(() => {
    if (!visible || !key || shownRef.current === key) return
    shownRef.current = key
    void api.productEvent(isClosing ? 'closing_mode_shown' : 'nudge_shown', {
      goal_id: activeGoalId,
      payload: { qa_id: latest?.id, kind: nudge?.kind },
    })
  }, [activeGoalId, isClosing, key, latest?.id, nudge?.kind, visible])

  if (!visible || !latest) return null

  const close = () => {
    setDismissed(key)
    void api.productEvent(isClosing ? 'closing_mode_dismissed' : 'nudge_dismissed', {
      goal_id: activeGoalId,
      payload: { qa_id: latest.id, kind: nudge?.kind },
    })
  }

  if (isClosing) {
    const priorTopic = previous?.question?.trim()
    const suggestions = [
      priorTopic
        ? `刚才我们聊到“${priorTopic.slice(0, 42)}”，团队现在在这块最希望新成员先解决什么？`
        : `这个 ${goal?.role || '岗位'} 当前最需要新成员先解决的问题是什么？`,
      `这个 ${goal?.role || '岗位'} 前三个月最重要的 success criteria 是什么？`,
      goal?.company
        ? `${goal.company} 目前这个团队判断一个方案可以真正上线的质量门槛是什么？`
        : '团队现在最重要、但招聘信息里看不出来的技术或协作挑战是什么？',
    ]
    return (
      <div className="border-b border-accent-green/20 bg-accent-green/5 px-3 py-2.5 md:px-5" data-testid="closing-mode">
        <div className="flex items-start gap-2">
          <MessageCircleQuestion className="mt-0.5 h-4 w-4 flex-shrink-0 text-status-direct" />
          <div className="min-w-0 flex-1">
            <div className="text-xs font-semibold text-status-direct">Closing Mode · 可以反问</div>
            <div className="mt-1 grid gap-1 md:grid-cols-3">
              {suggestions.map((q, i) => <div key={i} className="rounded-lg bg-bg-secondary/80 px-2.5 py-2 text-xs leading-relaxed text-text-secondary">{q}</div>)}
            </div>
          </div>
          <button type="button" aria-label="关闭 Closing Mode" onClick={close} className="rounded-lg p-1 text-text-muted hover:bg-bg-hover"><X className="h-3.5 w-3.5" /></button>
        </div>
      </div>
    )
  }

  return (
    <div className="border-b border-bg-hover/50 bg-bg-secondary/55 px-3 py-2 md:px-5" data-testid="live-nudge">
      <div className="flex items-center gap-2">
        <CornerDownRight className="h-3.5 w-3.5 flex-shrink-0 text-text-muted" />
        <span className="text-[11px] font-semibold text-text-muted">还可以补一句</span>
        <span className="min-w-0 flex-1 truncate text-xs text-text-secondary">{nudge?.text}</span>
        <button type="button" aria-label="忽略提示" onClick={close} className="rounded-lg p-1 text-text-muted hover:bg-bg-hover"><X className="h-3.5 w-3.5" /></button>
      </div>
    </div>
  )
}
