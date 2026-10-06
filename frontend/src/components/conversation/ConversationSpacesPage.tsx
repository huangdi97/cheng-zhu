import { useMemo, useState } from 'react'
import { ArrowRight, Plus } from 'lucide-react'
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

      {showCreate ? (
        <div className="mb-5 rounded-2xl border border-accent-blue/25 bg-accent-blue/5 p-4">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="空间名称"><input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例如：PDIG · Android Architecture" autoFocus /></Field>
            <Field label="场景模板">
              <select className={inputCls} value={profile} onChange={(e) => setProfile(e.target.value as ConversationProfile)}>
                {(templates.data?.items ?? []).map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
              </select>
            </Field>
          </div>
          <div className="mt-3"><Field label="希望持续达成什么（可选）"><input className={inputCls} value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="例如：把 conflict merge strategy 做成明确 Decision" /></Field></div>
          <div className="mt-3 text-[11px] text-text-muted">默认帮助方式：{templateMap.get(profile)?.default_mode ?? 'BALANCED'}。后续每场 Preflight 可单独选择。</div>
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
