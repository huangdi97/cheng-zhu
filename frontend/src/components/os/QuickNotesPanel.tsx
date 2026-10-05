/**
 * Quick Notes (canonical §9). First-class notes, global or goal-scoped.
 * A note is never evidence: the panel says so, and selecting a note into a
 * Goal's pack labels it as a user note.
 *
 * ``readOnly`` (Live): notes are shown, not edited, by default.
 * Concurrent edits: saves send ``base_revision``; a 409 shows the newer text.
 */
import { useCallback, useEffect, useState } from 'react'
import { ArrowDown, ArrowUp, Pin } from 'lucide-react'
import { productApi, type QuickNote } from '@/lib/productApi'
import { ActionMenu, EmptyState, ErrorState, inputCls, Loading, PrimaryButton, SecondaryButton } from './ui'

interface Props {
  goalId?: string | null
  readOnly?: boolean
  selectedIds?: string[]
  onSelectionChange?: (ids: string[]) => void
  context?: 'live' | 'library' | 'goal'
  compact?: boolean
}

export default function QuickNotesPanel({ goalId, readOnly = false, selectedIds, onSelectionChange, context = 'library', compact = false }: Props) {
  const [notes, setNotes] = useState<QuickNote[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [draftTitle, setDraftTitle] = useState('')
  const [scope, setScope] = useState<'GLOBAL' | 'GOAL'>(goalId ? 'GOAL' : 'GLOBAL')
  const [editing, setEditing] = useState<{ id: string; title: string; content: string; revision: number } | null>(null)
  const [conflict, setConflict] = useState<QuickNote | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await productApi.quickNotes({ goal_id: goalId ?? undefined, context })
      setNotes(res.items)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }, [goalId, context])
  useEffect(() => { void load() }, [load])

  const create = async () => {
    if (!draft.trim() && !draftTitle.trim()) return
    try {
      await productApi.createQuickNote({ content: draft, title: draftTitle, scope, goal_id: scope === 'GOAL' ? goalId : null })
      setDraft('')
      setDraftTitle('')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    }
  }

  const saveEdit = async () => {
    if (!editing) return
    try {
      await productApi.patchQuickNote(editing.id, { title: editing.title, content: editing.content, base_revision: editing.revision })
      setEditing(null)
      setConflict(null)
      await load()
    } catch (e) {
      const message = e instanceof Error ? e.message : ''
      if (message.includes('409')) {
        const fresh = (await productApi.quickNotes({ goal_id: goalId ?? undefined })).items.find((n) => n.id === editing.id) ?? null
        setConflict(fresh)
      } else {
        setError(message || '保存失败')
      }
    }
  }

  const move = async (index: number, delta: number) => {
    if (!notes) return
    const next = [...notes]
    const [item] = next.splice(index, 1)
    next.splice(index + delta, 0, item)
    setNotes(next)
    await productApi.reorderQuickNotes(next.map((n) => n.id))
  }

  const toggleSelected = (id: string) => {
    if (!onSelectionChange) return
    const current = new Set(selectedIds ?? [])
    if (current.has(id)) current.delete(id)
    else current.add(id)
    onSelectionChange(Array.from(current))
  }

  if (error && !notes) return <ErrorState message={error} onRetry={load} />
  if (!notes) return <Loading />

  return (
    <div className="space-y-2" data-testid="quick-notes-panel">
      {!compact ? <p className="text-[11px] text-text-muted">速记只是你的提醒，不是证据，也不会自动变成已确认的事实。</p> : null}
      {!readOnly ? (
        <form className="rounded-2xl border border-bg-hover/60 p-2 space-y-1.5" onSubmit={(e) => { e.preventDefault(); void create() }}>
          <input aria-label="速记标题" className={inputCls} placeholder="标题（可选），例如：想问" value={draftTitle} onChange={(e) => setDraftTitle(e.target.value)} />
          <textarea aria-label="速记内容" className={`${inputCls} min-h-[56px]`} placeholder="写一条速记…" value={draft} onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); void create() } }} />
          <div className="flex flex-wrap items-center justify-between gap-2">
            {goalId ? (
              <div role="radiogroup" aria-label="速记范围" className="flex gap-1 text-[11px]">
                {(['GOAL', 'GLOBAL'] as const).map((s) => (
                  <button key={s} type="button" role="radio" aria-checked={scope === s} onClick={() => setScope(s)}
                    className={`rounded-full px-2 py-0.5 ${scope === s ? 'bg-container-primary text-container-on-primary' : 'text-text-muted'}`}>
                    {s === 'GOAL' ? '仅这个目标' : '全局'}
                  </button>
                ))}
              </div>
            ) : <span />}
            <PrimaryButton type="submit" disabled={!draft.trim() && !draftTitle.trim()}>添加速记</PrimaryButton>
          </div>
        </form>
      ) : null}
      {error ? <p role="alert" className="text-xs text-status-risk">{error}</p> : null}
      {!notes.length ? <EmptyState title="还没有速记" body={readOnly ? '在资料库或目标里添加速记，上场时可以在这里查看。' : '记下想问的问题、要强调的数字或容易忘的点。'} /> : null}
      <ul className="space-y-1.5">
        {notes.map((note, i) => (
          <li key={note.id} className="rounded-xl border border-bg-hover/50 bg-bg-secondary/50 p-2.5">
            {editing?.id === note.id ? (
              <div className="space-y-1.5">
                <input aria-label="编辑标题" className={inputCls} value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} />
                <textarea aria-label="编辑内容" className={`${inputCls} min-h-[56px]`} value={editing.content} onChange={(e) => setEditing({ ...editing, content: e.target.value })} />
                {conflict ? (
                  <div role="alert" className="rounded-lg border border-status-inferred/30 bg-status-inferred/5 p-2 text-[11px] text-text-secondary">
                    这条速记已在别处修改：「{conflict.content.slice(0, 80)}」
                    <div className="mt-1 flex gap-2">
                      <SecondaryButton onClick={() => { setEditing({ id: conflict.id, title: conflict.title, content: conflict.content, revision: conflict.revision }); setConflict(null) }}>使用最新内容</SecondaryButton>
                      <SecondaryButton onClick={() => { setEditing({ ...editing, revision: conflict.revision }); setConflict(null) }}>保留我的修改</SecondaryButton>
                    </div>
                  </div>
                ) : null}
                <div className="flex gap-2">
                  <PrimaryButton onClick={() => void saveEdit()}>保存</PrimaryButton>
                  <SecondaryButton onClick={() => { setEditing(null); setConflict(null) }}>取消</SecondaryButton>
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-2">
                {onSelectionChange ? (
                  <input type="checkbox" className="mt-1" aria-label={`带入本目标的上场内容：${note.title || note.content.slice(0, 20)}`}
                    checked={(selectedIds ?? []).includes(note.id)} onChange={() => toggleSelected(note.id)} />
                ) : null}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    {note.pinned ? <Pin className="h-3 w-3 text-accent-amber" aria-label="已置顶" /> : null}
                    {note.title ? <span className="text-xs font-semibold text-text-primary">{note.title}</span> : null}
                    <span className="text-[10px] text-text-muted">{note.scope === 'GLOBAL' ? '全局' : '目标'}</span>
                  </div>
                  <p className="whitespace-pre-wrap break-words text-xs text-text-secondary">{note.content}</p>
                </div>
                {!readOnly ? (
                  <div className="flex items-center">
                    <button type="button" aria-label="上移" disabled={i === 0} onClick={() => void move(i, -1)} className="rounded p-1 text-text-muted hover:bg-bg-hover disabled:opacity-30"><ArrowUp className="h-3.5 w-3.5" aria-hidden /></button>
                    <button type="button" aria-label="下移" disabled={i === notes.length - 1} onClick={() => void move(i, 1)} className="rounded p-1 text-text-muted hover:bg-bg-hover disabled:opacity-30"><ArrowDown className="h-3.5 w-3.5" aria-hidden /></button>
                    <ActionMenu label="速记操作" actions={[
                      { key: 'edit', label: '编辑', onSelect: () => setEditing({ id: note.id, title: note.title, content: note.content, revision: note.revision }) },
                      { key: 'pin', label: note.pinned ? '取消置顶' : '置顶', onSelect: () => void productApi.patchQuickNote(note.id, { pinned: !note.pinned, base_revision: note.revision }).then(load) },
                      { key: 'delete', label: '删除', danger: true, onSelect: () => void productApi.deleteQuickNote(note.id).then(load) },
                    ]} />
                  </div>
                ) : null}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
