import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Plus, Search } from 'lucide-react'
import { conversationApi } from '@/lib/conversationApi'
import type { ConversationProfile } from '@/lib/conversationContracts'
import { navigate, paths } from '@/lib/router'
import { EmptyState, ErrorState, Field, Loading, Page, PageHeader, PrimaryButton, SecondaryButton, StatusBadge, formatWhen, inputCls, useAsync } from '@/components/os/ui'

const MODE_LABEL: Record<string, string> = {
  QUIET: '安静',
  BALANCED: '平衡',
  ACTIVE: '主动',
  PRESENTATION: '演示',
  ONE_ON_ONE: '1:1',
}

export default function ConversationSpacesPage({ query = {} }: { query?: Record<string, string> }) {
  const spaces = useAsync(() => conversationApi.spaces(), [])
  const templates = useAsync(() => conversationApi.templates(), [])
  const [showCreate, setShowCreate] = useState(query.new === '1')
  const [title, setTitle] = useState('')
  const [profile, setProfile] = useState<ConversationProfile>('PROJECT_SYNC')
  const [goal, setGoal] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [searchType, setSearchType] = useState(query.find ?? '')
  const [searchText, setSearchText] = useState(query.q ?? '')
  const [searchBusy, setSearchBusy] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [searchResults, setSearchResults] = useState<Awaited<ReturnType<typeof conversationApi.searchItems>>['items']>([])
  const templateMap = useMemo(() => new Map((templates.data?.items ?? []).map((x) => [x.key, x])), [templates.data])
  const groups = useMemo(() => {
    const now = Date.now() / 1000
    const recentCutoff = now - 7 * 24 * 3600
    const result: Array<{ key: string; label: string; items: NonNullable<typeof spaces.data>['items'] }> = [
      { key: 'upcoming', label: '即将发生', items: [] },
      { key: 'recent', label: '最近发生', items: [] },
      { key: 'active', label: '持续进行', items: [] },
      { key: 'archived', label: '已归档', items: [] },
    ]
    for (const space of spaces.data?.items ?? []) {
      if (space.status === 'ARCHIVED') result[3].items.push(space)
      else if (space.next_session?.scheduled_at && space.next_session.scheduled_at >= now) result[0].items.push(space)
      else if ((space.last_session?.ended_at ?? space.updated_at) >= recentCutoff) result[1].items.push(space)
      else result[2].items.push(space)
    }
    return result.filter((group) => group.items.length)
  }, [spaces.data])

  const searchItems = async (type = searchType, q = searchText) => {
    setSearchBusy(true); setSearchError('')
    try {
      const result = await conversationApi.searchItems(q.trim(), type, 80)
      setSearchResults(result.items)
    } catch (e) {
      setSearchError(e instanceof Error ? e.message : String(e))
    } finally { setSearchBusy(false) }
  }

  useEffect(() => {
    if (query.find || query.q) void searchItems(query.find ?? '', query.q ?? '')
    // Route query is the command-palette entry point; do not re-run on typing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.find, query.q])

  const create = async () => {
    if (!title.trim()) return
    setSaving(true); setSaveError('')
    try {
      const row = await conversationApi.createSpace({ title: title.trim(), profile, default_goal: goal.trim() })
      setTitle(''); setGoal(''); setShowCreate(false)
      await spaces.reload()
      navigate(paths.conversationSpace(row.id))
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e))
    } finally { setSaving(false) }
  }

  return (
    <Page testId="conversation-spaces">
      <PageHeader title="对话空间" subtitle="把会反复发生的对话放在同一个空间里，让承诺、决策和未解决问题跨场延续。"
        actions={<PrimaryButton onClick={() => setShowCreate(true)} icon={<Plus className="h-3.5 w-3.5" />}>新建空间</PrimaryButton>} />

      <section className="mb-5 border-y border-bg-tertiary/70 py-3" aria-label="Conversation 全局查找" data-testid="conversation-search">
        <div className="flex flex-wrap items-center gap-2">
          <Search className="h-4 w-4 text-accent-blue" aria-hidden />
          <h2 className="text-sm font-semibold text-text-primary">查找承诺、决策和开放问题</h2>
          <span className="text-[11px] text-text-muted">每条结果都会保留它来自哪个空间、哪场会话和什么时间。</span>
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-[180px_minmax(0,1fr)_auto]">
          <select className={inputCls} value={searchType} onChange={(e) => setSearchType(e.target.value)}>
            <option value="">全部类型</option>
            <option value="Decision">决策</option>
            <option value="Commitment">承诺 / 任务</option>
            <option value="OpenQuestion">开放问题</option>
          </select>
          <input className={inputCls} value={searchText} onChange={(e) => setSearchText(e.target.value)} placeholder="关键词可为空；为空时按最近更新返回" onKeyDown={(e) => { if (e.key === 'Enter') void searchItems() }} />
          <SecondaryButton onClick={() => void searchItems()} disabled={searchBusy}>{searchBusy ? '查找中…' : '查找'}</SecondaryButton>
        </div>
        {searchError ? <div className="mt-3"><ErrorState message={searchError} /></div> : null}
        {(query.find || query.q || searchResults.length > 0) ? (
          <div className="mt-4 space-y-2">
            {searchResults.length ? searchResults.map((item) => (
              <button key={item.id} type="button"
                onClick={() => navigate(paths.conversationSpace(item.space_id, item.type === 'Decision' ? 'decisions' : 'overview'))}
                className="w-full rounded-xl border border-bg-tertiary/70 bg-bg-primary/55 px-3 py-2 text-left hover:bg-bg-hover/45">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge tone={item.review_status === 'AI_EXTRACTED' ? 'warn' : 'ok'}>{item.type}</StatusBadge>
                  <StatusBadge tone="muted">{item.state}</StatusBadge>
                  <span className="min-w-0 flex-1 truncate text-xs font-semibold text-text-primary">{item.title}</span>
                </div>
                <div className="mt-1 text-[11px] text-text-muted">{item.space_title} · {item.session_title || '未命名 Session'} · {formatWhen(item.updated_at || item.created_at)}</div>
                <div className="mt-1 text-[10px] text-text-muted">来源：{item.source_refs.length ? item.source_refs.map((ref) => ref.kind).join(' · ') : '未附来源'} · review={item.review_status}</div>
              </button>
            )) : <p className="text-xs text-text-muted">没有找到符合条件的结构化 Conversation Item。</p>}
          </div>
        ) : null}
      </section>

      {showCreate ? (
        <section className="mb-5 border-y border-accent-blue/25 bg-accent-blue/[0.025] py-4" aria-label="新建对话空间">
          <div className="mb-3">
            <h2 className="text-sm font-semibold text-text-primary">新建一个持续对话</h2>
            <p className="mt-0.5 text-[11px] text-text-muted">空间应该代表一个会重复发生的关系或工作主题，而不是一次会议。</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="空间名称"><input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例如：PDIG · Android Architecture" autoFocus /></Field>
            <Field label="场景模板">
              <select className={inputCls} value={profile} onChange={(e) => setProfile(e.target.value as ConversationProfile)}>
                {(templates.data?.items ?? []).map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
              </select>
            </Field>
          </div>
          <div className="mt-3"><Field label="希望持续达成什么（可选）"><input className={inputCls} value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="例如：把 conflict merge strategy 做成明确 Decision" /></Field></div>
          <div className="mt-3 border-l-2 border-bg-tertiary/80 pl-3 text-[11px] text-text-muted">
            <p>默认帮助方式：{MODE_LABEL[templateMap.get(profile)?.default_mode ?? 'BALANCED'] ?? templateMap.get(profile)?.default_mode ?? '平衡'}；每一场开始前都可以单独调整。</p>
            {templateMap.get(profile)?.playbook?.closing_objective ? (
              <p className="mt-1 text-text-secondary">这个场景通常希望最后留下：{templateMap.get(profile)!.playbook.closing_objective}</p>
            ) : null}
          </div>
          {saveError ? <div className="mt-3"><ErrorState message={saveError} /></div> : null}
          <div className="mt-4 flex gap-2"><PrimaryButton onClick={create} disabled={saving || !title.trim()}>{saving ? '创建中…' : '创建空间'}</PrimaryButton><SecondaryButton onClick={() => setShowCreate(false)}>取消</SecondaryButton></div>
        </section>
      ) : null}

      {spaces.loading ? <Loading /> : spaces.error ? <ErrorState message={spaces.error} onRetry={spaces.reload} /> : (spaces.data?.items.length ?? 0) === 0 ? (
        <EmptyState title="还没有空间" body="推荐先用项目同步或设计评审验证真实价值。" action={<PrimaryButton onClick={() => setShowCreate(true)}>新建空间</PrimaryButton>} />
      ) : (
        <div className="space-y-6">
          {groups.map((group) => (
            <section key={group.key} aria-label={group.label}>
              <div className="mb-2 flex items-center gap-2">
                <h2 className="text-xs font-semibold text-text-secondary">{group.label}</h2>
                <span className="text-[10px] text-text-muted">{group.items.length}</span>
              </div>
              <div className="space-y-2">
                {group.items.map((space) => (
                  <button key={space.id} type="button" onClick={() => navigate(paths.conversationSpace(space.id))}
                    className="group flex w-full items-center justify-between border-b border-bg-tertiary/70 px-1 py-3.5 text-left first:border-t hover:bg-bg-hover/20">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate text-sm font-semibold text-text-primary">{space.title}</span>
                        <StatusBadge tone={space.status === 'ARCHIVED' ? 'muted' : 'info'}>{templateMap.get(space.profile)?.label ?? space.profile}</StatusBadge>
                        {space.next_session ? <StatusBadge tone="busy">{formatWhen(space.next_session.scheduled_at)}</StatusBadge> : null}
                      </div>
                      <p className="mt-1 truncate text-xs text-text-secondary">{space.default_goal || '尚未设置长期目标'}</p>
                      <p className="mt-1 text-[11px] text-text-muted">{space.open_commitments_count ?? 0} 个未完成承诺 · {space.open_questions_count ?? 0} 个开放问题 · {MODE_LABEL[space.default_mode] ?? space.default_mode}</p>
                    </div>
                    <ArrowRight className="h-4 w-4 flex-shrink-0 text-text-muted group-hover:text-text-primary" />
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </Page>
  )
}
