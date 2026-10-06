import { useState } from 'react'
import { ArrowLeft, CheckCircle2, Play, ShieldCheck, Sparkles } from 'lucide-react'
import { conversationApi } from '@/lib/conversationApi'
import { navigate, paths } from '@/lib/router'
import { ErrorState, Page, PageHeader, PrimaryButton, SecondaryButton, StatusBadge } from '@/components/os/ui'

type Demo = Awaited<ReturnType<typeof conversationApi.demo>>

export default function ConversationOnboardingPage() {
  const [demo, setDemo] = useState<Demo | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  const runDemo = async () => {
    setRunning(true); setError('')
    try { setDemo(await conversationApi.demo()) }
    catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setRunning(false) }
  }

  const complete = () => {
    try {
      window.localStorage.setItem('chengzhu-conversation-optin', '1')
      window.localStorage.setItem('chengzhu-product-profile', 'conversation')
    } catch { /* storage can be unavailable */ }
    navigate(paths.conversationHome())
  }

  const back = () => {
    try { window.localStorage.setItem('chengzhu-product-profile', 'interview') } catch { /* noop */ }
    navigate(paths.home())
  }

  return (
    <Page wide testId="conversation-onboarding">
      <button type="button" onClick={back} className="mb-3 inline-flex items-center gap-1 text-xs text-text-muted hover:text-text-primary">
        <ArrowLeft className="h-3.5 w-3.5" /> 返回面试
      </button>
      <PageHeader
        eyebrow="Conversation Beta · Opt-in"
        title="把成竹用于真实对话"
        subtitle="把过去真正发生过的事带进下一场对话，并在值得开口的时候提醒你。默认本地、私密、不开录音、不自动写外部系统。"
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="rounded-2xl border border-bg-tertiary bg-bg-secondary/25 p-5">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-accent-blue" />
            <h2 className="text-sm font-semibold text-text-primary">先确认工作边界</h2>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {[
              ['默认记录', 'NOTES_ONLY；需要转写时每场 Preflight 再开启。'],
              ['默认处理', 'LOCAL；不会因 provider 故障静默切到更宽松模式。'],
              ['外部动作', 'Draft only；用户确认草稿也不等于已经发送。'],
              ['身份', '音频通道不是人物身份；不会默认做长期 voice biometric identity。'],
              ['真相', 'Proposal 不等于 Decision；模型抽取默认只是待确认 Candidate。'],
              ['证据', '真实用户证据仍待补；Dry Run 只证明工程行为。'],
            ].map(([title, body]) => (
              <article key={title} className="rounded-xl bg-bg-primary/65 p-3">
                <h3 className="text-xs font-semibold text-text-primary">{title}</h3>
                <p className="mt-1 text-[11px] leading-relaxed text-text-muted">{body}</p>
              </article>
            ))}
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <PrimaryButton onClick={runDemo} disabled={running} icon={<Play className="h-3.5 w-3.5" />}>
              {running ? '运行中…' : '运行 30–60 秒等价 Dry Run'}
            </PrimaryButton>
            <SecondaryButton onClick={complete}>跳过 Demo，直接开启</SecondaryButton>
          </div>
          {error ? <div className="mt-3"><ErrorState message={error} /></div> : null}

          {demo ? (
            <div className="mt-5" data-testid="conversation-dry-run">
              <div className="flex flex-wrap items-center gap-2">
                <Sparkles className="h-4 w-4 text-accent-blue" />
                <h2 className="text-sm font-semibold text-text-primary">{demo.title}</h2>
                <StatusBadge tone="warn">{demo.evidence}</StatusBadge>
              </div>
              <p className="mt-1 text-xs text-text-muted">目标：{demo.goal}</p>
              <ol className="mt-4 space-y-2">
                {demo.steps.map((step, index) => (
                  <li key={step.kind} className="rounded-xl border border-bg-tertiary/70 p-3">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-bg-tertiary text-[10px] font-bold text-text-secondary">{index + 1}</span>
                      <span className="text-xs font-semibold text-text-primary">{step.title}</span>
                      <StatusBadge tone={step.kind === 'SILENT' ? 'muted' : step.kind === 'CONTRIBUTION_OPPORTUNITY' ? 'info' : 'ok'}>{step.kind}</StatusBadge>
                    </div>
                    <p className="mt-2 text-xs text-text-secondary">{step.input}</p>
                    <p className="mt-1 text-xs font-medium text-text-primary">→ {step.output}</p>
                    {step.source ? <p className="mt-1 text-[10px] text-text-muted">来源：{step.source}</p> : null}
                  </li>
                ))}
              </ol>
              <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl bg-accent-blue/5 p-3">
                <CheckCircle2 className="h-4 w-4 text-status-direct" />
                <p className="flex-1 text-xs text-text-secondary">你刚看到的是确定性 Synthetic Demo，不会写入真实 Space，也不会被统计成真实用户价值证据。</p>
                <PrimaryButton onClick={complete}>开启 Conversation Beta</PrimaryButton>
              </div>
            </div>
          ) : null}
        </section>

        <aside className="rounded-2xl border border-bg-tertiary p-4">
          <h2 className="text-sm font-semibold text-text-primary">开启后第一次建议这样用</h2>
          <ol className="mt-3 space-y-2 text-xs text-text-secondary">
            <li>1. 建一个 Project Sync 或 Design Review Space。</li>
            <li>2. 只带入 1–3 个明确来源或 Quick Note。</li>
            <li>3. Preflight 选择 Notes Only，先跑一场低风险真实对话。</li>
            <li>4. 会后逐项确认 Decision / Commitment / Open Question。</li>
            <li>5. 下一场观察 Recall 是否真的帮到你，而不是看会议数量。</li>
          </ol>
          <p className="mt-4 text-[11px] leading-relaxed text-text-muted">Calendar、邮件、任务系统等连接会在你明确授权后才接入；当前不会自动扫描或导入。</p>
        </aside>
      </div>
    </Page>
  )
}
