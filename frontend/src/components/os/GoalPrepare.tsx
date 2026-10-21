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
import { EmptyState, ErrorState, Field, inputCls, Loading, PrimaryButton, SecondaryButton, StatusBadge, useAsync } from './ui'

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

  const coveredStories = data.stories.coverage.categories.filter((item) => item.story_ids.length).length
  const storyTotal = data.stories.coverage.categories.length
  const storyGap = data.stories.coverage.missing[0] ?? null
  const readyMaterials = data.pack_preview.materials.length
  const selectedNotes = data.pack_preview.quick_notes.length

  return (
    <div data-testid="goal-prepare-workspace">
      {!data.has_jd ? (
        <section aria-labelledby="prepare-jd-heading" className="mb-5 border-y border-status-inferred/30 py-3">
          <h2 id="prepare-jd-heading" className="text-sm font-semibold text-text-primary">先补完整 JD</h2>
          <p className="mt-0.5 max-w-3xl text-xs leading-5 text-text-secondary">JD 只属于这个求职目标；补齐后，准备缺口和追问才会围绕真实岗位要求生成。</p>
          <Field label="岗位描述">
            <textarea className={`${inputCls} mt-2 min-h-[110px]`} value={jd} onChange={(e) => setJd(e.target.value)} />
          </Field>
          <div className="mt-2"><PrimaryButton disabled={!jd.trim()} onClick={() => void productApi.patchGoal(goal.id, { jd }).then(reload)}>保存 JD</PrimaryButton></div>
        </section>
      ) : null}

      <section aria-labelledby="prepare-focus-heading" className="mb-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[11px] font-medium text-text-muted">NEXT INTERVIEW PREP</p>
            <h2 id="prepare-focus-heading" className="mt-1 text-base font-semibold text-text-primary">下一场，先把这些讲清楚</h2>
            <p className="mt-1 max-w-3xl text-xs leading-5 text-text-secondary">这里只保留最值得先处理的内容。缺口、追问和资料都服务于下一场，而不是分别成为一套管理模块。</p>
          </div>
          <div className="grid grid-cols-3 divide-x divide-bg-tertiary/70 border-y border-bg-tertiary/70 py-2.5 text-right">
            <div className="px-3">
              <p className="text-lg font-semibold tabular-nums text-text-primary">{data.gap_map.length}</p>
              <p className="text-[10px] text-text-muted">准备缺口</p>
            </div>
            <div className="px-3">
              <p className="text-lg font-semibold tabular-nums text-text-primary">{data.attack_surface.length}</p>
              <p className="text-[10px] text-text-muted">高概率深挖</p>
            </div>
            <div className="px-3">
              <p className="text-lg font-semibold tabular-nums text-text-primary">{coveredStories}/{storyTotal}</p>
              <p className="text-[10px] text-text-muted">故事覆盖</p>
            </div>
          </div>
        </div>
        <div className="mt-3">
          <NextFocusList goalId={goal.id} items={data.next_focus} onChanged={reload} />
        </div>
      </section>

      <div className="grid gap-9 lg:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.72fr)]">
        <div className="min-w-0 space-y-7">
          <section aria-labelledby="prepare-gap-heading">
            <div className="flex items-end justify-between gap-3">
              <div>
                <h2 id="prepare-gap-heading" className="text-sm font-semibold text-text-primary">准备缺口</h2>
                <p className="mt-0.5 text-[11px] text-text-muted">优先补“岗位会问、但你目前讲不扎实”的地方。</p>
              </div>
              {data.gap_map.length ? <span className="text-[11px] tabular-nums text-text-muted">{data.gap_map.length} 项</span> : null}
            </div>
            {data.gap_map.length ? (
              <ul className="mt-2 divide-y divide-bg-tertiary/70 border-y border-bg-tertiary/70">
                {data.gap_map.map((g) => {
                  const meta = GAP_STATUS[g.status] ?? { label: g.status, tone: 'muted' as const }
                  return (
                    <li key={g.topic} className="py-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-text-primary">{g.topic}</span>
                        <StatusBadge tone={meta.tone}>{meta.label}</StatusBadge>
                        {g.priority === 'high' ? <span className="text-[10px] font-medium text-status-inferred">优先</span> : null}
                      </div>
                      <p className="mt-0.5 text-[11px] leading-5 text-text-muted">{g.reason}</p>
                    </li>
                  )
                })}
              </ul>
            ) : <div className="mt-2"><EmptyState title={data.has_jd ? '没有发现明显缺口' : '补充 JD 后显示'} /></div>}
          </section>

          <section aria-labelledby="prepare-deep-dive-heading">
            <div>
              <h2 id="prepare-deep-dive-heading" className="text-sm font-semibold text-text-primary">最可能被深挖的经历</h2>
              <p className="mt-0.5 text-[11px] text-text-muted">不是预测“会不会过”，而是提前看哪些个人说法最容易被继续追问。</p>
            </div>
            {data.attack_surface.length ? (
              <ul className="mt-2 divide-y divide-bg-tertiary/70 border-y border-bg-tertiary/70">
                {data.attack_surface.map((item) => (
                  <li key={item.claim_id} className="py-3">
                    <p className="text-sm font-medium leading-5 text-text-primary">{item.text}</p>
                    {item.risks.length ? <p className="mt-1 text-[11px] leading-4 text-status-inferred">{item.risks.join(' · ')}</p> : null}
                    {item.probes.length ? (
                      <div className="mt-2 border-l-2 border-bg-hover pl-3">
                        <p className="text-[10px] font-medium text-text-muted">继续追问可能会问</p>
                        <ul className="mt-1 space-y-1 text-[11px] leading-4 text-text-secondary">
                          {item.probes.map((probe) => <li key={probe}>{probe}</li>)}
                        </ul>
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : <div className="mt-2"><EmptyState title="导入简历并确认事实后显示" action={<SecondaryButton onClick={() => navigate(paths.me('resume'))}>去导入简历</SecondaryButton>} /></div>}
          </section>

          <section aria-labelledby="prepare-question-heading">
            <div>
              <h2 id="prepare-question-heading" className="text-sm font-semibold text-text-primary">可能追问</h2>
              <p className="mt-0.5 text-[11px] text-text-muted">把一个主题继续向“知识 → 真实经历 → 开放设计”推进，练的是追问链，不是背答案。</p>
            </div>
            <div className="mt-3 border-y border-bg-tertiary/70 py-3">
              {data.question_graph.length ? <QuestionTree nodes={data.question_graph} /> : <EmptyState title="暂无追问建议" />}
            </div>
          </section>
        </div>

        <aside className="min-w-0 space-y-6 lg:border-l lg:border-bg-tertiary/70 lg:pl-7">
          <section aria-labelledby="prepare-story-heading">
            <h2 id="prepare-story-heading" className="text-sm font-semibold text-text-primary">故事与证据</h2>
            <div className="mt-2 border-y border-bg-tertiary/70 py-3">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-xs text-text-secondary">常见能力情境</span>
                <span className="text-sm font-semibold tabular-nums text-text-primary">{coveredStories} / {storyTotal}</span>
              </div>
              {storyGap ? (
                <div className="mt-3">
                  <p className="text-xs font-medium text-text-primary">下一块最值得补：{storyGap.label}</p>
                  <p className="mt-0.5 text-[11px] leading-4 text-text-muted">只从真实经历里补一个能经得住追问的故事，不为覆盖率编经历。</p>
                  <button type="button" className="mt-2 text-xs font-medium text-accent-blue hover:underline" onClick={() => navigate(paths.me('stories'))}>去整理这个故事</button>
                </div>
              ) : <p className="mt-2 text-[11px] text-text-muted">常见能力情境已有故事覆盖；继续优先补证据和结果口径。</p>}
            </div>
            {goal.legacy_prep_space_id ? (
              <div className="mt-3">
                <button type="button" onClick={() => setSkillsOpen((value) => !value)} className="text-xs text-text-secondary hover:text-text-primary">
                  {skillsOpen ? '收起技能卡与预测题' : '查看旧版技能卡与预测题'}
                </button>
                {skillsOpen ? (
                  <div className="mt-2 max-h-[640px] overflow-hidden rounded-xl border border-bg-hover/50">
                    <Suspense fallback={<Loading />}><PrepSpace initialSpaceId={goal.legacy_prep_space_id} embedded /></Suspense>
                  </div>
                ) : null}
              </div>
            ) : null}
          </section>

          <section aria-labelledby="prepare-pack-heading">
            <div className="flex items-end justify-between gap-3">
              <div>
                <h2 id="prepare-pack-heading" className="text-sm font-semibold text-text-primary">带入下一场</h2>
                <p className="mt-0.5 text-[11px] leading-4 text-text-muted">上场前还会再次确认并冻结。速记只是提醒，不会变成个人经历证据。</p>
              </div>
            </div>

            <div className="mt-3 grid grid-cols-2 divide-x divide-bg-tertiary/70 border-y border-bg-tertiary/70 py-2.5">
              <div className="pr-3">
                <p className="text-lg font-semibold tabular-nums text-text-primary">{readyMaterials}</p>
                <p className="text-[10px] text-text-muted">就绪资料</p>
              </div>
              <div className="pl-3">
                <p className="text-lg font-semibold tabular-nums text-text-primary">{selectedNotes}</p>
                <p className="text-[10px] text-text-muted">本场速记</p>
              </div>
            </div>

            {data.materials.skipped.length ? (
              <p className="mt-2 text-[11px] leading-4 text-status-inferred">有 {data.materials.skipped.length} 份资料未就绪，不会进入本场。</p>
            ) : null}

            <details className="mt-3 border-b border-bg-tertiary/70 pb-3">
              <summary className="cursor-pointer text-xs font-medium text-text-secondary">调整项目资料</summary>
              <div className="mt-2">
                {mats.data?.items.length ? (
                  <ul className="space-y-2">
                    {mats.data.items.map((material) => (
                      <li key={material.id} className="flex items-center gap-2 text-xs">
                        <input type="checkbox" id={`mat-${material.id}`} checked={goal.selected_material_ids.includes(material.id)} onChange={() => toggleMaterial(material.id)}
                          disabled={material.lifecycle.state === 'FAILED' && !material.lifecycle.active_version} />
                        <label htmlFor={`mat-${material.id}`} className="min-w-0 flex-1 truncate text-text-primary">{material.title}</label>
                        <MaterialStateBadge state={material.lifecycle.state} />
                      </li>
                    ))}
                  </ul>
                ) : <EmptyState title="还没有项目资料" action={<SecondaryButton onClick={() => navigate(paths.library('materials'))}>添加资料</SecondaryButton>} />}
                <button type="button" className="mt-2 text-[11px] text-text-muted hover:text-text-primary" onClick={() => navigate(paths.library('materials'))}>打开资料库</button>
              </div>
            </details>

            <details className="mt-3 border-b border-bg-tertiary/70 pb-3">
              <summary className="cursor-pointer text-xs font-medium text-text-secondary">调整本场速记</summary>
              <div className="mt-2">
                <QuickNotesPanel goalId={goal.id} context="goal" compact selectedIds={noteIds}
                  onSelectionChange={(ids) => { setNoteIds(ids); void productApi.patchGoal(goal.id, { selected_quick_note_ids: ids }).then(() => void reloadPrep()) }} />
              </div>
            </details>

            <div className="mt-3 text-[11px] leading-4 text-text-muted">
              <p>资料：{data.pack_preview.materials.length ? data.pack_preview.materials.map((item) => item.title).join('、') : '未选择'}</p>
              <p className="mt-1">速记：{data.pack_preview.quick_notes.length ? data.pack_preview.quick_notes.map((item) => item.title || item.content.slice(0, 12)).join('、') : '未选择'}</p>
            </div>
          </section>
        </aside>
      </div>
    </div>
  )
  )
}
