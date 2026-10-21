import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { api, getErrorMessage, type FactsPayload, type SkillCardOverview, type StoryItem, type VoicePreferences } from '@/lib/api'
import { useInterviewStore } from '@/stores/configStore'
import FactsSources from './FactsSources'

const ResumeOptimizer = lazy(() => import('@/components/ResumeOptimizer'))

// R2 Stage M「我的成竹」：概览 / 简历 / 项目 / 事实与来源 / Stories / Skills / 我的表达。
export type TabKey = 'overview' | 'resume' | 'projects' | 'facts' | 'stories' | 'skills' | 'voice'

const TABS: Array<[TabKey, string]> = [
  ['overview', '概览'],
  ['resume', '简历'],
  ['projects', '项目'],
  ['facts', '事实与来源'],
  ['stories', 'Stories'],
  ['skills', 'Skills'],
  ['voice', '我的表达'],
]

export function Overview({ onJump }: { onJump: (tab: TabKey) => void }) {
  const [facts, setFacts] = useState<FactsPayload | null>(null)
  const [stories, setStories] = useState<StoryItem[]>([])
  const [cards, setCards] = useState<SkillCardOverview[]>([])
  useEffect(() => {
    api.intelFacts().then(setFacts).catch(() => setFacts(null))
    api.intelStories().then(setStories).catch(() => setStories([]))
    api.intelSkillCards().then(setCards).catch(() => setCards([]))
  }, [])

  const list = facts?.facts ?? []
  const direct = list.filter((f) => f.provenance_status === 'DIRECT_EVIDENCE').length
  const unsupported = list.filter((f) => f.provenance_status === 'NO_EVIDENCE').length
  const confirmed = list.filter((f) => f.user_assertion_status === 'USER_CONFIRMED').length
  const reviewedSkills = cards.filter((c) => c.user_reviewed).length

  return (
    <div className="p-4 space-y-5" data-testid="my-overview">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.75fr)]">
        <section aria-labelledby="my-facts-heading" className="min-w-0">
          <p className="text-[11px] font-medium text-text-muted">PERSONAL TRUTH</p>
          <h2 id="my-facts-heading" className="mt-1 text-base font-semibold text-text-primary">个人事实与证据</h2>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-text-secondary">上场时，成竹只把有来源或经你确认的内容当作你的个人经历；没有证据的说法会继续保持边界。</p>
          <div className="mt-4 grid grid-cols-3 divide-x divide-bg-tertiary/70 border-y border-bg-tertiary/70 py-3">
            <button type="button" onClick={() => onJump('facts')} className="px-3 text-left first:pl-0">
              <span className="block text-2xl font-semibold tabular-nums text-text-primary">{direct}</span>
              <span className="mt-0.5 block text-[11px] text-text-muted">有直接证据</span>
            </button>
            <button type="button" onClick={() => onJump('facts')} className="px-3 text-left">
              <span className="block text-2xl font-semibold tabular-nums text-text-primary">{confirmed}</span>
              <span className="mt-0.5 block text-[11px] text-text-muted">你已确认</span>
            </button>
            <button type="button" onClick={() => onJump('facts')} className="px-3 text-left">
              <span className="block text-2xl font-semibold tabular-nums text-text-primary">{unsupported}</span>
              <span className="mt-0.5 block text-[11px] text-text-muted">暂无证据</span>
            </button>
          </div>
        </section>

        <section aria-labelledby="my-assets-heading" className="min-w-0 lg:border-l lg:border-bg-tertiary/70 lg:pl-6">
          <p className="text-[11px] font-medium text-text-muted">REUSABLE EXPRESSION</p>
          <h2 id="my-assets-heading" className="mt-1 text-base font-semibold text-text-primary">可复用表达资产</h2>
          <div className="mt-3 divide-y divide-bg-tertiary/70 border-y border-bg-tertiary/70">
            <button type="button" onClick={() => onJump('stories')} className="flex w-full items-center justify-between gap-4 py-3 text-left">
              <span><span className="block text-sm font-medium text-text-primary">Stories</span><span className="mt-0.5 block text-[11px] text-text-muted">真实经历整理成可复用故事</span></span>
              <span className="text-xl font-semibold tabular-nums text-text-primary">{stories.length}</span>
            </button>
            <button type="button" onClick={() => onJump('skills')} className="flex w-full items-center justify-between gap-4 py-3 text-left">
              <span><span className="block text-sm font-medium text-text-primary">已确认技能卡</span><span className="mt-0.5 block text-[11px] text-text-muted">确认后才会进入 Interview Pack</span></span>
              <span className="text-xl font-semibold tabular-nums text-text-primary">{reviewedSkills}</span>
            </button>
          </div>
        </section>
      </div>

      <section aria-label="下一步" className="border-t border-bg-tertiary/70 pt-4">
        <p className="text-[11px] font-medium text-text-muted">下一步</p>
        {unsupported > 0 ? (
          <div className="mt-1 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-text-primary">先处理 {unsupported} 条暂无证据的个人事实</p>
              <p className="mt-0.5 text-xs text-text-secondary">确认、否认或补来源，避免面试中把不确定内容说成既定事实。</p>
            </div>
            <button type="button" onClick={() => onJump('facts')} className="btn-subtle rounded-lg px-3 py-1.5 text-xs">去待确认</button>
          </div>
        ) : (
          <p className="mt-1 text-sm text-text-secondary">当前事实边界没有明显缺口，可以继续补充 Stories 或进入练习。</p>
        )}
      </section>
    </div>
  )
}

export function Projects() {
  const [cards, setCards] = useState<SkillCardOverview[]>([])
  useEffect(() => { api.intelSkillCards().then(setCards).catch(() => setCards([])) }, [])
  const projects = Array.from(new Map(cards.map((c) => [c.project_name, c])).values())
  if (!projects.length) {
    return <p className="p-6 text-sm text-text-muted">还没有项目。在「求职 → 岗位目标」里生成技能卡后，项目会出现在这里。</p>
  }
  return (
    <ul className="p-4 space-y-2">
      {projects.map((p) => (
        <li key={p.id} className="rounded-xl border border-bg-hover/50 bg-bg-secondary p-3">
          <div className="text-sm font-semibold text-text-primary">{p.project_name}</div>
          <div className="mt-0.5 text-[11px] text-text-muted">来自岗位目标：{p.space_title} · {p.user_reviewed ? '已确认' : '待确认'}</div>
          {typeof p.card.background === 'string' && p.card.background && (
            <p className="mt-1 text-xs text-text-secondary">{p.card.background}</p>
          )}
        </li>
      ))}
    </ul>
  )
}

// v1.3 Stories 3.0 capability categories (canonical §6)
const STORY_CATEGORIES: Array<[string, string]> = [
  ['Ownership', 'Ownership 担当'], ['Conflict', '冲突处理'], ['Failure', '失败与反思'], ['Leadership', '领导力'],
  ['Ambiguity', '模糊情境决策'], ['Collaboration', '协作'], ['Difficult Problem', '解决困难问题'],
  ['Influence', '影响他人'], ['Trade-off', '取舍'], ['Learning', '学习成长'],
]

const EMPTY_STORY: Omit<StoryItem, 'id' | 'updated_at' | 'tags'> = { title: '', situation: '', challenge: '', action: '', result: '', reflection: '' }
const STORY_FIELDS: Array<[keyof typeof EMPTY_STORY, string]> = [
  ['title', '标题'],
  ['situation', '情境'],
  ['challenge', '挑战'],
  ['action', '你的行动'],
  ['result', '结果'],
  ['reflection', '复盘'],
]

export function Stories() {
  const pushToast = useInterviewStore((s) => s.pushToast)
  const [items, setItems] = useState<StoryItem[]>([])
  const [draft, setDraft] = useState(EMPTY_STORY)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingRelations, setEditingRelations] = useState<{ source_ids: string[]; skill_ids: string[]; last_used_session: string }>({ source_ids: [], skill_ids: [], last_used_session: '' })
  const [category, setCategory] = useState('')
  const load = useCallback(() => { api.intelStories().then(setItems).catch(() => setItems([])) }, [])
  useEffect(() => { load() }, [load])

  const save = async () => {
    if (!draft.title.trim()) return
    try {
      const body = { ...draft, ...editingRelations, tags: category ? [category] : [] }
      if (editingId) await api.intelUpdateStory(editingId, body)
      else await api.intelCreateStory(body)
      setDraft(EMPTY_STORY)
      setEditingRelations({ source_ids: [], skill_ids: [], last_used_session: '' })
      setCategory('')
      setEditingId(null)
      load()
    } catch (error) {
      pushToast(getErrorMessage(error, '保存失败'), 'error')
    }
  }

  const startNew = () => {
    setEditingId(null)
    setDraft(EMPTY_STORY)
    setEditingRelations({ source_ids: [], skill_ids: [], last_used_session: '' })
    setCategory('')
  }

  return (
    <div className="grid gap-8 p-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
      <section aria-labelledby="story-library-heading" className="min-w-0">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h3 id="story-library-heading" className="text-sm font-semibold text-text-primary">故事素材</h3>
            <p className="mt-0.5 max-w-2xl text-[11px] leading-5 text-text-muted">
              这里不是“标准答案库”。每个故事都应该来自真实经历，并保留足够的情境、行动和结果，方便下一场按问题重组表达。
            </p>
          </div>
          <button type="button" onClick={startNew} className="btn-subtle flex-shrink-0 rounded-lg px-3 py-1.5 text-xs">写新故事</button>
        </div>

        {items.length === 0 ? (
          <p className="mt-4 border-y border-bg-tertiary/70 py-5 text-sm text-text-muted">还没有故事。先从一个最近被追问过、你确实亲历的项目开始。</p>
        ) : (
          <ul className="mt-3 divide-y divide-bg-tertiary/70 border-y border-bg-tertiary/70">
            {items.map((story) => {
              const tag = (story.tags ?? [])[0] ?? ''
              const categoryLabel = STORY_CATEGORIES.find(([key]) => key === tag)?.[1] ?? tag
              const summary = [story.situation, story.action, story.result].filter(Boolean).join(' → ')
              return (
                <li key={story.id} className="py-3">
                  <div className="flex items-start gap-3">
                    <button type="button" className="min-w-0 flex-1 text-left" onClick={() => {
                      setEditingId(story.id)
                      setCategory(tag)
                      setEditingRelations({ source_ids: story.source_ids ?? [], skill_ids: story.skill_ids ?? [], last_used_session: story.last_used_session ?? '' })
                      setDraft({ title: story.title, situation: story.situation, challenge: story.challenge, action: story.action, result: story.result, reflection: story.reflection })
                    }}>
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-text-primary">{story.title}</span>
                        {categoryLabel ? <span className="text-[10px] text-text-muted">{categoryLabel}</span> : null}
                      </span>
                      {summary ? <span className="mt-1 block text-xs leading-5 text-text-secondary">{summary}</span> : null}
                      {(story.source_ids?.length || story.skill_ids?.length || story.last_used_session) ? (
                        <span className="mt-1.5 block text-[10px] text-text-muted">
                          {story.source_ids?.length ? `来源 ${story.source_ids.length}` : '来源未关联'}
                          {story.skill_ids?.length ? ` · 技能 ${story.skill_ids.length}` : ''}
                          {story.last_used_session ? ` · 最近用于场次 ${story.last_used_session.slice(0, 12)}` : ''}
                        </span>
                      ) : (
                        <span className="mt-1.5 block text-[10px] text-text-muted">尚未关联来源或技能</span>
                      )}
                    </button>
                    <button type="button" className="flex-shrink-0 text-[11px] text-text-muted hover:text-status-risk" onClick={() => api.intelDeleteStory(story.id).then(load)}>删除</button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      <aside aria-labelledby="story-editor-heading" className="min-w-0 lg:border-l lg:border-bg-tertiary/70 lg:pl-7" data-testid="story-builder">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 id="story-editor-heading" className="text-sm font-semibold text-text-primary">{editingId ? '编辑这个故事' : '写一个真实故事'}</h3>
            <p className="mt-0.5 text-[11px] leading-5 text-text-muted">只写你真实经历过的事。确认后的内容可以进入 Interview Pack；成竹不会替你补造个人经历。</p>
          </div>
          <button type="button" onClick={() => void save()} disabled={!draft.title.trim()}
            className="btn-primary inline-flex min-h-[32px] flex-shrink-0 items-center rounded-lg px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50">
            {editingId ? '保存修改' : '保存故事'}
          </button>
        </div>

        <div className="mt-4 space-y-3">
          <label className="block">
            <span className="text-[11px] font-medium text-text-secondary">能力情境</span>
            <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Story 能力分类"
              className="mt-1 w-full rounded-lg border border-bg-hover bg-bg-primary px-2.5 py-1.5 text-sm text-text-primary">
              <option value="">未分类</option>
              {STORY_CATEGORIES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>
          </label>

          {STORY_FIELDS.map(([key, label]) => (
            <label key={key} className="block">
              <span className="text-[11px] font-medium text-text-secondary">{label}</span>
              {key === 'title' ? (
                <input value={draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
                  placeholder="一句话说明这是什么经历"
                  className="mt-1 w-full rounded-lg border border-bg-hover bg-bg-primary px-2.5 py-1.5 text-sm text-text-primary" />
              ) : (
                <textarea rows={key === 'action' ? 3 : 2} value={draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
                  className="mt-1 w-full resize-y rounded-lg border border-bg-hover bg-bg-primary px-2.5 py-1.5 text-sm leading-5 text-text-primary" />
              )}
            </label>
          ))}

          {editingId ? <div className="pt-1"><button type="button" onClick={startNew} className="text-xs text-text-muted hover:text-text-primary">取消编辑</button></div> : null}
        </div>
      </aside>
    </div>
  )
}

export function Skills() {
  const [cards, setCards] = useState<SkillCardOverview[]>([])
  const load = useCallback(() => { api.intelSkillCards().then(setCards).catch(() => setCards([])) }, [])
  useEffect(() => { load() }, [load])

  const reviewed = cards.filter((c) => c.user_reviewed)
  const pending = cards.filter((c) => !c.user_reviewed)
  const readCardText = (card: Record<string, unknown>) => {
    const keys = ['background', 'summary', 'evidence', 'impact', 'skill']
    for (const key of keys) {
      const value = card[key]
      if (typeof value === 'string' && value.trim()) return value.trim()
    }
    return ''
  }

  if (!cards.length) {
    return (
      <div className="p-5">
        <p className="text-sm font-medium text-text-primary">还没有可复用的技能证据</p>
        <p className="mt-1 max-w-xl text-xs leading-5 text-text-muted">
          技能卡从具体求职目标和项目材料中生成。只有你确认内容属实后，它才会进入 Interview Pack。
        </p>
      </div>
    )
  }

  return (
    <div className="p-4" data-testid="skills-library">
      <section aria-label="技能卡边界" className="grid gap-3 border-y border-bg-tertiary/70 py-3 sm:grid-cols-[1fr_auto_auto] sm:items-center">
        <div>
          <p className="text-sm font-semibold text-text-primary">确认的是“我确实做过什么”</p>
          <p className="mt-0.5 max-w-2xl text-xs leading-5 text-text-secondary">
            技能卡不是能力评分，也不是证书。它把项目事实整理成下一场可复用的表达证据；未确认内容不会进入 Interview Pack。
          </p>
        </div>
        <div className="text-left sm:text-right">
          <p className="text-lg font-semibold tabular-nums text-text-primary">{reviewed.length}</p>
          <p className="text-[10px] text-text-muted">已确认 · 可进入 Pack</p>
        </div>
        <div className="text-left sm:text-right">
          <p className="text-lg font-semibold tabular-nums text-text-primary">{pending.length}</p>
          <p className="text-[10px] text-text-muted">待你确认</p>
        </div>
      </section>

      <div className="mt-4 grid gap-8 lg:grid-cols-[minmax(0,1.1fr)_minmax(300px,0.75fr)]">
        <section aria-labelledby="skills-ready-heading">
          <div className="flex items-end justify-between gap-3">
            <div>
              <h3 id="skills-ready-heading" className="text-sm font-semibold text-text-primary">可复用能力证据</h3>
              <p className="mt-0.5 text-[11px] text-text-muted">按项目保留来源，不跨项目把相似经历自动合并成一条“能力结论”。</p>
            </div>
            <span className="text-[11px] text-text-muted">{cards.length} 张</span>
          </div>

          <ul className="mt-3 divide-y divide-bg-tertiary/70 border-y border-bg-tertiary/70">
            {cards.map((card) => {
              const detail = readCardText(card.card)
              return (
                <li key={card.id} className="py-3">
                  <div className="flex items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-text-primary">{card.project_name}</span>
                        <span className={`text-[10px] ${card.user_reviewed ? 'text-status-direct' : 'text-text-muted'}`}>
                          {card.user_reviewed ? '已确认' : '待确认'}
                        </span>
                      </div>
                      <p className="mt-0.5 text-[11px] text-text-muted">{card.space_title}</p>
                      {detail ? <p className="mt-1.5 text-xs leading-5 text-text-secondary">{detail}</p> : null}
                    </div>
                    <button type="button" aria-pressed={card.user_reviewed}
                      onClick={() => api.prepReviewSkillCard(card.id, !card.user_reviewed).then(load)}
                      className={`flex-shrink-0 rounded-lg border px-3 py-1.5 text-xs font-medium ${card.user_reviewed ? 'border-status-direct/35 text-status-direct' : 'border-bg-hover text-text-secondary hover:bg-bg-hover/35'}`}>
                      {card.user_reviewed ? '移出 Pack' : '确认内容属实'}
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
        </section>

        <aside className="lg:border-l lg:border-bg-tertiary/70 lg:pl-7">
          <h3 className="text-sm font-semibold text-text-primary">进入 Pack 前的检查</h3>
          <div className="mt-3 divide-y divide-bg-tertiary/70 border-y border-bg-tertiary/70 text-xs">
            <div className="py-2.5">
              <p className="font-medium text-text-primary">事实可追溯</p>
              <p className="mt-0.5 text-[11px] leading-4 text-text-muted">能指回具体项目、材料或你本人确认过的事实。</p>
            </div>
            <div className="py-2.5">
              <p className="font-medium text-text-primary">措辞不过度</p>
              <p className="mt-0.5 text-[11px] leading-4 text-text-muted">“参与 / 负责 / 主导”要与真实责任范围一致。</p>
            </div>
            <div className="py-2.5">
              <p className="font-medium text-text-primary">能经得住追问</p>
              <p className="mt-0.5 text-[11px] leading-4 text-text-muted">确认后它会被练习和上场引用，不要只确认一句漂亮结论。</p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}

export function Voice() {
  const pushToast = useInterviewStore((s) => s.pushToast)
  const [prefs, setPrefs] = useState<VoicePreferences | null>(null)
  const [banned, setBanned] = useState('')
  useEffect(() => {
    api.intelVoice().then((p) => { setPrefs(p); setBanned(p.banned_phrases.join('，')) }).catch(() => setPrefs(null))
  }, [])
  if (!prefs) return <p className="p-4 text-sm text-text-muted">加载中…</p>
  const save = async () => {
    try {
      const saved = await api.intelSaveVoice({ ...prefs, banned_phrases: banned.split(/[,，\n]/).map((s) => s.trim()).filter(Boolean) })
      setPrefs(saved)
      pushToast('已保存；下次冻结 Interview Pack 时生效', 'success')
    } catch (error) {
      pushToast(getErrorMessage(error, '保存失败'), 'error')
    }
  }
  return (
    <div className="p-4 max-w-xl space-y-3" data-testid="voice-preferences">
      <label className="flex items-center gap-2 text-sm text-text-primary">
        <input type="checkbox" checked={prefs.conclusion_first} onChange={(e) => setPrefs({ ...prefs, conclusion_first: e.target.checked })} />
        先说结论
      </label>
      <label className="block text-sm text-text-primary">
        目标时长：{prefs.target_seconds} 秒
        <input type="range" min={15} max={180} step={5} value={prefs.target_seconds} aria-label="目标时长"
          onChange={(e) => setPrefs({ ...prefs, target_seconds: Number(e.target.value) })} className="block w-full" />
      </label>
      <label className="block text-sm text-text-primary">
        回答语言
        <select value={prefs.language} onChange={(e) => setPrefs({ ...prefs, language: e.target.value })}
          className="mt-1 block rounded-lg border border-bg-hover bg-bg-secondary px-2 py-1 text-sm">
          <option value="zh-CN">中文</option>
          <option value="en">English</option>
        </select>
      </label>
      <label className="block text-sm text-text-primary">
        中英术语
        <select value={prefs.term_style} onChange={(e) => setPrefs({ ...prefs, term_style: e.target.value })}
          className="mt-1 block rounded-lg border border-bg-hover bg-bg-secondary px-2 py-1 text-sm">
          <option value="keep_english_terms">技术术语保留英文</option>
          <option value="translate_terms">尽量用中文术语</option>
        </select>
      </label>
      <fieldset className="text-sm text-text-primary">
        <legend>表达形态</legend>
        {(['bullet', 'narrative'] as const).map((shape) => (
          <label key={shape} className="mr-4 inline-flex items-center gap-1">
            <input type="radio" name="shape" checked={prefs.shape === shape} onChange={() => setPrefs({ ...prefs, shape })} />
            {shape === 'bullet' ? '要点式' : '叙述式'}
          </label>
        ))}
      </fieldset>
      <label className="block text-sm text-text-primary">
        禁用的 AI 套话（逗号分隔）
        <textarea rows={2} value={banned} onChange={(e) => setBanned(e.target.value)}
          className="mt-1 w-full rounded-lg border border-bg-hover bg-bg-primary px-2 py-1 text-sm" placeholder="赋能，抓手，闭环" />
      </label>
      <button type="button" onClick={() => void save()} className="rounded-lg bg-accent-blue px-3 py-1.5 text-xs font-medium text-white">保存</button>
    </div>
  )
}

export default function MyChengzhu() {
  const [tab, setTab] = useState<TabKey>('resume')
  return (
    <div className="flex-1 flex flex-col min-h-0" data-testid="my-chengzhu">
      <div role="tablist" aria-label="我的成竹" className="flex gap-1 overflow-x-auto scrollbar-none px-3 md:px-5 py-2 border-b border-bg-tertiary/70 bg-bg-secondary/40 flex-shrink-0">
        {TABS.map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
            className={`whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium ${tab === key ? 'bg-container-primary text-container-on-primary' : 'text-text-muted hover:text-text-primary'}`}>
            {label}
          </button>
        ))}
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto flex flex-col">
        {tab === 'overview' && <Overview onJump={setTab} />}
        {tab === 'resume' && (
          <Suspense fallback={<div className="p-4 text-sm text-text-muted">加载中…</div>}>
            <ResumeOptimizer />
          </Suspense>
        )}
        {tab === 'projects' && <Projects />}
        {tab === 'facts' && <FactsSources />}
        {tab === 'stories' && <Stories />}
        {tab === 'skills' && <Skills />}
        {tab === 'voice' && <Voice />}
      </div>
    </div>
  )
}
