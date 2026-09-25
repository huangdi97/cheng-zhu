import { useCallback, useEffect, useState } from 'react'
import { Plus, Trash2, Sparkles, RefreshCw, ArrowLeft, Target, ListChecks, FolderKanban, Loader2, AlertTriangle, BriefcaseBusiness, ShieldCheck } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import PracticePanel from './PracticePanel'
import SkillBuilderPanel from './SkillBuilderPanel'
import { api, LaunchPack, PrepSpace as PrepSpaceType, PrepSpaceLite, ResumeHistoryItem } from '@/lib/api'

type View = { kind: 'list' } | { kind: 'new' } | { kind: 'detail'; id: number }

const EMPTY_CARD = {
  name: '',
  background: '',
  my_role: '',
  tech_decisions: [] as string[],
  metrics: [] as string[],
  tradeoffs: [] as string[],
  likely_follow_ups: [] as string[],
}

function statusBadge(status: string): { label: string; cls: string } {
  switch (status) {
    case 'done':
      return { label: '已生成', cls: 'bg-accent-green/15 text-accent-green border-accent-green/30' }
    case 'generating':
      return { label: '生成中', cls: 'bg-accent-blue/15 text-accent-blue border-accent-blue/30' }
    case 'failed':
      return { label: '失败', cls: 'bg-accent-red/15 text-accent-red border-accent-red/30' }
    default:
      return { label: '待生成', cls: 'bg-bg-hover/40 text-text-muted border-bg-hover/40' }
  }
}

function FieldList({ title, items }: { title: string; items: string[] }) {
  if (!items || items.length === 0) return null
  return (
    <div className="mt-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted mb-1.5">{title}</div>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="text-[13px] text-text-secondary leading-relaxed flex gap-2">
            <span className="text-accent-blue select-none">•</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function SkillCardView({ raw }: { raw: { project_name: string; card: Record<string, unknown> } }) {
  const card = { ...EMPTY_CARD, ...(raw.card || {}) }
  const list = (key: string) => Array.isArray(card[key]) ? (card[key] as string[]) : []
  return (
    <div className="rounded-xl border border-bg-hover/50 bg-bg-secondary p-4">
      <div className="text-sm font-semibold text-text-primary">{card.name || raw.project_name}</div>
      {card.background ? <p className="mt-1.5 text-[13px] text-text-secondary leading-relaxed">{card.background}</p> : null}
      {card.my_role ? (
        <p className="mt-1.5 text-[13px] text-text-secondary leading-relaxed">
          <span className="text-text-muted">我的角色：</span>{card.my_role}
        </p>
      ) : null}
      <FieldList title="技术决策" items={list('tech_decisions')} />
      <FieldList title="量化结果" items={list('metrics')} />
      <FieldList title="取舍 / 踩坑" items={list('tradeoffs')} />
      <FieldList title="面试官可能追问" items={list('likely_follow_ups')} />
    </div>
  )
}

export default function PrepSpace() {
  const [view, setView] = useState<View>({ kind: 'list' })
  const [spaces, setSpaces] = useState<PrepSpaceLite[]>([])
  const [space, setSpace] = useState<PrepSpaceType | null>(null)
  const [loadingList, setLoadingList] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [practiceOpen, setPracticeOpen] = useState(false)
  const [skillBuilderOpen, setSkillBuilderOpen] = useState(false)
  const [activatingPack, setActivatingPack] = useState(false)
  const [launchPack, setLaunchPack] = useState<LaunchPack | null>(null)

  // create form
  const [role, setRole] = useState('')
  const [company, setCompany] = useState('')
  const [jdText, setJdText] = useState('')
  const [resumeText, setResumeText] = useState('')
  const [resumeItems, setResumeItems] = useState<ResumeHistoryItem[]>([])
  const [selectedResumeId, setSelectedResumeId] = useState<number | ''>('')
  const [creating, setCreating] = useState(false)

  const loadList = useCallback(async () => {
    setLoadingList(true)
    try {
      const res = await api.prepListSpaces()
      setSpaces(res.items || [])
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoadingList(false)
    }
  }, [])

  useEffect(() => {
    loadList()
  }, [loadList])

  useEffect(() => {
    if (view.kind !== 'new') return
    api.resumeHistory().then((res) => setResumeItems(res.items || [])).catch(() => setResumeItems([]))
  }, [view.kind])

  const loadDetail = useCallback(async (id: number) => {
    setLoadingDetail(true)
    setError(null)
    try {
      const data = await api.prepGetSpace(id)
      setSpace(data)
      setView({ kind: 'detail', id })
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoadingDetail(false)
    }
  }, [])

  const handleCreate = async () => {
    if (!role.trim() && !jdText.trim() && !resumeText.trim()) {
      setError('请至少填写岗位名称、JD 或简历')
      return
    }
    setCreating(true)
    setError(null)
    try {
      const created = await api.prepCreateSpace({
        role: role.trim() || undefined,
        company: company.trim() || undefined,
        jd_text: jdText.trim() || undefined,
        resume_text: resumeText.trim() || undefined,
        resume_history_id: selectedResumeId === '' ? undefined : selectedResumeId,
      })
      setSpace(created)
      setView({ kind: 'detail', id: created.id })
      loadList()
    } catch (e) {
      setError(e instanceof Error ? e.message : '创建失败')
    } finally {
      setCreating(false)
    }
  }

  const handleGenerate = async () => {
    if (!space) return
    setGenerating(true)
    setError(null)
    try {
      const updated = await api.prepGenerate(space.id)
      setSpace(updated)
      loadList()
    } catch (e) {
      setError(e instanceof Error ? e.message : '生成失败')
    } finally {
      setGenerating(false)
    }
  }

  const handleActivateLaunchPack = async () => {
    if (!space) return
    setActivatingPack(true)
    setError(null)
    try {
      const result = await api.prepActivateLaunchPack(space.id)
      setLaunchPack(result.pack)
    } catch (e) {
      setError(e instanceof Error ? e.message : '启用上场包失败')
    } finally {
      setActivatingPack(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await api.prepDeleteSpace(id)
      if (view.kind === 'detail' && view.id === id) setView({ kind: 'list' })
      setSpace(null)
      loadList()
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败')
    }
  }

  const handlePickResume = async (id: number | '') => {
    setSelectedResumeId(id)
    if (id === '') return
    try {
      const detail = await api.resumeHistoryDetail(id)
      if (detail.summary) setResumeText(detail.summary)
    } catch {
      /* ignore */
    }
  }

  const backToList = () => {
    setView({ kind: 'list' })
    setSpace(null)
  }

  if (view.kind === 'new') {
    return (
      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        <div className="max-w-3xl mx-auto space-y-4">
          <button onClick={backToList} className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-accent-blue transition-colors">
            <ArrowLeft className="h-4 w-4" /> 返回列表
          </button>
          <div className="rounded-2xl border border-bg-hover/50 bg-bg-secondary p-5">
            <div className="flex items-center gap-2 mb-4">
              <FolderKanban className="h-5 w-5 text-accent-blue" />
              <h2 className="text-base font-bold text-text-primary">新建准备空间</h2>
            </div>
            <div className="grid gap-3">
              <div className="grid sm:grid-cols-2 gap-3">
                <label className="block">
                  <span className="text-xs text-text-muted">目标岗位 *</span>
                  <input value={role} onChange={(e) => setRole(e.target.value)} placeholder="例如：后端开发工程师"
                    className="mt-1 w-full rounded-xl border border-bg-hover/50 bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-blue/60 focus:outline-none" />
                </label>
                <label className="block">
                  <span className="text-xs text-text-muted">目标公司</span>
                  <input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="例如：某互联网公司"
                    className="mt-1 w-full rounded-xl border border-bg-hover/50 bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-blue/60 focus:outline-none" />
                </label>
              </div>
              <label className="block">
                <span className="text-xs text-text-muted">岗位 JD（粘贴或输入）</span>
                <textarea value={jdText} onChange={(e) => setJdText(e.target.value)} rows={4} placeholder="粘贴目标岗位的职位描述…"
                  className="mt-1 w-full rounded-xl border border-bg-hover/50 bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-blue/60 focus:outline-none resize-y" />
              </label>
              <label className="block">
                <span className="text-xs text-text-muted">简历正文（可粘贴，或从下面历史选用）</span>
                <textarea value={resumeText} onChange={(e) => setResumeText(e.target.value)} rows={6} placeholder="粘贴你的简历正文 / 项目经历…"
                  className="mt-1 w-full rounded-xl border border-bg-hover/50 bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-blue/60 focus:outline-none resize-y" />
              </label>
              {resumeItems.length > 0 && (
                <label className="block">
                  <span className="text-xs text-text-muted">从简历历史选用（自动填入上方正文）</span>
                  <select value={selectedResumeId} onChange={(e) => handlePickResume(e.target.value === '' ? '' : Number(e.target.value))}
                    className="mt-1 w-full rounded-xl border border-bg-hover/50 bg-bg-primary px-3 py-2 text-sm text-text-primary focus:border-accent-blue/60 focus:outline-none">
                    <option value="">不选用历史简历</option>
                    {resumeItems.map((item) => (
                      <option key={item.id} value={item.id}>{item.original_filename}</option>
                    ))}
                  </select>
                </label>
              )}
            </div>
            {error ? <div className="mt-3 text-sm text-accent-red">{error}</div> : null}
            <button onClick={handleCreate} disabled={creating}
              className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-accent-blue px-4 py-2 text-sm font-medium text-white shadow-sm shadow-accent-blue/20 hover:bg-accent-blue/90 disabled:opacity-50">
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              创建准备空间
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (view.kind === 'detail' && skillBuilderOpen && space) {
    return (
      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        <div className="max-w-4xl mx-auto h-full min-h-0">
          <SkillBuilderPanel spaceId={space.id} onClose={() => setSkillBuilderOpen(false)} />
        </div>
      </div>
    )
  }
  if (view.kind === 'detail' && practiceOpen && space) {
    return (
      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        <div className="max-w-4xl mx-auto h-full min-h-0">
          <PracticePanel spaceId={space.id} onClose={() => setPracticeOpen(false)} />
        </div>
      </div>
    )
  }
  if (view.kind === 'detail' && (space || loadingDetail)) {
    return (
      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        <div className="max-w-4xl mx-auto space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <button onClick={backToList} className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-accent-blue transition-colors">
              <ArrowLeft className="h-4 w-4" /> 返回列表
            </button>
            <div className="flex items-center gap-2">
              {space && (
                <>
                <button onClick={() => setSkillBuilderOpen(true)}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-accent-blue/15 border border-accent-blue/30 px-3.5 py-1.5 text-xs font-medium text-accent-blue hover:bg-accent-blue/25 transition-colors">
                  <FolderKanban className="h-3.5 w-3.5" /> 技能卡工作台
                </button>
                <button onClick={() => setPracticeOpen(true)}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-accent-green/15 border border-accent-green/30 px-3.5 py-1.5 text-xs font-medium text-accent-green hover:bg-accent-green/25 transition-colors">
                  <Sparkles className="h-3.5 w-3.5" /> 开始模拟面试
                </button>
                </>
              )}
              {space && (
                <button onClick={() => handleDelete(space.id)}
                  className="inline-flex items-center gap-1 rounded-lg border border-bg-hover/50 px-3 py-1.5 text-xs text-text-muted hover:text-accent-red hover:border-accent-red/40 transition-colors">
                  <Trash2 className="h-3.5 w-3.5" /> 删除
                </button>
              )}
              {space && (
                <button onClick={handleGenerate} disabled={generating}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-accent-blue/30 bg-accent-blue/10 px-3.5 py-1.5 text-xs font-medium text-accent-blue hover:bg-accent-blue/20 disabled:opacity-50">
                  {generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                  {generating ? '生成中…' : '生成 / 重新生成'}
                </button>
              )}
              {space && (
                <button onClick={() => void handleActivateLaunchPack()} disabled={activatingPack}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-accent-blue px-3.5 py-1.5 text-xs font-medium text-white hover:brightness-110 disabled:opacity-50">
                  {activatingPack ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BriefcaseBusiness className="h-3.5 w-3.5" />}
                  {activatingPack ? '正在启用…' : launchPack ? '已用于本场' : '用于本场面试'}
                </button>
              )}
            </div>
          </div>

          {generating && (
            <div className="rounded-2xl border border-accent-blue/30 bg-accent-blue/10 p-4 text-sm text-accent-blue flex items-center gap-2">
              <RefreshCw className="h-4 w-4 animate-spin" />
              正在生成岗位洞察、项目技能卡和预测真题，首次约 20-60 秒，请稍候…
            </div>
          )}

          {launchPack && (
            <section className="rounded-2xl border border-accent-blue/25 bg-bg-secondary p-5" aria-label="本场上场包">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4 text-accent-green" />
                    <h3 className="text-sm font-bold text-text-primary">本场上场包已启用</h3>
                  </div>
                  <p className="mt-1 text-xs text-text-muted">
                    仅作用于当前面试会话 · 来源：{[launchPack.title, launchPack.company, launchPack.role].filter(Boolean).join(' · ')}
                  </p>
                </div>
                <div className="flex flex-wrap gap-1.5 text-[10px]">
                  <span className="rounded-full border border-bg-hover bg-bg-tertiary px-2 py-1 text-text-secondary">
                    项目 {launchPack.readiness.project_count}
                  </span>
                  <span className="rounded-full border border-bg-hover bg-bg-tertiary px-2 py-1 text-text-secondary">
                    预测题 {launchPack.readiness.question_count}
                  </span>
                  <span className={`rounded-full border px-2 py-1 ${launchPack.readiness.has_resume ? 'border-accent-green/25 bg-accent-green/10 text-accent-green' : 'border-accent-amber/25 bg-accent-amber/10 text-accent-amber'}`}>
                    {launchPack.readiness.has_resume ? '简历已绑定' : '缺少简历'}
                  </span>
                </div>
              </div>
              {launchPack.risk_prompts.length > 0 ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold text-text-secondary">上场前重点补齐</p>
                  <ul className="mt-1.5 grid gap-1 sm:grid-cols-2">
                    {launchPack.risk_prompts.slice(0, 4).map((item) => (
                      <li key={item} className="text-xs leading-relaxed text-text-muted">• {item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </section>
          )}

          {loadingDetail && !space ? (
            <div className="py-16 text-center text-sm text-text-muted">加载中…</div>
          ) : space ? (
            <>
              <div className="rounded-2xl border border-bg-hover/50 bg-bg-secondary p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-bold text-text-primary">{space.title}</h2>
                  {space.role ? <span className="rounded-lg bg-bg-tertiary px-2 py-0.5 text-xs text-text-secondary">{space.role}</span> : null}
                  {space.company ? <span className="rounded-lg bg-bg-tertiary px-2 py-0.5 text-xs text-text-secondary">{space.company}</span> : null}
                </div>
                {space.insight_status === 'failed' && space.insight_error ? (
                  <div className="mt-3 flex items-start gap-2 rounded-xl bg-accent-red/10 border border-accent-red/30 p-3 text-sm text-accent-red">
                    <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" /> {space.insight_error}
                  </div>
                ) : null}
              </div>

              <div className="rounded-2xl border border-bg-hover/50 bg-bg-secondary p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Target className="h-4 w-4 text-accent-blue" />
                    <h3 className="text-sm font-bold text-text-primary">岗位对齐洞察</h3>
                  </div>
                  <span className={`rounded-lg border px-2 py-0.5 text-[11px] ${statusBadge(space.insight_status).cls}`}>
                    {statusBadge(space.insight_status).label}
                  </span>
                </div>
                {space.insight_markdown ? (
                  <div className="prose-sm max-w-none text-[13px] text-text-secondary leading-relaxed">
                    <ReactMarkdown>{space.insight_markdown}</ReactMarkdown>
                  </div>
                ) : (
                  <p className="text-sm text-text-muted">尚未生成。点击右上角"生成 / 重新生成"。</p>
                )}
              </div>

              <div className="rounded-2xl border border-bg-hover/50 bg-bg-secondary p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <ListChecks className="h-4 w-4 text-accent-blue" />
                    <h3 className="text-sm font-bold text-text-primary">预测真题（{space.questions.length}）</h3>
                  </div>
                  <span className={`rounded-lg border px-2 py-0.5 text-[11px] ${statusBadge(space.questions_status).cls}`}>
                    {statusBadge(space.questions_status).label}
                  </span>
                </div>
                {space.questions.length > 0 ? (
                  <ol className="space-y-2.5">
                    {space.questions.map((q, i) => (
                      <li key={i} className="rounded-xl border border-bg-hover/40 bg-bg-primary/60 p-3">
                        <div className="flex items-start gap-2">
                          <span className="text-xs font-semibold text-text-muted mt-0.5">{i + 1}.</span>
                          <div className="min-w-0">
                            <div className="text-[13px] text-text-primary leading-relaxed">{q.question}</div>
                            {q.why ? <div className="mt-1 text-xs text-text-muted">考察：{q.why}</div> : null}
                          </div>
                        </div>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="text-sm text-text-muted">尚未生成。</p>
                )}
              </div>

              <div className="rounded-2xl border border-bg-hover/50 bg-bg-secondary p-5">
                <div className="flex items-center gap-2 mb-3">
                  <FolderKanban className="h-4 w-4 text-accent-blue" />
                  <h3 className="text-sm font-bold text-text-primary">项目技能卡（{space.skill_cards.length}）</h3>
                </div>
                {space.skill_cards.length > 0 ? (
                  <div className="grid gap-3">
                    {space.skill_cards.map((c) => (
                      <SkillCardView key={c.id} raw={{ project_name: c.project_name, card: c.card }} />
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-text-muted">尚未生成。</p>
                )}
              </div>
            </>
          ) : null}
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6">
      <div className="max-w-4xl mx-auto space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-text-primary">面试准备</h2>
            <p className="text-xs text-text-muted mt-0.5">每个目标岗位一个准备空间：岗位对齐洞察 + 项目技能卡 + 预测真题</p>
          </div>
          <button onClick={() => { setError(null); setView({ kind: 'new' }) }}
            className="inline-flex items-center gap-1.5 rounded-xl bg-accent-blue px-3.5 py-2 text-xs font-medium text-white shadow-sm shadow-accent-blue/20 hover:bg-accent-blue/90">
            <Plus className="h-3.5 w-3.5" /> 新建准备空间
          </button>
        </div>

        {error ? <div className="rounded-xl bg-accent-red/10 border border-accent-red/30 p-3 text-sm text-accent-red">{error}</div> : null}

        {loadingList ? (
          <div className="py-16 text-center text-sm text-text-muted">加载中…</div>
        ) : spaces.length === 0 ? (
          <div className="py-16 text-center">
            <FolderKanban className="h-10 w-10 text-text-muted/50 mx-auto mb-3" />
            <p className="text-sm text-text-muted">还没有准备空间，点击右上角"新建准备空间"开始</p>
          </div>
        ) : (
          <div className="grid gap-3">
            {spaces.map((s) => (
              <div key={s.id} onClick={() => loadDetail(s.id)}
                className="cursor-pointer rounded-2xl border border-bg-hover/50 bg-bg-secondary p-4 hover:border-accent-blue/40 transition-colors">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="truncate text-sm font-semibold text-text-primary">{s.title}</span>
                    {s.role ? <span className="rounded-lg bg-bg-tertiary px-2 py-0.5 text-[11px] text-text-secondary truncate max-w-[160px]">{s.role}</span> : null}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className={`rounded-lg border px-2 py-0.5 text-[11px] ${statusBadge(s.insight_status).cls}`}>洞察 {statusBadge(s.insight_status).label}</span>
                    <span className={`rounded-lg border px-2 py-0.5 text-[11px] ${statusBadge(s.questions_status).cls}`}>真题 {statusBadge(s.questions_status).label}</span>
                    <span className="rounded-lg border border-bg-hover/40 px-2 py-0.5 text-[11px] text-text-muted">技能卡 {s.skill_card_count}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
