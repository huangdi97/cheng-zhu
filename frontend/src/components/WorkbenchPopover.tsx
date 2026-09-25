import { useEffect, useRef, useState } from 'react'
import { LayoutDashboard, Layers, NotebookPen, Pin, PinOff, Sparkles } from 'lucide-react'
import SessionsPanel from './SessionsPanel'
import MemoPanel from './MemoPanel'

interface Props {
  memoPinned: boolean
  onToggleMemoPin: () => void
}

export default function WorkbenchPopover({ memoPinned, onToggleMemoPin }: Props) {
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<'sessions' | 'memo'>('sessions')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title="面试工作台：多场会话 + 滚动备忘"
        aria-haspopup="dialog"
        aria-expanded={open}
        className={`relative inline-flex items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-xs border transition-all duration-200 flex-shrink-0 ${
          open
            ? 'border-accent-blue/50 bg-accent-blue/10 text-accent-blue'
            : 'border-bg-hover/50 bg-bg-tertiary/50 text-text-secondary hover:border-accent-blue/40 hover:text-text-primary'
        }`}
      >
        <LayoutDashboard className="w-3.5 h-3.5" />
        <span className="font-medium hidden sm:inline">工作台</span>
        <span className="rounded-full bg-accent-blue/15 text-accent-blue p-1"><Sparkles className="w-3 h-3" aria-hidden /></span>
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="面试工作台"
          className="absolute right-0 top-full mt-1.5 z-50 w-[340px] glass-popover rounded-2xl p-2 animate-fade-up"
        >
          <div className="flex items-center gap-1 border-b border-bg-tertiary/50 px-1 pb-2 mb-2">
            <button
              type="button"
              onClick={() => setTab('sessions')}
              aria-pressed={tab === 'sessions'}
              className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors ${
                tab === 'sessions' ? 'bg-accent-blue/10 text-accent-blue' : 'text-text-muted hover:text-text-primary'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              会话
            </button>
            <button
              type="button"
              onClick={() => setTab('memo')}
              aria-pressed={tab === 'memo'}
              className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors ${
                tab === 'memo' ? 'bg-accent-blue/10 text-accent-blue' : 'text-text-muted hover:text-text-primary'
              }`}
            >
              <NotebookPen className="w-3.5 h-3.5" />
              备忘
            </button>
            {tab === 'memo' && (
              <button
                type="button"
                onClick={onToggleMemoPin}
                title={memoPinned ? '取消固定到右侧面板' : '固定到右侧面板（面试中常驻显示）'}
                aria-pressed={memoPinned}
                className={`ml-auto inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[10px] font-medium transition-colors ${
                  memoPinned ? 'bg-accent-green/10 text-accent-green' : 'text-text-muted hover:text-text-primary'
                }`}
              >
                {memoPinned ? <PinOff className="w-3 h-3" /> : <Pin className="w-3 h-3" />}
                {memoPinned ? '已固定' : '固定右侧'}
              </button>
            )}
          </div>

          {tab === 'sessions' ? (
            <SessionsPanel />
          ) : (
            <div className="max-h-[60vh] overflow-hidden rounded-lg border border-bg-hover/40">
              <MemoPanel />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
