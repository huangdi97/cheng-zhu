/** 求职目标 list (canonical §6): Active first, Completed collapsed; stage is metadata, not an ATS board. */
import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { navigate, paths } from '@/lib/router'
import { productApi, type Goal } from '@/lib/productApi'
import { useOsStore } from '@/stores/osStore'
import { EmptyState, ErrorState, formatWhen, Loading, Page, PageHeader, PrimaryButton, Section, SecondaryButton, useAsync } from './ui'

const STATUS_LABEL: Record<string, string> = { ACTIVE: '进行中', PAUSED: '暂停', COMPLETED: '已结束', ARCHIVED: '已归档' }

function GoalRow({ goal }: { goal: Goal }) {
  const next = goal.next_interview_at ? `${goal.interview_round || '下一轮'} · ${formatWhen(goal.next_interview_at)}` : (goal.stage || '待安排')
  return (
    <li>
      <button type="button" onClick={() => navigate(paths.goal(goal.id))}
        className="flex w-full items-center gap-3 rounded-2xl border border-bg-hover/60 px-4 py-3 text-left hover:bg-bg-hover/40">
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-text-primary break-words">{goal.title}</span>
          <span className="block text-xs text-text-muted">{next}{goal.offer_state !== 'NONE' ? ` · Offer：${goal.offer_state}` : ''}</span>
        </span>
        <ChevronRight className="h-4 w-4 text-text-muted" aria-hidden />
      </button>
    </li>
  )
}

export default function GoalsPage() {
  const { data, error, loading, reload } = useAsync(() => productApi.goals(), [])
  const openCreateGoal = useOsStore((s) => s.openCreateGoal)
  const [showDone, setShowDone] = useState(false)
  const items = data?.items ?? []
  const active = items.filter((g) => g.status === 'ACTIVE' || g.status === 'PAUSED')
  const done = items.filter((g) => g.status === 'COMPLETED' || g.status === 'ARCHIVED')
  return (
    <Page testId="goals-page">
      <PageHeader title="求职目标" subtitle="每个目标对应一个岗位：准备、练习、上场和复盘都围绕它进行。"
        actions={<PrimaryButton onClick={openCreateGoal} testId="create-goal">新建目标</PrimaryButton>} />
      {loading && !data ? <Loading /> : null}
      {error ? <ErrorState message={error} onRetry={reload} /> : null}
      {data && !items.length ? (
        <EmptyState title="还没有求职目标" body="创建一个目标后，成竹会给出下一步。" action={<PrimaryButton onClick={openCreateGoal}>创建第一个求职目标</PrimaryButton>} />
      ) : null}
      {active.length ? (
        <Section title={`Active · ${active.length}`}>
          <ul className="space-y-2">{active.map((g) => <GoalRow key={g.id} goal={g} />)}</ul>
        </Section>
      ) : null}
      {done.length ? (
        <Section title={`Completed · ${done.length}`} action={<SecondaryButton onClick={() => setShowDone((v) => !v)}>{showDone ? '收起' : '展开'}</SecondaryButton>}>
          {showDone ? <ul className="space-y-2">{done.map((g) => <GoalRow key={g.id} goal={g} />)}</ul> : null}
        </Section>
      ) : null}
      <p className="pt-3 text-[11px] text-text-muted">状态：{Object.values(STATUS_LABEL).join(' / ')}。旧版投递看板仍可在目标的「面试」页打开。</p>
    </Page>
  )
}
