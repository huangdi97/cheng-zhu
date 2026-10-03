import { useEffect } from 'react'
import { api } from '@/lib/api'
import { useInterviewStore } from '@/stores/configStore'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'

function editableTarget(target: EventTarget | null) {
  const el = target as HTMLElement | null
  const tag = el?.tagName?.toLowerCase()
  return tag === 'input' || tag === 'textarea' || tag === 'select' || Boolean(el?.isContentEditable)
}

/** Ctrl/Cmd+P marks the current Live moment as user-important.
 * User judgement is first-class: the pin is stored locally and never becomes Evidence.
 */
export default function LivePinShortcut() {
  const appMode = useUiPrefsStore((s) => s.appMode)
  const activeGoalId = useUiPrefsStore((s) => s.activeGoalId)
  const activeSessionId = useInterviewStore((s) => s.activeSessionId)
  const qaPairs = useInterviewStore((s) => s.qaPairs)
  const candidateTranscriptions = useInterviewStore((s) => s.candidateTranscriptions)
  const pushToast = useInterviewStore((s) => s.pushToast)

  useEffect(() => {
    if (appMode !== 'assist') return
    const onKey = async (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 'p' || event.shiftKey || event.altKey) return
      if (editableTarget(event.target)) return
      event.preventDefault()
      const qa = qaPairs[qaPairs.length - 1]
      try {
        await api.productCreatePin({
          session_id: activeSessionId || '',
          goal_id: activeGoalId,
          turn_id: qa?.id ?? '',
          label: 'IMPORTANT',
          question: qa?.question ?? '',
          transcript_excerpt: candidateTranscriptions.slice(-2).join(' '),
        })
        pushToast('已标记这个时刻 · Review 会优先显示', 'success')
      } catch (error) {
        pushToast(error instanceof Error ? error.message : '标记失败', 'error')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [activeGoalId, activeSessionId, appMode, candidateTranscriptions, pushToast, qaPairs])

  return null
}
