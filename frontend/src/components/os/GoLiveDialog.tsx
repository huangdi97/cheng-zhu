/**
 * Go Live → Preflight 3.0 (canonical §17). Lists every input of the coming
 * session with its origin (我的成竹 / Goal 默认 / 本场覆盖 / 系统默认).
 * Overrides chosen here apply to this session only.
 */
import { useEffect, useState } from 'react'
import { navigate, paths } from '@/lib/router'
import { productApi, type Preflight } from '@/lib/productApi'
import { setLiveContextLabel } from '@/lib/liveContext'
import { useOsStore } from '@/stores/osStore'
import { Dialog } from './CreateGoalDialog'
import { ErrorState, Field, inputCls, Loading, PrimaryButton, SecondaryButton, StatusBadge, useAsync } from './ui'

const OVERRIDABLE: Record<string, Array<[string, string]>> = {
  answer_language: [['中文', '中文'], ['English', 'English'], ['FOLLOW_INTERVIEW', '跟随面试语言']],
  whisper_language: [['auto', '自动识别'], ['zh', '中文'], ['en', 'English']],
  ai_policy_mode: [['AI_FORBIDDEN', '禁止 AI'], ['AI_LIMITED', '有限 AI'], ['AI_ALLOWED', '允许 AI'], ['AI_EXPECTED', '要求使用 AI']],
  human_assistance_policy: [['HUMAN_FORBIDDEN', '禁止真人辅助'], ['HUMAN_PRACTICE_ONLY', '仅练习'], ['HUMAN_ALLOWED', '允许真人辅助']],
  share_privacy_mode: [['OFF', '关闭'], ['PRIVATE_OVERLAY', '私密浮窗']],
}

const GROUPS: Array<[string, string[]]> = [
  ['本场内容', ['goal', 'resume', 'skill_cards', 'stories', 'knowledge', 'materials', 'quick_notes']],
  ['语言与模型', ['answer_language', 'whisper_language', 'language', 'technical_term_policy', 'active_model']],
  ['音频与识别', ['audio', 'stt', 'screen_context']],
  ['辅助与隐私', ['ai_policy_mode', 'human_assistance_policy', 'share_privacy_mode']],
]

function originTone(origin: string): 'info' | 'warn' | 'muted' | 'ok' {
  if (origin === 'SESSION') return 'warn'
  if (origin === 'GOAL') return 'info'
  if (origin === 'PERSON') return 'ok'
  return 'muted'
}

export default function GoLiveDialog() {
  const open = useOsStore((s) => s.goLiveOpen)
  const close = useOsStore((s) => s.closeGoLive)
  const initialGoal = useOsStore((s) => s.goLiveGoalId)
  if (!open) return null
  return <GoLiveInner initialGoal={initialGoal} close={close} />
}

function GoLiveInner({ initialGoal, close }: { initialGoal: string | null; close: () => void }) {
  const setLive = useOsStore((s) => s.setLive)
  const goals = useAsync(() => productApi.goals('ACTIVE'), [])
  const [goalId, setGoalId] = useState(initialGoal ?? '')
  const [overrides, setOverrides] = useState<Record<string, string>>({})
  const [pre, setPre] = useState<Preflight | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!goalId && goals.data?.items.length === 1) setGoalId(goals.data.items[0].id)
  }, [goalId, goals.data])

  useEffect(() => {
    if (!goalId) { setPre(null); return }
    let alive = true
    setError(null)
    productApi.preflight(goalId, overrides).then((p) => alive && setPre(p)).catch((e) => alive && setError(e instanceof Error ? e.message : '加载失败'))
    return () => { alive = false }
  }, [goalId, overrides])

  const start = async () => {
    if (!goalId) return
    setBusy(true)
    try {
      const res = await productApi.liveStart(goalId, overrides)
      const title = pre?.goal.title ?? ''
      setLive({ sessionId: res.session_id, goalId, goalTitle: title, startedAt: Date.now() })
      setLiveContextLabel(title.split(' · ')[0] ?? title)
      close()
      navigate(paths.live(res.session_id))
    } catch (e) {
      setError(e instanceof Error ? e.message : '上场失败')
    } finally {
      setBusy(false)
    }
  }

  const withoutGoal = () => {
    setLive(null)
    setLiveContextLabel('')
    close()
    navigate(paths.live())
  }

  const byKey = Object.fromEntries((pre?.items ?? []).map((i) => [i.key, i]))
  return (
    <Dialog title="上场前检查（Preflight）" onClose={close} labelledBy="golive-title" wide>
      <div className="space-y-3" data-testid="preflight">
        <Field label="这一场属于哪个求职目标？">
          <select className={inputCls} value={goalId} onChange={(e) => { setGoalId(e.target.value); setOverrides({}) }}>
            <option value="">选择目标</option>
            {(goals.data?.items ?? []).map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}
          </select>
        </Field>
        {error ? <ErrorState message={error} /> : null}
        {goalId && !pre && !error ? <Loading label="正在准备本场内容…" /> : null}
        {pre ? (
          <div className="space-y-3">
            {GROUPS.map(([title, keys]) => (
              <section key={title} aria-label={title}>
                <h3 className="text-xs font-semibold text-text-secondary">{title}</h3>
                <ul className="mt-1 divide-y divide-bg-tertiary/60 rounded-xl border border-bg-hover/50">
                  {keys.filter((k) => byKey[k]).map((k) => {
                    const item = byKey[k]
                    const opts = OVERRIDABLE[k]
                    return (
                      <li key={k} className="flex flex-wrap items-center gap-2 px-3 py-1.5 text-xs">
                        <span className="w-24 flex-shrink-0 text-text-muted">{item.label}</span>
                        {opts ? (
                          <select aria-label={`${item.label}（本场）`} className="rounded-lg border border-bg-hover bg-bg-primary px-2 py-0.5 text-xs" value={String(item.value)}
                            onChange={(e) => setOverrides((o) => ({ ...o, [k]: e.target.value }))}>
                            {opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                          </select>
                        ) : <span className="min-w-0 flex-1 truncate text-text-primary">{String(item.value)}</span>}
                        <span className="ml-auto"><StatusBadge tone={item.ok ? originTone(item.origin) : 'risk'}>{item.ok ? item.origin_label : item.hint || '需要处理'}</StatusBadge></span>
                        {item.ok && item.hint ? <span className="w-full text-[11px] text-status-inferred">{item.hint}</span> : null}
                      </li>
                    )
                  })}
                </ul>
              </section>
            ))}
            {byKey.human_assistance_policy?.value === 'HUMAN_ALLOWED' ? (
              <p className="text-[11px] text-text-secondary">本场允许真人辅助：教练的建议会单独标为「教练」，不会被当作你的证据。</p>
            ) : null}
            <p className="text-[11px] text-text-muted">{pre.share_privacy_note}</p>
            <div className="flex flex-wrap gap-2">
              <SecondaryButton onClick={() => { close(); navigate(paths.settings('speech')) }}>检测麦克风与系统音频</SecondaryButton>
            </div>
          </div>
        ) : null}
        <div className="flex flex-wrap justify-between gap-2 border-t border-bg-tertiary/70 pt-3">
          <SecondaryButton onClick={withoutGoal}>不选目标，直接进入</SecondaryButton>
          <div className="flex gap-2">
            <SecondaryButton onClick={close}>取消</SecondaryButton>
            <PrimaryButton testId="preflight-start" disabled={!goalId || !pre || busy} onClick={() => void start()}>{busy ? '冻结本场内容…' : '开始上场'}</PrimaryButton>
          </div>
        </div>
      </div>
    </Dialog>
  )
}
