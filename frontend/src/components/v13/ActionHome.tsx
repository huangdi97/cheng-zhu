import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, ArrowRight, CalendarClock, CheckCircle2, Mic, Play, Target } from 'lucide-react'
import { api, type FactItem, type ProductGoal } from '@/lib/api'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'

function when(ts?: number | null) {
  if (!ts) return '时间待定'
  return new Date(ts * 1000).toLocaleString()
}

export default function ActionHome() {
  const [goals, setGoals] = useState<ProductGoal[]>([])
  const [facts, setFacts] = useState<FactItem[]>([])
  const [loading, setLoading] = useState(true)
  const setAppMode = useUiPrefsStore((s) => s.setAppMode)
  const setActiveGoalId = useUiPrefsStore((s) => s.setActiveGoalId)

  useEffect(() => {
    let alive = true
    Promise.all([
      api.productGoals().catch(() => ({ items: [] })),
      api.intelFacts().catch(() => ({ candidate_id: '', facts: [], evidence: [] })),
    ]).then(([g, f]) => {
      if (!alive) return
      setGoals(g.items ?? [])
      setFacts(f.facts ?? [])
      setLoading(false)
    })
    return () => { alive = false }
  }, [])

  const activeGoals = useMemo(
    () => goals.filter((g) => g.stage !== 'completed' && g.stage !== 'archived'),
    [goals],
  )
  const target = useMemo(() => {
    const withDate = [...activeGoals].filter((g) => g.next_interview_at).sort((a, b) => Number(a.next_interview_at) - Number(b.next_interview_at))
    return withDate[0] ?? activeGoals[0] ?? null
  }, [activeGoals])
  const pendingFacts = facts.filter((f) => f.user_assertion_status === 'UNREVIEWED')

  const openGoal = (id: number) => {
    setActiveGoalId(id)
    setAppMode('goals')
    void api.productEvent('goal_opened', { goal_id: id })
  }
  const practice = (id: number) => {
    setActiveGoalId(id)
    setAppMode('prep')
    void api.productEvent('practice_started_from_home', { goal_id: id })
  }
  const live = (id?: number) => {
    if (id != null) setActiveGoalId(id)
    setAppMode('assist')
    void api.productEvent('preflight_started', { goal_id: id })
  }

  if (loading) {
    return <div className="flex-1 grid place-items-center text-sm text-text-muted">正在恢复你的求职上下文…</div>
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8" data-testid="v13-action-home">
      <div className="mx-auto max-w-5xl space-y-5">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-accent-green">Chengzhu · Interview OS</div>
            <h2 className="mt-1 text-2xl font-bold tracking-tight text-text-primary">现在最值得做什么？</h2>
            <p className="mt-1 text-sm text-text-muted">系统可以复杂，但你的下一步必须简单。</p>
          </div>
          <button type="button" onClick={() => live(target?.goal_id)}
            className="inline-flex items-center gap-2 rounded-xl bg-container-primary px-4 py-2.5 text-sm font-semibold text-container-on-primary shadow-sm">
            <Mic className="h-4 w-4" /> 上场
          </button>
        </header>

        {!target ? (
          <section className="rounded-2xl border border-dashed border-bg-hover bg-bg-secondary p-7">
            <Target className="h-6 w-6 text-accent-blue" />
            <h3 className="mt-3 text-base font-semibold text-text-primary">先创建第一个求职目标</h3>
            <p className="mt-1 text-sm text-text-muted">一个 Goal = 一家公司 × 一个岗位。准备、练习、面试和复盘都围绕它持续积累。</p>
            <button type="button" onClick={() => setAppMode('goals')}
              className="mt-4 rounded-xl bg-container-primary px-4 py-2 text-sm font-semibold text-container-on-primary">
              创建求职目标
            </button>
          </section>
        ) : (
          <>
            <section className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-5 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 text-xs font-semibold text-accent-blue"><CalendarClock className="h-4 w-4" /> 下一场</div>
                  <h3 className="mt-2 text-xl font-bold text-text-primary">{target.company || '未填写公司'} · {target.role || target.title}</h3>
                  <p className="mt-1 text-sm text-text-muted">{target.interview_round || '面试轮次待定'} · {when(target.next_interview_at)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => openGoal(target.goal_id)}
                    className="rounded-xl border border-bg-hover px-3 py-2 text-sm font-medium text-text-secondary hover:bg-bg-hover/50">继续准备</button>
                  <button type="button" onClick={() => practice(target.goal_id)}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-accent-green/30 bg-accent-green/10 px-3 py-2 text-sm font-semibold text-status-direct">
                    <Play className="h-4 w-4" /> 开始练习
                  </button>
                  <button type="button" onClick={() => live(target.goal_id)}
                    className="rounded-xl bg-container-primary px-3 py-2 text-sm font-semibold text-container-on-primary">Preflight</button>
                </div>
              </div>
            </section>

            <div className="grid gap-4 lg:grid-cols-[1.35fr_.65fr]">
              <section className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-5">
                <div className="flex items-center gap-2 text-xs font-semibold text-accent-green"><Target className="h-4 w-4" /> Next Focus</div>
                {target.next_focus?.length ? (
                  <div className="mt-3 space-y-3">
                    {target.next_focus.slice(0, 3).map((item, idx) => (
                      <button key={idx} type="button" onClick={() => openGoal(target.goal_id)}
                        className="group flex w-full items-start justify-between gap-3 rounded-xl bg-bg-tertiary/40 p-3 text-left hover:bg-bg-hover/60">
                        <div>
                          <div className="text-sm font-semibold text-text-primary">{item.title}</div>
                          {item.reason && <div className="mt-1 text-xs leading-relaxed text-text-muted">{item.reason}</div>}
                        </div>
                        <ArrowRight className="mt-0.5 h-4 w-4 flex-shrink-0 text-text-muted group-hover:text-text-primary" />
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="mt-3 flex items-center gap-2 rounded-xl bg-accent-green/8 p-3 text-sm text-text-secondary">
                    <CheckCircle2 className="h-4 w-4 text-status-direct" /> 当前没有高优先 blocker。可以继续练习或进入 Preflight。
                  </div>
                )}
              </section>

              <section className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-5">
                <div className="flex items-center gap-2 text-xs font-semibold text-status-inferred"><AlertCircle className="h-4 w-4" /> 需要你处理</div>
                <button type="button" onClick={() => setAppMode('resume-opt')}
                  className="mt-3 w-full rounded-xl bg-bg-tertiary/40 p-3 text-left hover:bg-bg-hover/60">
                  <div className="text-2xl font-semibold tabular-nums text-text-primary">{pendingFacts.length}</div>
                  <div className="mt-1 text-xs text-text-muted">个事实待确认</div>
                </button>
                <button type="button" onClick={() => openGoal(target.goal_id)}
                  className="mt-2 w-full rounded-xl bg-bg-tertiary/40 p-3 text-left hover:bg-bg-hover/60">
                  <div className="text-2xl font-semibold tabular-nums text-text-primary">{target.quick_note_count}</div>
                  <div className="mt-1 text-xs text-text-muted">条当前 Goal Quick Notes</div>
                </button>
              </section>
            </div>

            {activeGoals.length > 1 && (
              <section className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-5">
                <div className="text-xs font-semibold uppercase tracking-[0.15em] text-text-muted">其它进行中的 Goal</div>
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {activeGoals.filter((g) => g.goal_id !== target.goal_id).slice(0, 4).map((goal) => (
                    <button key={goal.goal_id} type="button" onClick={() => openGoal(goal.goal_id)}
                      className="flex items-center justify-between rounded-xl border border-bg-hover/40 p-3 text-left hover:bg-bg-hover/50">
                      <div>
                        <div className="text-sm font-semibold text-text-primary">{goal.company || '未填写公司'} · {goal.role || goal.title}</div>
                        <div className="mt-0.5 text-xs text-text-muted">{goal.interview_round || goal.stage}</div>
                      </div>
                      <ArrowRight className="h-4 w-4 text-text-muted" />
                    </button>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  )
}
