import { useCallback, useEffect, useState } from 'react'
import { Bookmark, Target } from 'lucide-react'
import { api, type PinMoment } from '@/lib/api'
import { useInterviewStore } from '@/stores/configStore'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'

const LABELS: Record<string, string> = {
  IMPORTANT: '重要',
  BAD_ANSWER: '我答崩了',
  COUNTERPARTY_INFO: '对方关键信息',
  PREP_NEXT: '下一场要准备',
  FACT_CHECK: '事实待确认',
}

export default function PinnedMoments() {
  const activeGoalId = useUiPrefsStore((s) => s.activeGoalId)
  const setAppMode = useUiPrefsStore((s) => s.setAppMode)
  const pushToast = useInterviewStore((s) => s.pushToast)
  const [items, setItems] = useState<PinMoment[]>([])

  const load = useCallback(() => {
    api.productPins(activeGoalId ? { goalId: activeGoalId } : undefined)
      .then((r) => setItems(r.items ?? []))
      .catch(() => setItems([]))
  }, [activeGoalId])
  useEffect(() => { load() }, [load])

  const nextFocus = async (pin: PinMoment) => {
    if (!pin.goal_id) {
      pushToast('这个 Pin 没有关联 Goal，先在求职目标中选择当前 Goal', 'warn')
      return
    }
    try {
      const goal = await api.productGoal(pin.goal_id)
      const focus = [{
        type: pin.label === 'FACT_CHECK' ? 'fact' : 'practice',
        title: pin.note || pin.question || LABELS[pin.label] || '复盘这个时刻',
        reason: '来自你主动 Pin 的重要时刻',
        action: 'PRACTICE',
        priority: 'high',
      }, ...(goal.next_focus ?? []).filter((x) => x.title !== (pin.note || pin.question)).slice(0, 2)]
      await api.productPatchGoal(pin.goal_id, { next_focus: focus })
      await api.productEvent('next_focus_changed', { goal_id: pin.goal_id, payload: { source: 'pin', pin_id: pin.id } })
      pushToast('已设为当前 Goal 的 Next Focus', 'success')
      setAppMode('goals')
    } catch (error) {
      pushToast(error instanceof Error ? error.message : '写入 Next Focus 失败', 'error')
    }
  }

  if (!items.length) return null
  return (
    <section className="mx-3 mt-3 rounded-2xl border border-accent-amber/20 bg-accent-amber/5 p-4 md:mx-5" data-testid="pinned-moments">
      <div className="flex items-center gap-2"><Bookmark className="h-4 w-4 text-accent-amber" /><h3 className="text-sm font-semibold text-text-primary">你标记的重要时刻</h3></div>
      <p className="mt-1 text-xs text-text-muted">用户判断优先于 AI 摘要。这里的 Pin 不会自动成为事实。</p>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {items.slice(0, 6).map((pin) => (
          <article key={pin.id} className="rounded-xl border border-bg-hover/50 bg-bg-secondary p-3">
            <div className="text-[10px] font-semibold text-accent-amber">{LABELS[pin.label] ?? pin.label}</div>
            <div className="mt-1 text-sm font-medium text-text-primary">{pin.question || pin.note || '已标记时刻'}</div>
            {pin.transcript_excerpt && <div className="mt-1 line-clamp-2 text-xs text-text-muted">你说：{pin.transcript_excerpt}</div>}
            <button type="button" onClick={() => void nextFocus(pin)}
              className="mt-2 inline-flex items-center gap-1 rounded-lg border border-bg-hover px-2 py-1 text-[11px] text-text-secondary hover:bg-bg-hover/50">
              <Target className="h-3 w-3" /> 设为 Next Focus
            </button>
          </article>
        ))}
      </div>
    </section>
  )
}
