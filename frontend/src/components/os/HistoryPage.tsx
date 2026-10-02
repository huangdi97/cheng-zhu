/** 历史 (canonical §18): Real Interviews · Practice Sessions · Reflections, filtered by Goal / date / type / round. */
import { useState } from 'react'
import { productApi } from '@/lib/productApi'
import { ROUND_LABEL, SessionList } from './SessionList'
import { ErrorState, Field, inputCls, Loading, Page, PageHeader, Tabs, useAsync } from './ui'
import { fromLocalInput } from './CreateGoalDialog'

type Kind = 'ALL' | 'REAL' | 'PRACTICE' | 'REFLECTED'

export default function HistoryPage({ initialGoalId = '' }: { initialGoalId?: string }) {
  const goals = useAsync(() => productApi.goals(), [])
  const [goalId, setGoalId] = useState(initialGoalId)
  const [kind, setKind] = useState<Kind>('ALL')
  const [round, setRound] = useState('')
  const [since, setSince] = useState('')
  const { data, error, loading, reload } = useAsync(
    () => productApi.history({ goal_id: goalId, type: kind === 'REAL' || kind === 'PRACTICE' ? kind : '', round, since: fromLocalInput(since) ?? undefined }),
    [goalId, kind, round, since],
  )
  const items = (data?.items ?? []).filter((i) => kind !== 'REFLECTED' || i.has_reflection_actions)
  return (
    <Page testId="history-page" wide>
      <PageHeader title="历史" subtitle="真实面试、练习和复盘都在这里；目标页里看到的是同一份记录。" />
      <Tabs<Kind> label="场次类型" value={kind} onChange={setKind}
        tabs={[['ALL', '全部'], ['REAL', '真实面试'], ['PRACTICE', '练习'], ['REFLECTED', '已处理复盘']]} />
      <div className="grid gap-2 py-3 sm:grid-cols-3">
        <Field label="求职目标">
          <select className={inputCls} value={goalId} onChange={(e) => setGoalId(e.target.value)}>
            <option value="">全部目标</option>
            {(goals.data?.items ?? []).map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}
          </select>
        </Field>
        <Field label="轮次">
          <select className={inputCls} value={round} onChange={(e) => setRound(e.target.value)}>
            <option value="">全部轮次</option>
            {Object.entries(ROUND_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </Field>
        <Field label="开始于之后"><input type="datetime-local" className={inputCls} value={since} onChange={(e) => setSince(e.target.value)} /></Field>
      </div>
      {loading && !data ? <Loading /> : null}
      {error ? <ErrorState message={error} onRetry={reload} /> : null}
      {data ? <SessionList items={items} showGoal emptyText="没有符合条件的场次。" /> : null}
    </Page>
  )
}
