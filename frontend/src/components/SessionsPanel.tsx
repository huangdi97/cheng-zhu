import { useEffect, useRef, useState } from 'react'
import { Layers, Plus, Trash2, Check, Pencil } from 'lucide-react'
import { useInterviewStore } from '@/stores/configStore'
import { api, getErrorMessage } from '@/lib/api'

/** 会话列表面板：新建/切换/重命名/删除（供「工作台」popover 使用）。 */
export default function SessionsPanel() {
  const sessions = useInterviewStore((s) => s.sessions)
  const activeSessionId = useInterviewStore((s) => s.activeSessionId)
  const setSessions = useInterviewStore((s) => s.setSessions)
  const pushToast = useInterviewStore((s) => s.pushToast)
  const [label, setLabel] = useState('')
  const [creating, setCreating] = useState(false)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameDraft, setRenameDraft] = useState('')
  const [highlightIndex, setHighlightIndex] = useState(-1)

  useEffect(() => {
    let cancelled = false
    api.sessionsList()
      .then((res) => {
        if (!cancelled) setSessions(res.items, res.active_id)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [setSessions])

  const refresh = async () => {
    try {
      const res = await api.sessionsList()
      setSessions(res.items, res.active_id)
    } catch { /* ignore */ }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const dir = e.key === 'ArrowDown' ? 1 : -1
      setHighlightIndex((prev) => {
        if (sessions.length === 0) return -1
        const next = prev < 0 ? 0 : Math.min(sessions.length - 1, Math.max(0, prev + dir))
        return next
      })
    }
    if (e.key === 'Enter' && highlightIndex >= 0 && highlightIndex < sessions.length) {
      e.preventDefault()
      const target = sessions[highlightIndex]
      if (target && target.id !== activeSessionId) void handleActivate(target.id)
    }
  }

  const handleCreate = async () => {
    if (creating) return
    setCreating(true)
    try {
      await api.sessionsCreate(label.trim())
      setLabel('')
      void refresh()
    } catch (err) {
      pushToast(getErrorMessage(err, '新建会话失败'), 'error')
    } finally {
      setCreating(false)
    }
  }

  const handleActivate = async (id: string) => {
    try {
      await api.sessionsActivate(id)
    } catch (err) {
      pushToast(getErrorMessage(err, '切换会话失败'), 'error')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await api.sessionsDelete(id)
      void refresh()
    } catch (err) {
      pushToast(getErrorMessage(err, '删除会话失败'), 'error')
    }
  }

  const commitRename = async (id: string) => {
    const next = renameDraft.trim()
    setRenamingId(null)
    if (!next) return
    try {
      await api.sessionsRename(id, next)
      void refresh()
    } catch (err) {
      pushToast(getErrorMessage(err, '重命名失败'), 'error')
    }
  }

  return (
    <div onKeyDown={handleKeyDown}>
      <div className="flex items-center gap-1.5">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') void handleCreate() }}
          placeholder="新会话名称（如：腾讯一面）"
          aria-label="新会话名称"
          className="flex-1 min-w-0 rounded-lg border border-bg-hover bg-bg-tertiary px-2.5 py-1.5 text-xs text-text-primary outline-none focus:border-accent-blue/60"
        />
        <button
          type="button"
          onClick={() => void handleCreate()}
          disabled={creating || !label.trim()}
          className="inline-flex items-center gap-1 rounded-lg bg-accent-blue px-2.5 py-1.5 text-xs font-medium text-white hover:bg-accent-blue/90 disabled:opacity-50"
        >
          <Plus className="w-3.5 h-3.5" />
          新建
        </button>
      </div>

      <div className="mt-2 max-h-64 overflow-y-auto space-y-1" role="listbox" aria-label="会话列表">
        {sessions.length === 0 && (
          <p className="px-2 py-3 text-[11px] text-text-muted text-center">暂无会话，先新建一场</p>
        )}
        {sessions.map((sess, idx) => {
          const active = sess.id === activeSessionId || sess.is_active
          const highlighted = idx === highlightIndex
          const renaming = renamingId === sess.id
          return (
            <div
              key={sess.id}
              role="option"
              aria-selected={active}
              className={`flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs transition-colors ${
                active
                  ? 'bg-accent-blue/10 text-accent-blue border border-accent-blue/25'
                  : highlighted
                    ? 'bg-bg-tertiary/70 text-text-secondary cursor-pointer border border-bg-hover/40'
                    : 'text-text-secondary hover:bg-bg-tertiary/60 cursor-pointer border border-transparent'
              }`}
              onClick={() => { if (!active && !renaming) void handleActivate(sess.id) }}
            >
              {active ? <Check className="w-3.5 h-3.5 flex-shrink-0" /> : <Layers className="w-3.5 h-3.5 flex-shrink-0 opacity-60" />}
              {renaming ? (
                <input
                  autoFocus
                  value={renameDraft}
                  onChange={(e) => setRenameDraft(e.target.value)}
                  onBlur={() => void commitRename(sess.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') { e.stopPropagation(); void commitRename(sess.id) }
                    if (e.key === 'Escape') { e.stopPropagation(); setRenamingId(null) }
                  }}
                  aria-label="重命名会话"
                  className="flex-1 min-w-0 rounded border border-accent-blue/50 bg-bg-primary px-1.5 py-0.5 text-xs text-text-primary outline-none"
                />
              ) : (
                <span className="flex-1 min-w-0 truncate font-medium">{sess.label || '未命名会话'}</span>
              )}
              {sess.is_recording && <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse" title="录制中" />}
              <span className="text-[10px] text-text-muted tabular-nums">{sess.qa_count} 题</span>
              {!renaming && (
                <button
                  type="button"
                  title="重命名会话"
                  aria-label={`重命名会话 ${sess.label || ''}`}
                  onClick={(e) => { e.stopPropagation(); setRenamingId(sess.id); setRenameDraft(sess.label || '') }}
                  className="rounded p-1 text-text-muted hover:text-accent-blue"
                >
                  <Pencil className="w-3 h-3" />
                </button>
              )}
              {!active && !renaming && (
                <button
                  type="button"
                  title="删除该会话"
                  aria-label={`删除会话 ${sess.label || ''}`}
                  onClick={(e) => { e.stopPropagation(); void handleDelete(sess.id) }}
                  className="rounded p-1 text-text-muted hover:text-accent-red"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
