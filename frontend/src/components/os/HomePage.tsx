/** Action Home (canonical §6): one current Goal, one next action, supporting history. */
import { CalendarClock, ClipboardList, Flag } from 'lucide-react'
import { navigate, paths } from '@/lib/router'
import { productApi } from '@/lib/productApi'
import { formatInterviewRound } from '@/lib/interviewRound'
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
      <Page testId="action-home" wide>
        <h1 className="sr-only">首页</h1>
        <div className="mx-auto max-w-2xl py-16">
          <EmptyState testId="home-empty" title="从一个具体的求职目标开始"
            body="告诉成竹你要面的公司和岗位。之后的准备、练习、上场和复盘都围绕这个目标推进。"
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

  const goalId = data.next_interview?.goal_id ?? data.focus_goal?.id ?? null
  const heroTitle = data.next_interview
    ? data.next_interview.title || [data.next_interview.company, data.next_interview.role].filter(Boolean).join(' · ')
    : data.focus_goal?.title ?? '当前目标'
  const heroMeta = data.next_interview
    ? [data.next_interview.role, formatInterviewRound(data.next_interview.round), formatWhen(data.next_interview.scheduled_at)].filter(Boolean).join(' · ')
    : '还没有安排下一轮时间'

  return (
    <Page testId="action-home" wide>
      <h1 className="sr-only">首页</h1>

      <section aria-label={data.next_interview ? '下一场' : '当前目标'} className="border-b border-bg-tertiary/80 pb-6 pt-2">
        <div className="flex items-center gap-2 text-[11px] font-medium text-text-muted">
          {data.next_interview ? <CalendarClock className="h-3.5 w-3.5" aria-hidden /> : <Flag className="h-3.5 w-3.5" aria-hidden />}
          {data.next_interview ? '下一场面试' : '当前目标'}
        </div>
        <div className="mt-2 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <h2 className="text-[28px] font-semibold leading-tight tracking-[-0.02em] text-text-primary break-words md:text-[32px]">
              {heroTitle}
            </h2>
            <p className="mt-1.5 text-sm text-text-muted">{heroMeta}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {data.next_interview ? (
              <>
                <PrimaryButton onClick={() => runActionKey('continue_prepare', { goalId: data.next_interview!.goal_id })}>继续准备</PrimaryButton>
                <SecondaryButton onClick={() => runActionKey('start_practice', { goalId: data.next_interview!.goal_id })}>开始练习</SecondaryButton>
                <SecondaryButton onClick={() => runActionKey('preflight', { goalId: data.next_interview!.goal_id })}>上场检查</SecondaryButton>
              </>
            ) : (
              <>
                <PrimaryButton onClick={() => runActionKey(data.primary_action.key, { goalId: data.primary_action.goal_id })}>{data.primary_action.label}</PrimaryButton>
                <SecondaryButton onClick={() => goalId && navigate(paths.goal(goalId, 'interviews'))}>安排下一轮</SecondaryButton>
              </>
            )}
          </div>
        </div>
      </section>

      <div className="grid gap-x-10 lg:grid-cols-[minmax(0,1.55fr)_minmax(260px,0.7fr)]">
        <div className="min-w-0">
          {goalId ? (
            <Section title="接下来最值得准备">
              <NextFocusList goalId={goalId} items={data.next_focus} onChanged={reload} />
            </Section>
          ) : null}

          <Section title="最近的会话">
            {data.recent_session ? (
              <button type="button" onClick={() => navigate(paths.reflection(data.recent_session!.reflection_ref.session_kind, data.recent_session!.reflection_ref.session_ref))}
                className="group flex w-full items-center gap-3 border-y border-bg-tertiary/70 px-1 py-3 text-left transition-colors hover:bg-bg-hover/25">
                <ClipboardList className="h-4 w-4 flex-shrink-0 text-text-muted" aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium text-text-primary truncate">{data.recent_session.title}{data.recent_session.goal_title ? ` · ${data.recent_session.goal_title}` : ''}</span>
                  <span className="mt-0.5 block text-[11px] text-text-muted">{formatWhen(data.recent_session.started_at)} · {data.recent_session.type === 'REAL' ? '真实面试' : '练习'}</span>
                </span>
                <span className="text-xs text-text-muted transition-colors group-hover:text-text-primary">查看复盘</span>
              </button>
            ) : (
              <EmptyState title="还没有场次" body="完成第一次练习后，复盘会出现在这里。"
                action={<SecondaryButton onClick={() => runActionKey('start_practice', { goalId })}>开始练习</SecondaryButton>} />
            )}
          </Section>
        </div>

        <aside className="min-w-0 lg:border-l lg:border-bg-tertiary/70 lg:pl-7">
          <Section title="目标上下文">
            <div className="space-y-2 text-xs">
              <p className="font-medium text-text-primary">{data.focus_goal?.title ?? heroTitle}</p>
              <p className="leading-5 text-text-muted">
                {data.next_interview
                  ? `下一场已安排 · ${formatWhen(data.next_interview.scheduled_at)}`
                  : '下一场时间还没有安排。'}
              </p>
              {data.active_goal_count > 1 ? (
                <button type="button" onClick={() => navigate(paths.goals())}
                  className="text-left text-text-secondary underline decoration-bg-hover underline-offset-2 transition-colors hover:text-text-primary">
                  还有 {data.active_goal_count - 1} 个进行中的目标
                </button>
              ) : null}
            </div>
          </Section>
          <Attention items={data.needs_attention} />
        </aside>
      </div>
    </Page>
  )
}

// SAFETY: `needs_attention` is optional in the API response. A partial payload
// must degrade to "nothing needs attention", never crash the shell.
function Attention({ items }: { items?: Array<{ kind: string; text: string; action: { key: string; label: string; goal_id?: string; target?: string } }> }) {
  if (!items?.length) return null
  return (
    <Section title="需要处理">
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.kind} className="flex flex-wrap items-center justify-between gap-2 border-b border-bg-tertiary/70 pb-2 last:border-b-0">
            <StatusBadge tone={item.kind === 'MODEL' ? 'risk' : 'warn'}>{item.text}</StatusBadge>
            <SecondaryButton onClick={() => runActionKey(item.action.key, { goalId: item.action.goal_id, target: item.action.target })}>{item.action.label}</SecondaryButton>
          </li>
        ))}
      </ul>
    </Section>
  )
}
