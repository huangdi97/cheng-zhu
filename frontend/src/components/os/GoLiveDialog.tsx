/**
 * Go Live → Preflight 3.0 (canonical §17). Lists every input of the coming
 * session with its origin (我的成竹 / Goal 默认 / 本场覆盖 / 系统默认).
 * Overrides chosen here apply to this session only.
 */
import { useEffect, useState } from 'react'
import { navigate, paths } from '@/lib/router'
import { productApi, type Preflight } from '@/lib/productApi'
import { setLiveContextLabel } from '@/lib/liveContext'
import { useOsStore } from '@/stores/osStore'
import { Dialog } from './CreateGoalDialog'
import { ErrorState, Field, inputCls, Loading, PrimaryButton, SecondaryButton, useAsync } from './ui'

const OVERRIDABLE: Record<string, Array<[string, string]>> = {
  answer_language: [['中文', '中文'], ['English', 'English'], ['FOLLOW_INTERVIEW', '跟随面试语言']],
  whisper_language: [['auto', '自动识别'], ['zh', '中文'], ['en', 'English']],
  ai_policy_mode: [['AI_FORBIDDEN', '禁止 AI'], ['AI_LIMITED', '有限 AI'], ['AI_ALLOWED', '允许 AI'], ['AI_EXPECTED', '要求使用 AI']],
  human_assistance_policy: [['HUMAN_FORBIDDEN', '禁止真人辅助'], ['HUMAN_PRACTICE_ONLY', '仅练习'], ['HUMAN_ALLOWED', '允许真人辅助']],
  share_privacy_mode: [['OFF', '关闭'], ['PRIVATE_OVERLAY', '私密浮窗']],
}

export default function GoLiveDialog() {
  const open = useOsStore((s) => s.goLiveOpen)
  const close = useOsStore((s) => s.closeGoLive)
  const initialGoal = useOsStore((s) => s.goLiveGoalId)
  if (!open) return null
  return <GoLiveInner initialGoal={initialGoal} close={close} />
}

function GoLiveInner({ initialGoal, close }: { initialGoal: string | null; close: () => void }) {
  const setLive = useOsStore((s) => s.setLive)
  const goals = useAsync(() => productApi.goals('ACTIVE'), [])
  const [goalId, setGoalId] = useState(initialGoal ?? '')
  const [overrides, setOverrides] = useState<Record<string, string>>({})
  const [pre, setPre] = useState<Preflight | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!goalId && goals.data?.items.length === 1) setGoalId(goals.data.items[0].id)
  }, [goalId, goals.data])

  useEffect(() => {
    if (!goalId) { setPre(null); return }
    let alive = true
    setError(null)
    productApi.preflight(goalId, overrides).then((p) => alive && setPre(p)).catch((e) => alive && setError(e instanceof Error ? e.message : '加载失败'))
    return () => { alive = false }
  }, [goalId, overrides])

  const start = async () => {
    if (!goalId) return
    setBusy(true)
    try {
      const res = await productApi.liveStart(goalId, overrides)
      const title = pre?.goal.title ?? ''
      setLive({ sessionId: res.session_id, goalId, goalTitle: title, startedAt: Date.now() })
      setLiveContextLabel(title.split(' · ')[0] ?? title)
      close()
      navigate(paths.live(res.session_id))
    } catch (e) {
      setError(e instanceof Error ? e.message : '上场失败')
    } finally {
      setBusy(false)
    }
  }

  const withoutGoal = () => {
    setLive(null)
    setLiveContextLabel('')
    close()
    navigate(paths.live())
  }

  const byKey = Object.fromEntries((pre?.items ?? []).map((i) => [i.key, i]))
  const blockers = pre ? (pre.blockers.length ? pre.blockers : pre.items.filter((item) => !item.ok)) : []
  const readyCount = pre?.items.filter((item) => item.ok).length ?? 0
  const overrideCount = Object.keys(overrides).length
  const hasBlockers = blockers.length > 0
  const primaryContentKeys = ['goal', 'resume', 'skill_cards', 'stories']
  const secondaryContentKeys = ['knowledge', 'materials', 'quick_notes']
  const deviceKeys = ['audio', 'stt', 'screen_context']
  const overrideKeys = ['answer_language', 'whisper_language', 'ai_policy_mode', 'human_assistance_policy', 'share_privacy_mode']
  const detailKeys = ['language', 'technical_term_policy', 'active_model']

  return (
    <Dialog title="上场前检查（Preflight）" onClose={close} labelledBy="golive-title" extraWide>
      <div className="space-y-4" data-testid="preflight">
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <Field label="这一场属于哪个求职目标？">
            <select className={inputCls} value={goalId} onChange={(e) => { setGoalId(e.target.value); setOverrides({}) }}>
              <option value="">选择目标</option>
              {(goals.data?.items ?? []).map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}
            </select>
          </Field>
          {pre ? <span className="pb-1 text-[11px] text-text-muted">Preflight 只影响这一场，不会改写 Goal 默认值。</span> : null}
        </div>

        {error ? <ErrorState message={error} /> : null}
        {goalId && !pre && !error ? <Loading label="正在准备本场内容…" /> : null}

        {pre ? (
          <>
            <section aria-label="本场摘要" className="grid gap-3 border-y border-bg-tertiary/70 py-3 sm:grid-cols-[1fr_auto_auto_auto] sm:items-center">
              <div className="min-w-0">
                <p className="text-[10px] font-semibold tracking-[0.14em] text-text-muted">THIS SESSION</p>
                <h3 className="mt-0.5 truncate text-base font-semibold text-text-primary">{pre.goal.title}</h3>
                <p className="mt-0.5 text-[11px] text-text-muted">确认本场带入内容、设备状态与 session-only 覆盖，然后再开始。</p>
              </div>
              <div className="text-left sm:text-right">
                <p className="text-lg font-semibold tabular-nums text-text-primary">{readyCount}</p>
                <p className="text-[10px] text-text-muted">已就绪</p>
              </div>
              <div className="text-left sm:text-right">
                <p className={`text-lg font-semibold tabular-nums ${hasBlockers ? 'text-status-risk' : 'text-status-direct'}`}>{blockers.length}</p>
                <p className="text-[10px] text-text-muted">阻塞项</p>
              </div>
              <div className="text-left sm:text-right">
                <p className="text-lg font-semibold tabular-nums text-text-primary">{overrideCount}</p>
                <p className="text-[10px] text-text-muted">本场覆盖</p>
              </div>
            </section>

            {hasBlockers ? (
              <section aria-labelledby="preflight-blockers-heading" className="border-l-2 border-status-risk/45 bg-status-risk/[0.035] px-4 py-2.5">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h3 id="preflight-blockers-heading" className="text-sm font-semibold text-text-primary">开始前需要处理</h3>
                    <p className="mt-0.5 text-[11px] text-text-secondary">这些项目会影响这场会话，处理后再开始，避免面试中途才发现输入不可用。</p>
                  </div>
                  <SecondaryButton onClick={() => { close(); navigate(paths.settings('speech')) }}>打开语音与音频设置</SecondaryButton>
                </div>
                <ul className="mt-2 divide-y divide-status-risk/15">
                  {blockers.map((item) => (
                    <li key={item.key} className="py-2">
                      <div className="flex items-start justify-between gap-3">
                        <span className="text-xs font-medium text-text-primary">{item.label}</span>
                        <span className="text-[10px] text-status-risk">{String(item.value)}</span>
                      </div>
                      <p className="mt-0.5 text-[11px] text-text-secondary">{item.hint || '当前状态未通过本场检查。'}</p>
                    </li>
                  ))}
                </ul>
              </section>
            ) : (
              <p role="status" className="border-l-2 border-status-direct/40 pl-3 text-xs text-text-secondary">
                本场没有阻塞项。开始后才会进入正式会话。
              </p>
            )}

            <div className="grid gap-8 lg:grid-cols-[minmax(0,1.15fr)_minmax(300px,0.78fr)]">
              <div className="min-w-0 space-y-5">
                <section aria-labelledby="preflight-content-heading">
                  <div className="flex items-end justify-between gap-3">
                    <div>
                      <h3 id="preflight-content-heading" className="text-sm font-semibold text-text-primary">本场带入内容</h3>
                      <p className="mt-0.5 text-[11px] text-text-muted">这些内容会在开始时被冻结为本场上下文。</p>
                    </div>
                  </div>
                  <ul className="mt-2 divide-y divide-bg-tertiary/70 border-y border-bg-tertiary/70">
                    {primaryContentKeys.filter((key) => byKey[key]).map((key) => {
                      const item = byKey[key]
                      return (
                        <li key={key} className="grid grid-cols-[92px_minmax(0,1fr)_auto] items-center gap-3 py-2.5 text-xs">
                          <span className="text-text-muted">{item.label}</span>
                          <span className="min-w-0 truncate font-medium text-text-primary">{String(item.value)}</span>
                          <span className="text-[10px] text-text-muted">{item.origin_label}</span>
                          {item.hint ? <span className={`col-start-2 col-span-2 text-[10px] ${item.ok ? 'text-text-muted' : 'text-status-risk'}`}>{item.hint}</span> : null}
                        </li>
                      )
                    })}
                  </ul>
                  <details className="mt-2 border-b border-bg-tertiary/70 pb-2 text-xs">
                    <summary className="cursor-pointer text-text-secondary">其他本场上下文</summary>
                    <ul className="mt-2 divide-y divide-bg-tertiary/60 border-t border-bg-tertiary/60">
                      {secondaryContentKeys.filter((key) => byKey[key]).map((key) => {
                        const item = byKey[key]
                        return (
                          <li key={key} className="grid grid-cols-[92px_minmax(0,1fr)_auto] items-center gap-3 py-2 text-xs">
                            <span className="text-text-muted">{item.label}</span>
                            <span className="min-w-0 truncate font-medium text-text-primary">{String(item.value)}</span>
                            <span className="text-[10px] text-text-muted">{item.origin_label}</span>
                            {item.hint ? <span className={`col-start-2 col-span-2 text-[10px] ${item.ok ? 'text-text-muted' : 'text-status-risk'}`}>{item.hint}</span> : null}
                          </li>
                        )
                      })}
                    </ul>
                  </details>
                </section>

                <section aria-labelledby="preflight-device-heading">
                  <div className="flex flex-wrap items-end justify-between gap-2">
                    <div>
                      <h3 id="preflight-device-heading" className="text-sm font-semibold text-text-primary">这台电脑</h3>
                      <p className="mt-0.5 text-[11px] text-text-muted">这里只确认本场真正依赖的输入是否可用。</p>
                    </div>
                    <button type="button" className="text-[11px] text-accent-blue underline underline-offset-2" onClick={() => { close(); navigate(paths.settings('speech')) }}>检测麦克风与系统音频</button>
                  </div>
                  <ul className="mt-2 grid gap-2 sm:grid-cols-3">
                    {deviceKeys.filter((key) => byKey[key]).map((key) => {
                      const item = byKey[key]
                      return (
                        <li key={key} className="border-t border-bg-tertiary/70 pt-2">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-medium text-text-primary">{item.label}</span>
                            <span className={`text-[10px] ${item.ok ? 'text-status-direct' : 'text-status-risk'}`}>{item.ok ? '就绪' : '需要处理'}</span>
                          </div>
                          <p className="mt-0.5 truncate text-[10px] text-text-muted">{String(item.value)}</p>
                        </li>
                      )
                    })}
                  </ul>
                </section>
              </div>

              <aside className="min-w-0 lg:border-l lg:border-bg-tertiary/70 lg:pl-7">
                <h3 className="text-sm font-semibold text-text-primary">本场覆盖</h3>
                <p className="mt-0.5 text-[11px] leading-5 text-text-muted">只在这一场生效；不改 Goal，也不改全局设置。</p>

                <div className="mt-3 grid gap-x-5 border-y border-bg-tertiary/70 sm:grid-cols-2">
                  {overrideKeys.filter((key) => byKey[key]).map((key) => {
                    const item = byKey[key]
                    const opts = OVERRIDABLE[key]
                    return (
                      <label key={key} className="border-b border-bg-tertiary/60 py-2.5 text-xs">
                        <span className="mb-1 flex items-center justify-between gap-2">
                          <span className="font-medium text-text-secondary">{item.label}</span>
                          <span className="text-[10px] text-text-muted">{item.origin_label}</span>
                        </span>
                        <span>
                          {opts ? (
                            <select aria-label={`${item.label}（本场）`} className="w-full rounded-lg border border-bg-hover bg-bg-primary px-2 py-1.5 text-xs text-text-primary" value={String(item.value)}
                              onChange={(e) => setOverrides((current) => ({ ...current, [key]: e.target.value }))}>
                              {opts.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                            </select>
                          ) : <span className="text-text-primary">{String(item.value)}</span>}
                        </span>
                      </label>
                    )
                  })}
                </div>

                {byKey.human_assistance_policy?.value === 'HUMAN_ALLOWED' ? (
                  <p className="mt-3 text-[11px] leading-5 text-text-secondary">真人教练建议会单独标为「教练」，不会被当作你的个人证据。</p>
                ) : null}

                <details className="mt-4 border-t border-bg-tertiary/70 pt-3 text-xs">
                  <summary className="cursor-pointer text-text-secondary">查看模型与完整来源</summary>
                  <div className="mt-2 space-y-2">
                    {detailKeys.filter((key) => byKey[key]).map((key) => {
                      const item = byKey[key]
                      return (
                        <div key={key} className="flex items-start justify-between gap-3">
                          <span className="text-text-muted">{item.label}</span>
                          <span className="text-right text-text-primary">{String(item.value)} <span className="block text-[10px] text-text-muted">{item.origin_label}</span></span>
                        </div>
                      )
                    })}
                  </div>
                </details>

                <p className="mt-4 text-[10px] leading-4 text-text-muted">{pre.share_privacy_note}</p>
              </aside>
            </div>
          </>
        ) : null}

        <div className="sticky bottom-0 z-10 -mx-4 -mb-4 mt-0 flex flex-wrap justify-between gap-2 border-t border-bg-tertiary/70 bg-bg-primary/95 px-4 pb-4 pt-3 backdrop-blur">
          <SecondaryButton onClick={withoutGoal}>不选目标，直接进入</SecondaryButton>
          <div className="flex gap-2">
            <SecondaryButton onClick={close}>取消</SecondaryButton>
            <PrimaryButton testId="preflight-start" disabled={!goalId || !pre || busy || hasBlockers} onClick={() => void start()}>
              {busy ? '冻结本场内容…' : hasBlockers ? '先处理阻塞项' : '开始上场'}
            </PrimaryButton>
          </div>
        </div>
      </div>
    </Dialog>
  )
}
