/**
 * Goal Room (canonical §6) — the main Studio page. Primary views are 概览 / 准备 / 会话.
 * [进入面试] is the primary action; Offer remains a secondary lifecycle surface.
 */
import { lazy, Suspense, useEffect, useState } from 'react'
import { navigate, paths, type GoalTab } from '@/lib/router'
import { productApi, type GoalDetail } from '@/lib/productApi'
import { formatInterviewRound } from '@/lib/interviewRound'
import { useOsStore } from '@/stores/osStore'
import { Dialog, fromLocalInput, toLocalInput } from './CreateGoalDialog'
import { NextFocusList } from './NextFocusList'
import { goLive, startPractice } from './actions'
import { ActionMenu, ErrorState, Field, formatWhen, inputCls, Loading, Page, PrimaryButton, SecondaryButton, Section, StatusBadge, Tabs, useAsync } from './ui'
import GoalPrepare from './GoalPrepare'
import { SessionList } from './SessionList'

const JobTracker = lazy(() => import('@/components/JobTracker'))

const OFFER_STATES: Array<[string, string]> = [
  ['NONE', '暂无'], ['PENDING', '等待结果'], ['RECEIVED', '已收到'], ['NEGOTIATING', '谈判中'], ['ACCEPTED', '已接受'], ['DECLINED', '已拒绝'],
]

const GOAL_STATUS_LABELS: Record<string, string> = {
  ACTIVE: '进行中',
  PAUSED: '已暂停',
  COMPLETED: '已结束',
  ARCHIVED: '已归档',
}

export default function GoalRoom({ goalId, tab }: { goalId: string; tab: GoalTab }) {
  const { data: goal, error, loading, reload } = useAsync(() => productApi.goal(goalId, true), [goalId])
  const setContextGoal = useOsStore((s) => s.setContextGoal)
  const [editOpen, setEditOpen] = useState(false)
  useEffect(() => {
    setContextGoal(goalId)
    return () => setContextGoal(null)
  }, [goalId, setContextGoal])

  if (loading && !goal) return <Page><Loading /></Page>
  if (error) return <Page><ErrorState message={error} onRetry={reload} extra={<SecondaryButton onClick={() => navigate(paths.goals())}>返回目标列表</SecondaryButton>} /></Page>
  if (!goal) return null

  const nextLine = goal.next_interview_at ? `${formatInterviewRound(goal.interview_round) || '下一轮'} · ${formatWhen(goal.next_interview_at)}` : (goal.stage || '还没有安排下一轮')
  const setStatus = (status: string) => void productApi.patchGoal(goal.id, { status } as never).then(reload)

  return (
    <Page testId="goal-room" wide>
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-bg-tertiary/80 pb-5 pt-1">
        <div className="min-w-0">
          <p className="mb-1 text-[11px] font-medium text-text-muted">求职目标</p>
          <h1 className="text-[28px] font-semibold leading-tight tracking-[-0.02em] text-text-primary break-words md:text-[32px]">{goal.title}</h1>
          <p className="mt-1.5 text-sm text-text-muted">{nextLine}{goal.status !== 'ACTIVE' ? ` · ${GOAL_STATUS_LABELS[goal.status] ?? goal.status}` : ''}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SecondaryButton testId="goal-start-practice" onClick={() => startPractice(goal.id)}>练习模拟</SecondaryButton>
          <PrimaryButton testId="goal-go-live" onClick={() => goLive(goal.id)}>进入面试</PrimaryButton>
          <ActionMenu label="目标操作" actions={[
            { key: 'edit', label: '编辑目标信息', onSelect: () => setEditOpen(true) },
            { key: 'offer', label: goal.offer_state !== 'NONE' ? `录用状态 · ${OFFER_STATES.find(([key]) => key === goal.offer_state)?.[1] ?? goal.offer_state}` : '录用状态', onSelect: () => navigate(paths.goal(goal.id, 'offer')) },
            { key: 'settings', label: '目标默认设置', onSelect: () => navigate(`${paths.settings('language')}?goal=${goal.id}`) },
            { key: 'export', label: '导出这个目标', onSelect: () => void productApi.exportData({ kind: 'goal', goal_id: goal.id }).then((r) => window.alert(`已导出到 ${r.path}`)) },
            goal.status === 'ACTIVE'
              ? { key: 'pause', label: '暂停', onSelect: () => setStatus('PAUSED') }
              : { key: 'resume', label: '恢复为进行中', onSelect: () => setStatus('ACTIVE') },
            { key: 'complete', label: '标记已结束', onSelect: () => setStatus('COMPLETED') },
            { key: 'delete', label: '删除目标', danger: true, onSelect: () => {
              if (window.confirm(`删除「${goal.title}」？目标内的速记、面试轮次和下一步建议会一起删除；练习与复盘记录保留在历史里。`)) {
                void productApi.deleteGoal(goal.id).then(() => navigate(paths.goals()))
              }
            } },
          ]} />
        </div>
      </header>
      <div className="pt-1">
        <Tabs<GoalTab> label="目标视图" value={tab} onChange={(t) => navigate(paths.goal(goal.id, t), { replace: true })}
          tabs={[['overview', '概览'], ['prepare', '准备'], ['interviews', '会话', goal.interviews.filter((i) => i.status === 'UPCOMING').length]]} />
      </div>
      <div className="pt-3">
        {tab === 'overview' ? <Overview goal={goal} reload={reload} /> : null}
        {tab === 'prepare' ? <GoalPrepare goal={goal} reload={reload} /> : null}
        {tab === 'interviews' ? <Interviews goal={goal} reload={reload} /> : null}
        {tab === 'offer' ? <Offer goal={goal} reload={reload} /> : null}
      </div>
      {editOpen ? <EditGoalDialog goal={goal} onClose={() => setEditOpen(false)} onSaved={() => { setEditOpen(false); void reload() }} /> : null}
    </Page>
  )
}

function Overview({ goal, reload }: { goal: GoalDetail; reload: () => void }) {
  const [notes, setNotes] = useState(goal.goal_notes)
  const [notesEditing, setNotesEditing] = useState(Boolean(goal.goal_notes))
  const jdLines = goal.jd.split('\n').map((l) => l.trim()).filter(Boolean).slice(0, 4)
  const upcoming = goal.interviews.filter((i) => i.status === 'UPCOMING')
  return (
    <div className="grid gap-x-10 lg:grid-cols-[minmax(0,1.55fr)_minmax(260px,0.7fr)]">
      <div className="min-w-0">
        <Section title="接下来最值得准备">
          <NextFocusList goalId={goal.id} items={goal.next_focus} onChanged={reload} />
        </Section>
        <Section title="最近的会话" action={<SecondaryButton onClick={() => navigate(paths.goal(goal.id, 'interviews'))}>全部</SecondaryButton>}>
          <SessionList items={goal.sessions.slice(0, 4)} emptyText="还没有练习或面试记录。" />
        </Section>
        <details className="border-t border-bg-tertiary/70 py-3">
          <summary className="cursor-pointer list-none text-xs font-medium text-text-muted transition-colors hover:text-text-primary">
            查看进展趋势
          </summary>
          <div className="pt-2"><ProgressTrends goalId={goal.id} /></div>
        </details>
      </div>
      <aside className="min-w-0 lg:border-l lg:border-bg-tertiary/70 lg:pl-7">
        <Section title="下一场">
          {upcoming.length ? (
            <ul className="space-y-1 text-sm">
              {upcoming.slice(0, 2).map((i) => <li key={i.id} className="text-text-primary">{formatInterviewRound(i.round) || '面试'} · <span className="text-text-secondary">{formatWhen(i.scheduled_at) || '时间待定'}</span></li>)}
            </ul>
          ) : (
            <SecondaryButton onClick={() => navigate(paths.goal(goal.id, 'interviews'))}>安排下一轮</SecondaryButton>
          )}
        </Section>
        <Section title="目标简介">
          <dl className="space-y-1.5 text-xs">
            <div><dt className="inline text-text-muted">岗位：</dt><dd className="inline text-text-primary">{goal.role || '未填写'}</dd></div>
            <div><dt className="inline text-text-muted">阶段：</dt><dd className="inline text-text-primary">{goal.stage || '未记录'}</dd></div>
            <div>
              <dt className="text-text-muted">JD 摘要：</dt>
              <dd className="text-text-secondary">{jdLines.length ? jdLines.map((l) => <div key={l} className="truncate">{l}</div>) : <button type="button" className="text-accent-blue underline" onClick={() => navigate(paths.goal(goal.id, 'prepare'))}>补充 JD</button>}</dd>
            </div>
          </dl>
          <div className="mt-3">
            {notesEditing || notes ? (
              <Field label="目标备注（面试官信息、对方透露的情况…）">
                <textarea className={`${inputCls} min-h-[64px]`} value={notes} onChange={(e) => setNotes(e.target.value)}
                  onBlur={() => {
                    if (notes !== goal.goal_notes) void productApi.patchGoal(goal.id, { goal_notes: notes }).then(reload)
                    if (!notes.trim()) setNotesEditing(false)
                  }} />
              </Field>
            ) : (
              <button type="button" onClick={() => setNotesEditing(true)}
                className="text-xs text-accent-blue underline underline-offset-2 hover:text-accent-blue/80">
                + 补充面试官信息或目标备注
              </button>
            )}
          </div>
        </Section>
      </aside>
    </div>
  )
}

function ProgressTrends({ goalId }: { goalId: string }) {
  const { data, error, loading, reload } = useAsync(() => productApi.trends(goalId), [goalId])
  const direction = {
    IMPROVING: ['在改善', 'ok'],
    DECLINING: ['需要注意', 'risk'],
    REPEATING: ['反复出现', 'warn'],
    STABLE: ['保持稳定', 'muted'],
    INSUFFICIENT: ['数据不足', 'muted'],
  } as const

  return (
    <Section title="进展趋势" action={data?.sessions ? <span className="text-[11px] text-text-muted">最近 {data.sessions} 场</span> : null}>
      {loading && !data ? <Loading label="整理最近练习与面试…" /> : null}
      {error ? <ErrorState message={error} onRetry={reload} /> : null}
      {data && !data.dimensions.length ? (
        <p className="text-xs text-text-muted">完成至少两次带复盘的练习或面试后，这里会显示具体能力的变化，而不是一个综合“面试分”。</p>
      ) : null}
      {data?.dimensions.length ? (
        <ul className="space-y-2" data-testid="goal-progress-trends">
          {data.dimensions.slice(0, 6).map((d) => {
            const [label, tone] = direction[d.direction]
            const latest = d.series[d.series.length - 1]
            const first = d.series[0]
            return (
              <li key={d.dimension} className="rounded-xl border border-bg-hover/50 px-3 py-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="min-w-0 flex-1 text-xs font-medium text-text-primary">{d.label}</span>
                  <StatusBadge tone={tone}>{label}</StatusBadge>
                </div>
                <p className="mt-1 text-[11px] text-text-secondary">{d.text}</p>
                {d.series.length >= 2 ? (
                  <div className="mt-1 flex items-center gap-1.5 text-[11px] text-text-muted" aria-label={`${d.label} 趋势，从 ${first} 到 ${latest}`}>
                    <span>{first}</span>
                    <span aria-hidden>→</span>
                    <span className="font-medium text-text-primary">{latest}</span>
                    <span>· {d.series.length} 次观察</span>
                  </div>
                ) : null}
              </li>
            )
          })}
          {data.delivery ? (
            <li className="rounded-xl border border-bg-hover/50 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="min-w-0 flex-1 text-xs font-medium text-text-primary">表达</span>
                <StatusBadge tone={direction[data.delivery.direction as keyof typeof direction]?.[1] ?? 'muted'}>
                  {direction[data.delivery.direction as keyof typeof direction]?.[0] ?? data.delivery.direction}
                </StatusBadge>
              </div>
              <p className="mt-1 text-[11px] text-text-secondary">{data.delivery.text}</p>
            </li>
          ) : null}
        </ul>
      ) : null}
      <p className="mt-2 text-[11px] text-text-muted">这些只反映同一求职目标下的练习和复盘变化，不是录用概率，也不和其他候选人比较。</p>
    </Section>
  )
}

function Interviews({ goal, reload }: { goal: GoalDetail; reload: () => void }) {
  const [round, setRound] = useState('')
  const [when, setWhen] = useState('')
  const [boardOpen, setBoardOpen] = useState(false)
  const real = goal.sessions.filter((s) => s.type === 'REAL')
  const practice = goal.sessions.filter((s) => s.type === 'PRACTICE')
  const reflected = goal.sessions.filter((s) => s.has_reflection_actions)
  return (
    <div>
      <Section title="即将到来">
        <ul className="space-y-1.5">
          {goal.interviews.filter((i) => i.status === 'UPCOMING').map((i) => (
            <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-bg-hover/50 px-3 py-2">
              <span className="text-sm text-text-primary">{formatInterviewRound(i.round) || '面试'} · <span className="text-text-secondary">{formatWhen(i.scheduled_at) || '时间待定'}</span></span>
              <span className="flex items-center gap-1">
                <SecondaryButton onClick={() => goLive(goal.id)}>上场检查</SecondaryButton>
                <ActionMenu label="轮次操作" actions={[
                  { key: 'done', label: '标记已面完', onSelect: () => void productApi.patchInterview(i.id, { status: 'DONE' }).then(reload) },
                  { key: 'cancel', label: '取消这一轮', onSelect: () => void productApi.patchInterview(i.id, { status: 'CANCELLED' }).then(reload) },
                  { key: 'delete', label: '删除', danger: true, onSelect: () => void productApi.deleteInterview(i.id).then(reload) },
                ]} />
              </span>
            </li>
          ))}
        </ul>
        <form className="mt-2 flex flex-wrap items-end gap-2" onSubmit={(e) => {
          e.preventDefault()
          void productApi.addInterview(goal.id, { round, scheduled_at: fromLocalInput(when) }).then(() => { setRound(''); setWhen(''); reload() })
        }}>
          <Field label="轮次"><input className={inputCls} value={round} onChange={(e) => setRound(e.target.value)} placeholder="技术二面" /></Field>
          <Field label="时间"><input type="datetime-local" className={inputCls} value={when} onChange={(e) => setWhen(e.target.value)} /></Field>
          <PrimaryButton type="submit" disabled={!round.trim() && !when}>添加轮次</PrimaryButton>
        </form>
      </Section>
      <Section title={`真实面试 · ${real.length}`}><SessionList items={real} emptyText="还没有真实面试记录。上场结束后会自动出现在这里。" /></Section>
      <Section title={`练习 · ${practice.length}`}><SessionList items={practice} emptyText="还没有练习。" /></Section>
      <Section title={`已处理复盘 · ${reflected.length}`}><SessionList items={reflected} emptyText="复盘中执行过的动作会在这里汇总。" /></Section>
      {goal.application_id ? (
        <Section title="投递记录（旧版看板）" action={<SecondaryButton onClick={() => setBoardOpen((v) => !v)}>{boardOpen ? '收起' : '打开'}</SecondaryButton>}>
          {boardOpen ? <div className="h-[520px] flex flex-col rounded-xl border border-bg-hover/50 overflow-hidden"><Suspense fallback={<Loading />}><JobTracker /></Suspense></div> : null}
        </Section>
      ) : null}
    </div>
  )
}

function Offer({ goal, reload }: { goal: GoalDetail; reload: () => void }) {
  const [status, setStatus] = useState(goal.offer.status)
  const [comp, setComp] = useState(goal.offer.comp)
  const [deadline, setDeadline] = useState(toLocalInput(goal.offer.deadline))
  const [notes, setNotes] = useState(goal.offer.notes)
  const [saved, setSaved] = useState(false)
  return (
    <form className="max-w-lg space-y-3" onSubmit={(e) => {
      e.preventDefault()
      void productApi.putOffer(goal.id, { status, comp, deadline: fromLocalInput(deadline), notes }).then(() => { setSaved(true); reload() })
    }}>
      <Field label="状态">
        <select className={inputCls} value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
          {OFFER_STATES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </Field>
      <Field label="薪资与构成"><textarea className={`${inputCls} min-h-[64px]`} value={comp} onChange={(e) => setComp(e.target.value)} placeholder="base / bonus / equity" /></Field>
      <Field label="答复截止"><input type="datetime-local" className={inputCls} value={deadline} onChange={(e) => setDeadline(e.target.value)} /></Field>
      <Field label="备注"><textarea className={`${inputCls} min-h-[64px]`} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
      <div className="flex items-center gap-2">
        <PrimaryButton type="submit">保存</PrimaryButton>
        {saved ? <span role="status" className="text-xs text-status-direct">已保存</span> : null}
      </div>
    </form>
  )
}

function EditGoalDialog({ goal, onClose, onSaved }: { goal: GoalDetail; onClose: () => void; onSaved: () => void }) {
  const [company, setCompany] = useState(goal.company)
  const [role, setRole] = useState(goal.role)
  const [stage, setStage] = useState(goal.stage)
  const [jd, setJd] = useState(goal.jd)
  return (
    <Dialog title="编辑目标信息" onClose={onClose} labelledBy="edit-goal-title">
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); void productApi.patchGoal(goal.id, { company, role, stage, jd }).then(onSaved) }}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="公司"><input className={inputCls} value={company} onChange={(e) => setCompany(e.target.value)} /></Field>
          <Field label="岗位"><input className={inputCls} value={role} onChange={(e) => setRole(e.target.value)} /></Field>
        </div>
        <Field label="阶段（投递、一面、二面…）"><input className={inputCls} value={stage} onChange={(e) => setStage(e.target.value)} /></Field>
        <Field label="JD"><textarea className={`${inputCls} min-h-[120px]`} value={jd} onChange={(e) => setJd(e.target.value)} /></Field>
        <div className="flex justify-end gap-2"><SecondaryButton onClick={onClose}>取消</SecondaryButton><PrimaryButton type="submit">保存</PrimaryButton></div>
      </form>
    </Dialog>
  )
}
