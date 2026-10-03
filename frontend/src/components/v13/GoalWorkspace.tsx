import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, CalendarClock, ChevronRight, Play, Plus, Snowflake, Target } from 'lucide-react'
import { api, type ProductGoal } from '@/lib/api'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'
import JobWorkspacePanel from '@/components/JobWorkspacePanel'
import QuickNotesPanel from './QuickNotesPanel'

type Tab = 'overview' | 'prepare' | 'interviews' | 'offer'

function fmtDate(ts?: number | null) {
  return ts ? new Date(ts * 1000).toLocaleString() : '未安排'
}

export default function GoalWorkspace() {
  const [goals, setGoals] = useState<ProductGoal[]>([])
  const [goal, setGoal] = useState<ProductGoal | null>(null)
  const [tab, setTab] = useState<Tab>('overview')
  const [creating, setCreating] = useState(false)
  const [draft, setDraft] = useState({ company: '', role: '', jd: '' })
  const [interviews, setInterviews] = useState<Record<string, unknown>[]>([])
  const activeGoalId = useUiPrefsStore((s) => s.activeGoalId)
  const setActiveGoalId = useUiPrefsStore((s) => s.setActiveGoalId)
  const setAppMode = useUiPrefsStore((s) => s.setAppMode)

  const loadGoals = useCallback(async () => {
    const res = await api.productGoals().catch(() => ({ items: [] as ProductGoal[] }))
    setGoals(res.items ?? [])
    const desired = activeGoalId ?? res.items?.[0]?.goal_id ?? null
    if (desired != null) {
      setActiveGoalId(desired)
      const found = res.items.find((g) => g.goal_id === desired)
      if (found) setGoal(found)
      else setGoal(await api.productGoal(desired).catch(() => null))
    } else {
      setGoal(null)
    }
  }, [activeGoalId, setActiveGoalId])

  useEffect(() => { void loadGoals() }, [loadGoals])
  useEffect(() => {
    api.reviewSessions(1, 100).then((r) => setInterviews((r as { items?: Record<string, unknown>[] }).items ?? [])).catch(() => setInterviews([]))
  }, [])

  const select = async (id: number) => {
    setActiveGoalId(id)
    const found = goals.find((g) => g.goal_id === id) ?? await api.productGoal(id).catch(() => null)
    setGoal(found)
    setTab('overview')
    void api.productEvent('goal_opened', { goal_id: id })
  }

  const createGoal = async () => {
    if (!draft.company.trim() && !draft.role.trim() && !draft.jd.trim()) return
    const created = await api.prepCreateSpace({
      title: [draft.company, draft.role].filter(Boolean).join(' · ') || draft.role || '新求职目标',
      company: draft.company,
      role: draft.role,
      jd_text: draft.jd,
    })
    setCreating(false)
    setDraft({ company: '', role: '', jd: '' })
    setActiveGoalId(created.id)
    await api.productEvent('goal_created', { goal_id: created.id })
    await loadGoals()
  }

  const filteredInterviews = useMemo(() => {
    if (!goal) return []
    return interviews.filter((x) => {
      const company = String(x.company ?? '')
      const role = String(x.role ?? '')
      return (goal.company && company === goal.company) || (goal.role && role === goal.role)
    })
  }, [goal, interviews])

  const launch = async () => {
    if (!goal) return
    await api.prepActivateLaunchPack(goal.goal_id).catch(() => null)
    await api.productEvent('preflight_started', { goal_id: goal.goal_id })
    setAppMode('assist')
  }

  if (!goal) {
    return (
      <div className="flex-1 overflow-y-auto p-4 md:p-8" data-testid="goal-workspace-empty">
        <div className="mx-auto max-w-4xl">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-blue">求职目标</div>
              <h2 className="mt-1 text-2xl font-bold text-text-primary">你要拿下哪个岗位？</h2>
            </div>
            <button type="button" onClick={() => setCreating(true)} className="inline-flex items-center gap-1.5 rounded-xl bg-container-primary px-3 py-2 text-sm font-semibold text-container-on-primary">
              <Plus className="h-4 w-4" /> 新建 Goal
            </button>
          </div>
          {goals.length > 0 && <div className="mt-5 grid gap-3 md:grid-cols-2">{goals.map((g) => (
            <button key={g.goal_id} type="button" onClick={() => void select(g.goal_id)}
              className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-4 text-left hover:border-accent-blue/40">
              <div className="text-sm font-semibold text-text-primary">{g.company || '未填写公司'} · {g.role || g.title}</div>
              <div className="mt-1 text-xs text-text-muted">{g.interview_round || g.stage}</div>
            </button>
          ))}</div>}
          {(creating || goals.length === 0) && (
            <div className="mt-5 rounded-2xl border border-bg-hover/60 bg-bg-secondary p-5">
              <div className="grid gap-2 md:grid-cols-2">
                <input value={draft.company} onChange={(e) => setDraft({ ...draft, company: e.target.value })} placeholder="公司" className="rounded-xl border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary" />
                <input value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value })} placeholder="岗位" className="rounded-xl border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary" />
              </div>
              <textarea value={draft.jd} onChange={(e) => setDraft({ ...draft, jd: e.target.value })} rows={7} placeholder="粘贴 JD（可稍后补）"
                className="mt-2 w-full rounded-xl border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary" />
              <button type="button" onClick={() => void createGoal()} className="mt-2 rounded-xl bg-container-primary px-4 py-2 text-sm font-semibold text-container-on-primary">创建 Goal</button>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 min-h-0 overflow-y-auto" data-testid="goal-workspace">
      <div className="border-b border-bg-tertiary/70 bg-bg-secondary/50 px-4 py-4 md:px-6">
        <div className="mx-auto max-w-6xl">
          <button type="button" onClick={() => { setGoal(null); setActiveGoalId(null) }} className="inline-flex items-center gap-1 text-xs text-text-muted hover:text-text-primary"><ArrowLeft className="h-3.5 w-3.5" /> 所有求职目标</button>
          <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold text-text-primary">{goal.company || '未填写公司'} · {goal.role || goal.title}</h2>
              <div className="mt-1 flex flex-wrap gap-3 text-xs text-text-muted">
                <span>{goal.interview_round || '轮次待定'}</span>
                <span className="inline-flex items-center gap-1"><CalendarClock className="h-3.5 w-3.5" /> {fmtDate(goal.next_interview_at)}</span>
              </div>
            </div>
            <div className="flex gap-2">
              <button type="button" onClick={() => setAppMode('prep')} className="inline-flex items-center gap-1.5 rounded-xl border border-accent-green/30 bg-accent-green/10 px-3 py-2 text-sm font-semibold text-status-direct"><Play className="h-4 w-4" /> 开始练习</button>
              <button type="button" onClick={() => void launch()} className="rounded-xl bg-container-primary px-4 py-2 text-sm font-semibold text-container-on-primary">上场</button>
            </div>
          </div>
          <div role="tablist" className="mt-4 flex gap-1 overflow-x-auto">
            {([['overview','概览'],['prepare','准备'],['interviews','面试'],['offer','Offer']] as Array<[Tab,string]>).map(([key,label]) => (
              <button key={key} type="button" role="tab" aria-selected={tab===key} onClick={() => setTab(key)}
                className={`rounded-full px-3 py-1.5 text-xs font-medium ${tab===key?'bg-container-primary text-container-on-primary':'text-text-muted hover:bg-bg-hover/50 hover:text-text-primary'}`}>{label}</button>
            ))}
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl p-4 md:p-6">
        {tab === 'overview' && (
          <div className="grid gap-4 lg:grid-cols-[1.25fr_.75fr]">
            <section className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-5">
              <div className="flex items-center gap-2 text-xs font-semibold text-accent-green"><Target className="h-4 w-4" /> Next Focus</div>
              <div className="mt-3 space-y-2">
                {(goal.next_focus ?? []).length === 0 && <div className="rounded-xl bg-bg-tertiary/40 p-3 text-sm text-text-muted">当前没有高优先 Focus。可以继续准备或练习。</div>}
                {(goal.next_focus ?? []).slice(0, 5).map((f, i) => (
                  <button key={i} type="button" onClick={() => setTab('prepare')} className="flex w-full items-start justify-between rounded-xl bg-bg-tertiary/40 p-3 text-left hover:bg-bg-hover/60">
                    <div><div className="text-sm font-semibold text-text-primary">{f.title}</div>{f.reason && <div className="mt-1 text-xs text-text-muted">{f.reason}</div>}</div>
                    <ChevronRight className="h-4 w-4 text-text-muted" />
                  </button>
                ))}
              </div>
            </section>
            <section className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-5">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">What We Know</div>
              <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-xl bg-bg-tertiary/40 p-3"><dt className="text-xs text-text-muted">Skill Cards</dt><dd className="mt-1 text-xl font-semibold text-text-primary">{goal.skill_card_count ?? 0}</dd></div>
                <div className="rounded-xl bg-bg-tertiary/40 p-3"><dt className="text-xs text-text-muted">Quick Notes</dt><dd className="mt-1 text-xl font-semibold text-text-primary">{goal.quick_note_count}</dd></div>
              </dl>
              <button type="button" onClick={() => setTab('prepare')} className="mt-3 w-full rounded-xl border border-bg-hover px-3 py-2 text-sm text-text-secondary hover:bg-bg-hover/50">打开准备空间</button>
            </section>
            <section className="lg:col-span-2">
              <QuickNotesPanel goalId={goal.goal_id} />
            </section>
          </div>
        )}

        {tab === 'prepare' && (
          <div className="space-y-4">
            <JobWorkspacePanel jdText={goal.jd_text ?? ''} resumeText={goal.resume_text ?? ''} />
            <div className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-text-primary"><Snowflake className="h-4 w-4 text-accent-blue" /> InterviewPack</div>
              <p className="mt-1 text-xs text-text-muted">正式上场前冻结当前 Goal + Person + 已确认材料。Live 不再读取“最近岗位”。</p>
              <button type="button" onClick={() => void launch()} className="mt-3 rounded-xl bg-container-primary px-4 py-2 text-sm font-semibold text-container-on-primary">冻结并进入 Preflight</button>
            </div>
          </div>
        )}

        {tab === 'interviews' && (
          <div className="space-y-2">
            {filteredInterviews.length === 0 && <div className="rounded-2xl border border-dashed border-bg-hover p-6 text-sm text-text-muted">这个 Goal 还没有可关联的 Session。</div>}
            {filteredInterviews.map((s, idx) => (
              <article key={String(s.id ?? idx)} className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-4">
                <div className="text-sm font-semibold text-text-primary">{String(s.title ?? 'Session')}</div>
                <div className="mt-1 text-xs text-text-muted">{String(s.source ?? '')} · {s.turn_count != null ? `${String(s.turn_count)} turns` : ''}</div>
              </article>
            ))}
          </div>
        )}

        {tab === 'offer' && (
          <div className="max-w-2xl rounded-2xl border border-bg-hover/60 bg-bg-secondary p-5">
            <h3 className="text-sm font-semibold text-text-primary">Offer / 决策状态</h3>
            <p className="mt-1 text-xs text-text-muted">这里只管理这个 Goal 的结果与关键期限，不把 Chengzhu 变成完整 ATS。</p>
            <pre className="mt-3 whitespace-pre-wrap rounded-xl bg-bg-tertiary/40 p-3 text-xs text-text-secondary">{JSON.stringify(goal.offer ?? {}, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  )
}
