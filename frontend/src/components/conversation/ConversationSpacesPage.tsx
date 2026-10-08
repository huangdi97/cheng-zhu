import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Plus, Search } from 'lucide-react'
import { conversationApi } from '@/lib/conversationApi'
import type { ConversationProfile } from '@/lib/conversationContracts'
import { navigate, paths } from '@/lib/router'
import { EmptyState, ErrorState, Field, Loading, Page, PageHeader, PrimaryButton, SecondaryButton, StatusBadge, formatWhen, inputCls, useAsync } from '@/components/os/ui'

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
      { key: 'upcoming', label: 'Upcoming', items: [] },
      { key: 'recent', label: '最近', items: [] },
      { key: 'active', label: 'Active', items: [] },
      { key: 'archived', label: 'Archived', items: [] },
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
      <PageHeader title="对话空间" subtitle="一个 Space 承载多场连续对话，而不是一张会议文件夹。"
        actions={<PrimaryButton onClick={() => setShowCreate(true)} icon={<Plus className="h-3.5 w-3.5" />}>新建空间</PrimaryButton>} />

      <section className="mb-5 rounded-2xl border border-bg-tertiary/70 bg-bg-secondary/20 p-4" aria-label="Conversation 全局查找" data-testid="conversation-search">
        <div className="flex flex-wrap items-center gap-2">
          <Search className="h-4 w-4 text-accent-blue" aria-hidden />
          <h2 className="text-sm font-semibold text-text-primary">查找长期对话事实</h2>
          <span className="text-[11px] text-text-muted">只返回结构化 Item；每条结果带 Space / Session / 时间 / provenance。</span>
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-[180px_minmax(0,1fr)_auto]">
          <select className={inputCls} value={searchType} onChange={(e) => setSearchType(e.target.value)}>
            <option value="">全部 Item</option>
            <option value="Decision">Decision</option>
            <option value="Commitment">Commitment / Task</option>
            <option value="OpenQuestion">Open Question</option>
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
        <div className="mb-5 rounded-2xl border border-accent-blue/25 bg-accent-blue/5 p-4">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="空间名称"><input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例如：PDIG · Android Architecture" autoFocus /></Field>
            <Field label="场景模板">
              <select className={inputCls} value={profile} onChange={(e) => setProfile(e.target.value as ConversationProfile)}>
                {(templates.data?.items ?? []).map((item) => <option key={item.key} value={item.key}>{item.label}{item.launch_wedge ? ' · 首发验证' : ' · 共享 runtime'}</option>)}
              </select>
            </Field>
          </div>
          <div className="mt-3"><Field label="希望持续达成什么（可选）"><input className={inputCls} value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="例如：把 conflict merge strategy 做成明确 Decision" /></Field></div>
          <div className="mt-3 rounded-xl border border-bg-tertiary/70 bg-bg-secondary/25 p-3 text-[11px] text-text-muted">
            <div>默认帮助方式：{templateMap.get(profile)?.default_mode ?? 'BALANCED'}。后续每场 Preflight 可单独选择。</div>
            {templateMap.get(profile)?.playbook ? <div className="mt-2 rounded-lg bg-bg-primary/45 p-2.5">
              <div className="font-semibold text-text-secondary">本 Profile 的 Closing Objective</div>
              <div className="mt-1 text-text-primary">{templateMap.get(profile)!.playbook.closing_objective}</div>
              <div className="mt-2 space-y-1">{templateMap.get(profile)!.playbook.success_conditions.slice(0, 3).map((item) => <div key={item}>• {item}</div>)}</div>
              <div className="mt-2 text-text-muted">Priority truth · {templateMap.get(profile)!.playbook.priority_truth_types.join(' · ')}</div>
            </div> : null}
            {templateMap.get(profile)?.launch_wedge ? (
              <div className="mt-1 text-text-secondary">成熟度 · BETA_WEDGE：这是当前首发验证楔子；runtime 可用，但 stable release / real-user validation 仍未成立。</div>
            ) : (
              <div className="mt-1 text-text-secondary">成熟度 · SHARED_RUNTIME_TEMPLATE：共享 Conversation runtime 可用，但该场景的 specialized behavior 尚未单独验证。</div>
            )}
          </div>
          {saveError ? <div className="mt-3"><ErrorState message={saveError} /></div> : null}
          <div className="mt-4 flex gap-2"><PrimaryButton onClick={create} disabled={saving || !title.trim()}>{saving ? '创建中…' : '创建'}</PrimaryButton><SecondaryButton onClick={() => setShowCreate(false)}>取消</SecondaryButton></div>
        </div>
      ) : null}

      {spaces.loading ? <Loading /> : spaces.error ? <ErrorState message={spaces.error} onRetry={spaces.reload} /> : (spaces.data?.items.length ?? 0) === 0 ? (
        <EmptyState title="还没有空间" body="推荐先用项目同步或设计评审验证真实价值。" action={<PrimaryButton onClick={() => setShowCreate(true)}>新建空间</PrimaryButton>} />
      ) : (
        <div className="space-y-6">
          {groups.map((group) => (
            <section key={group.key} aria-label={group.label}>
              <div className="mb-2 flex items-center gap-2">
                <h2 className="text-xs font-semibold uppercase tracking-wide text-text-secondary">{group.label}</h2>
                <span className="text-[10px] text-text-muted">{group.items.length}</span>
              </div>
              <div className="space-y-2">
                {group.items.map((space) => (
                  <button key={space.id} type="button" onClick={() => navigate(paths.conversationSpace(space.id))}
                    className="group flex w-full items-center justify-between rounded-2xl border border-bg-tertiary/70 bg-bg-secondary/30 px-4 py-3 text-left hover:bg-bg-hover/45">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate text-sm font-semibold text-text-primary">{space.title}</span>
                        <StatusBadge tone={space.status === 'ARCHIVED' ? 'muted' : 'info'}>{templateMap.get(space.profile)?.label ?? space.profile}</StatusBadge>
                        {space.next_session ? <StatusBadge tone="busy">{formatWhen(space.next_session.scheduled_at)}</StatusBadge> : null}
                      </div>
                      <p className="mt-1 truncate text-xs text-text-muted">{space.default_goal || '尚未设置长期对话目标'} · {space.default_mode}</p>
                      <p className="mt-1 text-[11px] text-text-muted">{space.open_commitments_count ?? 0} open commitments · {space.open_questions_count ?? 0} open questions</p>
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
