/** Keyboard-openable Quick Notes drawer; read-only while a Live session runs. */
import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { useRouter } from '@/lib/router'
import { useOsStore } from '@/stores/osStore'
import QuickNotesPanel from './QuickNotesPanel'

export default function QuickNotesDrawer() {
  const open = useOsStore((s) => s.quickNotesOpen)
  const setOpen = useOsStore((s) => s.setQuickNotes)
  const goalId = useOsStore((s) => s.live?.goalId ?? s.contextGoalId)
  const inLive = useRouter((s) => s.route.name === 'live')
  const ref = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', onKey)
    ref.current?.focus()
    return () => window.removeEventListener('keydown', onKey)
  }, [open, setOpen])
  if (!open) return null
  return (
    <aside ref={ref} tabIndex={-1} role="dialog" aria-label="速记" className="fixed right-0 top-0 bottom-0 z-50 w-full sm:w-[380px] overflow-y-auto border-l border-bg-hover bg-bg-primary p-4 shadow-2xl animate-slide-left" data-testid="quick-notes-drawer">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text-primary">速记{inLive ? '（上场中只读）' : ''}</h2>
        <button type="button" aria-label="关闭速记" onClick={() => setOpen(false)} className="rounded-lg p-1.5 text-text-muted hover:bg-bg-hover"><X className="h-4 w-4" aria-hidden /></button>
      </div>
      <QuickNotesPanel goalId={goalId} readOnly={inLive} context={inLive ? 'live' : 'library'} />
    </aside>
  )
}
