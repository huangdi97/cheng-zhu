import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { navigate, paths } from '@/lib/router'
import { productApi } from '@/lib/productApi'
import { useOsStore } from '@/stores/osStore'
import { Field, inputCls, PrimaryButton, SecondaryButton } from './ui'

export function Dialog({ title, onClose, children, labelledBy, wide = false }: {
  title: string
  onClose: () => void
  children: React.ReactNode
  labelledBy: string
  wide?: boolean
}) {
  const ref = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    ref.current?.querySelector<HTMLElement>('input, textarea, select, button')?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'Tab' && ref.current) {
        const focusables = Array.from(ref.current.querySelectorAll<HTMLElement>('button, input, textarea, select, [tabindex="0"]'))
          .filter((el) => !el.hasAttribute('disabled'))
        if (!focusables.length) return
        const first = focusables[0]
        const last = focusables[focusables.length - 1]
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      previous?.focus?.()
    }
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/30 p-0 sm:p-4" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby={labelledBy}
        className={`w-full ${wide ? 'sm:max-w-2xl' : 'sm:max-w-lg'} max-h-[92vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl border border-bg-hover bg-bg-primary p-4 shadow-xl animate-fade-up`}>
        <div className="flex items-center justify-between pb-3">
          <h2 id={labelledBy} className="text-base font-semibold text-text-primary">{title}</h2>
          <button type="button" onClick={onClose} aria-label="关闭" className="rounded-lg p-1.5 text-text-muted hover:bg-bg-hover hover:text-text-primary">
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

function toLocalInput(ts: number | null): string {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function fromLocalInput(value: string): number | null {
  if (!value) return null
  const t = new Date(value).getTime()
  return Number.isFinite(t) ? Math.round(t / 1000) : null
}

export { toLocalInput }

export default function CreateGoalDialog() {
  const open = useOsStore((s) => s.createGoalOpen)
  const close = useOsStore((s) => s.closeCreateGoal)
  const [company, setCompany] = useState('')
  const [role, setRole] = useState('')
  const [jd, setJd] = useState('')
  const [round, setRound] = useState('')
  const [when, setWhen] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (!open) return null
  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      const goal = await productApi.createGoal({ company, role, jd, interview_round: round, next_interview_at: fromLocalInput(when) })
      close()
      setCompany(''); setRole(''); setJd(''); setRound(''); setWhen('')
      navigate(paths.goal(goal.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : '创建失败')
    } finally {
      setBusy(false)
    }
  }
  return (
    <Dialog title="创建求职目标" onClose={close} labelledBy="create-goal-title">
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); void submit() }}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="公司"><input className={inputCls} value={company} onChange={(e) => setCompany(e.target.value)} placeholder="例如 MindRank" /></Field>
          <Field label="岗位"><input className={inputCls} value={role} onChange={(e) => setRole(e.target.value)} placeholder="例如 AIDD Agent Engineer" /></Field>
        </div>
        <Field label="JD（可稍后补充）" hint="JD 只属于这个目标，用来生成 Gap Map 和 Question Graph。">
          <textarea className={`${inputCls} min-h-[96px]`} value={jd} onChange={(e) => setJd(e.target.value)} />
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="下一轮（可选）"><input className={inputCls} value={round} onChange={(e) => setRound(e.target.value)} placeholder="技术二面" /></Field>
          <Field label="时间（可选）"><input type="datetime-local" className={inputCls} value={when} onChange={(e) => setWhen(e.target.value)} /></Field>
        </div>
        {error ? <p role="alert" className="text-xs text-status-risk">{error}</p> : null}
        <div className="flex justify-end gap-2 pt-1">
          <SecondaryButton onClick={close}>取消</SecondaryButton>
          <PrimaryButton type="submit" disabled={busy || (!company.trim() && !role.trim())}>{busy ? '创建中…' : '创建目标'}</PrimaryButton>
        </div>
      </form>
    </Dialog>
  )
}
