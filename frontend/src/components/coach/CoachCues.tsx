import { Users, X } from 'lucide-react'
import { buildApiUrl } from '@/lib/backendUrl'
import { useInterviewStore } from '@/stores/configStore'

// 教练建议：来源 HUMAN_COACH，只是建议，不是证据，也不是你本人的确认。
export default function CoachCues({ targetSessionId = '' }: { targetSessionId?: string }) {
  const allCues = useInterviewStore((s) => s.coachCues)
  const cues = targetSessionId
    ? allCues.filter((cue) => cue.sessionKind === 'conversation' && cue.targetSessionId === targetSessionId)
    : allCues.filter((cue) => cue.sessionKind !== 'conversation')
  const dismiss = useInterviewStore((s) => s.dismissCoachCue)
  if (!cues.length) return null
  return (
    <div className="px-3 md:px-5 pt-2 space-y-1.5" aria-live="polite" data-testid="coach-cues">
      {cues.slice(-3).map((c) => (
        <div key={c.id} className="flex items-start gap-2 rounded-xl border border-status-inferred/30 bg-status-inferred/5 px-3 py-2 text-xs">
          <Users className="w-3.5 h-3.5 mt-0.5 text-status-inferred flex-shrink-0" aria-hidden />
          <div className="flex-1 min-w-0">
            <span className="font-semibold text-status-inferred">教练建议</span>
            <span className="ml-1 text-[10px] text-text-muted">（建议，不是事实来源）</span>
            {c.text && <p className="text-text-primary break-words">{c.text}</p>}
            {c.voiceUrl && <audio controls src={buildApiUrl(c.voiceUrl)} className="mt-1 h-8 w-full" aria-label="教练语音建议" />}
          </div>
          <button type="button" aria-label="关闭教练建议" onClick={() => dismiss(c.id)} className="text-text-muted hover:text-text-primary">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  )
}
