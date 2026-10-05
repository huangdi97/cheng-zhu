/**
 * v1.3 workbench primitives: quiet, legible, one primary action per screen.
 * Status is always icon + text; secondary actions live in an ⋯ menu.
 */
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, CircleDashed, Loader2, MoreHorizontal, RefreshCw, XCircle } from 'lucide-react'

export function PageHeader({ title, subtitle, actions, eyebrow }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-3 pb-4">
      <div className="min-w-0">
        {eyebrow ? <div className="text-[11px] font-medium text-text-muted">{eyebrow}</div> : null}
        <h1 className="text-lg font-semibold text-text-primary leading-snug break-words">{title}</h1>
        {subtitle ? <p className="mt-0.5 text-xs text-text-muted">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  )
}

export function Page({ children, testId, wide = false }: { children: ReactNode; testId?: string; wide?: boolean }) {
  return (
    <main className="flex-1 min-h-0 overflow-y-auto" data-testid={testId}>
      <div className={`mx-auto w-full ${wide ? 'max-w-6xl' : 'max-w-4xl'} px-4 md:px-6 py-5`}>{children}</div>
    </main>
  )
}

export function Section({ title, children, action, id }: { title: ReactNode; children: ReactNode; action?: ReactNode; id?: string }) {
  const headingId = useId()
  return (
    <section aria-labelledby={headingId} id={id} className="py-3 border-t border-bg-tertiary/70 first:border-t-0">
      <div className="flex items-center justify-between gap-2 pb-2">
        <h2 id={headingId} className="text-sm font-semibold text-text-primary">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

type ButtonProps = {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  type?: 'button' | 'submit'
  title?: string
  ariaLabel?: string
  testId?: string
  icon?: ReactNode
}

export function PrimaryButton({ children, onClick, disabled, type = 'button', title, ariaLabel, testId, icon }: ButtonProps) {
  return (
    <button type={type} onClick={onClick} disabled={disabled} title={title} aria-label={ariaLabel} data-testid={testId}
      className="btn-primary inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold disabled:opacity-50 disabled:cursor-not-allowed min-h-[32px]">
      {icon}
      {children}
    </button>
  )
}

export function SecondaryButton({ children, onClick, disabled, type = 'button', title, ariaLabel, testId, icon }: ButtonProps) {
  return (
    <button type={type} onClick={onClick} disabled={disabled} title={title} aria-label={ariaLabel} data-testid={testId}
      className="btn-subtle inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed min-h-[32px]">
      {icon}
      {children}
    </button>
  )
}

export function TextButton({ children, onClick, disabled, title, ariaLabel, testId }: ButtonProps) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} title={title} aria-label={ariaLabel} data-testid={testId}
      className="inline-flex items-center gap-1 rounded-lg px-1.5 py-1 text-xs font-medium text-accent-blue hover:underline disabled:opacity-50">
      {children}
    </button>
  )
}

export type Tone = 'ok' | 'info' | 'warn' | 'risk' | 'muted' | 'busy'

const TONE: Record<Tone, { cls: string; Icon: typeof CheckCircle2 }> = {
  ok: { cls: 'text-status-direct bg-status-direct/10 border-status-direct/25', Icon: CheckCircle2 },
  info: { cls: 'text-accent-blue bg-accent-blue/10 border-accent-blue/25', Icon: CircleDashed },
  warn: { cls: 'text-status-inferred bg-status-inferred/10 border-status-inferred/25', Icon: AlertTriangle },
  risk: { cls: 'text-status-risk bg-status-risk/10 border-status-risk/25', Icon: XCircle },
  muted: { cls: 'text-text-muted bg-bg-tertiary/50 border-bg-hover/50', Icon: CircleDashed },
  busy: { cls: 'text-accent-blue bg-accent-blue/10 border-accent-blue/25', Icon: Loader2 },
}

/** Status = icon + text, never color alone. */
export function StatusBadge({ tone, children, title }: { tone: Tone; children: ReactNode; title?: string }) {
  const { cls, Icon } = TONE[tone]
  return (
    <span title={title} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${cls}`}>
      <Icon className={`h-3 w-3 ${tone === 'busy' ? 'motion-safe:animate-spin' : ''}`} aria-hidden />
      {children}
    </span>
  )
}

export function EmptyState({ title, body, action, testId }: { title: ReactNode; body?: ReactNode; action?: ReactNode; testId?: string }) {
  return (
    <div data-testid={testId} className="rounded-2xl border border-dashed border-bg-hover p-6 text-center">
      <p className="text-sm font-medium text-text-primary">{title}</p>
      {body ? <p className="mt-1 text-xs text-text-muted">{body}</p> : null}
      {action ? <div className="mt-3 flex justify-center">{action}</div> : null}
    </div>
  )
}

/** Every error offers a next step (canonical §19). */
export function ErrorState({ message, onRetry, extra }: { message: string; onRetry?: () => void; extra?: ReactNode }) {
  return (
    <div role="alert" className="rounded-2xl border border-status-risk/30 bg-status-risk/5 p-4 text-sm">
      <div className="flex items-start gap-2 text-status-risk">
        <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden />
        <span className="break-words">{message}</span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {onRetry ? <SecondaryButton onClick={onRetry} icon={<RefreshCw className="h-3.5 w-3.5" aria-hidden />}>重试</SecondaryButton> : null}
        {extra}
      </div>
    </div>
  )
}

export function Loading({ label = '加载中…' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-6 text-xs text-text-muted">
      <Loader2 className="h-4 w-4 motion-safe:animate-spin" aria-hidden /> {label}
    </div>
  )
}

export interface MenuAction {
  key: string
  label: string
  onSelect: () => void
  danger?: boolean
  disabled?: boolean
}

/** ⋯ contextual actions: keyboard-operable menu (Arrow keys / Enter / Escape). */
export function ActionMenu({ actions, label = '更多操作' }: { actions: MenuAction[]; label?: string }) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const ref = useRef<HTMLDivElement | null>(null)
  const buttonRef = useRef<HTMLButtonElement | null>(null)
  const menuId = useId()
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener('mousedown', onDown)
    return () => window.removeEventListener('mousedown', onDown)
  }, [open])
  if (!actions.length) return null
  const choose = (a: MenuAction) => {
    if (a.disabled) return
    setOpen(false)
    buttonRef.current?.focus()
    a.onSelect()
  }
  return (
    <div className="relative" ref={ref}>
      <button ref={buttonRef} type="button" aria-label={label} title={label} aria-haspopup="menu" aria-expanded={open} aria-controls={menuId}
        onClick={() => { setOpen((v) => !v); setActive(0) }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive(0) }
        }}
        className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-text-muted hover:bg-bg-hover hover:text-text-primary">
        <MoreHorizontal className="h-4 w-4" aria-hidden />
      </button>
      {open ? (
        <div id={menuId} role="menu" aria-label={label} tabIndex={-1}
          ref={(el) => el?.focus()}
          onKeyDown={(e) => {
            if (e.key === 'Escape') { e.preventDefault(); setOpen(false); buttonRef.current?.focus() }
            if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => (i + 1) % actions.length) }
            if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => (i - 1 + actions.length) % actions.length) }
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(actions[active]) }
          }}
          className="absolute right-0 top-[calc(100%+4px)] z-40 min-w-[168px] glass-popover rounded-xl p-1 animate-fade-up">
          {actions.map((a, i) => (
            <button key={a.key} type="button" role="menuitem" disabled={a.disabled} tabIndex={-1}
              onMouseEnter={() => setActive(i)} onClick={() => choose(a)}
              className={`flex w-full items-center rounded-lg px-2.5 py-1.5 text-left text-xs ${i === active ? 'bg-bg-hover' : ''} ${a.danger ? 'text-status-risk' : 'text-text-primary'} disabled:opacity-50`}>
              {a.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function Tabs<T extends string>({ tabs, value, onChange, label }: { tabs: Array<[T, string, number?]>; value: T; onChange: (v: T) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto scrollbar-none border-b border-bg-tertiary/70">
      {tabs.map(([key, text, count]) => (
        <button key={key} type="button" role="tab" aria-selected={value === key} onClick={() => onChange(key)}
          onKeyDown={(e) => {
            const idx = tabs.findIndex(([k]) => k === key)
            if (e.key === 'ArrowRight') onChange(tabs[(idx + 1) % tabs.length][0])
            if (e.key === 'ArrowLeft') onChange(tabs[(idx - 1 + tabs.length) % tabs.length][0])
          }}
          className={`relative whitespace-nowrap px-3 py-2 text-xs font-medium ${value === key ? 'text-text-primary' : 'text-text-muted hover:text-text-primary'}`}>
          {text}
          {typeof count === 'number' && count > 0 ? <span className="ml-1 rounded-full bg-accent-amber/15 px-1.5 text-[10px] text-status-inferred">{count}</span> : null}
          {value === key ? <span className="absolute inset-x-2 -bottom-px h-0.5 rounded bg-accent-blue" aria-hidden /> : null}
        </button>
      ))}
    </div>
  )
}

/** Wraps one control: the nested input is labelled implicitly. */
export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block text-xs">
      <span className="font-medium text-text-secondary">{label}</span>
      <span className="mt-1 block">{children}</span>
      {hint ? <span className="mt-0.5 block text-[11px] text-text-muted">{hint}</span> : null}
    </label>
  )
}

export const inputCls =
  'w-full rounded-xl border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-blue/60 outline-none'

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const seq = useRef(0)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(fn, deps)
  const reload = useCallback(async () => {
    const id = ++seq.current
    setLoading(true)
    setError(null)
    try {
      const value = await run()
      if (id === seq.current) setData(value)
    } catch (e) {
      if (id === seq.current) setError(e instanceof Error ? e.message : String(e))
    } finally {
      if (id === seq.current) setLoading(false)
    }
  }, [run])
  useEffect(() => {
    void reload()
  }, [reload])
  return { data, error, loading, reload, setData }
}

export function formatWhen(ts: number | null | undefined): string {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const now = new Date()
  const day = 86400000
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const diff = Math.round((startOf(d) - startOf(now)) / day)
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  if (diff === 0) return `今天 ${hm}`
  if (diff === 1) return `明天 ${hm}`
  if (diff === -1) return `昨天 ${hm}`
  return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')} ${hm}`
}
