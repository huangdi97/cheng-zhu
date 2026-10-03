import { useEffect, useMemo, useRef, useState } from 'react'
import { Command, FileText, History, Library, Mic, Play, Search, Settings, Target } from 'lucide-react'
import { useUiPrefsStore, type AppMode } from '@/stores/uiPrefsStore'
import { useInterviewStore } from '@/stores/configStore'

type Item = { id: string; label: string; hint: string; icon: typeof Search; mode?: AppMode; action?: () => void }

export default function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement | null>(null)
  const setAppMode = useUiPrefsStore((s) => s.setAppMode)
  const toggleSettings = useInterviewStore((s) => s.toggleSettings)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      const typing = ['input','textarea','select'].includes(target?.tagName?.toLowerCase() ?? '') || target?.isContentEditable
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((v) => !v)
        return
      }
      if (e.key === 'Escape') setOpen(false)
      if (typing) return
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  useEffect(() => { if (open) setTimeout(() => inputRef.current?.focus(), 0) }, [open])

  const items: Item[] = useMemo(() => [
    { id: 'home', label: '回到首页', hint: 'Action Home', icon: Command, mode: 'home' },
    { id: 'goal', label: '打开当前求职目标', hint: 'Goal Room', icon: Target, mode: 'goals' },
    { id: 'practice', label: '开始练习', hint: 'Practice', icon: Play, mode: 'prep' },
    { id: 'live', label: '上场', hint: 'Preflight → Live', icon: Mic, mode: 'assist' },
    { id: 'me', label: '我的成竹', hint: 'Person Workspace', icon: FileText, mode: 'resume-opt' },
    { id: 'library', label: '资料库', hint: 'KB / Quick Notes / Question Banks', icon: Library, mode: 'library' },
    { id: 'history', label: '历史与复盘', hint: 'Sessions / Reflection', icon: History, mode: 'history' },
    { id: 'settings', label: '设置', hint: 'Models / Audio / Privacy / Diagnostics', icon: Settings, action: toggleSettings },
  ], [toggleSettings])

  const visible = items.filter((item) => !query.trim() || (item.label + item.hint).toLowerCase().includes(query.toLowerCase()))

  const run = (item: Item) => {
    item.action?.()
    if (item.mode) setAppMode(item.mode)
    setOpen(false)
    setQuery('')
  }

  if (!open) return null
  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center bg-black/40 px-4 pt-[12vh]" role="dialog" aria-modal="true" aria-label="命令面板" onMouseDown={(e) => { if (e.currentTarget === e.target) setOpen(false) }}>
      <div className="w-full max-w-xl overflow-hidden rounded-2xl border border-bg-hover bg-bg-secondary shadow-2xl">
        <div className="flex items-center gap-2 border-b border-bg-hover px-4 py-3">
          <Search className="h-4 w-4 text-text-muted" />
          <input ref={inputRef} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索命令…"
            className="min-w-0 flex-1 bg-transparent text-sm text-text-primary outline-none" />
          <kbd className="rounded border border-bg-hover px-1.5 py-0.5 text-[10px] text-text-muted">Esc</kbd>
        </div>
        <div className="max-h-[52vh] overflow-y-auto p-2">
          {visible.map((item) => {
            const Icon = item.icon
            return <button key={item.id} type="button" onClick={() => run(item)} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left hover:bg-bg-hover/60">
              <div className="grid h-8 w-8 place-items-center rounded-lg bg-bg-tertiary"><Icon className="h-4 w-4 text-text-secondary" /></div>
              <div className="min-w-0 flex-1"><div className="text-sm font-medium text-text-primary">{item.label}</div><div className="truncate text-[11px] text-text-muted">{item.hint}</div></div>
            </button>
          })}
          {visible.length === 0 && <div className="p-5 text-center text-sm text-text-muted">没有匹配命令</div>}
        </div>
      </div>
    </div>
  )
}
