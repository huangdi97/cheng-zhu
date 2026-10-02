/**
 * Practice 3.0 (canonical §10). Setup → adaptive session → report.
 * Content and Delivery feedback are shown side by side, never merged.
 */
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { Mic, Users } from 'lucide-react'
import { navigate, paths } from '@/lib/router'
import {
  productApi,
  type PanelState,
  type PracticeAnswerResult,
  type PracticeConfig,
  type PracticeFeedback,
  type PracticeOptions,
  type PracticeQuestion,
  type PracticeReport,
} from '@/lib/productApi'
import { useVoiceAnswer } from '@/hooks/useVoiceAnswer'
import { useOsStore } from '@/stores/osStore'
import { ErrorState, Field, inputCls, Loading, Page, PageHeader, PrimaryButton, SecondaryButton, Section, StatusBadge, useAsync } from './ui'

const CoachPanel = lazy(() => import('@/components/coach/CoachPanel'))

const MOVE_LABEL: Record<string, string> = {
  OPEN: '新问题', FOLLOW_UP: '追问', CHALLENGE: '质疑', CONSTRAINT_CHANGE: '条件变化', OWNERSHIP_PROBE: '追问你本人的贡献',
  QUANTIFY: '要数字', CLARIFY: '澄清', CONTRADICTION_PROBE: '前后对照', CLOSING: '收尾',
}
const DIMENSION_LABEL: Record<string, string> = {
  technical_correctness: '技术正确性', depth: '深度', trade_off: '取舍', ownership: 'Ownership', impact: '影响 / 结果',
  communication: '表达结构', evidence_discipline: '证据纪律', followup_resilience: '追问韧性',
}

function Chips({ label, options, value, onChange }: { label: string; options: Array<{ key: string; label: string }>; value: string; onChange: (v: string) => void }) {
  return (
    <fieldset>
      <legend className="text-xs font-medium text-text-secondary">{label}</legend>
      <div role="radiogroup" aria-label={label} className="mt-1 flex flex-wrap gap-1.5">
        {options.map((o) => (
          <button key={o.key} type="button" role="radio" aria-checked={value === o.key} onClick={() => onChange(o.key)}
            className={`rounded-full border px-3 py-1 text-xs ${value === o.key ? 'border-accent-blue/50 bg-container-primary text-container-on-primary font-semibold' : 'border-bg-hover text-text-secondary hover:text-text-primary'}`}>
            {o.label}
          </button>
        ))}
      </div>
    </fieldset>
  )
}

export default function PracticePage({ practiceId, query }: { practiceId?: string; query: Record<string, string> }) {
  if (practiceId) return <PracticeSession practiceId={practiceId} />
  return <PracticeSetup query={query} />
}

function PracticeSetup({ query }: { query: Record<string, string> }) {
  const goals = useAsync(() => productApi.goals('ACTIVE'), [])
  const [goalId, setGoalId] = useState(query.goal ?? '')
  const opts = useAsync<PracticeOptions>(() => productApi.practiceOptions(goalId), [goalId])
  const [cfg, setCfg] = useState<PracticeConfig>({
    round: query.round || 'TECHNICAL', personas: [], demeanor: 'NEUTRAL', difficulty: 'STANDARD',
    sources: ['GOAL_GRAPH', 'RECENT_WEAKNESS', 'ROLE_BANK'], questions: 5, language: 'zh', delivery_analytics: true,
  })
  const [panel, setPanel] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const defaults = opts.data?.defaults
  const focus = useMemo(() => (query.focus && defaults?.focus?.id === query.focus ? defaults.focus : defaults?.focus ?? null), [defaults, query.focus])

  // Next Focus drives the defaults (round / demeanor) unless the URL picked a round
  useEffect(() => {
    if (!defaults) return
    setCfg((c) => ({ ...c, round: query.round || defaults.round || c.round, demeanor: defaults.demeanor || c.demeanor, sources: defaults.sources?.length ? defaults.sources : c.sources }))
  }, [defaults, query.round])

  const set = <K extends keyof PracticeConfig>(k: K, v: PracticeConfig[K]) => setCfg((c) => ({ ...c, [k]: v }))
  const togglePersona = (key: string) => {
    const has = cfg.personas.includes(key)
    const next = has ? cfg.personas.filter((p) => p !== key) : [...cfg.personas, key].slice(0, 3)
    set('personas', next)
  }
  const toggleSource = (key: string) => set('sources', cfg.sources.includes(key) ? cfg.sources.filter((s) => s !== key) : [...cfg.sources, key])

  const start = async () => {
    setBusy(true)
    setError(null)
    try {
      const res = await productApi.startPractice({ ...cfg, goal_id: goalId || null, personas: panel ? cfg.personas : cfg.personas.slice(0, 1), focus })
      navigate(paths.practice(res.practice_id))
    } catch (e) {
      setError(e instanceof Error ? e.message : '开始失败')
    } finally {
      setBusy(false)
    }
  }

  if (opts.loading && !opts.data) return <Page><Loading /></Page>
  if (opts.error) return <Page><ErrorState message={opts.error} onRetry={opts.reload} /></Page>
  const o = opts.data!
  const panelInvalid = panel && (cfg.personas.length < 2 || cfg.personas.length > 3)
  return (
    <Page testId="practice-setup" wide>
      <PageHeader title="练习" subtitle="面试官会根据你的回答追问；回答前不显示参考答案。" />
      {focus ? (
        <div className="mb-3 rounded-2xl border border-accent-blue/30 bg-accent-blue/5 px-3 py-2 text-xs">
          <span className="font-semibold text-text-primary">本次聚焦：{focus.title}</span>
          <span className="block text-text-secondary">{focus.reason}</span>
        </div>
      ) : null}
      <div className="grid gap-x-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-4">
          <Field label="求职目标">
            <select className={inputCls} value={goalId} onChange={(e) => setGoalId(e.target.value)}>
              <option value="">不关联目标（用岗位题库）</option>
              {(goals.data?.items ?? []).map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}
            </select>
          </Field>
          <Chips label="轮次" options={o.rounds} value={cfg.round} onChange={(v) => set('round', v)} />
          <fieldset>
            <legend className="text-xs font-medium text-text-secondary">面试官</legend>
            <label className="mt-1 flex items-center gap-2 text-xs text-text-primary">
              <input type="checkbox" checked={panel} onChange={(e) => setPanel(e.target.checked)} />
              <Users className="h-3.5 w-3.5" aria-hidden /> 小组面（2–3 位面试官轮流提问）
            </label>
            <div className="mt-1.5 grid gap-1.5 sm:grid-cols-2">
              {o.personas.map((p) => {
                const checked = cfg.personas.includes(p.key)
                return (
                  <label key={p.key} className={`flex items-start gap-2 rounded-xl border px-2.5 py-2 text-xs ${checked ? 'border-accent-blue/50 bg-accent-blue/5' : 'border-bg-hover'}`}>
                    <input type={panel ? 'checkbox' : 'radio'} name="persona" checked={checked}
                      onChange={() => (panel ? togglePersona(p.key) : set('personas', [p.key]))} className="mt-0.5" />
                    <span><span className="font-medium text-text-primary">{p.label}</span><span className="block text-[11px] text-text-muted">{p.followup_style}</span></span>
                  </label>
                )
              })}
            </div>
            {panelInvalid ? <p className="mt-1 text-[11px] text-status-inferred">小组面需要选 2–3 位面试官。</p> : null}
          </fieldset>
          <Chips label="风格" options={o.demeanors} value={cfg.demeanor} onChange={(v) => set('demeanor', v)} />
          <Chips label="难度" options={o.difficulties} value={cfg.difficulty} onChange={(v) => set('difficulty', v)} />
        </div>
        <div className="space-y-4">
          <fieldset>
            <legend className="text-xs font-medium text-text-secondary">题目来源</legend>
            <div className="mt-1 space-y-1">
              {o.sources.map((s) => (
                <label key={s.key} className="flex items-center gap-2 text-xs text-text-primary">
                  <input type="checkbox" checked={cfg.sources.includes(s.key)} onChange={() => toggleSource(s.key)} /> {s.label}
                </label>
              ))}
            </div>
          </fieldset>
          <Field label={`题目数量：${cfg.questions}`}>
            <input type="range" min={1} max={12} value={cfg.questions} aria-label="题目数量" onChange={(e) => set('questions', Number(e.target.value))} className="w-full" />
          </Field>
          <Chips label="语言" options={[{ key: 'zh', label: '中文' }, { key: 'en', label: 'English' }]} value={cfg.language} onChange={(v) => set('language', v as 'zh' | 'en')} />
          <label className="flex items-center gap-2 text-xs text-text-primary">
            <input type="checkbox" checked={cfg.delivery_analytics !== false} onChange={(e) => set('delivery_analytics', e.target.checked)} />
            本地表达分析（语速、结论时间等，只在本机）
          </label>
          <label className="flex items-center gap-2 text-xs text-text-primary">
            <input type="checkbox" checked={!!cfg.human_coach} onChange={(e) => set('human_coach', e.target.checked)} />
            邀请真人教练一起练
          </label>
          {cfg.human_coach ? <Suspense fallback={<Loading />}><CoachPanel sessionKind="practice" /></Suspense> : null}
        </div>
      </div>
      {error ? <p role="alert" className="mt-3 text-xs text-status-risk">{error}</p> : null}
      <div className="mt-4 flex gap-2">
        <PrimaryButton testId="practice-start" onClick={() => void start()} disabled={busy || !cfg.sources.length || panelInvalid}>{busy ? '准备题目…' : '开始练习'}</PrimaryButton>
      </div>
    </Page>
  )
}

interface Turn {
  question: PracticeQuestion
  answer: string
  feedback: PracticeFeedback | null
}

function PracticeSession({ practiceId }: { practiceId: string }) {
  const setActivePractice = useOsStore((s) => s.setActivePractice)
  const [turns, setTurns] = useState<Turn[]>([])
  const [current, setCurrent] = useState<PracticeQuestion | null>(null)
  const [panel, setPanel] = useState<PanelState | null>(null)
  const [goalId, setGoalId] = useState<string | null>(null)
  const [report, setReport] = useState<PracticeReport | null>(null)
  const [answer, setAnswer] = useState('')
  const [durationMs, setDurationMs] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const voice = useVoiceAnswer()

  useEffect(() => {
    setActivePractice(practiceId, current?.question ?? '')
  }, [practiceId, current, setActivePractice])
  useEffect(() => () => setActivePractice(null), [setActivePractice])

  useEffect(() => {
    let alive = true
    setLoading(true)
    productApi.practice(practiceId).then((raw) => {
      if (!alive) return
      const data = raw as unknown as { status: string; goal_id: string | null; panel: PanelState; review_session_id: number | null; turns: Array<PracticeQuestion & { answer: string; content: PracticeFeedback['content']; delivery: PracticeFeedback['delivery'] }> }
      setGoalId(data.goal_id)
      setPanel(data.panel)
      const answered = data.turns.filter((t) => t.answer)
      setTurns(answered.map((t) => ({ question: t, answer: t.answer, feedback: { content: t.content, delivery: t.delivery && Object.keys(t.delivery).length ? t.delivery : null } })))
      const open = data.turns.find((t) => !t.answer)
      setCurrent(data.status === 'ACTIVE' ? open ?? null : null)
      if (data.status !== 'ACTIVE') {
        setReport({ practice_id: practiceId, review_session_id: data.review_session_id, goal_id: data.goal_id, turn_count: answered.length, went_well: [], to_improve: [], delivery: [] })
      }
    }).catch((e) => setError(e instanceof Error ? e.message : '加载失败')).finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [practiceId])

  const submit = async () => {
    if (!current || !answer.trim() || busy) return
    setBusy(true)
    setError(null)
    try {
      const res: PracticeAnswerResult = await productApi.answerPractice(practiceId, { answer: answer.trim(), duration_ms: durationMs })
      setTurns((t) => [...t, { question: current, answer: answer.trim(), feedback: res.feedback }])
      setAnswer('')
      setDurationMs(null)
      if (res.panel) setPanel(res.panel)
      if (res.done) {
        setCurrent(null)
        setReport(res.report ?? null)
      } else {
        setCurrent(res.next_question ?? null)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交失败')
    } finally {
      setBusy(false)
    }
  }

  const finish = async () => {
    setBusy(true)
    try {
      setReport(await productApi.finishPractice(practiceId))
      setCurrent(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '结束失败')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Page><Loading /></Page>
  const last = turns[turns.length - 1]
  return (
    <Page testId="practice-session" wide>
      <PageHeader title="练习中" subtitle={`已回答 ${turns.length} 题 · Ctrl+P 标记这一刻`}
        actions={!report ? <SecondaryButton onClick={() => void finish()} disabled={busy || !turns.length}>结束练习</SecondaryButton> : null} />
      {panel?.is_panel ? (
        <div className="mb-3 flex flex-wrap gap-1.5" aria-label="面试官">
          {panel.personas.map((p) => (
            <StatusBadge key={p.id} tone={p.id === panel.current_speaker ? 'info' : 'muted'} title={p.concern}>
              {p.label}{p.id === panel.current_speaker ? ' · 正在提问' : ''}
            </StatusBadge>
          ))}
        </div>
      ) : null}
      {error ? <ErrorState message={error} /> : null}

      {last?.feedback ? <FeedbackSplit feedback={last.feedback} /> : null}

      {current ? (
        <section aria-label="当前问题" className="mt-3 rounded-2xl border border-bg-hover/60 bg-bg-secondary/60 p-4">
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-muted">
            {current.persona_label ? <span className="font-semibold text-text-secondary">{current.persona_label}</span> : null}
            <StatusBadge tone={current.move === 'OPEN' ? 'muted' : 'warn'}>{MOVE_LABEL[current.move] ?? current.move}</StatusBadge>
          </div>
          <p className="mt-1.5 text-base font-medium text-text-primary" data-testid="practice-question">{current.question}</p>
          <textarea aria-label="你的回答" className={`${inputCls} mt-3 min-h-[120px]`} value={answer} placeholder="说出或写下你的回答…"
            onChange={(e) => setAnswer(e.target.value)}
            onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); void submit() } }} />
          {voice.recording ? <p role="status" className="mt-1 text-[11px] text-text-muted">{voice.liveText || voice.message}</p> : voice.message ? <p className="mt-1 text-[11px] text-text-muted">{voice.message}</p> : null}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <PrimaryButton testId="practice-submit" onClick={() => void submit()} disabled={busy || !answer.trim()}>{busy ? '分析中…' : '提交回答'}</PrimaryButton>
            <SecondaryButton disabled={voice.recording} onClick={() => void voice.record().then((r) => { if (r) { setAnswer(r.text); setDurationMs(r.durationMs) } })} icon={<Mic className="h-3.5 w-3.5" aria-hidden />}>
              {voice.recording ? '正在听…' : '语音回答'}
            </SecondaryButton>
            {voice.devices.length > 1 ? (
              <select aria-label="麦克风" className="rounded-lg border border-bg-hover bg-bg-primary px-2 py-1 text-xs" value={voice.deviceId} onChange={(e) => voice.setDeviceId(Number(e.target.value))}>
                {voice.devices.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            ) : null}
          </div>
        </section>
      ) : null}

      {report ? (
        <Section title="练习结束">
          {report.went_well.length ? <p className="text-xs text-text-secondary">做得好：{report.went_well.join('、')}</p> : null}
          {report.to_improve.length ? <p className="text-xs text-text-secondary">需要改进：{report.to_improve.join('、')}</p> : null}
          {report.delivery.map((d) => <p key={d} className="text-xs text-text-secondary">{d}</p>)}
          <div className="mt-3 flex flex-wrap gap-2">
            <PrimaryButton testId="practice-open-reflection" onClick={() => navigate(paths.reflection('PRACTICE', practiceId))}>查看复盘</PrimaryButton>
            <SecondaryButton onClick={() => navigate(paths.practice(undefined, goalId ? { goal: goalId } : {}))}>再练一次</SecondaryButton>
          </div>
        </Section>
      ) : null}

      {turns.length > 1 ? (
        <Section title="本场记录">
          <ol className="space-y-1.5">
            {turns.slice(0, -1).map((t) => (
              <li key={t.question.id} className="rounded-xl border border-bg-hover/50 px-3 py-2 text-xs">
                <span className="font-medium text-text-primary">{t.question.question}</span>
                <span className="block text-text-secondary">你：{t.answer.slice(0, 140)}{t.answer.length > 140 ? '…' : ''}</span>
              </li>
            ))}
          </ol>
        </Section>
      ) : null}
    </Page>
  )
}

/** Content vs Delivery — two separate panels, no combined score. */
export function FeedbackSplit({ feedback }: { feedback: PracticeFeedback }) {
  const findings = feedback.content.findings ?? []
  return (
    <div className="grid gap-3 md:grid-cols-2" aria-label="上一题反馈">
      <section aria-label="内容" className="rounded-2xl border border-bg-hover/60 p-3">
        <h2 className="text-xs font-semibold text-text-primary">内容</h2>
        {findings.length ? (
          <ul className="mt-1.5 space-y-2">
            {findings.slice(0, 3).map((f) => (
              <li key={f.signal} className="text-xs">
                <span className="font-medium text-text-primary">{DIMENSION_LABEL[f.dimension] ?? f.dimension}：</span>
                <span className="text-text-secondary">{f.finding}</span>
                {f.evidence_from_actual_speech ? <span className="block text-[11px] text-text-muted">你说的：“{f.evidence_from_actual_speech}”</span> : null}
                <span className="block text-[11px] text-accent-blue">下一步：{f.action}</span>
              </li>
            ))}
          </ul>
        ) : <p className="mt-1 text-xs text-text-secondary">这一题的内容维度都比较完整。</p>}
      </section>
      <section aria-label="表达" className="rounded-2xl border border-bg-hover/60 p-3">
        <h2 className="text-xs font-semibold text-text-primary">表达</h2>
        {feedback.delivery ? (
          <>
            <p className="mt-1 text-[11px] text-text-muted">
              时长 {String(feedback.delivery.metrics.answer_duration_s ?? '—')}s
              {feedback.delivery.metrics.timing_estimated ? '（按字数估算）' : ''}
              {feedback.delivery.metrics.time_to_conclusion_s != null ? ` · 结论在 ${String(feedback.delivery.metrics.time_to_conclusion_s)}s` : ''}
              {` · 填充词 ${String(feedback.delivery.metrics.fillers ?? 0)}`}
            </p>
            {feedback.delivery.advice.length ? (
              <ul className="mt-1 list-disc pl-4 text-xs text-text-secondary">{feedback.delivery.advice.map((a) => <li key={a}>{a}</li>)}</ul>
            ) : <p className="mt-1 text-xs text-text-secondary">节奏没有明显问题。</p>}
          </>
        ) : <p className="mt-1 text-xs text-text-muted">本地表达分析已关闭。</p>}
      </section>
    </div>
  )
}
