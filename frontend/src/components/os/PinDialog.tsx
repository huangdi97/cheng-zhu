/**
 * Pin Moment (canonical §13) — Ctrl+P in Live or Practice. The user decides
 * what mattered; Reflection shows these moments first.
 */
import { useEffect, useState } from 'react'
import { productApi } from '@/lib/productApi'
import { useInterviewStore } from '@/stores/configStore'
import { useOsStore } from '@/stores/osStore'
import { Dialog } from './CreateGoalDialog'
import { inputCls, PrimaryButton, SecondaryButton } from './ui'

const TAGS: Array<[string, string]> = [
  ['BAD_ANSWER', '没答好'], ['IMPORTANT', '重要'], ['PREP_NEXT', '下次要准备'], ['FACT_CHECK', '事实待核对'],
  ['COUNTERPARTY_INFO', '对方透露的信息'], ['CUSTOM', '自定义'],
]

export default function PinDialog() {
  const open = useOsStore((s) => s.pinDialogOpen)
  const setOpen = useOsStore((s) => s.setPinDialog)
  const live = useOsStore((s) => s.live)
  const practiceId = useOsStore((s) => s.activePracticeId)
  const practiceQuestion = useOsStore((s) => s.activePracticeQuestion)
  const contextGoal = useOsStore((s) => s.contextGoalId)
  const [tag, setTag] = useState('BAD_ANSWER')
  const [note, setNote] = useState('')
  const [status, setStatus] = useState<string | null>(null)
  useEffect(() => { if (open) { setNote(''); setStatus(null) } }, [open])
  if (!open) return null

  const qaPairs = useInterviewStore.getState().qaPairs
  const latest = qaPairs[qaPairs.length - 1]
  const transcripts = useInterviewStore.getState().transcriptions
  const excerpt = transcripts.slice(-4).map((t) => (typeof t === 'string' ? t : (t as { text?: string }).text ?? '')).join('\n')
  const isPractice = Boolean(practiceId)
  const save = async () => {
    try {
      await productApi.createPin({
        session_kind: isPractice ? 'PRACTICE' : 'LIVE',
        session_id: isPractice ? practiceId! : live?.sessionId ?? '',
        tag, note,
        turn_id: isPractice ? '' : latest?.id ?? '',
        question: isPractice ? practiceQuestion : latest?.question ?? '',
        transcript_excerpt: isPractice ? '' : excerpt,
        goal_id: live?.goalId ?? contextGoal ?? null,
      })
      setStatus('已标记，复盘时会优先显示')
      window.setTimeout(() => setOpen(false), 700)
    } catch (e) {
      setStatus(e instanceof Error ? e.message : '标记失败')
    }
  }
  return (
    <Dialog title="标记这一刻" onClose={() => setOpen(false)} labelledBy="pin-title">
      <div className="space-y-3" data-testid="pin-dialog">
        <div role="radiogroup" aria-label="标签" className="flex flex-wrap gap-1.5">
          {TAGS.map(([k, l]) => (
            <button key={k} type="button" role="radio" aria-checked={tag === k} onClick={() => setTag(k)}
              className={`rounded-full border px-3 py-1 text-xs ${tag === k ? 'border-accent-amber/60 bg-accent-amber/15 text-text-primary font-semibold' : 'border-bg-hover text-text-secondary'}`}>{l}</button>
          ))}
        </div>
        <textarea aria-label="备注（可选）" className={`${inputCls} min-h-[56px]`} placeholder="备注（可选）" value={note} onChange={(e) => setNote(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); void save() } }} />
        {status ? <p role="status" className="text-xs text-text-secondary">{status}</p> : null}
        <div className="flex justify-end gap-2">
          <SecondaryButton onClick={() => setOpen(false)}>取消</SecondaryButton>
          <PrimaryButton onClick={() => void save()} disabled={!isPractice && !live}>标记</PrimaryButton>
        </div>
        {!isPractice && !live ? <p className="text-[11px] text-text-muted">只能在练习或上场中标记。</p> : null}
      </div>
    </Dialog>
  )
}
