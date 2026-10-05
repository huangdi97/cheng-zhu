/**
 * Goal Room → 准备: Next Focus · Gap Map · Attack Surface · Question Graph ·
 * Skills / Stories · Materials · InterviewPack Preview.
 * Everything here is preparation, never a personal fact.
 */
import { lazy, Suspense, useMemo, useState } from 'react'
import { navigate, paths } from '@/lib/router'
import { productApi, type GoalDetail, type QuestionNode } from '@/lib/productApi'
import { NextFocusList } from './NextFocusList'
import QuickNotesPanel from './QuickNotesPanel'
import { MaterialStateBadge } from './MaterialStateBadge'
import { EmptyState, ErrorState, Field, inputCls, Loading, PrimaryButton, SecondaryButton, Section, StatusBadge, useAsync } from './ui'

const PrepSpace = lazy(() => import('@/components/PrepSpace'))

const GAP_STATUS: Record<string, { label: string; tone: 'risk' | 'warn' | 'info' | 'muted' }> = {
  GAP: { label: '缺证据', tone: 'risk' },
  KNOWLEDGE_MATCH: { label: '只能讲知识', tone: 'warn' },
  PARTIAL_MATCH: { label: '只有技能层面', tone: 'info' },
  REVIEW_WEAKNESS: { label: '复盘薄弱点', tone: 'warn' },
  REPEATED_TOPIC: { label: '反复被问', tone: 'info' },
}

function QuestionTree({ nodes }: { nodes: QuestionNode[] }) {
  const children = useMemo(() => {
    const map = new Map<string, QuestionNode[]>()
    for (const n of nodes) {
      const list = map.get(n.parent_id) ?? []
      list.push(n)
      map.set(n.parent_id, list)
    }
    return map
  }, [nodes])
  const render = (parent: string, depth: number): React.ReactNode => {
    const list = children.get(parent) ?? []
    if (!list.length) return null
    return (
      <ul className={depth ? 'ml-4 border-l border-bg-hover/60 pl-3 space-y-1' : 'space-y-2'} role={depth ? 'group' : 'tree'} aria-label={depth ? undefined : '可能追问'}>
        {list.map((n) => (
          <li key={n.id} role="treeitem" aria-expanded={children.has(n.id) ? true : undefined} className="text-xs">
            <span className={depth ? 'text-text-secondary' : 'font-medium text-text-primary'}>{n.text}</span>
            {render(n.id, depth + 1)}
          </li>
        ))}
      </ul>
    )
  }
  return <>{render('', 0)}</>
}

export default function GoalPrepare({ goal, reload }: { goal: GoalDetail; reload: () => void }) {
  const { data, error, loading, reload: reloadPrep } = useAsync(() => productApi.prepare(goal.id), [goal.id, goal.updated_at])
  const mats = useAsync(() => productApi.materials('PROJECT'), [])
  const [jd, setJd] = useState(goal.jd)
  const [skillsOpen, setSkillsOpen] = useState(false)
  const [noteIds, setNoteIds] = useState<string[]>(goal.selected_quick_note_ids)

  if (loading && !data) return <Loading />
  if (error) return <ErrorState message={error} onRetry={reloadPrep} />
  if (!data) return null

  const toggleMaterial = (id: string) => {
    const set = new Set(goal.selected_material_ids)
    if (set.has(id)) set.delete(id)
    else set.add(id)
    void productApi.patchGoal(goal.id, { selected_material_ids: Array.from(set) }).then(() => { reload(); void reloadPrep() })
  }

  return (
    <div className="grid gap-x-6 lg:grid-cols-[1.3fr_1fr]">
      <div>
        <Section title="下一步"><NextFocusList goalId={goal.id} items={data.next_focus} onChanged={reload} /></Section>
        {!data.has_jd ? (
          <Section title="补充 JD">
            <Field label="JD 只属于这个目标；补充后会生成准备缺口和可能追问。">
              <textarea className={`${inputCls} min-h-[120px]`} value={jd} onChange={(e) => setJd(e.target.value)} />
            </Field>
            <div className="mt-2"><PrimaryButton disabled={!jd.trim()} onClick={() => void productApi.patchGoal(goal.id, { jd }).then(reload)}>保存 JD</PrimaryButton></div>
          </Section>
        ) : null}
        <Section title="准备缺口">
          {data.gap_map.length ? (
            <ul className="space-y-1.5">
              {data.gap_map.map((g) => {
                const meta = GAP_STATUS[g.status] ?? { label: g.status, tone: 'muted' as const }
                return (
                  <li key={g.topic} className="rounded-xl border border-bg-hover/50 px-3 py-2">
                    <div className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium text-text-primary">{g.topic}</span><StatusBadge tone={meta.tone}>{meta.label}</StatusBadge></div>
                    <p className="text-[11px] text-text-muted">{g.reason}</p>
                  </li>
                )
              })}
            </ul>
          ) : <EmptyState title={data.has_jd ? '没有发现明显缺口' : '补充 JD 后显示'} />}
        </Section>
        <Section title="可能被深挖">
          {data.attack_surface.length ? (
            <ul className="space-y-2">
              {data.attack_surface.map((a) => (
                <li key={a.claim_id} className="rounded-xl border border-bg-hover/50 px-3 py-2">
                  <p className="text-sm text-text-primary">{a.text}</p>
                  {a.risks.length ? <p className="text-[11px] text-status-inferred">{a.risks.join(' · ')}</p> : null}
                  {a.probes.length ? <ul className="mt-1 list-disc pl-4 text-[11px] text-text-secondary">{a.probes.map((p) => <li key={p}>{p}</li>)}</ul> : null}
                </li>
              ))}
            </ul>
          ) : <EmptyState title="导入简历并确认事实后显示" action={<SecondaryButton onClick={() => navigate(paths.me('resume'))}>去导入简历</SecondaryButton>} />}
        </Section>
        <Section title="可能追问">
          {data.question_graph.length ? <QuestionTree nodes={data.question_graph} /> : <EmptyState title="暂无问题图" />}
        </Section>
      </div>
      <div>
        <Section title="能力与故事">
          <div className="flex flex-wrap gap-1.5">
            {data.stories.coverage.categories.map((c) => (
              <StatusBadge key={c.key} tone={c.story_ids.length ? 'ok' : 'muted'}>{c.label}</StatusBadge>
            ))}
          </div>
          {data.stories.coverage.missing.length ? (
            <p className="mt-2 text-xs text-text-secondary">还没有「{data.stories.coverage.missing[0].label}」故事。
              <button type="button" className="ml-1 text-accent-blue underline" onClick={() => navigate(paths.me('stories'))}>开始 5 分钟故事整理</button></p>
          ) : null}
          {goal.legacy_prep_space_id ? (
            <div className="mt-2">
              <SecondaryButton onClick={() => setSkillsOpen((v) => !v)}>{skillsOpen ? '收起技能卡与预测题' : '技能卡与预测题'}</SecondaryButton>
              {skillsOpen ? (
                <div className="mt-2 rounded-2xl border border-bg-hover/50 overflow-hidden flex flex-col max-h-[640px]">
                  <Suspense fallback={<Loading />}><PrepSpace initialSpaceId={goal.legacy_prep_space_id} embedded /></Suspense>
                </div>
              ) : null}
            </div>
          ) : null}
        </Section>
        <Section title="项目资料" action={<SecondaryButton onClick={() => navigate(paths.library('materials'))}>资料库</SecondaryButton>}>
          {mats.data?.items.length ? (
            <ul className="space-y-1">
              {mats.data.items.map((m) => (
                <li key={m.id} className="flex items-center gap-2 text-xs">
                  <input type="checkbox" id={`mat-${m.id}`} checked={goal.selected_material_ids.includes(m.id)} onChange={() => toggleMaterial(m.id)}
                    disabled={m.lifecycle.state === 'FAILED' && !m.lifecycle.active_version} />
                  <label htmlFor={`mat-${m.id}`} className="min-w-0 flex-1 truncate text-text-primary">{m.title}</label>
                  <MaterialStateBadge state={m.lifecycle.state} />
                </li>
              ))}
            </ul>
          ) : <EmptyState title="还没有项目资料" action={<SecondaryButton onClick={() => navigate(paths.library('materials'))}>添加资料</SecondaryButton>} />}
        </Section>
        <Section title="速记（本场可用）">
          <QuickNotesPanel goalId={goal.id} context="goal" compact selectedIds={noteIds}
            onSelectionChange={(ids) => { setNoteIds(ids); void productApi.patchGoal(goal.id, { selected_quick_note_ids: ids }).then(() => void reloadPrep()) }} />
        </Section>
        <Section title="本场材料预览">
          <p className="text-[11px] text-text-muted">上场检查时会冻结这一场要用的内容。只有「就绪」的资料会进入；速记只是「你的提醒」，不是证据。</p>
          <ul className="mt-1.5 space-y-1 text-xs">
            <li>速记：{data.pack_preview.quick_notes.length ? data.pack_preview.quick_notes.map((n) => n.title || n.content.slice(0, 12)).join('、') : '未选择（默认带上置顶速记）'}</li>
            <li>资料：{data.pack_preview.materials.length ? data.pack_preview.materials.map((m) => m.title).join('、') : '未选择'}</li>
            {data.materials.skipped.length ? <li className="text-status-inferred">未就绪，不会进入：{data.materials.skipped.map((s) => s.title).join('、')}</li> : null}
          </ul>
        </Section>
      </div>
    </div>
  )
}
