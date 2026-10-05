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
  const count = (pred: (f: (typeof list)[number]) => boolean) => list.filter(pred).length
  const tiles: Array<[string, number, TabKey]> = [
    ['有直接证据', count((f) => f.provenance_status === 'DIRECT_EVIDENCE'), 'facts'],
    ['暂无证据', count((f) => f.provenance_status === 'NO_EVIDENCE'), 'facts'],
    ['用户已确认', count((f) => f.user_assertion_status === 'USER_CONFIRMED'), 'facts'],
    ['Stories', stories.length, 'stories'],
    ['已确认技能卡', cards.filter((c) => c.user_reviewed).length, 'skills'],
  ]
  return (
    <div className="p-4 grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="my-overview">
      {tiles.map(([label, value, tab]) => (
        <button key={label} type="button" onClick={() => onJump(tab)}
          className="rounded-2xl border border-bg-hover/50 bg-bg-secondary p-4 text-left hover:border-accent-blue/40">
          <div className="text-2xl font-semibold text-text-primary tabular-nums">{value}</div>
          <div className="mt-1 text-xs text-text-muted">{label}</div>
        </button>
      ))}
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
  ['situation', 'Situation 情境'],
  ['challenge', 'Challenge 挑战'],
  ['action', 'Action 你的行动'],
  ['result', 'Result 结果'],
  ['reflection', 'Reflection 反思'],
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

  return (
    <div className="p-4 grid md:grid-cols-2 gap-4">
      <div className="rounded-2xl border border-bg-hover/50 bg-bg-secondary p-4 space-y-2" data-testid="story-builder">
        <h3 className="text-sm font-semibold text-text-primary">{editingId ? '编辑 Story' : 'Story Builder'}</h3>
        <p className="text-[11px] text-text-muted">只写你真实经历过的事。成竹不会替你编造经历；这里的内容会冻结进 Interview Pack 作为个人来源。</p>
        <label className="block">
          <span className="text-[11px] text-text-muted">能力分类</span>
          <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Story 能力分类"
            className="mt-0.5 w-full rounded-lg border border-bg-hover bg-bg-primary px-2 py-1 text-sm text-text-primary">
            <option value="">未分类</option>
            {STORY_CATEGORIES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
        </label>
        {STORY_FIELDS.map(([key, label]) => (
          <label key={key} className="block">
            <span className="text-[11px] text-text-muted">{label}</span>
            {key === 'title' ? (
              <input value={draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
                className="mt-0.5 w-full rounded-lg border border-bg-hover bg-bg-primary px-2 py-1 text-sm text-text-primary" />
            ) : (
              <textarea rows={2} value={draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
                className="mt-0.5 w-full rounded-lg border border-bg-hover bg-bg-primary px-2 py-1 text-sm text-text-primary" />
            )}
          </label>
        ))}
        <div className="flex gap-2">
          <button type="button" onClick={() => void save()} disabled={!draft.title.trim()}
            className="rounded-lg bg-accent-blue px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50">保存</button>
          {editingId && (
            <button type="button" onClick={() => { setEditingId(null); setDraft(EMPTY_STORY); setEditingRelations({ source_ids: [], skill_ids: [], last_used_session: '' }) }}
              className="rounded-lg border border-bg-hover px-3 py-1.5 text-xs text-text-muted">取消</button>
          )}
        </div>
      </div>
      <ul className="space-y-2">
        {items.length === 0 && <li className="text-sm text-text-muted">还没有 Story。</li>}
        {items.map((story) => (
          <li key={story.id} className="rounded-xl border border-bg-hover/50 bg-bg-secondary p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold text-text-primary">{story.title}</span>
              <span className="flex gap-2 text-[11px]">
                <button type="button" className="text-accent-blue" onClick={() => {
                  setEditingId(story.id)
                  setCategory((story.tags ?? [])[0] ?? '')
                  setEditingRelations({ source_ids: story.source_ids ?? [], skill_ids: story.skill_ids ?? [], last_used_session: story.last_used_session ?? '' })
                  setDraft({ title: story.title, situation: story.situation, challenge: story.challenge, action: story.action, result: story.result, reflection: story.reflection })
                }}>编辑</button>
                <button type="button" className="text-text-muted hover:text-status-risk" onClick={() => api.intelDeleteStory(story.id).then(load)}>删除</button>
              </span>
            </div>
            <p className="mt-1 text-xs text-text-secondary">{[story.situation, story.action, story.result].filter(Boolean).join(' → ')}</p>
            {(story.source_ids?.length || story.skill_ids?.length || story.last_used_session) ? (
              <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] text-text-muted" aria-label="Story 关联">
                {story.source_ids?.length ? <span className="rounded-full bg-bg-tertiary px-2 py-0.5">来源 {story.source_ids.length}</span> : null}
                {story.skill_ids?.length ? <span className="rounded-full bg-bg-tertiary px-2 py-0.5">技能 {story.skill_ids.length}</span> : null}
                {story.last_used_session ? <span className="rounded-full bg-bg-tertiary px-2 py-0.5">最近用于场次 {story.last_used_session.slice(0, 12)}</span> : null}
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function Skills() {
  const [cards, setCards] = useState<SkillCardOverview[]>([])
  const load = useCallback(() => { api.intelSkillCards().then(setCards).catch(() => setCards([])) }, [])
  useEffect(() => { load() }, [load])
  if (!cards.length) return <p className="p-6 text-sm text-text-muted">还没有技能卡。在「求职 → 岗位目标」的技能卡工作台里生成。</p>
  return (
    <ul className="p-4 space-y-2">
      <li className="text-[11px] text-text-muted">技能卡链路：生成草稿 → 你确认内容属实 → 进入 Interview Pack。未确认的草稿不会被上场使用。</li>
      {cards.map((c) => (
        <li key={c.id} className="flex items-center justify-between gap-3 rounded-xl border border-bg-hover/50 bg-bg-secondary p-3">
          <div>
            <div className="text-sm font-semibold text-text-primary">{c.project_name}</div>
            <div className="text-[11px] text-text-muted">{c.space_title}</div>
          </div>
          <button type="button" aria-pressed={c.user_reviewed}
            onClick={() => api.prepReviewSkillCard(c.id, !c.user_reviewed).then(load)}
            className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${c.user_reviewed ? 'border-status-direct/40 text-status-direct' : 'border-bg-hover text-text-muted'}`}>
            {c.user_reviewed ? '已确认 · 进入 Pack' : '确认内容属实'}
          </button>
        </li>
      ))}
    </ul>
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
