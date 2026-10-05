/**
 * Reflection 3.0 (canonical §18). First screen: Next Step · Pinned moments ·
 * What went well · What to improve · Fact checks · Story opportunities.
 * Turn timeline is the second layer. Every action writes back for real.
 */
import { lazy, Suspense, useState } from 'react'
import { Pin } from 'lucide-react'
import { navigate, paths } from '@/lib/router'
import { productApi, type Reflection, type ReflectionFinding } from '@/lib/productApi'
import { ActionMenu, EmptyState, ErrorState, Loading, Page, PageHeader, PrimaryButton, SecondaryButton, Section, StatusBadge, useAsync } from './ui'

const ReviewSessionDetail = lazy(() => import('@/components/review/ReviewSessionDetail'))

const ACTION_LABEL: Record<string, string> = {
  PRACTICE_THIS: '练这个', SET_NEXT_FOCUS: '设为下一步重点', CONFIRM_FACT: '确认事实', MARK_MISTAKE: '标记口误',
  ADD_SOURCE: '补来源', CREATE_STORY: '整理成故事', ADD_QUICK_NOTE: '记成速记', DONT_REMEMBER: '不记得了',
}

function Quote({ text }: { text: string }) {
  if (!text) return <p className="text-[11px] text-text-muted">（没有采集到你的原话：候选人语音识别可能未开启）</p>
  return <blockquote className="mt-1 border-l-2 border-bg-hover pl-2 text-xs text-text-secondary">你说的：“{text}”</blockquote>
}

export default function ReflectionPage({ kind, sessionRef }: { kind: string; sessionRef: string }) {
  const { data, error, loading, reload } = useAsync(() => productApi.reflection(kind, sessionRef), [kind, sessionRef])
  const [done, setDone] = useState<Record<string, string>>({})
  const [feedbackSent, setFeedbackSent] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)
  const [sourceFor, setSourceFor] = useState<{ id: string; text: string } | null>(null)

  if (loading && !data) return <Page><Loading /></Page>
  if (error) return <Page><ErrorState message={error} onRetry={reload} extra={<SecondaryButton onClick={() => navigate(paths.history())}>返回历史</SecondaryButton>} /></Page>
  if (!data) return null
  const fs = data.first_screen

  const act = async (action: string, finding: Record<string, unknown>, payload: Record<string, unknown> = {}) => {
    try {
      const res = await productApi.reflectionAction(data.session_kind, data.session_ref, { action, finding, goal_id: data.goal_id, payload })
      setDone((d) => ({ ...d, [`${String(finding.id ?? '')}:${action}`]: '已完成' }))
      if (action === 'PRACTICE_THIS' && data.goal_id) {
        const defaults = res.practice_defaults as { round?: string; focus?: { id?: string } } | undefined
        navigate(paths.practice(undefined, { goal: data.goal_id, round: defaults?.round ?? '', focus: defaults?.focus?.id ?? '' }))
      }
    } catch (e) {
      setDone((d) => ({ ...d, [`${String(finding.id ?? '')}:${action}`]: e instanceof Error ? e.message : '失败' }))
    }
  }
  const status = (f: { id?: string }, action: string) => done[`${f.id ?? ''}:${action}`]

  return (
    <Page testId="reflection-page" wide>
      <PageHeader title={data.title} eyebrow={data.session_kind === 'PRACTICE' ? '练习复盘' : '面试复盘'}
        actions={
          <div className="flex items-center gap-2">
            {data.goal_id ? <SecondaryButton onClick={() => navigate(paths.goal(data.goal_id!))}>回到目标</SecondaryButton> : null}
            <ActionMenu label="复盘操作" actions={[
              {
                key: 'export-session',
                label: '导出场次',
                onSelect: () => void productApi.exportData({ kind: 'session', session_kind: data.session_kind, session_ref: data.session_ref })
                  .then((r) => window.alert(`已导出到 ${r.path}`)),
              },
              {
                key: 'export-reflection',
                label: '导出复盘',
                onSelect: () => void productApi.exportData({ kind: 'reflection', session_kind: data.session_kind, session_ref: data.session_ref })
                  .then((r) => window.alert(`已导出到 ${r.path}`)),
              },
              {
                key: 'delete-session',
                label: '删除这场记录',
                danger: true,
                onSelect: () => {
                  if (!window.confirm('删除这场记录及其复盘关联？这个操作不能撤销。')) return
                  void productApi.deleteSession(data.session_kind, data.session_ref).then(() => navigate(paths.history()))
                },
              },
            ]} />
          </div>
        } />

      <Section title="下一步">
        {fs.next_step ? (
          <div className="rounded-2xl border border-accent-blue/30 bg-accent-blue/5 p-3">
            <p className="text-sm font-semibold text-text-primary">{fs.next_step.title}</p>
            <p className="text-xs text-text-secondary">{fs.next_step.reason}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {data.goal_id ? (
                <>
                  <PrimaryButton testId="reflection-practice-next" onClick={() => void act('PRACTICE_THIS', { ...fs.next_step!, id: fs.next_step!.finding_id ?? fs.next_step!.pin_id })}>练这个</PrimaryButton>
                  <SecondaryButton onClick={() => void act('SET_NEXT_FOCUS', { ...fs.next_step!, id: fs.next_step!.finding_id ?? fs.next_step!.pin_id })}>
                    {status({ id: fs.next_step.finding_id ?? fs.next_step.pin_id }, 'SET_NEXT_FOCUS') ?? '设为下一步重点'}
                  </SecondaryButton>
                </>
              ) : <LinkGoal reviewId={data.session_kind === 'REVIEW' ? Number(data.session_ref) : null} onLinked={reload} />}
            </div>
          </div>
        ) : <EmptyState title="这场没有明显需要改进的地方" />}
      </Section>

      <Section title={`你标记的时刻 · ${fs.pinned_moments.length}`}>
        {fs.pinned_moments.length ? (
          <ul className="space-y-1.5">
            {fs.pinned_moments.map((p) => (
              <li key={p.id} className="rounded-xl border border-accent-amber/30 bg-accent-amber/5 px-3 py-2">
                <div className="flex flex-wrap items-center gap-2"><Pin className="h-3.5 w-3.5 text-accent-amber" aria-hidden /><StatusBadge tone="warn">{p.tag_label ?? p.tag}</StatusBadge></div>
                {p.question ? <p className="mt-1 text-sm text-text-primary">{p.question}</p> : null}
                {p.note ? <p className="text-xs text-text-secondary">备注：{p.note}</p> : null}
                {data.goal_id ? <div className="mt-1.5"><SecondaryButton onClick={() => void act('SET_NEXT_FOCUS', { id: p.id, pin_id: p.id, kind: 'USER_PIN' })}>{status({ id: p.id }, 'SET_NEXT_FOCUS') ?? '设为下一步重点'}</SecondaryButton></div> : null}
              </li>
            ))}
          </ul>
        ) : <p className="text-xs text-text-muted">这场没有标记。下次在练习或上场中按 Ctrl+P 标记重要时刻。</p>}
      </Section>

      <div className="grid gap-x-6 lg:grid-cols-2">
        <Section title="做得好">
          {fs.went_well.length ? (
            <ul className="space-y-2">{fs.went_well.map((w, i) => <li key={i} className="text-xs"><span className="font-medium text-status-direct">{w.dimension_label}</span><Quote text={w.actual_speech} /></li>)}</ul>
          ) : <p className="text-xs text-text-muted">暂无。</p>}
        </Section>
        <Section title="需要改进">
          {fs.to_improve.length ? (
            <ul className="space-y-2">{fs.to_improve.map((f) => <FindingRow key={f.id} f={f} goalLinked={!!data.goal_id} act={act} status={status} />)}</ul>
          ) : <p className="text-xs text-text-muted">暂无。</p>}
        </Section>
        <Section title={`事实核对 · ${fs.fact_checks.length}`}>
          {fs.fact_checks.length ? (
            <ul className="space-y-2">
              {fs.fact_checks.map((f) => (
                <li key={f.id} className="rounded-xl border border-bg-hover/50 px-3 py-2">
                  <p className="text-xs text-text-primary">{f.finding}</p>
                  <Quote text={f.actual_speech} />
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {(['CONFIRM_FACT', 'MARK_MISTAKE', 'DONT_REMEMBER'] as const).map((a) => (
                      <SecondaryButton key={a} onClick={() => void act(a, f as unknown as Record<string, unknown>)}>{status(f, a) ?? ACTION_LABEL[a]}</SecondaryButton>
                    ))}
                    {f.claim_id ? (
                      <SecondaryButton onClick={() => setSourceFor(sourceFor?.id === f.id ? null : { id: f.id, text: '' })}>
                        {status(f, 'ADD_SOURCE') ?? '补来源'}
                      </SecondaryButton>
                    ) : null}
                  </div>
                  {f.claim_id && sourceFor?.id === f.id ? (
                    <div className="mt-2 rounded-lg border border-bg-hover/60 bg-bg-tertiary/20 p-2">
                      <label className="text-[11px] font-medium text-text-secondary" htmlFor={`reflection-source-${f.id}`}>粘贴能支持这条说法的原始来源</label>
                      <textarea id={`reflection-source-${f.id}`} value={sourceFor.text}
                        onChange={(e) => setSourceFor({ id: f.id, text: e.target.value })}
                        placeholder="例如：设计文档、周报、PR 描述中的原文。成竹只把你提供的内容记为 supporting evidence。"
                        className="mt-1 min-h-[64px] w-full rounded-lg border border-bg-hover bg-bg-primary px-2 py-1.5 text-xs text-text-primary" />
                      <div className="mt-1.5 flex gap-2">
                        <PrimaryButton disabled={!sourceFor.text.trim()} onClick={() => void act('ADD_SOURCE', f as unknown as Record<string, unknown>, { source_text: sourceFor.text })}>
                          保存来源
                        </PrimaryButton>
                        <SecondaryButton onClick={() => setSourceFor(null)}>取消</SecondaryButton>
                      </div>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : <p className="text-xs text-text-muted">没有需要核对的说法。</p>}
        </Section>
        <Section title="故事机会">
          {fs.story_opportunities.length ? (
            <ul className="space-y-2">
              {fs.story_opportunities.map((s) => (
                <li key={s.id} className="rounded-xl border border-bg-hover/50 px-3 py-2">
                  <p className="text-xs text-text-primary">{s.question}</p>
                  <Quote text={s.actual_speech} />
                  <div className="mt-1.5"><SecondaryButton onClick={() => void act('CREATE_STORY', s as unknown as Record<string, unknown>)}>{status(s, 'CREATE_STORY') ?? '整理成故事草稿'}</SecondaryButton></div>
                </li>
              ))}
            </ul>
          ) : <p className="text-xs text-text-muted">暂无。</p>}
        </Section>
      </div>

      {data.delivery.length ? (
        <Section title="表达（本地分析）">
          <ul className="list-disc pl-4 text-xs text-text-secondary">{data.delivery.map((d) => <li key={d}>{d}</li>)}</ul>
        </Section>
      ) : null}

      {data.ask_cue_feedback && !feedbackSent ? (
        <Section title="这场 Fast Cue 有帮助吗？">
          <div className="flex gap-2">
            {([['YES', '有'], ['SOMEWHAT', '一般'], ['NO', '没有']] as const).map(([k, l]) => (
              <SecondaryButton key={k} onClick={() => void productApi.reflectionFeedback(data.session_kind, data.session_ref, k).then(() => setFeedbackSent(true))}>{l}</SecondaryButton>
            ))}
          </div>
        </Section>
      ) : null}

      <Timeline data={data} />
      {data.session_kind === 'REVIEW' ? (
        <Section title="完整复盘（逐题分析、AI 参考答案）" action={<SecondaryButton onClick={() => setDetailOpen((v) => !v)}>{detailOpen ? '收起' : '展开'}</SecondaryButton>}>
          {detailOpen ? <div className="rounded-2xl border border-bg-hover/50 overflow-hidden"><Suspense fallback={<Loading />}><ReviewSessionDetail sessionId={Number(data.session_ref)} onBack={() => setDetailOpen(false)} /></Suspense></div> : null}
        </Section>
      ) : null}
    </Page>
  )
}

function FindingRow({ f, goalLinked, act, status }: {
  f: ReflectionFinding
  goalLinked: boolean
  act: (a: string, f: Record<string, unknown>, p?: Record<string, unknown>) => Promise<void>
  status: (f: { id?: string }, a: string) => string | undefined
}) {
  const finding = f as unknown as Record<string, unknown>
  return (
    <li className="rounded-xl border border-bg-hover/50 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge tone="warn">{f.kind_label ?? f.kind}</StatusBadge>
        {f.occurrences && f.occurrences > 1 ? <span className="text-[11px] text-text-muted">出现 {f.occurrences} 次</span> : null}
      </div>
      <p className="mt-1 text-xs text-text-primary">{f.finding}</p>
      {f.question ? <p className="text-[11px] text-text-muted">问题：{f.question}</p> : null}
      <Quote text={f.actual_speech} />
      {f.action_hint ? <p className="mt-0.5 text-[11px] text-text-secondary">建议：{f.action_hint}</p> : null}
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
        {goalLinked ? <SecondaryButton onClick={() => void act('PRACTICE_THIS', finding)}>{status(f, 'PRACTICE_THIS') ?? '练这个'}</SecondaryButton> : null}
        <ActionMenu label="更多复盘操作" actions={[
          ...(goalLinked ? [{ key: 'focus', label: '设为下一步重点', onSelect: () => void act('SET_NEXT_FOCUS', finding) }] : []),
          { key: 'note', label: '记成速记', onSelect: () => void act('ADD_QUICK_NOTE', finding) },
          ...(f.actual_speech ? [{ key: 'story', label: '整理成故事草稿', onSelect: () => void act('CREATE_STORY', finding) }] : []),
        ]} />
        {status(f, 'SET_NEXT_FOCUS') || status(f, 'ADD_QUICK_NOTE') || status(f, 'CREATE_STORY') ? (
          <span role="status" className="text-[11px] text-status-direct">{status(f, 'SET_NEXT_FOCUS') || status(f, 'ADD_QUICK_NOTE') || status(f, 'CREATE_STORY')}</span>
        ) : null}
      </div>
    </li>
  )
}

function Timeline({ data }: { data: Reflection }) {
  const [open, setOpen] = useState(false)
  return (
    <Section title={`逐题记录 · ${data.timeline.length}`} action={<SecondaryButton onClick={() => setOpen((v) => !v)}>{open ? '收起' : '展开'}</SecondaryButton>}>
      {open ? (
        <ol className="space-y-2">
          {data.timeline.map((t) => (
            <li key={t.turn_id} className="rounded-xl border border-bg-hover/50 px-3 py-2">
              <p className="text-xs font-medium text-text-primary">Q{t.seq}. {t.question}</p>
              <Quote text={t.actual_speech} />
              {t.content.findings?.length ? <p className="mt-1 text-[11px] text-text-muted">{t.content.findings.map((f) => f.finding).join('；')}</p> : null}
            </li>
          ))}
        </ol>
      ) : null}
    </Section>
  )
}

function LinkGoal({ reviewId, onLinked }: { reviewId: number | null; onLinked: () => void }) {
  const goals = useAsync(() => productApi.goals('ACTIVE'), [])
  const [goalId, setGoalId] = useState('')
  if (!reviewId) return <p className="text-xs text-text-muted">这场练习没有关联目标。</p>
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="text-text-secondary">关联到求职目标后可以设为下一步重点：</span>
      <select aria-label="选择求职目标" value={goalId} onChange={(e) => setGoalId(e.target.value)} className="rounded-lg border border-bg-hover bg-bg-primary px-2 py-1">
        <option value="">选择目标</option>
        {(goals.data?.items ?? []).map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}
      </select>
      <PrimaryButton disabled={!goalId} onClick={() => void productApi.linkHistoryGoal(reviewId, goalId).then(onLinked)}>关联</PrimaryButton>
    </div>
  )
}
