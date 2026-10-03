import { ClipboardList, Mic, Users } from 'lucide-react'
import { navigate, paths } from '@/lib/router'
import type { HistoryItem } from '@/lib/productApi'
import { EmptyState, formatWhen } from './ui'

const ROUND_LABEL: Record<string, string> = {
  TECHNICAL: '技术面', PROJECT_DEEP_DIVE: '项目深挖', SYSTEM_DESIGN: '系统设计', HIRING_MANAGER: 'Hiring Manager',
  HR: 'HR 面', BEHAVIORAL: '行为面', PRODUCT_CASE: '产品 / Case',
}

/** Same rows as History — Goal Room and History read one list, never a copy. */
export function SessionList({ items, emptyText, showGoal = false }: { items: HistoryItem[]; emptyText: string; showGoal?: boolean }) {
  if (!items.length) return <EmptyState title={emptyText} />
  return (
    <ul className="space-y-1.5">
      {items.map((item) => {
        const Icon = item.type === 'REAL' ? Mic : item.panel ? Users : ClipboardList
        return (
          <li key={item.key}>
            <button type="button" onClick={() => navigate(paths.reflection(item.reflection_ref.session_kind, item.reflection_ref.session_ref))}
              className="flex w-full items-center gap-3 rounded-xl border border-bg-hover/50 px-3 py-2 text-left hover:bg-bg-hover/40">
              <Icon className="h-4 w-4 flex-shrink-0 text-text-muted" aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm text-text-primary">
                  {item.type === 'REAL' ? '真实面试' : item.guided ? '引导练习' : item.panel ? '小组面练习' : '练习'}
                  {item.round ? ` · ${ROUND_LABEL[item.round] ?? item.round}` : ''}
                  {showGoal && item.goal_title ? ` · ${item.goal_title}` : ''}
                </span>
                <span className="block text-[11px] text-text-muted">{formatWhen(item.started_at)}{item.has_reflection_actions ? ' · 已处理复盘' : ''}</span>
              </span>
              <span className="text-[11px] text-accent-blue">复盘</span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

export { ROUND_LABEL }
