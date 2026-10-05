import { Target } from 'lucide-react'
import { navigate, paths } from '@/lib/router'
import { productApi, track, type NextFocusItem } from '@/lib/productApi'
import { runActionKey } from './actions'
import { ActionMenu, EmptyState } from './ui'

const SOURCE_LABEL: Record<string, string> = {
  USER: '你设定的',
  REFLECTION: '来自复盘',
  PIN: '来自你的标记',
  PRACTICE: '来自练习',
  FACT: '事实边界',
  GAP: '岗位要求',
  STORY: 'Story 缺口',
}

/** 1–3 Next Focus items with their reason and real actions (no scores). */
export function NextFocusList({ goalId, items, onChanged, compact = false }: {
  goalId: string
  items: NextFocusItem[]
  onChanged?: () => void
  compact?: boolean
}) {
  if (!items.length) {
    return <EmptyState title="暂时没有需要优先处理的点" body="补充 JD、完成一次练习或复盘后，这里会给出下一步。" />
  }
  const act = (item: NextFocusItem, key: string) => {
    track('next_focus_opened', { type: item.type, action: key }, { goal_id: goalId })
    if (key === 'practice') {
      navigate(paths.practice(undefined, { goal: goalId, focus: item.id }))
      return
    }
    runActionKey(key, { goalId, focusTitle: item.title })
  }
  return (
    <ol className="space-y-2" aria-label="Next Focus">
      {items.slice(0, 3).map((item, idx) => (
        <li key={item.id} className="rounded-2xl border border-bg-hover/60 bg-bg-secondary/60 p-3">
          <div className="flex items-start gap-2">
            <Target className="mt-0.5 h-4 w-4 flex-shrink-0 text-accent-blue" aria-hidden />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-sm font-semibold text-text-primary break-words">{item.title}</span>
                <span className="text-[11px] text-text-muted">{idx === 0 ? '最优先 · ' : ''}{SOURCE_LABEL[item.source_kind] ?? item.source_kind}</span>
              </div>
              <p className="mt-0.5 text-xs text-text-secondary">原因：{item.reason}</p>
              {!compact ? (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {(item.actions ?? []).slice(0, 3).map((a, i) => (
                    <button key={a.key} type="button" onClick={() => act(item, a.key)}
                      className={i === 0 && idx === 0
                        ? 'btn-primary rounded-full px-3 py-1 text-xs font-semibold'
                        : 'btn-subtle rounded-full px-3 py-1 text-xs'}>
                      {a.label}
                    </button>
                  ))}
                  <ActionMenu label={`${item.title} 的更多操作`} actions={[
                    { key: 'done', label: '标记已完成', onSelect: () => void productApi.completeFocus(item.id).then(() => onChanged?.()) },
                    { key: 'dismiss', label: '不再提示', onSelect: () => void productApi.dismissFocus(item.id).then(() => onChanged?.()) },
                  ]} />
                </div>
              ) : null}
            </div>
          </div>
        </li>
      ))}
    </ol>
  )
}
