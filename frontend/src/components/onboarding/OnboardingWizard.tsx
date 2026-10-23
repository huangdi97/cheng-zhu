import { useCallback, useEffect, useRef, useState } from 'react'
import { CheckCircle2, CircleAlert, Loader2 } from 'lucide-react'
import { api, getErrorMessage } from '@/lib/api'
import { updateConfigAndRefresh } from '@/lib/configSync'
import { navigate, paths } from '@/lib/router'
import { useInterviewStore } from '@/stores/configStore'
import { productApi, track } from '@/lib/productApi'
import GuidedFirstPractice from './GuidedFirstPractice'

/**
 * First run answers three questions and nothing else:
 *
 *   01 理解      — what Chengzhu is, and why everything hangs off one Goal;
 *   02 创建目标  — the few facts needed to say "this is the interview I am
 *                  getting ready for";
 *   03 就绪      — what happens next, plus an honest one-line machine status.
 *
 * Environment work that used to live here (model keys, STT, microphone,
 * loopback capture, resume import, privacy defaults) belongs to Settings and to
 * the blocker-first Preflight, where it is checked at the moment it matters.
 * This surface must never turn into a setup wizard.
 */

interface Diagnostics {
  data_writable: boolean
  has_usable_model: boolean
  stt_provider: string
  has_microphone: boolean
  has_system_audio: boolean
}

const STEPS = [
  { key: 'understand', label: '理解', title: '成竹围绕一个目标工作' },
  { key: 'goal', label: '创建目标', title: '你下一场在准备什么？' },
  { key: 'ready', label: '就绪', title: '接下来从这里开始' },
] as const

const FLOW = [
  { step: '准备', detail: '把简历、事实和资料收进这一个目标。' },
  { step: '练习', detail: '针对下一场的重点先练一轮，拿到可验证的反馈。' },
  { step: '上场', detail: '上场前检查一次；面试中只出现当前需要的一条提示。' },
  { step: '复盘', detail: '把这一场真实说过的话写回下一步。' },
]

function Row({ step, detail }: { step: string; detail: string }) {
  return (
    <li className="grid gap-1 border-t border-bg-tertiary/70 py-2.5 sm:grid-cols-[72px_minmax(0,1fr)] sm:gap-4">
      <span className="text-sm font-medium text-text-primary">{step}</span>
      <span className="text-xs leading-5 text-text-secondary">{detail}</span>
    </li>
  )
}

function MachineStatus({ diag }: { diag: Diagnostics | null }) {
  if (!diag) {
    return (
      <p className="flex items-center gap-2 text-xs text-text-muted">
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        正在读取这台电脑的状态…
      </p>
    )
  }
  const checks = [
    { label: '模型', ok: diag.has_usable_model },
    { label: '麦克风', ok: diag.has_microphone },
    { label: '系统音频', ok: diag.has_system_audio },
    { label: '数据目录', ok: diag.data_writable },
  ]
  return (
    <div className="space-y-1.5">
      <p className="text-[11px] font-medium tracking-[0.12em] text-text-muted">这台电脑</p>
      <ul className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {checks.map((check) => (
          <li key={check.label} className="flex items-center gap-1.5 text-xs">
            {check.ok
              ? <CheckCircle2 className="h-3.5 w-3.5 text-status-direct" aria-hidden />
              : <CircleAlert className="h-3.5 w-3.5 text-status-risk" aria-hidden />}
            <span className="text-text-secondary">{check.label}</span>
            <span className={check.ok ? 'text-text-muted' : 'font-medium text-status-risk'}>{check.ok ? '就绪' : '未就绪'}</span>
          </li>
        ))}
      </ul>
      <p className="text-[11px] leading-5 text-text-muted">
        没就绪的项不会挡在这里：上场前还会再检查一次，缺什么就在那一步修。
      </p>
    </div>
  )
}

export default function OnboardingWizard() {
  const config = useInterviewStore((s) => s.config)
  const pushToast = useInterviewStore((s) => s.pushToast)
  const [step, setStep] = useState(0)
  const [diag, setDiag] = useState<Diagnostics | null>(null)
  const [company, setCompany] = useState('')
  const [role, setRole] = useState('')
  const [jd, setJd] = useState('')
  const [round, setRound] = useState('')
  const [when, setWhen] = useState('')
  const [createdGoalId, setCreatedGoalId] = useState<string | null>(null)
  const [guided, setGuided] = useState(false)
  const [showGuided, setShowGuided] = useState(false)
  const [dismissed, setDismissed] = useState(false)
  const [busy, setBusy] = useState(false)

  const open = config?.onboarding_completed === false && !dismissed
  const markGuidedComplete = useCallback(() => setGuided(true), [])

  useEffect(() => {
    if (!open) return
    api.intelDiagnostics().then((d) => setDiag(d as unknown as Diagnostics)).catch(() => setDiag(null))
  }, [open])
  const panelRef = useRef<HTMLDivElement | null>(null)

  const finish = useCallback(async () => {
    try {
      await updateConfigAndRefresh({ onboarding_completed: true })
      track('onboarding_completed', { guided, steps: STEPS.length })
    } catch (error) {
      pushToast(getErrorMessage(error, '保存失败'), 'error')
    }
    setDismissed(true)
    if (createdGoalId) navigate(paths.goal(createdGoalId))
  }, [createdGoalId, guided, pushToast])

  // Modal contract, same as the shared Dialog: focus moves to the primary action
  // of the step, Tab stays inside the panel, Escape leaves first run.
  useEffect(() => {
    if (!open) return
    const panel = panelRef.current
    if (!panel) return
    const target = panel.querySelector<HTMLElement>('[data-testid="onboarding-next"], [data-testid="onboarding-finish"], [data-testid="onboarding-skip"]')
    ;(target ?? panel).focus()
  }, [open, step])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      const panel = panelRef.current
      if (!panel) return
      if (event.key === 'Escape') {
        event.preventDefault()
        void finish()
        return
      }
      if (event.key !== 'Tab') return
      const focusables = Array.from(panel.querySelectorAll<HTMLElement>('button, input, textarea, select, summary, [tabindex="0"]'))
        .filter((el) => !el.hasAttribute('disabled') && el.offsetParent !== null)
      if (!focusables.length) return
      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      const active = document.activeElement as HTMLElement | null
      if (!event.shiftKey && active === last) { event.preventDefault(); first.focus() }
      else if (event.shiftKey && active === first) { event.preventDefault(); last.focus() }
      else if (active && !panel.contains(active)) { event.preventDefault(); first.focus() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, finish])

  if (!open) return null

  const createGoal = async () => {
    if (!role.trim()) {
      pushToast('请填写目标岗位；公司可以暂时留空', 'warn')
      return false
    }
    setBusy(true)
    try {
      const goal = await productApi.createGoal({
        company: company.trim(),
        role: role.trim(),
        jd,
        interview_round: round.trim(),
        next_interview_at: when ? Math.round(new Date(when).getTime() / 1000) : null,
      })
      setCreatedGoalId(goal.id)
      return true
    } catch (error) {
      pushToast(getErrorMessage(error, '创建求职目标失败'), 'error')
      return false
    } finally {
      setBusy(false)
    }
  }

  const next = async () => {
    if (STEPS[step].key === 'goal' && !createdGoalId && !(await createGoal())) return
    setStep((s) => Math.min(STEPS.length - 1, s + 1))
  }

  const current = STEPS[step]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-labelledby="onboarding-title" data-testid="onboarding">
      <div ref={panelRef} tabIndex={-1} className="flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-bg-hover/70 bg-bg-secondary outline-none">
        <header className="border-b border-bg-tertiary/70 px-6 py-4">
          <div className="flex items-center justify-between gap-4">
            <p className="text-[11px] font-medium tracking-[0.14em] text-text-muted">
              FIRST RUN · {step + 1} / {STEPS.length}
            </p>
            <ol aria-label="首次引导阶段" className="flex items-center gap-3">
              {STEPS.map((item, index) => (
                <li
                  key={item.key}
                  aria-current={index === step ? 'step' : undefined}
                  className={`text-[11px] ${index === step ? 'font-semibold text-text-primary' : index < step ? 'text-text-secondary' : 'text-text-muted'}`}
                >
                  {String(index + 1).padStart(2, '0')} {item.label}
                </li>
              ))}
            </ol>
          </div>
          <h2 id="onboarding-title" className="mt-2 text-xl font-semibold tracking-tight text-text-primary">{current.title}</h2>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5 text-sm text-text-secondary">
          {current.key === 'understand' && (
            <div className="space-y-4">
              <p className="max-w-xl text-sm leading-6 text-text-primary">
                成竹不给你一堆 AI 功能。它只围绕一个具体的求职目标，把准备、练习、上场和复盘连成一条线。
              </p>
              <ul className="border-b border-bg-tertiary/70">
                {FLOW.map((item) => <Row key={item.step} {...item} />)}
              </ul>
              <p className="text-xs leading-5 text-text-muted">
                之所以先建目标：准备内容和复盘结论都要落回同一场面试，否则它们只是互不相干的笔记。
              </p>
              <p className="text-xs leading-5 text-text-muted">
                数据默认留在这台电脑上；调用模型时才会把必要上下文发给你自己配置的服务商。成竹开源（MIT License）。
              </p>
            </div>
          )}

          {current.key === 'goal' && (
            <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); void next() }}>
              <p className="max-w-xl text-xs leading-5 text-text-muted">
                先写最必要的三项。JD 用来生成准备缺口和可能追问；时间和轮次可以稍后补。
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-xs">
                  <span className="font-medium text-text-secondary">公司</span>
                  <input
                    data-testid="onboarding-goal-company"
                    value={company}
                    onChange={(event) => setCompany(event.target.value)}
                    placeholder="例如 字节跳动"
                    className="mt-1 w-full rounded-lg border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-blue/60 outline-none"
                  />
                </label>
                <label className="block text-xs">
                  <span className="font-medium text-text-secondary">岗位</span>
                  <input
                    data-testid="onboarding-goal-role"
                    value={role}
                    onChange={(event) => setRole(event.target.value)}
                    placeholder="例如 AI 产品经理"
                    className="mt-1 w-full rounded-lg border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-blue/60 outline-none"
                  />
                </label>
              </div>
              <label className="block text-xs">
                <span className="font-medium text-text-secondary">JD / 岗位描述</span>
                <textarea
                  data-testid="onboarding-goal-jd"
                  rows={5}
                  value={jd}
                  onChange={(event) => setJd(event.target.value)}
                  placeholder="粘贴岗位描述，成竹据此判断要补什么"
                  className="mt-1 min-h-[104px] w-full rounded-lg border border-bg-hover bg-bg-primary px-3 py-2 text-sm leading-6 text-text-primary placeholder:text-text-muted focus:border-accent-blue/60 outline-none"
                />
              </label>
              <details className="border-t border-bg-tertiary/70 pt-3 text-xs">
                <summary className="cursor-pointer text-text-secondary">下一轮信息（可选）</summary>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <label className="block">
                    <span className="font-medium text-text-secondary">轮次</span>
                    <input
                      value={round}
                      onChange={(event) => setRound(event.target.value)}
                      placeholder="例如 产品二面"
                      className="mt-1 w-full rounded-lg border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-blue/60 outline-none"
                    />
                  </label>
                  <label className="block">
                    <span className="font-medium text-text-secondary">时间</span>
                    <input
                      type="datetime-local"
                      value={when}
                      onChange={(event) => setWhen(event.target.value)}
                      className="mt-1 w-full rounded-lg border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary focus:border-accent-blue/60 outline-none"
                    />
                  </label>
                </div>
              </details>
              {createdGoalId ? <p className="text-xs text-status-direct">这个目标已经建立，可以继续。</p> : null}
            </form>
          )}

          {current.key === 'ready' && (
            <div className="space-y-4" data-testid="onboarding-complete-step">
              <p className="max-w-xl text-sm leading-6 text-text-primary">
                {createdGoalId ? '目标已建立。' : '可以先进入成竹，之后再建目标。'}
                接下来只记住一条路径：打开目标 → 看下一步重点 → 准备或练习 → 上场 → 复盘。
              </p>
              <ul className="border-b border-bg-tertiary/70">
                {FLOW.map((item) => <Row key={item.step} {...item} />)}
              </ul>
              <MachineStatus diag={diag} />
              <div className="border-t border-bg-tertiary/70 pt-3">
                {showGuided ? (
                  <GuidedFirstPractice goalId={createdGoalId} onCompleted={() => markGuidedComplete()} />
                ) : (
                  <button
                    type="button"
                    data-testid="onboarding-guided-start"
                    onClick={() => setShowGuided(true)}
                    className="text-xs text-text-secondary underline decoration-bg-hover underline-offset-2 hover:text-text-primary"
                  >
                    先用三分钟跑一次演练（可选）
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-bg-tertiary/70 bg-bg-primary/35 px-6 py-3">
          <button type="button" data-testid="onboarding-skip" onClick={() => void finish()} className="text-xs text-text-muted hover:text-text-primary">
            跳过引导
          </button>
          <div className="flex items-center gap-2">
            {step > 0 && (
              <button type="button" onClick={() => setStep((s) => s - 1)} className="rounded-lg border border-bg-hover px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-bg-hover/60">
                上一步
              </button>
            )}
            {step < STEPS.length - 1 ? (
              <button
                type="button"
                data-testid="onboarding-next"
                onClick={() => void next()}
                disabled={busy}
                className="rounded-lg bg-accent-blue px-3.5 py-1.5 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? '创建中…' : current.key === 'goal' ? '创建并继续' : '下一步'}
              </button>
            ) : (
              <button type="button" data-testid="onboarding-finish" onClick={() => void finish()} className="rounded-lg bg-accent-blue px-3.5 py-1.5 text-xs font-semibold text-white">
                进入成竹
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
