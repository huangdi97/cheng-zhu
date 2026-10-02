/** Ctrl+K Command Palette — context-ranked, keyboard-first, executes real actions. */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Command as CommandIcon } from 'lucide-react'
import { useRouter } from '@/lib/router'
import { useOsStore } from '@/stores/osStore'
import { buildCommands, contextOf, executeCommand, rankCommands, type CommandContext } from './commands'

const CONTEXT_LABEL: Record<CommandContext, string> = {
  home: '首页', goal: '求职目标', live: '上场', me: '我的成竹', practice: '练习', global: '全局',
}

export default function CommandPalette() {
  const open = useOsStore((s) => s.commandPaletteOpen)
  const setOpen = useOsStore((s) => s.setCommandPalette)
  const goalId = useOsStore((s) => s.contextGoalId ?? s.live?.goalId ?? null)
  const route = useRouter((s) => s.route)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const context = contextOf(route)
  const commands = useMemo(() => (open ? rankCommands(buildCommands(goalId), query, context) : []), [open, goalId, query, context])

  useEffect(() => {
    if (open) {
      setQuery('')
      setActive(0)
      setError(null)
      window.setTimeout(() => inputRef.current?.focus(), 0)
    }
  }, [open])
  useEffect(() => setActive(0), [query])

  if (!open) return null
  const run = async (index: number) => {
    const cmd = commands[index]
    if (!cmd) return
    try {
      setOpen(false)
      await executeCommand(cmd, context)
    } catch (e) {
      setOpen(true)
      setError(e instanceof Error ? e.message : '执行失败')
    }
  }
  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-black/30 p-4 pt-[12vh]" onMouseDown={(e) => { if (e.target === e.currentTarget) setOpen(false) }}>
      <div role="dialog" aria-modal="true" aria-label="命令面板" className="w-full max-w-lg overflow-hidden rounded-2xl border border-bg-hover bg-bg-primary shadow-2xl" data-testid="command-palette">
        <div className="flex items-center gap-2 border-b border-bg-tertiary px-3">
          <CommandIcon className="h-4 w-4 text-text-muted" aria-hidden />
          <input ref={inputRef} role="combobox" aria-expanded="true" aria-controls="command-list" aria-activedescendant={commands[active] ? `cmd-${commands[active].id}` : undefined}
            aria-label="搜索命令" placeholder={`在「${CONTEXT_LABEL[context]}」中执行…`} value={query} onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') { e.preventDefault(); setOpen(false) }
              if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => Math.min(commands.length - 1, i + 1)) }
              if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(0, i - 1)) }
              if (e.key === 'Enter') { e.preventDefault(); void run(active) }
            }}
            className="w-full bg-transparent py-3 text-sm text-text-primary outline-none placeholder:text-text-muted" />
          <kbd className="rounded border border-bg-hover px-1 text-[10px] text-text-muted">Esc</kbd>
        </div>
        {error ? <p role="alert" className="px-3 py-2 text-xs text-status-risk">{error}</p> : null}
        <ul id="command-list" role="listbox" aria-label="命令" className="max-h-[50vh] overflow-y-auto p-1">
          {commands.length ? commands.map((c, i) => (
            <li key={c.id} id={`cmd-${c.id}`} role="option" aria-selected={i === active}>
              <button type="button" tabIndex={-1} onMouseEnter={() => setActive(i)} onClick={() => void run(i)}
                className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm ${i === active ? 'bg-bg-hover text-text-primary' : 'text-text-secondary'}`}>
                <span>{c.label}</span>
                <span className="text-[10px] text-text-muted">{c.contexts.includes(context) ? CONTEXT_LABEL[context] : CONTEXT_LABEL[c.contexts[0]]}</span>
              </button>
            </li>
          )) : <li className="px-3 py-4 text-center text-xs text-text-muted">没有匹配的命令</li>}
        </ul>
      </div>
    </div>
  )
}
