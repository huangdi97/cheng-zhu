/** Action Home (canonical §6): next interview · next focus · needs attention · recent session. */
import { CalendarClock, ClipboardList, Flag } from 'lucide-react'
import { navigate, paths } from '@/lib/router'
import { productApi } from '@/lib/productApi'
import { useOsStore } from '@/stores/osStore'
import { NextFocusList } from './NextFocusList'
import { runActionKey } from './actions'
import { EmptyState, ErrorState, formatWhen, Loading, Page, PrimaryButton, Section, SecondaryButton, StatusBadge, useAsync } from './ui'

export default function HomePage() {
  const { data, error, loading, reload } = useAsync(() => productApi.home(), [])
  const openCreateGoal = useOsStore((s) => s.openCreateGoal)

  if (loading && !data) return <Page testId="action-home"><Loading /></Page>
  if (error) return <Page testId="action-home"><ErrorState message={error} onRetry={reload} /></Page>
  if (!data) return null

  if (data.state === 'NO_GOAL' || (!data.focus_goal && !data.next_interview)) {
    return (
      <Page testId="action-home">
        <h1 className="sr-only">首页</h1>
        <div className="py-10">
          <EmptyState testId="home-empty" title="从一个具体的求职目标开始"
            body="告诉成竹你要面的公司和岗位，它会围绕这个目标安排准备、练习、上场和复盘。"
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <PrimaryButton onClick={openCreateGoal} testId="create-first-goal">创建第一个求职目标</PrimaryButton>
                <SecondaryButton onClick={() => navigate(paths.goals())}>查看求职目标</SecondaryButton>
              </div>
            } />
        </div>
        <Attention items={data.needs_attention} />
      </Page>
    )
  }

  const goalId = data.focus_goal?.id ?? null
  return (
    <Page testId="action-home">
      <h1 className="sr-only">首页</h1>
      {data.next_interview ? (
        <section aria-label="下一场" className="rounded-2xl border border-bg-hover/60 bg-bg-secondary/60 p-4">
          <div className="flex items-center gap-2 text-[11px] font-medium text-text-muted">
            <CalendarClock className="h-3.5 w-3.5" aria-hidden /> 下一场
          </div>
          <div className="mt-1 text-lg font-semibold text-text-primary break-words">
            {data.next_interview.company}{data.next_interview.round ? ` · ${data.next_interview.round}` : ''}
          </div>
          <div className="text-sm text-text-secondary">{formatWhen(data.next_interview.scheduled_at)}{data.next_interview.role ? ` · ${data.next_interview.role}` : ''}</div>
          <div className="mt-3 flex flex-wrap gap-2">
            <PrimaryButton onClick={() => runActionKey('continue_prepare', { goalId: data.next_interview!.goal_id })}>继续准备</PrimaryButton>
            <SecondaryButton onClick={() => runActionKey('start_practice', { goalId: data.next_interview!.goal_id })}>开始练习</SecondaryButton>
            <SecondaryButton onClick={() => runActionKey('preflight', { goalId: data.next_interview!.goal_id })}>上场检查</SecondaryButton>
          </div>
        </section>
      ) : data.focus_goal ? (
        <section aria-label="当前目标" className="rounded-2xl border border-bg-hover/60 bg-bg-secondary/60 p-4">
          <div className="flex items-center gap-2 text-[11px] font-medium text-text-muted"><Flag className="h-3.5 w-3.5" aria-hidden /> 当前目标</div>
          <div className="mt-1 text-lg font-semibold text-text-primary break-words">{data.focus_goal.title}</div>
          <div className="text-sm text-text-secondary">还没有安排下一轮时间</div>
          <div className="mt-3 flex flex-wrap gap-2">
            <PrimaryButton onClick={() => runActionKey(data.primary_action.key, { goalId: data.primary_action.goal_id })}>{data.primary_action.label}</PrimaryButton>
            <SecondaryButton onClick={() => goalId && navigate(paths.goal(goalId, 'interviews'))}>安排下一轮</SecondaryButton>
          </div>
        </section>
      ) : null}

      {goalId ? (
        <Section title={`下一步 · ${data.focus_goal?.title ?? ''}`}>
          <NextFocusList goalId={goalId} items={data.next_focus} onChanged={reload} />
        </Section>
      ) : null}

      <Attention items={data.needs_attention} />

      <Section title="最近一场">
        {data.recent_session ? (
          <button type="button" onClick={() => navigate(paths.reflection(data.recent_session!.reflection_ref.session_kind, data.recent_session!.reflection_ref.session_ref))}
            className="flex w-full items-center gap-3 rounded-2xl border border-bg-hover/60 p-3 text-left hover:bg-bg-hover/40">
            <ClipboardList className="h-4 w-4 text-text-muted" aria-hidden />
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium text-text-primary truncate">{data.recent_session.title}{data.recent_session.goal_title ? ` · ${data.recent_session.goal_title}` : ''}</span>
              <span className="block text-[11px] text-text-muted">{formatWhen(data.recent_session.started_at)} · {data.recent_session.type === 'REAL' ? '真实面试' : '练习'}</span>
            </span>
            <span className="text-xs text-accent-blue">查看复盘</span>
          </button>
        ) : (
          <EmptyState title="还没有场次" body="完成第一次练习后，复盘会出现在这里。"
            action={<SecondaryButton onClick={() => runActionKey('start_practice', { goalId })}>开始练习</SecondaryButton>} />
        )}
      </Section>
    </Page>
  )
}

// SAFETY: `needs_attention` is optional in the API response. A partial payload
// must degrade to "nothing needs attention", never crash the shell.
function Attention({ items }: { items?: Array<{ kind: string; text: string; action: { key: string; label: string; goal_id?: string; target?: string } }> }) {
  if (!items?.length) return null
  return (
    <Section title="需要处理">
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item.kind} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-bg-hover/50 px-3 py-2">
            <StatusBadge tone={item.kind === 'MODEL' ? 'risk' : 'warn'}>{item.text}</StatusBadge>
            <SecondaryButton onClick={() => runActionKey(item.action.key, { goalId: item.action.goal_id, target: item.action.target })}>{item.action.label}</SecondaryButton>
          </li>
        ))}
      </ul>
    </Section>
  )
}
