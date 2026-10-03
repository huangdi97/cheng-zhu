import { useCallback, useEffect, useState } from 'react'
import { FilePlus2, Pin, Save, Trash2 } from 'lucide-react'
import { api, type QuickNote } from '@/lib/api'

export default function QuickNotesPanel({ goalId }: { goalId?: number | null }) {
  const [items, setItems] = useState<QuickNote[]>([])
  const [draft, setDraft] = useState({ title: '', content: '', scope: goalId ? 'GOAL' : 'GLOBAL' })
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api.productQuickNotes(goalId ?? undefined).then((r) => setItems(r.items ?? [])).catch(() => setItems([]))
  }, [goalId])
  useEffect(() => { load() }, [load])

  const create = async () => {
    if (!draft.title.trim()) return
    setBusy(true)
    try {
      await api.productCreateQuickNote({
        title: draft.title,
        content: draft.content,
        scope: draft.scope,
        goal_id: draft.scope === 'GOAL' ? goalId ?? undefined : undefined,
      })
      setDraft({ title: '', content: '', scope: goalId ? 'GOAL' : 'GLOBAL' })
      load()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4" data-testid="quick-notes-panel">
      <div className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-text-primary"><FilePlus2 className="h-4 w-4 text-accent-blue" /> 新建 Quick Note</div>
        <p className="mt-1 text-[11px] text-text-muted">这是你写给自己看的现场短笔记，不是 Evidence、KB 或长期事实。</p>
        <div className="mt-3 grid gap-2 md:grid-cols-[1fr_auto]">
          <input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} placeholder="标题"
            className="rounded-xl border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary" />
          <select value={draft.scope} onChange={(e) => setDraft({ ...draft, scope: e.target.value })}
            className="rounded-xl border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary">
            {goalId && <option value="GOAL">当前 Goal</option>}
            <option value="GLOBAL">全局</option>
          </select>
        </div>
        <textarea value={draft.content} onChange={(e) => setDraft({ ...draft, content: e.target.value })} rows={4} placeholder={'Redis\n- session state\n- 没用过 Cluster\n\n想问\n- production scale'}
          className="mt-2 w-full rounded-xl border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary" />
        <button type="button" onClick={() => void create()} disabled={busy || !draft.title.trim()}
          className="mt-2 inline-flex items-center gap-1.5 rounded-xl bg-container-primary px-3 py-2 text-xs font-semibold text-container-on-primary disabled:opacity-50">
          <Save className="h-3.5 w-3.5" /> 保存
        </button>
      </div>

      <div className="space-y-2">
        {items.length === 0 && <div className="rounded-xl border border-dashed border-bg-hover p-5 text-sm text-text-muted">还没有 Quick Note。</div>}
        {items.map((note) => (
          <article key={note.id} className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  {Boolean(note.pinned) && <Pin className="h-3.5 w-3.5 text-accent-amber" />}
                  <h4 className="truncate text-sm font-semibold text-text-primary">{note.title}</h4>
                  <span className="rounded-full border border-bg-hover px-2 py-0.5 text-[10px] text-text-muted">{note.scope === 'GLOBAL' ? '全局' : 'Goal'}</span>
                </div>
                <pre className="mt-2 whitespace-pre-wrap font-sans text-xs leading-relaxed text-text-secondary">{note.content}</pre>
              </div>
              <div className="flex gap-1">
                <button type="button" aria-label={note.pinned ? '取消置顶' : '置顶'} onClick={() => api.productPatchQuickNote(note.id, { pinned: !Boolean(note.pinned) }).then(load)}
                  className="rounded-lg p-1.5 text-text-muted hover:bg-bg-hover hover:text-text-primary"><Pin className="h-3.5 w-3.5" /></button>
                <button type="button" aria-label="删除 Quick Note" onClick={() => api.productDeleteQuickNote(note.id).then(load)}
                  className="rounded-lg p-1.5 text-text-muted hover:bg-status-risk/10 hover:text-status-risk"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
